import copy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import Mock

import pytest
import requests

from entra_access_review import (
    DEFINITIONS,
    GRAPH,
    ROLES,
    TIMEOUT,
    DemoClient,
    GraphClient,
    ReviewError,
    apply_plan,
    build_payload,
    confirmation,
    create_plan,
    delete_plan,
    get_token,
    guid,
    retry_delay,
    safe_json,
)

ROLE = "11111111-1111-4111-8111-111111111111"
REVIEWER = "44444444-4444-4444-8444-444444444444"
REVIEW = "33333333-3333-4333-8333-333333333333"


def response(status=200, body=None, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = body if body is not None else {}
    return result


def graph(*responses):
    session = Mock()
    session.request.side_effect = responses
    sleep = Mock()
    return GraphClient("test-token", session=session, sleep=sleep), session, sleep


@pytest.mark.parametrize("value", [None, "", "../users", "not-a-uuid", "1' or true", 42])
def test_reject_invalid_ids(value):
    with pytest.raises(ReviewError):
        guid(value)


@pytest.mark.parametrize(
    "frequency,kind,interval",
    [
        ("once", None, None),
        ("weekly", "weekly", 1),
        ("monthly", "absoluteMonthly", 1),
        ("quarterly", "absoluteMonthly", 3),
        ("halfyearly", "absoluteMonthly", 6),
    ],
)
def test_schedule_and_safe_defaults(frequency, kind, interval):
    body = build_payload({"id": ROLE, "displayName": "Role"}, [REVIEWER], frequency, "2026-10-17")
    settings = body["settings"]
    pattern = settings["recurrence"].get("pattern")
    if kind:
        assert pattern["type"] == kind and pattern["interval"] == interval
    else:
        assert pattern is None
    assert not settings["autoApplyDecisionsEnabled"]
    assert not settings["defaultDecisionEnabled"]
    assert not settings["mailNotificationsEnabled"]
    assert settings["justificationRequiredOnApproval"]
    if frequency == "weekly":
        assert "daysOfWeek" not in pattern
        assert settings["instanceDurationInDays"] < 7
    if frequency == "once":
        assert settings["recurrence"]["range"]["endDate"] == "2026-10-24"


@pytest.mark.parametrize(
    "scope,fragment",
    [
        ("all", f"{ROLES}/{ROLE}"),
        ("active", "assignmentType eq 'Assigned'"),
        ("eligible", "roleEligibilityScheduleInstances"),
    ],
)
def test_documented_user_only_scope(scope, fragment):
    body = build_payload({"id": ROLE, "displayName": "Role"}, [REVIEWER], "once", "2026-10-17", scope)
    assert fragment in body["scope"]["query"]
    assert body["scope"]["@odata.type"] == "#microsoft.graph.accessReviewQueryScope"
    if scope != "all":
        assert "isof(principal,'microsoft.graph.user')" in body["scope"]["query"]
        assert f"roleDefinitionId eq '{ROLE}'" in body["scope"]["query"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"reviewer_ids": []},
        {"reviewer_ids": ["bad"]},
        {"reviewer_ids": [REVIEWER] * 11},
        {"frequency": "unknown"},
        {"assignment": "groups"},
        {"start": "2026-02-30"},
        {"role": {"id": ROLE, "displayName": ""}},
    ],
)
def test_invalid_plan_inputs(overrides):
    args = dict(
        role={"id": ROLE, "displayName": "Role"},
        reviewer_ids=[REVIEWER],
        frequency="once",
        start="2026-10-17",
    )
    with pytest.raises(ReviewError):
        build_payload(**(args | overrides))


def test_paginate_and_transport_safety():
    next_url = GRAPH + ROLES + "?$skiptoken=next"
    client, session, _ = graph(
        response(body={"value": [{"id": 1}], "@odata.nextLink": next_url}),
        response(body={"value": [{"id": 2}]}),
    )
    assert client.roles() == [{"id": 1}, {"id": 2}]
    call = session.request.call_args_list[-1]
    assert call.args == ("GET", next_url)
    assert call.kwargs["timeout"] == TIMEOUT
    assert call.kwargs["allow_redirects"] is False
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-token"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/v1.0/roles",
        "http://graph.microsoft.com/v1.0/roles",
        "https://graph.microsoft.com@evil.example/v1.0/roles",
        "https://graph.microsoft.com/beta/roles",
        "https://graph.microsoft.com/v1.0/../beta/roles",
        "https://graph.microsoft.com/v1.0/%2e%2e/beta/roles",
        "https://graph.microsoft.com/v1.0/roles#token",
        "https://graph.microsoft.com:443/v1.0/roles",
    ],
)
def test_next_link_cannot_exfiltrate_token(url):
    client, session, _ = graph(response(body={"value": [], "@odata.nextLink": url}))
    with pytest.raises(ReviewError):
        client.roles()
    assert session.request.call_count == 1


@pytest.mark.parametrize("body", [{}, {"value": "bad"}, {"value": [1]}, {"value": [], "@odata.nextLink": 1}])
def test_invalid_collections_fail_explicitly(body):
    client, _, _ = graph(response(body=body))
    with pytest.raises(ReviewError):
        client.roles()


def test_pagination_loop():
    client, session, _ = graph(response(body={"value": [], "@odata.nextLink": GRAPH + ROLES}))
    with pytest.raises(ReviewError, match="pagination"):
        client.roles()
    assert session.request.call_count == 1


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
def test_429_retry_bounded(method):
    client, session, sleep = graph(*[response(429, headers={"Retry-After": "0"}) for _ in range(3)])
    with pytest.raises(ReviewError, match="429"):
        client.request(method, DEFINITIONS)
    assert session.request.call_count == 3
    assert sleep.call_count == 2


def test_get_503_retry_success():
    client, session, sleep = graph(response(503), response(body={"value": []}))
    assert client.roles() == []
    assert session.request.call_count == 2
    sleep.assert_called_once_with(1)


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("failure", [response(503), requests.Timeout("test-token secret")])
def test_ambiguous_write_never_replayed(method, failure):
    client, session, _ = graph(failure)
    with pytest.raises(ReviewError, match="Outcome unknown") as error:
        client.request(method, DEFINITIONS)
    assert "test-token" not in str(error.value)
    assert session.request.call_count == 1


@pytest.mark.parametrize("code", [301, 400, 401, 403, 404, 500])
def test_errors_hide_remote_body(code):
    client, _, _ = graph(response(code, {"error": "secret and ANSI \u001b[31m"}))
    with pytest.raises(ReviewError) as error:
        client.roles()
    assert str(code) in str(error.value)
    assert "secret" not in str(error.value)


def test_invalid_json():
    reply = response()
    reply.json.side_effect = ValueError("secret")
    client, _, _ = graph(reply)
    with pytest.raises(ReviewError, match="Invalid Graph JSON"):
        client.roles()


def test_retry_after():
    assert retry_delay(None, 2) == 4
    assert retry_delay("invalid", 1) == 2
    assert retry_delay("3", 0) == 3
    future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=10))
    assert 8 < retry_delay(future, 0) <= 10
    for value in ("1000", "nan", "inf", "-1"):
        with pytest.raises(ReviewError):
            retry_delay(value, 0)


def test_safe_output():
    output = safe_json({"displayName": "\u001b[2J\u202efake"})
    assert "\u001b" not in output and "\u202e" not in output
    assert "\\u001b" in output


def test_create_delete_and_stale_plan():
    client = DemoClient()
    plan = create_plan(client, "demo", ROLE, [REVIEWER], "once", "2026-10-17", "all")
    original = copy.deepcopy(plan)
    with pytest.raises(ReviewError):
        apply_plan(client, plan, "yes")
    result = apply_plan(client, plan, confirmation(plan))
    assert plan == original
    assert len(client.reviews()) == 2
    delete = delete_plan(client, "demo", result["id"])
    client.data["reviews"][-1]["displayName"] = "Changed"
    with pytest.raises(ReviewError, match="changed"):
        apply_plan(client, delete, confirmation(delete))
    delete = delete_plan(client, "demo", result["id"])
    apply_plan(client, delete, confirmation(delete))
    assert len(client.reviews()) == 1


def test_plan_confirmation_binds_tenant_and_payload():
    plan = create_plan(DemoClient(), "demo", ROLE, [REVIEWER], "once", "2026-10-17", "all")
    assert confirmation(plan) != confirmation(plan | {"tenant": "other"})
    altered = copy.deepcopy(plan)
    altered["payload"]["settings"]["autoApplyDecisionsEnabled"] = True
    assert confirmation(plan) != confirmation(altered)


def test_authentication(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", ROLE)
    monkeypatch.setenv("AZURE_CLIENT_ID", REVIEWER)
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "fixture-secret")
    post = Mock(return_value=response(body={"access_token": "fixture-token"}))
    monkeypatch.setattr(requests, "post", post)
    assert get_token() == "fixture-token"
    assert post.call_args.kwargs["allow_redirects"] is False
    assert post.call_args.kwargs["timeout"] == TIMEOUT
    post.return_value = response(401, {"error": "fixture-secret"})
    with pytest.raises(ReviewError) as error:
        get_token()
    assert "fixture-secret" not in str(error.value)
    post.side_effect = requests.Timeout("fixture-secret")
    with pytest.raises(ReviewError, match="unavailable"):
        get_token()


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    with pytest.raises(ReviewError):
        get_token()


def test_assignment_inventory_uses_minimal_projection():
    client, session, _ = graph(response(body={"value": [{"principalId": REVIEWER}]}))
    assert client.assignments(ROLE) == [{"principalId": REVIEWER}]
    url = session.request.call_args.args[1]
    assert f"roleDefinitionId eq '{ROLE}'" in url
    assert "$select=id,principalId,roleDefinitionId,directoryScopeId" in url
    assert "$expand" not in url


def test_pagination_page_cap():
    session = Mock()
    session.request.side_effect = [
        response(body={"value": [], "@odata.nextLink": GRAPH + ROLES + f"?$skip={i}"}) for i in range(100)
    ]
    client = GraphClient("fixture", session=session)
    with pytest.raises(ReviewError, match="100-page"):
        client.roles()
    assert session.request.call_count == 100


@pytest.mark.parametrize("start", ["20261017", "9999-12-31"])
def test_unrepresentable_dates(start):
    with pytest.raises(ReviewError):
        build_payload({"id": ROLE, "displayName": "Role"}, [REVIEWER], "once", start)


def test_mismatched_graph_objects():
    client, _, _ = graph(response(body={"id": REVIEWER}))
    with pytest.raises(ReviewError, match="different role"):
        create_plan(client, "demo", ROLE, [REVIEWER], "once", "2026-10-17", "all")
    client, _, _ = graph(response(body={"id": ROLE}))
    with pytest.raises(ReviewError, match="different review"):
        delete_plan(client, "demo", REVIEW)


def test_missing_secret_and_malformed_token_response(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", ROLE)
    monkeypatch.setenv("AZURE_CLIENT_ID", REVIEWER)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    with pytest.raises(ReviewError, match="AZURE_CLIENT_SECRET"):
        get_token()
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "fixture-secret")
    for body in ([], {}, {"access_token": "bad\ntoken"}):
        reply = response()
        reply.json.return_value = body
        monkeypatch.setattr(requests, "post", Mock(return_value=reply))
        with pytest.raises(ReviewError, match="invalid"):
            get_token()


def test_invalid_url_and_unknown_demo_resource():
    client, session, _ = graph()
    with pytest.raises(ReviewError):
        client.request("GET", "https://[invalid/v1.0/")
    session.request.assert_not_called()
    with pytest.raises(ReviewError, match="404"):
        DemoClient().details(REVIEWER)
