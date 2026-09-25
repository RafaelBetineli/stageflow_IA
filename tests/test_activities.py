import unittest

from stageflow.activities import (
    ActivityAllocator,
    activity_document_fields,
    build_activity_prompt,
)


class ActivityAllocatorTests(unittest.TestCase):
    def test_allocates_exact_total_by_weight(self) -> None:
        result = ActivityAllocator().allocate(
            130,
            (("Atividade 1", 10), ("Atividade 2", 7), ("Atividade 3", 9)),
        )

        self.assertEqual([50, 35, 45], [item.hours for item in result])
        self.assertEqual(130, sum(item.hours for item in result))

    def test_rounding_still_closes_the_total(self) -> None:
        result = ActivityAllocator().allocate(
            130,
            (("Atividade A", 1), ("Atividade B", 1), ("Atividade C", 1)),
        )

        self.assertEqual(130, sum(item.hours for item in result))

    def test_builds_document_fields_and_blanks_unused_positions(self) -> None:
        allocations = ActivityAllocator().allocate(10, (("Conferência", 1),))
        fields = activity_document_fields(allocations, limit=3)

        self.assertEqual("Conferência", fields["TITULO_ATV1"])
        self.assertEqual("10 horas", fields["CARGA_ATV1"])
        self.assertEqual("", fields["TITULO_ATV2"])

    def test_prompt_includes_previous_activities(self) -> None:
        prompt = build_activity_prompt(
            area="Drogaria",
            course="Farmácia",
            module="Módulo I",
            count=3,
            previous_titles=("Conferência de medicamentos",),
        )

        self.assertIn("Conferência de medicamentos", prompt)
        self.assertIn("Evite repetir", prompt)


if __name__ == "__main__":
    unittest.main()
