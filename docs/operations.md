# Operating guide

[Back to the project overview](../README.md)

## Commands and change control

```bash
python app.py --help
python app.py --demo reviews
python app.py --demo assignments --role 11111111-1111-4111-8111-111111111111
python app.py --demo details 33333333-3333-4333-8333-333333333333
python app.py --demo create \
  --role 11111111-1111-4111-8111-111111111111 \
  --reviewer 44444444-4444-4444-8444-444444444444 \
  --assignment eligible --frequency quarterly --start 2026-10-17 --dry-run
python app.py --demo delete 33333333-3333-4333-8333-333333333333 --dry-run
```

Read commands show compact tables by default. Add `--json` after `roles`, `reviews`, `assignments` or `details` to receive JSON with no banner; full IDs and fields are preserved. Running `python app.py` without arguments shows help without authentication.

Use one role per create. Repeat `--reviewer USER_UUID` for up to ten explicit reviewers. UUID syntax is checked locally; reviewer existence, eligibility and independence must be verified by the operator. The service can reject invalid reviewer objects. Automatic self-review and bulk creation have been removed.

`create` and `delete` are dry runs by default. Add `--apply` to print the complete plan and require an exact typed phrase (`POST <plan hash>` or `DELETE <plan hash>`). The hash covers the tenant, target and payload. A wrong phrase or EOF sends no write. A delete removes the **entire review series**; the tool rereads its definition immediately before deletion and aborts if it changed. This check is not atomic: Graph offers no transaction across the preview and delete.

Schedules: one-time (default, seven days), weekly (three-day review), monthly, quarterly and every six months (seven-day review). The start date is UTC today in live mode. One-time reviews omit the recurrence pattern; repeating reviews use only the access-review-supported weekly/monthly properties. Monthly schedules use the start day; use days 1–28 when a date must exist in every month. Recurring series have no end date; this is visible in the plan.

## Live configuration and minimum permissions

Live mode is opt-in: omit `--demo`. Configure a Microsoft Entra app registration using **application permissions** and tenant admin consent. This CLI uses client credentials, not delegated user login.

| Operation | Least application permissions needed by this tool |
| --- | --- |
| `roles`, `assignments` | `RoleManagement.Read.Directory` |
| `reviews`, `details`, deletion preview | `AccessReview.Read.All` |
| Creation preview (reads role definition) | `RoleManagement.Read.Directory` |
| Create | `RoleManagement.Read.Directory` + `AccessReview.ReadWrite.All` |
| Delete | `AccessReview.ReadWrite.All` |

Use a separate read-only app registration for inspection. `AccessReview.ReadWrite.All` supersedes the read permission for writes. Do not grant `RoleManagement.ReadWrite.Directory` or `Directory.Read.All` for these commands. The tool does not resolve assignment principal names/types or fetch user profiles, so it needs no extra user/group read permission. `assignments` lists direct active role assignments by principal UUID, including scoped assignments; it does not enumerate eligible assignments or expand group members.

Inject these through your environment or a secret manager:

```text
AZURE_TENANT_ID=<directory UUID>
AZURE_CLIENT_ID=<application UUID>
AZURE_CLIENT_SECRET=<secret value>
```

Never put credentials in source, command arguments, screenshots or transcripts. `.env` files are ignored but are **not loaded** automatically. The token remains in process memory; there is no token cache or credential file. Keep a short-lived secret and rotate it through your organization's process. An expired token produces a clear error; rerun the command to authenticate again.

Tenant access-review licensing and feature availability are also required. Microsoft describes licensing for groups/apps separately from Entra role reviews; confirm the current entitlement for your tenant in the [access reviews overview](https://learn.microsoft.com/en-us/entra/id-governance/access-reviews-overview). A successful token is not proof that review creation is licensed or authorized.

## Review scope and conservative defaults

The payload follows Microsoft's [documented role scopes, example 12](https://learn.microsoft.com/en-us/graph/accessreviews-scope-concept):

- `all`: users with active or eligible assignments to one directory role.
- `active`: assigned active user schedule instances (`assignmentType eq 'Assigned'`), excluding PIM activations.
- `eligible`: eligible user schedule instances.

These scopes do not claim coverage of service principals, group membership, Azure resource RBAC, or all indirect access. There is no hardcoded authoritative list of privileged roles. Inspect the actual role definition and choose the UUID explicitly.

Automatic application of decisions, default decisions, email notifications and reminders are disabled. An administrator must apply completed review decisions separately. The CLI never applies decisions or changes accounts, group membership or role assignments.

## Reliability and local security model

- Connect/read timeouts: 5/30 seconds for authentication and Graph calls.
- Pagination follows `@odata.nextLink`, rejects cycles and fails at 100 pages rather than returning partial results as complete.
- Only the exact global Graph HTTPS origin and `/v1.0/` paths may receive the token. Redirects and unsafe next links are rejected. The configured cloud is Microsoft Graph global.
- At most three attempts: explicit HTTP 429 responses respect `Retry-After` (seconds or HTTP date); GET also retries 502/503/504. Missing/invalid delay uses bounded backoff. Delays above 30 seconds cause an error instead of retrying too soon.
- Writes are never replayed after network errors or 5xx. Their outcome can be unknown: inspect the review list before retrying to avoid duplicate creation. Authentication is not retried.
- Errors expose HTTP status and a safe hint, not remote response bodies, tokens, exception URLs or client secrets. JSON output escapes terminal controls from remote names.

This is a trusted-user terminal program with no HTTP listener, HTML renderer, session cookies or shared web login. Browser CSRF/XSS controls therefore do not apply. The OS account and app registration define the trust boundary; confirmation is an operator safeguard, not an authorization boundary against someone who can edit the Python code. Live output contains tenant data: protect redirected output and avoid publishing it.

## Verification

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest --cov=app --cov=entra_access_review --cov-fail-under=90
python -m pip_audit -r requirements.txt --progress-spinner off
# Install gitleaks separately, then:
gitleaks git . --redact --no-banner
```

Tests block unexpected network calls. Unit tests cover payloads, UUIDs, pagination, token-origin isolation, redirects, retries, safe errors, confirmation and stale delete plans. An integration test sends real HTTP to a loopback Graph simulator through an explicitly injected transport and exercises the CLI dry run/create/details/delete lifecycle. Subprocess smoke tests check deterministic demo output without Azure environment variables.

CI runs tests on Python 3.11–3.13 on Linux and Windows, checks formatting, audits runtime dependencies and scans Git history with Gitleaks. CI requires no tenant secrets. Recorded test results are in [VALIDATION.md](../VALIDATION.md). Dependency ranges allow security updates; CI resolves fresh dependencies, so installations are not a fully locked environment.

## Graph references

Verified against official Microsoft documentation on 2026-10-17:

- [List role definitions](https://learn.microsoft.com/en-us/graph/api/rbacapplication-list-roledefinitions?view=graph-rest-1.0) and [role assignments](https://learn.microsoft.com/en-us/graph/api/rbacapplication-list-roleassignments?view=graph-rest-1.0).
- [List review definitions](https://learn.microsoft.com/en-us/graph/api/accessreviewset-list-definitions?view=graph-rest-1.0), [create](https://learn.microsoft.com/en-us/graph/api/accessreviewset-post-definitions?view=graph-rest-1.0), [delete](https://learn.microsoft.com/en-us/graph/api/accessreviewscheduledefinition-delete?view=graph-rest-1.0) and [instances](https://learn.microsoft.com/en-us/graph/api/accessreviewscheduledefinition-list-instances?view=graph-rest-1.0).
- [Supported schedule settings](https://learn.microsoft.com/en-us/graph/api/resources/accessreviewschedulesettings?view=graph-rest-1.0), [one-time recurrence](https://learn.microsoft.com/en-us/graph/api/resources/patternedrecurrence?view=graph-rest-1.0) and [throttling](https://learn.microsoft.com/en-us/graph/throttling).

## Migration from the original menu

The old numbered interactive menu and token-taking helper functions have been replaced by explicit subcommands and a single Graph client. Scripts importing the old functions must migrate. Each command now uses the shared Graph client, an explicit scope and consistent error handling. Select one role and explicit reviewers when planning a review.
