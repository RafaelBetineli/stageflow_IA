"""Seleção de templates e geração transacional dos documentos de estágio."""

from __future__ import annotations

from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
import unicodedata

from .template_engine import DocumentGenerator
from .enrichment import DataEnricher
from .fields import normalize_label
from .validation import FieldValidator

if TYPE_CHECKING:
    from .scheduling import ScheduleResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "docx"
TEMPLATES_ROOT = PROJECT_ROOT / "templates"

AREA_TEMPLATES = {
    "estetica": ("biomedicina", "biomedicina"),
    "biomedicina estetica": ("biomedicina", "biomedicina"),
    "drogaria": ("farmacia", "farmacia"),
    "farmacia drogaria": ("farmacia", "farmacia"),
    "hospitalar": ("farmacia", "farmacia"),
    "farmacia hospitalar": ("farmacia", "farmacia"),
    "manipulacao": ("farmacia", "farmacia"),
    "farmacia manipulacao": ("farmacia", "farmacia"),
    "controle de qualidade": ("farmacia", "farmacia"),
    "farmacia controle de qualidade": ("farmacia", "farmacia"),
}

MANUAL_CONTENT_FIELDS = (
    "INTRODUCAO",
    "OBJETIVO_GERAL",
    "OBJETIVOS_ESPECIFICOS",
    "HISTORIA_EMPRESA",
    "DESCRICAO_AREA_EMPRESA",
    "CONCLUSAO",
    "REFERENCIAS",
    "COMPLEMENTAR1",
    "COMPLEMENTAR2",
    *(f"ATV{position}" for position in range(1, 11)),
)
ACTIVITY_FIELDS = (
    *(f"TITULO_ATV{position}" for position in range(1, 11)),
    *(f"CARGA_ATV{position}" for position in range(1, 11)),
)


def sanitize_filename(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    ascii_value = decomposed.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9_]+", "", ascii_value.casefold().replace(" ", "_"))


class DocumentService:
    """Valida os dados e publica os três documentos como uma única operação."""

    def __init__(
        self,
        templates_root: str | Path = TEMPLATES_ROOT,
        validator: FieldValidator | None = None,
        enricher: DataEnricher | None = None,
    ) -> None:
        self.templates_root = Path(templates_root)
        self.validator = validator or FieldValidator()
        self.enricher = enricher or DataEnricher()

    def generate(
        self,
        data: dict[str, str],
        output_dir: str | Path = DEFAULT_OUTPUT,
        *,
        overwrite: bool = False,
        schedule: ScheduleResult | None = None,
    ) -> tuple[Path, ...]:
        self.validator.validate(data)
        templates = self._resolve_templates(data["AREA_ESTAGIO"])
        self._ensure_templates_exist(templates)

        enriched = self.enricher.enrich(data)
        final_data = {
            **dict.fromkeys(ACTIVITY_FIELDS, ""),
            **enriched,
            **dict.fromkeys(MANUAL_CONTENT_FIELDS, ""),
        }
        student_name = sanitize_filename(enriched["NOME_ALUNO"])
        if not student_name:
            raise ValueError("O nome do aluno não produz um nome de arquivo válido.")

        output = Path(output_dir)
        destinations = tuple(
            output / f"{prefix}_{student_name}.docx" for prefix, _ in templates
        )
        self._ensure_overwrite_allowed(destinations, overwrite)

        output.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".stageflow_", dir=output) as temporary:
            publications: list[tuple[Path, Path]] = []
            for (prefix, template), destination in zip(templates, destinations):
                generated = Path(temporary) / f"{prefix}.docx"
                DocumentGenerator(template).generate(
                    final_data,
                    generated,
                    attendance_days=schedule.days if schedule else (),
                )
                publications.append((generated, destination))
            self._publish(publications)

        return destinations

    def _resolve_templates(self, internship_area: str) -> tuple[tuple[str, Path], ...]:
        area = normalize_label(internship_area)
        configuration = AREA_TEMPLATES.get(area)
        if not configuration:
            raise ValueError(f"Área de estágio não reconhecida: {internship_area!r}.")
        folder, suffix = configuration
        base = self.templates_root / folder
        return (
            ("relatorio", base / f"modelo_relatorio_{suffix}_automatizado.docx"),
            ("plano_estagio", base / f"modelo_plano_{suffix}_automatizado.docx"),
            ("termo_compromisso", base / f"modelo_termo_{suffix}_automatizado.docx"),
        )

    @staticmethod
    def _ensure_templates_exist(templates: tuple[tuple[str, Path], ...]) -> None:
        missing = [str(path) for _, path in templates if not path.is_file()]
        if missing:
            raise FileNotFoundError("Templates ausentes:\n- " + "\n- ".join(missing))

    @staticmethod
    def _ensure_overwrite_allowed(destinations: tuple[Path, ...], overwrite: bool) -> None:
        existing = tuple(path for path in destinations if path.exists())
        if existing and not overwrite:
            listing = "\n- ".join(str(path) for path in existing)
            raise FileExistsError(
                "Documentos de saída já existem. Autorize a substituição para continuar:\n"
                f"- {listing}"
            )

    @staticmethod
    def _publish(publications: list[tuple[Path, Path]]) -> None:
        backups: list[tuple[Path, Path]] = []
        published: list[Path] = []
        try:
            for _, destination in publications:
                if destination.exists():
                    backup = destination.with_suffix(destination.suffix + ".bak")
                    backup.unlink(missing_ok=True)
                    destination.replace(backup)
                    backups.append((backup, destination))
            for source, destination in publications:
                source.replace(destination)
                published.append(destination)
        except Exception:
            for destination in published:
                destination.unlink(missing_ok=True)
            for backup, destination in backups:
                backup.replace(destination)
            raise
        else:
            for backup, _ in backups:
                backup.unlink(missing_ok=True)
