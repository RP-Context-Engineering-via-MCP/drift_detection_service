"""
Seed test data for drift detection testing.

This script creates realistic test data patterns in the database
to verify that each detector works correctly.
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.connection import get_sync_connection, create_tables
from app.models.behavior import BehaviorRecord, ConflictRecord

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def now_ts() -> int:
    """Get current timestamp."""
    return int(datetime.now(timezone.utc).timestamp())


def days_ago_ts(days: int) -> int:
    """Get timestamp N days ago."""
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return int(dt.timestamp())


def insert_behavior(conn, behavior: BehaviorRecord):
    """Insert a behavior record into the database."""
    query = """
        INSERT INTO behavior_snapshots (
            user_id, behavior_id, target, intent, context,
            polarity, credibility, reinforcement_count, state,
            created_at, last_seen_at, snapshot_updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    cursor = conn.cursor()
    cursor.execute(
        query,
        (
            behavior.user_id,
            behavior.behavior_id,
            behavior.target,
            behavior.intent,
            behavior.context,
            behavior.polarity,
            behavior.credibility,
            behavior.reinforcement_count,
            behavior.state,
            behavior.created_at,
            behavior.last_seen_at,
            behavior.snapshot_updated_at,
        ),
    )
    cursor.close()


def insert_conflict(conn, conflict: ConflictRecord):
    """Insert a conflict record into the database."""
    query = """
        INSERT INTO conflict_snapshots (
            user_id, conflict_id, conflict_type,
            behavior_id_1, behavior_id_2,
            old_target, new_target,
            old_polarity, new_polarity,
            resolution_status, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    cursor = conn.cursor()
    cursor.execute(
        query,
        (
            conflict.user_id,
            conflict.conflict_id,
            conflict.conflict_type,
            conflict.behavior_id_1,
            conflict.behavior_id_2,
            conflict.old_target,
            conflict.new_target,
            conflict.old_polarity,
            conflict.new_polarity,
            conflict.resolution_status,
            conflict.created_at,
        ),
    )
    cursor.close()


def seed_emergence_pattern(conn, user_id: str):
    """
    Seed TOPIC_EMERGENCE pattern.
    
    Pattern: User starts with Python behaviors, then gradually adopts
    ML-related topics (PyTorch, TensorFlow, Kaggle, Neural Networks).
    These should cluster together as domain emergence.
    """
    logger.info(f"Seeding TOPIC_EMERGENCE pattern for {user_id}...")
    
    behaviors = [
        # Old behaviors (reference window: 60-30 days ago)
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_python_old",
            target="python",
            intent="PREFERENCE",
            context="general",
            polarity="POSITIVE",
            credibility=0.7,
            reinforcement_count=8,
            state="ACTIVE",
            created_at=days_ago_ts(55),
            last_seen_at=days_ago_ts(35),
            snapshot_updated_at=days_ago_ts(35),
        ),
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_django_old",
            target="django",
            intent="PREFERENCE",
            context="web development",
            polarity="POSITIVE",
            credibility=0.6,
            reinforcement_count=5,
            state="ACTIVE",
            created_at=days_ago_ts(50),
            last_seen_at=days_ago_ts(32),
            snapshot_updated_at=days_ago_ts(32),
        ),
        # Current window: New ML/AI topics emerging
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_pytorch_new",
            target="pytorch",
            intent="PREFERENCE",
            context="machine learning",
            polarity="POSITIVE",
            credibility=0.8,
            reinforcement_count=6,
            state="ACTIVE",
            created_at=days_ago_ts(25),
            last_seen_at=days_ago_ts(2),
            snapshot_updated_at=days_ago_ts(2),
        ),
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_tensorflow_new",
            target="tensorflow",
            intent="PREFERENCE",
            context="machine learning",
            polarity="POSITIVE",
            credibility=0.75,
            reinforcement_count=5,
            state="ACTIVE",
            created_at=days_ago_ts(20),
            last_seen_at=days_ago_ts(3),
            snapshot_updated_at=days_ago_ts(3),
        ),
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_kaggle_new",
            target="kaggle",
            intent="PREFERENCE",
            context="data science",
            polarity="POSITIVE",
            credibility=0.7,
            reinforcement_count=4,
            state="ACTIVE",
            created_at=days_ago_ts(18),
            last_seen_at=days_ago_ts(1),
            snapshot_updated_at=days_ago_ts(1),
        ),
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_neural_nets_new",
            target="neural networks",
            intent="PREFERENCE",
            context="machine learning",
            polarity="POSITIVE",
            credibility=0.85,
            reinforcement_count=7,
            state="ACTIVE",
            created_at=days_ago_ts(15),
            last_seen_at=days_ago_ts(1),
            snapshot_updated_at=days_ago_ts(1),
        ),
    ]
    
    for behavior in behaviors:
        insert_behavior(conn, behavior)
    
    conn.commit()
    logger.info(f"  ✓ Inserted {len(behaviors)} behaviors for emergence pattern")


def seed_abandonment_pattern(conn, user_id: str):
    """
    Seed TOPIC_ABANDONMENT pattern.
    
    Pattern: User had strong React preference (high reinforcement)
    but hasn't mentioned it in 35+ days. Now focusing on Vue.
    """
    logger.info(f"Seeding TOPIC_ABANDONMENT pattern for {user_id}...")
    
    behaviors = [
        # Reference window: Strong React activity
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_react_old",
            target="react",
            intent="PREFERENCE",
            context="frontend",
            polarity="POSITIVE",
            credibility=0.9,
            reinforcement_count=12,  # High reinforcement
            state="ACTIVE",
            created_at=days_ago_ts(55),
            last_seen_at=days_ago_ts(40),  # 40 days ago - silent!
            snapshot_updated_at=days_ago_ts(40),
        ),
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_hooks_old",
            target="react hooks",
            intent="PREFERENCE",
            context="frontend",
            polarity="POSITIVE",
            credibility=0.85,
            reinforcement_count=8,
            state="ACTIVE",
            created_at=days_ago_ts(50),
            last_seen_at=days_ago_ts(38),
            snapshot_updated_at=days_ago_ts(38),
        ),
        # Current window: Shifted to Vue
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_vue_new",
            target="vue",
            intent="PREFERENCE",
            context="frontend",
            polarity="POSITIVE",
            credibility=0.8,
            reinforcement_count=6,
            state="ACTIVE",
            created_at=days_ago_ts(20),
            last_seen_at=days_ago_ts(2),
            snapshot_updated_at=days_ago_ts(2),
        ),
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_composition_new",
            target="composition api",
            intent="PREFERENCE",
            context="frontend",
            polarity="POSITIVE",
            credibility=0.75,
            reinforcement_count=5,
            state="ACTIVE",
            created_at=days_ago_ts(15),
            last_seen_at=days_ago_ts(1),
            snapshot_updated_at=days_ago_ts(1),
        ),
    ]
    
    for behavior in behaviors:
        insert_behavior(conn, behavior)
    
    conn.commit()
    logger.info(f"  ✓ Inserted {len(behaviors)} behaviors for abandonment pattern")


def seed_preference_reversal(conn, user_id: str):
    """
    Seed PREFERENCE_REVERSAL pattern.
    
    Pattern: User had POSITIVE polarity for "remote work",
    now has NEGATIVE polarity. Conflict record links them.
    """
    logger.info(f"Seeding PREFERENCE_REVERSAL pattern for {user_id}...")
    
    behaviors = [
        # Reference window: POSITIVE about remote work
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_remote_positive",
            target="remote work",
            intent="PREFERENCE",
            context="work style",
            polarity="POSITIVE",
            credibility=0.85,
            reinforcement_count=7,
            state="SUPERSEDED",  # Superseded by new behavior
            created_at=days_ago_ts(50),
            last_seen_at=days_ago_ts(35),
            snapshot_updated_at=days_ago_ts(25),
        ),
        # Current window: NEGATIVE about remote work
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_remote_negative",
            target="remote work",
            intent="PREFERENCE",
            context="work style",
            polarity="NEGATIVE",
            credibility=0.9,
            reinforcement_count=5,
            state="ACTIVE",
            created_at=days_ago_ts(20),
            last_seen_at=days_ago_ts(2),
            snapshot_updated_at=days_ago_ts(2),
        ),
    ]
    
    for behavior in behaviors:
        insert_behavior(conn, behavior)
    
    # Create conflict linking the two
    conflict = ConflictRecord(
        user_id=user_id,
        conflict_id="conflict_remote_polarity",
        conflict_type="USER_DECISION_NEEDED",
        behavior_id_1="beh_remote_positive",
        behavior_id_2="beh_remote_negative",
        old_target="remote work",
        new_target="remote work",
        old_polarity="POSITIVE",
        new_polarity="NEGATIVE",
        resolution_status="PENDING",
        created_at=days_ago_ts(20),
    )
    
    insert_conflict(conn, conflict)
    conn.commit()
    logger.info(f"  ✓ Inserted {len(behaviors)} behaviors + 1 conflict for reversal pattern")


def seed_intensity_shift(conn, user_id: str):
    """
    Seed INTENSITY_SHIFT pattern.
    
    Pattern: User had moderate credibility (0.4) for "vim",
    now has very high credibility (0.95). Significant intensity increase.
    """
    logger.info(f"Seeding INTENSITY_SHIFT pattern for {user_id}...")
    
    behaviors = [
        # Reference window: Moderate interest in vim
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_vim_low",
            target="vim",
            intent="PREFERENCE",
            context="text editor",
            polarity="POSITIVE",
            credibility=0.4,  # Low credibility
            reinforcement_count=3,
            state="SUPERSEDED",
            created_at=days_ago_ts(55),
            last_seen_at=days_ago_ts(35),
            snapshot_updated_at=days_ago_ts(30),
        ),
        # Current window: Very strong preference for vim
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_vim_high",
            target="vim",
            intent="PREFERENCE",
            context="text editor",
            polarity="POSITIVE",
            credibility=0.95,  # High credibility
            reinforcement_count=10,
            state="ACTIVE",
            created_at=days_ago_ts(25),
            last_seen_at=days_ago_ts(1),
            snapshot_updated_at=days_ago_ts(1),
        ),
        # Also in current: Other topics for comparison
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_emacs_current",
            target="emacs",
            intent="PREFERENCE",
            context="text editor",
            polarity="NEGATIVE",
            credibility=0.6,
            reinforcement_count=2,
            state="ACTIVE",
            created_at=days_ago_ts(22),
            last_seen_at=days_ago_ts(3),
            snapshot_updated_at=days_ago_ts(3),
        ),
    ]
    
    for behavior in behaviors:
        insert_behavior(conn, behavior)
    
    conn.commit()
    logger.info(f"  ✓ Inserted {len(behaviors)} behaviors for intensity shift pattern")


def seed_context_shift(conn, user_id: str):
    """
    Seed CONTEXT_SHIFT pattern.
    
    Pattern: User had "python" in specific context ("data science"),
    now uses it in "general" context. This is context expansion.
    """
    logger.info(f"Seeding CONTEXT_SHIFT pattern for {user_id}...")
    
    behaviors = [
        # Reference window: Python in data science context
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_python_ds",
            target="python",
            intent="PREFERENCE",
            context="data science",
            polarity="POSITIVE",
            credibility=0.8,
            reinforcement_count=7,
            state="SUPERSEDED",
            created_at=days_ago_ts(55),
            last_seen_at=days_ago_ts(32),
            snapshot_updated_at=days_ago_ts(30),
        ),
        # Current window: Python in general context (expansion)
        BehaviorRecord(
            user_id=user_id,
            behavior_id="beh_python_general",
            target="python",
            intent="PREFERENCE",
            context="general",
            polarity="POSITIVE",
            credibility=0.85,
            reinforcement_count=9,
            state="ACTIVE",
            created_at=days_ago_ts(25),
            last_seen_at=days_ago_ts(2),
            snapshot_updated_at=days_ago_ts(2),
        ),
    ]
    
    for behavior in behaviors:
        insert_behavior(conn, behavior)
    
    conn.commit()
    logger.info(f"  ✓ Inserted {len(behaviors)} behaviors for context shift pattern")


def seed_all_patterns(conn, user_id: str):
    """Seed all drift patterns for comprehensive testing."""
    logger.info(f"\n=== Seeding ALL patterns for {user_id} ===\n")
    
    seed_emergence_pattern(conn, user_id)
    seed_abandonment_pattern(conn, user_id)
    seed_preference_reversal(conn, user_id)
    seed_intensity_shift(conn, user_id)
    seed_context_shift(conn, user_id)
    
    logger.info(f"\n✅ All patterns seeded successfully for {user_id}\n")


def clear_test_data(conn, user_id: str = None):
    """
    Clear test data from database.
    
    Args:
        user_id: If provided, delete only for this user. Otherwise delete all.
    """
    cursor = conn.cursor()
    
    if user_id:
        logger.info(f"Clearing test data for user: {user_id}")
        cursor.execute("DELETE FROM drift_events WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM conflict_snapshots WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM behavior_snapshots WHERE user_id = %s", (user_id,))
    else:
        logger.info("Clearing ALL test data from database")
        cursor.execute("DELETE FROM drift_events")
        cursor.execute("DELETE FROM conflict_snapshots")
        cursor.execute("DELETE FROM behavior_snapshots")
    
    conn.commit()
    cursor.close()
    logger.info("✓ Test data cleared")


def main():
    """Main entry point for seed script."""
    parser = argparse.ArgumentParser(
        description="Seed test data for drift detection testing"
    )
    parser.add_argument(
        "--user",
        type=str,
        default="test_user_001",
        help="User ID to seed data for (default: test_user_001)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        choices=["emergence", "abandonment", "reversal", "intensity", "context", "all"],
        default="all",
        help="Which drift pattern to seed (default: all)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear test data instead of seeding",
    )
    parser.add_argument(
        "--clear-all",
        action="store_true",
        help="Clear ALL test data for all users",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create database tables before seeding",
    )
    
    args = parser.parse_args()
    
    # Create tables if requested (before opening connection)
    if args.create_tables:
        logger.info("Creating database tables...")
        create_tables()
        logger.info("✓ Tables created")
    
    try:
        # Get database connection using context manager
        with get_sync_connection() as conn:
            logger.info("Connected to database")
            
            # Clear data if requested
            if args.clear_all:
                clear_test_data(conn, user_id=None)
                return
            
            if args.clear:
                clear_test_data(conn, user_id=args.user)
                return
            
            # Seed data based on pattern
            pattern_map = {
                "emergence": seed_emergence_pattern,
                "abandonment": seed_abandonment_pattern,
                "reversal": seed_preference_reversal,
                "intensity": seed_intensity_shift,
                "context": seed_context_shift,
                "all": seed_all_patterns,
            }
            
            seed_func = pattern_map[args.pattern]
            seed_func(conn, args.user)
            
            # Show summary
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM behavior_snapshots WHERE user_id = %s",
                (args.user,)
            )
            behavior_count = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT COUNT(*) FROM conflict_snapshots WHERE user_id = %s",
                (args.user,)
            )
            conflict_count = cursor.fetchone()[0]
            cursor.close()
            
            logger.info(f"\n📊 Summary for {args.user}:")
            logger.info(f"   Behaviors: {behavior_count}")
            logger.info(f"   Conflicts: {conflict_count}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
