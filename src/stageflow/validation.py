"""Validações determinísticas dos dados revisados."""

from __future__ import annotations

from datetime import datetime
import re

from .fields import REQUIRED_FIELDS, normalize_label
from .formatting import digits_only
from .models import ValidationIssue


class InputValidationError(ValueError):
    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.validation_issues = issues
        self.issues = tuple(issue.message for issue in issues)
        super().__init__("Entrada inválida:\n- " + "\n- ".join(self.issues))


class FieldValidator:
    """Retorna erros bloqueantes e avisos que exigem revisão humana."""

    DATE_FIELDS = (
        "DATA_INICIO_VIGENCIA",
        "DATA_FIM_VIGENCIA",
        "DATA_INICIO_ESTAGIO",
        "DATA_FIM_ESTAGIO",
    )

    def check(self, data: dict[str, str]) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        for key, label in REQUIRED_FIELDS.items():
            if not str(data.get(key, "")).strip():
                issues.append(ValidationIssue(key, f"Campo obrigatório: {label}."))

        dates: dict[str, datetime] = {}
        for key in self.DATE_FIELDS:
            value = str(data.get(key, "")).strip()
            if not value:
                continue
            try:
                dates[key] = datetime.strptime(value, "%d/%m/%Y")
            except ValueError:
                issues.append(ValidationIssue(key, f"{REQUIRED_FIELDS[key]} deve usar DD/MM/AAAA."))

        self._date_order(dates, "DATA_INICIO_ESTAGIO", "DATA_FIM_ESTAGIO", "A data final do estágio deve ser igual ou posterior à inicial.", issues)
        self._date_order(dates, "DATA_INICIO_VIGENCIA", "DATA_FIM_VIGENCIA", "A data final da vigência deve ser igual ou posterior à inicial.", issues)

        if dates.get("DATA_INICIO_VIGENCIA") and dates.get("DATA_INICIO_ESTAGIO"):
            if dates["DATA_INICIO_VIGENCIA"] > dates["DATA_INICIO_ESTAGIO"]:
                issues.append(ValidationIssue("DATA_INICIO_VIGENCIA", "A vigência do seguro começa depois do estágio.", "atencao"))
        if dates.get("DATA_FIM_VIGENCIA") and dates.get("DATA_FIM_ESTAGIO"):
            if dates["DATA_FIM_VIGENCIA"] < dates["DATA_FIM_ESTAGIO"]:
                issues.append(ValidationIssue("DATA_FIM_VIGENCIA", "A vigência do seguro termina antes do estágio.", "atencao"))

        for key, label in (("EMAIL_ALUNO", "E-mail do aluno"), ("EMAIL_RT", "E-mail do responsável técnico")):
            value = str(data.get(key, "")).strip()
            if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                issues.append(ValidationIssue(key, f"{label} possui formato inválido."))

        cpf = str(data.get("CPF", "")).strip()
        if cpf and len(digits_only(cpf)) != 11:
            issues.append(ValidationIssue("CPF", "CPF deve conter 11 dígitos."))
        cnpj = str(data.get("CNPJ", "")).strip()
        if cnpj and len(digits_only(cnpj)) != 14:
            issues.append(ValidationIssue("CNPJ", "CNPJ deve conter 14 dígitos."))

        workload = str(data.get("CARGA_HORARIA", "")).strip()
        match = re.search(r"\d+", workload)
        if workload and (match is None or int(match.group()) <= 0):
            issues.append(ValidationIssue("CARGA_HORARIA", "Carga horária deve conter um número positivo."))

        weekly_load = str(data.get("CARGA_SEMANAL", "")).strip()
        weekly_match = re.search(r"\d+(?:[.,]\d+)?", weekly_load)
        if weekly_load and (
            weekly_match is None
            or float(weekly_match.group().replace(",", ".")) <= 0
            or float(weekly_match.group().replace(",", ".")) > 30
        ):
            issues.append(
                ValidationIssue(
                    "CARGA_SEMANAL",
                    "Carga semanal deve ser positiva e não pode ultrapassar 30 horas.",
                )
            )

        self._professional_context(data, issues)
        area = normalize_label(str(data.get("AREA_ESTAGIO", "")))
        valid_areas = {
            "estetica", "biomedicina estetica", "drogaria", "farmacia drogaria",
            "hospitalar", "farmacia hospitalar", "manipulacao", "farmacia manipulacao",
            "controle de qualidade", "farmacia controle de qualidade",
        }
        if area and area not in valid_areas:
            issues.append(ValidationIssue("AREA_ESTAGIO", "Área de estágio não reconhecida."))

        return tuple(issues)

    def validate(self, data: dict[str, str]) -> None:
        errors = tuple(issue for issue in self.check(data) if issue.severity == "erro")
        if errors:
            raise InputValidationError(errors)

    @staticmethod
    def _date_order(dates: dict[str, datetime], start: str, end: str, message: str, issues: list[ValidationIssue]) -> None:
        if start in dates and end in dates and dates[end] < dates[start]:
            issues.append(ValidationIssue(end, message))

    @staticmethod
    def _professional_context(data: dict[str, str], issues: list[ValidationIssue]) -> None:
        area = normalize_label(str(data.get("AREA_ESTAGIO", "")))
        council = normalize_label(str(data.get("CONSELHO_RT", "")))
        role = normalize_label(str(data.get("CARGO_REPRESENTANTE", "")))
        if area in {"estetica", "biomedicina estetica"}:
            expected_council, expected_role, context = "crbm", "biomed", "Biomedicina Estética"
        elif area in {"drogaria", "farmacia drogaria", "hospitalar", "farmacia hospitalar", "manipulacao", "farmacia manipulacao", "controle de qualidade", "farmacia controle de qualidade"}:
            expected_council, expected_role, context = "crf", "farmac", "Farmácia"
        else:
            return
        if council and not re.match(rf"^{expected_council}(?:\b|[- ])", council):
            issues.append(ValidationIssue("CONSELHO_RT", f"Conselho incompatível com {context}; esperado {expected_council.upper()}."))
        if role and expected_role not in role:
            label = "biomédico" if expected_role == "biomed" else "farmacêutico"
            issues.append(ValidationIssue("CARGO_REPRESENTANTE", f"Cargo incompatível com {context}; esperado cargo de {label}."))
