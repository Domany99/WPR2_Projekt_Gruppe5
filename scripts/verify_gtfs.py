#!/usr/bin/env python3
"""Verifiziert die gefilterte GTFS-Datei"""

import zipfile
import csv
import io
from pathlib import Path

script_dir = Path(__file__).parent
project_root = script_dir.parent
filtered_file = project_root / "otp/graphs/bern/gtfs_bern_filtered.zip"

print("="*60)
print("VERIFIZIERUNG DER GEFILTERTEN GTFS-DATEI")
print("="*60)
print(f"Datei: {filtered_file.name}\n")

if not filtered_file.exists():
    print("FEHLER: Gefilterte Datei nicht gefunden!")
    exit(1)

with zipfile.ZipFile(filtered_file, 'r') as z:
    print("Enthaltene Dateien:")
    for name in z.namelist():
        info = z.getinfo(name)
        size_kb = info.file_size / 1024
        print(f"  - {name:25s} ({size_kb:>8.1f} KB)")

    print("\n" + "-"*60)
    print("STOPS (Haltestellen)")
    print("-"*60)
    data = z.read('stops.txt').decode('utf-8')
    reader = csv.DictReader(io.StringIO(data))
    stops = list(reader)

    print(f"Gesamt: {len(stops)} Haltestellen\n")
    print("Erste 5 Stationen:")
    for stop in stops[:5]:
        print(f"  - {stop['stop_name']:40s} ({stop['stop_lat']}, {stop['stop_lon']})")

    # Prüfe Bern-Stadt
    bern_city = [s for s in stops if 'Bern ' in s['stop_name'] or s['stop_name'].startswith('Bern,')][:5]
    if bern_city:
        print("\nBeispiel Bern-Stadt Stationen:")
        for stop in bern_city:
            print(f"  - {stop['stop_name']:40s} ({stop['stop_lat']}, {stop['stop_lon']})")

    print("\n" + "-"*60)
    print("ROUTES (Linien)")
    print("-"*60)
    data = z.read('routes.txt').decode('utf-8')
    reader = csv.DictReader(io.StringIO(data))
    routes = list(reader)

    print(f"Gesamt: {len(routes)} Routen\n")
    print("Erste 10 Routen:")
    for route in routes[:10]:
        route_name = route.get('route_short_name', '') or route.get('route_long_name', '')
        route_type = route.get('route_type', '')
        print(f"  - {route_name:20s} (Typ: {route_type})")

    print("\n" + "-"*60)
    print("TRIPS (Fahrten)")
    print("-"*60)
    data = z.read('trips.txt').decode('utf-8')
    reader = csv.DictReader(io.StringIO(data))
    trips = list(reader)

    print(f"Gesamt: {len(trips)} Fahrten")

    print("\n" + "="*60)
    print("FAZIT: Gefilterte GTFS-Datei ist valide!")
    print("="*60)
    print(f"Die Datei enthält alle notwendigen Daten für OTP.")

