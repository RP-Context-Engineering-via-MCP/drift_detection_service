"""
Test script for distributed lock mechanism.

This script verifies that the Redis-based distributed lock prevents
multiple processes from executing the same job simultaneously.
"""
import redis
import time
import sys
import os
from contextlib import contextmanager
from typing import Generator

# Import the distributed lock from scheduler
sys.path.insert(0, ".")
from app.scheduler.cron import distributed_lock
from app.config import get_settings

# Override Redis URL for local testing
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
settings = get_settings()


def get_test_redis_client():
    """Get a Redis client for testing, using localhost."""
    return redis.Redis.from_url("redis://localhost:6379/0", decode_responses=True)


def test_lock_acquisition():
    """Test that lock can be acquired and released."""
    print("Test 1: Lock Acquisition and Release")
    print("=" * 50)
    
    try:
        with distributed_lock("test_lock", timeout=10):
            print("✅ Lock acquired successfully")
            print("   Holding lock for 2 seconds...")
            time.sleep(2)
            print("   Releasing lock...")
        
        print("✅ Lock released successfully")
        print()
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        return False


def test_lock_exclusion():
    """Test that lock prevents concurrent execution."""
    print("Test 2: Lock Exclusion (Sequential)")
    print("=" * 50)
    
    redis_client = get_test_redis_client()
    lock_name = "test_exclusion_lock"
    
    try:
        # Manually acquire lock
        acquired = redis_client.set(
            f"scheduler_lock:{lock_name}",
            "manual_test",
            nx=True,
            ex=5
        )
        
        if acquired:
            print("✅ First lock acquired manually")
            
            # Try to acquire with context manager (should fail)
            with distributed_lock(lock_name, timeout=5) as lock_acquired:
                if lock_acquired:
                    print("❌ Second lock should NOT have been acquired!")
                    return False
                else:
                    print(f"✅ Second lock correctly blocked")
            
            # Release manual lock
            redis_client.delete(f"scheduler_lock:{lock_name}")
            print("✅ Manual lock released")
            
            # Now it should work
            with distributed_lock(lock_name, timeout=5) as lock_acquired:
                if lock_acquired:
                    print("✅ Lock acquired after first was released")
                else:
                    print("❌ Should have acquired lock after release")
                    return False
            
            print()
            return True
        else:
            print("❌ Could not acquire initial lock")
            print()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        return False


def test_lock_timeout():
    """Test that lock expires after timeout."""
    print("Test 3: Lock Timeout")
    print("=" * 50)
    
    redis_client = get_test_redis_client()
    lock_name = "test_timeout_lock"
    
    try:
        # Acquire lock with 2 second timeout
        acquired = redis_client.set(
            f"scheduler_lock:{lock_name}",
            "timeout_test",
            nx=True,
            ex=2
        )
        
        if acquired:
            print("✅ Lock acquired with 2-second timeout")
            print("   Waiting 3 seconds for expiration...")
            time.sleep(3)
            
            # Check if lock expired
            exists = redis_client.exists(f"scheduler_lock:{lock_name}")
            if not exists:
                print("✅ Lock expired after timeout")
                
                # Should be able to acquire now
                with distributed_lock(lock_name, timeout=5) as lock_acquired:
                    if lock_acquired:
                        print("✅ New lock acquired after expiration")
                    else:
                        print("❌ Could not acquire lock after expiration")
                        return False
                
                print()
                return True
            else:
                print("❌ Lock did not expire")
                print()
                return False
        else:
            print("❌ Could not acquire initial lock")
            print()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        return False


def test_lock_with_job_simulation():
    """Simulate actual scheduler job with lock."""
    print("Test 4: Job Simulation with Lock")
    print("=" * 50)
    
    execution_count = 0
    
    def simulated_job():
        nonlocal execution_count
        execution_count += 1
        print(f"   Job executed (count: {execution_count})")
        time.sleep(1)
    
    try:
        # First execution should succeed
        with distributed_lock("simulated_job", timeout=10) as lock_acquired:
            if lock_acquired:
                print("✅ Lock acquired for first execution")
                simulated_job()
            else:
                print("❌ Could not acquire lock for first execution")
                return False
        
        print(f"✅ First execution completed (count: {execution_count})")
        
        # Second execution should also succeed (lock released)
        with distributed_lock("simulated_job", timeout=10) as lock_acquired:
            if lock_acquired:
                print("✅ Lock acquired for second execution")
                simulated_job()
            else:
                print("❌ Could not acquire lock for second execution")
                return False
        
        print(f"✅ Second execution completed (count: {execution_count})")
        
        if execution_count == 2:
            print("✅ Both executions ran successfully")
            print()
            return True
        else:
            print(f"❌ Unexpected execution count: {execution_count}")
            print()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print()
        return False


def main():
    """Run all distributed lock tests."""
    print("\n" + "=" * 50)
    print("DISTRIBUTED LOCK TEST SUITE")
    print("=" * 50 + "\n")
    
    results = []
    
    # Run all tests
    results.append(("Lock Acquisition", test_lock_acquisition()))
    results.append(("Lock Exclusion", test_lock_exclusion()))
    results.append(("Lock Timeout", test_lock_timeout()))
    results.append(("Job Simulation", test_lock_with_job_simulation()))
    
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
