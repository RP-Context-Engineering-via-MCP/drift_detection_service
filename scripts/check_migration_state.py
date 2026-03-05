"""
Check Alembic migration state.
"""
import sys
sys.path.insert(0, '.')

from app.config import get_settings
import psycopg2

def check_migration_state():
    """Check if alembic_version table exists and current version."""
    settings = get_settings()
    
    try:
        conn = psycopg2.connect(settings.database_url, connect_timeout=5)
        cursor = conn.cursor()
        
        # Check if alembic_version table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            )
        """)
        
        exists = cursor.fetchone()[0]
        
        if exists:
            print("✅ alembic_version table exists")
            
            # Get current version
            cursor.execute("SELECT version_num FROM alembic_version")
            version = cursor.fetchone()
            
            if version:
                print(f"📌 Current migration version: {version[0]}")
            else:
                print("⚠️  alembic_version table is empty (no migrations recorded)")
        else:
            print("❌ alembic_version table does not exist")
            print("\n💡 Solution: Since tables exist, mark database as up-to-date:")
            print("   alembic stamp head")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_migration_state()
