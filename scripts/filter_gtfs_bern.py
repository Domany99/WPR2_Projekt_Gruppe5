#!/usr/bin/env python3
"""
GTFS Filter für Kanton Bern

Filtert die kompletten Schweizer GTFS-Daten auf die Region Bern.
Basierend auf Bounding Box Filterung.
"""

import zipfile
import csv
import shutil
from pathlib import Path
import sys

# UTF-8 Encoding für Windows Console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# Bern Region Bounding Box (erweitert für ganzen Kanton)
BERN_LAT_MIN = 46.40  # Süden (Thunersee, Gstaad)
BERN_LAT_MAX = 47.10  # Norden (Biel/Bienne)
BERN_LON_MIN = 7.00   # Westen (Jura-Region)
BERN_LON_MAX = 8.50   # Osten (Berner Oberland, Meiringen)


def is_in_bern_region(lat, lon):
    """Prüft ob Koordinaten in der Bern-Region liegen"""
    try:
        lat = float(lat)
        lon = float(lon)
        return (BERN_LAT_MIN <= lat <= BERN_LAT_MAX and
                BERN_LON_MIN <= lon <= BERN_LON_MAX)
    except (ValueError, TypeError):
        return False


def filter_gtfs_for_bern(input_zip, output_zip):
    """
    Filtert GTFS-Daten für die Region Bern

    Args:
        input_zip: Pfad zur kompletten GTFS-Datei
        output_zip: Pfad zur gefilterten GTFS-Datei
    """
    print(f"Lade GTFS-Daten von: {input_zip}")

    # Temporäres Verzeichnis für Extraktion
    script_dir = Path(__file__).parent
    temp_dir = script_dir / "temp_gtfs"
    temp_dir.mkdir(exist_ok=True)

    # Entpacke GTFS
    print("Extrahiere GTFS-Daten...")
    with zipfile.ZipFile(input_zip, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    print("Filtere Haltestellen in Bern-Region...")

    # 1. Filtere stops.txt - nur Haltestellen in Bern
    bern_stops = set()
    stops_in = temp_dir / "stops.txt"
    stops_out = temp_dir / "stops_filtered.txt"

    with open(stops_in, 'r', encoding='utf-8-sig') as f_in, \
         open(stops_out, 'w', encoding='utf-8', newline='') as f_out:

        reader = csv.DictReader(f_in)
        fieldnames = [f.strip() for f in reader.fieldnames]  # Entferne Whitespace
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            # Entferne Whitespace von Keys
            row = {k.strip(): v for k, v in row.items()}
            if is_in_bern_region(row.get('stop_lat', ''), row.get('stop_lon', '')):
                stop_id = row.get('stop_id', '')
                if stop_id:
                    bern_stops.add(stop_id)
                    writer.writerow(row)

    print(f"  -> Gefunden: {len(bern_stops)} Haltestellen in Bern-Region")

    # 2. Filtere stop_times.txt - nur Fahrten mit Bern-Haltestellen
    bern_trips = set()
    stop_times_in = temp_dir / "stop_times.txt"
    stop_times_out = temp_dir / "stop_times_filtered.txt"

    print("Filtere Fahrzeiten...")
    with open(stop_times_in, 'r', encoding='utf-8-sig') as f_in, \
         open(stop_times_out, 'w', encoding='utf-8', newline='') as f_out:

        reader = csv.DictReader(f_in)
        fieldnames = [f.strip() for f in reader.fieldnames]
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            row = {k.strip(): v for k, v in row.items()}
            if row.get('stop_id', '') in bern_stops:
                trip_id = row.get('trip_id', '')
                if trip_id:
                    bern_trips.add(trip_id)
                    writer.writerow(row)

    print(f"  -> Gefunden: {len(bern_trips)} relevante Fahrten")

    # 3. Filtere trips.txt
    bern_routes = set()
    bern_services = set()
    trips_in = temp_dir / "trips.txt"
    trips_out = temp_dir / "trips_filtered.txt"

    print("Filtere Fahrten...")
    with open(trips_in, 'r', encoding='utf-8-sig') as f_in, \
         open(trips_out, 'w', encoding='utf-8', newline='') as f_out:

        reader = csv.DictReader(f_in)
        fieldnames = [f.strip() for f in reader.fieldnames]
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            row = {k.strip(): v for k, v in row.items()}
            if row.get('trip_id', '') in bern_trips:
                route_id = row.get('route_id', '')
                service_id = row.get('service_id', '')
                if route_id:
                    bern_routes.add(route_id)
                if service_id:
                    bern_services.add(service_id)
                writer.writerow(row)

    print(f"  -> Gefunden: {len(bern_routes)} Routen")

    # 4. Filtere routes.txt
    routes_in = temp_dir / "routes.txt"
    routes_out = temp_dir / "routes_filtered.txt"

    print("Filtere Routen...")
    with open(routes_in, 'r', encoding='utf-8-sig') as f_in, \
         open(routes_out, 'w', encoding='utf-8', newline='') as f_out:

        reader = csv.DictReader(f_in)
        fieldnames = [f.strip() for f in reader.fieldnames]
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            row = {k.strip(): v for k, v in row.items()}
            if row.get('route_id', '') in bern_routes:
                writer.writerow(row)

    # 5. Filtere calendar.txt und calendar_dates.txt (nur relevante Services)
    calendar_files = [
        ('calendar.txt', 'calendar_filtered.txt'),
        ('calendar_dates.txt', 'calendar_dates_filtered.txt')
    ]

    for in_name, out_name in calendar_files:
        in_file = temp_dir / in_name
        out_file = temp_dir / out_name

        if in_file.exists():
            print(f"Filtere {in_name}...")
            with open(in_file, 'r', encoding='utf-8-sig') as f_in, \
                 open(out_file, 'w', encoding='utf-8', newline='') as f_out:

                reader = csv.DictReader(f_in)
                fieldnames = [f.strip() for f in reader.fieldnames]
                writer = csv.DictWriter(f_out, fieldnames=fieldnames)
                writer.writeheader()

                for row in reader:
                    row = {k.strip(): v for k, v in row.items()}
                    if row.get('service_id', '') in bern_services:
                        writer.writerow(row)

    # 6. Kopiere agency.txt unverändert
    agency_in = temp_dir / "agency.txt"
    agency_out = temp_dir / "agency_filtered.txt"

    if agency_in.exists():
        print("Kopiere agency.txt...")
        shutil.copy2(agency_in, agency_out)

    # 7. Erstelle gefilterte ZIP-Datei
    print(f"\nErstelle gefilterte GTFS-Datei: {output_zip}")
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filename in temp_dir.glob("*_filtered.txt"):
            arcname = filename.name.replace('_filtered', '')
            zipf.write(filename, arcname)
            print(f"  -> Hinzugefuegt: {arcname}")

    # Cleanup
    print("Raeume temporaere Dateien auf...")
    shutil.rmtree(temp_dir)

    print("\n" + "="*60)
    print("FERTIG! Gefilterte GTFS-Daten gespeichert.")
    print("="*60)
    print(f"Statistik:")
    print(f"  - {len(bern_stops):,} Haltestellen")
    print(f"  - {len(bern_trips):,} Fahrten")
    print(f"  - {len(bern_routes):,} Routen")
    print(f"  - {len(bern_services):,} Service-Kalender")
    print(f"\nOutput: {output_zip}")


if __name__ == "__main__":
    # Pfade relativ zum Projekt-Root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    input_file = project_root / "otp/graphs/bern/gtfs_fp2025_20251101.zip"
    output_file = project_root / "otp/graphs/bern/gtfs_bern_filtered.zip"

    # Prüfen ob Input-Datei existiert
    if not input_file.exists():
        print(f"FEHLER: Input-Datei nicht gefunden!")
        print(f"Erwartet: {input_file}")
        print(f"\nBitte stelle sicher, dass die GTFS-Datei hier liegt.")
        exit(1)

    print("="*60)
    print("GTFS-Filter fuer Kanton Bern")
    print("="*60)
    print(f"Input:  {input_file.name}")
    print(f"Output: {output_file.name}")
    print(f"Region: Lat {BERN_LAT_MIN}-{BERN_LAT_MAX}, Lon {BERN_LON_MIN}-{BERN_LON_MAX}")
    print("="*60 + "\n")

    filter_gtfs_for_bern(str(input_file), str(output_file))

    print("\n" + "="*60)
    print("NAECHSTE SCHRITTE:")
    print("="*60)
    print("1. Original-GTFS sichern (optional):")
    print("   move otp\\graphs\\bern\\gtfs_fp2025_20251101.zip otp\\graphs\\bern\\gtfs_full_backup.zip")
    print("\n2. Gefilterte Datei verwenden:")
    print("   move otp\\graphs\\bern\\gtfs_bern_filtered.zip otp\\graphs\\bern\\gtfs_fp2025_20251101.zip")
    print("\n3. OTP neu starten:")
    print("   docker-compose down")
    print("   docker-compose up --build")
    print("="*60)

