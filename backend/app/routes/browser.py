import logging
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import repo
from ..browser_import import import_shift_from_browser


logger = logging.getLogger("crewloop.browser")
router = APIRouter(tags=["browser-import"])


class BrowserImportRequest(BaseModel):
    source_url: str | None = Field(
        default=None,
        description="Staffing/event page URL. Defaults to the local Bay Events demo page.",
    )
    force_local: bool = Field(
        default=False,
        description="Skip Browser Use Cloud and use the local extractor. Useful for localhost demo pages.",
    )


def _absolute_source_url(request: Request, source_url: str | None) -> str:
    base = str(request.base_url).rstrip("/")
    if not source_url:
        return f"{base}/bay-events/staffing"
    if source_url.startswith("/"):
        return f"{base}{source_url}"
    return source_url


async def _create_import(source_url: str, force_local: bool) -> dict[str, Any]:
    try:
        result = await import_shift_from_browser(source_url, force_local=force_local)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"source page returned {exc.response.status_code}",
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"source page could not be loaded: {exc}")
    except Exception:
        logger.exception("browser import failed")
        raise HTTPException(status_code=500, detail="browser import failed")

    job = await repo.create_job_from_import(result.imported_fields)
    browser_source = await repo.create_browser_source(
        job_id=job["id"],
        source_url=result.source_url,
        source_type=result.source_type,
        imported_fields=result.imported_fields,
        screenshot_url=result.screenshot_url,
        source_html_url=result.source_html_url,
        extraction_confidence=result.extraction_confidence,
        update_status=result.update_status,
        browser_action_log=result.browser_action_log,
    )
    return {
        "job": job,
        "browser_source": browser_source,
        "used_browser_use": result.used_browser_use,
    }


@router.post("/browser/import")
@router.post("/api/browser/import")
async def browser_import(payload: BrowserImportRequest, request: Request) -> dict[str, Any]:
    source_url = _absolute_source_url(request, payload.source_url)
    return await _create_import(source_url, payload.force_local)


@router.get("/api/browser-sources")
async def list_browser_sources(limit: int = 50) -> dict[str, Any]:
    return {"items": await repo.list_browser_sources(limit=limit)}


@router.get("/api/browser-sources/{source_id}")
async def get_browser_source(source_id: UUID) -> dict[str, Any]:
    source = await repo.get_browser_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="browser source not found")
    return {"browser_source": source}


@router.get("/jobs/{job_id}")
@router.get("/api/jobs/{job_id}")
async def get_job(job_id: UUID) -> dict[str, Any]:
    job = await repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    sources = await repo.list_browser_sources_for_job(job_id)
    return {"job": job, "browser_sources": sources}
