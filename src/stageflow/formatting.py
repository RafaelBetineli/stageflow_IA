"""Formatação conservadora de identificadores recebidos sem pontuação."""

from __future__ import annotations

import re


def digits_only(value: object) -> str:
    return re.sub(r"\D", "", str(value or ""))


def format_cpf(value: object) -> str:
    digits = digits_only(value)
    if len(digits) != 11:
        return str(value or "").strip()
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def format_cnpj(value: object) -> str:
    digits = digits_only(value)
    if len(digits) != 14:
        return str(value or "").strip()
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def without_repeated_label(value: object, label: str) -> str:
    """Remove um rótulo que já aparece impresso no formulário."""
    text = str(value or "").strip()
    return re.sub(rf"^\s*{re.escape(label)}\s*", "", text, flags=re.IGNORECASE).strip()


def format_semester_for_document(value: object) -> str:
    """Evita resultados como `6º semestre` após o rótulo Semestre."""
    text = str(value or "").strip()
    return re.sub(r"\s+semestre\s*$", "", text, flags=re.IGNORECASE).strip()


def split_professional_council(value: object) -> tuple[str, str]:
    """Separa sigla e inscrição de valores como `CRF-SP 90909`."""
    text = " ".join(str(value or "").strip().split())
    if not text:
        return "", ""
    match = re.search(r"\b(CRF|CRBM|CRQ|COREN|CREFITO|CRM|CRO|CRN)\b", text, re.IGNORECASE)
    if not match:
        return "", text
    acronym = match.group(1).upper()
    registration = text[match.end() :].strip()
    registration = re.sub(r"^\s*[-/]\s*[A-Z]{2}\b", "", registration, flags=re.IGNORECASE).strip()
    registration = re.sub(r"^\s*(?:n[º°o]?\.?|número)\s*", "", registration, flags=re.IGNORECASE).strip()
    return acronym, registration
