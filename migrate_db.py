import os
from website import create_app, db
from sqlalchemy import text

def migrate():
    app = create_app()
    with app.app_context():
        # Define the columns to add
        new_columns = [
            ('whatsapp_chat_id', 'VARCHAR(100)'),
            ('whatsapp_chat_name', 'VARCHAR(200)')
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

if __name__ == "__main__":
    migrate()
    print("Migration attempt finished.")
