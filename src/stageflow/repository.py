"""Persistência SQLite local para empresas e histórico de atividades."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import re
import sqlite3
import unicodedata

from .activities import ActivityAllocation
from .formatting import format_cnpj


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "stageflow.db"

COMPANY_FIELDS = (
    "EMPRESA",
    "EMPRESA_FANTASIA",
    "RAMO_EMPRESA",
    "ENDERECO_EMPRESA",
    "BAIRRO_EMPRESA",
    "CIDADE_EMPRESA",
    "ESTADO_EMPRESA",
    "TELEFONE_EMPRESA",
)


def normalize_cnpj(value: str) -> str:
    return re.sub(r"\D", "", value)


def normalize_activity(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())


class LocalRepository:
    def __init__(self, database: str | Path = DEFAULT_DATABASE) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    cnpj TEXT PRIMARY KEY,
                    empresa TEXT NOT NULL,
                    empresa_fantasia TEXT NOT NULL DEFAULT '',
                    ramo_empresa TEXT NOT NULL DEFAULT '',
                    endereco_empresa TEXT NOT NULL DEFAULT '',
                    bairro_empresa TEXT NOT NULL DEFAULT '',
                    cidade_empresa TEXT NOT NULL DEFAULT '',
                    estado_empresa TEXT NOT NULL DEFAULT '',
                    telefone_empresa TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activity_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    area TEXT NOT NULL,
                    course TEXT NOT NULL,
                    module TEXT NOT NULL,
                    student_reference TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    normalized_activity TEXT NOT NULL,
                    hours INTEGER NOT NULL,
                    used_at TEXT NOT NULL,
                    UNIQUE(area, module, student_reference, normalized_activity)
                );
                CREATE INDEX IF NOT EXISTS idx_activity_area
                    ON activity_history(area, used_at DESC);
                """
            )
            connection.commit()

    def save_company(self, data: dict[str, str]) -> None:
        cnpj = normalize_cnpj(str(data.get("CNPJ", "")))
        if len(cnpj) != 14:
            raise ValueError("Informe um CNPJ válido antes de salvar a empresa.")
        company = str(data.get("EMPRESA", "")).strip()
        if not company:
            raise ValueError("Informe a razão social antes de salvar a empresa.")
        values = [str(data.get(field, "")).strip() for field in COMPANY_FIELDS]
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO companies (
                    cnpj, empresa, empresa_fantasia, ramo_empresa,
                    endereco_empresa, bairro_empresa, cidade_empresa,
                    estado_empresa, telefone_empresa, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cnpj) DO UPDATE SET
                    empresa = excluded.empresa,
                    empresa_fantasia = excluded.empresa_fantasia,
                    ramo_empresa = excluded.ramo_empresa,
                    endereco_empresa = excluded.endereco_empresa,
                    bairro_empresa = excluded.bairro_empresa,
                    cidade_empresa = excluded.cidade_empresa,
                    estado_empresa = excluded.estado_empresa,
                    telefone_empresa = excluded.telefone_empresa,
                    updated_at = excluded.updated_at
                """,
                (cnpj, *values, datetime.now().isoformat(timespec="seconds")),
            )
            connection.commit()

    def company(self, cnpj_value: str) -> dict[str, str] | None:
        cnpj = normalize_cnpj(cnpj_value)
        if len(cnpj) != 14:
            return None
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM companies WHERE cnpj = ?", (cnpj,)
            ).fetchone()
        if row is None:
            return None
        return {
            "CNPJ": format_cnpj(cnpj),
            **{field: str(row[field.casefold()]) for field in COMPANY_FIELDS},
        }

    def save_activities(
        self,
        *,
        area: str,
        course: str,
        module: str,
        student_reference: str,
        allocations: tuple[ActivityAllocation, ...],
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        rows = tuple(
            (
                area.strip(),
                course.strip(),
                module.strip(),
                student_reference.strip(),
                item.title.strip(),
                normalize_activity(item.title),
                item.hours,
                now,
            )
            for item in allocations
            if item.title.strip()
        )
        if not rows:
            return
        with closing(self._connect()) as connection:
            connection.executemany(
                """
                INSERT INTO activity_history (
                    area, course, module, student_reference, activity,
                    normalized_activity, hours, used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(area, module, student_reference, normalized_activity)
                DO UPDATE SET hours = excluded.hours, used_at = excluded.used_at
                """,
                rows,
            )
            connection.commit()

    def activity_titles(self, area: str, limit: int = 50) -> tuple[str, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT activity, MAX(used_at) AS latest
                FROM activity_history
                WHERE lower(area) = lower(?)
                GROUP BY normalized_activity
                ORDER BY latest DESC
                LIMIT ?
                """,
                (area.strip(), limit),
            ).fetchall()
        return tuple(str(row["activity"]) for row in rows)

    def similar_activities(
        self,
        area: str,
        title: str,
        threshold: float = 0.78,
    ) -> tuple[str, ...]:
        target = normalize_activity(title)
        if not target:
            return ()
        return tuple(
            previous
            for previous in self.activity_titles(area)
            if SequenceMatcher(None, target, normalize_activity(previous)).ratio() >= threshold
        )
