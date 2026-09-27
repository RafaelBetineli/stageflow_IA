"""Controle de pedidos (serviços) do StageFlow.

Guarda, na mesma base SQLite local já usada para empresas e histórico de
atividades, os serviços em andamento: aluno, curso, serviço contratado,
datas de início/entrega prevista, status de produção e situação de
pagamento. O objetivo é responder rápido a duas perguntas: "o que está
atrasado ou perto do prazo?" e "esse aluno já pagou?".
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import sqlite3

from .repository import DEFAULT_DATABASE

STATUSES: tuple[str, ...] = (
    "aguardando_pagamento",
    "em_producao",
    "em_revisao",
    "concluido",
)

STATUS_LABELS: dict[str, str] = {
    "aguardando_pagamento": "Aguardando pagamento",
    "em_producao": "Em produção",
    "em_revisao": "Em revisão",
    "concluido": "Concluído",
}


@dataclass(slots=True)
class Order:
    id: int | None
    aluno: str
    curso: str
    servico: str
    data_inicio: date
    data_entrega_prevista: date
    status: str = "aguardando_pagamento"
    pago: bool = False
    valor: float | None = None
    observacoes: str = ""
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def atrasado(self) -> bool:
        return self.status != "concluido" and self.data_entrega_prevista < date.today()

    @property
    def dias_restantes(self) -> int:
        return (self.data_entrega_prevista - date.today()).days

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)


class OrdersRepository:
    """Persistência SQLite dos pedidos. Usa o mesmo arquivo de banco do
    StageFlow (``data/stageflow.db``) para não precisar de outra base."""

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
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aluno TEXT NOT NULL,
                    curso TEXT NOT NULL,
                    servico TEXT NOT NULL,
                    data_inicio TEXT NOT NULL,
                    data_entrega_prevista TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'aguardando_pagamento',
                    pago INTEGER NOT NULL DEFAULT 0,
                    valor REAL,
                    observacoes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_orders_status
                    ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_orders_entrega
                    ON orders(data_entrega_prevista);
                """
            )
            connection.commit()

    def create(self, order: Order) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO orders (
                    aluno, curso, servico, data_inicio, data_entrega_prevista,
                    status, pago, valor, observacoes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.aluno.strip(),
                    order.curso.strip(),
                    order.servico.strip(),
                    order.data_inicio.isoformat(),
                    order.data_entrega_prevista.isoformat(),
                    order.status,
                    int(order.pago),
                    order.valor,
                    order.observacoes.strip(),
                    now,
                    now,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def update(self, order_id: int, **fields: object) -> None:
        allowed = {
            "aluno", "curso", "servico", "data_inicio",
            "data_entrega_prevista", "status", "pago", "valor", "observacoes",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        for date_key in ("data_inicio", "data_entrega_prevista"):
            if isinstance(updates.get(date_key), date):
                updates[date_key] = updates[date_key].isoformat()
        if "pago" in updates:
            updates["pago"] = int(bool(updates["pago"]))
        updates["updated_at"] = datetime.now().isoformat(timespec="seconds")
        columns = ", ".join(f"{key} = ?" for key in updates)
        with closing(self._connect()) as connection:
            connection.execute(
                f"UPDATE orders SET {columns} WHERE id = ?",
                (*updates.values(), order_id),
            )
            connection.commit()

    def set_status(self, order_id: int, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"Status inválido: {status}")
        self.update(order_id, status=status)

    def set_paid(self, order_id: int, pago: bool) -> None:
        self.update(order_id, pago=pago)

    def delete(self, order_id: int) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            connection.commit()

    def get(self, order_id: int) -> Order | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
        return _row_to_order(row) if row else None

    def list(
        self,
        *,
        status: str | None = None,
        aluno: str | None = None,
        somente_atrasados: bool = False,
        order_by: str = "data_entrega_prevista",
    ) -> tuple[Order, ...]:
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if aluno:
            clauses.append("lower(aluno) LIKE ?")
            params.append(f"%{aluno.strip().lower()}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM orders {where} ORDER BY {order_by} ASC",
                params,
            ).fetchall()
        orders = tuple(_row_to_order(row) for row in rows)
        if somente_atrasados:
            orders = tuple(item for item in orders if item.atrasado)
        return orders


def _row_to_order(row: sqlite3.Row) -> Order:
    return Order(
        id=row["id"],
        aluno=row["aluno"],
        curso=row["curso"],
        servico=row["servico"],
        data_inicio=date.fromisoformat(row["data_inicio"]),
        data_entrega_prevista=date.fromisoformat(row["data_entrega_prevista"]),
        status=row["status"],
        pago=bool(row["pago"]),
        valor=row["valor"],
        observacoes=row["observacoes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
