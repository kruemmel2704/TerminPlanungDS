import sqlite3
import os

DB_PATH = 'instance/database.db'

def run_update():
    if not os.path.exists(DB_PATH):
        print(f"❌ Fehler: Datenbank unter '{DB_PATH}' wurde nicht gefunden.")
        return

    print(f"🔄 Starte Datenbank-Update für '{DB_PATH}'...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Helper function to check if a column exists
    def column_exists(table, column):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        return column in columns

    # 1. Update user table
    try:
        if not column_exists('user', 'whatsapp_admin_jid'):
            print("➕ Füge Spalte 'whatsapp_admin_jid' zur Tabelle 'user' hinzu...")
            cursor.execute("ALTER TABLE user ADD COLUMN whatsapp_admin_jid VARCHAR(100)")
            print("✅ Spalte 'whatsapp_admin_jid' erfolgreich hinzugefügt.")
        else:
            print("ℹ️ Spalte 'whatsapp_admin_jid' in Tabelle 'user' existiert bereits.")
    except Exception as e:
        print(f"❌ Fehler bei 'user'-Update: {e}")

    # 2. Update poll table
    try:
        if not column_exists('poll', 'whatsapp_creator_chat_id'):
            print("➕ Füge Spalte 'whatsapp_creator_chat_id' zur Tabelle 'poll' hinzu...")
            cursor.execute("ALTER TABLE poll ADD COLUMN whatsapp_creator_chat_id VARCHAR(100)")
            print("✅ Spalte 'whatsapp_creator_chat_id' erfolgreich hinzugefügt.")
        else:
            print("ℹ️ Spalte 'whatsapp_creator_chat_id' in Tabelle 'poll' existiert bereits.")
    except Exception as e:
        print(f"❌ Fehler bei 'poll'-Update: {e}")

    # 3. Create whatsapp_state table
    try:
        print("🔨 Erstelle Tabelle 'whatsapp_state' falls sie nicht existiert...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whatsapp_state (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                chat_id VARCHAR(100) UNIQUE NOT NULL,
                sender_jid VARCHAR(100) NOT NULL,
                state VARCHAR(50) NOT NULL,
                poll_type VARCHAR(50),
                title VARCHAR(200),
                dates TEXT,
                whatsapp_poll_id VARCHAR(200),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Tabelle 'whatsapp_state' ist bereit.")
    except Exception as e:
        print(f"❌ Fehler beim Erstellen der Tabelle 'whatsapp_state': {e}")

    conn.commit()
    conn.close()
    print("🎉 Datenbank-Update erfolgreich abgeschlossen!")

if __name__ == "__main__":
    run_update()
