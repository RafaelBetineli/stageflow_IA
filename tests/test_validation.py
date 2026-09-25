import unittest
from pathlib import Path

from stageflow.extraction import RuleBasedExtractor
from stageflow.validation import FieldValidator, InputValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT_ROOT / "data" / "mensagem_zap.example.txt"


class FieldValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = RuleBasedExtractor().extract(EXAMPLE.read_text(encoding="utf-8")).fields

    def test_versioned_example_is_valid(self) -> None:
        FieldValidator().validate(self.data)

    def test_reports_missing_fields_together(self) -> None:
        self.data["NOME_ALUNO"] = ""
        self.data.pop("CNPJ")

        with self.assertRaises(InputValidationError) as context:
            FieldValidator().validate(self.data)

        self.assertTrue(any("Nome do aluno" in issue for issue in context.exception.issues))
        self.assertTrue(any("CNPJ" in issue for issue in context.exception.issues))

    def test_rejects_inverted_internship_dates(self) -> None:
        self.data["DATA_INICIO_ESTAGIO"] = "30/06/2026"
        self.data["DATA_FIM_ESTAGIO"] = "02/02/2026"

        with self.assertRaisesRegex(InputValidationError, "data final do estágio"):
            FieldValidator().validate(self.data)

    def test_warns_when_insurance_does_not_cover_the_internship(self) -> None:
        self.data["DATA_FIM_VIGENCIA"] = "31/05/2026"

        issues = FieldValidator().check(self.data)

        self.assertTrue(
            any(issue.key == "DATA_FIM_VIGENCIA" and issue.severity == "atencao" for issue in issues)
        )
        FieldValidator().validate(self.data)

    def test_accepts_unformatted_cpf_and_cnpj(self) -> None:
        self.data["CPF"] = "12345678901"
        self.data["CNPJ"] = "12345678000190"

        FieldValidator().validate(self.data)

    def test_rejects_more_than_thirty_weekly_hours(self) -> None:
        self.data["CARGA_SEMANAL"] = "36 horas"

        with self.assertRaisesRegex(InputValidationError, "30 horas"):
            FieldValidator().validate(self.data)

    def test_rejects_professional_council_incompatible_with_area(self) -> None:
        self.data["CONSELHO_RT"] = "CREFITO-3 123456-F"

        with self.assertRaisesRegex(InputValidationError, "esperado CRF"):
            FieldValidator().validate(self.data)

    def test_accepts_biomedicine_context_with_crbm(self) -> None:
        self.data["AREA_ESTAGIO"] = "Estética"
        self.data["CONSELHO_RT"] = "CRBM-SP 000000"
        self.data["CARGO_REPRESENTANTE"] = "Biomédica responsável técnica"

        FieldValidator().validate(self.data)


if __name__ == "__main__":
    unittest.main()
