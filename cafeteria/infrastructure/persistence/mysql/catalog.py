from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
import logging

import pymysql
from django.conf import settings


logger = logging.getLogger(__name__)


class MySQLCatalogError(RuntimeError):
    pass


@contextmanager
def mysql_connection(*, autocommit: bool = True):
    connection = None
    try:
        connection = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=autocommit,
            connect_timeout=settings.MYSQL_CONNECT_TIMEOUT,
            read_timeout=settings.MYSQL_READ_TIMEOUT,
            write_timeout=settings.MYSQL_WRITE_TIMEOUT,
        )
        yield connection
        if not autocommit:
            connection.commit()
    except Exception as exc:
        if connection is not None and not autocommit:
            connection.rollback()
        if isinstance(exc, pymysql.MySQLError):
            raise MySQLCatalogError("No se pudo consultar la base de datos MySQL") from exc
        raise
    finally:
        if connection is not None:
            connection.close()


@contextmanager
def mysql_cursor(*, autocommit: bool = True):
    with mysql_connection(autocommit=autocommit) as connection:
        with connection.cursor() as cursor:
            yield connection, cursor


def touch_pos_account_access(email: str) -> None:
    query = "UPDATE cuenta_pos SET ultimo_acceso = NOW() WHERE correo = %s"
    with mysql_cursor() as (_, cursor):
        cursor.execute(query, (email,))


def get_pos_account_by_email(email: str) -> dict | None:
    query = """
        SELECT correo, password_hash, nombre_modulo, activa
        FROM cuenta_pos
        WHERE correo = %s
        LIMIT 1
    """
    with mysql_cursor() as (_, cursor):
        cursor.execute(query, (email,))
        return cursor.fetchone()


def list_products(search_query: str = "", selected_category: str | None = None) -> list[dict]:
    query, parameters = _build_products_query(search_query, selected_category)

    with mysql_cursor() as (_, cursor):
        cursor.execute(query, parameters)
        return [_normalize_product(row) for row in cursor.fetchall()]


def get_index_catalog_data(search_query: str = "", selected_category: str | None = None) -> tuple[list[dict], list[dict]]:
    products_query, product_parameters = _build_products_query(search_query, selected_category)

    with mysql_cursor() as (_, cursor):
        cursor.execute(products_query, product_parameters)
        products = [_normalize_product(row) for row in cursor.fetchall()]

        cursor.execute(
            """
                SELECT id, nombre, descuento_pct, condiciones
                FROM promocion
                WHERE activa = 1
                ORDER BY id
            """
        )
        promotions = [_normalize_promotion(row) for row in cursor.fetchall()]

    logger.info(
        "Index catalog loaded with %s products and %s promotions",
        len(products),
        len(promotions),
    )
    return products, promotions


def get_product_by_id(product_id: int | str) -> dict | None:
    query = """
        SELECT id, nombre, precio, categoria
        FROM producto
        WHERE id = %s
        LIMIT 1
    """
    with mysql_cursor() as (_, cursor):
        cursor.execute(query, (product_id,))
        row = cursor.fetchone()
        return _normalize_product(row) if row else None


def list_promotions() -> list[dict]:
    query = """
        SELECT id, nombre, descuento_pct, condiciones
        FROM promocion
        WHERE activa = 1
        ORDER BY id
    """
    with mysql_cursor() as (_, cursor):
        cursor.execute(query)
        return [_normalize_promotion(row) for row in cursor.fetchall()]


def get_promotion_by_id(promotion_id: int | str) -> dict | None:
    query = """
        SELECT id, nombre, descuento_pct, condiciones
        FROM promocion
        WHERE id = %s AND activa = 1
        LIMIT 1
    """
    with mysql_cursor() as (_, cursor):
        cursor.execute(query, (promotion_id,))
        row = cursor.fetchone()
        return _normalize_promotion(row) if row else None


def get_frequent_client(dni: str) -> dict | None:
    query = """
        SELECT dni, saldo_cafes
        FROM cliente_frecuente
        WHERE dni = %s
        LIMIT 1
    """
    with mysql_cursor() as (_, cursor):
        cursor.execute(query, (dni,))
        return cursor.fetchone()


def decrement_frequent_client_balance(dni: str) -> int | None:
    select_query = """
        SELECT saldo_cafes
        FROM cliente_frecuente
        WHERE dni = %s
        LIMIT 1
        FOR UPDATE
    """
    update_query = "UPDATE cliente_frecuente SET saldo_cafes = %s WHERE dni = %s"

    with mysql_cursor(autocommit=False) as (_, cursor):
        cursor.execute(select_query, (dni,))
        row = cursor.fetchone()
        if row is None:
            return None

        current_balance = int(row["saldo_cafes"])
        if current_balance <= 0:
            return 0

        new_balance = current_balance - 1
        cursor.execute(update_query, (new_balance, dni))
        return new_balance


def order_exists(order_id: int) -> bool:
    query = "SELECT 1 FROM orden WHERE id = %s LIMIT 1"
    with mysql_cursor() as (_, cursor):
        cursor.execute(query, (order_id,))
        return cursor.fetchone() is not None


def get_order_items_for_repeat(order_id: int) -> list[dict]:
    query = """
        SELECT producto_id, nombre_producto, precio_unitario, categoria_producto, cantidad
        FROM item_orden
        WHERE orden_id = %s
        ORDER BY id
    """
    with mysql_cursor() as (_, cursor):
        cursor.execute(query, (order_id,))
        return [
            {
                "id": str(row["producto_id"]),
                "name": row["nombre_producto"],
                "price": float(row["precio_unitario"]),
                "category": row["categoria_producto"],
                "quantity": int(row["cantidad"]),
            }
            for row in cursor.fetchall()
        ]


def create_order(
    cart: list[dict],
    discount_percentage: Decimal,
    totals: dict[str, Decimal],
    *,
    dni_cliente: str | None = None,
    orden_anterior_id: int | None = None,
    discount_entries: list[dict] | None = None,
) -> int:
    order_query = """
        INSERT INTO orden (subtotal, pct_descuento, monto_descuento, total, dni_cliente, orden_anterior_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    item_query = """
        INSERT INTO item_orden (
            orden_id,
            producto_id,
            nombre_producto,
            categoria_producto,
            precio_unitario,
            cantidad,
            total_linea
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    discount_query = """
        INSERT INTO historial_descuento (
            orden_id,
            tipo_descuento,
            pct_aplicado,
            monto_aplicado,
            dni_cliente,
            promocion_id
        )
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    with mysql_cursor(autocommit=False) as (connection, cursor):
        cursor.execute(
            order_query,
            (
                totals["subtotal"],
                discount_percentage,
                totals["discount_amount"],
                totals["total"],
                dni_cliente,
                orden_anterior_id,
            ),
        )
        order_id = int(connection.insert_id())

        cursor.executemany(
            item_query,
            [
                (
                    order_id,
                    int(item["id"]),
                    item["name"],
                    item["category"],
                    Decimal(str(item["price"])),
                    int(item["quantity"]),
                    _quantize_amount(Decimal(str(item["price"])) * int(item["quantity"])),
                )
                for item in cart
            ],
        )

        normalized_entries = _normalize_discount_entries(discount_entries or [], totals)
        if normalized_entries:
            cursor.executemany(
                discount_query,
                [
                    (
                        order_id,
                        entry["tipo_descuento"],
                        entry["pct_aplicado"],
                        entry["monto_aplicado"],
                        entry.get("dni_cliente"),
                        entry.get("promocion_id"),
                    )
                    for entry in normalized_entries
                ],
            )

        return order_id


def _normalize_product(row: dict | None) -> dict | None:
    if row is None:
        return None

    price = row["precio"]
    if not isinstance(price, Decimal):
        price = Decimal(str(price))

    return {
        "id": int(row["id"]),
        "name": row["nombre"],
        "price": price,
        "category": row["categoria"],
    }


def _normalize_promotion(row: dict | None) -> dict | None:
    if row is None:
        return None

    return {
        "id": int(row["id"]),
        "name": row["nombre"],
        "discount": int(row["descuento_pct"]),
        "conditions": row["condiciones"],
    }


def _build_products_query(search_query: str = "", selected_category: str | None = None) -> tuple[str, list[str]]:
    conditions: list[str] = []
    parameters: list[str] = []

    if search_query:
        like_value = f"%{search_query}%"
        conditions.append("(nombre LIKE %s OR categoria LIKE %s)")
        parameters.extend([like_value, like_value])

    if selected_category:
        conditions.append("categoria = %s")
        parameters.append(selected_category)

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = (
        "SELECT id, nombre, precio, categoria "
        "FROM producto"
        f"{where_clause} "
        "ORDER BY id"
    )
    return query, parameters


def _normalize_discount_entries(discount_entries: list[dict], totals: dict[str, Decimal]) -> list[dict]:
    subtotal = totals["subtotal"]
    total_discount_amount = totals["discount_amount"]
    if subtotal <= 0 or total_discount_amount <= 0:
        return []

    normalized_entries: list[dict] = []
    distributed_amount = Decimal("0.00")
    active_entries = [entry for entry in discount_entries if Decimal(str(entry["pct"])) > 0]

    for index, entry in enumerate(active_entries):
        pct_aplicado = Decimal(str(entry["pct"]))
        if index == len(active_entries) - 1:
            monto_aplicado = total_discount_amount - distributed_amount
        else:
            monto_aplicado = _quantize_amount(subtotal * (pct_aplicado / Decimal("100")))
            distributed_amount += monto_aplicado

        normalized_entries.append(
            {
                "tipo_descuento": entry["type"],
                "pct_aplicado": pct_aplicado,
                "monto_aplicado": max(monto_aplicado, Decimal("0.00")),
                "dni_cliente": entry.get("dni_cliente"),
                "promocion_id": entry.get("promotion_id"),
            }
        )

    return normalized_entries


def _quantize_amount(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
