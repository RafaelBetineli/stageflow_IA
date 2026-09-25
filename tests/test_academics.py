import unittest

from stageflow.academics import AcademicRules, max_activities


class AcademicRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = AcademicRules()

    def test_resolves_regular_pharmacy_module(self) -> None:
        definition = self.rules.regular("Farmácia", "7º semestre")

        self.assertEqual("Módulo V", definition.module)
        self.assertEqual(150, definition.hours)

    def test_resolves_regular_biomedicine_module(self) -> None:
        definition = self.rules.regular("Biomedicina", "8º")

        self.assertEqual("Módulo II", definition.module)
        self.assertEqual(360, definition.hours)

    def test_dp_uses_selected_module_instead_of_current_semester(self) -> None:
        definition = self.rules.for_module("Farmácia", "Módulo I")

        self.assertEqual(3, definition.semester)
        self.assertEqual(130, definition.hours)

    def test_rejects_unconfigured_regular_semester(self) -> None:
        with self.assertRaisesRegex(ValueError, "Não existe módulo regular"):
            self.rules.regular("Farmácia", "2º semestre")

    def test_activity_limit_matches_document_templates(self) -> None:
        self.assertEqual(3, max_activities("Farmácia"))
        self.assertEqual(8, max_activities("Biomedicina"))


if __name__ == "__main__":
    unittest.main()
