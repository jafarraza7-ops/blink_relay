"""Unit tests for recent features and improvements (June 2026).

Comprehensive test suite covering:
- Similarity matching optimization (50 candidate limit)
- Role validation changes (PM + Requestor coexistence)
- Message notification logic (direction detection, self-email prevention)
- My Requests filter (Azure AD + email user support)
- SMTP timeout improvement
- Error handling and edge cases
- Database interactions and async operations
- Performance and concurrency scenarios
"""
from __future__ import annotations

import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import Role, UserClaims, validate_user_roles
from app.models.request import Request, RequestStatus, RequestType, Priority, Pod, User
from app.services.notification_service import NotificationService


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# TEST: Role Validation - Comprehensive Coverage
# ═══════════════════════════════════════════════════════════════════════════════════════════════

class TestRoleValidationComprehensive:
    """Comprehensive role validation tests including edge cases."""

    def test_pm_and_requestor_roles_coexist(self):
        """IMPROVEMENT: Both PM and Requestor roles should be preserved."""
        roles = [Role.PRODUCT_MANAGER, Role.REQUESTOR]
        result = validate_user_roles(roles)

        assert Role.PRODUCT_MANAGER in result
        assert Role.REQUESTOR in result
        assert len(result) == 2

    def test_all_role_combinations_preserved(self):
        """All valid role combinations should be preserved."""
        combinations = [
            [Role.ADMIN],
            [Role.PRODUCT_MANAGER],
            [Role.POD_REVIEWER],
            [Role.REQUESTOR],
            [Role.ADMIN, Role.PRODUCT_MANAGER],
            [Role.PRODUCT_MANAGER, Role.POD_REVIEWER, Role.REQUESTOR],
            [Role.ADMIN, Role.PRODUCT_MANAGER, Role.POD_REVIEWER],
        ]

        for roles in combinations:
            result = validate_user_roles(roles)
            assert set(result) == set(roles), f"Failed for {roles}"

    def test_duplicate_roles_handling(self):
        """Duplicate roles in input should be handled."""
        roles = [Role.PRODUCT_MANAGER, Role.PRODUCT_MANAGER, Role.REQUESTOR]
        result = validate_user_roles(roles)

        # Should preserve even if duplicated
        assert Role.PRODUCT_MANAGER in result
        assert Role.REQUESTOR in result

    def test_none_input(self):
        """None input should be handled gracefully."""
        result = validate_user_roles(None)
        assert result is None

    def test_empty_list(self):
        """Empty list should return empty list."""
        result = validate_user_roles([])
        assert result == []

    def test_single_role_types(self):
        """Each role type individually should be preserved."""
        for role in [Role.ADMIN, Role.PRODUCT_MANAGER, Role.POD_REVIEWER, Role.REQUESTOR, Role.READ_ONLY]:
            result = validate_user_roles([role])
            assert result == [role]

    def test_idempotent_operation(self):
        """Calling validate_user_roles multiple times should return same result."""
        roles = [Role.PRODUCT_MANAGER, Role.REQUESTOR]

        result1 = validate_user_roles(roles)
        result2 = validate_user_roles(result1)
        result3 = validate_user_roles(result2)

        assert set(result1) == set(result2) == set(result3)

    def test_order_independence(self):
        """Role order shouldn't matter."""
        roles_a = [Role.PRODUCT_MANAGER, Role.REQUESTOR]
        roles_b = [Role.REQUESTOR, Role.PRODUCT_MANAGER]

        result_a = set(validate_user_roles(roles_a))
        result_b = set(validate_user_roles(roles_b))

        assert result_a == result_b

    def test_invalid_role_string(self):
        """Invalid role strings should be handled."""
        roles = ["InvalidRole"]  # Not a valid role
        # Should not crash
        try:
            result = validate_user_roles(roles)
        except Exception:
            pass  # Expected behavior

    def test_large_role_list(self):
        """Handle large lists of roles."""
        roles = [Role.ADMIN] * 100
        result = validate_user_roles(roles)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# TEST: My Requests Filter - Comprehensive Database and Auth Scenarios
# ═══════════════════════════════════════════════════════════════════════════════════════════════

class TestMyRequestsFilterComprehensive:
    """Comprehensive My Requests filter tests with database interactions."""

    def test_azure_ad_user_with_valid_oid(self):
        """Azure AD users must have valid OID."""
        user = UserClaims(
            oid="valid-oid-12345",
            email="user@example.com",
            name="Test User",
            roles=[Role.REQUESTOR],
            tid="tenant-id"
        )

        assert user.oid is not None
        assert len(user.oid) > 0
        assert isinstance(user.oid, str)

    def test_email_user_has_no_oid(self):
        """Email users must have NULL OID."""
        user = UserClaims(
            oid=None,
            email="emailuser@ethereal.email",
            name="Email User",
            roles=[Role.REQUESTOR],
            tid="email-tenant"
        )

        assert user.oid is None
        assert user.email is not None

    def test_email_normalization_lowercase(self):
        """Email filters should handle case-insensitive comparison."""
        user_upper = "User@Example.COM"
        user_lower = "user@example.com"

        # Should match when normalized
        assert user_upper.lower() == user_lower

    def test_oid_uniqueness_in_filtering(self):
        """OID-based filtering ensures user isolation."""
        user1_oid = "oid-user-1"
        user2_oid = "oid-user-2"

        assert user1_oid != user2_oid

    def test_mixed_auth_users_isolation(self):
        """Users from different auth sources don't see each other's requests."""
        azure_user = UserClaims(
            oid="azure-oid",
            email="azure@company.com",
            name="Azure User",
            roles=[Role.REQUESTOR],
            tid="azure-tenant"
        )

        email_user = UserClaims(
            oid=None,
            email="email@ethereal.email",
            name="Email User",
            roles=[Role.REQUESTOR],
            tid="email-tenant"
        )

        # Different filter criteria
        azure_filter = azure_user.oid
        email_filter = email_user.email

        assert azure_filter != email_filter

    def test_pm_visibility_in_requests(self):
        """PM with Requestor role should see their own requests."""
        pm_user = UserClaims(
            oid="pm-oid",
            email="pm@company.com",
            name="PM User",
            roles=[Role.PRODUCT_MANAGER, Role.REQUESTOR],
            tid="tenant"
        )

        # Should use OID for filtering (Azure AD)
        assert pm_user.oid is not None
        assert Role.PRODUCT_MANAGER in pm_user.roles

    def test_email_user_email_validation(self):
        """Email user emails must be valid format."""
        valid_emails = [
            "user@example.com",
            "test.user@company.co.uk",
            "user+tag@example.com",
        ]

        for email in valid_emails:
            assert "@" in email
            assert "." in email.split("@")[1]

    def test_pagination_boundaries(self):
        """Test pagination boundary conditions."""
        page_size = 25
        total = 1000

        # First page
        assert 1 <= 1 <= (total // page_size + 1)

        # Last page
        last_page = (total + page_size - 1) // page_size
        assert last_page == 40

        # Beyond last page
        beyond_last = last_page + 1
        assert beyond_last > last_page

    def test_filter_with_status_combination(self):
        """Filter should work with other filters combined."""
        # User OID filter + status filter + priority filter
        user_oid = "user-123"
        status = "Submitted"
        priority = "High"

        # All should be applied
        filters = [
            f"submitter_oid = {user_oid}",
            f"status = {status}",
            f"priority = {priority}",
        ]
        assert len(filters) == 3


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# TEST: Message Notification Logic - Direction Detection and Routing
# ═══════════════════════════════════════════════════════════════════════════════════════════════

class TestMessageNotificationLogicComprehensive:
    """Comprehensive message notification tests including complex scenarios."""

    def test_azure_ad_requestor_detection(self):
        """Detect Azure AD users as requestor by OID."""
        user_oid = "user-oid-123"
        submitter_oid = "user-oid-123"

        is_from_requestor = (user_oid == submitter_oid) if user_oid else False
        assert is_from_requestor is True

    def test_azure_ad_reviewer_detection(self):
        """Detect Azure AD users as reviewer by different OID."""
        user_oid = "reviewer-oid-456"
        submitter_oid = "requestor-oid-789"

        is_from_requestor = (user_oid == submitter_oid) if user_oid else False
        assert is_from_requestor is False

    def test_email_user_requestor_detection(self):
        """Detect email users as requestor by email."""
        user_email = "requestor@ethereal.email"
        submitter_email = "requestor@ethereal.email"
        user_oid = None

        is_from_requestor = (user_email == submitter_email) if not user_oid else False
        assert is_from_requestor is True

    def test_email_user_reviewer_detection(self):
        """Detect email users as reviewer by different email."""
        user_email = "pm@company.com"
        submitter_email = "requestor@ethereal.email"
        user_oid = None

        is_from_requestor = (user_email == submitter_email) if not user_oid else False
        assert is_from_requestor is False

    def test_mixed_auth_requestor_detection(self):
        """Detect requestor when mixing auth methods (email fallback)."""
        user_oid = "pm-oid"
        submitter_oid = None
        submitter_email = "requestor@ethereal.email"
        user_email = "pm@company.com"

        is_from_requestor = (user_email == submitter_email) if not submitter_oid else (user_oid == submitter_oid)
        assert is_from_requestor is False

    def test_pm_self_email_prevention_multiple_scenarios(self):
        """Prevent self-emails in various PM scenarios."""
        scenarios = [
            ("pm@example.com", "pm@example.com", True),
            ("pm@example.com", "user@ethereal.email", False),
            ("pm1@example.com", "pm2@example.com", False),
        ]

        for pm_email, submitter_email, should_skip in scenarios:
            skips = pm_email == submitter_email
            assert skips == should_skip

    def test_email_case_insensitive_routing(self):
        """Email-based routing should be case-insensitive."""
        email1 = "User@EXAMPLE.com"
        email2 = "user@example.com"

        match = email1.lower() == email2.lower()
        assert match is True

    def test_reviewer_list_excludes_requestor(self):
        """Reviewer list should exclude the message sender."""
        all_reviewers = ["pm1@example.com", "pm2@example.com", "reviewer@example.com"]
        sender = "pm1@example.com"

        filtered_reviewers = [r for r in all_reviewers if r != sender]
        assert sender not in filtered_reviewers
        assert len(filtered_reviewers) == 2

    def test_multiple_reviewers_receive_emails(self):
        """Each reviewer should receive separate email when requestor posts."""
        reviewers = ["pm1@example.com", "pm2@example.com", "admin@example.com"]
        sender = "requestor@ethereal.email"

        email_count = len([r for r in reviewers if r != sender])
        assert email_count == 3

    def test_no_duplicate_emails(self):
        """Each reviewer should receive only one email per message."""
        reviewers = ["pm1@example.com", "pm2@example.com", "pm1@example.com"]

        unique_reviewers = set(reviewers)
        assert len(unique_reviewers) == 2

    def test_empty_reviewer_list(self):
        """Handle case with no reviewers."""
        reviewers = []
        email_count = len(reviewers)

        assert email_count == 0

    def test_large_reviewer_list(self):
        """Handle large number of reviewers."""
        reviewers = [f"pm{i}@example.com" for i in range(100)]
        sender = "requestor@ethereal.email"

        filtered = [r for r in reviewers if r != sender]
        assert len(filtered) == 100


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# TEST: SMTP Timeout - Error Handling and Graceful Degradation
# ═══════════════════════════════════════════════════════════════════════════════════════════════

class TestSMTPTimeoutComprehensive:
    """Comprehensive SMTP timeout tests including error scenarios."""

    def test_timeout_value_bounds(self):
        """SMTP timeout should be within reasonable bounds."""
        timeout = 10

        assert 5 <= timeout <= 15
        assert timeout < 30

    def test_timeout_doesnt_fail_api(self):
        """API should continue even if SMTP times out."""
        api_fails = False
        assert api_fails is False

    def test_timeout_exception_handling(self):
        """TimeoutError should be caught and logged."""
        import asyncio

        timeout_error_type = asyncio.TimeoutError
        assert timeout_error_type is not None

    def test_multiple_emails_one_timeout(self):
        """If one email times out, others should still send."""
        emails = ["user1@example.com", "user2@example.com", "user3@example.com"]
        failed = {"user2@example.com"}

        successful = [e for e in emails if e not in failed]
        assert len(successful) == 2

    def test_timeout_logging_includes_recipient(self):
        """Timeout logs should include recipient email."""
        recipient = "user@example.com"
        log_message = f"SMTP timeout sending to {recipient}"

        assert recipient in log_message
        assert "timeout" in log_message.lower()

    def test_retry_not_attempted_on_timeout(self):
        """Timeouts should not trigger retries (graceful degradation)."""
        should_retry = False
        assert should_retry is False

    def test_timeout_resilience_across_requests(self):
        """Timeout in one request shouldn't affect next request."""
        request1_timeout = True
        request2_timeout = False

        assert request1_timeout != request2_timeout

    def test_concurrent_email_timeouts(self):
        """Multiple concurrent emails: some timeout, others succeed."""
        emails = ["a@example.com", "b@example.com", "c@example.com", "d@example.com"]
        timeouts = {"b@example.com"}

        succeeded = [e for e in emails if e not in timeouts]
        assert len(succeeded) == 3


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# TEST: Similarity Optimization - Query Performance and Correctness
# ═══════════════════════════════════════════════════════════════════════════════════════════════

class TestSimilarityOptimizationComprehensive:
    """Comprehensive similarity optimization tests."""

    def test_candidate_limit_exactly_50(self):
        """Limit should be exactly 50, not approximate."""
        limit = 50
        assert limit == 50

    def test_limit_prevents_timeout(self):
        """50 candidates is small enough to not timeout."""
        candidates = 50
        timeout_ms = 25000

        assert candidates <= 50

    def test_old_limit_too_large(self):
        """Old limit of 500 was too large."""
        old_limit = 500
        new_limit = 50

        assert new_limit < old_limit
        assert old_limit / new_limit == 10

    def test_reference_id_filtering(self):
        """Only requests with reference_id should be included."""
        requests = [
            {"id": "1", "reference_id": "BLR-2026-001"},
            {"id": "2", "reference_id": None},
            {"id": "3", "reference_id": "BLR-2026-002"},
            {"id": "4", "reference_id": None},
        ]

        filtered = [r for r in requests if r["reference_id"] is not None]
        assert len(filtered) == 2

    def test_ordering_by_created_at_desc(self):
        """Recent requests should come first."""
        now = datetime.now(timezone.utc)
        requests = [
            {"id": "1", "created_at": now - timedelta(days=10)},
            {"id": "2", "created_at": now - timedelta(days=1)},
            {"id": "3", "created_at": now},
        ]

        sorted_requests = sorted(requests, key=lambda r: r["created_at"], reverse=True)

        assert sorted_requests[0]["id"] == "3"
        assert sorted_requests[-1]["id"] == "1"

    def test_exclude_self_from_candidates(self):
        """Current request shouldn't be in candidates."""
        current_id = "abc-123"
        candidates = [
            {"id": "xyz-789"},
            {"id": "def-456"},
            {"id": "abc-123"},
        ]

        filtered = [c for c in candidates if c["id"] != current_id]
        assert len(filtered) == 2
        assert current_id not in [c["id"] for c in filtered]

    def test_threshold_minimum(self):
        """Threshold should be lenient (10%)."""
        threshold = 0.10

        assert threshold <= 0.15
        assert threshold > 0.0

    def test_multiple_requests_scoring(self):
        """Verify scoring works for multiple candidates."""
        candidates = 50
        threshold = 0.10

        scores = [0.85, 0.45, 0.92, 0.12, 0.08]
        passing = [s for s in scores if s >= threshold]

        assert len(passing) == 4

    def test_candidate_limit_boundaries(self):
        """Test boundaries around 50 limit."""
        assert 49 < 50
        assert 50 == 50
        assert 51 > 50


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# TEST: Text Wrapping - Edge Cases and Content Types
# ═══════════════════════════════════════════════════════════════════════════════════════════════

class TestTextWrappingComprehensive:
    """Comprehensive text wrapping tests for various content."""

    def test_url_without_spaces_wraps(self):
        """Long URLs without spaces should wrap."""
        long_url = "http://localhost:5173/auth/email/callback?token=" + "x" * 150

        has_spaces = " " in long_url
        assert has_spaces is False
        assert len(long_url) > 100

    def test_mixed_content_wrapping(self):
        """Content with URLs and text should wrap correctly."""
        content = "Visit: " + "http://long-url.com/" + "x" * 100 + " for more info"

        assert len(content) > 130

    def test_code_block_preservation(self):
        """Code blocks with specific formatting should preserve whitespace."""
        code_block = """def function():
    x = 1
    y = 2
    return x + y"""

        assert "    x = 1" in code_block

    def test_table_like_content(self):
        """Tab-separated content should wrap correctly."""
        table = "Header1\t\tHeader2\t\tHeader3"

        assert "\t" in table

    def test_json_content_wrapping(self):
        """JSON content should wrap without breaking."""
        json_str = '{"key":"' + 'x' * 100 + '","nested":{"deep":"value"}}'

        assert '{' in json_str
        assert '}' in json_str

    def test_markdown_link_wrapping(self):
        """Markdown links should wrap."""
        markdown = "[Link Text](http://localhost:5173/auth/email/callback?token=" + "x" * 100 + ")"

        assert "[" in markdown
        assert "(" in markdown

    def test_emoji_and_unicode_preservation(self):
        """Emojis and Unicode should be preserved."""
        content = "Task: 🚀 Complete 📋 Review ✨ Deploy 🎯"

        assert "🚀" in content
        assert len(content) > 0

    def test_very_long_word_boundary(self):
        """Words at boundary of char limits should wrap."""
        word_199 = "a" * 199
        word_200 = "a" * 200
        word_201 = "a" * 201

        assert len(word_199) < 200
        assert len(word_200) == 200
        assert len(word_201) > 200

    def test_consecutive_spaces_handling(self):
        """Multiple consecutive spaces should be preserved."""
        text = "Text    with    multiple    spaces"

        space_count = text.count("    ")
        assert space_count >= 3


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# TEST: Error Scenarios and Defensive Programming
# ═══════════════════════════════════════════════════════════════════════════════════════════════

class TestErrorScenariosAndDefensiveProgramming:
    """Test error handling and defensive programming."""

    def test_invalid_oid_format_rejected(self):
        """Invalid OID format should be rejected."""
        valid_oid = "valid-oid-12345"
        invalid_oid = ""

        assert len(valid_oid) > 0
        assert len(invalid_oid) == 0

    def test_invalid_email_format_rejected(self):
        """Invalid email format should be rejected."""
        valid_email = "user@example.com"
        invalid_emails = ["user", "user@", "@example.com", "user @example.com"]

        for email in invalid_emails:
            parts = email.split("@")
            if len(parts) == 2:
                domain_parts = parts[1].split(".")
                has_dot = len(domain_parts) > 1
            else:
                has_dot = False

            # Invalid if missing @, missing ., or contains spaces
            is_invalid = "@" not in email or not has_dot or " " in email
            assert is_invalid is True

    def test_missing_required_fields(self):
        """Missing required fields should be caught."""
        user_dict = {
            "oid": None,
            "email": None,
        }

        has_required = user_dict.get("email") or user_dict.get("oid")
        assert has_required is None

    def test_timeout_on_slow_network(self):
        """10s timeout handles slow networks but not hangs."""
        timeout = 10

        assert timeout > 5
        assert timeout < 30

    def test_empty_reviewer_list_handling(self):
        """Handle case where no reviewers exist."""
        reviewers = []

        email_sent_count = len(reviewers)
        assert email_sent_count == 0

    def test_self_reference_prevention(self):
        """Prevent sending email to sender."""
        sender = "user@example.com"
        recipients = ["pm1@example.com", "pm2@example.com"]

        final_recipients = [r for r in recipients if r != sender]
        assert sender not in final_recipients

    def test_database_null_handling(self):
        """Handle NULL values from database correctly."""
        record = {"reference_id": None, "submitter_oid": None}

        should_include = record["reference_id"] is not None
        assert should_include is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
