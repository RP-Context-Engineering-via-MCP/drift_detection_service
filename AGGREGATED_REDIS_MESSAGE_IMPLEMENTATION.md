# Aggregated Redis Message Publishing - Implementation Summary

## Overview
The Drift Detection Service has been updated to aggregate all drift events from a single scan into ONE Redis message, instead of publishing individual messages for each event.

## Changes Made

### 1. DriftEventWriter (`app/pipeline/drift_event_writer.py`)

#### Modified `write()` method
- **Previous behavior**: Published individual Redis messages for each drift event
- **New behavior**: Publishes ONE aggregated message per scan
- Individual events are still stored in the database (unchanged)
- Only Redis publishing changed to aggregated format

#### Added `_publish_aggregated_message()` method
A new method that creates a single aggregated Redis message with:
- **drift_event_ids**: Array of all event IDs from the scan
- **user_id**: User identifier (same for all events in a scan)
- **severity**: Highest severity detected across all events
- **behavior_ref_ids**: Deduplicated union of all behavior_ref_ids
- **event_count**: Total number of events in the scan

**Severity Selection Logic**:
```python
severity_order = {
    "NO_DRIFT": 0,
    "WEAK_DRIFT": 1,
    "MODERATE_DRIFT": 2,
    "STRONG_DRIFT": 3
}
highest_severity = max(events, key=lambda e: severity_order[e.severity.value]).severity.value
```

### 2. DriftDetector (`app/core/drift_detector.py`)

#### Modified `_persist_events()` method
- **Previous behavior**: Called `write_single()` in a loop for each event
- **New behavior**: Calls batch `write()` method with all events
- Passes reference and current snapshots for context

#### Updated method signature
```python
def _persist_events(
    self, 
    events: List[DriftEvent],
    reference=None,
    current=None
) -> None:
```

## Redis Message Format

### Previous Format (Individual Messages)
```json
{
  "drift_event_id": "drift-evt-abc123",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "severity": "STRONG_DRIFT",
  "behavior_ref_ids": ["b1", "b2", "b3"]
}
```
**Result**: 3 separate messages for 3 events

### New Format (Aggregated Message)
```json
{
  "drift_event_ids": ["drift-evt-001", "drift-evt-002", "drift-evt-003"],
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "severity": "STRONG_DRIFT",
  "behavior_ref_ids": ["b1", "b2", "b3", "b4", "b5", "b6"],
  "event_count": 3
}
```
**Result**: 1 single aggregated message per scan

## Example Scenario

### Input Events
1. **Event 1**: TOPIC_EMERGENCE
   - Severity: STRONG_DRIFT (0.85)
   - behavior_ref_ids: ["b1", "b2", "b3"]

2. **Event 2**: TOPIC_ABANDONMENT
   - Severity: MODERATE_DRIFT (0.65)
   - behavior_ref_ids: ["b2", "b4", "b5"]

3. **Event 3**: PREFERENCE_REVERSAL
   - Severity: MODERATE_DRIFT (0.75)
   - behavior_ref_ids: ["b1", "b3", "b6"]

### Output Aggregated Message
```json
{
  "drift_event_ids": ["drift_001", "drift_002", "drift_003"],
  "user_id": "user_123",
  "severity": "STRONG_DRIFT",
  "behavior_ref_ids": ["b1", "b2", "b3", "b4", "b5", "b6"],
  "event_count": 3
}
```

**Key Points**:
- Severity: STRONG_DRIFT (highest from Event 1)
- behavior_ref_ids: 6 unique IDs (deduplicated from all events)
- event_count: 3 events aggregated

## Testing

### Test Script
Created `scripts/test_aggregated_redis.py` to verify:
- ✅ Only ONE Redis message published per scan
- ✅ Highest severity correctly selected
- ✅ behavior_ref_ids properly deduplicated
- ✅ All drift_event_ids included
- ✅ Event count is accurate

### Existing Tests
All 71 existing tests continue to pass without modification.

## Benefits

1. **Reduced Redis Traffic**: One message per scan instead of N messages
2. **Simplified Consumption**: Downstream consumers receive one comprehensive message
3. **Better Aggregation**: Highest severity and complete behavior context in one place
4. **Database Unchanged**: Individual events still stored for historical tracking

## Backward Compatibility

⚠️ **Breaking Change**: Downstream consumers that expect individual drift event messages will need to be updated to handle the new aggregated format.

**Migration Path for Consumers**:
1. Check if message contains `drift_event_ids` (array) or `drift_event_id` (string)
2. If array, it's an aggregated message
3. Process accordingly based on the new format

## Files Modified

1. `app/pipeline/drift_event_writer.py`
   - Modified: `write()` method
   - Added: `_publish_aggregated_message()` method

2. `app/core/drift_detector.py`
   - Modified: `_persist_events()` method
   - Modified: `detect_drift()` method call to `_persist_events()`

3. `scripts/test_aggregated_redis.py` (new)
   - Test script for aggregated Redis publishing

## Future Considerations

1. **Consumer Updates**: Update downstream services to handle aggregated format
2. **Monitoring**: Update metrics/dashboards to track aggregated messages
3. **Documentation**: Update API/integration docs with new message format
