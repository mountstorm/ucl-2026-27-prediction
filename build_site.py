#!/usr/bin/env python3
"""Run the live model and write site/data.js for the website.

Besides today's prediction, it replays the season one matchday at a time
(odds before matchday 1, after matchday 1, ...) so the site can show how
each club's chances moved, like a price chart.

    python build_site.py                 # 50,000 sims now, 20,000 per history point
    python build_site.py --sims 10000    # quicker
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

from ucl_predictor.draw import validate_draw
from ucl_predictor.model import MatchModel, load_teams
from ucl_predictor.simulate import STAGES, SimConfig, Simulator

ROOT = Path(__file__).resolve().parent


def load_schedule(path: Path):
    """[(matchday, home, away)] in file order."""
    with open(path, newline="", encoding="utf-8") as fh:
        return [(int(r["matchday"]), r["home"].strip(), r["away"].strip()) for r in csv.DictReader(fh)]


def load_played(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        return {(r["home"].strip(), r["away"].strip()): (int(r["home_goals"]), int(r["away_goals"]))
                for r in csv.DictReader(fh) if r.get("home")}


def simulate(teams, model, fixtures, played, n, seed):
    sim = Simulator(teams, model, fixtures, played, SimConfig(n_sims=n, seed=seed))
    return sim, sim.run()


def standings(teams, schedule, played):
    rows = {t.name: dict(p=0, w=0, d=0, l=0, gf=0, ga=0, agf=0, pts=0) for t in teams}
    for _, h, a in schedule:
        if (h, a) not in played:
            continue
        hg, ag = played[(h, a)]
        H, A = rows[h], rows[a]
        H["p"] += 1; A["p"] += 1
        H["gf"] += hg; H["ga"] += ag; A["gf"] += ag; A["ga"] += hg; A["agf"] += ag
        if hg > ag:
            H["w"] += 1; A["l"] += 1; H["pts"] += 3
        elif hg < ag:
            A["w"] += 1; H["l"] += 1; A["pts"] += 3
        else:
            H["d"] += 1; A["d"] += 1; H["pts"] += 1; A["pts"] += 1
    order = sorted(rows, key=lambda n: (rows[n]["pts"], rows[n]["gf"] - rows[n]["ga"], rows[n]["gf"],
                                        rows[n]["agf"], rows[n]["w"]), reverse=True)
    return rows, order


DISPLAY = {"Atletico Madrid": "Atlético Madrid", "Bodo/Glimt": "Bodø/Glimt", "Fenerbahce": "Fenerbahçe"}


def _pct(p: float) -> str:
    return f"{100 * p:.1f}%"


def write_readme_table(teams, through, n_played, top_final, source):
    """Rewrite the block between the prediction markers in README.md."""
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    start, end = "<!-- prediction:start -->", "<!-- prediction:end -->"
    if start not in text or end not in text:
        return
    top = sorted(teams, key=lambda t: -t["probs"]["champion"])[:10]
    fav = top[0]
    lines = [
        start,
        f"## Current prediction (after matchday {through}, {n_played} of 144 league games played)",
        "",
        "| # | Club | Pts | Rating (pre → now) | Top 8 | Last 16 | QF | SF | Final | **Win** |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for i, t in enumerate(top, 1):
        n = DISPLAY.get(t["name"], t["name"])
        p = t["probs"]
        lines.append(f"| {i} | {'**' + n + '**' if i == 1 else n} | {t['pts']} | {t['rating_pre']:.0f} → {t['rating_now']:.0f} | "
                     f"{_pct(p['top8'])} | {_pct(p['r16'])} | {_pct(p['qf'])} | {_pct(p['sf'])} | {_pct(p['final'])} | **{_pct(p['champion'])}** |")
    a, b = (DISPLAY.get(x, x) for x in (top_final["a"], top_final["b"]))
    fetched = f" Results from {source['source']}, fetched {source['fetched_at']}." if source.get("fetched_at") else ""
    lines += ["", f"Favourite: **{DISPLAY.get(fav['name'], fav['name'])}** ({_pct(fav['probs']['champion'])}, "
                  f"{_pct(fav['history']['champion'][0])} before matchday 1). Most likely final: {a} v {b} ({_pct(top_final['p'])}).{fetched}",
              end]
    i, j = text.index(start), text.index(end) + len(end)
    path.write_text(text[:i] + "\n".join(lines) + text[j:], encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sims", type=int, default=50000)
    ap.add_argument("--history-sims", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--out", type=Path, default=ROOT / "site" / "data.js")
    args = ap.parse_args()

    teams = load_teams(ROOT / "data" / "teams.csv")
    schedule = load_schedule(ROOT / "data" / "fixtures.csv")
    fixtures = [(h, a) for _, h, a in schedule]
    validate_draw(teams, fixtures)
    played = load_played(ROOT / "data" / "results.csv")
    md_of = {(h, a): md for md, h, a in schedule}
    through = max((md_of[k] for k in played), default=0)
    model = MatchModel()
    src_path = ROOT / "data" / "source.json"
    source = json.loads(src_path.read_text()) if src_path.exists() else {"source": "manual"}
    t0 = time.time()

    # History: odds after each completed matchday (0 = before a ball was kicked).
    history = {s: defaultdict(list) for s in STAGES}
    for k in range(through + 1):
        subset = {f: r for f, r in played.items() if md_of[f] <= k}
        n = args.sims if k == through else args.history_sims
        sim, res = simulate(teams, model, fixtures, subset, n, args.seed)
        for t in teams:
            for s in STAGES:
                history[s][t.name].append(round(res.prob(t.name, s), 5))
        print(f"  after matchday {k}: {n:,} sims ({time.time() - t0:.0f}s)")

    # `sim` / `res` now hold the full, current run.
    rows, order = standings(teams, schedule, played)
    table_pos = {n: i + 1 for i, n in enumerate(order)}
    now = sim.start_ratings

    out_teams = []
    for t in teams:
        r = rows[t.name]
        games = []
        for md, h, a in schedule:
            if t.name not in (h, a):
                continue
            home = h == t.name
            opp = a if home else h
            g = {"md": md, "opp": opp, "home": home}
            if (h, a) in played:
                hg, ag = played[(h, a)]
                g["gf"], g["ga"] = (hg, ag) if home else (ag, hg)
            else:
                w, d, l = model.score_probs(now[h], now[a])
                g["pw"], g["pd"], g["pl"] = (round(w, 3), round(d, 3), round(l, 3)) if home else \
                                            (round(l, 3), round(d, 3), round(w, 3))
            games.append(g)
        n = res.n_sims
        out_teams.append({
            "name": t.name, "country": t.country, "pot": t.pot,
            "rating_pre": t.rating, "rating_now": round(now[t.name], 1),
            "table_pos": table_pos[t.name],
            "p": r["p"], "w": r["w"], "d": r["d"], "l": r["l"], "gf": r["gf"], "ga": r["ga"], "pts": r["pts"],
            "avg_points": round(res.points_sum[t.name] / n, 2),
            "avg_position": round(res.position_sum[t.name] / n, 2),
            "pos_hist": [round(c / n, 4) for c in res.position_hist[t.name]],
            "probs": {s: round(res.prob(t.name, s), 5) for s in STAGES},
            "history": {s: history[s][t.name] for s in STAGES},
            "games": games,
        })

    finals = sorted(res.finals.items(), key=lambda kv: -kv[1])[:10]
    data = {
        "updated": date.today().isoformat(),
        "through_md": through,
        "n_played": len(played),
        "n_sims": args.sims,
        "history_sims": args.history_sims,
        "seed": args.seed,
        "model": {"elo_k": model.elo_k, "rho": model.rho, "home_advantage": model.home_advantage,
                  "rating_noise": SimConfig().rating_noise},
        "teams": out_teams,
        "finals": [{"a": a, "b": b, "p": round(c / res.n_sims, 4)} for (a, b), c in finals],
        "source": source,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("// Generated by build_site.py. Do not edit by hand.\nwindow.UCL = "
                        + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    write_readme_table(out_teams, through, len(played), data["finals"][0], source)
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
