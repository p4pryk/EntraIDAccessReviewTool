"""Small Microsoft Graph client and explicit, conservative review plans."""

import copy
import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from uuid import UUID

import requests

GRAPH = "https://graph.microsoft.com/v1.0"
DEFINITIONS = "/identityGovernance/accessReviews/definitions"
ROLES = "/roleManagement/directory/roleDefinitions"
TIMEOUT = (5, 30)


class ReviewError(Exception):
    """Safe to display: never contains remote bodies, credentials or URLs."""


def guid(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ReviewError("Expected a UUID identifier.") from None


def get_token():
    """Use process environment only; do not save credentials or token responses."""
    tenant = guid(os.environ.get("AZURE_TENANT_ID"))
    client = guid(os.environ.get("AZURE_CLIENT_ID"))
    secret = os.environ.get("AZURE_CLIENT_SECRET", "")
    if not secret.strip():
        raise ReviewError("Set AZURE_CLIENT_SECRET in the process environment.")
    try:
        response = requests.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": client,
                "client_secret": secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise ReviewError("Authentication failed. Check credentials and admin consent.")
        body = response.json()
        if not isinstance(body, dict):
            raise ReviewError("Authentication returned an invalid response.")
        token = body.get("access_token")
        if not isinstance(token, str) or not token.strip() or any(c.isspace() for c in token):
            raise ReviewError("Authentication returned an invalid token.")
        return token
    except (requests.RequestException, ValueError):
        raise ReviewError("Authentication unavailable or response invalid.") from None


def retry_delay(value, attempt):
    """Honor Retry-After; abort rather than retry earlier than a long server delay."""
    if value is None:
        return min(2**attempt, 30)
    try:
        delay = float(value)
    except ValueError:
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return min(2**attempt, 30)
    if not 0 <= delay <= 30:
        raise ReviewError("Graph requested a long/invalid retry delay. Try again later.")
    return delay


class GraphClient:
    def __init__(self, token, *, session=None, sleep=time.sleep):
        self._token = token
        self._session = session or requests.Session()
        self._sleep = sleep

    def _url(self, path):
        url = path if path.startswith("https://") else GRAPH + path
        try:
            parts = urlsplit(url)
        except ValueError:
            raise ReviewError("Rejected an invalid Graph URL.") from None
        # Pagination is untrusted input. Never forward credentials to another origin,
        # API version, encoded path or fragment; never follow HTTP redirects.
        if (
            parts.scheme != "https"
            or parts.netloc != "graph.microsoft.com"
            or not parts.path.startswith("/v1.0/")
            or parts.fragment
            or "%" in parts.path
            or "/../" in parts.path
            or "/./" in parts.path
        ):
            raise ReviewError("Rejected an unsafe Graph URL.")
        return url

    def request(self, method, path, payload=None):
        url = self._url(path)
        for attempt in range(3):
            try:
                response = self._session.request(
                    method,
                    url,
                    headers={"Authorization": f"Bearer {self._token}"},
                    json=payload,
                    timeout=TIMEOUT,
                    allow_redirects=False,
                )
            except requests.RequestException:
                message = "Graph connection failed."
                if method != "GET":
                    message += " Outcome unknown; inspect reviews before trying again."
                raise ReviewError(message) from None
            # A POST is replayed only after an explicit rejection by throttling.
            # Never replay ambiguous writes on timeouts or 5xx responses.
            if response.status_code == 429 or (method == "GET" and response.status_code in (502, 503, 504)):
                if attempt < 2:
                    self._sleep(retry_delay(response.headers.get("Retry-After"), attempt))
                    continue
            expected = {"GET": 200, "POST": 201, "DELETE": 204}[method]
            if response.status_code != expected:
                hint = {
                    401: "Token expired or invalid.",
                    403: "Check application permissions, consent and licensing.",
                    404: "Resource not found.",
                    429: "Retry limit reached; try later.",
                }.get(response.status_code, "Request rejected.")
                if method != "GET" and response.status_code >= 500:
                    hint = "Outcome unknown; inspect reviews before trying again."
                raise ReviewError(f"Graph HTTP {response.status_code}. {hint}")
            if expected == 204:
                return None
            try:
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError
                return result
            except ValueError:
                suffix = " Outcome unknown; inspect reviews before trying again." if method != "GET" else ""
                raise ReviewError("Invalid Graph JSON response." + suffix) from None
        raise ReviewError("Graph retry limit reached.")

    def collection(self, path):
        items, seen = [], set()
        while path:
            url = self._url(path)
            if url in seen or len(seen) >= 100:
                raise ReviewError(
                    "Graph pagination loop or 100-page safety limit reached; results incomplete."
                )
            seen.add(url)
            page = self.request("GET", path)
            values = page.get("value")
            if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
                raise ReviewError("Invalid Graph collection response.")
            items.extend(values)
            path = page.get("@odata.nextLink")
            if path is not None and (not isinstance(path, str) or not path.startswith("https://")):
                raise ReviewError("Invalid Graph pagination link.")
        return items

    def roles(self):
        return self.collection(ROLES)

    def assignments(self, role_id):
        role_id = guid(role_id)
        return self.collection(
            f"/roleManagement/directory/roleAssignments?$filter=roleDefinitionId eq '{role_id}'"
            "&$select=id,principalId,roleDefinitionId,directoryScopeId"
        )

    def reviews(self):
        return self.collection(DEFINITIONS)

    def details(self, review_id):
        path = f"{DEFINITIONS}/{guid(review_id)}"
        result = self.request("GET", path)
        result["instances"] = self.collection(path + "/instances")
        return result


def build_payload(role, reviewer_ids, frequency, start, assignment="all"):
    role_id = guid(role["id"])
    name = role.get("displayName")
    if not isinstance(name, str) or not 1 <= len(name) <= 120:
        raise ReviewError("Role name must contain 1–120 characters.")
    if not reviewer_ids or len(reviewer_ids) > 10:
        raise ReviewError("Specify 1–10 explicit reviewer user UUIDs.")
    reviewers = list(dict.fromkeys(guid(r) for r in reviewer_ids))
    try:
        start_date = date.fromisoformat(start)
        if start_date.isoformat() != start:
            raise ValueError
    except (ValueError, TypeError):
        raise ReviewError("Start date must use YYYY-MM-DD.") from None
    if frequency not in ("once", "weekly", "monthly", "quarterly", "halfyearly"):
        raise ReviewError("Unsupported review frequency.")
    if assignment not in ("all", "active", "eligible"):
        raise ReviewError("Unsupported assignment scope.")
    query = f"{ROLES}/{role_id}"
    if assignment != "all":
        kind = (
            "roleAssignmentScheduleInstances"
            if assignment == "active"
            else "roleEligibilityScheduleInstances"
        )
        active = "assignmentType eq 'Assigned' and " if assignment == "active" else ""
        query = (
            f"/roleManagement/directory/{kind}?$expand=principal&$filter=("
            f"{active}isof(principal,'microsoft.graph.user') and roleDefinitionId eq '{role_id}')"
        )
    try:
        end = (start_date + timedelta(days=7)).isoformat()
    except OverflowError:
        raise ReviewError("Start date is too far in the future.") from None
    pattern = None
    if frequency == "weekly":
        pattern = {"type": "weekly", "interval": 1}
    elif frequency != "once":
        pattern = {
            "type": "absoluteMonthly",
            "interval": {"monthly": 1, "quarterly": 3, "halfyearly": 6}[frequency],
            "dayOfMonth": start_date.day,
        }
    return {
        "displayName": f"Review: {name}",
        "descriptionForAdmins": f"Review {assignment} user assignments to {name}.",
        "descriptionForReviewers": f"Validate continued need for {name} access.",
        "scope": {
            "@odata.type": "#microsoft.graph.accessReviewQueryScope",
            "query": query,
            "queryType": "MicrosoftGraph",
        },
        "reviewers": [{"query": f"/users/{r}", "queryType": "MicrosoftGraph"} for r in reviewers],
        "settings": {
            "mailNotificationsEnabled": False,
            "reminderNotificationsEnabled": False,
            "justificationRequiredOnApproval": True,
            "defaultDecisionEnabled": False,
            "instanceDurationInDays": 7 if frequency != "weekly" else 3,
            "autoApplyDecisionsEnabled": False,
            "recommendationsEnabled": True,
            "recurrence": {
                **({"pattern": pattern} if pattern else {}),
                "range": {
                    "type": "endDate" if frequency == "once" else "noEnd",
                    "startDate": start,
                    **({"endDate": end} if frequency == "once" else {}),
                },
            },
        },
    }


def create_plan(client, tenant, role_id, reviewers, frequency, start, assignment):
    role_id = guid(role_id)
    role = client.request("GET", f"{ROLES}/{role_id}")
    if guid(role.get("id")) != role_id:
        raise ReviewError("Graph returned a different role.")
    payload = build_payload(role, reviewers, frequency, start, assignment)
    return {"tenant": tenant, "method": "POST", "path": DEFINITIONS, "payload": payload}


def delete_plan(client, tenant, review_id):
    review_id = guid(review_id)
    review = client.request("GET", f"{DEFINITIONS}/{review_id}")
    if guid(review.get("id")) != review_id:
        raise ReviewError("Graph returned a different review.")
    return {"tenant": tenant, "method": "DELETE", "path": f"{DEFINITIONS}/{review_id}", "target": review}


def confirmation(plan):
    digest = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()[:12]
    return f"{plan['method']} {digest}"


def apply_plan(client, plan, phrase):
    """Apply the in-memory preview only, never an imported arbitrary JSON plan."""
    if phrase != confirmation(plan):
        raise ReviewError("Confirmation did not match. No change sent.")
    if plan["method"] == "DELETE":
        current = client.request("GET", plan["path"])
        if current != plan["target"]:
            raise ReviewError("Review changed since preview. Generate a new plan.")
    return client.request(plan["method"], plan["path"], plan.get("payload"))


def safe_json(value):
    # ensure_ascii escapes remote terminal controls, including ANSI and bidi marks.
    return json.dumps(value, indent=2, ensure_ascii=True)


class DemoClient(GraphClient):
    """Deterministic in-memory fixture. No HTTP session or credentials."""

    def __init__(self):
        from pathlib import Path

        fixture = Path(__file__).with_name("examples") / "demo.json"
        self.data = json.loads(fixture.read_text(encoding="utf-8"))
        self.created = 0

    def request(self, method, path, payload=None):
        if path.startswith("/roleManagement/directory/roleAssignments?") and method == "GET":
            role_id = path.split("roleDefinitionId eq '")[1].split("'")[0]
            return {
                "value": copy.deepcopy(
                    [r for r in self.data["assignments"] if r["roleDefinitionId"] == role_id]
                )
            }
        if path == ROLES and method == "GET":
            return {"value": copy.deepcopy(self.data["roles"])}
        if path.startswith(ROLES + "/") and method == "GET":
            rows = self.data["roles"]
        elif path == DEFINITIONS:
            if method == "POST":
                self.created += 1
                row = {
                    **copy.deepcopy(payload),
                    "id": f"dddddddd-dddd-4ddd-8ddd-{self.created:012d}",
                    "status": "NotStarted",
                }
                self.data["reviews"].append(row)
                return copy.deepcopy(row)
            return {"value": copy.deepcopy(self.data["reviews"])}
        elif path.endswith("/instances"):
            return {"value": []}
        else:
            rows = self.data["reviews"]
        row = next((r for r in rows if r["id"] == path.rsplit("/", 1)[-1]), None)
        if row is None:
            raise ReviewError("Graph HTTP 404. Resource not found.")
        if method == "DELETE":
            rows.remove(row)
            return None
        return copy.deepcopy(row)
