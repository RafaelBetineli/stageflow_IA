import unittest

from stageflow.extraction import HybridExtractor, OllamaClient, RuleBasedExtractor
from stageflow.models import FieldEvidence


class FakeOllama:
    def __init__(self) -> None:
        self.received = ""
        self.candidate_keys = ()

    def extract(self, text, candidate_keys):
        self.received = text
        self.candidate_keys = candidate_keys
        return (
            (FieldEvidence("HORARIO_ESTAGIO", "08h às 14h", "vou das 8h às 14h", "ia"),),
            (),
        )


class DuplicateValueOllama:
    def extract(self, text, candidate_keys):
        return (
            (
                FieldEvidence(
                    "ENDERECO_EMPRESA",
                    "Drogaria Exemplo",
                    "Drogaria Exemplo",
                    "ia",
                ),
            ),
            (),
        )


class RuleBasedExtractorTests(unittest.TestCase):
    def test_normalizes_labels_and_preserves_unrecognized_lines(self) -> None:
        result = RuleBasedExtractor().extract(
            "nome ALUNO: Aluno Exemplo\n"
            "Celular: (00) 00000-0000\n"
            "vou das 8h às 14h\n"
        )

        self.assertEqual("Aluno Exemplo", result.fields["NOME_ALUNO"])
        self.assertEqual("(00) 00000-0000", result.fields["TELEFONE_ALUNO"])
        self.assertEqual(("vou das 8h às 14h",), result.unrecognized_lines)
        self.assertEqual("regra", result.evidence["NOME_ALUNO"].method)

    def test_reports_conflicting_duplicates_without_overwriting_first_value(self) -> None:
        result = RuleBasedExtractor().extract("RA: 111\nRA: 222")

        self.assertEqual("111", result.fields["RA_ALUNO"])
        self.assertEqual(("RA",), result.duplicates)

    def test_recognizes_common_informal_rt_labels(self) -> None:
        result = RuleBasedExtractor().extract(
            "email responsavel tecnico: rt@example.invalid\n"
            "telefone rt: (11) 90000-0000\n"
            "Nome da rt: Profissional Exemplo\n"
            "Local: Drogaria Exemplo"
        )

        self.assertEqual("rt@example.invalid", result.fields["EMAIL_RT"])
        self.assertEqual("(11) 90000-0000", result.fields["TELEFONE_EMPRESA"])
        self.assertEqual("Profissional Exemplo", result.fields["NOME_RT"])
        self.assertEqual("Drogaria Exemplo", result.fields["EMPRESA_FANTASIA"])

    def test_extracts_colon_lists_using_section_context(self) -> None:
        result = RuleBasedExtractor().extract(
            "DADOS NECESSÁRIOS PARA REALIZAÇÃO DO RELATÓRIO DE ESTÁGIO\n"
            "## Identificação do aluno\n"
            "- Nome completo:Aluna Exemplo\n"
            "- Ra:123456789\n"
            "- RG:12345678\n"
            "- CPF:12345678901\n"
            "- Semestre atual:8 semestre\n"
            "- Campus:Memorial\n"
            "- Período:Noturno\n"
            "- Endereço residencial:Rua Exemplo, nº 10\n"
            "- Cidade:Guarulhos\n"
            "- Bairro:Jardim Exemplo\n"
            "- N° celular:11 90000-0000\n"
            "- Endereço de email:aluna@example.invalid\n"
            "- N° apólice seguro de vida:116194\n"
            "- Empresa seguradora:Seguradora Exemplo S.A.\n"
            "- Vigência do seguro:09/09/2026 ate 09/09/2029\n"
            "## Identificação da empresa\n"
            "Nome Fantasia: Drogaria Exemplo\n"
            "Nome da Razão Social: Drogaria Exemplo S/A.\n"
            "CNPJ n°: 12.345.678.0001-99\n"
            "Telefone: (11) 2402-4392\n"
            "Endereço: Avenida Exemplo, nº 100\n"
            "Cidade: Guarulhos - SP\n"
            "Bairro: Vila Exemplo\n"
            "Nome do Responsável Técnico (RT): Profissional Exemplo\n"
            "Sigla Conselho de classe: CRF nº: 70590\n"
            "E-mail RT: profissional@example.invalid\n"
        )

        expected = {
            "NOME_ALUNO": "Aluna Exemplo",
            "RA_ALUNO": "123456789",
            "RG": "12345678",
            "CPF": "12345678901",
            "SEMESTRE": "8 semestre",
            "CAMPUS": "Memorial",
            "PERIODO": "Noturno",
            "ENDERECO_ALUNO": "Rua Exemplo, nº 10",
            "CIDADE_ALUNO": "Guarulhos",
            "BAIRRO_ALUNO": "Jardim Exemplo",
            "TELEFONE_ALUNO": "11 90000-0000",
            "EMAIL_ALUNO": "aluna@example.invalid",
            "APOLICE": "116194",
            "SEGURADORA": "Seguradora Exemplo S.A.",
            "DATA_INICIO_VIGENCIA": "09/09/2026",
            "DATA_FIM_VIGENCIA": "09/09/2029",
            "EMPRESA_FANTASIA": "Drogaria Exemplo",
            "EMPRESA": "Drogaria Exemplo S/A.",
            "CNPJ": "12.345.678.0001-99",
            "TELEFONE_EMPRESA": "(11) 2402-4392",
            "ENDERECO_EMPRESA": "Avenida Exemplo, nº 100",
            "CIDADE_EMPRESA": "Guarulhos",
            "ESTADO_EMPRESA": "SP",
            "BAIRRO_EMPRESA": "Vila Exemplo",
            "NOME_RT": "Profissional Exemplo",
            "CONSELHO_RT": "CRF nº: 70590",
            "EMAIL_RT": "profissional@example.invalid",
        }
        for key, value in expected.items():
            self.assertEqual(value, result.fields.get(key), key)
        self.assertEqual((), result.duplicates)
        self.assertEqual((), result.unrecognized_lines)

    def test_extracts_answers_on_line_after_template_labels(self) -> None:
        result = RuleBasedExtractor().extract(
            "Identificação do aluno\n"
            "- Nome completo\n"
            "- \u2060Aluna Exemplo\n"
            "- RA\n"
            "- 123456789\n"
            "- Campus\n"
            "- Memorial\n"
        )

        self.assertEqual("Aluna Exemplo", result.fields["NOME_ALUNO"])
        self.assertEqual("123456789", result.fields["RA_ALUNO"])
        self.assertEqual("Memorial", result.fields["CAMPUS"])

    def test_explicit_state_replaces_state_derived_from_city(self) -> None:
        result = RuleBasedExtractor().extract(
            "Identificação da empresa\nCidade: Exemplo - SP\nEstado: RJ"
        )

        self.assertEqual("Exemplo", result.fields["CIDADE_EMPRESA"])
        self.assertEqual("RJ", result.fields["ESTADO_EMPRESA"])
        self.assertEqual((), result.duplicates)


class HybridExtractorTests(unittest.TestCase):
    def test_uses_rules_first_but_sends_full_context_to_ai(self) -> None:
        ollama = FakeOllama()
        result = HybridExtractor(ollama=ollama).extract(
            "Nome aluno: Aluno Exemplo\nvou das 8h às 14h"
        )

        self.assertEqual(
            "Nome aluno: Aluno Exemplo\nvou das 8h às 14h",
            ollama.received,
        )
        self.assertEqual("08h às 14h", result.fields["HORARIO_ESTAGIO"])
        self.assertEqual("ia", result.evidence["HORARIO_ESTAGIO"].method)
        self.assertEqual((), result.unrecognized_lines)
        self.assertNotIn("MODULO_ESTAGIO", ollama.candidate_keys)
        self.assertNotIn("CARGA_HORARIA", ollama.candidate_keys)
        self.assertIn("RAMO_EMPRESA", ollama.candidate_keys)

    def test_can_disable_ai(self) -> None:
        ollama = FakeOllama()
        result = HybridExtractor(ollama=ollama).extract("texto livre", use_ai=False)

        self.assertFalse(result.ai_used)
        self.assertEqual("", ollama.received)
        self.assertEqual(("texto livre",), result.unrecognized_lines)

    def test_does_not_call_ai_when_every_message_line_was_understood(self) -> None:
        ollama = FakeOllama()
        result = HybridExtractor(ollama=ollama).extract(
            "Identificação do aluno\nNome completo: Aluna Exemplo\nRA: 123456789"
        )

        self.assertFalse(result.ai_used)
        self.assertEqual("", ollama.received)
        self.assertEqual((), result.unrecognized_lines)

    def test_evidence_must_exist_in_original_text(self) -> None:
        self.assertTrue(OllamaClient._source_exists("Meu RA é 123", "RA é 123"))
        self.assertFalse(OllamaClient._source_exists("Meu RA é 123", "RA é 999"))

    def test_evidence_ignores_invisible_whatsapp_formatting(self) -> None:
        message = "- Nome completo\n- \u2060Pessoa Exemplo"

        self.assertTrue(OllamaClient._source_exists(message, "Pessoa Exemplo"))

    def test_does_not_copy_one_value_into_multiple_fields(self) -> None:
        result = HybridExtractor(ollama=DuplicateValueOllama()).extract(
            "Local: Drogaria Exemplo\ninformação adicional sem rótulo"
        )

        self.assertEqual("Drogaria Exemplo", result.fields["EMPRESA_FANTASIA"])
        self.assertNotIn("ENDERECO_EMPRESA", result.fields)
        self.assertTrue(result.ai_notes)


if __name__ == "__main__":
    unittest.main()
