# Test results

Validated on 2026-10-17 for `p4pryk/EntraIDAccessReviewTool`.

## Automated checks

| Environment | Python | Result |
| --- | --- | --- |
| GitHub Actions / Linux | 3.11, 3.12, 3.13 | 82 tests passed per version |
| GitHub Actions / Windows | 3.11, 3.12, 3.13 | 82 tests passed per version |
| Local macOS ARM64 | 3.11, 3.12, 3.13 | 82 tests passed per version |

| Quality check | Result |
| --- | --- |
| Statement coverage | 98.80% (329/333 statements) |
| Ruff lint and formatting | Passed |
| Runtime dependency audit | No known vulnerabilities found |
| Gitleaks history and publication scans | No secrets found |
| Offline demo walkthrough | Passed |
| README visuals and local documentation links | Checked |

[GitHub Actions results](https://github.com/p4pryk/EntraIDAccessReviewTool/actions/workflows/ci.yml) provide checks for each published commit.

## Review lifecycle integration

The integration test runs the production Graph client and CLI against a real HTTP server on loopback. It covers:

- throttling followed by a paginated role list;
- directory assignment queries and their selected fields;
- a creation preview with zero write requests;
- exact confirmation followed by a simulated HTTP 201 response;
- review listing, definition details and review instances;
- deletion confirmation, target reread and a simulated HTTP 204 response;
- verification that the confirmed lifecycle sends exactly one POST and one DELETE.

Unit and CLI tests cover scope and date validation, supported schedules, terminal-safe output, JSON-only output, token-origin isolation, redirects, pagination loops and limits, retry limits, authentication errors, HTTP 403 handling, ambiguous write failures, wrong confirmations and changed deletion targets. Unexpected external network access is blocked during the suite.

## Live directory reads

A separate read-only check used an existing delegated user token and the production Graph client to verify role-definition enumeration, individual role retrieval and direct role assignments. A locally generated review payload was checked using the returned role definition.

The transport allowed only GET requests to inspection endpoints, rejected request bodies and disabled redirects. This check required no new app registration, consent grant or role assignment. Tenant records and credentials are kept out of source, fixtures and screenshots.

The evidence is separated by environment: review creation and deletion are exercised in the HTTP simulator; the live check covers directory reads. The CLI's documented deployment authentication uses application client credentials.

## Reproduce the checks

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest --cov=app --cov=entra_access_review --cov-fail-under=90
python -m pip_audit -r requirements.txt --progress-spinner off
gitleaks git . --redact --no-banner
python examples/demo.py
```

Runtime dependencies use version ranges so security updates can be picked up by fresh installations and audited by CI. The recorded local runtime resolved to `requests==2.34.2` and `urllib3==2.8.0`.
