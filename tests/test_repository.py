import tempfile
import unittest
from pathlib import Path

from stageflow.activities import ActivityAllocation
from stageflow.repository import LocalRepository


class LocalRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = LocalRepository(Path(self.temporary.name) / "test.db")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_saves_and_loads_company_by_normalized_cnpj(self) -> None:
        self.repository.save_company(
            {
                "CNPJ": "12.345.678/0001-90",
                "EMPRESA": "Empresa Exemplo Ltda.",
                "EMPRESA_FANTASIA": "Empresa Exemplo",
                "ESTADO_EMPRESA": "SP",
            }
        )

        company = self.repository.company("12345678000190")

        self.assertIsNotNone(company)
        self.assertEqual("Empresa Exemplo Ltda.", company["EMPRESA"])
        self.assertEqual("SP", company["ESTADO_EMPRESA"])

    def test_activity_history_detects_similar_names(self) -> None:
        self.repository.save_activities(
            area="Drogaria",
            course="Farmácia",
            module="Módulo I",
            student_reference="Aluno Exemplo",
            allocations=(ActivityAllocation("Conferência de medicamentos", 5, 40),),
        )

        matches = self.repository.similar_activities(
            "Drogaria", "Conferencia dos medicamentos"
        )

        self.assertEqual(("Conferência de medicamentos",), matches)

    def test_saving_same_activity_twice_does_not_duplicate_history(self) -> None:
        allocation = ActivityAllocation("Controle de estoque", 5, 50)
        arguments = {
            "area": "Drogaria",
            "course": "Farmácia",
            "module": "Módulo I",
            "student_reference": "Aluno Exemplo",
            "allocations": (allocation,),
        }
        self.repository.save_activities(**arguments)
        self.repository.save_activities(**arguments)

        self.assertEqual(("Controle de estoque",), self.repository.activity_titles("Drogaria"))


if __name__ == "__main__":
    unittest.main()
