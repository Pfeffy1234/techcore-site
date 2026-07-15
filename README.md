# TagCore — statische Bewerbungsseite (tagcore.de)

Statischer Export für QR-gestützte Bewerbungsunterlagen: schlanke Startseite mit Lebenslauf und Zeugnissen, plus Detailseiten pro freigegebener Bewerbung. Erzeugt `dist/` zum Upload beim Hoster.

**Marke:** TagCore (T-A-G-C-O-R-E)  
**Domain:** `tagcore.de` mit `https://www.tagcore.de` (in `site.config.yaml`). Das GitHub-Repository heißt intern `techcore-site`.

## Schnellstart

```powershell
cd K:\AI\Projects\techcore-site
python scripts\export_site.py
```

Ausgabe: `dist/` mit `index.html`, Firmenseiten unter `/{slug}/`, Unterlagen unter `assets/` und `manifest.json`.

## URL-Struktur

| Seite | URL | Inhalt |
|-------|-----|--------|
| Startseite | `https://www.tagcore.de/` | Name, Kurzzeile, 3 Downloads (Lebenslauf, Atzinger, Tibas) |
| Pro Bewerbung | `https://www.tagcore.de/{slug}/` | Anschreiben + Downloads für diese Firma |

Beispiele:

```
https://www.tagcore.de/
https://www.tagcore.de/leyton-deutschland-gmbh/
https://www.tagcore.de/cyqueo-gmbh/
```

Der Slug wird aus dem **Firmennamen** erzeugt (nicht aus dem Ordnernamen mit Stellentitel).

## QR-Codes

| Zweck | URL |
|-------|-----|
| Allgemeine Unterlagen (Lebenslauf + Zeugnisse) | `https://www.tagcore.de/` |
| Konkrete Bewerbung | `https://www.tagcore.de/{slug}/` |

Telegram (bestehender QR-Skill):

```
qr: https://www.tagcore.de/
qr: https://www.tagcore.de/leyton-deutschland-gmbh/
```

## Lokale Vorschau (vor Netlify/DNS)

Nach dem Export:

```powershell
cd K:\AI\Projects\techcore-site
py -m http.server 8080 --directory dist
```

Oder:

```powershell
scripts\preview.cmd
```

Dann im Browser öffnen: **http://localhost:8080**

So können Startseite und Firmenseiten lokal geprüft werden, bevor die Domain live ist.

## Deployment (Netlify)

1. Repository `Pfeffy1234/techcore-site` mit Netlify verbinden.
2. `netlify.toml` nutzt `publish = "dist"` und Build `python scripts/export_site.py`.
3. Domain `tagcore.de` (mit `www`) als Custom Domain in Netlify hinterlegen.
4. QR-Codes mit den URLs oben drucken.

Alternativ: `dist/` manuell per FTP/rsync hochladen.

## Konfiguration

`site.config.yaml` — Markenname, Domain, Pfade zu Profil, Bewerbungsordnern und Referenzdokumenten.

Freigegebene Bewerbungen: Ordner unter `K:\AI\Bewerbungen 2026\` mit gesetztem `approved_at` in `metadata.json`.

## Tests

```powershell
cd K:\AI
python -m pytest Projects/techcore-site/tests -q
```

## OpenClaw-Neustart

**Nein** — separates statisches Projekt, kein OpenClaw-Plugin.
