"""Local terminal UI. Mutations always start with a printable dry-run plan."""

import argparse
import os
import sys
from datetime import datetime, timezone

from entra_access_review import (
    DemoClient,
    GraphClient,
    ReviewError,
    apply_plan,
    confirmation,
    create_plan,
    delete_plan,
    get_token,
    guid,
    safe_json,
)


def parser():
    root = argparse.ArgumentParser(description="Microsoft Entra ID Access Review Tool")
    root.add_argument("--demo", action="store_true", help="Fictional data; no login or network")
    commands = root.add_subparsers(dest="command", required=True)
    roles = commands.add_parser("roles", help="List role definitions (no risk classification)")
    assignments = commands.add_parser("assignments", help="List direct active assignments by principal UUID")
    assignments.add_argument("--role", required=True, type=guid)
    reviews = commands.add_parser("reviews", help="List review schedule definitions")
    details = commands.add_parser("details", help="Read a definition and its instances")
    details.add_argument("review_id", type=guid)
    for command in (roles, reviews, assignments, details):
        command.add_argument("--json", action="store_true", help="Output JSON only for scripts")
    create = commands.add_parser("create", help="Preview a review for ONE role; dry-run by default")
    create.add_argument("--role", required=True, type=guid)
    create.add_argument(
        "--reviewer",
        required=True,
        action="append",
        type=guid,
        help="User UUID; repeat for multiple reviewers",
    )
    create.add_argument("--assignment", choices=("all", "active", "eligible"), default="all")
    create.add_argument(
        "--frequency", choices=("once", "weekly", "monthly", "quarterly", "halfyearly"), default="once"
    )
    create.add_argument("--start", help="YYYY-MM-DD; defaults to UTC today (fixed in demo)")
    delete = commands.add_parser("delete", help="Preview deletion of ONE entire review series")
    delete.add_argument("review_id", type=guid)
    for command in (create, delete):
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true", help="Require typed confirmation after preview")
        mode.add_argument("--dry-run", action="store_true", help="Explicitly preview only (the default)")
    return root


def text(value):
    """Keep remote text on one line and escape terminal controls."""
    return safe_json(str(value))[1:-1]


def table(rows, columns):
    if not rows:
        print("No results.")
        return
    cells = [[text(row.get(key, "-")) for _, key, _ in columns] for row in rows]
    widths = [
        min(limit, max(len(title), *(len(row[i]) for row in cells)))
        for i, (title, _, limit) in enumerate(columns)
    ]

    def line(values):
        return "  ".join(
            (v if len(v) <= w else v[: w - 3] + "...").ljust(w) for v, w in zip(values, widths, strict=True)
        ).rstrip()

    print(line([title for title, _, _ in columns]))
    print("  ".join("-" * width for width in widths))
    for row in cells:
        print(line(row))
    print(f"\n{len(rows)} result(s). Use --json for complete records.")


def plan_summary(plan):
    payload = plan.get("payload", plan.get("target", {}))
    print("  Target       " + text(payload.get("displayName", "Unnamed review")))
    print("  Tenant       " + text(plan["tenant"]))
    if plan["method"] == "DELETE":
        print("  Effect       Delete the entire review series and its definition.")
    else:
        settings = payload["settings"]
        recurrence = settings["recurrence"]
        pattern = recurrence.get("pattern")
        schedule = "One-time"
        if pattern:
            schedule = (
                "Weekly"
                if pattern["type"] == "weekly"
                else {1: "Monthly", 3: "Quarterly", 6: "Every six months"}[pattern["interval"]]
            )
        print("  Scope        " + text(payload["scope"]["query"]))
        print("  Schedule     " + schedule + " / starts " + recurrence["range"]["startDate"])
        print(f"  Duration     {settings['instanceDurationInDays']} days per review")
        print(f"  Reviewers    {len(payload['reviewers'])} explicit user(s)")
        print("  Safeguards   Auto-apply OFF / default decision OFF / email OFF")
    print("  Confirmation " + confirmation(plan))
    print("\nFull change plan:")


def main(argv=None, *, client=None, input_fn=input):
    try:
        arguments = sys.argv[1:] if argv is None else argv
        if not arguments:
            parser().print_help()
            return 0
        args = parser().parse_args(arguments)
        tenant = "DEMO — fictional tenant" if args.demo else guid(os.environ.get("AZURE_TENANT_ID"))
        if client is None:
            client = DemoClient() if args.demo else GraphClient(get_token())
        json_only = getattr(args, "json", False)
        if not json_only:
            print("ENTRA ID ACCESS REVIEW | " + ("DEMO / NO NETWORK" if args.demo else "LIVE / " + tenant))
            print()
        if args.command in ("roles", "reviews"):
            rows = getattr(client, args.command)()
            if json_only:
                print(safe_json(rows))
            elif args.command == "roles":
                table(rows, [("ROLE", "displayName", 38), ("ROLE ID", "id", 36)])
            else:
                table(
                    rows, [("REVIEW", "displayName", 38), ("STATUS", "status", 16), ("REVIEW ID", "id", 36)]
                )
        elif args.command == "assignments":
            rows = client.assignments(args.role)
            if json_only:
                print(safe_json(rows))
            else:
                print("Direct active assignments; principal names/types are not resolved.\n")
                table(
                    rows, [("PRINCIPAL ID", "principalId", 36), ("DIRECTORY SCOPE", "directoryScopeId", 38)]
                )
        elif args.command == "details":
            print(safe_json(client.details(args.review_id)))
        else:
            if args.command == "create":
                today = "2026-10-17" if args.demo else datetime.now(timezone.utc).date().isoformat()
                start = args.start or today
                if start < today:
                    raise ReviewError("Start date cannot be in the past.")
                plan = create_plan(
                    client, tenant, args.role, args.reviewer, args.frequency, start, args.assignment
                )
            else:
                plan = delete_plan(client, tenant, args.review_id)
            print(
                "CHANGE PREVIEW — "
                + ("create one review" if args.command == "create" else "delete entire review series")
            )
            plan_summary(plan)
            print(safe_json(plan))
            if not args.apply:
                print("DRY RUN: no change sent. Use --apply to preview again and confirm.")
                return 0
            phrase = confirmation(plan)
            print(f"Type exactly {phrase} to apply this plan to the displayed tenant.")
            result = apply_plan(client, plan, input_fn("> "))
            print(
                "DEMO: simulated change; discarded on exit." if args.demo else "Graph confirmed the change."
            )
            if result:
                print(safe_json(result))
        return 0
    except (ReviewError, EOFError, KeyboardInterrupt) as error:
        print(
            "Error: "
            + (str(error) if isinstance(error, ReviewError) else "Cancelled. No further requests sent."),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
