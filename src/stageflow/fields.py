"""Catálogo central dos campos aceitos pelo StageFlow."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    key: str
    label: str
    group: str
    required: bool = True
    aliases: tuple[str, ...] = ()
    origin: str = "aluno"


GROUPS = (
    ("aluno", "Aluno"),
    ("academico", "Dados acadêmicos"),
    ("empresa", "Empresa"),
    ("responsavel", "Responsável técnico"),
    ("estagio", "Estágio"),
    ("seguro", "Seguro"),
)


FIELD_DEFINITIONS = (
    FieldDefinition("NOME_ALUNO", "Nome do aluno", "aluno", aliases=("Nome aluno", "Aluno", "Nome completo")),
    FieldDefinition("RA_ALUNO", "RA", "aluno", aliases=("Registro acadêmico", "Matrícula")),
    FieldDefinition("TELEFONE_ALUNO", "Telefone do aluno", "aluno", aliases=("Telefone aluno", "Celular", "Nº celular", "N° celular", "WhatsApp")),
    FieldDefinition("EMAIL_ALUNO", "E-mail do aluno", "aluno", aliases=("E-mail aluno", "Email aluno", "E-mail", "Endereço de e-mail", "Endereço de email")),
    FieldDefinition("CPF", "CPF", "aluno"),
    FieldDefinition("RG", "RG", "aluno", aliases=("Documento de identidade",)),
    FieldDefinition("ENDERECO_ALUNO", "Endereço do aluno", "aluno", aliases=("Endereço aluno", "Endereço residencial")),
    FieldDefinition("BAIRRO_ALUNO", "Bairro do aluno", "aluno", aliases=("Bairro aluno", "Bairro")),
    FieldDefinition("CIDADE_ALUNO", "Cidade do aluno", "aluno", aliases=("Cidade aluno", "Cidade")),
    FieldDefinition("ESTADO_ALUNO", "Estado do aluno", "aluno", aliases=("Estado aluno", "UF aluno", "UF")),
    FieldDefinition("CEP_ALUNO", "CEP do aluno", "aluno", required=False, aliases=("CEP aluno", "CEP")),
    FieldDefinition("SEMESTRE", "Semestre", "academico", aliases=("Semestre atual",)),

    FieldDefinition("CAMPUS", "Campus", "academico", aliases=("Polo",)),
    FieldDefinition("PERIODO", "Período", "academico", aliases=("Turno",)),
    FieldDefinition("CURSO", "Curso", "academico", aliases=("Graduação",), origin="operador"),
    FieldDefinition("MODULO_ESTAGIO", "Módulo do estágio", "academico", aliases=("Módulo estágio", "Disciplina de estágio"), origin="calculado"),
    FieldDefinition("DEPENDENCIA", "Dependência", "academico", required=False),
    FieldDefinition("HISTORICO_MODULOS", "Histórico dos módulos", "academico", required=False, aliases=("Histórico de módulos",)),
    FieldDefinition("EMPRESA", "Razão social", "empresa", aliases=("Empresa", "Nome da empresa", "Razão social da empresa"), origin="consulta"),
    FieldDefinition("EMPRESA_FANTASIA", "Nome fantasia", "empresa", aliases=("Nome fantasia da empresa", "Local", "Local de estágio"), origin="consulta"),
    FieldDefinition("CNPJ", "CNPJ", "empresa"),
    FieldDefinition("RAMO_EMPRESA", "Ramo da empresa", "empresa", aliases=("Ramo empresa", "Ramo de atividade"), origin="consulta"),
    FieldDefinition("ENDERECO_EMPRESA", "Endereço da empresa", "empresa", aliases=("Endereço empresa",), origin="consulta"),
    FieldDefinition("BAIRRO_EMPRESA", "Bairro da empresa", "empresa", aliases=("Bairro empresa",), origin="consulta"),
    FieldDefinition("CIDADE_EMPRESA", "Cidade da empresa", "empresa", aliases=("Cidade empresa",), origin="consulta"),
    FieldDefinition("ESTADO_EMPRESA", "Estado da empresa", "empresa", aliases=("Estado empresa", "UF empresa"), origin="consulta"),
    FieldDefinition("TELEFONE_EMPRESA", "Telefone da empresa", "empresa", aliases=("Telefone empresa", "Contato da empresa", "Telefone RT", "Telefone do RT", "Celular RT")),
    FieldDefinition("NOME_RT", "Nome do responsável técnico", "responsavel", aliases=("Nome RT", "Nome da RT", "Responsável técnico", "Nome do responsável", "Nome do RT")),
    FieldDefinition("EMAIL_RT", "E-mail do responsável técnico", "responsavel", aliases=("E-mail RT", "Email RT", "E-mail do RT", "Email do responsável técnico", "E-mail responsável técnico", "Email responsável técnico")),
    FieldDefinition("CONSELHO_RT", "Conselho do responsável técnico", "responsavel", aliases=("Conselho RT", "Sigla do conselho de classe", "Conselho de classe", "Registro profissional", "CRF", "CRBM", "Coren")),
    FieldDefinition("CARGO_REPRESENTANTE", "Cargo do representante", "responsavel", aliases=("Cargo representante", "Cargo do RT"), origin="calculado"),
    FieldDefinition("AREA_ESTAGIO", "Área do estágio", "estagio", aliases=("Área estágio", "Área", "Campo de estágio"), origin="operador"),
    FieldDefinition("DATA_INICIO_ESTAGIO", "Data de início do estágio", "estagio", aliases=("Data início estágio", "Início do estágio"), origin="calculado"),
    FieldDefinition("DATA_FIM_ESTAGIO", "Data de término do estágio", "estagio", aliases=("Data fim estágio", "Fim do estágio", "Término do estágio"), origin="calculado"),
    FieldDefinition("CARGA_HORARIA", "Carga horária total", "estagio", aliases=("Carga horária", "Carga total"), origin="calculado"),
    FieldDefinition("CARGA_SEMANAL", "Carga horária semanal", "estagio", aliases=("Carga semanal", "Horas semanais"), origin="calculado"),
    FieldDefinition("DIAS_ESTAGIO", "Dias de estágio", "estagio", aliases=("Dias da semana", "Dias estágio"), origin="calculado"),
    FieldDefinition("HORARIO_ESTAGIO", "Horário do estágio", "estagio", aliases=("Horário de estágio", "Horário estágio"), origin="calculado"),
    FieldDefinition("QTD_DIAS", "Quantidade de dias", "estagio", required=False, aliases=("Total de dias",), origin="calculado"),
    FieldDefinition("OBSERVACOES_PLANO", "Observações do plano", "estagio", required=False, aliases=("Observações",), origin="operador"),
    FieldDefinition("APOLICE", "Número da apólice", "seguro", aliases=("Apólice", "Número apólice", "Nº apólice seguro de vida", "N° apólice seguro de vida")),
    FieldDefinition("SEGURADORA", "Seguradora", "seguro", aliases=("Nome da seguradora", "Empresa seguradora")),
    FieldDefinition("DATA_INICIO_VIGENCIA", "Data de início da vigência", "seguro", aliases=("Data início vigência", "Início da vigência")),
    FieldDefinition("DATA_FIM_VIGENCIA", "Data de término da vigência", "seguro", aliases=("Data fim vigência", "Fim da vigência", "Término da vigência")),
)


FIELD_BY_KEY = {field.key: field for field in FIELD_DEFINITIONS}
REQUIRED_FIELDS = {field.key: field.label for field in FIELD_DEFINITIONS if field.required}
OPTIONAL_FIELDS = tuple(field.key for field in FIELD_DEFINITIONS if not field.required)


def normalize_label(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_accents.strip().split())


LABEL_TO_KEY: dict[str, str] = {}
for definition in FIELD_DEFINITIONS:
    for label in (definition.label, *definition.aliases):
        normalized = normalize_label(label)
        existing = LABEL_TO_KEY.get(normalized)
        if existing and existing != definition.key:
            raise RuntimeError(f"Rótulo duplicado no catálogo: {label}")
        LABEL_TO_KEY[normalized] = definition.key


def fields_for_group(group: str) -> tuple[FieldDefinition, ...]:
    return tuple(field for field in FIELD_DEFINITIONS if field.group == group)
