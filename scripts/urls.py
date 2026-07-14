"""URL-Hilfen für tagcore.de QR-Landing und Bewerbungs-Slugs."""

from __future__ import annotations

import re

DEFAULT_DOMAIN = "tagcore.de"
DEFAULT_BASE_URL = f"https://{DEFAULT_DOMAIN}"
DEFAULT_QR_LANDING_PATH = "/bewerbung"

_SLUG_PATTERN = re.compile(r"[^\w\-]+", re.UNICODE)


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def normalize_path(path: str) -> str:
    cleaned = path.strip()
    if not cleaned:
        return "/"
    return cleaned if cleaned.startswith("/") else f"/{cleaned}"


def build_qr_url(*, base_url: str = DEFAULT_BASE_URL, landing_path: str = DEFAULT_QR_LANDING_PATH) -> str:
    """URL für QR-Code auf gedruckten Bewerbungsunterlagen."""
    return f"{normalize_base_url(base_url)}{normalize_path(landing_path)}"


def application_slug(folder_name: str, *, max_length: int = 80) -> str:
    """URL-Slug aus BewerbungsAgent-Ordnernamen (Phase 2)."""
    slug = folder_name.strip().lower()
    slug = _SLUG_PATTERN.sub("-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        return "bewerbung"
    return slug[:max_length].strip("-")


def build_application_url(
    folder_name: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    applications_path: str = "/bewerbung",
) -> str:
    """Pro-Bewerbung-URL (Phase 2)."""
    base = normalize_base_url(base_url)
    prefix = normalize_path(applications_path).rstrip("/")
    return f"{base}{prefix}/{application_slug(folder_name)}"


def qr_url_template(*, base_url: str = DEFAULT_BASE_URL, landing_path: str = DEFAULT_QR_LANDING_PATH) -> str:
    """Telegram-/Druck-Hinweis mit Platzhalter für Stellen-Slug."""
    landing = build_qr_url(base_url=base_url, landing_path=landing_path)
    return f"{landing}/{{slug}}"
