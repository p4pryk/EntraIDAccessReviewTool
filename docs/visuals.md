# Reproduce the README visuals

The three README images are screenshots of local presentation pages populated with **captured output from the actual offline CLI**. They use fictional fixtures; no live tenant data is included. The cover adds editorial typography around a real role inventory. The inventory presents three actual read commands. The change preview splits one actual command's summary and full JSON payload into two columns without changing their content.

Sources are kept beside the PNGs in `docs/assets/`. No external fonts, stock photographs, telemetry, AI-generated product screens or hosted assets are used.

From the repository root, after installing runtime dependencies:

```bash
python scripts/build_readme_assets.py
python examples/demo.py > examples/demo-transcript.txt
```

Open each generated HTML file in a browser and capture at these viewport sizes:

| Source | Viewport | Output |
| --- | --- | --- |
| `docs/assets/readme-hero.html` | 1600 × 760 | `docs/assets/readme-hero.png` |
| `docs/assets/inventory.html` | 1600 × 1300 | `docs/assets/inventory.png` |
| `docs/assets/change-preview.html` | 1600 × 1280 | `docs/assets/change-preview.png` |

For example, with the separately installed `agent-browser` utility:

```bash
agent-browser --session entra-docs --allow-file-access open file:///ABSOLUTE_REPO_PATH/docs/assets/readme-hero.html
agent-browser --session entra-docs set viewport 1600 760
agent-browser --session entra-docs screenshot /ABSOLUTE_REPO_PATH/docs/assets/readme-hero.png
agent-browser --session entra-docs close
```

Repeat for the inventory and change-preview files at their respective viewport sizes. Inspect the images for clipped text and incorrect line wrapping before committing. The visual tool is not a runtime dependency of the access review CLI.
