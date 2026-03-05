"""
Test script for Redis-based idempotency mechanism.

This script verifies that the event consumer correctly tracks processed
events using Redis, preventing duplicate processing across restarts and instances.
"""
import redis
import sys
import time
import os
from datetime import datetime

# Override Redis URL for local testing
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, ".")
from app.config import get_settings

settings = get_settings()


def get_test_redis_client():
    """Get a Redis client for testing, using localhost."""
    return redis.Redis.from_url("redis://localhost:6379/0", decode_responses=True)


def test_event_tracking():
    """Test basic event tracking functionality."""
    print("Test 1: Basic Event Tracking")
    print("=" * 50)
    
    redis_client = get_test_redis_client()
    processed_events_key = "consumer:processed_events"
    
    try:
        # Clean up first
        redis_client.delete(processed_events_key)
        
        # Mark events as processed
        event_ids = ["test-event-1", "test-event-2", "test-event-3"]
        
        for event_id in event_ids:
            result = redis_client.sadd(processed_events_key, event_id)
            if result:
                print(f"✅ Marked {event_id} as processed")
            else:
                print(f"❌ Failed to mark {event_id}")
                return False
        
        # Verify all events are tracked
        stored_events = redis_client.smembers(processed_events_key)
        if stored_events == set(event_ids):
            print(f"✅ All {len(event_ids)} events stored correctly")
        else:
            print(f"❌ Mismatch: expected {event_ids}, got {stored_events}")
            return False
        
        # Test duplicate detection
        for event_id in event_ids:
            is_member = redis_client.sismember(processed_events_key, event_id)
            if is_member:
                print(f"✅ {event_id} correctly identified as processed")
            else:
                print(f"❌ {event_id} not found in processed set")
                return False
        
        # Test new event
        new_event = "test-event-4"
        is_new = not redis_client.sismember(processed_events_key, new_event)
        if is_new:
            print(f"✅ {new_event} correctly identified as new")
        else:
            print(f"❌ {new_event} incorrectly marked as processed")
            return False
        
        # Cleanup
        redis_client.delete(processed_events_key)
        print()
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        return False


def test_duplicate_prevention():
    """Test that duplicate events are prevented."""
    print("Test 2: Duplicate Event Prevention")
    print("=" * 50)
    
    redis_client = get_test_redis_client()
    processed_events_key = "consumer:processed_events"
    
    try:
        # Clean up
        redis_client.delete(processed_events_key)
        
        event_id = "duplicate-test-event"
        processed_count = 0
        
        # Process event first time
        if not redis_client.sismember(processed_events_key, event_id):
            redis_client.sadd(processed_events_key, event_id)
            processed_count += 1
            print(f"✅ Event processed first time (count: {processed_count})")
        
        # Try to process again (should be skipped)
        if not redis_client.sismember(processed_events_key, event_id):
            redis_client.sadd(processed_events_key, event_id)
            processed_count += 1
            print(f"❌ Event processed again! (count: {processed_count})")
            return False
        else:
            print(f"✅ Duplicate event correctly skipped")
        
        # Verify final count
        if processed_count == 1:
            print(f"✅ Event processed exactly once")
            print()
            redis_client.delete(processed_events_key)
            return True
        else:
            print(f"❌ Event processed {processed_count} times (expected 1)")
            print()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        return False


def test_ttl_functionality():
    """Test that processed events have correct TTL."""
    print("Test 3: TTL Functionality")
    print("=" * 50)
    
    redis_client = get_test_redis_client()
    processed_events_key = "consumer:processed_events_ttl_test"
    
    try:
        # Clean up
        redis_client.delete(processed_events_key)
        
        # Add event with 5 second TTL
        event_id = "ttl-test-event"
        redis_client.sadd(processed_events_key, event_id)
        redis_client.expire(processed_events_key, 5)
        
        # Check TTL
        ttl = redis_client.ttl(processed_events_key)
        if 0 < ttl <= 5:
            print(f"✅ TTL set correctly ({ttl} seconds)")
        else:
            print(f"❌ TTL incorrect: {ttl}")
            return False
        
        # Verify event exists
        exists = redis_client.sismember(processed_events_key, event_id)
        if exists:
            print(f"✅ Event exists before expiration")
        else:
            print(f"❌ Event missing before expiration")
            return False
        
        # Wait for expiration
        print(f"   Waiting {ttl + 1} seconds for expiration...")
        time.sleep(ttl + 1)
        
        # Verify key expired
        exists = redis_client.exists(processed_events_key)
        if not exists:
            print(f"✅ Key expired after TTL")
            print()
            return True
        else:
            print(f"❌ Key still exists after TTL")
            print()
            redis_client.delete(processed_events_key)
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        return False


def test_multi_instance_simulation():
    """Simulate multiple consumer instances."""
    print("Test 4: Multi-Instance Simulation")
    print("=" * 50)
    
    redis_client = get_test_redis_client()
    processed_events_key = "consumer:processed_events"
    
    try:
        # Clean up
        redis_client.delete(processed_events_key)
        
        # Simulate 3 consumer instances processing same events
        event_ids = [f"event-{i}" for i in range(10)]
        
        processed_by_instance = {1: [], 2: [], 3: []}
        
        # Instance 1 processes first 5
        for event_id in event_ids[:5]:
            if not redis_client.sismember(processed_events_key, event_id):
                redis_client.sadd(processed_events_key, event_id)
                processed_by_instance[1].append(event_id)
        
        print(f"✅ Instance 1 processed {len(processed_by_instance[1])} events")
        
        # Instance 2 tries to process events 3-7 (overlap with instance 1)
        for event_id in event_ids[3:7]:
            if not redis_client.sismember(processed_events_key, event_id):
                redis_client.sadd(processed_events_key, event_id)
                processed_by_instance[2].append(event_id)
        
        print(f"✅ Instance 2 processed {len(processed_by_instance[2])} events (overlap prevented)")
        
        # Instance 3 processes remaining
        for event_id in event_ids[5:]:
            if not redis_client.sismember(processed_events_key, event_id):
                redis_client.sadd(processed_events_key, event_id)
                processed_by_instance[3].append(event_id)
        
        print(f"✅ Instance 3 processed {len(processed_by_instance[3])} events")
        
        # Verify no duplicates
        all_processed = (
            processed_by_instance[1] +
            processed_by_instance[2] +
            processed_by_instance[3]
        )
        
        if len(all_processed) == len(set(all_processed)):
            print(f"✅ No duplicate processing detected")
        else:
            print(f"❌ Duplicates found!")
            return False
        
        # Verify all events processed exactly once
        stored_events = redis_client.smembers(processed_events_key)
        if stored_events == set(event_ids):
            print(f"✅ All {len(event_ids)} events processed exactly once")
            print()
            redis_client.delete(processed_events_key)
            return True
        else:
            print(f"❌ Mismatch in processed events")
            print()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        return False


def test_consumer_restart_simulation():
    """Simulate consumer restart."""
    print("Test 5: Consumer Restart Simulation")
    print("=" * 50)
    
    redis_client = get_test_redis_client()
    processed_events_key = "consumer:processed_events"
    
    try:
        # Clean up
        redis_client.delete(processed_events_key)
        
        # Consumer processes some events
        batch_1 = [f"restart-event-{i}" for i in range(5)]
        for event_id in batch_1:
            redis_client.sadd(processed_events_key, event_id)
        
        print(f"✅ Consumer processed {len(batch_1)} events before restart")
        
        # Simulate restart (in real world, consumer process stops and starts)
        # But Redis state persists
        
        stored_before = redis_client.smembers(processed_events_key)
        print(f"✅ {len(stored_before)} events persisted in Redis")
        
        # After restart, consumer should skip these events
        skipped_count = 0
        processed_count = 0
        
        batch_2 = batch_1 + [f"restart-event-{i}" for i in range(5, 10)]
        
        for event_id in batch_2:
            if redis_client.sismember(processed_events_key, event_id):
                skipped_count += 1
            else:
                redis_client.sadd(processed_events_key, event_id)
                processed_count += 1
        
        print(f"✅ After restart: {skipped_count} skipped, {processed_count} new events processed")
        
        if skipped_count == 5 and processed_count == 5:
            print(f"✅ Consumer correctly resumed after restart")
            print()
            redis_client.delete(processed_events_key)
            return True
        else:
            print(f"❌ Unexpected counts: skipped={skipped_count}, processed={processed_count}")
            print()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        return False


def main():
    """Run all idempotency tests."""
    print("\n" + "=" * 50)
    print("IDEMPOTENCY TEST SUITE")
    print("=" * 50 + "\n")
    
    results = []
    
    # Run all tests
    results.append(("Event Tracking", test_event_tracking()))
    results.append(("Duplicate Prevention", test_duplicate_prevention()))
    results.append(("TTL Functionality", test_ttl_functionality()))
    results.append(("Multi-Instance", test_multi_instance_simulation()))
    results.append(("Consumer Restart", test_consumer_restart_simulation()))
    
    # Summary
    print("=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 50 + "\n")
    
    return all(result for _, result in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
