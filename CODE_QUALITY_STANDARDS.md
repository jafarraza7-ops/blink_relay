# Code Quality Standards

This document establishes the code quality principles that guide all development work on Blink Relay. Every commit, pull request, and code review should evaluate changes against these standards.

---

## 1. Readability & Structure

### Naming Conventions
- **Variables/Functions:** Use clear, descriptive names that explain intent
  - ✅ `validate_user_roles()` — immediately clear what it does
  - ❌ `validate()` — too vague, requires reading implementation
  
- **Classes:** Noun-based, singular or plural as appropriate
  - ✅ `NotificationService`, `EmailLoginToken`
  - ❌ `Notifier`, `TokenManager` (less clear responsibility)

- **Constants:** UPPER_SNAKE_CASE, explain what value represents
  - ✅ `SMTP_TIMEOUT_SECONDS = 10` — immediately clear
  - ❌ `TIMEOUT = 10` — unclear context

### Code Formatting
- Consistent indentation (4 spaces Python, 2 spaces JavaScript/TypeScript)
- Maximum line length: 100 characters (readability without horizontal scrolling)
- Blank lines separate logical blocks
- Use linters automatically:
  - Python: `Black`, `isort`, `flake8`
  - TypeScript/JavaScript: `ESLint`, `Prettier`

### Function Design
- **Single Responsibility Principle (SRP):** Each function does one thing
  - ✅ `create_login_token()` — only creates tokens
  - ❌ `authenticate_user()` — creates token, sends email, logs in, updates DB (too many concerns)

- **Function Length:** Keep under 30-40 lines; complex logic gets extracted
- **Parameters:** Max 4-5; if more needed, consider grouping into objects

---

## 2. Maintainability

### DRY Principle (Don't Repeat Yourself)
- **Identify duplicated logic:** If same code appears 3+ times, extract to shared function
- **Duplicated patterns:** Common patterns → shared utilities/helpers
  - ✅ Extract `convert_timestamp_to_utc()` used in 5 places
  - ❌ Same timestamp logic repeated across 5 functions

### Modular & Loosely Coupled Design
- Components should not depend on implementation details of others
- Use dependency injection for testability
  - ✅ `send_email(notification_service, email)` — can mock service
  - ❌ `send_email(email)` that imports NotificationService internally

### Separation of Concerns
```
Backend:
- app/models/        → Data models (Request, User, Message)
- app/services/      → Business logic (SimilarityService, NotificationService)
- app/api/           → HTTP endpoints (requests.py, auth.py)
- app/workers/       → Async tasks (email_tasks.py)
- app/core/          → Configuration, security, database

Frontend:
- src/pages/         → Full-page components (SubmitPage, DashboardPage)
- src/components/    → Reusable UI components (Button, Card, Form)
- src/hooks/         → Business logic (useAuth, useRequests)
- src/lib/           → Utilities (api.ts, types.ts, constants.ts)
```

### Named Constants (No Magic Numbers/Strings)
- ✅ `SMTP_TIMEOUT_SECONDS = 10` — named, documented
- ❌ `timeout = 10` — magic number, unexplained

```python
# app/services/similarity_service.py
CANDIDATE_LIMIT = 50  # Reduced from 500 to prevent frontend timeout
MIN_SIMILARITY_THRESHOLD = 0.10  # 10% threshold for cross-domain matching
TITLE_WEIGHT = 0.60
PROBLEM_WEIGHT = 0.30
AREA_WEIGHT = 0.10
```

---

## 3. Reliability

### Error Handling
- **Catch and handle** predictable errors; don't let them bubble up
- **Log at appropriate level:** DEBUG (info), INFO (normal), WARNING (concerning), ERROR (failure)
- **Graceful degradation:** If optional operation fails, continue
  - ✅ `except TimeoutError: logger.warning(...); continue` — email times out but request succeeds
  - ❌ `except TimeoutError: raise` — email timeout crashes entire endpoint

### Edge Cases & Input Validation
- **Validate all inputs** at system boundaries (API endpoints, file uploads)
- **Test edge cases:** empty strings, None values, boundary values (0, 200, 201)
- **Defensive programming:** Don't assume inputs are safe

```python
# app/api/requests.py - list_my_requests
if user.oid:
    submitter_filter = Request.submitter_oid == user.oid
else:
    submitter_filter = Request.submitter_email == user.email

# Handles both Azure AD (OID) and email (no OID) users — defensive
```

### Testing Coverage
- **Unit tests:** Core logic in isolation (18+ per feature)
- **Integration tests:** Multi-component workflows (3+ per feature)
- **Edge case tests:** Boundaries, nulls, empty data (5+ per feature)
- **Error scenario tests:** Failures, timeouts, invalid inputs (5+ per feature)
- **Real-world tests:** Practical usage examples (4+ per feature)

---

## 4. Documentation

### Comments: Explain *Why*, Not *What*
- ❌ Bad: `x = 50  # Set x to 50`
- ✅ Good: `SIMILARITY_CANDIDATE_LIMIT = 50  # Reduced from 500 to prevent >30s frontend timeout`

- ❌ Bad: `if user.oid == submitter_oid: is_from_requestor = True`
- ✅ Good: `# IMPROVEMENT: Detect Azure AD users as requestor by matching OID`

### Docstrings for Functions/Classes
- All public functions should have docstrings
- Include: purpose, arguments, return value, raises (if applicable)

```python
def validate_user_roles(roles: list[str]) -> list[str]:
    """Validate and normalize user roles.

    FEATURE: Allow PMs to be Requestors (removed mutual exclusivity)
    Reasoning: PMs should be able to create their own requests and receive notifications.

    Args:
        roles: List of role strings assigned to user

    Returns:
        Validated list of roles (no filtering applied in current implementation)
    """
```

### README & Architecture
- Setup instructions (requirements, env vars, how to run)
- How features work (magic links, similarity matching, email notifications)
- File structure and module organization
- Key architectural decisions and trade-offs

---

## 5. Code Reviews & Collaboration

### Pull Request Checklist
Before merging, verify:
- [ ] Clear, descriptive PR title and description
- [ ] Code follows naming conventions and style
- [ ] No duplicated logic (DRY principle)
- [ ] Proper error handling
- [ ] Comprehensive tests (unit, integration, edge cases)
- [ ] Comments explain *why*, not *what*
- [ ] No hardcoded values (use constants)
- [ ] Related memory updated (if needed)

### Commit Messages
- Clear, actionable description
- Include *why*, not just *what*
- Reference related files/changes

```
✅ Good:
"Add comprehensive unit tests for recent improvements (200+ tests)

Backend: 150+ tests covering role validation, message notification, SMTP timeout
Frontend: 70+ tests for text wrapping, accessibility, real-world scenarios
All tests follow pytest/vitest patterns with clear assertions and edge cases"

❌ Bad:
"Add tests"
"Update code"
"Fix stuff"
```

### Enforce Standards Automatically
- **Pre-commit hooks:** Run linters, tests before commit
- **CI/CD pipelines:** Tests run on every push
- **ESLint/Black:** Auto-fix formatting
- **Code coverage:** Track and maintain >80% coverage

---

## 6. Performance & Security

### Avoid Unnecessary Complexity
- ✅ `CANDIDATE_LIMIT = 50` — simple limit prevents timeout
- ❌ Complex caching strategy without clear benefit

### Identify & Remove Bottlenecks
- Similarity matching: Reduced 500→50 candidates (10x faster)
- SMTP: Added 10s timeout (prevents hanging)
- Database: Order by created_at DESC (prioritize recent)

### Input Sanitization
- Validate email format before use
- Check OID format (non-empty string)
- Escape strings in database queries
- Never trust user input at API boundaries

### Least Privilege & Security
- Users only see their own requests (filtered by OID or email)
- PM/Requestor roles properly validated
- Sensitive operations logged but not exposed
- Timeouts prevent resource exhaustion

### Keep Dependencies Updated
- Regular security updates to packages
- Remove unused dependencies
- Pin versions in requirements.txt/package.json

---

## 7. Tooling & Automation

### Linters & Formatters
**Python:**
```bash
black app/          # Format code
isort app/          # Sort imports
flake8 app/         # Lint
mypy app/           # Type checking
```

**TypeScript/JavaScript:**
```bash
eslint src/         # Lint
prettier --write src/  # Format
```

### CI/CD Automation
- Tests run on every commit
- Linters check code style
- Type checkers verify types
- Coverage reports track quality

### Type Safety
- Python: Use type hints
  ```python
  def validate_user_roles(roles: list[str]) -> list[str]:
  ```
- TypeScript: Leverage strict mode
  ```typescript
  interface UserClaims {
    oid: string | null
    email: string
    roles: string[]
  }
  ```

---

## 8. Refactoring Habits

### Regular Cleanup
- Every sprint: Remove unused code
- Every quarter: Address technical debt
- Replace magic numbers with constants
- Simplify overly complex logic

### Identifying Opportunities
- ✅ "This function is 50 lines and does 3 things → split it"
- ✅ "These 5 functions have identical error handling → extract helper"
- ✅ "This value appears in 10 places → make it a constant"

### Dead Code Removal
- Remove unused imports
- Delete unreferenced functions
- Clean up old experiment branches
- Archive deprecated patterns

---

## Applying These Standards

### On Every Commit
1. **Readability:** Are function/variable names clear?
2. **Maintainability:** Is there duplicated logic to extract?
3. **Reliability:** Are edge cases handled? Is there proper error handling?
4. **Documentation:** Are complex decisions documented (comments explain *why*)?
5. **Testing:** Is new logic covered by tests?

### On Every Pull Request
1. **Code review:** Do changes follow these standards?
2. **Style:** Does it match the codebase?
3. **Tests:** Are they comprehensive (unit, integration, edge cases)?
4. **Documentation:** Are comments and docstrings updated?
5. **Architecture:** Does it maintain separation of concerns?

### On Every Release
1. **Quality metrics:** Test coverage, lint issues, type errors
2. **Performance:** Are there new bottlenecks?
3. **Security:** Any new vulnerabilities?
4. **Technical debt:** What should be refactored next?

---

## Example: Applying Standards

### Feature: Role Validation
**Before (Low Quality):**
```python
def validate_roles(r):
    if "PM" in r and "Req" in r:
        r.remove("Req")
    return r
```

**After (High Quality):**
```python
def validate_user_roles(roles: list[str]) -> list[str]:
    """Validate and normalize user roles.

    FEATURE: Allow PMs to be Requestors (removed mutual exclusivity)
    Reasoning: PMs should be able to create their own requests and receive notifications.
    Previous behavior: ProductManager role automatically removed Requestor role.
    Current behavior: Both roles can coexist for the same user.

    Args:
        roles: List of role strings assigned to user

    Returns:
        Validated list of roles (no filtering applied)
    """
    if not roles:
        return roles
    return roles
```

**Tests Added:**
- Unit: PM+Requestor coexist, single roles preserved, None handled
- Integration: PM creates request, sees it in My Requests, receives PM notifications
- Edge cases: Duplicate roles, empty list, very long list
- Documentation: Explains why this matters

---

## Measuring Success

- ✅ **Code coverage:** >80% (unit + integration tests)
- ✅ **Lint issues:** 0 errors, <5 warnings
- ✅ **Type errors:** 0 (strict mode)
- ✅ **Duplicated code:** <5% (DRY maintained)
- ✅ **Avg function size:** <30 lines (focused, readable)
- ✅ **Avg code review time:** Able to understand changes in <10 min
- ✅ **Incident rate:** <1 per sprint (reliability)
- ✅ **On-time delivery:** >90% (maintainability helps speed)

---

## Remember

**Good code is:**
- Easy to read (clear names, short functions, good structure)
- Easy to maintain (DRY, modular, documented)
- Easy to test (small, focused, testable)
- Easy to refactor (loose coupling, clear separation of concerns)
- **Fast to develop** (reusable components, clear patterns, good tooling)

Every line you write today affects code written six months from now. Code quality is not a feature — it's a foundation.
