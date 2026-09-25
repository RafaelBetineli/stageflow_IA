"""Objetos de domínio compartilhados entre extração, validação e interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .fields import REQUIRED_FIELDS


ExtractionMethod = Literal["regra", "ia", "manual"]
IssueSeverity = Literal["erro", "atencao"]


@dataclass(frozen=True, slots=True)
class FieldEvidence:
    key: str
    value: str
    source: str
    method: ExtractionMethod


@dataclass(slots=True)
class ExtractionResult:
    fields: dict[str, str] = field(default_factory=dict)
    evidence: dict[str, FieldEvidence] = field(default_factory=dict)
    unrecognized_lines: tuple[str, ...] = ()
    duplicates: tuple[str, ...] = ()
    ai_used: bool = False
    ai_error: str | None = None
    ai_notes: tuple[str, ...] = ()

    @property
    def missing_required(self) -> tuple[str, ...]:
        return tuple(
            key for key in REQUIRED_FIELDS if not str(self.fields.get(key, "")).strip()
        )


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    key: str | None
    message: str
    severity: IssueSeverity = "erro"


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    extraction: ExtractionResult
    issues: tuple[ValidationIssue, ...]

    @property
    def can_generate(self) -> bool:
        return not any(issue.severity == "erro" for issue in self.issues)
