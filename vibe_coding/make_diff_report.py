#!/usr/bin/env python3
"""
make_diff_report.py
-------------------
Builds dashboard/vibe/index.html: the prompts, the code as first generated, and a
highlighted diff of every change made since, so rubric item 3 can be shown from
the running dashboard (http://localhost:8011/vibe/index.html).

Snapshots compared:
  vibe_coding/phase1_baseline/   the project before phase 2 began
  vibe_coding/generated_v0/      phase-2 code exactly as the assistant first wrote it
  vibe_coding/rounds/NN-name/    each later prompt: ROUND.md (the prompt), FILES.txt
                                 (what it changed) and before/ (those files just before it)
  the working tree               what the project is now

Rerun after any edit; your own changes show up highlighted automatically. For a
new prompt, save the files it will change into a new rounds/ folder first.

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


# Source written after both snapshots (for example integration/replication.py) is
# in neither of them, so it is found here and listed in full.
LATER_DIRS = ("api", "integration", "dashboard", "data", "scripts", "tests")
LATER_EXT = (".py", ".js", ".html", ".css")
LATER_SKIP = ("dashboard/vibe/", "dashboard/_legacy/", "__pycache__", "SYSTEM_GUIDE")


def added_later(known):
    out = []
    for top in LATER_DIRS:
        for rel in files_under(os.path.join(ROOT, top)):
            rel = top + "/" + rel
            if rel.endswith(LATER_EXT) and rel not in known and not any(s in rel for s in LATER_SKIP):
                out.append(rel)
    return sorted(out)


# Requests made after generation ("rounds"). Each vibe_coding/rounds/<NN-name>/
# holds ROUND.md (the prompt, quoted), FILES.txt (what it changed) and before/
# (those files just before it). A file's state after round i is the next round's
# saved copy of it, or the working tree when no later round touched it.
ROUNDS = os.path.join(HERE, "rounds")


def round_names():
    if not os.path.isdir(ROUNDS):
        return []
    return sorted(d for d in os.listdir(ROUNDS) if os.path.isdir(os.path.join(ROUNDS, d)))


def after_round(names, i, rel):
    for later in names[i + 1:]:
        p = os.path.join(ROUNDS, later, "before", rel)
        if os.path.exists(p):
            return read(p)
    return read(os.path.join(ROOT, rel))


def render_rounds():
    names = round_names()
    cards, total_p, total_m = [], 0, 0
    for i, name in enumerate(names):
        d = os.path.join(ROUNDS, name)
        num = name.split("-", 1)[0].lstrip("0")
        files = [l.strip() for l in (read(os.path.join(d, "FILES.txt")) or []) if l.strip()]
        rows, diffs = [], []
        for rel in files:
            a = read(os.path.join(d, "before", rel))
            b = after_round(names, i, rel)
            if b is None:
                continue
            if a is None:
                total_p += len(b)
                rows.append(f"<tr><td><code>{html.escape(rel)}</code></td><td>new file</td>"
                            f"<td class='num plus'>+{len(b)}</td><td class='num minus'>-0</td></tr>")
                diffs.append(f"<details><summary>{html.escape(rel)} <span class='tag'>new file</span> "
                             f"<span class='plus'>+{len(b)}</span></summary><div><pre class='src'>"
                             f"{html.escape(chr(10).join(b))}</pre></div></details>")
                continue
            p, m = stats(a, b)
            if not (p or m):
                continue
            total_p += p
            total_m += m
            rows.append(f"<tr><td><code>{html.escape(rel)}</code></td><td>changed</td>"
                        f"<td class='num plus'>+{p}</td><td class='num minus'>-{m}</td></tr>")
            diffs.append(f"<details><summary>{html.escape(rel)} <span class='plus'>+{p}</span> "
                         f"<span class='minus'>-{m}</span></summary><div>"
                         f"{diff_table(a, b, f'before prompt {num}', f'after prompt {num}')}</div></details>")
        intro = "\n".join(read(os.path.join(d, "ROUND.md")) or [f"# {name}"])
        cards.append(f"<section class='round' id='prompt-{num}'><div class='card'>{md(intro)}"
                     f"<p class='eyebrow' style='margin-top:14px'>Code this prompt changed ({len(rows)} file(s)). "
                     f"Open a file to see it before and after, highlighted.</p>"
                     f"<table><thead><tr><th>File</th><th>Kind</th><th class='num'>Added</th><th class='num'>Removed</th>"
                     f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>{''.join(diffs)}</section>")
    return cards, total_p, total_m, names


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
h1{font:700 clamp(1.9rem,4vw,2.7rem)/1.12 "IBM Plex Sans Condensed",system-ui,sans-serif;letter-spacing:-.02em;margin:6px 0 10px}
h2{font:700 clamp(1.3rem,2.4vw,1.7rem)/1.2 "IBM Plex Sans Condensed",system-ui,sans-serif;letter-spacing:-.015em;margin:56px 0 6px;display:flex;gap:12px;align-items:center}
h2 .n{flex:0 0 auto;width:32px;height:32px;border-radius:9px;background:var(--lime);color:var(--bg);display:grid;place-items:center;font-size:.95rem}
.card h2{font-size:1.25rem;margin:24px 0 8px;display:block}.card h2:first-child{margin-top:0}h3{margin:28px 0 8px}h4,h5{margin:18px 0 6px}
.use{color:var(--muted);max-width:88ch;margin:0 0 12px 44px}.use strong{color:var(--ink)}
.guide{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;margin:18px 0 8px}
.guide a{display:block;padding:12px 14px;border:1px solid var(--rim);border-radius:12px;background:var(--surface);color:var(--ink);text-decoration:none}
.guide a:hover{border-color:var(--lime)}.guide b{display:block;font-size:.92rem}.guide span{display:block;color:var(--muted);font-size:.78rem;margin-top:3px;line-height:1.45}
.tag{font-size:.72rem;padding:1px 7px;border-radius:6px;background:var(--add);color:var(--add-ink);margin-left:4px}.round{margin-top:26px}
@media (max-width:600px){.use{margin-left:0}}
.eyebrow{color:var(--faint);font-size:.8rem}.card{background:var(--surface);border:1px solid var(--rim);border-radius:16px;padding:22px;margin:14px 0}
.lede{color:var(--muted);max-width:80ch}code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.82rem}
code{background:var(--inset);padding:1px 5px;border-radius:5px}blockquote{margin:12px 0;padding:6px 16px;border-left:3px solid var(--lime);color:var(--muted);background:var(--inset);border-radius:0 10px 10px 0}
table{border-collapse:collapse;width:100%;margin:10px 0}th,td{border-bottom:1px solid var(--rim);padding:7px 10px;text-align:left;vertical-align:top}
th{color:var(--faint);font-weight:500;font-size:.8rem}.num{text-align:right;font-variant-numeric:tabular-nums}
.plus{color:var(--add-ink)}.minus{color:var(--sub-ink)}.legend span{display:inline-block;padding:2px 9px;border-radius:6px;margin-right:6px;font-size:.8rem}
details{border:1px solid var(--rim);border-radius:12px;margin:10px 0;background:var(--surface)}summary{cursor:pointer;padding:12px 16px;font-weight:600}
details>div{padding:0 12px 14px;overflow-x:auto}pre.src{background:var(--inset);padding:14px;border-radius:10px;overflow:auto;max-height:540px;line-height:1.5}
table.diff{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.74rem;border:0;width:100%}table.diff td{border:0;padding:1px 6px;white-space:pre-wrap;word-break:break-word}
table.diff th{background:var(--inset);color:var(--muted);font-weight:500}td.diff_next,th.diff_next{display:none}
table.diff td.diff_header{color:var(--faint);text-align:right;width:1%;white-space:nowrap;word-break:normal;padding-right:8px}
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

    later = []
    for rel in added_later(set(v0_files) | p1_files):
        src = "\n".join(read(os.path.join(ROOT, rel)) or [])
        later.append(f"<details><summary>{html.escape(rel)} <span class='eyebrow'>{src.count(chr(10)) + 1} lines"
                     f"</span></summary><div><pre class='src'>{html.escape(src)}</pre></div></details>")

    round_cards, round_p, round_m, names = render_rounds()
    first_later = names[0].split("-", 1)[0].lstrip("0") if names else "12"
    round_links = " &middot; ".join(f"<a href='#prompt-{n.split('-', 1)[0].lstrip('0')}'>prompt {n.split('-', 1)[0].lstrip('0')}</a>"
                                    for n in names)

    def head(n, anchor, title, use):
        return f"<h2 id='{anchor}'><span class='n'>{n}</span>{title}</h2><p class='use'>{use}</p>"

    guide = "".join(f"<a href='#{a}'><b>{n} &middot; {t}</b><span>{s}</span></a>" for n, a, t, s in [
        (1, "prompts", "The prompts", "Every prompt, exactly as typed, including the later requests."),
        (2, "later", "Later prompts and their code", "Each request made after generation, with the code it changed, before → after."),
        (3, "why", "Why each change was made", "Every change after generation, with the problem it fixed."),
        (4, "first", "The generated code, as first written", "The new Phase 2 files exactly as the assistant first wrote them."),
        (5, "since", "Generated code → now", "Every line changed since generation, highlighted."),
        (6, "phase1", "Phase 1 files → now", "What Phase 2 changed in files that already existed in Phase 1."),
        (7, "added", "Files added later", "New files written after the first snapshot, in full."),
    ])

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vibe-coding report</title>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=IBM+Plex+Sans+Condensed:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<p class="eyebrow"><a href="../uncertainty.html#vibe">&larr; Back to Matching &amp; cleaning</a> &middot; built {now}</p>
<p class="eyebrow" style="color:var(--lime)">Rubric item 3 &middot; vibe coding</p>
<h1>The prompts, the code they produced, and every change</h1>
<p class="lede">Three things in one place: the prompts that were typed; the code exactly as the assistant first wrote it
(frozen before anything was run, {html.escape(snap)}); and every line changed since, highlighted. Requests made after
the code was generated (prompt {first_later} onwards) are shown one by one with the code each of them changed.</p>
<div class="card legend"><span class="diff_add">added</span><span class="diff_chg">changed</span><span class="diff_sub">removed</span>
&nbsp; Since generation: <strong class="plus">+{total_p}</strong> / <strong class="minus">-{total_m}</strong> lines in
{len(gen_diffs)} generated file(s). Later prompts: <strong class="plus">+{round_p}</strong> /
<strong class="minus">-{round_m}</strong> lines.</div>
<p class="eyebrow" style="margin-top:22px">What is on this page</p>
<div class="guide">{guide}</div>

{head(1, "prompts", "The prompts", "<strong>Use this to</strong> read every prompt exactly as it was typed: the first request (prompt 0), the 11 prompts the Phase 2 code was generated from, and the later requests (prompt " + first_later + " onwards).")}
<div class="card">{md(prompts)}</div>

{head(2, "later", "Later prompts and the code they changed", "<strong>Use this to</strong> see what each request made after generation did to the code. Each prompt is quoted, then every file it changed is listed; open a file to see it just before and just after that prompt, highlighted. Jump to: " + round_links + ".")}
{''.join(round_cards) or '<p>No later prompts yet.</p>'}

{head(3, "why", "Why each change was made", "<strong>Use this to</strong> read the reason behind every change made after generation: what was wrong, how it was found, and what was done, with the files it touched.")}
<div class="card">{md(changes)}</div>

{head(4, "first", "The generated code, as first written", "<strong>Use this to</strong> see the new Phase 2 files exactly as the assistant first wrote them, before anything was run. Files that already existed in Phase 1 are shown as diffs in part 6.")}
{''.join(listings)}

{head(5, "since", "Generated code &rarr; now, highlighted", "<strong>Use this to</strong> see every line changed in the generated files since generation, all prompts together. Open a file for the highlighted diff.")}
<div class="card"><table><thead><tr><th>File</th><th>Kind</th><th class="num">Lines as generated</th><th class="num">Added</th><th class="num">Removed</th></tr></thead>
<tbody>{''.join(gen_rows)}</tbody></table></div>
{''.join(gen_diffs) or '<p>No changes since generation.</p>'}

{head(6, "phase1", "Phase 1 files &rarr; now", "<strong>Use this to</strong> see what Phase 2 changed in files that already existed in Phase 1.")}
<div class="card"><table><thead><tr><th>File</th><th class="num">Added</th><th class="num">Removed</th></tr></thead>
<tbody>{''.join(p1_rows)}</tbody></table></div>
{''.join(p1_diffs)}

{head(7, "added", "Files added later", "<strong>Use this to</strong> read, in full, the new files written after the first snapshot (their reasons are in part 3).")}
{''.join(later) or '<p>None.</p>'}
</div></body></html>"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  {len(gen_diffs)} generated file(s) changed since the snapshot (+{total_p} / -{total_m} lines)")
    print(f"  {len(p1_rows)} phase-1 file(s) changed by phase 2")
    print(f"  {len(later)} file(s) added after both snapshots")
    print(f"  {len(names)} later prompt(s) shown with their code (+{round_p} / -{round_m} lines)")
    print(f"  report -> {OUT}")


if __name__ == "__main__":
    main()
