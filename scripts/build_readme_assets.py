"""Capture the offline CLI and generate self-contained screenshot source pages.

Run with the project virtual environment, then follow docs/visuals.md to capture PNGs.
No tenant data, network calls or image-generation service is used.
"""

import html
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
ROLE = "11111111-1111-4111-8111-111111111111"
REVIEWER = "44444444-4444-4444-8444-444444444444"


def capture(*args):
    return subprocess.check_output(  # noqa: S603 - fixed local CLI, no shell
        [sys.executable, str(ROOT / "app.py"), "--demo", *args], cwd=ROOT, text=True, timeout=10
    )


def terminal(command, output, title="Offline demo", extra=""):
    return (
        f'<section class="terminal {extra}"><div class="bar"><span class="dots">● ● ●</span>'
        f'{html.escape(title)}</div><div class="content"><div class="command">'
        f"$ {html.escape(command)}</div><pre>{html.escape(output)}</pre></div></section>"
    )


def page(name, title, body, height):
    style = (ASSETS / "theme.css").read_text(encoding="utf-8")
    output = (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{style}</style>"
        f'<body style="height:{height}px"><main>{body}</main></body></html>'
    )
    (ASSETS / f"{name}.html").write_text(output, encoding="utf-8")


def run():
    roles = capture("roles")
    reviews = capture("reviews")
    assignments = capture("assignments", "--role", ROLE)
    plan = capture(
        "create",
        "--role",
        ROLE,
        "--reviewer",
        REVIEWER,
        "--assignment",
        "eligible",
        "--frequency",
        "quarterly",
    )
    summary, payload = plan.split("\nFull change plan:\n", 1)
    footer = "<footer>Captured from the CLI · Fictional data · No login or tenant changes</footer>"
    hero = (
        '<div class="eyebrow"><span class="mark">E</span> ENTRA ID ACCESS REVIEW TOOL</div>'
        '<div class="hero"><div class="intro"><div class="tag">IDENTITY &amp; ACCESS GOVERNANCE</div>'
        "<h1>Inspect access.<br>Review scope.<br><em>Confirm changes.</em></h1>"
        "<p>A local Microsoft Graph CLI for deliberate<br>directory-role access reviews.</p>"
        '<div class="pills"><span>Dry run by default</span><span>Offline demo</span></div>'
        '<div class="small">Python 3.11–3.13 · Microsoft Graph v1.0</div></div>'
        + terminal("python app.py --demo roles", roles, "Role inventory / fictional data")
        + '</div><div class="bottom"><span>Explicit scope. Explicit reviewers. Explicit confirmation.</span>'
        "<span>p4pryk / EntraIDAccessReviewTool</span></div>"
    )
    page("readme-hero", "Entra ID Access Review Tool", hero, 760)
    inventory = (
        '<div class="eyebrow">01 / INSPECT</div><h2>See the roles. Trace the assignments.</h2>'
        '<p>Readable tables for people. Complete JSON records for scripts.</p><div class="stack">'
        + terminal("python app.py --demo roles", roles, "Directory role definitions")
        + terminal(
            "python app.py --demo assignments --role " + ROLE, assignments, "Direct active assignments"
        )
        + terminal("python app.py --demo reviews", reviews, "Review schedule definitions")
        + "</div>"
        + footer
    )
    page("inventory", "Inspect roles, assignments and review definitions", inventory, 1300)
    preview = (
        '<div class="eyebrow">02 / PREVIEW</div><h2>Understand the change before it happens.</h2>'
        "<p>One role. Explicit reviewers. A tenant-bound confirmation phrase.</p>"
        '<div class="preview-grid"><div>'
        + terminal(
            "python app.py --demo create --role … --reviewer …\n  --assignment eligible --frequency quarterly",
            summary,
            "Change summary / excerpt",
            "summary",
        )
        + '<div class="note"><b>Dry run is the default.</b><p>Adding --apply prints the plan again and asks for the exact confirmation phrase.</p>'
        "<b>Automatic access removal is disabled.</b><p>Review decisions require a separate administrator action to take effect.</p></div></div>"
        + terminal("Full change plan", payload, "Payload / complete output", "payload")
        + "</div>"
        + footer
    )
    page("change-preview", "Preview a scoped access review", preview, 1280)
    print("Generated 3 self-contained visual source pages from real offline CLI output.")


if __name__ == "__main__":
    run()
