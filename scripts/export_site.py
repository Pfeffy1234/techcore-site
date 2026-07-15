"""Statischen Export für tagcore.de erzeugen (Profil, Bewerbungen, Detailseiten)."""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
AI_ROOT = PROJECT_ROOT.parents[1]
KNOWLEDGE_ROOT = PROJECT_ROOT.parent / "BewerbungsAgent" / "knowledge"

if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from Integrations.Gmail.application_attachments import (  # noqa: E402
    resolve_standard_application_attachments,
)
from urls import (  # noqa: E402
    application_slug,
    build_application_url,
    build_qr_url,
)

CONFIG_FILE = PROJECT_ROOT / "site.config.yaml"
GREETING_LINE_PATTERN = re.compile(r"(?i)sehr\s+geehrte")


@dataclass(frozen=True)
class SiteConfig:
    domain: str
    base_url: str
    qr_landing_path: str
    profile_yaml: Path
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


@dataclass
class ExperienceHighlight:
    company: str
    role: str
    period: str
    location: str
    highlights: list[str] = field(default_factory=list)


@dataclass
class SkillGroup:
    title: str
    items: list[str] = field(default_factory=list)


def _resolve_path(value: str, *, base: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def load_site_config(config_path: Path = CONFIG_FILE) -> SiteConfig:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return SiteConfig(
        domain=str(raw.get("domain", "tagcore.de")),
        base_url=str(raw.get("base_url", "https://tagcore.de")),
        qr_landing_path=str(raw.get("qr_landing_path", "/bewerbung")),
        profile_yaml=_resolve_path(
            str(raw.get("profile_yaml", "../BewerbungsAgent/knowledge/profile.yaml")),
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
                "summary": "Bewerbungsprofil — Profildaten fehlen lokal.",
            }
        }
    return yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}


def _format_period(period: dict | None) -> str:
    if not period:
        return ""
    start = str(period.get("from", "")).strip()
    end = str(period.get("to", "")).strip() or "heute"
    if not start:
        return end
    return f"{start} – {end}"


def _load_yaml_items(path: Path, *, key: str = "items") -> dict[str, dict]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get(key) or data.get("experiences") or []
    if isinstance(items, list) and items and isinstance(items[0], str):
        return {}
    if isinstance(items, list):
        return {str(item.get("id", "")): item for item in items if isinstance(item, dict)}
    return {}


def load_experience_highlights(profile: dict, knowledge_root: Path = KNOWLEDGE_ROOT) -> list[ExperienceHighlight]:
    indexes = profile.get("indexes", {})
    experience_ids = indexes.get("experiences") or []
    highlights: list[ExperienceHighlight] = []

    for exp_id in experience_ids:
        exp_path = knowledge_root / "experiences" / f"{exp_id}.yaml"
        if not exp_path.is_file():
            continue
        data = yaml.safe_load(exp_path.read_text(encoding="utf-8")) or {}
        responsibilities = data.get("responsibilities") or []
        top_tasks = [str(item.get("text", "")).strip() for item in responsibilities[:3] if item.get("text")]
        highlights.append(
            ExperienceHighlight(
                company=str(data.get("company", "")),
                role=str(data.get("role", "")),
                period=_format_period(data.get("period")),
                location=str(data.get("location", "")),
                highlights=top_tasks,
            )
        )
    return highlights


def load_skill_groups(profile: dict, knowledge_root: Path = KNOWLEDGE_ROOT) -> list[SkillGroup]:
    indexes = profile.get("indexes", {})
    skills_index = indexes.get("skills") or {}
    technical_ids = skills_index.get("technical") or []
    soft_ids = skills_index.get("soft") or []

    technical_items = _load_yaml_items(knowledge_root / "skills" / "technical.yaml")
    soft_items = _load_yaml_items(knowledge_root / "skills" / "soft.yaml")

    def _names(skill_ids: list[str], catalog: dict[str, dict]) -> list[str]:
        names: list[str] = []
        for skill_id in skill_ids:
            item = catalog.get(skill_id)
            if item and item.get("name"):
                names.append(str(item["name"]))
        return names

    groups: list[SkillGroup] = []
    domain_names = _names(technical_ids, technical_items)
    if domain_names:
        groups.append(SkillGroup(title="Fachkompetenzen", items=domain_names[:16]))
    soft_names = _names(soft_ids, soft_items)
    if soft_names:
        groups.append(SkillGroup(title="Soft Skills", items=soft_names))
    tech_focus = [
        name
        for name in _names(technical_ids, technical_items)
        if name
        in {
            "Python",
            "PowerShell",
            "OpenClaw",
            "Ollama",
            "Telegram Bot",
            "Prompt Engineering",
            "Workflow Automation",
            "AI Orchestration",
            "Plugin Development",
            "Git",
            "Playwright",
        }
    ]
    if tech_focus:
        groups.append(SkillGroup(title="KI & Automatisierung", items=tech_focus))
    return groups


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
        folder_name = str(data.get("folder_name") or folder.name)
        slug = application_slug(folder_name)
        entries.append(
            ApplicationEntry(
                company=str(data.get("company", folder.name)),
                job_title=str(data.get("job_title") or data.get("position", "")),
                folder_name=folder_name,
                folder_path=folder,
                approved_at=str(data.get("approved_at", "")),
                slug=slug,
                url=build_application_url(
                    folder_name,
                    base_url=config.base_url,
                    applications_path=config.qr_landing_path,
                ),
                cover_letter_text=extract_cover_letter_text(cover_path),
            )
        )
    entries.sort(key=lambda item: item.approved_at or item.company, reverse=True)
    return entries


def _render_nav(*, back_href: str | None = None, current: str = "") -> str:
    home = "/bewerbung/"
    links = [f'<a href="{home}"{" class=\"active\"" if current == "home" else ""}>Profil</a>']
    if back_href and back_href != home:
        links.append(f'<a href="{back_href}">Zurück</a>')
    return f'<nav class="site-nav">{" · ".join(links)}</nav>'


def _render_skill_groups(groups: list[SkillGroup]) -> str:
    if not groups:
        return ""
    blocks: list[str] = []
    for group in groups:
        chips = "".join(f'<span class="chip">{escape(name)}</span>' for name in group.items)
        blocks.append(
            f'      <div class="skill-group">\n'
            f"        <h3>{escape(group.title)}</h3>\n"
            f'        <div class="chips">{chips}</div>\n'
            f"      </div>"
        )
    return (
        "    <section>\n"
        "      <h2>Kompetenzen</h2>\n"
        f"{chr(10).join(blocks)}\n"
        "    </section>"
    )


def _render_experiences(experiences: list[ExperienceHighlight]) -> str:
    if not experiences:
        return ""
    items: list[str] = []
    for exp in experiences:
        meta_parts = [part for part in [exp.period, exp.location] if part]
        meta = " · ".join(meta_parts)
        highlights = "".join(f"<li>{escape(text)}</li>" for text in exp.highlights)
        items.append(
            "      <article class=\"experience-card\">\n"
            f"        <h3>{escape(exp.company)}</h3>\n"
            f"        <p class=\"role\">{escape(exp.role)}</p>\n"
            f"        <p class=\"meta\">{escape(meta)}</p>\n"
            f"        <ul>{highlights}</ul>\n"
            "      </article>"
        )
    return (
        "    <section>\n"
        "      <h2>Berufserfahrung</h2>\n"
        f"{chr(10).join(items)}\n"
        "    </section>"
    )


def _render_downloads(documents: list[tuple[str, str]]) -> str:
    doc_items = "\n".join(
        f'        <li><a href="{escape(href)}" download>{escape(label)}</a></li>'
        for label, href in documents
    )
    return (
        "    <section>\n"
        "      <h2>Unterlagen</h2>\n"
        f"      <ul class=\"downloads\">\n{doc_items}\n      </ul>\n"
        "    </section>"
    )


def _render_application_list(applications: list[ApplicationEntry]) -> str:
    if not applications:
        return ""
    app_items = "\n".join(
        "        <li>"
        f'<a href="{escape(entry.url)}/"><strong>{escape(entry.company)}</strong></a>'
        f" — {escape(entry.job_title)}"
        "</li>"
        for entry in applications
    )
    return (
        "    <section>\n"
        "      <h2>Aktuelle Bewerbungen</h2>\n"
        f"      <ul class=\"application-list\">\n{app_items}\n      </ul>\n"
        "    </section>"
    )


def render_landing_page(
    *,
    title: str,
    person: dict,
    documents: list[tuple[str, str]],
    applications: list[ApplicationEntry],
    experiences: list[ExperienceHighlight],
    skill_groups: list[SkillGroup],
    qr_url: str,
) -> str:
    name = escape(str(person.get("name", "Bewerbungsprofil")))
    headline = escape(str(person.get("title", "")))
    summary = escape(str(person.get("summary", "")).strip())

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="Bewerbungsprofil — {name}">
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <main class="container">
    {_render_nav(current="home")}
    <header class="hero">
      <p class="eyebrow">Bewerbungsprofil</p>
      <h1>{name}</h1>
      <p class="headline">{headline}</p>
    </header>
    <section>
      <h2>Profil</h2>
      <p class="summary">{summary}</p>
    </section>
{_render_experiences(experiences)}
{_render_skill_groups(skill_groups)}
{_render_downloads(documents)}
{_render_application_list(applications)}
    <footer>
      <p>Bewerbungsprofil unter <a href="{escape(qr_url)}">{escape(qr_url)}</a></p>
    </footer>
  </main>
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

    approved_line = f"<p class=\"meta\">Freigegeben am {escape(approved)}</p>" if approved else ""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{company} — {name}</title>
  <meta name="description" content="Bewerbung als {job_title} bei {company}">
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <main class="container">
    {_render_nav(back_href="/bewerbung/")}
    <header>
      <p class="eyebrow">Bewerbung</p>
      <h1>{company}</h1>
      <p class="headline">{job_title}</p>
      {approved_line}
    </header>
    <section class="letter">
      <h2>Anschreiben</h2>
      <div class="letter-body">
{letter_html}
      </div>
    </section>
    <section>
      <h2>Downloads</h2>
      <ul class="downloads">
{doc_items}
      </ul>
    </section>
    <footer>
      <p><a href="/bewerbung/">Zurück zum Bewerbungsprofil</a></p>
    </footer>
  </main>
</body>
</html>
"""


def _write_css(output_dir: Path) -> None:
    css = """
:root {
  color-scheme: light dark;
  --bg: #f4f6fb;
  --card: #ffffff;
  --text: #152033;
  --muted: #5c667a;
  --accent: #0b2d6b;
  --accent-soft: #e8eef9;
  --border: #d5ddea;
  --chip-bg: #edf2fb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e1420;
    --card: #171f2f;
    --text: #edf2ff;
    --muted: #a4afc4;
    --accent: #8eb4ff;
    --accent-soft: #1f2a40;
    --border: #2a354c;
    --chip-bg: #24304a;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  font-size: 1rem;
}
.container {
  max-width: 760px;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}
header, section, footer, article.experience-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
}
.hero { border-left: 4px solid var(--accent); }
.site-nav {
  margin-bottom: 1rem;
  font-size: 0.95rem;
}
.site-nav a {
  color: var(--accent);
  text-decoration: none;
  font-weight: 600;
}
.site-nav a.active { text-decoration: underline; }
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.75rem;
  color: var(--muted);
  margin: 0 0 0.35rem;
}
h1 { margin: 0.1rem 0 0.4rem; font-size: clamp(1.6rem, 4vw, 2.1rem); line-height: 1.2; }
h2 { margin-top: 0; font-size: 1.15rem; color: var(--accent); }
h3 { margin: 0 0 0.35rem; font-size: 1.05rem; }
.headline { color: var(--accent); margin: 0.2rem 0 0; font-weight: 600; }
.summary, .letter-body { white-space: pre-wrap; }
.role { margin: 0.15rem 0; font-weight: 600; }
.meta { color: var(--muted); font-size: 0.92rem; margin: 0.2rem 0 0.6rem; }
.muted { color: var(--muted); }
.downloads, ul, .application-list { padding-left: 1.2rem; margin: 0.4rem 0 0; }
.application-list a { font-weight: 600; }
a { color: var(--accent); }
a:hover { text-decoration: underline; }
.skill-group { margin-bottom: 0.9rem; }
.skill-group h3 { font-size: 0.95rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
.chips { display: flex; flex-wrap: wrap; gap: 0.45rem; }
.chip {
  display: inline-block;
  background: var(--chip-bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.2rem 0.7rem;
  font-size: 0.88rem;
}
.experience-card ul { margin-top: 0.4rem; }
.letter-body p { margin: 0 0 0.85rem; }
footer { font-size: 0.9rem; color: var(--muted); }
@media (max-width: 600px) {
  .container { padding: 1rem 0.75rem 2.5rem; }
  header, section, footer, article.experience-card { padding: 1rem 1.1rem; }
}
@media print {
  body { background: #fff; color: #000; font-size: 11pt; }
  .site-nav, footer { display: none; }
  .container { max-width: none; padding: 0; }
  header, section, article.experience-card {
    background: transparent;
    border: none;
    box-shadow: none;
    padding: 0 0 1rem;
    page-break-inside: avoid;
  }
  a { color: #000; text-decoration: none; }
  .chip { border-color: #ccc; background: #f5f5f5; }
  h2 { color: #000; }
}
"""
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "site.css").write_text(css.strip() + "\n", encoding="utf-8")


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
    experiences = load_experience_highlights(profile)
    skill_groups = load_skill_groups(profile)
    docs = collect_reference_documents()

    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    document_links: list[tuple[str, str]] = []
    for label, source, asset_name in docs:
        target = assets_dir / asset_name
        shutil.copy2(source, target)
        document_links.append((label, f"/assets/{asset_name}"))

    applications = collect_applications(config)
    for entry in applications:
        entry.cover_letter_download = _copy_application_assets(entry, output_dir)

    qr_url = build_qr_url(base_url=config.base_url, landing_path=config.qr_landing_path)

    landing_html = render_landing_page(
        title=f"{person.get('name', 'Bewerbung')} — {config.domain}",
        person=person,
        documents=document_links,
        applications=applications,
        experiences=experiences,
        skill_groups=skill_groups,
        qr_url=qr_url,
    )

    landing_dir = output_dir / config.qr_landing_path.strip("/")
    landing_dir.mkdir(parents=True, exist_ok=True)
    (landing_dir / "index.html").write_text(landing_html, encoding="utf-8")

    for entry in applications:
        app_dir = landing_dir / entry.slug
        app_dir.mkdir(parents=True, exist_ok=True)
        app_html = render_application_page(
            entry=entry,
            person=person,
            documents=document_links,
            cover_letter_text=entry.cover_letter_text,
        )
        (app_dir / "index.html").write_text(app_html, encoding="utf-8")

    redirect_path = config.qr_landing_path.strip("/")
    root_html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url=/{redirect_path}/">
  <title>Weiterleitung …</title>
</head>
<body>
  <p><a href="/{redirect_path}/">Zum Bewerbungsprofil</a></p>
</body>
</html>
"""
    (output_dir / "index.html").write_text(root_html, encoding="utf-8")
    _write_css(output_dir)

    manifest = {
        "exported_at": datetime.now().astimezone().isoformat(),
        "domain": config.domain,
        "qr_url": qr_url,
        "phase": "2",
        "applications": [
            {
                "company": entry.company,
                "job_title": entry.job_title,
                "slug": entry.slug,
                "url": entry.url,
                "approved_at": entry.approved_at,
                "has_cover_letter_text": bool(entry.cover_letter_text),
            }
            for entry in applications
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
    print(f"QR-URL: {build_qr_url(base_url=config.base_url, landing_path=config.qr_landing_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
