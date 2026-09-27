"""Painel de controle de pedidos: consulta rápida de aluno, pagamento e prazo."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from stageflow.orders import STATUS_LABELS, STATUSES, Order, OrdersRepository

st.set_page_config(page_title="Pedidos · StageFlow", page_icon="🗂️", layout="wide")


@st.cache_resource
def _repository() -> OrdersRepository:
    return OrdersRepository()


def _status_badge(order: Order) -> str:
    if order.atrasado:
        return f"🔴 Atrasado ({abs(order.dias_restantes)}d)"
    if order.status == "concluido":
        return "✅ Concluído"
    if 0 <= order.dias_restantes <= 2:
        return f"🟡 {order.status_label} · vence em {order.dias_restantes}d"
    return f"🟢 {order.status_label}"


st.title("🗂️ Controle de pedidos")
st.caption("Aluno, curso, serviço, prazo e pagamento — tudo num lugar só.")

repository = _repository()

with st.expander("➕ Novo pedido", expanded=False):
    with st.form("novo_pedido", clear_on_submit=True):
        col1, col2 = st.columns(2)
        aluno = col1.text_input("Aluno *")
        curso = col2.text_input("Curso *")
        servico = st.text_input("Serviço solicitado *", placeholder="Relatório + plano + termo")
        col3, col4 = st.columns(2)
        data_inicio = col3.date_input("Data de início", value=date.today())
        data_entrega = col4.date_input(
            "Entrega prevista", value=date.today() + timedelta(days=7)
        )
        col5, col6 = st.columns(2)
        status = col5.selectbox(
            "Status", STATUSES, format_func=lambda item: STATUS_LABELS[item]
        )
        pago = col6.checkbox("Pagamento confirmado")
        valor = st.number_input("Valor (opcional)", min_value=0.0, step=10.0, format="%.2f")
        observacoes = st.text_area("Observações", height=68)
        enviado = st.form_submit_button("Salvar pedido", type="primary")
        if enviado:
            if not aluno.strip() or not curso.strip() or not servico.strip():
                st.error("Preencha aluno, curso e serviço.")
            elif data_entrega < data_inicio:
                st.error("A entrega prevista não pode ser antes do início.")
            else:
                repository.create(
                    Order(
                        id=None,
                        aluno=aluno,
                        curso=curso,
                        servico=servico,
                        data_inicio=data_inicio,
                        data_entrega_prevista=data_entrega,
                        status=status,
                        pago=pago,
                        valor=valor or None,
                        observacoes=observacoes,
                    )
                )
                st.success("Pedido salvo.")
                st.rerun()

st.divider()

filtro_col1, filtro_col2, filtro_col3 = st.columns([2, 1, 1])
busca_aluno = filtro_col1.text_input("🔍 Buscar aluno", placeholder="Nome do aluno")
filtro_status = filtro_col2.selectbox(
    "Status",
    ("todos",) + STATUSES,
    format_func=lambda item: "Todos" if item == "todos" else STATUS_LABELS[item],
)
somente_atrasados = filtro_col3.checkbox("Só atrasados")

pedidos = repository.list(
    status=None if filtro_status == "todos" else filtro_status,
    aluno=busca_aluno or None,
    somente_atrasados=somente_atrasados,
)

if not pedidos:
    st.info("Nenhum pedido encontrado com esse filtro.")
else:
    atrasados = sum(1 for item in pedidos if item.atrasado)
    aguardando_pagamento = sum(1 for item in pedidos if not item.pago)
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Pedidos exibidos", len(pedidos))
    metric_col2.metric("Atrasados", atrasados)
    metric_col3.metric("Aguardando pagamento", aguardando_pagamento)

    for order in pedidos:
        with st.container(border=True):
            head_col, status_col = st.columns([3, 2])
            head_col.markdown(f"**{order.aluno}** · {order.curso}")
            head_col.caption(order.servico)
            status_col.markdown(_status_badge(order))
            status_col.caption(
                f"Início {order.data_inicio:%d/%m} → Entrega {order.data_entrega_prevista:%d/%m}"
            )

            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
            novo_status = action_col1.selectbox(
                "Status",
                STATUSES,
                index=STATUSES.index(order.status),
                format_func=lambda item: STATUS_LABELS[item],
                key=f"status_{order.id}",
                label_visibility="collapsed",
            )
            if novo_status != order.status:
                repository.set_status(order.id, novo_status)
                st.rerun()

            pago_novo = action_col2.checkbox(
                "Pago", value=order.pago, key=f"pago_{order.id}"
            )
            if pago_novo != order.pago:
                repository.set_paid(order.id, pago_novo)
                st.rerun()

            if order.valor:
                action_col3.caption(f"R$ {order.valor:,.2f}")

            if action_col4.button("Excluir", key=f"del_{order.id}"):
                repository.delete(order.id)
                st.rerun()

            if order.observacoes:
                st.caption(f"📝 {order.observacoes}")
