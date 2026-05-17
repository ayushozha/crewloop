from typing import Any

from fastapi import APIRouter, HTTPException

from .. import db


router = APIRouter(prefix="/api/contractors", tags=["contractors"])


@router.get("")
async def list_contractors(
    skill: str | None = None,
    min_reliability: int = 0,
    limit: int = 100,
) -> dict:
    sql = """
        SELECT
          c.id, c.name, c.phone, c.email, c.age, c.location, c.distance_miles,
          c.hourly_rate, c.reliability_score, c.response_speed, c.languages,
          c.certifications, c.notes, c.avatar_path, c.created_at,
          COALESCE(
            (SELECT array_agg(skill ORDER BY skill)
             FROM contractor_skills WHERE contractor_id = c.id),
            '{}'::text[]
          ) AS skills
        FROM contractors c
        WHERE c.reliability_score >= $1
          AND ($2::text IS NULL OR EXISTS (
            SELECT 1 FROM contractor_skills cs
            WHERE cs.contractor_id = c.id AND cs.skill = $2
          ))
        ORDER BY c.reliability_score DESC, c.name
        LIMIT $3
    """
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(sql, min_reliability, skill, limit)
    return {"items": [_row_to_dict(r) for r in rows]}


@router.get("/{contractor_id}")
async def get_contractor(contractor_id: str) -> dict[str, Any]:
    sql = """
        SELECT
          c.*,
          COALESCE(
            (SELECT array_agg(skill ORDER BY skill)
             FROM contractor_skills WHERE contractor_id = c.id),
            '{}'::text[]
          ) AS skills
        FROM contractors c
        WHERE c.id = $1
    """
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(sql, contractor_id)
    if not row:
        raise HTTPException(status_code=404, detail="contractor not found")
    return _row_to_dict(row)


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    # asyncpg returns numeric/Decimal types; flatten to floats for JSON.
    for key in ("distance_miles", "hourly_rate"):
        if d.get(key) is not None:
            d[key] = float(d[key])
    return d
