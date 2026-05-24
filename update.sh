#!/bin/bash
set -e

echo "🚀 Starte App- und Datenbank-Update..."

# 1. Pull the latest code from git
echo "📥 Lade neueste Code-Änderungen von Git..."
git pull

# 2. Update Python dependencies (in venv / .venv)
VENV_DIR=""
if [ -d ".venv" ]; then
    VENV_DIR=".venv"
elif [ -d "venv" ]; then
    VENV_DIR="venv"
fi

if [ -n "$VENV_DIR" ]; then
    echo "📦 Aktualisiere Python-Abhängigkeiten im $VENV_DIR..."
    $VENV_DIR/bin/pip install -r requirements.txt
else
    echo "⚠️ Kein venv oder .venv gefunden. Überspringe pip install. Falls nötig, installiere manuell."
fi

# 3. Run database migrations
echo "🗄️ Führe Datenbank-Migrationen aus..."
if [ -n "$VENV_DIR" ]; then
    $VENV_DIR/bin/python3 update_db.py
else
    python3 update_db.py
fi

# 4. Check if Docker is being used and running
if command -v docker &> /dev/null && docker info &> /dev/null; then
    # Check if we have docker-compose setup
    if [ -f "docker-compose.yml" ]; then
        if docker compose version &> /dev/null; then
            DOCKER_CMD="docker compose"
        else
            DOCKER_CMD="docker-compose"
        fi
        echo "🐳 Docker-Umgebung erkannt. Starte Container neu und baue neu mit $DOCKER_CMD..."
        $DOCKER_CMD down
        $DOCKER_CMD up --build -d
        echo "✅ Docker-Container erfolgreich aktualisiert und gestartet!"
    fi
else
    echo "ℹ️ Docker läuft nicht oder ist nicht installiert. Bitte starte deine App manuell neu (z.B. python app.py)."
fi

echo "🎉 Update erfolgreich abgeschlossen!"
