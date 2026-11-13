#!/usr/bin/env python3
"""Predict the UEFA Champions League 2026-27 with Monte Carlo simulation.

Examples:
    python predict.py                                  # 50,000 sims, generated draw
    python predict.py --sims 50000 --resample-draw     # average over many possible draws
    python predict.py --fixtures data/fixtures.csv --results data/results.csv   # live mode
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from pathlib import Path

from ucl_predictor.draw import generate_draw, load_fixtures, save_fixtures, validate_draw
from ucl_predictor.model import MatchModel, load_teams
from ucl_predictor.report import COLUMNS, rows, write_csv, write_html, write_markdown
from ucl_predictor.simulate import SimConfig, Simulator

ROOT = Path(__file__).resolve().parent


def load_results(path: Path, fixtures, team_names):
    played = {}
    if not path.exists():
        return played
    fixture_set = set(fixtures)
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r.get("home"):
                continue
            key = (r["home"].strip(), r["away"].strip())
            for name in key:
                if name not in team_names:
                    sys.exit(f"results: unknown team '{name}' (names must match data/teams.csv)")
            if key not in fixture_set:
                sys.exit(f"results: {key[0]} v {key[1]} is not in the fixture list")
            played[key] = (int(r["home_goals"]), int(r["away_goals"]))
    return played


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--teams", type=Path, default=ROOT / "data" / "teams.csv")
    ap.add_argument("--fixtures", type=Path, default=None, help="CSV home,away with all 144 league-phase games")
    ap.add_argument("--results", type=Path, default=ROOT / "data" / "results.csv",
                    help="CSV home,away,home_goals,away_goals of games already played")
    ap.add_argument("--sims", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--noise", type=float, default=45.0, help="sd of the per-season rating shock")
    ap.add_argument("--home-advantage", type=float, default=60.0)
    ap.add_argument("--elo-k", type=float, default=20.0,
                    help="Elo K-factor for rating updates after each match (0 = static ratings)")
    ap.add_argument("--rho", type=float, default=-0.12,
                    help="Dixon-Coles low-score correction (0 = independent Poisson)")
    ap.add_argument("--winter-noise", type=float, default=0.0,
                    help="sd of an extra rating shock before the knockouts")
    ap.add_argument("--resample-draw", action="store_true",
                    help="draw new league-phase fixtures in every simulation")
    ap.add_argument("--out", type=Path, default=ROOT / "output")
    args = ap.parse_args(argv)

    teams = load_teams(args.teams)
    names = {t.name for t in teams}
    args.out.mkdir(parents=True, exist_ok=True)

    if args.fixtures:
        fixtures = load_fixtures(args.fixtures)
        validate_draw(teams, fixtures)
        source = str(args.fixtures.name)
        if args.resample_draw:
            sys.exit("--resample-draw cannot be combined with --fixtures")
    else:
        fixtures = generate_draw(teams, random.Random(args.seed))
        save_fixtures(args.out / "generated_fixtures.csv", fixtures)
        source = "re-drawn every sim" if args.resample_draw else "generated draw (output/generated_fixtures.csv)"

    played = load_results(args.results, fixtures, names)
    if played and not args.fixtures:
        sys.exit("Played results need the real fixture list: pass --fixtures data/fixtures.csv")

    cfg = SimConfig(n_sims=args.sims, seed=args.seed, rating_noise=args.noise,
                    winter_noise=args.winter_noise, resample_draw=args.resample_draw)
    model = MatchModel(home_advantage=args.home_advantage, rho=args.rho, elo_k=args.elo_k)
    sim = Simulator(teams, model, fixtures, played, cfg)

    t0 = time.time()
    res = sim.run()
    elapsed = time.time() - t0

    meta = {"seed": args.seed, "fixtures_source": source, "n_played": len(played)}
    write_csv(res, args.out / "predictions.csv")
    write_markdown(res, args.out / "report.md", meta)
    write_html(res, args.out / "report.html", meta)

    data = rows(res)
    hdr = f"{'#':>2}  {'Team':<22}{'Pts':>6}" + "".join(f"{lbl:>9}" for _, lbl in COLUMNS)
    print(f"\nUEFA Champions League 2026-27 | {args.sims:,} simulations in {elapsed:.1f}s\n")
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(data, 1):
        print(f"{i:>2}  {r['team']:<22}{r['avg_points']:>6.1f}" + "".join(f"{100 * r[k]:>8.1f}%" for k, _ in COLUMNS))
    print(f"\nPredicted champion: {data[0]['team']} ({100 * data[0]['champion']:.1f}%)")
    print(f"Reports written to {args.out}/ (predictions.csv, report.md, report.html)")


if __name__ == "__main__":
    main()
