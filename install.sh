#!/bin/bash
set -e

echo "⚙️ Starte Installation des TerminPlaner Webhook Services..."

# Check if systemd exists
if ! command -v systemctl &> /dev/null; then
    echo "❌ Fehler: 'systemctl' wurde nicht gefunden. Dieses Installationsskript unterstützt nur Linux-Systeme mit systemd."
    exit 1
fi

USER_NAME=$(whoami)
WORKING_DIR=$(pwd)
PYTHON_PATH=$(which python3)

echo "📝 Erstelle systemd-Service-Datei..."
cat <<EOF > terminplaner-webhook.service
[Unit]
Description=TerminPlaner Git Webhook Listener
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$WORKING_DIR
ExecStart=$PYTHON_PATH -u webhook_listener.py
Restart=always
RestartSec=5
EnvironmentFile=-$WORKING_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

echo "📦 Kopiere Service-Datei nach /etc/systemd/system/ (erfordert sudo-Rechte)..."
sudo mv terminplaner-webhook.service /etc/systemd/system/terminplaner-webhook.service

echo "🔄 Lade systemd Daemon neu..."
sudo systemctl daemon-reload

echo "🚀 Starte und aktiviere den Webhook-Service..."
sudo systemctl enable terminplaner-webhook.service
sudo systemctl start terminplaner-webhook.service

echo "✅ Webhook-Service wurde erfolgreich installiert und gestartet!"
echo "📡 Der Service lauscht auf Port 5001. Konfiguriere deinen GitHub/GitLab-Webhook auf: http://<deine-server-ip>:5001"
echo "ℹ️ Optional: Füge 'WEBHOOK_SECRET=dein_secret' zu deiner .env hinzu, um Webhook-Signaturen zu verifizieren."
