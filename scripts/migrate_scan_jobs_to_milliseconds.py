"""
Migration script to convert drift_scan_jobs timestamps from seconds to milliseconds.

This script updates all existing scan job records to use milliseconds instead of seconds,
ensuring consistency with the behavior_snapshots table.

Run this ONCE after deploying the timestamp standardization fix.

Usage:
    python scripts/migrate_scan_jobs_to_milliseconds.py
"""

import sys
sys.path.insert(0, '.')

from app.db.connection import get_sync_connection


def migrate_timestamps():
    """
    Convert all drift_scan_jobs timestamp columns from seconds to milliseconds.
    
    This multiplies scheduled_at, started_at, and completed_at by 1000 for all rows
    where the values are less than 10^12 (indicating they're in seconds, not milliseconds).
    """
    
    print("="*80)
    print("MIGRATING drift_scan_jobs TIMESTAMPS TO MILLISECONDS")
    print("="*80)
    
    with get_sync_connection() as conn:
        cursor = conn.cursor()
        
        # Check how many rows need conversion
        # Timestamps in seconds are < 10^10 (year 2286)
        # Timestamps in milliseconds are >= 10^12 (valid from year 2001+)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM drift_scan_jobs 
            WHERE scheduled_at < 1000000000000
        """)
        
        count_to_migrate = cursor.fetchone()[0]
        
        if count_to_migrate == 0:
            print("\n✓ No records need migration - all timestamps are already in milliseconds")
            return
        
        print(f"\nFound {count_to_migrate} record(s) with timestamps in seconds")
        print("Converting to milliseconds...\n")
        
        # Update scheduled_at (always present)
        cursor.execute("""
            UPDATE drift_scan_jobs 
            SET scheduled_at = scheduled_at * 1000 
            WHERE scheduled_at < 1000000000000
        """)
        
        scheduled_updated = cursor.rowcount
        print(f"  ✓ Updated scheduled_at for {scheduled_updated} record(s)")
        
        # Update started_at (may be NULL)
        cursor.execute("""
            UPDATE drift_scan_jobs 
            SET started_at = started_at * 1000 
            WHERE started_at IS NOT NULL 
            AND started_at < 1000000000000
        """)
        
        started_updated = cursor.rowcount
        print(f"  ✓ Updated started_at for {started_updated} record(s)")
        
        # Update completed_at (may be NULL)
        cursor.execute("""
            UPDATE drift_scan_jobs 
            SET completed_at = completed_at * 1000 
            WHERE completed_at IS NOT NULL 
            AND completed_at < 1000000000000
        """)
        
        completed_updated = cursor.rowcount
        print(f"  ✓ Updated completed_at for {completed_updated} record(s)")
        
        # Commit changes
        conn.commit()
        
        print("\n" + "="*80)
        print("✅ MIGRATION COMPLETE")
        print("="*80)
        print(f"\nAll timestamps in drift_scan_jobs table are now in milliseconds.")
        print(f"This ensures consistency with the behavior_snapshots table.\n")
        
        # Verify the migration
        cursor.execute("""
            SELECT COUNT(*) 
            FROM drift_scan_jobs 
            WHERE scheduled_at < 1000000000000
        """)
        
        remaining = cursor.fetchone()[0]
        
        if remaining > 0:
            print(f"⚠️  WARNING: {remaining} record(s) still have timestamps in seconds!")
        else:
            print("✓ Verification passed - no records with second-based timestamps remain\n")


if __name__ == "__main__":
    try:
        migrate_timestamps()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
