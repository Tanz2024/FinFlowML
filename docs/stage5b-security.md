# Stage 5B: authentication, RBAC, and tenant isolation

Stage 5B adds local application authentication and organization-scoped access. It does not change Stage 4 model artifacts, adapters, checkpoints, or benchmark reports.

## Configuration and bootstrap

Set `DATABASE_URL`, `AUTH_SECRET` (a random secret of at least 32 characters), and optionally `ACCESS_TOKEN_MINUTES` in `.env`. Passwords are hashed with Argon2id when `argon2-cffi` is installed; the local test fallback uses scrypt so the test suite remains runnable in a minimal environment. Production deployments must install the pinned Argon2 dependency.

No production account or password is created by migrations. Existing rows receive nullable organization keys and remain quarantined until an operator performs an explicit, audited assignment to an organization. This avoids silently granting legacy financial data to an arbitrary user.

The login endpoint is `POST /auth/login` with `{email, password}` and returns a short-lived bearer token. Tokens are signed with `AUTH_SECRET`; rotate the secret to invalidate all outstanding tokens. Login responses do not reveal whether an email exists. Rate limiting, MFA, email verification, password reset, and centralized audit shipping remain deployment requirements.

## Roles

| Role | Permissions |
|---|---|
| admin | read, review, approve, accounting, manual expense, user administration |
| reviewer | read, correct, approve/reject receipts |
| accountant | read, accounting, explicitly authorized manual expense creation |
| viewer | read-only |

Authorization is enforced in FastAPI dependencies and every tenant-owned query includes the authenticated organization. Related IDs (receipt/category, invoice/customer, payment/invoice) are checked against that same organization. Receipt correction and approval/rejection store the authenticated actor. Approval is idempotent and the receipt-to-expense uniqueness constraint prevents duplicate expenses under concurrent requests.

`POST /expenses` is intentionally not a generic extraction bypass: the referenced receipt must belong to the organization and already be approved. Explicit manual accounting remains available to accountant/admin roles for approved receipts.

## Local demonstration

Install `requirements.txt`, run migrations, create an organization/user/membership through an operator-only bootstrap script or administrative SQL procedure, then log in and pass `Authorization: Bearer <token>` to the API. For macOS-only demos set `FINFLOW_MOCK_EXTRACTION=true`; the response is explicitly marked `mock: true` and is not AI inference. The demo review screen still sends corrections and approval through the authenticated API; browser role checks are convenience only.

## Migration and security limitations

Migrations are additive. Before applying `0006_auth_and_tenants`, inventory legacy rows and prepare an explicit organization assignment plan. Do not assign them to a user by default. PostgreSQL integration should be used for migration and concurrency verification because SQLite does not reproduce production locking behavior. This implementation is local-only until TLS, deployment secret management, rate limiting, MFA, authentication audit retention, authorization administration, and complete tenant-level database policies are added.
