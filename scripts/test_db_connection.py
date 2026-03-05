"""
Quick test to check database connectivity.
"""
import sys
sys.path.insert(0, '.')

from app.config import get_settings
import psycopg2
from psycopg2 import OperationalError

def test_connection():
    """Test database connection."""
    settings = get_settings()
    
    print("Testing database connection...")
    print(f"Database URL: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'configured'}")
    
    try:
        # Try to connect with a short timeout
        conn = psycopg2.connect(
            settings.database_url,
            connect_timeout=5  # 5 second timeout
        )
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        
        print("✅ Database connection successful!")
        print(f"PostgreSQL version: {version[0].split(',')[0]}")
        
        # Check if tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('behavior_snapshots', 'drift_events', 'drift_scan_jobs', 'conflict_snapshots')
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"\n✅ Found {len(tables)} existing tables:")
            for table in tables:
                print(f"   - {table[0]}")
            print("\n⚠️  Tables already exist! Migrations might have already been applied.")
        else:
            print("\n📋 No tables found. Ready for migration.")
        
        cursor.close()
        conn.close()
        return True
        
    except OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        print("\nPossible solutions:")
        print("1. Check if Supabase is accessible (network/firewall)")
        print("2. Verify DATABASE_URL credentials in .env")
        print("3. Use local PostgreSQL for development")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_connection()
