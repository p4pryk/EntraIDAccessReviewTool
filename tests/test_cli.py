import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app import main
from entra_access_review import DemoClient, confirmation, create_plan
from test_core import REVIEW, REVIEWER, ROLE

CREATE = ["--demo", "create", "--role", ROLE, "--reviewer", REVIEWER]


def test_demo_dry_run_without_credentials(capsys):
    client = DemoClient()
    assert main(CREATE, client=client) == 0
    assert "DRY RUN: no change sent" in capsys.readouterr().out
    assert len(client.reviews()) == 1


def test_main_flow(capsys):
    client = DemoClient()
    for command in ("roles", "reviews"):
        assert main(["--demo", command], client=client) == 0
    assert main(["--demo", "assignments", "--role", ROLE], client=client) == 0
    assert main(["--demo", "details", REVIEW], client=client) == 0
    plan = create_plan(client, "DEMO — fictional tenant", ROLE, [REVIEWER], "once", "2026-10-17", "all")
    assert main(CREATE + ["--apply"], client=client, input_fn=lambda _: confirmation(plan)) == 0
    assert len(client.reviews()) == 2
    assert main(["--demo", "delete", REVIEW], client=client) == 0
    assert len(client.reviews()) == 2
    assert "simulated change" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["y", "yes", "POST wrong", ""])
def test_confirmation_refuses_wrong_input(answer, capsys):
    client = DemoClient()
    assert main(CREATE + ["--apply"], client=client, input_fn=lambda _: answer) == 1
    assert len(client.reviews()) == 1
    assert "Confirmation did not match" in capsys.readouterr().err


def test_eof_and_past_date(capsys):
    def eof(_):
        raise EOFError

    assert main(CREATE + ["--apply"], input_fn=eof) == 1
    assert main(CREATE + ["--start", "2020-01-01"]) == 1
    assert main(["--demo", "details", "not-a-uuid"]) == 1


def test_real_demo_subprocess_repeatable():
    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("AZURE_")}
    outputs = [
        subprocess.run(  # noqa: S603 - constant local script, no shell
            [sys.executable, "app.py", *CREATE],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
        for _ in range(2)
    ]
    assert outputs[0] == outputs[1]
    assert "DEMO / NO NETWORK" in outputs[0]
    assert "DRY RUN" in outputs[0]


def test_demo_fixtures_are_fictional():
    data = DemoClient().data
    assert all(r["displayName"].startswith("Demo") for r in data["roles"] + data["reviews"])
    assert json.loads(json.dumps(data)) == data


def test_full_demo_walkthrough_has_no_network(capsys):
    import runpy

    runpy.run_path(str(Path(__file__).resolve().parents[1] / "examples" / "demo.py"), run_name="__main__")
    output = capsys.readouterr().out
    assert "Demo complete: one fictional review remains" in output
    assert output.count("DEMO: simulated change") == 2


def test_delete_wrong_confirmation(capsys):
    client = DemoClient()
    assert main(["--demo", "delete", REVIEW, "--apply"], client=client, input_fn=lambda _: "yes") == 1
    assert len(client.reviews()) == 1


@pytest.mark.parametrize(
    "args", [["roles"], ["reviews"], ["assignments", "--role", ROLE], ["details", REVIEW]]
)
def test_json_mode_is_parseable_without_banner(args, capsys):
    assert main(["--demo", *args, "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert isinstance(result, (list, dict))


def test_inventory_names_cannot_inject_terminal_controls(capsys):
    client = DemoClient()
    client.data["roles"][0]["displayName"] = "malicious\x1b[2J\nROLE"
    assert main(["--demo", "roles"], client=client) == 0
    output = capsys.readouterr().out
    assert "\x1b" not in output
    assert "\\u001b" in output and "\\nROLE" in output


def test_empty_inventory_and_long_names(capsys):
    client = DemoClient()
    client.data["roles"][0]["displayName"] = "Long role " * 20
    assert main(["--demo", "roles"], client=client) == 0
    assert "..." in capsys.readouterr().out
    client.data["roles"] = []
    assert main(["--demo", "roles"], client=client) == 0
    assert "No results." in capsys.readouterr().out


def test_no_arguments_shows_help_without_credentials(capsys):
    assert main([]) == 0
    assert "usage:" in capsys.readouterr().out
