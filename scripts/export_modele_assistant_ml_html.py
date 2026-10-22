#!/usr/bin/env python3
"""Export docs/MODELE_ASSISTANT_ML.md → HTML autonome avec diagrammes Mermaid."""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "docs" / "MODELE_ASSISTANT_ML.md"
OUT_PATH = ROOT / "docs" / "MODELE_ASSISTANT_ML.html"

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Modèle relationnel Assistant ML — SIRV2 / SENELEC</title>
  <style>
    :root {{
      --ink: #1b3a57;
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
    ul {{ margin: 0.5rem 0 1rem; padding-left: 1.4rem; }}
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
      background: #e8f1f8;
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
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="banner">
      <strong>Version complète avec diagrammes</strong> —
      ouvrez ce fichier dans Chrome ou Edge.
      Pour un PDF : <kbd>Ctrl</kbd>+<kbd>P</kbd> → « Enregistrer au format PDF ».
    </div>
    {body}
    <p class="footer">
      Document SIRV2 / SENELEC — Assistant ML P0 — export HTML depuis docs/MODELE_ASSISTANT_ML.md
      (diagrammes Mermaid rendus dans le navigateur).
    </p>
  </div>
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
    mermaid.initialize({{
      startOnLoad: true,
      theme: "neutral",
      securityLevel: "loose",
      flowchart: {{ useMaxWidth: true, htmlLabels: true }},
      er: {{ useMaxWidth: true }},
      sequence: {{ useMaxWidth: true }},
    }});
  </script>
</body>
</html>
"""


def _inline(text: str) -> str:
    """Convertit gras / italique / code inline en HTML."""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )
    return text


def _table_html(rows_raw: list[str]) -> str:
    rows: list[list[str]] = []
    for line in rows_raw:
        if re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return ""
    parts = ["<table>"]
    for i, row in enumerate(rows):
        tag = "th" if i == 0 else "td"
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<{tag}>{_inline(cell)}</{tag}>")
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)


def md_to_html_body(md: str) -> str:
    """Convertit un sous-ensemble Markdown (titres, listes, tableaux, Mermaid)."""
    mermaids: list[str] = []

    def _store_mermaid(m: re.Match[str]) -> str:
        mermaids.append(m.group(1).strip())
        return f"\n@@MERMAID_{len(mermaids) - 1}@@\n"

    md = re.sub(r"```mermaid\n(.*?)```", _store_mermaid, md, flags=re.DOTALL)
    md = re.sub(
        r"```[a-zA-Z]*\n(.*?)```",
        lambda m: "\n<pre><code>" + html.escape(m.group(1).rstrip()) + "</code></pre>\n",
        md,
        flags=re.DOTALL,
    )

    out: list[str] = []
    lines = md.splitlines()
    i = 0
    table_buf: list[str] = []
    list_open = False
    ol_open = False

    def flush_table() -> None:
        nonlocal table_buf
        if table_buf:
            out.append(_table_html(table_buf))
            table_buf = []

    def close_list() -> None:
        nonlocal list_open, ol_open
        if list_open:
            out.append("</ul>")
            list_open = False
        if ol_open:
            out.append("</ol>")
            ol_open = False

    while i < len(lines):
        line = lines[i]

        m_ph = re.match(r"^@@MERMAID_(\d+)@@$", line.strip())
        if m_ph:
            flush_table()
            close_list()
            idx = int(m_ph.group(1))
            out.append(f'<div class="mermaid">\n{mermaids[idx]}\n</div>')
            i += 1
            continue

        if "|" in line and line.strip().startswith("|"):
            close_list()
            table_buf.append(line)
            i += 1
            continue

        flush_table()

        if line.startswith("# "):
            close_list()
            out.append(f"<h1>{_inline(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            close_list()
            out.append(f"<h2>{_inline(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            close_list()
            out.append(f"<h3>{_inline(line[4:].strip())}</h3>")
        elif line.strip() == "---":
            close_list()
            out.append("<hr />")
        elif re.match(r"^\d+\.\s+", line.strip()):
            if list_open:
                out.append("</ul>")
                list_open = False
            if not ol_open:
                out.append("<ol>")
                ol_open = True
            item = re.sub(r"^\d+\.\s+", "", line.strip())
            out.append(f"<li>{_inline(item)}</li>")
        elif line.strip().startswith("- "):
            if ol_open:
                out.append("</ol>")
                ol_open = False
            if not list_open:
                out.append("<ul>")
                list_open = True
            out.append(f"<li>{_inline(line.strip()[2:])}</li>")
        elif line.strip().startswith("<pre>"):
            close_list()
            out.append(line)
        elif not line.strip():
            close_list()
        else:
            close_list()
            out.append(f"<p>{_inline(line.strip())}</p>")
        i += 1

    flush_table()
    close_list()
    return "\n".join(out)


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
