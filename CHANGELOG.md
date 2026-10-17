# Changelog

## Unreleased — 2026-10-17

- Replace duplicated terminal menus with explicit, documented CLI commands.
- Move authentication to environment-only client credentials; sanitize errors and terminal output.
- Centralize Graph v1.0 requests, timeouts, bounded throttling retries and guarded pagination.
- Use documented single-role user review scopes for active, eligible or both assignment types.
- Require explicit reviewers; disable automatic decisions, automatic application and notifications.
- Make creation and deletion dry-run by default, with exact plan confirmation and a stale-delete check.
- Add a deterministic offline demo, fictional fixtures and a complete CLI walkthrough.
- Add unit tests, a loopback HTTP integration test, subprocess smoke tests and CI security checks.
- Document minimum application permissions, operating boundaries, migration and live-test limitations.

### Live read validation

- Remove `appScopeId` from the directory role-assignment projection after the live directory endpoint rejected it with HTTP 400. Preserve `directoryScopeId` and keep application-specific scopes out of the directory inventory query.
- Extend the loopback integration contract to reject that unsupported directory projection.

### Presentation and usability

- Add readable inventory tables with a JSON-only mode for read commands.
- Show a concise change summary before the complete plan and confirmation.
- Show help without authentication when no command is supplied.
- Redesign the README with three reproducible visuals captured from actual offline CLI output.
- Move detailed operating instructions into a separate guide.

### Breaking changes

- Remove the numbered menu and the previous public helper function signatures.
- Remove bulk operations and the hardcoded privileged-role list.
- List assignment principal UUIDs without directory-object resolution or extra directory read permissions.
