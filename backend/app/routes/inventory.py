from typing import Any

from fastapi import APIRouter, HTTPException

from .. import db


router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    for k in ("par_level", "on_hand", "reorder_point", "unit_cost"):
        if d.get(k) is not None:
            d[k] = float(d[k])
    return d


@router.get("")
async def list_items(
    category: str | None = None,
    needs_reorder: bool = False,
    limit: int = 250,
) -> dict[str, Any]:
    sql = """
        SELECT id, sku, name, category, unit, par_level, on_hand, reorder_point,
               unit_cost, supplier, location, description, image_path, created_at
        FROM inventory_items
        WHERE ($1::text IS NULL OR category = $1)
          AND (NOT $2 OR on_hand <= reorder_point)
        ORDER BY category, name
        LIMIT $3
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, category, needs_reorder, limit)
    items = [_row_to_dict(r) for r in rows]
    cats = sorted({i["category"] for i in items})
    return {"items": items, "categories": cats, "count": len(items)}


@router.get("/summary")
async def summary() -> dict[str, Any]:
    sql_cats = """
        SELECT category, count(*) AS items,
               SUM(on_hand * unit_cost) AS value_on_hand,
               SUM(GREATEST(par_level - on_hand, 0) * unit_cost) AS replenish_cost,
               SUM(CASE WHEN on_hand <= reorder_point THEN 1 ELSE 0 END) AS low_stock
        FROM inventory_items
        GROUP BY category
        ORDER BY category
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql_cats)
        total = await conn.fetchval("SELECT count(*) FROM inventory_items")
        total_value = await conn.fetchval("SELECT COALESCE(SUM(on_hand * unit_cost), 0) FROM inventory_items")
        low_total = await conn.fetchval("SELECT count(*) FROM inventory_items WHERE on_hand <= reorder_point")
    return {
        "total_items": total,
        "total_value_on_hand": float(total_value or 0),
        "low_stock_count": low_total,
        "by_category": [
            {
                "category": r["category"],
                "items": r["items"],
                "value_on_hand": float(r["value_on_hand"] or 0),
                "replenish_cost": float(r["replenish_cost"] or 0),
                "low_stock": r["low_stock"],
            }
            for r in rows
        ],
    }


@router.get("/{item_id}")
async def get_item(item_id: str) -> dict[str, Any]:
    sql = "SELECT * FROM inventory_items WHERE id = $1"
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="inventory item not found")
    return _row_to_dict(row)
