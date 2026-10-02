# Roles and permissions (RBAC)

Authorization is **permission-based** and **centralized** in
`backend/app/rbac/catalog.py`, which is reviewed like any other code and
covered by tests. Endpoints declare the permission they need:

```python
@router.get("/admin/users")
def admin_list_users(_: Principal = Depends(require_permission(Permission.USERS_READ))): ...
```

Resource-level rules (ownership, agency membership) live in each domain's
service/policy functions — a permission says *what kind* of action is allowed,
the policy says *on which records*.

## Roles

| Role | Rank | Typical holder |
| --- | --- | --- |
| `SUPER_ADMIN` | 100 | Platform owner. Created only with the CLI. |
| `ADMIN` | 90 | Operations staff. |
| `MODERATOR` | 70 | Trust & safety: reviews listings and reports. |
| `AGENCY_OWNER` | 50 | Owner of a real-estate office. |
| `AGENT` | 40 | Agent working for an agency. |
| `PROPERTY_OWNER` | 20 | Individual listing their own property. |
| `CUSTOMER` | 10 | Every account (buyers/tenants). |

A user may hold several roles; permissions are the union.

## Permissions

| Permission | CUSTOMER | PROPERTY_OWNER / AGENT | AGENCY_OWNER | MODERATOR | ADMIN | SUPER_ADMIN |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| `inquiries.create`, `favorites.manage`, `saved_searches.manage`, `reports.create`, `ai.use`, `agencies.create`¹ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `properties.create`, `leads.read_own`, `leads.manage`, `ai.author`, `analytics.own` | | ✓ | ✓ | | ✓ | ✓ |
| `leads.read_agency`, `analytics.agency` | | | ✓ | | ✓ | ✓ |
| `users.read`, `properties.moderate`, `properties.verify`, `properties.read_private`, `agencies.verify`, `reports.review`, `audit.read` | | | | ✓ | ✓ | ✓ |
| `users.suspend`, `roles.assign`, `properties.manage_any`, `agencies.manage_any`, `leads.read_any`, `leads.configure`, `ai.admin`, `analytics.all`, `automation.manage` | | | | | ✓ | ✓ |
| `settings.manage` | | | | | | ✓ |

¹ Any account may *apply* to open an agency. The creator becomes
`AGENCY_OWNER` of an **unverified** agency; verification (`agencies.verify`)
is required before the agency badge is shown.

Object-level rules (who may edit/publish a listing, manage agency members,
see private data) live in `backend/app/policies.py` and are tested in
`tests/test_properties.py` and `tests/test_agencies.py`.

## Hierarchy (privilege-escalation protection)

- An actor can suspend/reactivate a user or change their roles **only if the
  actor's highest rank is strictly greater** than the target's highest rank.
- Roles can only be granted or revoked **below** the actor's own rank: ADMIN
  can grant up to MODERATOR; only SUPER_ADMIN can grant ADMIN; nobody can grant
  SUPER_ADMIN through the API.
- Nobody can act on their own account through admin endpoints.
- `CUSTOMER` cannot be removed.
- Every grant, revocation, suspension and reactivation is written to
  `audit_logs` in the same transaction.

## Database

`roles` mirrors the catalog (foreign-key target, Arabic/English names, rank);
`user_roles` stores assignments (`granted_by_id`, `granted_at`). A test fails
if `roles` and the catalog ever differ. Because permissions are resolved per
request, role changes apply on the user's next request without re-login.

## Endpoints

| Method | Path | Permission |
| --- | --- | --- |
| GET | `/api/v1/rbac/roles` | signed in |
| GET | `/api/v1/admin/users` | `users.read` |
| GET | `/api/v1/admin/users/{id}` | `users.read` |
| POST | `/api/v1/admin/users/{id}/suspend` | `users.suspend` + hierarchy |
| POST | `/api/v1/admin/users/{id}/reactivate` | `users.suspend` + hierarchy |
| PUT | `/api/v1/admin/users/{id}/roles/{role}` | `roles.assign` + hierarchy |
| DELETE | `/api/v1/admin/users/{id}/roles/{role}` | `roles.assign` + hierarchy |
| GET | `/api/v1/admin/audit-logs` | `audit.read` |
