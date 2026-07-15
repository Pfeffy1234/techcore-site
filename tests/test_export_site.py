"""Tests für techcore-site URL-Hilfen und Export."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
KNOWLEDGE_ROOT = PROJECT_ROOT.parent / "BewerbungsAgent" / "knowledge"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


urls = _load_module("techcore_urls", SCRIPTS / "urls.py")


@pytest.mark.parametrize(
    "folder_name, expected",
    [
        (
            "Leyton Deutschland GmbH - Inside Sales Representative (m_w_d)",
            "leyton-deutschland-gmbh-inside-sales-representative-m_w_d",
        ),
        ("Firma / Test: Sonderzeichen!!!", "firma-test-sonderzeichen"),
        ("   ", "bewerbung"),
    ],
)
def test_application_slug(folder_name: str, expected: str) -> None:
    assert urls.application_slug(folder_name) == expected


def test_build_qr_url() -> None:
    assert urls.build_qr_url() == "https://tagcore.de/bewerbung"


def test_build_application_url() -> None:
    url = urls.build_application_url("Leyton Deutschland GmbH - Inside Sales Representative (m_w_d)")
    assert url == "https://tagcore.de/bewerbung/leyton-deutschland-gmbh-inside-sales-representative-m_w_d"


def _write_minimal_cover_letter_docx(path: Path) -> None:
    from docx import Document

    document = Document()
    document.add_paragraph("Florian Pfisterhammer")
    document.add_paragraph("Sehr geehrte Damen und Herren,")
    document.add_paragraph("mit großem Interesse bewerbe ich mich auf die ausgeschriebene Stelle.")
    document.add_paragraph("Mit freundlichen Grüßen")
    document.add_paragraph("Florian Pfisterhammer")
    document.save(path)


def test_export_site_minimal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        yaml.safe_dump(
            {
                "person": {
                    "name": "Test User",
                    "title": "Test Title",
                    "summary": "Kurzprofil.",
                },
                "indexes": {
                    "experiences": ["exp-tibas"],
                    "skills": {
                        "technical": ["skill-vertrieb", "skill-b2b"],
                        "soft": ["soft-organisation"],
                    },
                },
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    apps_base = tmp_path / "apps"
    app_dir = apps_base / "Firma A - Job B"
    app_dir.mkdir(parents=True)
    _write_minimal_cover_letter_docx(app_dir / "Anschreiben.docx")
    (app_dir / "metadata.json").write_text(
        json.dumps(
            {
                "company": "Firma A",
                "job_title": "Job B",
                "folder_name": app_dir.name,
                "approved_at": "2026-07-13T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    ref_base = tmp_path / "refs"
    ref_base.mkdir()
    (ref_base / "Lebenslauf 2026.docx").write_bytes(b"cv")

    config_path = tmp_path / "site.config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "domain": "tagcore.de",
                "base_url": "https://tagcore.de",
                "qr_landing_path": "/bewerbung",
                "profile_yaml": str(profile_path),
                "applications_base": str(apps_base),
                "reference_base": str(ref_base),
                "require_approved": True,
                "output_dir": str(tmp_path / "dist"),
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    export_site = _load_module("techcore_export_site", SCRIPTS / "export_site.py")

    monkeypatch.setattr(
        export_site,
        "resolve_standard_application_attachments",
        lambda: {"cv": ref_base / "Lebenslauf 2026.docx"},
    )
    monkeypatch.setattr(export_site, "KNOWLEDGE_ROOT", KNOWLEDGE_ROOT)

    out = export_site.export_site(export_site.load_site_config(config_path))
    assert (out / "bewerbung" / "index.html").is_file()
    assert (out / "index.html").is_file()
    assert (out / "assets" / "site.css").is_file()
    assert (out / "manifest.json").is_file()

    landing_html = (out / "bewerbung" / "index.html").read_text(encoding="utf-8")
    assert "Test User" in landing_html
    assert "Firma A" in landing_html
    assert "Lebenslauf 2026" in landing_html
    assert "Kompetenzen" in landing_html
    assert "Berufserfahrung" in landing_html
    assert "href=\"https://tagcore.de/bewerbung/firma-a-job-b/\"" in landing_html

    app_page = out / "bewerbung" / "firma-a-job-b" / "index.html"
    assert app_page.is_file()
    app_html = app_page.read_text(encoding="utf-8")
    assert "Firma A" in app_html
    assert "Job B" in app_html
    assert "Sehr geehrte Damen und Herren" in app_html
    assert (out / "assets" / "applications" / "firma-a-job-b" / "anschreiben.docx").is_file()

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["qr_url"] == "https://tagcore.de/bewerbung"
    assert manifest["phase"] == "2"
    assert manifest["applications"][0]["has_cover_letter_text"] is True
