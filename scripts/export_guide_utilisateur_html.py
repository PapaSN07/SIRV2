#!/usr/bin/env python3
"""Export docs/GUIDE_UTILISATEUR_DISTRIBUTION.md → HTML autonome imprimable."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_modele_donnees_html import md_to_html_body  # noqa: E402

MD_PATH = ROOT / "docs" / "GUIDE_UTILISATEUR_DISTRIBUTION.md"
OUT_PATH = ROOT / "docs" / "GUIDE_UTILISATEUR_DISTRIBUTION.html"

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Guide utilisateur — Interruptions distribution — SENELEC</title>
  <style>
    :root {{
      --ink: #3c1053;
      --muted: #555;
      --border: #d0d7de;
      --bg: #fafbfc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Calibri, Arial, sans-serif;
      font-size: 15px;
      line-height: 1.55;
      color: #222;
      background: var(--bg);
    }}
    .page {{
      max-width: 920px;
      margin: 0 auto;
      padding: 2rem 1.5rem 4rem;
      background: #fff;
      box-shadow: 0 0 0 1px var(--border);
    }}
    h1, h2, h3 {{
      color: var(--ink);
      line-height: 1.25;
    }}
    h1 {{ font-size: 1.85rem; border-bottom: 3px solid var(--ink); padding-bottom: 0.4rem; }}
    h2 {{ font-size: 1.35rem; margin-top: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; }}
    h3 {{ font-size: 1.1rem; margin-top: 1.4rem; }}
    p {{ margin: 0.75rem 0; }}
    ul, ol {{ margin: 0.5rem 0 1rem; padding-left: 1.4rem; }}
    li {{ margin: 0.25rem 0; }}
    hr {{ border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1rem 0 1.5rem;
      font-size: 0.92rem;
    }}
    th, td {{
      border: 1px solid var(--border);
      padding: 0.45rem 0.65rem;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--ink);
      color: #fff;
      font-weight: 600;
    }}
    tr:nth-child(even) td {{ background: #f6f8fa; }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.9em;
      background: #f0f3f6;
      padding: 0.1em 0.35em;
      border-radius: 3px;
    }}
    em {{ color: var(--muted); }}
    .mermaid {{
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1rem;
      margin: 1.25rem 0;
      overflow-x: auto;
      text-align: center;
    }}
    .banner {{
      background: #f6eef8;
      border-left: 4px solid var(--ink);
      padding: 0.75rem 1rem;
      margin-bottom: 1.5rem;
      font-size: 0.95rem;
    }}
    .footer {{
      margin-top: 3rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border);
      font-size: 0.85rem;
      color: var(--muted);
      font-style: italic;
    }}
    @media print {{
      body {{ background: #fff; }}
      .page {{ box-shadow: none; max-width: none; padding: 0; }}
      .banner {{ break-inside: avoid; }}
      .mermaid {{ break-inside: avoid; }}
      h2 {{ break-after: avoid; }}
      table, tr {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="banner">
      <strong>Guide BCC / BRC — interruptions distribution</strong> —
      ouvrez ce fichier dans Chrome ou Edge.
      Pour un PDF : <kbd>Ctrl</kbd>+<kbd>P</kbd> → « Enregistrer au format PDF ».
    </div>
    {body}
    <p class="footer">
      Document SIR / SENELEC — export HTML depuis docs/GUIDE_UTILISATEUR_DISTRIBUTION.md
      (schéma Mermaid rendu dans le navigateur).
    </p>
  </div>
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
    mermaid.initialize({{
      startOnLoad: true,
      theme: "neutral",
      securityLevel: "loose",
      flowchart: {{ useMaxWidth: true, htmlLabels: true }},
    }});
  </script>
</body>
</html>
"""


def convert() -> Path:
    md = MD_PATH.read_text(encoding="utf-8")
    body = md_to_html_body(md)
    html_doc = HTML_TEMPLATE.format(body=body)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html_doc, encoding="utf-8")
    return OUT_PATH


if __name__ == "__main__":
    path = convert()
    content = path.read_text(encoding="utf-8")
    n_mermaid = content.count('class="mermaid"')
    print(path.resolve())
    print(f"size={path.stat().st_size}")
    print(f"diagrammes_mermaid={n_mermaid}")
