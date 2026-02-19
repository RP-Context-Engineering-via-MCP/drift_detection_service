"""Debug script to check drift detection data and diagnose issues."""

import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone, timedelta
from app.db.connection import get_sync_connection_simple
from app.db.repositories.behavior_repo import BehaviorRepository
from app.db.repositories.conflict_repo import ConflictRepository
from app.config import get_settings

def main():
    settings = get_settings()
    conn = get_sync_connection_simple()
    behavior_repo = BehaviorRepository(conn)
    conflict_repo = ConflictRepository(conn)
    
    user_id = "user_test_001"
    
    print("=" * 60)
    print("DRIFT DETECTION DEBUG")
    print("=" * 60)
    
    # Current time
    now = datetime.now(timezone.utc)
    now_ts = int(now.timestamp())
    print(f"\nCurrent time: {now} (ts: {now_ts})")
    
    # Time windows from config
    current_window_days = settings.current_window_days
    ref_start_days = settings.reference_window_start_days
    ref_end_days = settings.reference_window_end_days
    
    current_start = now - timedelta(days=current_window_days)
    current_end = now
    ref_start = now - timedelta(days=ref_start_days)
    ref_end = now - timedelta(days=ref_end_days)
    
    print(f"\nTime Window Configuration:")
    print(f"  Current window: {current_window_days} days")
    print(f"  Reference window: {ref_start_days} to {ref_end_days} days ago")
    
    print(f"\nCurrent Window: {current_start.date()} to {current_end.date()}")
    print(f"  Timestamps: {int(current_start.timestamp())} to {int(current_end.timestamp())}")
    
    print(f"\nReference Window: {ref_start.date()} to {ref_end.date()}")
    print(f"  Timestamps: {int(ref_start.timestamp())} to {int(ref_end.timestamp())}")
    
    # Get all behaviors for user
    print(f"\n{'=' * 60}")
    print(f"ALL BEHAVIORS FOR {user_id}")
    print("=" * 60)
    
    all_behaviors = behavior_repo.get_all_behaviors(user_id)
    print(f"Total behaviors: {len(all_behaviors)}")
    
    for b in all_behaviors:
        created_dt = datetime.fromtimestamp(b.created_at, tz=timezone.utc)
        print(f"  - {b.behavior_id}: {b.target} ({b.polarity})")
        print(f"    credibility={b.credibility}, reinforcement={b.reinforcement_count}, state={b.state}")
        print(f"    created_at={b.created_at} ({created_dt.date()})")
    
    # Get behaviors in reference window (with active_only=False for historical)
    print(f"\n{'=' * 60}")
    print(f"BEHAVIORS IN REFERENCE WINDOW (active_only=False)")
    print("=" * 60)
    
    ref_behaviors = behavior_repo.get_behaviors_in_window(
        user_id, 
        int(ref_start.timestamp()), 
        int(ref_end.timestamp()),
        active_only=False  # Include superseded behaviors for historical window
    )
    print(f"Found: {len(ref_behaviors)}")
    for b in ref_behaviors:
        print(f"  - {b.target} (credibility={b.credibility}, reinforcement={b.reinforcement_count}, state={b.state})")
    
    # Get behaviors in current window
    print(f"\n{'=' * 60}")
    print(f"BEHAVIORS IN CURRENT WINDOW")
    print("=" * 60)
    
    current_behaviors = behavior_repo.get_behaviors_in_window(
        user_id,
        int(current_start.timestamp()),
        int(current_end.timestamp())
    )
    print(f"Found: {len(current_behaviors)}")
    for b in current_behaviors:
        print(f"  - {b.target} (credibility={b.credibility}, reinforcement={b.reinforcement_count})")
    
    # Get conflicts
    print(f"\n{'=' * 60}")
    print(f"CONFLICTS IN CURRENT WINDOW")
    print("=" * 60)
    
    conflicts = conflict_repo.get_conflicts_in_window(
        user_id,
        int(current_start.timestamp()),
        int(current_end.timestamp())
    )
    print(f"Found: {len(conflicts)}")
    for c in conflicts:
        print(f"  - {c.conflict_id}: {c.old_polarity} -> {c.new_polarity} ({c.conflict_type})")
    
    # Show expected timestamps from sample data
    print(f"\n{'=' * 60}")
    print("SAMPLE DATA TIMESTAMPS (from sample_publish_drift_test.txt)")
    print("=" * 60)
    print("Reference window behaviors should have created_at:")
    print(f"  - 1766448000 = {datetime.fromtimestamp(1766448000, tz=timezone.utc).date()} (python)")
    print(f"  - 1766534400 = {datetime.fromtimestamp(1766534400, tz=timezone.utc).date()} (java)")
    print(f"  - 1766620800 = {datetime.fromtimestamp(1766620800, tz=timezone.utc).date()} (docker)")
    print(f"  - 1766707200 = {datetime.fromtimestamp(1766707200, tz=timezone.utc).date()} (remote work pos)")
    
    print("\nCurrent window behaviors should have created_at:")
    print(f"  - 1769126400 = {datetime.fromtimestamp(1769126400, tz=timezone.utc).date()} (python new)")
    print(f"  - 1769212800 = {datetime.fromtimestamp(1769212800, tz=timezone.utc).date()} (rust)")
    print(f"  - 1769299200 = {datetime.fromtimestamp(1769299200, tz=timezone.utc).date()} (kubernetes)")
    print(f"  - 1769385600 = {datetime.fromtimestamp(1769385600, tz=timezone.utc).date()} (docker new)")
    print(f"  - 1769472000 = {datetime.fromtimestamp(1769472000, tz=timezone.utc).date()} (remote work neg)")
    
    conn.close()

if __name__ == "__main__":
    main()
