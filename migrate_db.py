import os
from website import create_app, db
from sqlalchemy import text

def migrate():
    app = create_app()
    with app.app_context():
        # Define the columns to add
        new_columns = [
            ('whatsapp_chat_id', 'VARCHAR(100)'),
            ('whatsapp_chat_name', 'VARCHAR(200)'),
            ('google_calendar_name', 'VARCHAR(200)'),
            ('whatsapp_search_groups', 'TEXT')
        ]
        
        # Determine the database type
        engine = db.engine
        dialect = engine.dialect.name
        
        print(f"Detected database dialect: {dialect}")
        
        for col_name, col_type in new_columns:
            try:
                # Check if column already exists (basic check)
                # This varies by DB, but we can just try to add and catch the error
                print(f"Adding column {col_name}...")
                
                # SQLAlchemy text() handles the escaping
                if dialect == 'sqlite':
                    # SQLite syntax
                    db.session.execute(text(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}"))
                else:
                    # Generic SQL syntax (works for Postgres/MySQL)
                    db.session.execute(text(f"ALTER TABLE \"user\" ADD COLUMN {col_name} {col_type}"))
                
                db.session.commit()
                print(f"Successfully added {col_name}.")
            except Exception as e:
                db.session.rollback()
                # If it already exists, we might get an error like "duplicate column name"
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"Column {col_name} already exists.")
                else:
                    print(f"Error adding {col_name}: {e}")

        # Add poll_type to poll table
        try:
            print("Adding column poll_type to poll table...")
            db.session.execute(text("ALTER TABLE poll ADD COLUMN poll_type VARCHAR(50) DEFAULT 'single'"))
            db.session.commit()
            print("Successfully added poll_type column to poll table.")
        except Exception as e:
            db.session.rollback()
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("Column poll_type already exists in poll table.")
            else:
                print(f"Error adding poll_type column to poll table: {e}")

        # Add whatsapp_poll_id to poll table
        try:
            print("Adding column whatsapp_poll_id to poll table...")
            db.session.execute(text("ALTER TABLE poll ADD COLUMN whatsapp_poll_id VARCHAR(200)"))
            db.session.commit()
            print("Successfully added whatsapp_poll_id column to poll table.")
        except Exception as e:
            db.session.rollback()
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("Column whatsapp_poll_id already exists in poll table.")
            else:
                print(f"Error adding whatsapp_poll_id column to poll table: {e}")

        # Add whatsapp_sender to vote table
        try:
            print("Adding column whatsapp_sender to vote table...")
            db.session.execute(text("ALTER TABLE vote ADD COLUMN whatsapp_sender VARCHAR(100)"))
            db.session.commit()
            print("Successfully added whatsapp_sender column to vote table.")
        except Exception as e:
            db.session.rollback()
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("Column whatsapp_sender already exists in vote table.")
            else:
                print(f"Error adding whatsapp_sender column to vote table: {e}")

        # Add is_whatsapp to vote table
        try:
            print("Adding column is_whatsapp to vote table...")
            db.session.execute(text("ALTER TABLE vote ADD COLUMN is_whatsapp BOOLEAN DEFAULT 0"))
            db.session.commit()
            print("Successfully added is_whatsapp column to vote table.")
        except Exception as e:
            db.session.rollback()
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("Column is_whatsapp already exists in vote table.")
            else:
                print(f"Error adding is_whatsapp column to vote table: {e}")

        # Add whatsapp_admin_jid to user table
        try:
            print("Adding column whatsapp_admin_jid to user table...")
            db.session.execute(text("ALTER TABLE user ADD COLUMN whatsapp_admin_jid VARCHAR(100)"))
            db.session.commit()
            print("Successfully added whatsapp_admin_jid column to user table.")
        except Exception as e:
            db.session.rollback()
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("Column whatsapp_admin_jid already exists in user table.")
            else:
                print(f"Error adding whatsapp_admin_jid column to user table: {e}")

        # Add whatsapp_creator_chat_id to poll table
        try:
            print("Adding column whatsapp_creator_chat_id to poll table...")
            db.session.execute(text("ALTER TABLE poll ADD COLUMN whatsapp_creator_chat_id VARCHAR(100)"))
            db.session.commit()
            print("Successfully added whatsapp_creator_chat_id column to poll table.")
        except Exception as e:
            db.session.rollback()
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("Column whatsapp_creator_chat_id already exists in poll table.")
            else:
                print(f"Error adding whatsapp_creator_chat_id column to poll table: {e}")

        # Add whatsapp_last_reminder_at to poll table
        try:
            print("Adding column whatsapp_last_reminder_at to poll table...")
            db.session.execute(text("ALTER TABLE poll ADD COLUMN whatsapp_last_reminder_at DATETIME"))
            db.session.commit()
            print("Successfully added whatsapp_last_reminder_at column to poll table.")
        except Exception as e:
            db.session.rollback()
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("Column whatsapp_last_reminder_at already exists in poll table.")
            else:
                print(f"Error adding whatsapp_last_reminder_at column to poll table: {e}")

        # Add whatsapp_admin_chat_id to user table
        try:
            print("Adding column whatsapp_admin_chat_id to user table...")
            db.session.execute(text("ALTER TABLE user ADD COLUMN whatsapp_admin_chat_id VARCHAR(100)"))
            db.session.commit()
            print("Successfully added whatsapp_admin_chat_id column to user table.")
        except Exception as e:
            db.session.rollback()
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("Column whatsapp_admin_chat_id already exists in user table.")
            else:
                print(f"Error adding whatsapp_admin_chat_id column to user table: {e}")

        # Add whatsapp_admin_chat_name to user table
        try:
            print("Adding column whatsapp_admin_chat_name to user table...")
            db.session.execute(text("ALTER TABLE user ADD COLUMN whatsapp_admin_chat_name VARCHAR(200)"))
            db.session.commit()
            print("Successfully added whatsapp_admin_chat_name column to user table.")
        except Exception as e:
            db.session.rollback()
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                print("Column whatsapp_admin_chat_name already exists in user table.")
            else:
                print(f"Error adding whatsapp_admin_chat_name column to user table: {e}")


if __name__ == "__main__":
    migrate()
    print("Migration attempt finished.")
