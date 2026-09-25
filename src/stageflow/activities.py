"""Distribuição de horas e apoio ao controle de repetição de atividades."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR


@dataclass(frozen=True, slots=True)
class ActivityAllocation:
    title: str
    weight: int
    hours: int


class ActivityAllocator:
    def allocate(
        self,
        total_hours: int,
        activities: tuple[tuple[str, int], ...],
    ) -> tuple[ActivityAllocation, ...]:
        cleaned = tuple((title.strip(), int(weight)) for title, weight in activities if title.strip())
        if not cleaned:
            return ()
        if any(weight < 1 or weight > 10 for _, weight in cleaned):
            raise ValueError("O peso de cada atividade deve estar entre 1 e 10.")
        if total_hours < len(cleaned):
            raise ValueError("A carga total é insuficiente para as atividades informadas.")

        weight_sum = sum(weight for _, weight in cleaned)
        exact = [Decimal(total_hours) * Decimal(weight) / Decimal(weight_sum) for _, weight in cleaned]
        base = [int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in exact]
        missing = total_hours - sum(base)
        order = sorted(
            range(len(cleaned)),
            key=lambda index: (exact[index] - Decimal(base[index]), -index),
            reverse=True,
        )
        for index in order[:missing]:
            base[index] += 1

        return tuple(
            ActivityAllocation(title, weight, hours)
            for (title, weight), hours in zip(cleaned, base)
        )


def activity_document_fields(
    allocations: tuple[ActivityAllocation, ...],
    limit: int = 10,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for position in range(1, limit + 1):
        if position <= len(allocations):
            allocation = allocations[position - 1]
            result[f"TITULO_ATV{position}"] = allocation.title
            result[f"CARGA_ATV{position}"] = f"{allocation.hours} horas"
        else:
            result[f"TITULO_ATV{position}"] = ""
            result[f"CARGA_ATV{position}"] = ""
    return result


def build_activity_prompt(
    *,
    area: str,
    course: str,
    module: str,
    count: int,
    previous_titles: tuple[str, ...] = (),
) -> str:
    prompt = (
        f"Sugira {count} atividades práticas e distintas para um estágio de {course} "
        f"na área de {area}, referente ao {module}. Retorne apenas uma lista com os "
        "títulos das atividades, sem relatos nem cargas horárias. As atividades "
        "precisam ser compatíveis com a rotina real do campo de estágio e com a "
        "atuação supervisionada de um estudante. São sugestões para revisão, não "
        "declarações do que o aluno realizou. Atividades-base podem ser reutilizadas "
        "entre alunos; diversifique a combinação e use títulos claros e variados "
        "sem mudar o significado da atividade."
    )
    if previous_titles:
        avoided = "\n".join(f"- {title}" for title in previous_titles)
        prompt += (
            "\n\nEvite repetir exatamente estes títulos recentes. As atividades-base "
            "podem reaparecer com outra redação fiel ao significado:\n" + avoided
        )
    return prompt
