"""URL-Hilfen für tagcore.de QR-Landing und Bewerbungs-Slugs."""

from __future__ import annotations

import re

DEFAULT_DOMAIN = "tagcore.de"
DEFAULT_BASE_URL = "https://www.tagcore.de"
DEFAULT_QR_LANDING_PATH = "/"

_SLUG_PATTERN = re.compile(r"[^\w\-]+", re.UNICODE)


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def normalize_path(path: str) -> str:
    cleaned = path.strip()
    if not cleaned:
        return "/"
    return cleaned if cleaned.startswith("/") else f"/{cleaned}"


def slugify(value: str, *, max_length: int = 80) -> str:
    """URL-Slug aus beliebigem Text (Firmenname, Ordnername)."""
    slug = value.strip().lower()
    slug = _SLUG_PATTERN.sub("-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        return "bewerbung"
    return slug[:max_length].strip("-")


def company_slug(company: str, *, max_length: int = 80) -> str:
    """URL-Slug aus Firmenname (z. B. leyton-deutschland-gmbh)."""
    return slugify(company, max_length=max_length)


def application_slug(folder_name: str, *, max_length: int = 80) -> str:
    """URL-Slug aus BewerbungsAgent-Ordnernamen (Legacy-Kompatibilität)."""
    return slugify(folder_name, max_length=max_length)


def build_qr_url(*, base_url: str = DEFAULT_BASE_URL, landing_path: str = DEFAULT_QR_LANDING_PATH) -> str:
    """URL für QR-Code auf gedruckten Bewerbungsunterlagen."""
    base = normalize_base_url(base_url)
    path = normalize_path(landing_path)
    if path == "/":
        return f"{base}/"
    return f"{base}{path}"


def build_application_url(
    company: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
) -> str:
    """Pro-Bewerbung-URL unter /{company-slug}/."""
    base = normalize_base_url(base_url)
    return f"{base}/{company_slug(company)}/"


def qr_url_template(*, base_url: str = DEFAULT_BASE_URL, landing_path: str = DEFAULT_QR_LANDING_PATH) -> str:
    """Telegram-/Druck-Hinweis mit Platzhalter für Stellen-Slug."""
    landing = build_qr_url(base_url=base_url, landing_path=landing_path)
    return f"{landing}{{slug}}/"
