"""Regras acadêmicas determinísticas de módulo e carga horária."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .fields import normalize_label


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    course: str
    semester: int
    module: str
    hours: int


MODULES = (
    ModuleDefinition("Farmácia", 3, "Módulo I", 130),
    ModuleDefinition("Farmácia", 4, "Módulo II", 130),
    ModuleDefinition("Farmácia", 5, "Módulo III", 130),
    ModuleDefinition("Farmácia", 6, "Módulo IV", 140),
    ModuleDefinition("Farmácia", 7, "Módulo V", 150),
    ModuleDefinition("Farmácia", 8, "Módulo VI", 160),
    ModuleDefinition("Biomedicina", 7, "Módulo I", 320),
    ModuleDefinition("Biomedicina", 8, "Módulo II", 360),
)

MIN_ACTIVITIES = 3
MAX_ACTIVITIES = 10


class AcademicRules:
    COURSES = ("Farmácia", "Biomedicina")

    def regular(self, course: str, semester: str | int) -> ModuleDefinition:
        semester_number = self.semester_number(semester)
        normalized_course = normalize_label(course)
        for definition in MODULES:
            if (
                normalize_label(definition.course) == normalized_course
                and definition.semester == semester_number
            ):
                return definition
        raise ValueError(
            f"Não existe módulo regular configurado para {course}, {semester_number}º semestre."
        )

    def for_module(self, course: str, module: str) -> ModuleDefinition:
        normalized_course = normalize_label(course)
        normalized_module = normalize_label(module)
        for definition in MODULES:
            if (
                normalize_label(definition.course) == normalized_course
                and normalize_label(definition.module) == normalized_module
            ):
                return definition
        raise ValueError(f"Módulo {module!r} não configurado para {course}.")

    def modules_for_course(self, course: str) -> tuple[ModuleDefinition, ...]:
        normalized = normalize_label(course)
        return tuple(
            definition
            for definition in MODULES
            if normalize_label(definition.course) == normalized
        )

    @staticmethod
    def semester_number(value: str | int) -> int:
        match = re.search(r"\d+", str(value))
        if not match:
            raise ValueError("Informe o semestre do aluno com um número.")
        return int(match.group())


def max_activities(course: str) -> int:
    """Limite comum suportado pelos modelos de todos os cursos."""
    return MAX_ACTIVITIES


def min_activities(course: str) -> int:
    """Quantidade mínima exigida pela faculdade para todos os cursos."""
    return MIN_ACTIVITIES
