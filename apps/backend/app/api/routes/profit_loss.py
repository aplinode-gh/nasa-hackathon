"""Profit / Loss calculator API routes."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.core.deps import require_session
from app.core.http import error_response, read_json_body, success
from app.core.serialization import to_jsonable
from app.db.session import execute, query, query_one
from app.models.profit_loss import (
    CreateExpenseRequest,
    CreateProjectedCostRequest,
    CreateSeasonRequest,
    UpdateExpenseRequest,
    UpdateSeasonRequest,
)
from app.services.profit_loss import (
    compute_break_even,
    compute_pl,
    default_projected_costs,
    get_crop_unit,
    get_season_start_date,
)

router = APIRouter(prefix="/profit-loss", tags=["profit-loss"])

IMMUTABLE_AFTER_EXPENSES = ("crop_id", "acres", "season", "year")


def _crop_name(crop_id: str) -> str:
    return (crop_id or "").replace("_", " ").title()


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


async def _owned_season(season_id: str, account_id: str):
    return await query_one(
        "SELECT * FROM seasons WHERE id = $1 AND account_id = $2",
        season_id,
        account_id,
    )


def _season_summary(row: dict[str, Any]) -> dict[str, Any]:
    total_actual = _as_float(row.get("total_actual_cost"))
    total_projected = _as_float(row.get("total_projected_cost"))
    actual_revenue = _as_float(row.get("actual_price"))
    actual_yield = row.get("actual_yield")
    pl = compute_pl(total_projected, total_actual, 0.0, actual_revenue)
    if actual_yield is not None and row.get("actual_price") is not None:
        pl = compute_pl(total_projected, total_actual, 0.0, actual_revenue)
    return {
        "id": str(row.get("id")),
        "crop_id": row.get("crop_id"),
        "crop_name": _crop_name(str(row.get("crop_id") or "")),
        "farm_name": row.get("farm_name"),
        "season": row.get("season"),
        "year": row.get("year"),
        "acres": _as_float(row.get("acres")),
        "status": row.get("status"),
        "pl": pl,
    }


@router.get("")
async def list_seasons(session: dict = Depends(require_session)):
    try:
        rows = await query(
            """
            SELECT s.*, f.name AS farm_name,
                   COALESCE((SELECT SUM(e.amount) FROM expenses e WHERE e.season_id = s.id), 0) AS total_actual_cost,
                   COALESCE((SELECT SUM(p.total_projected_pkr) FROM projected_costs p WHERE p.season_id = s.id), 0) AS total_projected_cost
            FROM seasons s
            JOIN farms f ON f.id = s.farm_id
            WHERE s.account_id = $1 AND s.archived_at IS NULL
            ORDER BY s.created_at DESC
            LIMIT 100
            """,
            session["accountId"],
        )
        return success({"seasons": [_season_summary(row) for row in (rows or [])], "next_cursor": None})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("")
async def create_season(request: Request, session: dict = Depends(require_session)):
    try:
        body = await read_json_body(request)
        parsed = CreateSeasonRequest.model_validate(body or {})

        farm = await query_one(
            "SELECT id FROM farms WHERE id = $1 AND account_id = $2 AND archived_at IS NULL",
            parsed.farm_id,
            session["accountId"],
        )
        if not farm:
            return error_response("not_found", "Farm not found", 404)

        season = await query_one(
            """
            INSERT INTO seasons (account_id, farm_id, crop_id, season, year, start_date, acres)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            session["accountId"],
            parsed.farm_id,
            parsed.crop_id,
            parsed.season,
            parsed.year,
            get_season_start_date(parsed.season),
            parsed.acres,
        )
        if not season:
            return error_response("server_error", "Failed to create season", 500)

        for projected in default_projected_costs(parsed.acres):
            await execute(
                """
                INSERT INTO projected_costs (season_id, category, per_acre_cost_pkr, total_projected_pkr)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (season_id, category) DO NOTHING
                """,
                season["id"],
                projected["category"],
                projected["per_acre_cost_pkr"],
                projected["total_projected_pkr"],
            )

        return success({**to_jsonable(season), "cacp_fallback": True}, status_code=201)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Valid crop" in msg or "Invalid" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.get("/{season_id}")
async def get_season(season_id: str, session: dict = Depends(require_session)):
    try:
        season = await _owned_season(season_id, session["accountId"])
        if not season:
            return error_response("not_found", "Season not found", 404)

        farm = await query_one("SELECT * FROM farms WHERE id = $1", season.get("farm_id"))
        expenses = await query(
            "SELECT * FROM expenses WHERE season_id = $1 ORDER BY date DESC, created_at DESC",
            season_id,
        )
        projected = await query(
            "SELECT * FROM projected_costs WHERE season_id = $1 ORDER BY category",
            season_id,
        )

        total_projected = sum(_as_float(item.get("total_projected_pkr")) for item in (projected or []))
        total_actual = sum(_as_float(item.get("amount")) for item in (expenses or []))
        expected_yield = season.get("expected_yield")
        expected_price = season.get("expected_price")
        projected_revenue = (
            _as_float(expected_yield) * _as_float(expected_price)
            if expected_yield is not None and expected_price is not None
            else 0.0
        )
        actual_revenue = _as_float(season.get("actual_price"))

        enriched_expenses = []
        for item in expenses or []:
            category = item.get("category")
            projected_row = next((p for p in (projected or []) if p.get("category") == category), None)
            projected_total = _as_float((projected_row or {}).get("total_projected_pkr"))
            amount = _as_float(item.get("amount"))
            variance = amount - projected_total
            enriched_expenses.append(
                {
                    **item,
                    "variance": round(variance, 2),
                    "variance_percentage": round((variance / projected_total) * 1000) / 10
                    if projected_total > 0
                    else None,
                }
            )

        pl = compute_pl(total_projected, total_actual, projected_revenue, actual_revenue)
        break_even = compute_break_even(
            total_projected,
            _as_float(expected_price) if expected_price is not None else None,
            _as_float(expected_yield) if expected_yield is not None else None,
            _as_float(season.get("acres")),
        )

        payload = {
            "id": str(season.get("id")),
            "farm_id": str(season.get("farm_id")),
            "crop_id": season.get("crop_id"),
            "crop_name": _crop_name(str(season.get("crop_id") or "")),
            "season": season.get("season"),
            "year": season.get("year"),
            "start_date": season.get("start_date"),
            "acres": _as_float(season.get("acres")),
            "status": season.get("status"),
            "expected_yield": expected_yield,
            "expected_price": expected_price,
            "actual_yield": season.get("actual_yield"),
            "actual_price": season.get("actual_price"),
            "archived_at": season.get("archived_at"),
            "farm_name": (farm or {}).get("name"),
            "expenses": enriched_expenses,
            "projected_costs": projected or [],
            "pl": pl,
            "break_even": break_even,
            "crop_unit": get_crop_unit(str(season.get("crop_id") or "")),
            "actual_revenue": round(actual_revenue, 2),
        }
        return success(payload)
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.patch("/{season_id}")
async def update_season(season_id: str, request: Request, session: dict = Depends(require_session)):
    try:
        season = await _owned_season(season_id, session["accountId"])
        if not season:
            return error_response("not_found", "Season not found", 404)

        body = await read_json_body(request)
        parsed = UpdateSeasonRequest.model_validate(body or {})
        payload = parsed.model_dump(exclude_unset=True)
        if not payload:
            return success(to_jsonable(season))

        count_row = await query_one(
            "SELECT count(*)::text AS count FROM expenses WHERE season_id = $1",
            season_id,
        )
        has_expenses = int((count_row or {}).get("count") or 0) > 0
        if has_expenses and any(field in payload for field in IMMUTABLE_AFTER_EXPENSES):
            return error_response(
                "conflict",
                "Cannot update field after expenses have been logged",
                409,
            )

        set_clauses = []
        values: list[Any] = []
        idx = 1
        for key, value in payload.items():
            set_clauses.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1
        set_clauses.append("updated_at = now()")
        values.extend([season_id, session["accountId"]])

        row = await query_one(
            f"UPDATE seasons SET {', '.join(set_clauses)} "
            f"WHERE id = ${idx} AND account_id = ${idx + 1} RETURNING *",
            *values,
        )
        if not row:
            return error_response("server_error", "Failed to update season", 500)
        return success(to_jsonable(row))
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Invalid" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.delete("/{season_id}")
async def delete_season(season_id: str, session: dict = Depends(require_session)):
    try:
        season = await _owned_season(season_id, session["accountId"])
        if not season:
            return error_response("not_found", "Season not found", 404)

        count_row = await query_one(
            "SELECT count(*)::text AS count FROM expenses WHERE season_id = $1",
            season_id,
        )
        has_yield = season.get("actual_yield") is not None and season.get("actual_price") is not None
        if int((count_row or {}).get("count") or 0) > 0 or has_yield:
            return error_response("conflict", "Delete all expenses and harvest data first.", 409)

        await execute("DELETE FROM projected_costs WHERE season_id = $1", season_id)
        await execute("DELETE FROM seasons WHERE id = $1 AND account_id = $2", season_id, session["accountId"])
        return success({"ok": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.get("/{season_id}/expenses")
async def list_expenses(season_id: str, request: Request, session: dict = Depends(require_session)):
    try:
        season = await _owned_season(season_id, session["accountId"])
        if not season or season.get("archived_at") is not None:
            return error_response("not_found", "Season not found", 404)

        qp = request.query_params
        try:
            limit = int(qp.get("limit", "20"))
        except Exception:
            return error_response("validation_error", "Invalid query", 422)
        if limit <= 0 or limit > 100:
            return error_response("validation_error", "Invalid query", 422)
        cursor = qp.get("cursor")

        conditions = ["e.season_id = $1"]
        values: list[Any] = [season_id]
        idx = 2
        if cursor:
            conditions.append(f"e.created_at < (SELECT created_at FROM expenses WHERE id = ${idx})")
            values.append(cursor)
            idx += 1

        rows = await query(
            f"""
            SELECT e.*, pc.per_acre_cost_pkr, pc.total_projected_pkr
            FROM expenses e
            LEFT JOIN projected_costs pc ON pc.season_id = e.season_id AND pc.category = e.category
            WHERE {' AND '.join(conditions)}
            ORDER BY e.date DESC, e.created_at DESC
            LIMIT ${idx}
            """,
            *values,
            limit + 1,
        )
        rows = rows or []
        has_more = len(rows) > limit
        data = rows[:limit] if has_more else rows
        next_cursor = str(data[-1].get("id")) if has_more and data else None

        enriched = []
        for item in data:
            projected_total = _as_float(item.get("total_projected_pkr"))
            amount = _as_float(item.get("amount"))
            variance = amount - projected_total
            enriched.append(
                {
                    **item,
                    "variance": round(variance, 2),
                    "variance_percentage": round((variance / projected_total) * 1000) / 10
                    if projected_total > 0
                    else None,
                }
            )
        return success({"expenses": enriched, "next_cursor": next_cursor})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/{season_id}/expenses")
async def create_expense(season_id: str, request: Request, session: dict = Depends(require_session)):
    try:
        season = await _owned_season(season_id, session["accountId"])
        if not season or season.get("archived_at") is not None:
            return error_response("not_found", "Season not found", 404)

        body = await read_json_body(request)
        parsed = CreateExpenseRequest.model_validate(body or {})
        row = await query_one(
            """
            INSERT INTO expenses (season_id, account_id, category, amount, date, note)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            season_id,
            session["accountId"],
            parsed.category,
            parsed.amount,
            date.fromisoformat(parsed.date),
            parsed.note,
        )
        if not row:
            return error_response("server_error", "Failed to create expense", 500)
        return success(to_jsonable(row), status_code=201)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Invalid" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.patch("/{season_id}/expenses/{expense_id}")
async def update_expense(
    season_id: str,
    expense_id: str,
    request: Request,
    session: dict = Depends(require_session),
):
    try:
        expense = await query_one(
            """
            SELECT e.* FROM expenses e
            JOIN seasons s ON s.id = e.season_id
            WHERE e.id = $1 AND s.account_id = $2
            """,
            expense_id,
            session["accountId"],
        )
        if not expense:
            return error_response("not_found", "Expense not found", 404)

        body = await read_json_body(request)
        parsed = UpdateExpenseRequest.model_validate(body or {})
        payload = parsed.model_dump(exclude_unset=True)
        if not payload:
            return success(to_jsonable(expense))

        set_clauses = []
        values: list[Any] = []
        idx = 1
        for key, value in payload.items():
            set_clauses.append(f"{key} = ${idx}")
            values.append(date.fromisoformat(value) if key == "date" else value)
            idx += 1
        values.append(expense_id)

        row = await query_one(
            f"UPDATE expenses SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *",
            *values,
        )
        if not row:
            return error_response("server_error", "Failed to update expense", 500)
        return success(to_jsonable(row))
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Invalid" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.delete("/{season_id}/expenses/{expense_id}")
async def delete_expense(season_id: str, expense_id: str, session: dict = Depends(require_session)):
    try:
        owned = await query_one(
            """
            SELECT e.id FROM expenses e
            JOIN seasons s ON s.id = e.season_id
            WHERE e.id = $1 AND s.account_id = $2
            """,
            expense_id,
            session["accountId"],
        )
        if not owned:
            return error_response("not_found", "Expense not found", 404)
        await execute("DELETE FROM expenses WHERE id = $1", expense_id)
        return success({"ok": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/{season_id}/projected-costs")
async def upsert_projected_cost(
    season_id: str,
    request: Request,
    session: dict = Depends(require_session),
):
    try:
        season = await _owned_season(season_id, session["accountId"])
        if not season or season.get("archived_at") is not None:
            return error_response("not_found", "Season not found", 404)

        body = await read_json_body(request)
        parsed = CreateProjectedCostRequest.model_validate(body or {})
        total = round(parsed.per_acre_cost_pkr * _as_float(season.get("acres"), 1.0), 2)

        existing = await query_one(
            "SELECT id FROM projected_costs WHERE season_id = $1 AND category = $2",
            season_id,
            parsed.category,
        )
        if existing:
            await execute(
                "UPDATE projected_costs SET per_acre_cost_pkr = $1, total_projected_pkr = $2 WHERE id = $3",
                parsed.per_acre_cost_pkr,
                total,
                existing["id"],
            )
            return success({"ok": True, "updated": True})

        row = await query_one(
            """
            INSERT INTO projected_costs (season_id, category, per_acre_cost_pkr, total_projected_pkr)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            season_id,
            parsed.category,
            parsed.per_acre_cost_pkr,
            total,
        )
        if not row:
            return error_response("server_error", "Failed to create projected cost", 500)
        return success(to_jsonable(row), status_code=201)
    except Exception as err:
        msg = str(err)
        if "validation error" in msg.lower() or "Invalid" in msg:
            return error_response("validation_error", msg, 422)
        return error_response("server_error", msg, 500)


@router.post("/{season_id}/archive")
async def archive_season(season_id: str, session: dict = Depends(require_session)):
    try:
        row = await query_one(
            """
            UPDATE seasons SET archived_at = now(), updated_at = now()
            WHERE id = $1 AND account_id = $2 AND archived_at IS NULL
            RETURNING id
            """,
            season_id,
            session["accountId"],
        )
        if not row:
            return error_response("not_found", "Season not found", 404)
        return success({"ok": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)


@router.post("/{season_id}/restore")
async def restore_season(season_id: str, session: dict = Depends(require_session)):
    try:
        row = await query_one(
            """
            UPDATE seasons SET archived_at = NULL, updated_at = now()
            WHERE id = $1 AND account_id = $2 AND archived_at IS NOT NULL
            RETURNING id
            """,
            season_id,
            session["accountId"],
        )
        if not row:
            return error_response("not_found", "Season not found", 404)
        return success({"ok": True})
    except Exception as err:
        return error_response("server_error", str(err), 500)
