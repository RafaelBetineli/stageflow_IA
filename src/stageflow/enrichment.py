"""Cálculo dos campos objetivos derivados usados nos documentos."""

from __future__ import annotations

from datetime import datetime

from .fields import OPTIONAL_FIELDS
from .formatting import (
    format_cnpj,
    format_cpf,
    format_semester_for_document,
    split_professional_council,
    without_repeated_label,
)


class DataEnricher:
    MONTHS = (
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    )

    def enrich(self, data: dict[str, str]) -> dict[str, str]:
        enriched = {key: str(value) for key, value in data.items()}
        for key in OPTIONAL_FIELDS:
            enriched.setdefault(key, "")
        enriched["CPF"] = format_cpf(data.get("CPF", ""))
        enriched["CNPJ"] = format_cnpj(data.get("CNPJ", ""))
        enriched["MODULO_ESTAGIO"] = without_repeated_label(
            data.get("MODULO_ESTAGIO", ""), "Módulo"
        )
        enriched["CAMPUS"] = without_repeated_label(data.get("CAMPUS", ""), "Campus")
        enriched["SEMESTRE"] = format_semester_for_document(data.get("SEMESTRE", ""))
        council_acronym, council_registration = split_professional_council(
            data.get("CONSELHO_RT", "")
        )
        enriched["SIGLA_CONSELHO_RT"] = council_acronym
        enriched["NUMERO_CONSELHO_RT"] = council_registration
        enriched["CONSELHO_RT_DOCUMENTO"] = " ".join(
            part for part in (council_acronym, council_registration) if part
        )

        start = self._parse_date(data.get("DATA_INICIO_ESTAGIO"))
        end = self._parse_date(data.get("DATA_FIM_ESTAGIO"))
        if start:
            enriched["DATA_INICIO_EXTENSO"] = self._date_in_words(start)
        if end:
            enriched["DATA_FIM_EXTENSO"] = self._date_in_words(end)
            enriched["DATA_FIM"] = enriched["DATA_FIM_EXTENSO"]
        return enriched

    @staticmethod
    def _parse_date(value: object) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(str(value).strip(), "%d/%m/%Y")
        except ValueError:
            return None

    def _date_in_words(self, value: datetime) -> str:
        return f"{value.day} de {self.MONTHS[value.month - 1]} de {value.year}"
