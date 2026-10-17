"""Run the actual CLI through a deterministic, fictional review lifecycle."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main  # noqa: E402
from entra_access_review import (  # noqa: E402
    DemoClient,
    confirmation,
    create_plan,
    delete_plan,
)


def run():
    client = DemoClient()
    role = client.data["roles"][0]["id"]
    reviewer = "44444444-4444-4444-8444-444444444444"
    create = ["create", "--role", role, "--reviewer", reviewer]

    def command(args, phrase=""):
        print("\n$ python app.py --demo " + " ".join(args))

        def confirm(prompt):
            print(prompt + phrase)
            return phrase

        if main(["--demo", *args], client=client, input_fn=confirm):
            raise RuntimeError("Demo command failed")

    command(["roles"])
    command(["assignments", "--role", role])
    command(create)
    plan = create_plan(client, "DEMO — fictional tenant", role, [reviewer], "once", "2026-10-17", "all")
    command(create + ["--apply"], confirmation(plan))
    review_id = client.data["reviews"][-1]["id"]
    command(["reviews"])
    command(["details", review_id])
    command(["delete", review_id])
    plan = delete_plan(client, "DEMO — fictional tenant", review_id)
    command(["delete", review_id, "--apply"], confirmation(plan))
    command(["reviews"])
    print("\nDemo complete: one fictional review remains. No network or tenant changes.")


if __name__ == "__main__":
    run()
