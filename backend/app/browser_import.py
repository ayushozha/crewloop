import html
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from .config import settings


logger = logging.getLogger("crewloop.browser_import")

STATIC_DIR = Path(__file__).parent / "static"
EVIDENCE_DIR = STATIC_DIR / "evidence"


class ImportedShift(BaseModel):
    business_name: str = "Bay Events Co."
    role: str
    description: str | None = None
    location: str
    start_time: str
    end_time: str
    pay_amount: float
    urgency: str
    required_skills: list[str] = Field(default_factory=list)
    source_type: str = "staffing_portal"
    evidence_summary: str
    extraction_confidence: float = Field(ge=0, le=1)


class BrowserImportResult(BaseModel):
    source_url: str
    source_type: str
    imported_fields: dict[str, Any]
    screenshot_url: str | None
    source_html_url: str | None
    extraction_confidence: float
    update_status: str = "pending"
    browser_action_log: list[dict[str, Any]]
    used_browser_use: bool


def is_local_source(source_url: str) -> bool:
    host = (urlparse(source_url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local")


async def import_shift_from_browser(source_url: str, *, force_local: bool = False) -> BrowserImportResult:
    action_log: list[dict[str, Any]] = [
        {"step": "source_received", "status": "ok", "source_url": source_url}
    ]

    if settings.browser_use_api_key and not force_local and not is_local_source(source_url):
        try:
            result = await _import_with_browser_use(source_url, action_log)
            if result:
                return result
        except Exception as exc:
            logger.warning("Browser Use import failed; falling back to local extractor: %s", exc)
            action_log.append(
                {"step": "browser_use_cloud", "status": "failed", "message": str(exc)}
            )

    return await _import_with_local_browser(source_url, action_log)


async def _import_with_browser_use(
    source_url: str,
    action_log: list[dict[str, Any]],
) -> BrowserImportResult | None:
    task = (
        "Open this staffing or event source page and extract one urgent contractor shift. "
        "Return only JSON with these keys: business_name, role, description, location, "
        "start_time, end_time, pay_amount, urgency, required_skills, source_type, "
        f"evidence_summary, extraction_confidence. Source URL: {source_url}"
    )
    headers = {
        "X-Browser-Use-API-Key": settings.browser_use_api_key or "",
        "Content-Type": "application/json",
    }
    payload = {
        "task": task,
        "model": settings.browser_use_model,
        "keep_alive": False,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        create = await client.post(
            f"{settings.browser_use_base_url.rstrip('/')}/sessions",
            headers=headers,
            json=payload,
        )
        create.raise_for_status()
        session = create.json()
        session_id = session.get("id") or session.get("session_id")
        action_log.append(
            {
                "step": "browser_use_session_started",
                "status": "ok",
                "session_id": session_id,
                "live_url": session.get("liveUrl") or session.get("live_url"),
            }
        )
        if not session_id:
            raise RuntimeError("Browser Use response did not include a session id")

        final = session
        for _ in range(36):
            poll = await client.get(
                f"{settings.browser_use_base_url.rstrip('/')}/sessions/{session_id}",
                headers=headers,
            )
            poll.raise_for_status()
            final = poll.json()
            status = str(final.get("status") or "").lower()
            if status in {"idle", "stopped", "finished", "done", "error", "timed_out"}:
                break

        output = final.get("output") or final.get("result") or final.get("final_result")
        if isinstance(output, str):
            output = _parse_json_object(output)
        if not isinstance(output, dict):
            raise RuntimeError("Browser Use did not return structured shift JSON")

    shift = _normalize_imported_shift(output, default_source_type="staffing_portal")
    imported_fields = shift.model_dump(mode="json", exclude={"source_type"})
    action_log.append({"step": "shift_extracted", "status": "ok", "engine": "browser_use"})

    screenshot_url = (
        final.get("screenshotUrl")
        or final.get("screenshot_url")
        or final.get("lastScreenshotUrl")
        or final.get("last_screenshot_url")
    )

    return BrowserImportResult(
        source_url=source_url,
        source_type=shift.source_type,
        imported_fields=imported_fields,
        screenshot_url=screenshot_url,
        source_html_url=None,
        extraction_confidence=shift.extraction_confidence,
        browser_action_log=action_log,
        used_browser_use=True,
    )


async def _import_with_local_browser(
    source_url: str,
    action_log: list[dict[str, Any]],
) -> BrowserImportResult:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    evidence_id = uuid4().hex

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(source_url)
        response.raise_for_status()
        source_html = response.text

    source_html_name = f"browser-source-{evidence_id}.html"
    source_html_path = EVIDENCE_DIR / source_html_name
    source_html_path.write_text(source_html, encoding="utf-8")
    source_html_url = f"/static/evidence/{source_html_name}"
    action_log.append({"step": "source_html_captured", "status": "ok", "url": source_html_url})

    shift = _extract_shift_from_html(source_html, source_url)
    imported_fields = shift.model_dump(mode="json", exclude={"source_type"})
    action_log.append({"step": "shift_extracted", "status": "ok", "engine": "local"})

    screenshot_url = await _capture_screenshot(source_url, evidence_id, shift, action_log)

    return BrowserImportResult(
        source_url=source_url,
        source_type=shift.source_type,
        imported_fields=imported_fields,
        screenshot_url=screenshot_url,
        source_html_url=source_html_url,
        extraction_confidence=shift.extraction_confidence,
        browser_action_log=action_log,
        used_browser_use=False,
    )


def _extract_shift_from_html(source_html: str, source_url: str) -> ImportedShift:
    script_match = re.search(
        r"<script[^>]+id=[\"']crewloop-shift-data[\"'][^>]*>(.*?)</script>",
        source_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if script_match:
        raw = html.unescape(script_match.group(1).strip())
        parsed = json.loads(raw)
        return _normalize_imported_shift(parsed, default_source_type="staffing_portal")

    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", source_html)).strip()
    pay_match = re.search(r"\$([0-9]+(?:\.[0-9]{1,2})?)", plain)
    time_match = re.search(r"([0-9]{1,2}\s*(?::[0-9]{2})?\s*(?:AM|PM)?)\s*[-to]+\s*([0-9]{1,2}\s*(?::[0-9]{2})?\s*(?:AM|PM))", plain, re.IGNORECASE)
    role_match = re.search(r"\b(bartender|server|cleaner|mover|photographer|security)\b", plain, re.IGNORECASE)
    location_match = re.search(r"\b(SoMa|San Francisco|Mission|Oakland|Berkeley)\b", plain, re.IGNORECASE)

    return ImportedShift(
        business_name="Bay Events Co." if "Bay Events" in plain else urlparse(source_url).hostname or "Unknown",
        role=(role_match.group(1).lower() if role_match else "contractor"),
        description=plain[:240],
        location=location_match.group(1) if location_match else "Unknown",
        start_time=time_match.group(1).strip() if time_match else "Unknown",
        end_time=time_match.group(2).strip() if time_match else "Unknown",
        pay_amount=float(pay_match.group(1)) if pay_match else 0,
        urgency="urgent" if re.search(r"\b(urgent|asap|tonight|canceled|cancelled)\b", plain, re.IGNORECASE) else "normal",
        required_skills=["event experience"] if "event experience" in plain.lower() else [],
        source_type="staffing_portal",
        evidence_summary="Fallback extraction from visible page text.",
        extraction_confidence=0.62,
    )


def _normalize_imported_shift(data: dict[str, Any], *, default_source_type: str) -> ImportedShift:
    required_skills = data.get("required_skills") or data.get("requiredSkills") or []
    if isinstance(required_skills, str):
        required_skills = [skill.strip() for skill in required_skills.split(",") if skill.strip()]

    pay = data.get("pay_amount", data.get("payAmount", data.get("pay", 0)))
    if isinstance(pay, str):
        pay = re.sub(r"[^0-9.]", "", pay) or 0

    return ImportedShift(
        business_name=str(data.get("business_name") or data.get("businessName") or "Bay Events Co."),
        role=str(data.get("role") or "contractor").lower(),
        description=data.get("description"),
        location=str(data.get("location") or "Unknown"),
        start_time=str(data.get("start_time") or data.get("startTime") or "Unknown"),
        end_time=str(data.get("end_time") or data.get("endTime") or "Unknown"),
        pay_amount=float(pay),
        urgency=str(data.get("urgency") or "normal").lower(),
        required_skills=[str(skill) for skill in required_skills],
        source_type=str(data.get("source_type") or data.get("sourceType") or default_source_type),
        evidence_summary=str(data.get("evidence_summary") or data.get("evidenceSummary") or "Extracted from source page."),
        extraction_confidence=float(data.get("extraction_confidence") or data.get("extractionConfidence") or 0.85),
    )


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


async def _capture_screenshot(
    source_url: str,
    evidence_id: str,
    shift: ImportedShift,
    action_log: list[dict[str, Any]],
) -> str:
    screenshot_name = f"browser-source-{evidence_id}.png"
    screenshot_path = EVIDENCE_DIR / screenshot_name
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1440, "height": 1100})
            await page.goto(source_url, wait_until="networkidle", timeout=15000)
            await page.screenshot(path=str(screenshot_path), full_page=True)
            await browser.close()
        screenshot_url = f"/static/evidence/{screenshot_name}"
        action_log.append({"step": "screenshot_captured", "status": "ok", "url": screenshot_url})
        return screenshot_url
    except Exception as exc:
        logger.warning("Playwright screenshot failed; writing SVG evidence card: %s", exc)
        fallback_name = f"browser-source-{evidence_id}.svg"
        fallback_path = EVIDENCE_DIR / fallback_name
        fallback_path.write_text(_evidence_svg(source_url, shift), encoding="utf-8")
        fallback_url = f"/static/evidence/{fallback_name}"
        action_log.append(
            {
                "step": "screenshot_captured",
                "status": "fallback",
                "url": fallback_url,
                "message": "Playwright unavailable; generated evidence card instead.",
            }
        )
        return fallback_url


def _evidence_svg(source_url: str, shift: ImportedShift) -> str:
    rows = [
        ("Source", source_url),
        ("Business", shift.business_name),
        ("Role", shift.role),
        ("Time", f"{shift.start_time} to {shift.end_time}"),
        ("Location", shift.location),
        ("Pay", f"${shift.pay_amount:g}"),
        ("Urgency", shift.urgency),
        ("Skills", ", ".join(shift.required_skills)),
    ]
    svg_rows = []
    y = 128
    for label, value in rows:
        svg_rows.append(
            f'<text x="64" y="{y}" fill="#7A766C" font-size="18">{html.escape(label)}</text>'
            f'<text x="230" y="{y}" fill="#161410" font-size="20" font-weight="600">{html.escape(value)}</text>'
        )
        y += 42
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">
  <rect width="1200" height="620" fill="#F6F4EE"/>
  <rect x="36" y="36" width="1128" height="548" rx="18" fill="#FBFAF6" stroke="#D8D0C1"/>
  <text x="64" y="86" fill="#161410" font-family="Arial, sans-serif" font-size="34" font-weight="700">CrewLoop Browser Source Evidence</text>
  <g font-family="Arial, sans-serif">{''.join(svg_rows)}</g>
</svg>"""
