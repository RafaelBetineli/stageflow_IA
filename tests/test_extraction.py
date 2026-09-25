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

    def test_can_disable_ai(self) -> None:
        ollama = FakeOllama()
        result = HybridExtractor(ollama=ollama).extract("texto livre", use_ai=False)

        self.assertFalse(result.ai_used)
        self.assertEqual("", ollama.received)
        self.assertEqual(("texto livre",), result.unrecognized_lines)

    def test_evidence_must_exist_in_original_text(self) -> None:
        self.assertTrue(OllamaClient._source_exists("Meu RA é 123", "RA é 123"))
        self.assertFalse(OllamaClient._source_exists("Meu RA é 123", "RA é 999"))

    def test_evidence_ignores_invisible_whatsapp_formatting(self) -> None:
        message = "- Nome completo\n- \u2060Pessoa Exemplo"

        self.assertTrue(OllamaClient._source_exists(message, "Pessoa Exemplo"))

    def test_does_not_copy_one_value_into_multiple_fields(self) -> None:
        result = HybridExtractor(ollama=DuplicateValueOllama()).extract(
            "Local: Drogaria Exemplo"
        )

        self.assertEqual("Drogaria Exemplo", result.fields["EMPRESA_FANTASIA"])
        self.assertNotIn("ENDERECO_EMPRESA", result.fields)
        self.assertTrue(result.ai_notes)


if __name__ == "__main__":
    unittest.main()
