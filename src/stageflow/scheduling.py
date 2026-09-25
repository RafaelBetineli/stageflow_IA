"""Geração auditável do calendário diário do estágio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Mapping

import holidays


WEEKDAY_NAMES = (
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
)


@dataclass(frozen=True, slots=True)
class ScheduleDay:
    day: date
    start: time
    end: time
    minutes: int

    @property
    def hours(self) -> Decimal:
        return Decimal(self.minutes) / Decimal(60)


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    days: tuple[ScheduleDay, ...]
    excluded_holidays: tuple[tuple[date, str], ...]
    standard_daily_minutes: int

    @property
    def start_date(self) -> date:
        return self.days[0].day

    @property
    def end_date(self) -> date:
        return self.days[-1].day

    @property
    def total_minutes(self) -> int:
        return sum(item.minutes for item in self.days)

    @property
    def total_hours(self) -> Decimal:
        return Decimal(self.total_minutes) / Decimal(60)

    @property
    def weekly_hours(self) -> Decimal:
        totals: dict[tuple[int, int], int] = {}
        for item in self.days:
            iso = item.day.isocalendar()
            key = (iso.year, iso.week)
            totals[key] = totals.get(key, 0) + item.minutes
        return Decimal(max(totals.values(), default=0)) / Decimal(60)


class HolidayProvider:
    """Feriados nacionais e estaduais; municípios são informados pelo usuário."""

    def for_years(
        self,
        years: range | tuple[int, ...],
        state: str = "",
    ) -> dict[date, str]:
        normalized_state = state.strip().upper()
        calendar = holidays.country_holidays(
            "BR",
            subdiv=normalized_state or None,
            years=years,
            language="pt_BR",
        )
        return {day: str(name) for day, name in calendar.items()}


class ScheduleCalculator:
    MAX_DAILY_MINUTES = 6 * 60
    MAX_WEEKLY_MINUTES = 30 * 60

    def calculate(
        self,
        *,
        requested_start: date,
        total_hours: int | Decimal,
        start_time: time = time(8, 0),
        end_time: time = time(14, 0),
        working_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4),
        excluded_dates: Mapping[date, str] | None = None,
    ) -> ScheduleResult:
        weekdays = tuple(dict.fromkeys(working_weekdays))
        if not weekdays or any(day < 0 or day > 6 for day in weekdays):
            raise ValueError("Selecione ao menos um dia válido da semana.")

        daily_minutes = self._duration_minutes(start_time, end_time)
        if daily_minutes <= 0:
            raise ValueError("O horário final deve ser posterior ao inicial.")
        if daily_minutes > self.MAX_DAILY_MINUTES:
            raise ValueError("O estágio não pode ultrapassar 6 horas por dia.")
        if daily_minutes * len(weekdays) > self.MAX_WEEKLY_MINUTES:
            raise ValueError("A configuração ultrapassa 30 horas por semana.")

        required_minutes = int(Decimal(str(total_hours)) * Decimal(60))
        if required_minutes <= 0:
            raise ValueError("A carga horária total deve ser positiva.")

        exclusions = dict(excluded_dates or {})
        used_holidays: list[tuple[date, str]] = []
        result: list[ScheduleDay] = []
        remaining = required_minutes
        current = requested_start
        deadline = requested_start + timedelta(days=366 * 5)

        while remaining > 0:
            if current > deadline:
                raise ValueError("Não foi possível concluir o calendário em até cinco anos.")
            if current.weekday() in weekdays:
                if current in exclusions:
                    used_holidays.append((current, exclusions[current]))
                else:
                    allocated = min(daily_minutes, remaining)
                    result.append(
                        ScheduleDay(
                            day=current,
                            start=start_time,
                            end=self._add_minutes(start_time, allocated),
                            minutes=allocated,
                        )
                    )
                    remaining -= allocated
            current += timedelta(days=1)

        return ScheduleResult(
            days=tuple(result),
            excluded_holidays=tuple(used_holidays),
            standard_daily_minutes=daily_minutes,
        )

    @staticmethod
    def _duration_minutes(start: time, end: time) -> int:
        base = date(2000, 1, 1)
        return int((datetime.combine(base, end) - datetime.combine(base, start)).total_seconds() // 60)

    @staticmethod
    def _add_minutes(value: time, minutes: int) -> time:
        base = datetime.combine(date(2000, 1, 1), value)
        return (base + timedelta(minutes=minutes)).time()


def format_decimal_hours(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"))
    return format(normalized, "f").rstrip("0").rstrip(".")


def attendance_rows(schedule: ScheduleResult) -> tuple[dict[str, str], ...]:
    """Linhas prontas para a ficha de frequência e para exportação."""
    rows: list[dict[str, str]] = []
    for item in schedule.days:
        hours = format_decimal_hours(item.hours)
        unit = "hora" if hours == "1" else "horas"
        rows.append(
            {
                "Data": item.day.strftime("%d/%m/%Y"),
                "Horário de Entrada": item.start.strftime("%Hh%M"),
                "Horário de Saída": item.end.strftime("%Hh%M"),
                "Horas Cumpridas": f"{hours} {unit}",
            }
        )
    return tuple(rows)


def schedule_fields(
    schedule: ScheduleResult,
    working_weekdays: tuple[int, ...],
) -> dict[str, str]:
    first = schedule.days[0]
    regular_end = ScheduleCalculator._add_minutes(first.start, schedule.standard_daily_minutes)
    return {
        "DATA_INICIO_ESTAGIO": schedule.start_date.strftime("%d/%m/%Y"),
        "DATA_FIM_ESTAGIO": schedule.end_date.strftime("%d/%m/%Y"),
        "CARGA_HORARIA": f"{format_decimal_hours(schedule.total_hours)} horas",
        "CARGA_SEMANAL": f"{format_decimal_hours(schedule.weekly_hours)} horas",
        "DIAS_ESTAGIO": ", ".join(WEEKDAY_NAMES[index] for index in working_weekdays),
        "HORARIO_ESTAGIO": f"{first.start:%Hh%M} às {regular_end:%Hh%M}",
        "QTD_DIAS": str(len(schedule.days)),
    }
