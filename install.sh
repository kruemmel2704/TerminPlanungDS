#!/bin/bash
set -e

echo "Starting installation script for Debian/Ubuntu..."

# Check if script is run as root
if [ "$(id -u)" != "0" ]; then
    echo "This script needs to be run as root. Please switch to root (e.g. 'su -') or run with sudo."
    exit 1
fi

echo "Updating package list..."
apt-get update -y

echo "Installing essential dependencies (sudo, curl, wget, git, python3, pip, venv)..."
apt-get install -y sudo curl wget git python3 python3-pip python3-venv

if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    
    echo "Installing Docker Compose plugin..."
    apt-get install -y docker-compose-plugin
else
    echo "Docker is already installed."
fi

echo "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "Installing Python dependencies..."
.venv/bin/pip install -r requirements.txt

if [ ! -f ".env" ]; then
    echo ""
    echo "======================================"
    echo "Konfiguration der .env Datei"
    echo "Eingabetaste (Enter) drücken, um den Standardwert zu nutzen."
    echo "======================================"
    
    # Generate a default secret key
    DEFAULT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(24))' 2>/dev/null || echo "your_secret_key_here")
    
    read -p "FLASK_ENV [development]: " FLASK_ENV
    FLASK_ENV=${FLASK_ENV:-development}
    
    read -p "SECRET_KEY [$DEFAULT_SECRET]: " SECRET_KEY
    SECRET_KEY=${SECRET_KEY:-$DEFAULT_SECRET}
    
    read -p "DATABASE_URL [sqlite:///database.db]: " DATABASE_URL
    DATABASE_URL=${DATABASE_URL:-sqlite:///database.db}
    
    echo ""
    echo "--- Discord Settings ---"
    read -p "DISCORD_CLIENT_ID: " DISCORD_CLIENT_ID
    read -p "DISCORD_CLIENT_SECRET: " DISCORD_CLIENT_SECRET
    read -p "DISCORD_REDIRECT_URI [http://localhost:5000/callback/discord]: " DISCORD_REDIRECT_URI
    DISCORD_REDIRECT_URI=${DISCORD_REDIRECT_URI:-http://localhost:5000/callback/discord}
    read -p "DISCORD_BOT_TOKEN: " DISCORD_BOT_TOKEN
    read -p "DISCORD_GUILD_ID: " DISCORD_GUILD_ID
    read -p "DISCORD_ADMIN_ROLE_ID: " DISCORD_ADMIN_ROLE_ID
    read -p "DISCORD_USER_ROLE_ID (optional): " DISCORD_USER_ROLE_ID
    
    echo ""
    echo "--- Google Settings ---"
    read -p "GOOGLE_CLIENT_ID: " GOOGLE_CLIENT_ID
    read -p "GOOGLE_CLIENT_SECRET: " GOOGLE_CLIENT_SECRET
    GOOGLE_DISCOVERY_URL="https://accounts.google.com/.well-known/openid-configuration"

    echo "Erstelle .env Datei..."
    cat > .env <<EOF
FLASK_APP=app.py
FLASK_ENV=$FLASK_ENV
SECRET_KEY=$SECRET_KEY
DATABASE_URL=$DATABASE_URL

# Discord OAuth
DISCORD_CLIENT_ID=$DISCORD_CLIENT_ID
DISCORD_CLIENT_SECRET=$DISCORD_CLIENT_SECRET
DISCORD_REDIRECT_URI=$DISCORD_REDIRECT_URI
DISCORD_BOT_TOKEN=$DISCORD_BOT_TOKEN

# Discord Server Gating
DISCORD_GUILD_ID=$DISCORD_GUILD_ID
DISCORD_ADMIN_ROLE_ID=$DISCORD_ADMIN_ROLE_ID
DISCORD_USER_ROLE_ID=$DISCORD_USER_ROLE_ID

# Google OAuth (Admin Calendar Only)
GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET
GOOGLE_DISCOVERY_URL=$GOOGLE_DISCOVERY_URL
EOF
    echo ".env Datei erfolgreich erstellt!"
else
    echo ".env existiert bereits. Konfiguration übersprungen."
fi

# Webhook Service Installation
echo "⚙️ Installiere den Webhook-Service für automatische Updates..."

# Get the owner of the repository directory to avoid git dubious ownership errors
REAL_USER=$(stat -c '%U' . 2>/dev/null || stat -f '%Su' . 2>/dev/null || echo "${SUDO_USER:-$USER}")
if [ "$REAL_USER" = "root" ] && [ -n "$LOGNAME" ]; then
    REAL_USER=$LOGNAME
fi

WORKING_DIR=$(pwd)

echo "📝 Erstelle systemd-Service-Datei..."
cat <<EOF > /etc/systemd/system/terminplaner-webhook.service
[Unit]
Description=TerminPlaner Git Webhook Listener
After=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$WORKING_DIR
ExecStart=$WORKING_DIR/.venv/bin/python3 -u webhook_listener.py
Restart=always
RestartSec=5
EnvironmentFile=-$WORKING_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

echo "🔄 Lade systemd Daemon neu..."
systemctl daemon-reload

echo "🚀 Starte und aktiviere den Webhook-Service..."
systemctl enable terminplaner-webhook.service
systemctl start terminplaner-webhook.service

echo "✅ Webhook-Service wurde erfolgreich installiert und gestartet!"
echo "📡 Der Service lauscht auf Port 5001. Konfiguriere deinen GitHub/GitLab-Webhook auf: http://<deine-server-ip>:5001"
echo "ℹ️ Optional: Füge 'WEBHOOK_SECRET=dein_secret' zu deiner .env hinzu, um Webhook-Signaturen zu verifizieren."
echo "⚠️ Wichtig: Stelle sicher, dass der Benutzer '$REAL_USER' in der 'docker' Gruppe ist, falls du Docker verwendest:"
echo "    sudo usermod -aG docker $REAL_USER"

echo "Installation complete!"
