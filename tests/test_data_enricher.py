import unittest

from stageflow.enrichment import DataEnricher


class DataEnricherTests(unittest.TestCase):
    def test_derives_dates_without_inventing_worked_day_count(self) -> None:
        result = DataEnricher().enrich(
            {
                "DATA_INICIO_ESTAGIO": "01/02/2026",
                "DATA_FIM_ESTAGIO": "03/02/2026",
            }
        )

        self.assertEqual("", result["QTD_DIAS"])
        self.assertEqual("1 de fevereiro de 2026", result["DATA_INICIO_EXTENSO"])
        self.assertEqual("3 de fevereiro de 2026", result["DATA_FIM"])

    def test_preserves_informed_day_count(self) -> None:
        result = DataEnricher().enrich(
            {
                "DATA_INICIO_ESTAGIO": "02/02/2026",
                "DATA_FIM_ESTAGIO": "24/04/2026",
                "QTD_DIAS": "33",
            }
        )

        self.assertEqual("33", result["QTD_DIAS"])

    def test_adds_optional_fields_without_activity_content(self) -> None:
        result = DataEnricher().enrich({})

        self.assertEqual("", result["CEP_ALUNO"])
        self.assertEqual("", result["OBSERVACOES_PLANO"])
        self.assertNotIn("CARGA_ATV1", result)

    def test_formats_cpf_and_cnpj_for_documents(self) -> None:
        result = DataEnricher().enrich(
            {"CPF": "12345678901", "CNPJ": "12345678000190"}
        )

        self.assertEqual("123.456.789-01", result["CPF"])
        self.assertEqual("12.345.678/0001-90", result["CNPJ"])

    def test_removes_labels_that_are_already_printed_in_forms(self) -> None:
        result = DataEnricher().enrich(
            {
                "MODULO_ESTAGIO": "Módulo IV",
                "CAMPUS": "Campus Centro",
                "SEMESTRE": "6º semestre",
            }
        )

        self.assertEqual("IV", result["MODULO_ESTAGIO"])
        self.assertEqual("Centro", result["CAMPUS"])
        self.assertEqual("6º", result["SEMESTRE"])

    def test_splits_council_acronym_and_registration(self) -> None:
        result = DataEnricher().enrich({"CONSELHO_RT": "CRF-SP 90909"})

        self.assertEqual("CRF", result["SIGLA_CONSELHO_RT"])
        self.assertEqual("90909", result["NUMERO_CONSELHO_RT"])
        self.assertEqual("CRF nº 90909", result["CONSELHO_RT_DOCUMENTO"])

    def test_normalizes_council_number_label_and_separator(self) -> None:
        for informed_value in (
            "CRF nº: 70590",
            "CRF n° 70590",
            "CRF: 70590",
            "CRF número 70590",
        ):
            with self.subTest(informed_value=informed_value):
                result = DataEnricher().enrich({"CONSELHO_RT": informed_value})

                self.assertEqual("CRF", result["SIGLA_CONSELHO_RT"])
                self.assertEqual("70590", result["NUMERO_CONSELHO_RT"])
                self.assertEqual("CRF nº 70590", result["CONSELHO_RT_DOCUMENTO"])


if __name__ == "__main__":
    unittest.main()
