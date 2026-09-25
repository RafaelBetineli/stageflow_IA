"""Caso de uso principal independente de interface ou linha de comando."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .documents import DEFAULT_OUTPUT, DocumentService
from .extraction import HybridExtractor, OllamaClient
from .models import AnalysisResult, ValidationIssue
from .validation import FieldValidator

if TYPE_CHECKING:
    from .scheduling import ScheduleResult


class StageFlow:
    def __init__(
        self,
        extractor: HybridExtractor | None = None,
        validator: FieldValidator | None = None,
        documents: DocumentService | None = None,
    ) -> None:
        self.validator = validator or FieldValidator()
        self.extractor = extractor or HybridExtractor()
        self.documents = documents or DocumentService(validator=self.validator)

    def available_models(self) -> tuple[str, ...]:
        return self.extractor.ollama.list_models()

    def analyze(
        self,
        message: str,
        *,
        use_ai: bool = True,
        model: str | None = None,
    ) -> AnalysisResult:
        if not message.strip():
            issue = ValidationIssue(None, "Cole a mensagem recebida do aluno.")
            return AnalysisResult(self.extractor.rule_extractor.extract(message), (issue,))
        if model:
            self.extractor.ollama.model = model
        extraction = self.extractor.extract(message, use_ai=use_ai)
        issues = self.validator.check(extraction.fields)
        return AnalysisResult(extraction, issues)

    def validate(self, data: dict[str, str]) -> tuple[ValidationIssue, ...]:
        return self.validator.check(data)

    def generate(
        self,
        data: dict[str, str],
        output_dir: str | Path = DEFAULT_OUTPUT,
        *,
        overwrite: bool = False,
        schedule: ScheduleResult | None = None,
    ) -> tuple[Path, ...]:
        return self.documents.generate(
            data,
            output_dir,
            overwrite=overwrite,
            schedule=schedule,
        )

    @staticmethod
    def ollama(model: str = "qwen3:8b") -> "StageFlow":
        return StageFlow(extractor=HybridExtractor(ollama=OllamaClient(model=model)))
