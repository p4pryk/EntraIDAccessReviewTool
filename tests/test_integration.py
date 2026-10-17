"""Real HTTP to loopback, never a tenant. Same Graph client and CLI code paths."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import requests

from app import main
from entra_access_review import DEFINITIONS, GRAPH, ROLES, GraphClient, confirmation, create_plan, delete_plan
from test_core import ROLE, REVIEWER


# Save the real transport before the autouse network guard is installed.
REAL_REQUEST = requests.sessions.Session.request


class LoopbackTransport:
    def __init__(self, port):
        self.port = port

    def request(self, method, url, **kwargs):
        parts = urlsplit(url)
        assert parts.netloc == "graph.microsoft.com"
        assert kwargs["headers"]["Authorization"] == "Bearer fixture-token"
        path = parts.path + ("?" + parts.query if parts.query else "")
        return REAL_REQUEST(requests.Session(), method, f"http://127.0.0.1:{self.port}{path}", **kwargs)


def test_local_graph_lifecycle_and_cli(monkeypatch, capsys):
    state = {"reviews": [], "calls": [], "throttled": False}
    role = {"id": ROLE, "displayName": "Demo role"}
    review_id = "55555555-5555-4555-8555-555555555555"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, data=None, **headers):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            if data is not None:
                self.wfile.write(json.dumps(data).encode())

        def do_GET(self):
            state["calls"].append(("GET", self.path))
            if self.path == "/v1.0" + ROLES:
                if not state["throttled"]:
                    state["throttled"] = True
                    return self.reply(429, {}, **{"Retry-After": "0"})
                return self.reply(
                    200, {"value": [role], "@odata.nextLink": GRAPH + ROLES + "?$skiptoken=page2"}
                )
            if "skiptoken" in self.path:
                return self.reply(200, {"value": [{"id": REVIEWER, "displayName": "Second role"}]})
            if self.path == "/v1.0" + ROLES + "/" + ROLE:
                return self.reply(200, role)
            if self.path.startswith("/v1.0/roleManagement/directory/roleAssignments?"):
                fields = parse_qs(urlsplit(self.path).query)["$select"][0].split(",")
                if "appScopeId" in fields:
                    return self.reply(400, {"error": {"code": "Request_BadRequest"}})
                return self.reply(
                    200,
                    {
                        "value": [
                            {
                                "id": "assignment",
                                "principalId": REVIEWER,
                                "roleDefinitionId": ROLE,
                                "directoryScopeId": "/",
                            }
                        ]
                    },
                )
            if self.path.endswith("/instances"):
                return self.reply(200, {"value": [{"id": "instance", "status": "InProgress"}]})
            if self.path == "/v1.0" + DEFINITIONS:
                return self.reply(200, {"value": state["reviews"]})
            if self.path.endswith(review_id) and state["reviews"]:
                return self.reply(200, state["reviews"][0])
            return self.reply(404, {})

        def do_POST(self):
            state["calls"].append(("POST", self.path))
            assert self.path == "/v1.0" + DEFINITIONS
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["settings"]["autoApplyDecisionsEnabled"] is False
            assert body["scope"]["query"] == ROLES + "/" + ROLE
            row = dict(body, id=review_id, status="NotStarted")
            state["reviews"].append(row)
            self.reply(201, row)

        def do_DELETE(self):
            state["calls"].append(("DELETE", self.path))
            assert self.path == "/v1.0" + DEFINITIONS + "/" + review_id
            state["reviews"].clear()
            self.reply(204)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sleep = Mock()
        client = GraphClient("fixture-token", session=LoopbackTransport(server.server_port), sleep=sleep)
        assert len(client.roles()) == 2
        assert main(["--demo", "assignments", "--role", ROLE], client=client) == 0
        assert client.assignments(ROLE)[0]["principalId"] == REVIEWER
        sleep.assert_called_once_with(0)
        monkeypatch.setenv("AZURE_TENANT_ID", ROLE)
        args = ["create", "--role", ROLE, "--reviewer", REVIEWER, "--start", "2099-01-01"]
        assert main(args, client=client) == 0
        assert state["reviews"] == []
        plan = create_plan(client, ROLE, ROLE, [REVIEWER], "once", "2099-01-01", "all")
        assert main(args + ["--apply"], client=client, input_fn=lambda _: confirmation(plan)) == 0
        assert len(client.reviews()) == 1
        assert client.details(review_id)["instances"][0]["status"] == "InProgress"
        delete = delete_plan(client, ROLE, review_id)
        assert (
            main(["delete", review_id, "--apply"], client=client, input_fn=lambda _: confirmation(delete))
            == 0
        )
        assert state["reviews"] == []
        assert [method for method, _ in state["calls"] if method != "GET"] == ["POST", "DELETE"]
        assert "Graph confirmed" in capsys.readouterr().out
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
