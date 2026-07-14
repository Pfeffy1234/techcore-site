"""Statischen Export für tagcore.de erzeugen (Profil + Unterlagen + Bewerbungsliste)."""

from __future__ import annotations

import json
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
    application_slug,
    build_application_url,
    build_qr_url,
    qr_url_template,
)

CONFIG_FILE = PROJECT_ROOT / "site.config.yaml"


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


@dataclass(frozen=True)
class ApplicationEntry:
    company: str
    job_title: str
    folder_name: str
    approved_at: str
    slug: str
    future_url: str


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
        profile_yaml=_resolve_path(str(raw.get("profile_yaml", "../BewerbungsAgent/knowledge/profile.yaml")), base=PROJECT_ROOT),
        applications_base=_resolve_path(str(raw.get("applications_base", "K:/AI/Bewerbungen 2026")), base=PROJECT_ROOT),
        reference_base=_resolve_path(str(raw.get("reference_base", "K:/AI/application documents")), base=PROJECT_ROOT),
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


def _asset_name(source: Path) -> str:
    mapping = {
        "lebenslauf 2026.docx": "lebenslauf-2026.docx",
        "atzinger zeugnis.jpg": "atzinger-zeugnis.jpg",
        "tibas arbeitszeugnis.jpeg": "tibas-arbeitszeugnis.jpeg",
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
        if not (folder / "Anschreiben.docx").is_file():
            continue
        folder_name = str(data.get("folder_name") or folder.name)
        slug = application_slug(folder_name)
        entries.append(
            ApplicationEntry(
                company=str(data.get("company", folder.name)),
                job_title=str(data.get("job_title") or data.get("position", "")),
                folder_name=folder_name,
                approved_at=str(data.get("approved_at", "")),
                slug=slug,
                future_url=build_application_url(
                    folder_name,
                    base_url=config.base_url,
                    applications_path=config.qr_landing_path,
                ),
            )
        )
    entries.sort(key=lambda item: item.approved_at or item.company, reverse=True)
    return entries


def _render_page(
    *,
    title: str,
    person: dict,
    documents: list[tuple[str, str]],
    applications: list[ApplicationEntry],
    qr_url: str,
    phase2_template: str,
) -> str:
    name = escape(str(person.get("name", "Bewerbungsprofil")))
    headline = escape(str(person.get("title", "")))
    summary = escape(str(person.get("summary", "")).strip())

    doc_items = "\n".join(
        f'        <li><a href="{escape(href)}" download>{escape(label)}</a></li>'
        for label, href in documents
    )
    app_items = "\n".join(
        "        <li>"
        f"<strong>{escape(entry.company)}</strong>"
        f" — {escape(entry.job_title)}"
        f'<br><small>Phase 2: <code>{escape(entry.future_url)}</code></small>'
        "</li>"
        for entry in applications
    )
    apps_block = (
        f"<section>\n      <h2>Aktuelle Bewerbungen</h2>\n      <ul>\n{app_items}\n      </ul>\n    </section>"
        if applications
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="Bewerbungsprofil — {name}">
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <main class="container">
    <header>
      <p class="eyebrow">Bewerbungsprofil</p>
      <h1>{name}</h1>
      <p class="headline">{headline}</p>
    </header>
    <section>
      <h2>Profil</h2>
      <p class="summary">{summary}</p>
    </section>
    <section>
      <h2>Unterlagen</h2>
      <ul class="downloads">
{doc_items}
      </ul>
    </section>
{apps_block}
    <footer>
      <p>QR-Ziel (Phase 1): <code>{escape(qr_url)}</code></p>
      <p>Pro-Stelle (Phase 2): <code>{escape(phase2_template)}</code></p>
    </footer>
  </main>
</body>
</html>
"""


def _write_css(output_dir: Path) -> None:
    css = """
:root {
  color-scheme: light dark;
  --bg: #f7f8fb;
  --card: #ffffff;
  --text: #1a1f2e;
  --muted: #5b6475;
  --accent: #0c2577;
  --border: #d8dee9;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f141f;
    --card: #171d2b;
    --text: #eef2ff;
    --muted: #a6b0c3;
    --accent: #7aa2ff;
    --border: #2a3347;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
}
.container {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1.25rem 3rem;
}
header, section, footer {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
}
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.75rem;
  color: var(--muted);
  margin: 0 0 0.35rem;
}
.headline { color: var(--accent); margin-top: 0.25rem; }
.summary { white-space: pre-wrap; }
.downloads, ul { padding-left: 1.2rem; }
a { color: var(--accent); }
code { font-size: 0.85em; word-break: break-all; }
footer { font-size: 0.9rem; color: var(--muted); }
"""
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "site.css").write_text(css.strip() + "\n", encoding="utf-8")


def export_site(config: SiteConfig | None = None) -> Path:
    config = config or load_site_config()
    output_dir = config.output_dir
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    profile = load_profile(config.profile_yaml)
    person = profile.get("person", {})
    docs = collect_reference_documents()

    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    document_links: list[tuple[str, str]] = []
    for label, source, asset_name in docs:
        target = assets_dir / asset_name
        shutil.copy2(source, target)
        document_links.append((label, f"/assets/{asset_name}"))

    applications = collect_applications(config)
    qr_url = build_qr_url(base_url=config.base_url, landing_path=config.qr_landing_path)
    phase2_template = qr_url_template(base_url=config.base_url, landing_path=config.qr_landing_path)

    html = _render_page(
        title=f"{person.get('name', 'Bewerbung')} — {config.domain}",
        person=person,
        documents=document_links,
        applications=applications,
        qr_url=qr_url,
        phase2_template=phase2_template,
    )

    landing_dir = output_dir / config.qr_landing_path.strip("/")
    landing_dir.mkdir(parents=True, exist_ok=True)
    (landing_dir / "index.html").write_text(html, encoding="utf-8")

    # Root-Redirect auf QR-Landing
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
        "phase2_url_template": phase2_template,
        "applications": [
            {
                "company": entry.company,
                "job_title": entry.job_title,
                "slug": entry.slug,
                "url": entry.future_url,
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
