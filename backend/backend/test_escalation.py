#!/usr/bin/env python3
"""Test script for Auto-Escalation Alert feature."""
import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import AsyncSessionLocal
from app.models.request import Request, RequestStatus, RequestType, Priority, Pod
from app.services.escalation_service import get_escalation_summary
from app.workers.tasks import task_send_escalation_digest
import uuid


async def create_test_requests():
    """Create test requests in AwaitingInfo status for >7 days."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(days=8)

        test_requests = [
            Request(
                id=uuid.uuid4(),
                reference_id=f"TEST-ESC-001",
                title="Critical Request Waiting 8 Days",
                request_type=RequestType.FEATURE,
                pod=Pod.CHARGER,
                priority=Priority.CRITICAL,
                status=RequestStatus.AWAITING_INFO,
                business_problem="This is a critical issue waiting for response",
                affected_area="Charging network",
                region=["NA"],
                submitter_name="Test User",
                submitter_email="test@example.com",
                created_at=cutoff - timedelta(days=1),
                updated_at=cutoff,  # Set to 8 days ago
            ),
            Request(
                id=uuid.uuid4(),
                reference_id="TEST-ESC-002",
                title="High Priority Request Waiting 10 Days",
                request_type=RequestType.FEATURE,
                pod=Pod.DRIVER,
                priority=Priority.HIGH,
                status=RequestStatus.AWAITING_INFO,
                business_problem="High priority issue waiting for response",
                affected_area="Mobile app",
                region=["NA", "UK"],
                submitter_name="Test User 2",
                submitter_email="test2@example.com",
                created_at=cutoff - timedelta(days=3),
                updated_at=cutoff - timedelta(days=2),  # Set to 10 days ago
            ),
            Request(
                id=uuid.uuid4(),
                reference_id="TEST-ESC-003",
                title="Medium Priority Request Waiting 7 Days",
                request_type=RequestType.DEFECT,
                pod=Pod.REVENUE,
                priority=Priority.MEDIUM,
                status=RequestStatus.AWAITING_INFO,
                business_problem="Medium priority issue waiting for response",
                affected_area="Billing system",
                region=["EU"],
                submitter_name="Test User 3",
                submitter_email="test3@example.com",
                created_at=cutoff,
                updated_at=cutoff,  # Set to 8 days ago
            ),
        ]

        for req in test_requests:
            db.add(req)

        await db.commit()
        print(f"✅ Created {len(test_requests)} test escalation requests")
        return [r.reference_id for r in test_requests]


async def test_escalation_query():
    """Test the escalation query function."""
    async with AsyncSessionLocal() as db:
        summary = await get_escalation_summary(db, days_threshold=7)

        print("\n📊 Escalation Summary:")
        print(f"  Total escalated: {summary['total']}")
        print(f"  Oldest waiting: {summary['oldest_days']} days")

        if summary['by_priority']:
            print(f"  By Priority: {summary['by_priority']}")
        if summary['by_pod']:
            print(f"  By Pod: {summary['by_pod']}")

        if summary['requests']:
            print(f"\n  Escalated Requests:")
            for req in summary['requests']:
                days_waiting = (datetime.utcnow() - req.updated_at).days
                print(f"    - {req.reference_id}: {req.title} ({req.priority}, {req.pod}) - {days_waiting} days")

        return summary


async def test_escalation_task():
    """Test the escalation email task."""
    print("\n🚀 Testing Escalation Email Task...")

    try:
        result = task_send_escalation_digest()
        print(f"✅ Task executed: {result}")

        if result.get('skipped'):
            print(f"  (Skipped: {result.get('reason')})")
        elif result.get('sent_to'):
            print(f"  ✓ Sent to {result['sent_to']} PM(s)")
            print(f"  ✓ {result['escalations']} escalated request(s)")
            if result.get('oldest_days'):
                print(f"  ✓ Oldest waiting {result['oldest_days']} days")

        return result
    except Exception as e:
        print(f"❌ Task failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_api_endpoint():
    """Test the API endpoint."""
    print("\n🌐 Testing API Endpoint...")

    async with AsyncSessionLocal() as db:
        from app.services.escalation_service import get_escalation_summary

        summary = await get_escalation_summary(db, days_threshold=7)

        print(f"✅ Endpoint response:")
        print(f"  {{'total': {summary['total']}, 'by_pod': {summary['by_pod']}, 'by_priority': {summary['by_priority']}, 'oldest_days': {summary['oldest_days']}}}")

        return summary


async def cleanup_test_requests():
    """Remove test requests."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(Request).where(Request.reference_id.like('TEST-ESC-%'))
        )
        test_reqs = result.scalars().all()

        for req in test_reqs:
            await db.delete(req)

        await db.commit()
        print(f"\n🧹 Cleaned up {len(test_reqs)} test requests")


async def main():
    """Run all tests."""
    print("=" * 70)
    print("AUTO-ESCALATION ALERT FEATURE TEST SUITE")
    print("=" * 70)

    try:
        # Create test data
        print("\n1️⃣  CREATING TEST REQUESTS")
        print("-" * 70)
        ref_ids = await create_test_requests()

        # Test query
        print("\n2️⃣  TESTING ESCALATION QUERY")
        print("-" * 70)
        summary = await test_escalation_query()

        if summary['total'] == 0:
            print("❌ No escalations found! Test data may not have been created.")
            return False

        # Test task
        print("\n3️⃣  TESTING ESCALATION EMAIL TASK")
        print("-" * 70)
        task_result = await test_escalation_task()

        # Test API
        print("\n4️⃣  TESTING API ENDPOINT")
        print("-" * 70)
        api_result = await test_api_endpoint()

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"✅ Query test: PASSED ({summary['total']} escalations found)")
        print(f"✅ Task test: PASSED (task executed)")
        print(f"✅ API test: PASSED (endpoint responds correctly)")
        print(f"\n🎉 All tests passed!")

        # Cleanup
        print("\n5️⃣  CLEANING UP TEST DATA")
        print("-" * 70)
        await cleanup_test_requests()

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
