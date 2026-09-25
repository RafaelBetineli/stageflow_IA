import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.shared import Cm

from stageflow.template_engine import (
    DocumentGenerator,
    MalformedPlaceholderError,
    MissingPlaceholderValueError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DocumentGeneratorTests(unittest.TestCase):
    def test_project_templates_have_only_well_formed_placeholders(self) -> None:
        templates = sorted((PROJECT_ROOT / "templates").glob("*/*.docx"))
        self.assertTrue(templates)
        for template in templates:
            document = Document(template)
            with self.subTest(template=template.name):
                self.assertEqual(
                    (),
                    DocumentGenerator._collect_malformed_placeholders(document),
                )

    def test_pharmacy_plan_exposes_student_location_and_schedule(self) -> None:
        template = (
            PROJECT_ROOT
            / "templates"
            / "farmacia"
            / "modelo_plano_farmacia_automatizado.docx"
        )
        placeholders = DocumentGenerator._collect_placeholders(Document(template))
        self.assertTrue(
            {"ESTADO_ALUNO", "CAMPUS", "PERIODO"}.issubset(placeholders)
        )

    def test_reports_expose_separate_council_fields(self) -> None:
        templates = sorted(
            (PROJECT_ROOT / "templates").glob("*/modelo_relatorio_*.docx")
        )
        for template in templates:
            placeholders = DocumentGenerator._collect_placeholders(Document(template))
            with self.subTest(template=template.name):
                self.assertIn("SIGLA_CONSELHO_RT", placeholders)
                self.assertIn("NUMERO_CONSELHO_RT", placeholders)

    def test_report_templates_expose_reference_heading_and_placeholder(self) -> None:
        templates = sorted(
            (PROJECT_ROOT / "templates").glob("*/modelo_relatorio_*.docx")
        )
        self.assertTrue(templates)
        for template in templates:
            document = Document(template)
            headings = [
                paragraph
                for paragraph in document.paragraphs
                if paragraph.text.strip().upper() == "REFERÊNCIAS BIBLIOGRÁFICAS"
            ]
            placeholders = [
                paragraph
                for paragraph in document.paragraphs
                if "{{REFERENCIAS}}" in paragraph.text
            ]
            with self.subTest(template=template.name):
                self.assertEqual(1, len(headings))
                self.assertEqual(1, len(placeholders))

    def test_replaces_body_table_header_footer_and_split_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.docx"
            output = root / "output.docx"
            doc = Document()
            paragraph = doc.add_paragraph()
            paragraph.add_run("Aluno: {{NOME_")
            paragraph.add_run("ALUNO}}")
            doc.add_table(rows=1, cols=1).cell(0, 0).text = "RA: {{RA_ALUNO}}"
            doc.sections[0].header.paragraphs[0].text = "{{CABECALHO}}"
            doc.sections[0].footer.paragraphs[0].text = "{{RODAPE}}"
            doc.save(template)

            DocumentGenerator(template).generate(
                {
                    "NOME_ALUNO": "Aluno Exemplo",
                    "RA_ALUNO": "000000",
                    "CABECALHO": "Cabeçalho",
                    "RODAPE": "Rodapé",
                },
                output,
            )

            generated = Document(output)
            self.assertEqual("Aluno: Aluno Exemplo", generated.paragraphs[0].text)
            self.assertEqual("RA: 000000", generated.tables[0].cell(0, 0).text)
            self.assertEqual("Cabeçalho", generated.sections[0].header.paragraphs[0].text)
            self.assertEqual("Rodapé", generated.sections[0].footer.paragraphs[0].text)

    def test_replaces_placeholder_inside_text_box_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.docx"
            output = root / "output.docx"
            doc = Document()
            host = doc.add_paragraph()
            text_box = OxmlElement("w:txbxContent")
            text_box_paragraph = OxmlElement("w:p")
            text_box_run = OxmlElement("w:r")
            text_box_text = OxmlElement("w:t")
            text_box_text.text = "{{PERIODO}}"
            text_box_run.append(text_box_text)
            text_box_paragraph.append(text_box_run)
            text_box.append(text_box_paragraph)
            host._p.append(text_box)
            doc.save(template)

            DocumentGenerator(template).generate({"PERIODO": "Noturno"}, output)

            generated = Document(output)
            text_box_paragraphs = list(
                DocumentGenerator._iter_text_box_paragraphs(
                    generated.element.body,
                    generated,
                )
            )
            self.assertEqual(["Noturno"], [p.text for p in text_box_paragraphs])
            self.assertFalse(DocumentGenerator._collect_placeholders(generated))

    def test_replaces_placeholder_inside_hyperlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.docx"
            output = root / "output.docx"
            doc = Document()
            paragraph = doc.add_paragraph()
            hyperlink = OxmlElement("w:hyperlink")
            run = OxmlElement("w:r")
            text = OxmlElement("w:t")
            text.text = "Atividade: {{TITULO_ATV1}}"
            run.append(text)
            hyperlink.append(run)
            paragraph._p.append(hyperlink)
            doc.save(template)

            DocumentGenerator(template).generate(
                {"TITULO_ATV1": "Conferência de medicamentos"},
                output,
            )

            generated = Document(output)
            self.assertEqual(
                "Atividade: Conferência de medicamentos",
                generated.paragraphs[0].text,
            )
            self.assertFalse(DocumentGenerator._collect_placeholders(generated))

    def test_missing_value_does_not_replace_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.docx"
            output = root / "output.docx"
            doc = Document()
            doc.add_paragraph("{{OBRIGATORIO}}")
            doc.save(template)
            output.write_bytes(b"conteudo anterior")

            with self.assertRaises(MissingPlaceholderValueError):
                DocumentGenerator(template).generate({}, output)

            self.assertEqual(b"conteudo anterior", output.read_bytes())

    def test_malformed_placeholder_does_not_publish_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.docx"
            output = root / "output.docx"
            doc = Document()
            doc.add_paragraph("Cidade: {{CIDADE_ALUNO}} - {{ESTADO_ALUNO")
            doc.save(template)
            output.write_bytes(b"conteudo anterior")

            with self.assertRaisesRegex(
                MalformedPlaceholderError,
                "ESTADO_ALUNO",
            ):
                DocumentGenerator(template).generate(
                    {
                        "CIDADE_ALUNO": "Cidade Exemplo",
                        "ESTADO_ALUNO": "SP",
                    },
                    output,
                )

            self.assertEqual(b"conteudo anterior", output.read_bytes())

    def test_does_not_change_structure_outside_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.docx"
            output = root / "output.docx"
            doc = Document()
            doc.add_paragraph("SUMÁRIO")
            doc.add_paragraph()
            doc.add_paragraph()
            doc.add_paragraph("1. INTRODUÇÃO", style="Heading 1")
            doc.save(template)
            template_bytes = template.read_bytes()

            DocumentGenerator(template).generate({}, output)

            generated = Document(output)
            instructions = generated.element.body.xpath(".//w:instrText")
            self.assertFalse(instructions)
            self.assertEqual(
                ["SUMÁRIO", "", "", "1. INTRODUÇÃO"],
                [paragraph.text for paragraph in generated.paragraphs],
            )
            self.assertEqual(template_bytes, template.read_bytes())

    def test_multiline_value_becomes_real_paragraphs_with_template_format(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.docx"
            output = root / "output.docx"
            doc = Document()
            paragraph = doc.add_paragraph("{{TEXTO}}")
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            paragraph.paragraph_format.left_indent = Cm(1.25)
            paragraph.paragraph_format.space_after = Cm(0.2)
            doc.save(template)

            DocumentGenerator(template).generate(
                {"TEXTO": "Primeiro parágrafo.\n\nSegundo parágrafo.\nTerceiro parágrafo."},
                output,
            )

            generated = Document(output)
            self.assertEqual(
                [
                    "Primeiro parágrafo.",
                    "Segundo parágrafo.",
                    "Terceiro parágrafo.",
                ],
                [paragraph.text for paragraph in generated.paragraphs],
            )
            for generated_paragraph in generated.paragraphs:
                self.assertEqual(
                    WD_ALIGN_PARAGRAPH.JUSTIFY,
                    generated_paragraph.alignment,
                )
                self.assertAlmostEqual(
                    1.25,
                    generated_paragraph.paragraph_format.left_indent.cm,
                    places=2,
                )
                self.assertFalse(generated_paragraph._p.xpath(".//w:br"))


if __name__ == "__main__":
    unittest.main()
