"""
Migration script to transfer data from local SQLite to Turso cloud database.
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import models and database functions
import db
from db import ALL_MODELS

def migrate_data():
    """Migrate data from local SQLite to Turso cloud database."""
    
    print("Starting migration from local SQLite to Turso cloud database...")
    
    # First, connect to local SQLite database
    local_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'inventory.db')
    print(f"Local database path: {local_db_path}")
    
    if not os.path.exists(local_db_path):
        print(f"Local database not found at {local_db_path}")
        # Try alternative path
        local_db_path = 'inventory.db'
        if not os.path.exists(local_db_path):
            print("Local database not found. No data to migrate.")
            return
    
    # Create local engine
    local_engine = create_engine(f'sqlite:///{local_db_path}')
    LocalSession = sessionmaker(bind=local_engine)
    local_session = LocalSession()
    
    # Create Turso engine
    turso_engine = db.build_engine()
    TursoSession = sessionmaker(bind=turso_engine)
    turso_session = TursoSession()
    
    # Create tables in Turso if they don't exist
    print("Creating tables in Turso database...")
    db.Base.metadata.create_all(turso_engine)
    
    # Migrate each model
    for model in ALL_MODELS:
        table_name = model.__tablename__
        print(f"\nMigrating {table_name}...")
        
        try:
            # Get all rows from local database
            local_rows = local_session.query(model).all()
            print(f"Found {len(local_rows)} rows in local {table_name}")
            
            if not local_rows:
                print(f"No data to migrate for {table_name}")
                continue
            
            # Check if Turso table is empty
            turso_count = turso_session.query(model).count()
            print(f"Existing rows in Turso {table_name}: {turso_count}")
            
            if turso_count > 0:
                print(f"Turso {table_name} already has data. Skipping migration to avoid duplicates.")
                continue
            
            # Migrate data
            for row in local_rows:
                # Convert row to dict
                row_dict = db.row_to_dict(row)
                # Remove id to let Turso auto-generate
                row_dict.pop('id', None)
                
                # Create new instance in Turso
                new_row = model(**row_dict)
                turso_session.add(new_row)
            
            turso_session.commit()
            print(f"Successfully migrated {len(local_rows)} rows to Turso {table_name}")
            
        except Exception as e:
            turso_session.rollback()
            print(f"Error migrating {table_name}: {e}")
            continue
    
    # Close sessions
    local_session.close()
    turso_session.close()
    
    print("\nMigration completed!")

if __name__ == "__main__":
    migrate_data()