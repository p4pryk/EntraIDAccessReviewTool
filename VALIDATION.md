# Validation record

Date: 2026-10-17. Repository: `p4pryk/EntraIDAccessReviewTool`.
Upstream baseline: `83d3e06323a92430a4e69e0aa2fd8b4c1a625a19` on `main`.
GitHub identity was verified as `p4pryk`; no credentials are included in deliverables.

## Completed locally

| Check | Result |
| --- | --- |
| Python 3.11.6 / macOS ARM64 | 82 tests passed |
| Python 3.12.12 / macOS ARM64 | 82 tests passed |
| Python 3.13.11 / macOS ARM64 | 82 tests passed |
| Coverage on Python 3.12 | 98.80% statement coverage (329/333 statements) |
| Ruff 0.14.14 lint and formatting | Passed |
| pip-audit 2.10.1, runtime requirements | No known vulnerabilities found |
| Gitleaks 8.30.1, original full Git history | No leaks found (4 commits) |
| Gitleaks 8.30.1, complete prepared source snapshot | No leaks found |
| Gitleaks 8.30.1, staged patch | No leaks found |
| Live GET-only role definitions and direct assignments | Passed with an existing delegated user token; no tenant configuration changes |
| Live access-review reads | HTTP 403 in that token/account context; not validated |
| Live write requests | None sent |
| Deterministic offline demo lifecycle | Passed, including create and delete confirmation |
| Screenshot visual inspection | Passed; three README visuals render actual CLI output from fictional data |

The runtime dependency resolved to `requests==2.34.2`, with `urllib3==2.8.0`, `certifi==2026.7.22`, `charset-normalizer==3.5.2` and `idna==3.20`. Audit results reflect known advisories on the check date; dependencies are intentionally version ranges rather than a cross-platform lock file.

## What the integration test proves

A real HTTP server on `127.0.0.1` returns Graph-shaped responses. A test-only transport maps already-validated Graph URLs to this server. The production Graph origin allowlist is exercised separately with rejected redirect/next-link targets. All other test network access is blocked.

The flow covers a throttled, paginated role list; a create dry run with zero writes; exact create confirmation; HTTP 201; list and detail retrieval including instances; exact delete confirmation and reread; HTTP 204; and verification that exactly one POST and one DELETE occurred. CLI tests also verify readable tables, JSON-only output, help without credentials and escaped remote names. A live directory endpoint also rejected the original appScopeId projection with HTTP 400. The directory assignment query now selects only directory-supported fields, and the loopback contract verifies that behavior. Unit tests exercise unsafe next links, pagination loops and page limits, authentication failures, malformed JSON, 403 errors, ambiguous write failures, bounded retries, date/scope validation, escaped terminal controls, wrong confirmations and stale deletion targets.

These tests validate our client behavior and payload expectations. They do **not** establish that a real tenant accepts the payloads or returns the same schema, enforces a particular license, expands group assignments in a particular way or permits every reviewer configuration.

## Remaining acceptance work

- GitHub-hosted CI is configured for Linux and Windows, Python 3.11–3.13. See the pull request checks and Actions history for results tied to the published commit. The local results above were recorded on macOS.
- A limited live read-only test used an existing delegated user token through Azure CLI. It confirmed role definitions, a single role and direct assignments. Access-review listing returned HTTP 403, so details/instances could not be exercised. The token had broader permissions, but a transport allowlist rejected every method other than GET and disabled redirects and request bodies. No app registration, consent grant, role assignment or tenant data was changed.
- Before operational use or mutation testing, obtain explicit authorization for an isolated licensed test tenant. An administrator must grant the documented minimum application permissions, confirm reviewer user objects and review scope, and authorize creation/deletion of a dedicated disposable test review.
- In that environment, verify read-only pagination, actual active/eligible user coverage, one-time and repeating schedules, reviewer resolution, disabled notifications and disabled automatic application, and delete behavior. Confirm the Entra admin center shows the intended scope before relying on the tool.
- The delete reread is conservative but not atomic. Confirmation cannot prevent another administrator changing the target after the reread.
- A network failure or server error during a write can leave an unknown outcome. Check for an existing definition before retrying.
- Client-secret authentication is the only implemented live flow. No certificate/managed-identity flow, token refresh, sovereign-cloud configuration, browser UI, bulk mutation, decision application or LLM integration is included.

## Publication state

This update is submitted through a separate GitHub branch and pull request, with source, tests, fixtures, CI, README, changelog and demo evidence for review. Local tests and partial live read validation are documented above; GitHub-hosted results are tied to the PR commit. No raw tenant records, account identifiers, tokens or private live-test scripts are included. No repository visibility change, paid resource, automation or live tenant mutation is part of publication. No other project workspace was modified.
