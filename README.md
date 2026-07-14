# tagcore.de — statische Bewerbungsseite

Phase-1-Export für QR-gestützte Bewerbungsunterlagen. Erzeugt `dist/` zum Upload beim Hoster.

## Schnellstart

```powershell
cd K:\AI\Projects\techcore-site
python scripts\export_site.py
```

Ausgabe: `dist/` mit `bewerbung/index.html`, Unterlagen unter `assets/` und `manifest.json`.

## QR-URL (Phase 1)

```
https://tagcore.de/bewerbung
```

Telegram (bestehender QR-Skill):

```
qr: https://tagcore.de/bewerbung
```

## Pro-Stelle (Phase 2, noch nicht implementiert)

```
https://tagcore.de/bewerbung/{slug}
```

Beispiel:

```
https://tagcore.de/bewerbung/leyton-deutschland-gmbh-inside-sales-representative-m_w_d
```

## Deployment (manuell, Phase 1)

1. Domain `tagcore.de` beim Hoster auf statisches Hosting zeigen (z. B. Netlify, Cloudflare Pages, IONOS Webspace).
2. `dist/` per FTP, rsync oder Git-Deploy hochladen.
3. HTTPS aktivieren (Let's Encrypt / Hoster-Zertifikat).
4. QR-Code mit `https://tagcore.de/bewerbung` drucken.

## Konfiguration

`site.config.yaml` — Pfade zu Profil, Bewerbungsordnern und Referenzdokumenten.

## Tests

```powershell
cd K:\AI
python -m pytest Projects/techcore-site/tests -q
```

## OpenClaw-Neustart

**Nein** — separates statisches Projekt, kein OpenClaw-Plugin.
