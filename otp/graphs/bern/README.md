# OTP Daten-Download

Diese Dateien sind zu groß für Git und müssen separat heruntergeladen werden.

## Erforderliche Dateien

### 1. OSM-Daten (OpenStreetMap)
**Datei:** `switzerland-251104.osm.pbf`  
**Größe:** ~300-400 MB  
**Download:** https://download.geofabrik.de/europe/switzerland.html

```bash
# Download mit wget
wget https://download.geofabrik.de/europe/switzerland-latest.osm.pbf -O otp/graphs/bern/switzerland-251104.osm.pbf

# Oder mit curl
curl -o otp/graphs/bern/switzerland-251104.osm.pbf https://download.geofabrik.de/europe/switzerland-latest.osm.pbf
```

### 2. GTFS-Daten (Öffentlicher Verkehr Schweiz)
**Datei:** `gtfs_fp2025_20251101.zip` (Original) oder `gtfs_bern_filtered.zip` (gefiltert)  
**Größe:** ~500 MB (Original) / ~300 MB (gefiltert)  
**Download:** https://opentransportdata.swiss/de/dataset/timetable-2024-gtfs2020

```bash
# Download komplette Schweiz GTFS
# Gehe zu: https://opentransportdata.swiss/de/dataset/timetable-2024-gtfs2020
# Lade die neueste GTFS-Datei herunter und benenne sie um zu:
# otp/graphs/bern/gtfs_fp2025_20251101.zip
```

### 3. Gefilterte GTFS-Daten erstellen (Optional)

Falls du nur die Region Bern brauchst, kannst du die GTFS-Daten filtern:

```bash
# Nach Download der kompletten GTFS-Datei:
cd scripts
python filter_gtfs_bern.py

# Dann gefilterte Datei verwenden:
swap_gtfs.bat  # Windows
# oder manuell:
copy otp\graphs\bern\gtfs_bern_filtered.zip otp\graphs\bern\gtfs_fp2025_20251101.zip
```

Siehe `GTFS_FILTER.md` für Details.

## Verzeichnisstruktur

Nach dem Download sollte die Struktur so aussehen:

```
otp/
└── graphs/
    └── bern/
        ├── gtfs_fp2025_20251101.zip       ← GTFS-Daten (Original oder gefiltert)
        └── switzerland-251104.osm.pbf     ← OSM-Daten
```

## Alternativen

### Nur Bern-Region OSM
Falls du nur Bern brauchst, kannst du auch kleinere OSM-Extracts verwenden:

```bash
# Kleinere Region (schnellerer Download, aber weniger Coverage)
wget https://download.geofabrik.de/europe/switzerland/bern-latest.osm.pbf -O otp/graphs/bern/switzerland-251104.osm.pbf
```

**Hinweis:** Die komplette Schweiz-Datei wird empfohlen für bessere Routing-Qualität.

## Nach dem Download

Starte OTP:

```bash
docker-compose up --build
```

Der Graph-Build dauert ca. 5-10 Minuten (mit gefilterten GTFS) oder 30+ Minuten (mit kompletten GTFS).

