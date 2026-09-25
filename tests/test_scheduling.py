import unittest
from datetime import date, time

from stageflow.scheduling import (
    HolidayProvider,
    ScheduleCalculator,
    attendance_rows,
    schedule_fields,
)


class ScheduleCalculatorTests(unittest.TestCase):
    def test_completes_130_hours_and_reduces_last_day(self) -> None:
        holidays = HolidayProvider().for_years(range(2026, 2027), "SP")
        schedule = ScheduleCalculator().calculate(
            requested_start=date(2026, 9, 7),
            total_hours=130,
            excluded_dates=holidays,
        )

        self.assertEqual(date(2026, 9, 8), schedule.start_date)
        self.assertEqual(date(2026, 10, 7), schedule.end_date)
        self.assertEqual(22, len(schedule.days))
        self.assertEqual(240, schedule.days[-1].minutes)
        self.assertEqual(time(12, 0), schedule.days[-1].end)
        self.assertEqual(130, schedule.total_hours)
        self.assertEqual(30, schedule.weekly_hours)
        self.assertIn((date(2026, 9, 7), "Independência do Brasil"), schedule.excluded_holidays)

        rows = attendance_rows(schedule)
        self.assertEqual(
            {
                "Data": "08/09/2026",
                "Horário de Entrada": "08h00",
                "Horário de Saída": "14h00",
                "Horas Cumpridas": "6 horas",
            },
            rows[0],
        )
        self.assertEqual("4 horas", rows[-1]["Horas Cumpridas"])

    def test_accepts_a_different_fixed_shift(self) -> None:
        schedule = ScheduleCalculator().calculate(
            requested_start=date(2026, 9, 8),
            total_hours=10,
            start_time=time(16, 0),
            end_time=time(22, 0),
        )

        self.assertEqual(time(16, 0), schedule.days[-1].start)
        self.assertEqual(time(20, 0), schedule.days[-1].end)

    def test_rejects_more_than_thirty_configured_weekly_hours(self) -> None:
        with self.assertRaisesRegex(ValueError, "30 horas"):
            ScheduleCalculator().calculate(
                requested_start=date(2026, 9, 8),
                total_hours=130,
                working_weekdays=(0, 1, 2, 3, 4, 5),
            )

    def test_manual_exclusion_moves_the_end_date(self) -> None:
        normal = ScheduleCalculator().calculate(
            requested_start=date(2026, 9, 8), total_hours=12
        )
        excluded = ScheduleCalculator().calculate(
            requested_start=date(2026, 9, 8),
            total_hours=12,
            excluded_dates={date(2026, 9, 8): "Feriado municipal"},
        )

        self.assertEqual(date(2026, 9, 9), normal.end_date)
        self.assertEqual(date(2026, 9, 10), excluded.end_date)

    def test_formats_document_fields_from_worked_days(self) -> None:
        schedule = ScheduleCalculator().calculate(
            requested_start=date(2026, 9, 8), total_hours=10
        )
        fields = schedule_fields(schedule, (0, 1, 2, 3, 4))

        self.assertEqual("2", fields["QTD_DIAS"])
        self.assertEqual("10 horas", fields["CARGA_HORARIA"])
        self.assertEqual("08h00 às 14h00", fields["HORARIO_ESTAGIO"])


if __name__ == "__main__":
    unittest.main()
