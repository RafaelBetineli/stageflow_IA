"""Interface local do StageFlow construída com Streamlit."""

from __future__ import annotations

import csv
from datetime import date, datetime, time
from html import escape
from io import BytesIO, StringIO
import os
from pathlib import Path
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from stageflow.academics import AcademicRules, ModuleDefinition, max_activities
from stageflow.activity_suggestions import ActivitySuggestionService
from stageflow.activities import (
    ActivityAllocator,
    ActivityAllocation,
    activity_document_fields,
    build_activity_prompt,
)
from stageflow.documents import DEFAULT_OUTPUT
from stageflow.extraction import OllamaClient, OllamaError
from stageflow.fields import (
    FIELD_BY_KEY,
    GROUPS,
    REQUIRED_FIELDS,
    FieldDefinition,
    fields_for_group,
)
from stageflow.models import AnalysisResult, ValidationIssue
from stageflow.repository import (
    COMPANY_FIELDS,
    DEFAULT_DATABASE,
    LocalRepository,
    normalize_cnpj,
)
from stageflow.scheduling import (
    HolidayProvider,
    ScheduleCalculator,
    ScheduleResult,
    WEEKDAY_NAMES,
    attendance_rows,
    format_decimal_hours,
    schedule_fields,
)
from stageflow.workflow import StageFlow


st.set_page_config(
    page_title="StageFlow",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

STYLES = """
<style>
  :root { --sf-green:#236b58; --sf-ink:#1d3430; --sf-muted:#63756f; --sf-line:#dce6e1; }
  .stApp { background:#f6f8f7; color:var(--sf-ink); }
  [data-testid="stHeader"] { background: transparent; }
  .block-container { max-width:1180px; padding-top:2.1rem; padding-bottom:3rem; }
  h2, h3 { color:var(--sf-ink); letter-spacing:-.025em; }
  [data-testid="stHeadingWithActionElements"] h3 { font-size:1.35rem; }
  [data-testid="stCaptionContainer"] { color:var(--sf-muted); }
  .sf-topbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1.5rem; }
  .sf-brand { display:flex; align-items:center; gap:.8rem; }
  .sf-mark { width:2.8rem; height:2.8rem; display:grid; place-items:center; flex-shrink:0; border-radius:.85rem; background:var(--sf-green); color:white; font-weight:700; letter-spacing:-.05em; }
  .sf-brand h1 { font-size:1.5rem; margin:0; padding:0; font-weight:700; letter-spacing:-.04em; }
  .sf-brand p { margin:.2rem 0 0; color:var(--sf-muted); font-size:.85rem; }
  .sf-badge { display:inline-flex; align-items:center; padding:.35rem .7rem; border-radius:2rem; background:#e8f2ed; color:#285e4e; font-size:.75rem; font-weight:600; white-space:nowrap; }
  .sf-context { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:.6rem; padding:1rem 1.2rem; background:white; border:1px solid var(--sf-line); border-radius:.85rem; margin-bottom:1rem; }
  .sf-context strong { display:block; font-size:1rem; overflow-wrap:anywhere; }
  .sf-eyebrow { color:var(--sf-muted); font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; font-weight:700; margin-bottom:.3rem; }
  .sf-context-meta { color:var(--sf-muted); font-size:.85rem; }
  .sf-steps { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.6rem; margin:0 0 1.4rem; }
  .sf-step { display:flex; align-items:center; gap:.7rem; padding:.85rem; border-radius:.8rem; background:#fff; border:1px solid var(--sf-line); color:var(--sf-muted); }
  .sf-step-number { display:grid; place-items:center; width:1.8rem; height:1.8rem; flex-shrink:0; border-radius:50%; background:#f0f4f2; font-size:.8rem; font-weight:700; }
  .sf-step strong { display:block; font-size:.85rem; font-weight:600; }
  .sf-step small { display:block; margin-top:.15rem; font-size:.7rem; }
  .sf-step.active { background:#eaf4ef; color:#184c3e; border-color:#80b39f; }
  .sf-step.active .sf-step-number { background:var(--sf-green); color:#fff; }
  .sf-step.complete .sf-step-number { background:#e8f2ed; color:var(--sf-green); }
  .sf-step.complete { color:#356553; }
  .sf-private { padding:1rem; background:#edf5f0; border:1px solid #d7e8de; border-radius:.8rem; color:#315f52; font-size:.88rem; line-height:1.6; }
  .sf-private strong { display:block; margin-bottom:.25rem; }
  .sf-panel-title { font-size:.75rem; text-transform:uppercase; letter-spacing:.07em; color:var(--sf-muted); font-weight:700; margin:.5rem 0 .8rem; }
  .sf-suggestion { display:flex; align-items:flex-start; gap:.75rem; padding:.85rem 1rem; background:#f2f6fb; border:1px solid #dde6f0; border-radius:.65rem; margin:.4rem 0; color:#334d6b; }
  .sf-suggestion span { font-weight:700; font-size:.8rem; padding-top:.15rem; }
  .sf-activity-title { display:flex; align-items:center; gap:.7rem; min-height:4.5rem; overflow-wrap:anywhere; }
  .sf-activity-title span { display:grid; place-items:center; width:1.8rem; height:1.8rem; border-radius:.5rem; background:#eaf4ef; color:var(--sf-green); flex-shrink:0; font-size:.8rem; font-weight:700; }
  .sf-hours { min-height:4.5rem; display:flex; flex-direction:column; justify-content:center; align-items:flex-end; }
  .sf-hours strong { font-size:1.45rem; letter-spacing:-.04em; color:var(--sf-green); }
  .sf-hours small { font-size:.7rem; color:var(--sf-muted); }
  .sf-total { display:flex; justify-content:space-between; align-items:center; gap:.8rem; padding:1rem 1.2rem; border-radius:.8rem; background:#eaf4ef; color:#234f40; margin:.7rem 0; }
  .sf-total strong { font-size:1.1rem; }
  .sf-total.invalid { background:#fff2f0; color:#9b3328; }
  .st-key-sf_activity_assistant, [class*="st-key-sf_activity_card_"] { background:white; border-radius:.85rem; }
  div[data-testid="stMetric"] { background:white; border:1px solid var(--sf-line); padding:.85rem 1rem; border-radius:.8rem; }
  [data-testid="stMetricLabel"] { color:var(--sf-muted); font-size:.8rem; }
  [data-testid="stMetricValue"] { font-size:1.55rem; font-weight:600; letter-spacing:-.04em; }
  [data-testid="stVerticalBlockBorderWrapper"] > div { border-color:var(--sf-line) !important; border-radius:.9rem !important; }
  [data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stTextAreaRootElement"] { border-radius:.6rem; }
  [data-testid="stTextInputRootElement"]:focus-within, [data-testid="stTextAreaRootElement"]:focus-within { box-shadow:0 0 0 3px #236b581a; }
  [data-testid="stTextInputRootElement"] input:disabled { -webkit-text-fill-color:#587168; }
  .stButton button, .stDownloadButton button, .stLinkButton a { border-radius:.65rem; min-height:2.7rem; font-weight:600; }
  button[kind="primary"] { background:var(--sf-green); border-color:var(--sf-green); }
  button[kind="primary"]:not(:disabled):hover { background:#195340; border-color:#195340; }
  button:focus-visible, a:focus-visible { outline:3px solid #80b39f; outline-offset:3px; }
  [data-baseweb="tab-list"] { gap:.35rem; border-bottom:1px solid var(--sf-line); margin-bottom:.9rem; }
  [data-baseweb="tab"] { padding:.65rem 1rem; border-radius:.5rem .5rem 0 0; }
  [data-baseweb="tab"][aria-selected="true"] { background:#eaf4ef; color:#184c3e; font-weight:600; }
  [data-testid="stExpander"] { background:#fff; border-radius:.7rem; }
  [data-testid="stAlert"] { border-radius:.7rem; }
  [data-testid="stDataFrame"] { border:1px solid var(--sf-line); border-radius:.7rem; overflow:hidden; }
  div[data-testid="stDownloadButton"] button { width:100%; }
  @media (max-width:720px) {
    .block-container { padding-top:1.25rem; padding-left:1rem; padding-right:1rem; }
    .sf-topbar { align-items:flex-start; }
    .sf-topbar > .sf-badge { display:none; }
    .sf-brand p { font-size:.75rem; }
    .sf-steps { grid-template-columns:1fr 1fr; gap:.4rem; }
    .sf-step { padding:.65rem; gap:.5rem; }
    .sf-step strong { font-size:.8rem; }
    .sf-context { padding:.85rem; }
    .sf-hours { align-items:flex-start; min-height:2.5rem; }
  }
  @media (prefers-reduced-motion:reduce) { * { scroll-behavior:auto !important; } }
</style>
"""
st.markdown(STYLES, unsafe_allow_html=True)

ACADEMIC_RULES = AcademicRules()
SCHEDULE_CALCULATOR = ScheduleCalculator()
HOLIDAY_PROVIDER = HolidayProvider()
ACTIVITY_ALLOCATOR = ActivityAllocator()

AREA_OPTIONS = {
    "Farmácia": ("Drogaria", "Hospitalar", "Manipulação", "Controle de qualidade"),
    "Biomedicina": ("Estética",),
}


def _initialize() -> None:
    defaults = {
        "sf_stage": "input",
        "sf_message": "",
        "sf_analysis": None,
        "sf_data": {},
        "sf_manual_fields": set(),
        "sf_generated": (),
        "sf_confirmed": False,
        "sf_overwrite": False,
        "sf_course": "Farmácia",
        "sf_kind": "Regular",
        "sf_dp_module": "Módulo I",
        "sf_area": "Drogaria",
        "sf_start_date": date.today(),
        "sf_manual_exclusions": "",
        "sf_activity_text": "",
        "sf_allocations": (),
        "sf_schedule": None,
        "sf_notice": "",
        "sf_selected_model": os.getenv("STAGEFLOW_OLLAMA_MODEL", "qwen3:8b"),
        "sf_ollama_busy": False,
        "sf_activity_request": None,
        "sf_activity_suggestions": (),
        "sf_activity_suggestion_context": None,
        "sf_activity_error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset() -> None:
    for key in tuple(st.session_state):
        if key.startswith("sf_"):
            del st.session_state[key]
    _initialize()


@st.cache_data(ttl=10, show_spinner=False)
def _available_models(base_url: str) -> tuple[tuple[str, ...], str | None]:
    try:
        return OllamaClient(base_url=base_url, timeout_seconds=5).list_models(), None
    except OllamaError as error:
        return (), str(error)


@st.cache_resource(show_spinner=False)
def _local_repository(database_path: str) -> LocalRepository:
    return LocalRepository(database_path)


def _repository() -> LocalRepository:
    database = os.getenv("STAGEFLOW_DATABASE", str(DEFAULT_DATABASE))
    return _local_repository(database)


def _header() -> None:
    st.markdown(
        '<div class="sf-topbar"><div class="sf-brand"><div class="sf-mark">SF</div><div>'
        '<h1>StageFlow</h1><p>Revisão e preenchimento de documentos de estágio</p>'
        '</div></div><span class="sf-badge">Seu fluxo, organizado</span></div>',
        unsafe_allow_html=True,
    )
    data = st.session_state.sf_data
    current = st.session_state.sf_stage
    if current != "input":
        context = [data.get("CURSO", "") or st.session_state.sf_course]
        if current in ("complete", "done"):
            context[0] = st.session_state.sf_course
            try:
                if st.session_state.sf_kind == "DP":
                    module = st.session_state.get(
                        f"sf_dp_module_{context[0].casefold()}", "Módulo I",
                    )
                    definition = ACADEMIC_RULES.for_module(context[0], module)
                else:
                    definition = ACADEMIC_RULES.regular(context[0], data.get("SEMESTRE", ""))
                context.append(definition.module)
            except ValueError:
                pass
        elif data.get("SEMESTRE"):
            context.append(data["SEMESTRE"])
        st.markdown(
            '<div class="sf-context"><div><div class="sf-eyebrow">Demanda atual</div>'
            f'<strong>{escape(data.get("NOME_ALUNO") or "Aluno ainda não identificado")}</strong>'
            f'</div><div class="sf-context-meta">{escape(" · ".join(context))}</div></div>',
            unsafe_allow_html=True,
        )
    stages = (
        ("input", "Mensagem"),
        ("review", "Dados recebidos"),
        ("complete", "Complementação"),
        ("done", "Documentos"),
    )
    current_index = next(index for index, (key, _) in enumerate(stages) if key == current)
    steps = []
    for index, (key, label) in enumerate(stages):
        completed = index < current_index
        status = "active" if key == current else "complete" if completed else ""
        caption = "Etapa atual" if key == current else "Concluída" if completed else "A seguir"
        number = "✓" if completed else str(index + 1)
        aria = ' aria-current="step"' if key == current else ""
        steps.append(
            f'<div class="sf-step {status}"{aria}><span class="sf-step-number">{number}</span>'
            f'<div><strong>{label}</strong><small>{caption}</small></div></div>'
        )
    st.markdown(
        '<nav class="sf-steps" aria-label="Etapas do preenchimento">' + "".join(steps) + "</nav>",
        unsafe_allow_html=True,
    )


def _panel_title(title: str) -> None:
    st.markdown(f'<div class="sf-panel-title">{escape(title)}</div>', unsafe_allow_html=True)


def _mark_manual(key: str) -> None:
    st.session_state.sf_manual_fields.add(key)
    widget = _widget_key(key)
    if widget in st.session_state:
        st.session_state.sf_data[key] = str(st.session_state[widget]).strip()


def _widget_key(field_key: str) -> str:
    return f"sf_field_{field_key}"


def _initialize_field_widgets(data: dict[str, str]) -> None:
    st.session_state.sf_data = {
        key: str(data.get(key, "")).strip() for key in FIELD_BY_KEY
    }
    for key in FIELD_BY_KEY:
        st.session_state[_widget_key(key)] = st.session_state.sf_data[key]


def _ensure_field_widget(key: str) -> None:
    widget = _widget_key(key)
    # `sf_data` é a fonte permanente. O Streamlit pode limpar chaves de widgets
    # que deixam de ser exibidos ao mudar de etapa; recriamos a chave sempre
    # antes de renderizar o campo.
    st.session_state[widget] = str(st.session_state.sf_data.get(key, ""))


def _set_field(key: str, value: object) -> None:
    formatted = str(value).strip()
    st.session_state.sf_data[key] = formatted
    widget = _widget_key(key)
    if widget in st.session_state:
        st.session_state[widget] = formatted


def _current_data() -> dict[str, str]:
    current = {
        key: str(st.session_state.sf_data.get(key, "")).strip()
        for key in FIELD_BY_KEY
    }
    st.session_state.sf_data = current
    return current


def _prepare_planner(data: dict[str, str]) -> None:
    course = str(data.get("CURSO", "")).strip()
    if course in ACADEMIC_RULES.COURSES:
        st.session_state.sf_course = course
    area = str(data.get("AREA_ESTAGIO", "")).strip()
    if area in AREA_OPTIONS[st.session_state.sf_course]:
        st.session_state.sf_area = area
    combined_dp = f"{data.get('DEPENDENCIA', '')} {data.get('SEMESTRE', '')}".casefold()
    if "dp" in combined_dp:
        st.session_state.sf_kind = "DP"
    informed_start = str(data.get("DATA_INICIO_ESTAGIO", "")).strip()
    try:
        st.session_state.sf_start_date = datetime.strptime(informed_start, "%d/%m/%Y").date()
    except ValueError:
        pass


def _issues_by_key(issues: tuple[ValidationIssue, ...]) -> dict[str, list[ValidationIssue]]:
    grouped: dict[str, list[ValidationIssue]] = {}
    for issue in issues:
        if issue.key:
            grouped.setdefault(issue.key, []).append(issue)
    return grouped


def _field_help(key: str, analysis: AnalysisResult) -> str | None:
    if key in st.session_state.sf_manual_fields:
        return "Editado manualmente nesta revisão."
    evidence = analysis.extraction.evidence.get(key)
    if not evidence:
        return None
    method = "regras" if evidence.method == "regra" else "IA local"
    return f"Identificado por {method}. Origem: {evidence.source}"


def _render_field(
    definition: FieldDefinition,
    analysis: AnalysisResult,
    issues_by_key,
    *,
    show_messages: bool = True,
) -> None:
    _ensure_field_widget(definition.key)
    field_issues = issues_by_key.get(definition.key, [])
    marker = (
        "🔴"
        if any(item.severity == "erro" for item in field_issues)
        else "⚠️" if field_issues else ""
    )
    optional = " (opcional)" if not definition.required else ""
    st.text_input(
        f"{marker} {definition.label}{optional}".strip(),
        key=_widget_key(definition.key),
        help=_field_help(definition.key, analysis),
        on_change=_mark_manual,
        args=(definition.key,),
    )
    if show_messages:
        for issue in field_issues:
            if issue.severity == "erro":
                st.error(issue.message)
            else:
                st.warning(issue.message)


def _show_input() -> None:
    st.subheader("Cole a mensagem recebida do aluno")
    st.write(
        "Não é necessário organizar ou padronizar. Cole exatamente como a mensagem "
        "chegou no WhatsApp."
    )
    base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    models, ollama_error = _available_models(base_url)
    left, right = st.columns([2, 1], gap="large")
    with left:
        st.text_area(
            "Mensagem do aluno",
            key="sf_message",
            height=430,
            placeholder="Cole aqui todos os dados enviados pelo aluno...",
        )
    with right:
        st.markdown(
            '<div class="sf-private"><strong>🔒 Processamento local</strong>'
            'A mensagem não é gravada pelo StageFlow. Você revisa os dados antes de gerar os arquivos.</div>',
            unsafe_allow_html=True,
        )
        _panel_title("Como organizar os dados")
        if ollama_error or not models:
            st.warning("Ollama não está acessível. Ainda é possível usar apenas as regras.")
            use_ai = st.toggle("Usar IA local", value=False, disabled=True)
            model = "qwen3:8b"
        else:
            st.success(f"Ollama conectado · {len(models)} modelo(s)")
            use_ai = st.toggle("Usar IA local", value=True)
            default_index = models.index("qwen3:8b") if "qwen3:8b" in models else 0
            model = st.selectbox("Modelo", models, index=default_index, disabled=not use_ai)
        st.caption(
            "A IA organiza somente dados recebidos. Módulo, calendário e cargas "
            "serão calculados depois por regras."
        )
        identify = st.button(
            "Identificar e organizar", type="primary", width="stretch",
            disabled=st.session_state.sf_ollama_busy,
        )
    if identify:
        if not st.session_state.sf_message.strip():
            st.error("Cole a mensagem do aluno para continuar.")
            return
        with st.spinner("Organizando as informações..."):
            analysis = StageFlow.ollama(model).analyze(
                st.session_state.sf_message,
                use_ai=use_ai,
                model=model,
            )
        st.session_state.sf_analysis = analysis
        st.session_state.sf_selected_model = model
        st.session_state.sf_data = analysis.extraction.fields.copy()
        st.session_state.sf_manual_fields = set()
        _initialize_field_widgets(st.session_state.sf_data)
        _prepare_planner(st.session_state.sf_data)
        st.session_state.sf_stage = "review"
        st.rerun()


def _show_review() -> None:
    analysis: AnalysisResult = st.session_state.sf_analysis
    current = _current_data()
    all_issues = StageFlow().validate(current)
    student_keys = {
        definition.key for definition in FIELD_BY_KEY.values() if definition.origin == "aluno"
    }
    issues = tuple(issue for issue in all_issues if issue.key in student_keys)
    grouped_issues = _issues_by_key(issues)
    student_required = tuple(
        definition
        for definition in FIELD_BY_KEY.values()
        if definition.origin == "aluno" and definition.required
    )
    missing = sum(
        not current.get(definition.key, "").strip()
        for definition in student_required
    )
    st.subheader("Confira o que foi recebido")
    st.write(
        "Aqui aparecem somente os dados que deveriam vir do aluno. Informações da "
        "empresa e cálculos do estágio serão tratados na próxima etapa."
    )
    columns = st.columns(3)
    columns[0].metric("Obrigatórios recebidos", len(student_required) - missing)
    columns[1].metric("Ainda vazios", missing)
    ai_count = sum(
        evidence.method == "ia" and evidence.key in student_keys
        for evidence in analysis.extraction.evidence.values()
    )
    columns[2].metric("Organizados pela IA", ai_count)
    extraction = analysis.extraction
    if extraction.ai_error:
        st.warning(f"A identificação por IA não foi concluída: {extraction.ai_error}")
    if extraction.duplicates:
        st.warning("Campos repetidos: " + ", ".join(extraction.duplicates) + ".")
    if extraction.ai_notes:
        with st.expander(f"Sugestões recusadas ({len(extraction.ai_notes)})"):
            for note in extraction.ai_notes:
                st.write(f"- {note}")
    if extraction.unrecognized_lines:
        with st.expander(f"Trechos não reconhecidos ({len(extraction.unrecognized_lines)})"):
            st.code("\n".join(extraction.unrecognized_lines), language=None)
    group_tabs = []
    for group_key, group_label in GROUPS:
        definitions = tuple(
            item for item in fields_for_group(group_key) if item.origin == "aluno"
        )
        if definitions:
            group_tabs.append((group_label, definitions))
    tabs = st.tabs([label for label, _ in group_tabs])
    for tab, (_, definitions) in zip(tabs, group_tabs):
        with tab:
            display_columns = st.columns(2, gap="large")
            for index, definition in enumerate(definitions):
                with display_columns[index % 2]:
                    _render_field(definition, analysis, grouped_issues)
    st.divider()
    left, right = st.columns([1, 1.7])
    with left:
        if st.button("Voltar à mensagem", width="stretch"):
            st.session_state.sf_stage = "input"
            st.rerun()
    with right:
        if st.button("Continuar para complementação", type="primary", width="stretch"):
            st.session_state.sf_data = _current_data()
            st.session_state.sf_stage = "complete"
            st.rerun()


def _company_section(analysis: AnalysisResult, repository: LocalRepository) -> None:
    st.subheader("1. Empresa pelo CNPJ")
    _ensure_field_widget("CNPJ")
    cnpj = st.text_input(
        "CNPJ da empresa",
        key=_widget_key("CNPJ"),
        on_change=_mark_manual,
        args=("CNPJ",),
    )
    digits = normalize_cnpj(cnpj)
    actions = st.columns([1, 1, 1.4])
    with actions[0]:
        load = st.button("Buscar no cadastro local", width="stretch")
    with actions[1]:
        url = (
            "https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/"
            f"Cnpjreva_Solicitacao.asp?cnpj={quote(digits)}"
        )
        st.link_button("Abrir consulta oficial", url, width="stretch")
    with actions[2]:
        st.caption(f"CNPJ consultado: {digits}" if len(digits) == 14 else "Confira o CNPJ recebido antes de consultar.")
    if load:
        company = repository.company(cnpj)
        if company:
            for key, value in company.items():
                if key in FIELD_BY_KEY:
                    st.session_state.sf_data[key] = value
                    # O CNPJ já foi renderizado acima; alterar a chave do widget
                    # neste ponto causa erro no Streamlit. A consulta usa o mesmo
                    # CNPJ informado, então basta atualizar os demais campos.
                    if key != "CNPJ":
                        st.session_state[_widget_key(key)] = value
            st.session_state.sf_notice = "Empresa carregada do cadastro local."
            st.rerun()
        else:
            st.warning("Esse CNPJ ainda não está no cadastro local.")
    issues = _issues_by_key(StageFlow().validate(_current_data()))
    columns = st.columns(2, gap="large")
    definitions = tuple(FIELD_BY_KEY[key] for key in COMPANY_FIELDS)
    for index, definition in enumerate(definitions):
        with columns[index % 2]:
            _render_field(definition, analysis, issues, show_messages=False)
    if st.button("Salvar ou atualizar empresa", width="stretch"):
        try:
            repository.save_company(_current_data())
        except ValueError as error:
            st.error(str(error))
        else:
            st.success("Empresa salva localmente para os próximos estágios.")


def _academic_section() -> ModuleDefinition | None:
    st.subheader("2. Curso, módulo e área")
    columns = st.columns(3, gap="large")
    with columns[0]:
        course = st.selectbox("Curso", ACADEMIC_RULES.COURSES, key="sf_course")
    with columns[1]:
        kind = st.radio("Situação", ("Regular", "DP"), horizontal=True, key="sf_kind")
    with columns[2]:
        _ensure_field_widget("SEMESTRE")
        semester = st.text_input(
            "Semestre informado pelo aluno",
            key=_widget_key("SEMESTRE"),
            on_change=_mark_manual,
            args=("SEMESTRE",),
        )
    options = AREA_OPTIONS[course]
    if st.session_state.sf_area not in options:
        st.session_state.sf_area = options[0]
    area = st.selectbox("Área do estágio", options, key="sf_area")
    definition: ModuleDefinition | None = None
    if kind == "Regular":
        try:
            definition = ACADEMIC_RULES.regular(course, semester)
        except ValueError as error:
            st.warning(str(error))
            st.caption("Se for uma dependência, selecione DP e informe o módulo correto.")
        if definition:
            st.text_input(
                "Módulo calculado",
                value=definition.module,
                disabled=True,
                help="Definido automaticamente pelo curso e semestre.",
            )
    else:
        modules = ACADEMIC_RULES.modules_for_course(course)
        module_names = tuple(item.module for item in modules)
        module_state_key = f"sf_dp_module_{course.casefold()}"
        if (
            module_state_key not in st.session_state
            or st.session_state[module_state_key] not in module_names
        ):
            st.session_state[module_state_key] = module_names[0]
        selected = st.selectbox(
            "Módulo da DP",
            module_names,
            key=module_state_key,
            help="Escolha o módulo da dependência, independentemente do semestre atual.",
        )
        definition = ACADEMIC_RULES.for_module(course, selected)
    _set_field("CURSO", course)
    _set_field("AREA_ESTAGIO", area)
    _set_field("DEPENDENCIA", "Sim" if kind == "DP" else "Não")
    role = (
        "Biomédico responsável técnico"
        if course == "Biomedicina"
        else "Farmacêutico responsável técnico"
    )
    _set_field("CARGO_REPRESENTANTE", role)
    st.text_input(
        "Cargo do responsável técnico (calculado)",
        value=role,
        disabled=True,
        help="Preenchido automaticamente pelo curso e atualizado quando você muda o curso.",
    )
    _set_field("MODULO_ESTAGIO", definition.module if definition else "")
    _set_field("CARGA_HORARIA", f"{definition.hours} horas" if definition else "")
    metrics = st.columns(3)
    metrics[0].metric("Módulo", definition.module if definition else "—")
    metrics[1].metric("Carga obrigatória", f"{definition.hours}h" if definition else "—")
    metrics[2].metric("Tipo", kind)
    return definition


def _parse_manual_exclusions(value: str) -> tuple[dict[date, str], tuple[str, ...]]:
    exclusions: dict[date, str] = {}
    errors: list[str] = []
    for line_number, raw_line in enumerate(value.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        raw_date, separator, raw_reason = line.partition("-")
        try:
            day = datetime.strptime(raw_date.strip(), "%d/%m/%Y").date()
        except ValueError:
            errors.append(f"Linha {line_number}: use DD/MM/AAAA - motivo.")
            continue
        exclusions[day] = raw_reason.strip() if separator and raw_reason.strip() else "Exclusão manual"
    return exclusions, tuple(errors)


def _schedule_section(definition: ModuleDefinition | None) -> ScheduleResult | None:
    st.subheader("3. Calendário automático")
    st.write("Informe apenas a data inicial. O padrão é segunda a sexta, das 08h00 às 14h00.")
    start = st.date_input("Data inicial desejada", key="sf_start_date", format="DD/MM/YYYY")
    with st.expander("Ajustar horário ou calendário"):
        times = st.columns(2)
        with times[0]:
            start_time = st.time_input(
                "Horário inicial",
                value=time(8, 0),
                key="sf_start_time_v2",
                step=1800,
            )
        with times[1]:
            end_time = st.time_input(
                "Horário final",
                value=time(14, 0),
                key="sf_end_time_v2",
                step=1800,
            )
        selected_days = st.multiselect(
            "Dias trabalhados",
            WEEKDAY_NAMES,
            default=WEEKDAY_NAMES[:5],
            key="sf_working_days_v2",
        )
        st.text_area(
            "Feriados municipais ou outras datas sem expediente",
            key="sf_manual_exclusions",
            placeholder="20/11/2026 - Feriado municipal\n24/12/2026 - Empresa fechada",
            help="Informe uma data por linha. Feriados nacionais e estaduais são sugeridos automaticamente.",
        )
    if not definition:
        st.info("Defina primeiro um módulo válido para calcular o calendário.")
        return None
    working_weekdays = tuple(index for index, name in enumerate(WEEKDAY_NAMES) if name in selected_days)
    state = str(st.session_state.get(_widget_key("ESTADO_EMPRESA"), "")).strip()
    try:
        automatic_holidays = HOLIDAY_PROVIDER.for_years(range(start.year, start.year + 3), state)
    except (KeyError, ValueError) as error:
        automatic_holidays = HOLIDAY_PROVIDER.for_years(range(start.year, start.year + 3))
        st.warning(f"Estado não reconhecido; usando apenas feriados nacionais. {error}")
    manual, manual_errors = _parse_manual_exclusions(st.session_state.sf_manual_exclusions)
    for error in manual_errors:
        st.error(error)
    try:
        schedule = SCHEDULE_CALCULATOR.calculate(
            requested_start=start,
            total_hours=definition.hours,
            start_time=start_time,
            end_time=end_time,
            working_weekdays=working_weekdays,
            excluded_dates={**automatic_holidays, **manual},
        )
    except ValueError as error:
        st.error(str(error))
        st.session_state.sf_schedule = None
        return None
    for key, value in schedule_fields(schedule, working_weekdays).items():
        _set_field(key, value)
    st.session_state.sf_schedule = schedule
    metrics = st.columns(5)
    metrics[0].metric("Início efetivo", schedule.start_date.strftime("%d/%m/%Y"))
    metrics[1].metric("Término", schedule.end_date.strftime("%d/%m/%Y"))
    metrics[2].metric("Dias", len(schedule.days))
    metrics[3].metric("Total", f"{format_decimal_hours(schedule.total_hours)}h")
    metrics[4].metric("Último dia", f"{format_decimal_hours(schedule.days[-1].hours)}h")
    rows = attendance_rows(schedule)
    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        height=310,
    )
    export = StringIO(newline="")
    writer = csv.DictWriter(export, fieldnames=tuple(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    download, hint = st.columns([1, 2])
    with download:
        st.download_button(
            "Baixar calendário em CSV",
            data="\ufeff" + export.getvalue(),
            file_name="calendario_estagio.csv",
            mime="text/csv",
            width="stretch",
        )
    with hint:
        st.caption(
            "Essas linhas também serão preenchidas automaticamente na ficha de frequência do relatório."
        )
    with st.expander("Lista tabulada para copiar"):
        st.code(
            "\n".join(
                "\t".join(row.values())
                for row in rows
            ),
            language=None,
        )
    if schedule.excluded_holidays:
        with st.expander(f"Datas ignoradas ({len(schedule.excluded_holidays)})"):
            for day, reason in schedule.excluded_holidays:
                st.write(f"- {day:%d/%m/%Y} — {reason}")
    return schedule


def _apply_activity_suggestions() -> None:
    st.session_state.sf_activity_text = "\n".join(st.session_state.sf_activity_suggestions)
    for key in tuple(st.session_state):
        if key.startswith(("sf_activity_weight_", "sf_activity_hours_")):
            del st.session_state[key]
    st.session_state.sf_manual_activity_hours = False
    st.session_state.sf_confirmed = False
    st.session_state.sf_activity_suggestions = ()


def _discard_activity_suggestions() -> None:
    st.session_state.sf_activity_suggestions = ()


def _activity_ai_controls(
    definition: ModuleDefinition | None,
    previous: tuple[str, ...],
    count: int,
) -> None:
    base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    models, _ = _available_models(base_url)
    context = (
        st.session_state.sf_course, st.session_state.sf_area,
        definition.module if definition else "", count,
    )
    if st.session_state.sf_activity_suggestion_context != context:
        st.session_state.sf_activity_suggestions = ()
    if models:
        model_key = "sf_activity_model"
        if st.session_state.get(model_key) not in models:
            preferred = st.session_state.sf_selected_model
            st.session_state[model_key] = preferred if preferred in models else models[0]
        model = st.selectbox(
            "Modelo para sugerir atividades", models, key=model_key,
            disabled=st.session_state.sf_ollama_busy,
        )
        st.session_state.sf_selected_model = model
    else:
        model = st.session_state.sf_selected_model
        st.warning("Ollama indisponível ou sem modelos. Você pode preencher as atividades manualmente.")
    st.caption(
        "Esta chamada envia apenas curso, módulo, área, quantidade e títulos recentes. "
        "Não envia a mensagem nem os dados pessoais do aluno."
    )
    clicked = st.button(
        "Sugerir atividades com IA local", width="stretch",
        disabled=not models or not definition or st.session_state.sf_ollama_busy,
    )
    if clicked:
        st.session_state.sf_activity_request = {
            "model": model, "base_url": base_url,
            "course": context[0], "area": context[1], "module": context[2],
            "count": count, "previous_titles": previous,
            "started": False,
        }
        st.session_state.sf_ollama_busy = True
        st.session_state.sf_activity_error = ""
    if st.session_state.sf_activity_error:
        st.error(st.session_state.sf_activity_error)
    suggestions = st.session_state.sf_activity_suggestions
    if suggestions:
        _panel_title("Sugestões da IA · aguardando sua aprovação")
        for position, title in enumerate(suggestions, start=1):
            st.markdown(
                f'<div class="sf-suggestion"><span>{position:02d}</span><div>{escape(title)}</div></div>',
                unsafe_allow_html=True,
            )
        st.caption(
            "Confirme a compatibilidade e o que o aluno realmente realizou. "
            "Ao usar estas sugestões, os títulos atuais serão substituídos; "
            "você ainda poderá editá-los abaixo."
        )
        use, discard = st.columns(2)
        use.button(
            "Usar estas sugestões", width="stretch", on_click=_apply_activity_suggestions,
            disabled=st.session_state.sf_ollama_busy,
        )
        discard.button(
            "Descartar sugestões", width="stretch", on_click=_discard_activity_suggestions,
            disabled=st.session_state.sf_ollama_busy,
        )


def _process_activity_request() -> None:
    request = st.session_state.sf_activity_request
    if not request:
        return
    # Só reinicia depois de renderizar todos os campos, preservando seus valores.
    # A próxima passagem mostra o botão desabilitado antes de iniciar a chamada.
    if not request["started"]:
        request["started"] = True
        st.rerun()
    st.session_state.sf_activity_request = None
    try:
        with st.spinner("Sugerindo apenas os títulos das atividades..."):
            client = OllamaClient(model=request["model"], base_url=request["base_url"])
            suggestions = ActivitySuggestionService(client).suggest(
                course=request["course"], area=request["area"],
                module=request["module"], count=request["count"],
                previous_titles=request["previous_titles"],
            )
        st.session_state.sf_activity_suggestions = suggestions
        st.session_state.sf_activity_suggestion_context = (
            request["course"], request["area"], request["module"], request["count"],
        )
    except (OllamaError, ValueError) as failure:
        st.session_state.sf_activity_error = str(failure)
    finally:
        st.session_state.sf_ollama_busy = False
    st.rerun()


def _activity_section(
    definition: ModuleDefinition | None,
    repository: LocalRepository,
) -> tuple[ActivityAllocation, ...]:
    st.subheader("4. Atividades e distribuição de horas")
    course = st.session_state.sf_course
    area = st.session_state.sf_area
    maximum = max_activities(course)
    previous = repository.activity_titles(area, limit=30)
    prompt_count_key = "sf_prompt_activity_count_v2"
    if (
        prompt_count_key in st.session_state
        and int(st.session_state[prompt_count_key]) > maximum
    ):
        del st.session_state[prompt_count_key]
    prompt_count = st.number_input(
        "Quantidade de atividades para sugerir",
        min_value=1,
        max_value=maximum,
        value=min(3, maximum),
        key=prompt_count_key,
    )
    prompt = build_activity_prompt(
        area=area,
        course=course,
        module=definition.module if definition else "módulo ainda não definido",
        count=int(prompt_count),
        previous_titles=previous,
    )
    with st.expander("Prompt pronto para copiar para o ChatGPT"):
        st.code(prompt, language=None)
        if previous:
            st.caption(f"O prompt considera {len(previous)} atividade(s) anteriores em {area}.")
    with st.container(border=True, key="sf_activity_assistant"):
        _panel_title("Assistente de atividades · opcional")
        _activity_ai_controls(definition, previous, int(prompt_count))
    _panel_title("Atividades escolhidas por você")
    st.text_area(
        "Atividades escolhidas — uma por linha",
        key="sf_activity_text",
        placeholder="Conferência de medicamentos\nControle de estoque\nOrientação ao paciente",
    )
    titles = tuple(dict.fromkeys(line.strip() for line in st.session_state.sf_activity_text.splitlines() if line.strip()))
    if len(titles) > maximum:
        st.error(f"Os modelos de {course} aceitam no máximo {maximum} atividades.")
        st.session_state.sf_allocations = ()
        return ()
    if not titles or not definition:
        st.info("Cole as atividades escolhidas para distribuir a carga horária.")
        st.session_state.sf_allocations = ()
        return ()
    weighted: list[tuple[str, int]] = []
    hour_previews = []
    for index, title in enumerate(titles, start=1):
        with st.container(border=True, key=f"sf_activity_card_{index}"):
            columns = st.columns([4, 1, 1], vertical_alignment="center")
            columns[0].markdown(
                f'<div class="sf-activity-title"><span>{index:02d}</span><strong>{escape(title)}</strong></div>',
                unsafe_allow_html=True,
            )
            weight = columns[1].number_input(
                "Peso",
                min_value=1,
                max_value=10,
                value=5,
                key=f"sf_activity_weight_{index}",
                help="Quanto maior o peso, maior a parte da carga horária destinada à atividade.",
            )
            hour_previews.append(columns[2].empty())
            weighted.append((title, int(weight)))
            matches = repository.similar_activities(area, title)
            if matches:
                st.warning(f"Atividade semelhante já utilizada em {area}: " + ", ".join(matches[:3]))
    allocations = ACTIVITY_ALLOCATOR.allocate(definition.hours, tuple(weighted))
    manual_hours = st.checkbox(
        "Ajustar as horas diretamente",
        key="sf_manual_activity_hours",
        help="Use quando preferir informar as horas em vez de controlar a proporção pelos pesos.",
    )
    if manual_hours:
        adjusted: list[ActivityAllocation] = []
        hour_columns = st.columns(len(allocations))
        for index, (column, allocation) in enumerate(zip(hour_columns, allocations), start=1):
            with column:
                hours = st.number_input(
                    f"Horas — atividade {index}",
                    min_value=0,
                    max_value=definition.hours,
                    value=allocation.hours,
                    step=1,
                    key=f"sf_activity_hours_{index}",
                )
            adjusted.append(
                ActivityAllocation(allocation.title, allocation.weight, int(hours))
            )
        allocations = tuple(adjusted)
    for preview, allocation in zip(hour_previews, allocations):
        preview.markdown(
            f'<div class="sf-hours"><strong>{allocation.hours}h</strong>'
            f'<small>{"Horas definidas" if manual_hours else "Horas sugeridas"}</small></div>',
            unsafe_allow_html=True,
        )
    total = sum(item.hours for item in allocations)
    invalid = " invalid" if total != definition.hours else ""
    st.markdown(
        f'<div class="sf-total{invalid}"><span>Carga horária distribuída</span>'
        f'<strong>{total} / {definition.hours}h</strong></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Total distribuído: {sum(item.hours for item in allocations)}h. "
        "Altere os pesos para ajustar a proporção."
    )
    if sum(item.hours for item in allocations) != definition.hours:
        st.error(
            f"A distribuição precisa somar exatamente {definition.hours}h antes da geração."
        )
        st.session_state.sf_allocations = ()
        return ()
    st.session_state.sf_allocations = allocations
    return allocations


def _final_review_and_generate(
    analysis: AnalysisResult,
    repository: LocalRepository,
    allocations: tuple[ActivityAllocation, ...],
) -> None:
    st.subheader("5. Revisão final e documentos")
    with st.expander("Reabrir dados recebidos do aluno"):
        issues = _issues_by_key(StageFlow().validate(_current_data()))
        definitions = tuple(
            definition
            for definition in FIELD_BY_KEY.values()
            if definition.origin == "aluno"
            and definition.key not in (*COMPANY_FIELDS, "CNPJ", "SEMESTRE")
        )
        columns = st.columns(2, gap="large")
        for index, definition in enumerate(definitions):
            with columns[index % 2]:
                _render_field(definition, analysis, issues, show_messages=False)
    data = _current_data()
    validation_issues = StageFlow().validate(data)
    errors = tuple(issue for issue in validation_issues if issue.severity == "erro")
    warnings = tuple(issue for issue in validation_issues if issue.severity == "atencao")
    if not allocations:
        errors = (*errors, ValidationIssue(None, "Informe ao menos uma atividade."))
    summary = st.columns(4)
    filled = sum(bool(data.get(key, "").strip()) for key in REQUIRED_FIELDS)
    summary[0].metric("Campos", f"{filled}/{len(REQUIRED_FIELDS)}")
    summary[1].metric("Pendências", len(errors))
    summary[2].metric("Atenções", len(warnings))
    summary[3].metric("Atividades", len(allocations))
    if errors:
        st.info("Resolva as pendências abaixo para liberar a geração dos documentos.")
        with st.expander("Pendências para gerar", expanded=True):
            for issue in errors:
                st.error(issue.message)
    if warnings:
        with st.expander("Atenções para conferir"):
            st.caption("São avisos para sua revisão. Eles não bloqueiam a geração.")
            for issue in warnings:
                st.warning(issue.message)
    if not errors:
        st.success("Tudo pronto para gerar. Confirme a revisão dos dados e dos cálculos abaixo.")
    st.divider()
    controls = st.columns([1, 1.4, 1.2])
    with controls[0]:
        if st.button("Voltar aos dados recebidos", width="stretch"):
            st.session_state.sf_stage = "review"
            st.rerun()
    with controls[1]:
        st.checkbox("Revisei os dados e os cálculos", key="sf_confirmed", disabled=bool(errors))
        st.checkbox("Substituir documentos existentes", key="sf_overwrite")
    with controls[2]:
        generate = st.button(
            "Gerar os 3 documentos",
            type="primary",
            width="stretch",
            disabled=bool(errors) or not st.session_state.sf_confirmed,
        )
    if generate:
        final_data = {**data, **activity_document_fields(allocations)}
        try:
            with st.spinner("Preenchendo os modelos..."):
                paths = StageFlow().generate(
                    final_data,
                    DEFAULT_OUTPUT,
                    overwrite=st.session_state.sf_overwrite,
                    schedule=st.session_state.sf_schedule,
                )
            repository.save_company(final_data)
            repository.save_activities(
                area=final_data["AREA_ESTAGIO"],
                course=final_data["CURSO"],
                module=final_data["MODULO_ESTAGIO"],
                student_reference=final_data["NOME_ALUNO"],
                allocations=allocations,
            )
        except Exception as error:
            st.error(str(error))
        else:
            st.session_state.sf_generated = tuple(str(path) for path in paths)
            st.session_state.sf_stage = "done"
            st.rerun()


def _show_complete() -> None:
    analysis: AnalysisResult = st.session_state.sf_analysis
    repository = _repository()
    if st.session_state.sf_notice:
        st.success(st.session_state.sf_notice)
        st.session_state.sf_notice = ""
    st.subheader("Complete apenas o que depende de você")
    st.write(
        "Estes dados são consultados, definidos ou calculados. Eles não contam como "
        "informações esquecidas pelo aluno."
    )
    company_tab, schedule_tab, activity_tab, final_tab = st.tabs(
        ("Empresa", "Estágio e calendário", "Atividades", "Revisão final")
    )
    with company_tab:
        _company_section(analysis, repository)
    with schedule_tab:
        definition = _academic_section()
        st.divider()
        _schedule_section(definition)
    with activity_tab:
        allocations = _activity_section(definition, repository)
    with final_tab:
        _final_review_and_generate(analysis, repository, allocations)
    _process_activity_request()


def _zip_documents(paths: tuple[Path, ...]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, arcname=path.name)
    return buffer.getvalue()


def _show_done() -> None:
    paths = tuple(Path(path) for path in st.session_state.sf_generated)
    st.success("Documentos gerados e histórico atualizado.")
    st.subheader("Arquivos prontos")
    for path in paths:
        label = path.stem.replace("_", " ").title()
        st.download_button(
            f"Baixar {label}",
            data=path.read_bytes(),
            file_name=path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
        )
    if paths:
        st.download_button(
            "Baixar os 3 documentos em ZIP",
            data=_zip_documents(paths),
            file_name="documentos_estagio.zip",
            mime="application/zip",
            type="primary",
            width="stretch",
        )
    st.info(
        "Os títulos e as cargas das atividades foram preenchidos. Os textos acadêmicos "
        "permanecem em branco para sua edição manual."
    )
    if st.button("Iniciar nova demanda"):
        _reset()
        st.rerun()


_initialize()
_header()
if st.session_state.sf_stage == "input":
    _show_input()
elif st.session_state.sf_stage == "review":
    _show_review()
elif st.session_state.sf_stage == "complete":
    _show_complete()
else:
    _show_done()
