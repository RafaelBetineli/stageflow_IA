import tempfile
import unittest
from datetime import date
from pathlib import Path

from stageflow.academics import AcademicRules
from stageflow.activities import ActivityAllocator, activity_document_fields
from stageflow.documents import DocumentService
from stageflow.extraction import RuleBasedExtractor
from stageflow.repository import LocalRepository
from stageflow.scheduling import HolidayProvider, ScheduleCalculator, schedule_fields


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT_ROOT / "data" / "mensagem_zap.example.txt"


class PlannedWorkflowEndToEndTests(unittest.TestCase):
    def test_plans_generates_and_records_history(self) -> None:
        data = RuleBasedExtractor().extract(EXAMPLE.read_text(encoding="utf-8")).fields
        module = AcademicRules().regular("Farmácia", data["SEMESTRE"])
        holidays = HolidayProvider().for_years(range(2026, 2027), "SP")
        schedule = ScheduleCalculator().calculate(
            requested_start=date(2026, 9, 7),
            total_hours=module.hours,
            excluded_dates=holidays,
        )
        allocations = ActivityAllocator().allocate(
            module.hours,
            (
                ("Conferência de medicamentos", 10),
                ("Controle de estoque", 7),
                ("Orientação ao paciente", 9),
            ),
        )
        data.update(
            {
                "CURSO": module.course,
                "MODULO_ESTAGIO": module.module,
                **schedule_fields(schedule, (0, 1, 2, 3, 4)),
                **activity_document_fields(allocations),
            }
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = DocumentService().generate(data, root / "documents")
            repository = LocalRepository(root / "stageflow.db")
            repository.save_company(data)
            repository.save_activities(
                area=data["AREA_ESTAGIO"],
                course=data["CURSO"],
                module=data["MODULO_ESTAGIO"],
                student_reference=data["NOME_ALUNO"],
                allocations=allocations,
            )

            self.assertEqual(3, len(outputs))
            self.assertTrue(all(path.is_file() for path in outputs))
            self.assertEqual(data["EMPRESA"], repository.company(data["CNPJ"])["EMPRESA"])
            self.assertEqual(3, len(repository.activity_titles(data["AREA_ESTAGIO"])))


if __name__ == "__main__":
    unittest.main()
