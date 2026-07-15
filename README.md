# tagcore.de — statische Bewerbungsseite

Phase-2-Export für QR-gestützte Bewerbungsunterlagen: Profil, Kompetenzen, Berufserfahrung und Detailseiten pro freigegebener Bewerbung. Erzeugt `dist/` zum Upload beim Hoster.

## Schnellstart

```powershell
cd K:\AI\Projects\techcore-site
python scripts\export_site.py
```

Ausgabe: `dist/` mit `bewerbung/index.html`, Unterlagen unter `assets/` und `manifest.json`.

## QR-URL (Haupteinstieg)

```
https://tagcore.de/bewerbung
```

Telegram (bestehender QR-Skill):

```
qr: https://tagcore.de/bewerbung
```

## Seiten (Phase 2)

| Seite | URL |
|-------|-----|
| Root-Redirect | `https://tagcore.de/` → `/bewerbung/` |
| Bewerbungsprofil | `https://tagcore.de/bewerbung/` |
| Pro-Stelle | `https://tagcore.de/bewerbung/{slug}/` |

Beispiel Detailseite:

```
https://tagcore.de/bewerbung/leyton-deutschland-gmbh-inside-sales-representative-m_w_d/
```

## Deployment (Netlify)

1. Repository `Pfeffy1234/techcore-site` mit Netlify verbinden.
2. `netlify.toml` nutzt `publish = "dist"` und Build `python scripts/export_site.py`.
3. Domain `tagcore.de` als Custom Domain in Netlify hinterlegen (DNS beim Registrar).
4. QR-Code mit `https://tagcore.de/bewerbung` drucken.

Alternativ: `dist/` manuell per FTP/rsync hochladen.

## Konfiguration

`site.config.yaml` — Pfade zu Profil, Bewerbungsordnern und Referenzdokumenten.

## Tests

```powershell
cd K:\AI
python -m pytest Projects/techcore-site/tests -q
```

## OpenClaw-Neustart

**Nein** — separates statisches Projekt, kein OpenClaw-Plugin.
