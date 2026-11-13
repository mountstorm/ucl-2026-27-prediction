"""Writes predictions to CSV, Markdown and a standalone HTML page."""

from __future__ import annotations

import csv
import html
from pathlib import Path

from .simulate import Results

COLUMNS = [
    ("top8", "Top 8"),
    ("top24", "Top 24"),
    ("r16", "Last 16"),
    ("qf", "QF"),
    ("sf", "SF"),
    ("final", "Final"),
    ("champion", "Win"),
]


def rows(res: Results):
    out = []
    now = res.start_ratings or {}
    for t in res.teams:
        n = res.n_sims
        out.append(
            {
                "team": t.name,
                "country": t.country,
                "pot": t.pot,
                "rating": t.rating,
                "rating_now": now.get(t.name, t.rating),
                "avg_points": res.points_sum[t.name] / n,
                "avg_position": res.position_sum[t.name] / n,
                **{k: res.prob(t.name, k) for k, _ in COLUMNS},
            }
        )
    out.sort(key=lambda r: (-r["champion"], -r["final"], r["avg_position"]))
    return out


def write_csv(res: Results, path: Path):
    data = rows(res)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
        w.writeheader()
        for r in data:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})


def _pct(x: float) -> str:
    if x == 0:
        return "–"
    if x < 0.001:
        return "<0.1%"
    return f"{100 * x:.1f}%"


def top_finals(res: Results, k: int = 10):
    return sorted(res.finals.items(), key=lambda kv: -kv[1])[:k]


def write_markdown(res: Results, path: Path, meta: dict):
    data = rows(res)
    lines = [
        "# UEFA Champions League 2026-27: Monte Carlo prediction",
        "",
        f"*{res.n_sims:,} simulated seasons · seed {meta['seed']} · fixtures: {meta['fixtures_source']} · "
        f"played results fixed: {meta['n_played']}*",
        "",
        f"**Predicted winner: {data[0]['team']}** ({_pct(data[0]['champion'])})",
        "",
        "## Title odds and stage probabilities",
        "",
        "| # | Team | Pot | Rating (pre → now) | Avg pts | Avg pos | " + " | ".join(lbl for _, lbl in COLUMNS) + " |",
        "|---|------|-----|------:|--------:|--------:|" + "|".join("------:" for _ in COLUMNS) + "|",
    ]
    for i, r in enumerate(data, 1):
        lines.append(
            f"| {i} | {r['team']} | {r['pot']} | {r['rating']:.0f} → {r['rating_now']:.0f} | "
            f"{r['avg_points']:.1f} | {r['avg_position']:.1f} | "
            + " | ".join(_pct(r[k]) for k, _ in COLUMNS)
            + " |"
        )
    lines += ["", "## Most likely finals (Madrid, 5 June 2027)", "", "| Final | Probability |", "|---|---:|"]
    for (a, b), c in top_finals(res):
        lines.append(f"| {a} v {b} | {_pct(c / res.n_sims)} |")
    lines += ["", "## Projected league-phase table (by average position)", ""]
    lines += ["| Pos | Team | Avg pts | Outcome |", "|---:|---|---:|---|"]
    by_pos = sorted(data, key=lambda r: r["avg_position"])
    for i, r in enumerate(by_pos, 1):
        zone = "Round of 16" if i <= 8 else ("Play-off" if i <= 24 else "Eliminated")
        lines.append(f"| {i} | {r['team']} | {r['avg_points']:.1f} | {zone} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(res: Results, path: Path, meta: dict):
    data = rows(res)
    max_win = max(r["champion"] for r in data) or 1.0
    body_rows = []
    for i, r in enumerate(data, 1):
        bar = 100 * r["champion"] / max_win
        cells = "".join(f"<td class='n'>{_pct(r[k])}</td>" for k, _ in COLUMNS[:-1])
        body_rows.append(
            f"<tr><td class='n'>{i}</td><td>{html.escape(r['team'])}</td><td class='n'>{r['pot']}</td>"
            f"<td class='n'>{r['avg_points']:.1f}</td>{cells}"
            f"<td class='win'><span class='bar' style='width:{bar:.1f}%'></span><span class='v'>{_pct(r['champion'])}</span></td></tr>"
        )
    finals = "".join(
        f"<li>{html.escape(a)} v {html.escape(b)} <b>{_pct(c / res.n_sims)}</b></li>" for (a, b), c in top_finals(res, 6)
    )
    head = "".join(f"<th>{lbl}</th>" for _, lbl in COLUMNS)
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>UCL 2026-27 Prediction</title>
<style>
:root {{ --bg:#fbfaf7; --fg:#1d1d1f; --muted:#6b6b70; --line:#e4e2dc; --accent:#1f4fd1; --accent-soft:#dbe4fb; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141416; --fg:#ececef; --muted:#9a9aa2; --line:#2b2b30; --accent:#7ea2ff; --accent-soft:#25335a; }} }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif; }}
main {{ max-width:1040px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:26px; margin:0 0 4px; }} p.meta {{ color:var(--muted); margin:0 0 24px; }}
.hero {{ font-size:18px; margin-bottom:24px; }} .hero b {{ color:var(--accent); }}
.wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:10px; }}
table {{ border-collapse:collapse; width:100%; min-width:760px; }}
th,td {{ padding:7px 10px; border-bottom:1px solid var(--line); text-align:left; white-space:nowrap; }}
th {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); font-weight:600; }}
td.n,th:not(:nth-child(2)) {{ text-align:right; font-variant-numeric:tabular-nums; }}
td.win {{ position:relative; min-width:140px; text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }}
.bar {{ position:absolute; left:10px; top:8px; bottom:8px; background:var(--accent-soft); border-radius:3px; max-width:calc(100% - 70px); }}
.v {{ position:relative; }}
h2 {{ font-size:18px; margin:32px 0 8px; }} ul {{ padding-left:18px; }} li b {{ color:var(--accent); }}
</style></head><body><main>
<h1>Champions League 2026-27 prediction</h1>
<p class="meta">{res.n_sims:,} simulated seasons · seed {meta['seed']} · fixtures: {html.escape(meta['fixtures_source'])} · played results fixed: {meta['n_played']}</p>
<p class="hero">Predicted winner: <b>{html.escape(data[0]['team'])}</b> ({_pct(data[0]['champion'])})</p>
<div class="wrap"><table><thead><tr><th>#</th><th>Team</th><th>Pot</th><th>Avg pts</th>{head}</tr></thead>
<tbody>{''.join(body_rows)}</tbody></table></div>
<h2>Most likely finals</h2><ul>{finals}</ul>
</main></body></html>"""
    path.write_text(doc, encoding="utf-8")
