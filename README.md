# ⚔️ Liga Termin Planer

Ein professionelles Web-Tool zur Terminfindung und Roster-Planung für E-Sport Ligen und Clan-Wars. Mit Discord-Integration, Google Kalender Automatisierung und PWA-Support.

## 🚀 Features

*   **Discord SSO Login**: Nutzer melden sich einfach mit ihrem Discord-Account an.
*   **Server-Gating**: Nur Mitglieder deines spezifischen Discord-Servers (Guild) mit bestimmten Rollen erhalten Zugriff.
*   **Nickname-Support**: Die App nutzt automatisch den Server-spezifischen Nickname der Nutzer.
*   **Interaktives Voting**: Nutzer können für mehrere Terminvorschläge gleichzeitig abstimmen (Checkbox-System).
*   **Roster-Management**: Admins können nach dem Voting ein Roster (War Orga, 3 Spieler, Ersatz) festlegen.
*   **Google Kalender Integration**: Automatisches Erstellen eines gemeinsamen Spielplans.
*   **Erinnerungen**: Automatische Google-Kalender-Benachrichtigungen (1 Tag & 1 Stunde vorher).
*   **PWA-Support**: Als App auf dem Smartphone installierbar.

---

## 🛠️ Installation & Setup

### 1. Voraussetzungen
*   Python 3.8+
*   Ein Google Cloud Projekt (für Kalender API)
*   Eine Discord Application (für SSO & Bot)

### 2. Discord Setup
1.  Erstelle eine App im [Discord Developer Portal](https://discord.com/developers/applications).
2.  **OAuth2**: Füge die Redirect URI hinzu: `http://localhost:5000/callback/discord`.
3.  **Bot**: Aktiviere unter dem Reiter "Bot" den **"Server Members Intent"** (WICHTIG!).
4.  Lade den Bot auf deinen Server ein.
5.  Notiere dir: `Client ID`, `Client Secret`, `Bot Token`, `Guild ID` und die `Rollen-IDs`.

### 3. Google Cloud Setup
1.  Aktiviere die **Google Calendar API**.
2.  Erstelle **OAuth 2.0-Client-IDs** (Webanwendung).
3.  Füge die Redirect URI hinzu: `http://localhost:5000/admin/google-callback`.
4.  Notiere dir: `Client ID` und `Client Secret`.

### 4. Projekt aufsetzen
```bash
# Abhängigkeiten installieren
pip install -r requirements.txt

# .env Datei erstellen (Vorlage nutzen)
cp .env.template .env
```
Fülle die `.env` mit deinen notierten IDs und Secrets aus.

---

## 🏃 Betrieb

Starte die App (Webseite und Bot starten gleichzeitig):
```bash
python app.py
```
Die Seite ist dann unter `http://localhost:5000` erreichbar.

---

## 📖 Bedienung für Admins

1.  **Login**: Über Discord anmelden.
2.  **Kalender verknüpfen**: Im Dashboard einmalig "Google Kalender verknüpfen" klicken.
3.  **Abstimmung erstellen**: Titel, Deadline und Terminvorschläge eingeben.
4.  **Voting beenden**: Entweder manuell beenden oder warten, bis die Deadline abläuft.
5.  **Roster planen**: Klicke auf "Roster Planen". Wähle das Team aus und bestätige den Termin.
6.  **Fertig**: Der Termin wird automatisch in deinen Google-Kalender ("Liga Spielplan") eingetragen.

---

## 📱 Als App installieren (PWA)
Öffne die Seite auf deinem Handy im Browser (z.B. Chrome) und wähle **"Zum Startbildschirm hinzufügen"**. Das Tool erscheint nun als eigenständige App mit Icon in deinem Menü.

---

## 📝 Lizenz
Dieses Projekt wurde für den privaten Gebrauch in der Gaming-Community entwickelt.
