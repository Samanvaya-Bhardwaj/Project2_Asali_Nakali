#!/usr/bin/env python3
"""
make_diff_report.py
-------------------
Builds dashboard/vibe/index.html: the prompts, the code as first generated, and a
highlighted diff of every change made since, so rubric item 3 can be shown from
the running dashboard (http://localhost:8011/vibe/index.html).

Three snapshots are compared:
  vibe_coding/phase1_baseline/   the project before phase 2 began
  vibe_coding/generated_v0/      phase-2 code exactly as the assistant first wrote it
  the working tree               what the project is now

Rerun after any edit; your own changes show up highlighted automatically.

    python vibe_coding/make_diff_report.py
"""

from __future__ import annotations
import difflib
import html
import os
import re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
V0 = os.path.join(HERE, "generated_v0")
P1 = os.path.join(HERE, "phase1_baseline")
OUT = os.path.join(ROOT, "dashboard", "vibe", "index.html")


def read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def files_under(base):
    out = []
    for d, _, names in os.walk(base):
        for n in names:
            rel = os.path.relpath(os.path.join(d, n), base).replace("\\", "/")
            if rel != "SNAPSHOT_TAKEN_AT.txt":
                out.append(rel)
    return sorted(out)


def stats(a, b):
    plus = minus = 0
    for line in difflib.unified_diff(a, b, lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            plus += 1
        elif line.startswith("-") and not line.startswith("---"):
            minus += 1
    return plus, minus


def md(text):
    """A small Markdown renderer: headings, paragraphs, lists, quotes, tables, code, emphasis."""
    def inline(s):
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", s)
        return s

    out, para, lst, quote, table = [], [], [], [], []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()
        if lst:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in lst) + "</ul>")
            lst.clear()
        if quote:
            out.append("<blockquote>" + md("\n".join(quote)) + "</blockquote>")
            quote.clear()
        if table:
            rows = [r for r in table if not re.match(r"^\|[\s\-|:]+\|$", r)]
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            h = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells[0]) + "</tr></thead><tbody>"
            h += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
            out.append(h + "</tbody></table>")
            table.clear()

    for line in text.splitlines():
        if line.startswith(">"):
            if not quote:
                flush()
            body = line[1:]
            quote.append(body[1:] if body.startswith(" ") else body)   # keep continuation indents
            continue
        if quote:
            flush()
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            flush()
            n = len(m.group(1)) + 1
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif line.startswith("|"):
            if para or lst:
                flush()
            table.append(line)
        elif re.match(r"^\s*[*\-]\s+", line):
            if para or table:
                flush()
            lst.append(re.sub(r"^\s*[*\-]\s+", "", line))
        elif re.match(r"^\s*\d+\.\s+", line):
            if para or table:
                flush()
            lst.append(re.sub(r"^\s*\d+\.\s+", "", line))
        elif line.strip() == "---":
            flush()
            out.append("<hr>")
        elif not line.strip():
            flush()
        elif lst and line.startswith("  "):
            lst[-1] += " " + line.strip()
        else:
            if table:
                flush()
            para.append(line.strip())
    flush()
    return "\n".join(out)


def diff_table(a, b, left, right):
    return difflib.HtmlDiff(tabsize=4, wrapcolumn=96).make_table(a, b, left, right, context=True, numlines=2)


CSS = """
:root{--bg:#0b0c0e;--surface:#131519;--inset:#0e0f12;--ink:#eef0f2;--muted:#a3a8b0;--faint:#6b7079;--rim:#262a30;
--lime:#d8ff3e;--add:rgba(61,220,132,.20);--add-ink:#8ff0b8;--sub:rgba(255,77,61,.20);--sub-ink:#ff9a90;--chg:rgba(255,197,61,.22);}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f6f6f3;--surface:#fff;--inset:#f0f0ec;--ink:#16181b;
--muted:#4b5058;--faint:#7a7f87;--rim:#dcdcd6;--lime:#5f7a00;--add:rgba(30,160,90,.16);--add-ink:#106b3a;--sub:rgba(210,50,40,.14);
--sub-ink:#9c2219;--chg:rgba(220,160,0,.22);}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "IBM Plex Sans Condensed",system-ui,sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:28px 16px 80px}a{color:var(--lime)}
h1{font:400 clamp(2rem,5vw,3.2rem)/1 "Anton",Impact,sans-serif;letter-spacing:.01em;text-transform:uppercase;margin:6px 0 10px}
h2{font:400 1.7rem/1.1 "Anton",Impact,sans-serif;text-transform:uppercase;margin:44px 0 10px}h3{margin:28px 0 8px}h4,h5{margin:18px 0 6px}
.eyebrow{color:var(--faint);font-size:.8rem}.card{background:var(--surface);border:1px solid var(--rim);border-radius:16px;padding:22px;margin:14px 0}
.lede{color:var(--muted);max-width:80ch}code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.82rem}
code{background:var(--inset);padding:1px 5px;border-radius:5px}blockquote{margin:12px 0;padding:6px 16px;border-left:3px solid var(--lime);color:var(--muted);background:var(--inset);border-radius:0 10px 10px 0}
table{border-collapse:collapse;width:100%;margin:10px 0}th,td{border-bottom:1px solid var(--rim);padding:7px 10px;text-align:left;vertical-align:top}
th{color:var(--faint);font-weight:500;font-size:.8rem}.num{text-align:right;font-variant-numeric:tabular-nums}
.plus{color:var(--add-ink)}.minus{color:var(--sub-ink)}.legend span{display:inline-block;padding:2px 9px;border-radius:6px;margin-right:6px;font-size:.8rem}
details{border:1px solid var(--rim);border-radius:12px;margin:10px 0;background:var(--surface)}summary{cursor:pointer;padding:12px 16px;font-weight:600}
details>div{padding:0 12px 14px;overflow-x:auto}pre.src{background:var(--inset);padding:14px;border-radius:10px;overflow:auto;max-height:540px;line-height:1.5}
table.diff{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.74rem;border:0;width:100%}table.diff td{border:0;padding:1px 6px;white-space:pre-wrap;word-break:break-word}
table.diff th{background:var(--inset);color:var(--muted);font-weight:500}td.diff_header{color:var(--faint);text-align:right;width:1%}td.diff_next{display:none}
.diff_add{background:var(--add)}.diff_chg{background:var(--chg)}.diff_sub{background:var(--sub)}span.diff_add{color:var(--add-ink)}span.diff_sub{color:var(--sub-ink)}
"""


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    snap = (read(os.path.join(V0, "SNAPSHOT_TAKEN_AT.txt")) or ["?"])[0]
    prompts = "\n".join(read(os.path.join(HERE, "PROMPTS.md")) or [])
    changes = "\n".join(read(os.path.join(HERE, "CHANGES.md")) or [])

    v0_files = files_under(V0)
    p1_files = set(files_under(P1))

    gen_rows, gen_diffs, total_p, total_m = [], [], 0, 0
    for rel in v0_files:
        a = read(os.path.join(V0, rel)) or []
        b = read(os.path.join(ROOT, rel))
        if b is None:
            continue
        p, m = stats(a, b)
        total_p += p
        total_m += m
        new = "new in phase 2" if rel not in p1_files else "phase-1 file"
        gen_rows.append(f"<tr><td><code>{html.escape(rel)}</code></td><td>{new}</td><td class='num'>{len(a)}</td>"
                        f"<td class='num plus'>+{p}</td><td class='num minus'>-{m}</td></tr>")
        if p or m:
            gen_diffs.append(f"<details><summary>{html.escape(rel)} <span class='plus'>+{p}</span> "
                             f"<span class='minus'>-{m}</span></summary><div>"
                             f"{diff_table(a, b, 'as generated (v0)', 'now')}</div></details>")

    p1_rows, p1_diffs = [], []
    for rel in sorted(p1_files):
        a = read(os.path.join(P1, rel)) or []
        b = read(os.path.join(ROOT, rel))
        if b is None or a == b:
            continue
        p, m = stats(a, b)
        p1_rows.append(f"<tr><td><code>{html.escape(rel)}</code></td><td class='num plus'>+{p}</td>"
                       f"<td class='num minus'>-{m}</td></tr>")
        p1_diffs.append(f"<details><summary>{html.escape(rel)} <span class='plus'>+{p}</span> "
                        f"<span class='minus'>-{m}</span></summary><div>"
                        f"{diff_table(a, b, 'phase 1', 'now')}</div></details>")

    listings = []
    for rel in v0_files:
        if rel in p1_files:
            continue
        src = "\n".join(read(os.path.join(V0, rel)) or [])
        listings.append(f"<details><summary>{html.escape(rel)} <span class='eyebrow'>{src.count(chr(10)) + 1} lines"
                        f"</span></summary><div><pre class='src'>{html.escape(src)}</pre></div></details>")

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vibe-coding report</title>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=IBM+Plex+Sans+Condensed:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<p class="eyebrow"><a href="../uncertainty.html#vibe">&larr; Back to the uncertainty page</a> &middot; generated {now}</p>
<h1>Prompt, generated code, and what changed</h1>
<p class="lede">Rubric item 3. The prompts that produced the phase-2 code; the code exactly as the assistant first
wrote it (frozen before anything was run, {html.escape(snap)}); and every line changed since, highlighted. A second
set of diffs shows what phase 2 changed in files that already existed in phase 1.</p>
<div class="card legend"><span class="diff_add">added</span><span class="diff_chg">changed</span><span class="diff_sub">removed</span>
&nbsp; Since generation: <strong class="plus">+{total_p}</strong> / <strong class="minus">-{total_m}</strong> lines across
{len(gen_diffs)} file(s) touched after the snapshot.</div>

<h2>1 &middot; The prompts</h2><div class="card">{md(prompts)}</div>

<h2>2 &middot; What was changed after generation, and why</h2><div class="card">{md(changes)}</div>

<h2>3 &middot; Generated code &rarr; now, highlighted</h2>
<div class="card"><table><thead><tr><th>File</th><th>Kind</th><th class="num">Lines as generated</th><th class="num">Added</th><th class="num">Removed</th></tr></thead>
<tbody>{''.join(gen_rows)}</tbody></table></div>
{''.join(gen_diffs) or '<p>No changes since generation.</p>'}

<h2>4 &middot; The generated code, as first written</h2>
<p class="lede">New phase-2 files exactly as generated. Files that already existed in phase 1 are shown as diffs in section 5.</p>
{''.join(listings)}

<h2>5 &middot; Phase 1 &rarr; now, in files that already existed</h2>
<div class="card"><table><thead><tr><th>File</th><th class="num">Added</th><th class="num">Removed</th></tr></thead>
<tbody>{''.join(p1_rows)}</tbody></table></div>
{''.join(p1_diffs)}
</div></body></html>"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  {len(gen_diffs)} generated file(s) changed since the snapshot (+{total_p} / -{total_m} lines)")
    print(f"  {len(p1_rows)} phase-1 file(s) changed by phase 2")
    print(f"  report -> {OUT}")


if __name__ == "__main__":
    main()
