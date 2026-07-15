"""Statischen Export für tagcore.de erzeugen (Portfolio-Startseite ohne Bewerbungsliste)."""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
AI_ROOT = PROJECT_ROOT.parents[1]

if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from Integrations.Gmail.application_attachments import (  # noqa: E402
    resolve_standard_application_attachments,
)
from urls import (  # noqa: E402
    build_application_url,
    build_qr_url,
    company_slug,
)

CONFIG_FILE = PROJECT_ROOT / "site.config.yaml"
GREETING_LINE_PATTERN = re.compile(r"(?i)sehr\s+geehrte")

MONTH_NAMES = {
    "01": "Jan",
    "02": "Feb",
    "03": "Mär",
    "04": "Apr",
    "05": "Mai",
    "06": "Jun",
    "07": "Jul",
    "08": "Aug",
    "09": "Sep",
    "10": "Okt",
    "11": "Nov",
    "12": "Dez",
}

CERTIFICATE_KEYS = {
    "exp-tibas": "tibas",
    "exp-atzinger": "atzinger",
}


@dataclass(frozen=True)
class SiteConfig:
    brand_name: str
    domain: str
    base_url: str
    qr_landing_path: str
    profile_yaml: Path
    experiences_dir: Path
    sender_config: Path
    applications_base: Path
    reference_base: Path
    require_approved: bool
    output_dir: Path


@dataclass
class ApplicationEntry:
    company: str
    job_title: str
    folder_name: str
    folder_path: Path
    approved_at: str
    slug: str
    url: str
    cover_letter_text: str | None = None
    cover_letter_download: str | None = None


@dataclass(frozen=True)
class ExperienceEntry:
    id: str
    company: str
    role: str
    location: str
    period_from: str
    period_to: str
    period_display: str
    certificate_href: str | None = None
    certificate_mime: str | None = None


@dataclass(frozen=True)
class ContactInfo:
    location: str
    email: str | None = None
    phone: str | None = None


def _resolve_path(value: str, *, base: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def load_site_config(config_path: Path = CONFIG_FILE) -> SiteConfig:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return SiteConfig(
        brand_name=str(raw.get("brand_name", "TagCore")),
        domain=str(raw.get("domain", "tagcore.de")),
        base_url=str(raw.get("base_url", "https://www.tagcore.de")),
        qr_landing_path=str(raw.get("qr_landing_path", "/")),
        profile_yaml=_resolve_path(
            str(raw.get("profile_yaml", "../BewerbungsAgent/knowledge/profile.yaml")),
            base=PROJECT_ROOT,
        ),
        experiences_dir=_resolve_path(
            str(raw.get("experiences_dir", "../BewerbungsAgent/knowledge/experiences")),
            base=PROJECT_ROOT,
        ),
        sender_config=_resolve_path(
            str(raw.get("sender_config", "../BewerbungsAgent/knowledge/docx/config.yaml")),
            base=PROJECT_ROOT,
        ),
        applications_base=_resolve_path(
            str(raw.get("applications_base", "K:/AI/Bewerbungen 2026")),
            base=PROJECT_ROOT,
        ),
        reference_base=_resolve_path(
            str(raw.get("reference_base", "K:/AI/application documents")),
            base=PROJECT_ROOT,
        ),
        require_approved=bool(raw.get("require_approved", True)),
        output_dir=_resolve_path(str(raw.get("output_dir", "dist")), base=PROJECT_ROOT),
    )


def load_profile(profile_path: Path) -> dict:
    if not profile_path.is_file():
        return {
            "person": {
                "name": "Florian Pfisterhammer",
                "title": "Key Account Manager / Vertrieb",
            }
        }
    return yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}


def load_sender_config(sender_path: Path) -> ContactInfo:
    if not sender_path.is_file():
        return ContactInfo(location="Bayern")
    raw = yaml.safe_load(sender_path.read_text(encoding="utf-8")) or {}
    sender = raw.get("sender", {})
    zip_city = str(sender.get("zip_city", "")).strip()
    location = zip_city.split(",")[-1].strip() if "," in zip_city else zip_city
    if location and not location.endswith("Bayern"):
        location = f"{location}, Bayern"
    return ContactInfo(
        location=location or "Bayern",
        email=str(sender.get("email", "")).strip() or None,
        phone=str(sender.get("phone", "")).strip() or None,
    )


def format_month_year(value: str) -> str:
    """YYYY-MM → „Mai 2025“."""
    if not value or len(value) < 7:
        return value
    year = value[:4]
    month = value[5:7]
    label = MONTH_NAMES.get(month, month)
    return f"{label} {year}"


def format_period(period: dict | None) -> str:
    if not period:
        return ""
    start = format_month_year(str(period.get("from", "")))
    end_raw = str(period.get("to", ""))
    end = format_month_year(end_raw) if end_raw else "heute"
    if not start:
        return end
    return f"{start} – {end}"


def _certificate_extension(source: Path) -> str:
    suffix = source.suffix.lower().lstrip(".")
    if suffix == "jpeg":
        return "jpeg"
    if suffix in {"jpg", "png", "pdf"}:
        return suffix
    return "jpg"


def _certificate_mime(extension: str) -> str:
    mapping = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
    }
    return mapping.get(extension, "application/octet-stream")


def load_experiences(profile: dict, experiences_dir: Path) -> list[ExperienceEntry]:
    experience_ids = profile.get("indexes", {}).get("experiences", [])
    entries: list[ExperienceEntry] = []

    for exp_id in experience_ids:
        exp_path = experiences_dir / f"{exp_id}.yaml"
        if not exp_path.is_file():
            continue
        data = yaml.safe_load(exp_path.read_text(encoding="utf-8")) or {}
        period = data.get("period") or {}
        entries.append(
            ExperienceEntry(
                id=str(data.get("id", exp_id)),
                company=str(data.get("company", "")),
                role=str(data.get("role", "")),
                location=str(data.get("location", "")),
                period_from=str(period.get("from", "")),
                period_to=str(period.get("to", "")),
                period_display=format_period(period),
            )
        )

    entries.sort(key=lambda item: item.period_from, reverse=True)
    return entries


def _asset_name(source: Path) -> str:
    mapping = {
        "lebenslauf 2026.docx": "lebenslauf-2026.docx",
        "atzinger zeugnis.jpg": "atzinger-zeugnis.jpg",
        "tibas arbeitszeugnis.jpeg": "tibas-arbeitszeugnis.jpeg",
        "anschreiben.docx": "anschreiben.docx",
    }
    return mapping.get(source.name.lower(), source.name.replace(" ", "-"))


def collect_reference_documents() -> list[tuple[str, Path, str]]:
    """(label, source_path, asset_filename)"""
    resolved = resolve_standard_application_attachments()
    labels = {
        "cv": "Lebenslauf 2026",
        "atzinger_certificate": "Arbeitszeugnis Atzinger Verpackung GmbH",
        "tibas_certificate": "Arbeitszeugnis Tibas Gummi GmbH",
    }
    docs: list[tuple[str, Path, str]] = []
    for key, label in labels.items():
        path = resolved.get(key)
        if path is not None and path.is_file():
            docs.append((label, path, _asset_name(path)))
    return docs


def copy_certificates(
    *,
    output_dir: Path,
    attachments: dict[str, Path],
    experiences: list[ExperienceEntry],
) -> list[ExperienceEntry]:
    zeugnisse_dir = output_dir / "assets" / "zeugnisse"
    zeugnisse_dir.mkdir(parents=True, exist_ok=True)

    attachment_by_key = {
        "tibas": attachments.get("tibas_certificate"),
        "atzinger": attachments.get("atzinger_certificate"),
    }

    updated: list[ExperienceEntry] = []
    for exp in experiences:
        firm_slug = CERTIFICATE_KEYS.get(exp.id)
        source = attachment_by_key.get(firm_slug or "")
        if firm_slug and source is not None and source.is_file():
            extension = _certificate_extension(source)
            filename = f"{firm_slug}.{extension}"
            target = zeugnisse_dir / filename
            shutil.copy2(source, target)
            href = f"/assets/zeugnisse/{filename}"
            updated.append(
                ExperienceEntry(
                    id=exp.id,
                    company=exp.company,
                    role=exp.role,
                    location=exp.location,
                    period_from=exp.period_from,
                    period_to=exp.period_to,
                    period_display=exp.period_display,
                    certificate_href=href,
                    certificate_mime=_certificate_mime(extension),
                )
            )
        else:
            updated.append(exp)
    return updated


def extract_cover_letter_text(docx_path: Path) -> str | None:
    try:
        from docx import Document
    except ImportError:
        return None
    if not docx_path.is_file():
        return None
    try:
        paragraphs = [paragraph.text.strip() for paragraph in Document(docx_path).paragraphs if paragraph.text.strip()]
    except Exception:
        return None
    if not paragraphs:
        return None
    greeting_index = next(
        (index for index, paragraph in enumerate(paragraphs) if GREETING_LINE_PATTERN.search(paragraph)),
        None,
    )
    if greeting_index is None:
        return "\n\n".join(paragraphs)
    return "\n\n".join(paragraphs[greeting_index:])


def collect_applications(config: SiteConfig) -> list[ApplicationEntry]:
    if not config.applications_base.is_dir():
        return []

    entries: list[ApplicationEntry] = []
    used_slugs: dict[str, int] = {}

    for folder in sorted(config.applications_base.iterdir()):
        if not folder.is_dir():
            continue
        meta_path = folder / "metadata.json"
        if not meta_path.is_file():
            continue
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        if config.require_approved and not data.get("approved_at"):
            continue
        cover_path = folder / "Anschreiben.docx"
        if not cover_path.is_file():
            continue

        company = str(data.get("company", folder.name))
        folder_name = str(data.get("folder_name") or folder.name)
        slug = company_slug(company)
        if slug in used_slugs:
            used_slugs[slug] += 1
            slug = f"{slug}-{used_slugs[slug]}"
        else:
            used_slugs[slug] = 1

        entries.append(
            ApplicationEntry(
                company=company,
                job_title=str(data.get("job_title") or data.get("position", "")),
                folder_name=folder_name,
                folder_path=folder,
                approved_at=str(data.get("approved_at", "")),
                slug=slug,
                url=build_application_url(company, base_url=config.base_url),
                cover_letter_text=extract_cover_letter_text(cover_path),
            )
        )

    entries.sort(key=lambda item: item.approved_at or item.company, reverse=True)
    return entries


def _head_block(*, title: str, description: str) -> str:
    return f"""  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/site.css">"""


def _render_station_cards(experiences: list[ExperienceEntry]) -> str:
    cards: list[str] = []
    for exp in experiences:
        cert_attrs = ""
        tag = "article"
        if exp.certificate_href:
            cert_attrs = (
                f' role="button" tabindex="0" class="station-card has-certificate" '
                f'data-certificate="{escape(exp.certificate_href, quote=True)}" '
                f'data-mime="{escape(exp.certificate_mime or "", quote=True)}" '
                f'data-title="{escape(f"Zeugnis — {exp.company}", quote=True)}" '
                f'aria-label="{escape(f"Zeugnis von {exp.company} öffnen")}"'
            )
        else:
            cert_attrs = ' class="station-card" aria-label="{}"'.format(escape(exp.company))

        location_line = (
            f'<p class="station-location">{escape(exp.location)}</p>' if exp.location else ""
        )
        cert_hint = (
            '<span class="station-cert-hint">Zeugnis ansehen</span>'
            if exp.certificate_href
            else '<span class="station-cert-hint muted">Kein Zeugnis hinterlegt</span>'
        )
        cards.append(
            f"""      <{tag}{cert_attrs}>
        <div class="station-card-inner">
          <h3>{escape(exp.company)}</h3>
          <p class="station-role">{escape(exp.role)}</p>
          <p class="station-period">{escape(exp.period_display)}</p>
          {location_line}
          {cert_hint}
        </div>
      </{tag}>"""
        )
    return "\n".join(cards)


def _render_about_paragraphs(summary: str) -> str:
    text = summary.strip()
    if not text:
        return "<p>Ich freue mich auf den Austausch über passende Herausforderungen im Vertrieb.</p>"

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
        if sentence.strip()
    ]
    sentences = [
        sentence
        for sentence in sentences
        if not re.search(r"(?i)(repository\s+k:|nachweise\s+aus\s+lebenslauf)", sentence)
    ]

    grouped: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        current.append(sentence)
        if len(current) >= 2:
            grouped.append(" ".join(current))
            current = []
    if current:
        grouped.append(" ".join(current))

    warm_close = (
        "Ich freue mich über den persönlichen Austausch und bringe Zuverlässigkeit, "
        "Neugier und echte Begeisterung für vertriebliche und digitale Themen mit."
    )
    paragraphs = grouped[:3] or sentences[:2]
    if warm_close not in " ".join(paragraphs):
        paragraphs.append(warm_close)
    return "\n".join(f"          <p>{escape(chunk)}</p>" for chunk in paragraphs[:4])


def _render_contact(contact: ContactInfo) -> str:
    parts: list[str] = []
    if contact.email:
        parts.append(
            f'<a href="mailto:{escape(contact.email)}">{escape(contact.email)}</a>'
        )
    if contact.phone:
        parts.append(f'<span>{escape(contact.phone)}</span>')
    if not parts:
        return ""
    return f'        <p class="about-contact">{" · ".join(parts)}</p>'


def render_homepage(
    *,
    title: str,
    person: dict,
    contact: ContactInfo,
    experiences: list[ExperienceEntry],
    documents: list[tuple[str, str]],
    brand_name: str,
) -> str:
    name = escape(str(person.get("name", "Bewerbungsprofil")))
    headline = escape(str(person.get("title", "")).strip())
    summary = str(person.get("summary", "")).strip()
    station_cards = _render_station_cards(experiences)
    about_paragraphs = _render_about_paragraphs(summary)
    contact_block = _render_contact(contact)

    doc_items = "\n".join(
        f'          <li><a href="{escape(href)}" download>{escape(label)}</a></li>'
        for label, href in documents
    )
    downloads_section = ""
    if doc_items:
        downloads_section = f"""    <section class="panel downloads-panel" id="unterlagen">
      <h2>Unterlagen</h2>
      <ul class="downloads">
{doc_items}
      </ul>
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
{_head_block(title=title, description=f"Portfolio — {name}")}
</head>
<body>
  <a class="skip-link" href="#main">Zum Inhalt springen</a>
  <main id="main">
    <section class="hero" aria-labelledby="hero-title">
      <div class="hero-inner fade-in">
        <p class="hero-eyebrow">Portfolio</p>
        <h1 id="hero-title">{name}</h1>
        <p class="hero-tagline">{headline}</p>
      </div>
    </section>

    <section class="panel stationen-panel" id="stationen" aria-labelledby="stationen-title">
      <h2 id="stationen-title">Meine Stationen</h2>
      <div class="station-grid">
{station_cards}
      </div>
    </section>

    <section class="panel about-panel" id="ueber-mich" aria-labelledby="about-title">
      <h2 id="about-title">Über mich</h2>
      <div class="about-body">
{about_paragraphs}
        <p class="about-location">
          <svg class="icon-location" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path fill="currentColor" d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"/>
          </svg>
          <span>{escape(contact.location)}</span>
        </p>
{contact_block}
      </div>
    </section>
{downloads_section}
  </main>

  <footer class="site-footer">
    <p>{escape(brand_name)}</p>
  </footer>

  <div id="certificate-modal" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <div class="modal-backdrop" data-close-modal></div>
    <div class="modal-panel" role="document">
      <header class="modal-header">
        <h2 id="modal-title">Zeugnis</h2>
        <button type="button" class="modal-close" aria-label="Schließen" data-close-modal>&times;</button>
      </header>
      <div class="modal-body" id="modal-body"></div>
      <footer class="modal-footer">
        <a id="modal-download" href="#" download class="button-secondary">Herunterladen</a>
        <button type="button" class="button-primary" data-close-modal>Schließen</button>
      </footer>
    </div>
  </div>

  <script src="/assets/site.js" defer></script>
</body>
</html>
"""


def render_application_page(
    *,
    entry: ApplicationEntry,
    person: dict,
    documents: list[tuple[str, str]],
    cover_letter_text: str | None,
) -> str:
    name = escape(str(person.get("name", "Bewerbungsprofil")))
    company = escape(entry.company)
    job_title = escape(entry.job_title)
    approved = ""
    if entry.approved_at:
        try:
            approved_dt = datetime.fromisoformat(entry.approved_at.replace("Z", "+00:00"))
            approved = approved_dt.astimezone().strftime("%d.%m.%Y")
        except ValueError:
            approved = entry.approved_at[:10]

    if cover_letter_text:
        letter_html = "".join(
            f"<p>{escape(paragraph)}</p>"
            for paragraph in cover_letter_text.split("\n\n")
            if paragraph.strip()
        )
    else:
        letter_html = (
            '<p class="muted">Anschreiben-Text konnte nicht extrahiert werden. '
            "Bitte laden Sie die DOCX-Datei herunter.</p>"
        )

    app_downloads = list(documents)
    if entry.cover_letter_download:
        app_downloads.insert(0, ("Anschreiben", entry.cover_letter_download))

    doc_items = "\n".join(
        f'        <li><a href="{escape(href)}" download>{escape(label)}</a></li>'
        for label, href in app_downloads
    )

    approved_line = f'<p class="meta">Freigegeben am {escape(approved)}</p>' if approved else ""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
{_head_block(title=f"{company} — {name}", description=f"Bewerbung als {job_title} bei {company}")}
</head>
<body>
  <a class="skip-link" href="#main">Zum Inhalt springen</a>
  <main id="main" class="container">
    <nav class="site-nav" aria-label="Seitennavigation"><a href="/">← Startseite</a></nav>
    <header class="panel application-header">
      <p class="eyebrow">Bewerbung</p>
      <h1>{company}</h1>
      <p class="headline">{job_title}</p>
      {approved_line}
    </header>
    <section class="panel letter">
      <h2>Anschreiben</h2>
      <div class="letter-body">
{letter_html}
      </div>
    </section>
    <section class="panel">
      <h2>Downloads</h2>
      <ul class="downloads">
{doc_items}
      </ul>
    </section>
  </main>
  <footer class="site-footer">
    <p><a href="/">Zurück zur Startseite</a></p>
  </footer>
</body>
</html>
"""


def _write_css(output_dir: Path) -> None:
    css = """
:root {
  color-scheme: light;
  --bg: #f7f9fc;
  --bg-accent: #eef3ff;
  --surface: rgba(255, 255, 255, 0.82);
  --text: #0f172a;
  --muted: #64748b;
  --accent: #1d4ed8;
  --accent-hover: #1e40af;
  --accent-soft: #dbeafe;
  --border: rgba(148, 163, 184, 0.35);
  --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
  --shadow-hover: 0 16px 40px rgba(29, 78, 216, 0.14);
  --radius: 18px;
  --font: "Plus Jakarta Sans", system-ui, -apple-system, sans-serif;
  --max-width: 980px;
  --transition: 180ms ease;
}

*, *::before, *::after { box-sizing: border-box; }

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  font-family: var(--font);
  background:
    radial-gradient(circle at top right, var(--bg-accent), transparent 42%),
    linear-gradient(180deg, #ffffff 0%, var(--bg) 100%);
  color: var(--text);
  line-height: 1.65;
  font-size: 1rem;
  min-height: 100vh;
}

a { color: var(--accent); text-decoration: none; }
a:hover { color: var(--accent-hover); text-decoration: underline; }

.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  background: var(--accent);
  color: #fff;
  padding: 0.5rem 1rem;
  z-index: 1000;
}
.skip-link:focus { left: 1rem; top: 1rem; }

main {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 2rem 1.25rem 3rem;
}

.container { max-width: 760px; }

.hero {
  padding: 3.5rem 0 2.5rem;
  text-align: center;
}

.hero-inner {
  max-width: 720px;
  margin: 0 auto;
}

.hero-eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent);
  margin: 0 0 0.75rem;
}

.hero h1 {
  margin: 0;
  font-size: clamp(2.2rem, 6vw, 3.4rem);
  line-height: 1.08;
  letter-spacing: -0.03em;
  font-weight: 700;
}

.hero-tagline {
  margin: 1rem auto 0;
  max-width: 36rem;
  font-size: clamp(1.05rem, 2.5vw, 1.25rem);
  color: var(--muted);
  font-weight: 500;
}

.fade-in {
  animation: fadeUp 700ms ease both;
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}

.panel {
  background: var(--surface);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.5rem 1.6rem;
  margin-bottom: 1.25rem;
}

.panel h2 {
  margin: 0 0 1.1rem;
  font-size: 1.2rem;
  color: var(--accent);
  letter-spacing: -0.01em;
}

.station-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}

.station-card {
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) - 4px);
  background: rgba(255, 255, 255, 0.72);
  transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
}

.station-card.has-certificate {
  cursor: pointer;
}

.station-card.has-certificate:hover,
.station-card.has-certificate:focus-visible {
  transform: translateY(-3px);
  box-shadow: var(--shadow-hover);
  border-color: rgba(29, 78, 216, 0.35);
  outline: none;
}

.station-card-inner { padding: 1.1rem 1.15rem; }

.station-card h3 {
  margin: 0 0 0.35rem;
  font-size: 1.02rem;
  line-height: 1.3;
}

.station-role {
  margin: 0;
  font-weight: 600;
  color: var(--text);
  font-size: 0.95rem;
}

.station-period,
.station-location {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.station-cert-hint {
  display: inline-block;
  margin-top: 0.75rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--accent);
}

.station-cert-hint.muted { color: var(--muted); font-weight: 500; }

.about-body p { margin: 0 0 0.85rem; }

.about-location {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin: 1rem 0 0.35rem;
  font-weight: 600;
}

.about-contact { margin: 0.35rem 0 0; color: var(--muted); }

.icon-location { flex-shrink: 0; color: var(--accent); }

.downloads,
.application-links {
  margin: 0;
  padding-left: 1.2rem;
}

.application-links li { margin-bottom: 0.45rem; }

.site-nav {
  margin-bottom: 1rem;
  font-weight: 600;
}

.site-nav a { text-decoration: none; }

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.75rem;
  color: var(--muted);
  margin: 0 0 0.35rem;
}

.application-header h1,
.panel h1 {
  margin: 0.1rem 0 0.35rem;
  font-size: clamp(1.5rem, 4vw, 2rem);
}

.headline {
  color: var(--accent);
  margin: 0.2rem 0 0;
  font-weight: 600;
}

.letter-body p { margin: 0 0 0.85rem; white-space: pre-wrap; }

.meta, .muted { color: var(--muted); }

.site-footer {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0 1.25rem 2rem;
  text-align: center;
  color: var(--muted);
  font-size: 0.92rem;
}

.modal[hidden] { display: none; }

.modal {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: grid;
  place-items: center;
  padding: 1rem;
}

.modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
}

.modal-panel {
  position: relative;
  width: min(920px, 100%);
  max-height: min(90vh, 900px);
  background: #fff;
  border-radius: var(--radius);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.25);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header,
.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border);
}

.modal-footer { border-bottom: 0; border-top: 1px solid var(--border); }

.modal-header h2 {
  margin: 0;
  font-size: 1rem;
  color: var(--text);
}

.modal-close {
  border: 0;
  background: transparent;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  color: var(--muted);
}

.modal-body {
  padding: 0.75rem 1rem 1rem;
  overflow: auto;
  flex: 1;
}

.modal-body img,
.modal-body iframe,
.modal-body object {
  display: block;
  width: 100%;
  max-height: 70vh;
  border: 0;
  border-radius: 8px;
}

.button-primary,
.button-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.55rem 0.95rem;
  border-radius: 999px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  text-decoration: none;
}

.button-primary {
  background: var(--accent);
  color: #fff;
}

.button-secondary {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: rgba(29, 78, 216, 0.15);
}

@media (max-width: 640px) {
  main { padding: 1.25rem 1rem 2.5rem; }
  .hero { padding: 2.5rem 0 1.75rem; }
  .panel { padding: 1.15rem 1.1rem; }
  .modal-footer { flex-direction: column; align-items: stretch; }
}

@media print {
  body { background: #fff; color: #000; }
  .site-nav, .site-footer, .modal, .skip-link { display: none !important; }
  .panel { box-shadow: none; border: none; background: transparent; padding: 0 0 1rem; }
  a { color: #000; text-decoration: none; }
}
"""
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "site.css").write_text(css.strip() + "\n", encoding="utf-8")


def _write_js(output_dir: Path) -> None:
    js = """
(function () {
  const modal = document.getElementById("certificate-modal");
  const modalBody = document.getElementById("modal-body");
  const modalTitle = document.getElementById("modal-title");
  const modalDownload = document.getElementById("modal-download");
  let lastFocus = null;

  function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    modalBody.innerHTML = "";
    document.body.style.overflow = "";
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus();
    }
  }

  function openModal(href, mime, title) {
    if (!modal || !href) return;
    lastFocus = document.activeElement;
    modalTitle.textContent = title || "Zeugnis";
    modalDownload.href = href;
    modalDownload.hidden = false;

    if (mime && mime.startsWith("image/")) {
      const img = document.createElement("img");
      img.src = href;
      img.alt = title || "Arbeitszeugnis";
      modalBody.replaceChildren(img);
    } else {
      const frame = document.createElement("iframe");
      frame.src = href;
      frame.title = title || "Arbeitszeugnis";
      modalBody.replaceChildren(frame);
    }

    modal.hidden = false;
    document.body.style.overflow = "hidden";
    modal.querySelector(".modal-close").focus();
  }

  document.querySelectorAll(".station-card.has-certificate").forEach((card) => {
    card.addEventListener("click", () => {
      openModal(card.dataset.certificate, card.dataset.mime, card.dataset.title);
    });
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openModal(card.dataset.certificate, card.dataset.mime, card.dataset.title);
      }
    });
  });

  modal?.querySelectorAll("[data-close-modal]").forEach((el) => {
    el.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.hidden) {
      closeModal();
    }
  });
})();
"""
    (output_dir / "assets" / "site.js").write_text(js.strip() + "\n", encoding="utf-8")


def _copy_application_assets(
    entry: ApplicationEntry,
    output_dir: Path,
) -> str | None:
    cover_source = entry.folder_path / "Anschreiben.docx"
    if not cover_source.is_file():
        return None
    app_assets = output_dir / "assets" / "applications" / entry.slug
    app_assets.mkdir(parents=True, exist_ok=True)
    target = app_assets / "anschreiben.docx"
    shutil.copy2(cover_source, target)
    return f"/assets/applications/{entry.slug}/anschreiben.docx"


def export_site(config: SiteConfig | None = None) -> Path:
    config = config or load_site_config()
    output_dir = config.output_dir
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    profile = load_profile(config.profile_yaml)
    person = profile.get("person", {})
    contact = load_sender_config(config.sender_config)
    attachments = resolve_standard_application_attachments()

    experiences = load_experiences(profile, config.experiences_dir)
    docs = collect_reference_documents()

    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    document_links: list[tuple[str, str]] = []
    for label, source, asset_name in docs:
        target = assets_dir / asset_name
        shutil.copy2(source, target)
        document_links.append((label, f"/assets/{asset_name}"))

    experiences = copy_certificates(
        output_dir=output_dir,
        attachments=attachments,
        experiences=experiences,
    )

    qr_url = build_qr_url(base_url=config.base_url, landing_path=config.qr_landing_path)

    homepage_html = render_homepage(
        title=f"{person.get('name', 'Bewerbung')} — {config.brand_name}",
        person=person,
        contact=contact,
        experiences=experiences,
        documents=document_links,
        brand_name=config.brand_name,
    )
    (output_dir / "index.html").write_text(homepage_html, encoding="utf-8")

    _write_css(output_dir)
    _write_js(output_dir)

    manifest = {
        "exported_at": datetime.now().astimezone().isoformat(),
        "brand_name": config.brand_name,
        "domain": config.domain,
        "base_url": config.base_url,
        "qr_url": qr_url,
        "structure": "portfolio-homepage",
        "experiences": [
            {
                "id": exp.id,
                "company": exp.company,
                "role": exp.role,
                "period": exp.period_display,
                "certificate": exp.certificate_href,
            }
            for exp in experiences
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_dir


def main() -> int:
    try:
        out = export_site()
    except Exception as exc:
        print(f"Export fehlgeschlagen: {exc}", file=sys.stderr)
        return 1
    print(f"Export OK: {out}")
    config = load_site_config()
    print(f"QR-URL (Unterlagen): {build_qr_url(base_url=config.base_url, landing_path=config.qr_landing_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
