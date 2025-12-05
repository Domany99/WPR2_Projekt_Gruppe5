# WPR2 Projekt Gruppe 5 - Multimodale Routenplanung

Eine multimodale Routenplanungs-Anwendung für die Region Bern, die öffentliche Verkehrsmittel, E-Scooter und PubliBike integriert.

## Voraussetzungen

Bevor Sie das Projekt starten können, stellen Sie sicher, dass folgende Software installiert ist:

- **Python 3.10+** - [Download](https://www.python.org/downloads/)
- **Docker Desktop für Windows** - [Download](https://www.docker.com/products/docker-desktop/)
- **Git** (optional, zum Klonen des Repositories)

## Installation & Start (Windows)

### 1. Repository klonen oder herunterladen / Zip verwenden

Da in GIT die OTP Daten nicht Integriert sind (Dateien sind zu gross), rate ich Ihnen das per Teams verwendete ZIP zu verwenden

```cmd
git clone https://github.com/Domany99/WPR2_Projekt_Gruppe5.git
cd WPR2_Projekt_Gruppe5
```

### 2. Python-Abhängigkeiten installieren

Öffnen Sie eine Eingabeaufforderung (CMD) im Projektverzeichnis und führen Sie aus:

```cmd
pip install -r requirements.txt
```

### 3. Docker Desktop starten

Stellen Sie sicher, dass Docker Desktop läuft (im System Tray sichtbar).

### 4. OpenTripPlanner (OTP) starten

Der OTP-Server wird über Docker gestartet:

```cmd
docker-compose up --build
```

⚠️ **Hinweis:** Das Starten des Dockers beanspucht mehere Minuten. Auf meinem Rechner mit 32 GB RAM und einer I7-12700K CPU dauert es ca. 7 Minuten bis der OTP Server bereit ist. Ich rate Ihnen den Docker nicht auf einem Laptop zu starten.

### 5. Flask-Anwendung starten

Wechseln Sie in das `scripts`-Verzeichnis und starten Sie die App:

```cmd
cd scripts
python app.py
```

### 6. Anwendung öffnen

Öffnen Sie Ihren Browser und navigieren Sie zu:

```
http://localhost:5000
```

## Dienste im Überblick

| Dienst | URL | Beschreibung |
|--------|-----|--------------|
| Flask-App | http://localhost:5000 | Web-Oberfläche |
| OTP-Server | http://localhost:8080 | OpenTripPlanner API |

## Projekt stoppen

```cmd
# Flask-App stoppen: Ctrl+C im Terminal

# Docker-Container stoppen:
docker-compose down
```


