"""Test aggregated Redis message publishing."""
import sys
sys.path.insert(0, '.')

import json
import redis
from unittest.mock import MagicMock, patch
from app.models.drift import DriftEvent, DriftType, DriftSeverity
from app.pipeline.drift_event_writer import DriftEventWriter
from app.config import get_settings

# Create mock database connection
mock_conn = MagicMock()

# Create some test events
events = [
    DriftEvent(
        drift_event_id="drift_001",
        user_id="user_123",
        drift_type=DriftType.TOPIC_EMERGENCE,
        drift_score=0.85,
        confidence=0.9,
        severity=DriftSeverity.STRONG_DRIFT,
        affected_targets=["python", "ml"],
        evidence={"new_topics": ["python", "ml"]},
        reference_window_start=1000000,
        reference_window_end=2000000,
        current_window_start=2000000,
        current_window_end=3000000,
        detected_at=3000000,
        behavior_ref_ids=["b1", "b2", "b3"]
    ),
    DriftEvent(
        drift_event_id="drift_002",
        user_id="user_123",
        drift_type=DriftType.TOPIC_ABANDONMENT,
        drift_score=0.65,
        confidence=0.8,
        severity=DriftSeverity.MODERATE_DRIFT,
        affected_targets=["javascript"],
        evidence={"abandoned_topics": ["javascript"]},
        reference_window_start=1000000,
        reference_window_end=2000000,
        current_window_start=2000000,
        current_window_end=3000000,
        detected_at=3000000,
        behavior_ref_ids=["b2", "b4", "b5"]
    ),
    DriftEvent(
        drift_event_id="drift_003",
        user_id="user_123",
        drift_type=DriftType.PREFERENCE_REVERSAL,
        drift_score=0.75,
        confidence=0.85,
        severity=DriftSeverity.MODERATE_DRIFT,
        affected_targets=["react"],
        evidence={"reversed_preferences": ["react"]},
        reference_window_start=1000000,
        reference_window_end=2000000,
        current_window_start=2000000,
        current_window_end=3000000,
        detected_at=3000000,
        behavior_ref_ids=["b1", "b3", "b6"]
    )
]

print("=" * 80)
print("TEST: Aggregated Redis Message Publishing")
print("=" * 80)

print("\nTest Events:")
for event in events:
    print(f"  - {event.drift_event_id}: {event.drift_type.value} "
          f"(severity: {event.severity.value}, score: {event.drift_score})")
    print(f"    behavior_ref_ids: {event.behavior_ref_ids}")

print("\nExpected Aggregated Message:")
print(f"  - user_id: user_123")
print(f"  - highest_severity: STRONG_DRIFT (from drift_001)")
print(f"  - behavior_ref_ids: ['b1', 'b2', 'b3', 'b4', 'b5', 'b6'] (deduplicated union)")
print(f"  - drift_event_ids: ['drift_001', 'drift_002', 'drift_003']")
print(f"  - event_count: 3")

# Mock Redis client to capture published message
mock_redis = MagicMock()
published_messages = []

def mock_xadd(name, fields, maxlen=None, approximate=None):
    """Mock Redis XADD to capture published message."""
    published_messages.append({
        "stream": name,
        "fields": fields,
        "maxlen": maxlen,
        "approximate": approximate
    })
    return "1234567890123-0"  # Mock message ID

mock_redis.xadd = mock_xadd

# Create writer with mock Redis
writer = DriftEventWriter(mock_conn, redis_client=mock_redis)

# Mock the repository insert to not actually write to DB
with patch.object(writer.drift_event_repo, 'insert', side_effect=lambda e: e.drift_event_id):
    print("\n" + "=" * 80)
    print("Testing DriftEventWriter.write() with aggregated publishing")
    print("=" * 80)
    
    # Call write method
    event_ids = writer.write(events)
    
    print(f"\nPersisted event IDs: {event_ids}")
    print(f"Number of Redis messages published: {len(published_messages)}")
    
    if published_messages:
        print("\nPublished Redis Message:")
        for msg in published_messages:
            print(f"  Stream: {msg['stream']}")
            print(f"  Payload:")
            payload = json.loads(msg['fields']['payload'])
            print(f"    - user_id: {payload['user_id']}")
            print(f"    - severity: {payload['severity']}")
            print(f"    - event_count: {payload['event_count']}")
            print(f"    - drift_event_ids: {payload['drift_event_ids']}")
            print(f"    - behavior_ref_ids: {payload['behavior_ref_ids']}")
            
            # Verify aggregation
            print("\n  Verification:")
            assert payload['user_id'] == 'user_123', "User ID mismatch"
            print(f"    ✓ User ID correct")
            
            assert payload['severity'] == 'STRONG_DRIFT', "Highest severity not selected"
            print(f"    ✓ Highest severity selected (STRONG_DRIFT)")
            
            expected_behaviors = sorted(['b1', 'b2', 'b3', 'b4', 'b5', 'b6'])
            assert payload['behavior_ref_ids'] == expected_behaviors, "Behavior IDs not deduplicated correctly"
            print(f"    ✓ Behavior IDs deduplicated: {len(expected_behaviors)} unique IDs")
            
            assert payload['event_count'] == 3, "Event count mismatch"
            print(f"    ✓ Event count correct: {payload['event_count']}")
            
            assert len(payload['drift_event_ids']) == 3, "Drift event IDs count mismatch"
            print(f"    ✓ All drift event IDs included: {payload['drift_event_ids']}")
            
            print("\n  ✅ All assertions passed!")
    else:
        print("\n  ❌ No messages were published to Redis!")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
