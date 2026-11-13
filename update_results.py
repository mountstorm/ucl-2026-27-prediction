#!/usr/bin/env python3
"""Pull finished league-phase results from ESPN into data/results.csv.

Source: ESPN's public scoreboard feed (one request per month of the league
phase) plus its standings feed, which is used as a cross-check.

    python update_results.py            # fetch, check, rewrite data/results.csv if anything changed
    python update_results.py --dry-run  # show what would change

Every result must match a game in data/fixtures.csv, and the table built from
the results must agree with ESPN's own standings. If either check fails,
nothing is written.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import unicodedata
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "https://site.api.espn.com/apis"
SCOREBOARD = BASE + "/site/v2/sports/soccer/uefa.champions/scoreboard?dates={month}&limit=200"
STANDINGS = BASE + "/v2/sports/soccer/uefa.champions/standings"
LEAGUE_PHASE_MONTHS = ["202609", "202610", "202611", "202612", "202701"]

# ESPN display name -> name in data/teams.csv (only where they differ).
ALIASES = {
    "Feyenoord Rotterdam": "Feyenoord",
    "Internazionale": "Inter Milan",
    "LASK Linz": "LASK",
    "AS Roma": "Roma",
    "FC Porto": "Porto",
    "Viking FK": "Viking",
    "Sabah FK": "Sabah",
    "Atlético Madrid": "Atletico Madrid",
    "Bodø/Glimt": "Bodo/Glimt",
    "FK Bodø/Glimt": "Bodo/Glimt",
    "Fenerbahçe": "Fenerbahce",
    "Bayern München": "Bayern Munich",
    "PSV": "PSV Eindhoven",
    "Sporting": "Sporting CP",
    "Stuttgart": "VfB Stuttgart",
    "Slovan Bratislava": "Slovan Bratislava",
    "SK Slavia Prague": "Slavia Prague",
    "Shakhtar": "Shakhtar Donetsk",
    "Brugge": "Club Brugge",
    "Leipzig": "RB Leipzig",
    "Real Betis Balompié": "Real Betis",
    "AEK": "AEK Athens",
}


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower().strip()


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "ucl-predictor/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


class Names:
    def __init__(self, teams: list[str]):
        self.exact = {fold(t): t for t in teams}
        self.alias = {fold(k): v for k, v in ALIASES.items()}

    def __call__(self, espn_name: str) -> str | None:
        f = fold(espn_name)
        return self.exact.get(f) or self.alias.get(f)


def fetch_results(fixtures: set, names: Names, today: date):
    played, unknown, stray = {}, set(), []
    for month in LEAGUE_PHASE_MONTHS:
        if month > today.strftime("%Y%m"):
            break
        for ev in get_json(SCOREBOARD.format(month=month)).get("events", []):
            comp = ev["competitions"][0]
            status = comp["status"]["type"]
            if not status.get("completed") or status.get("state") != "post":
                continue
            side = {c["homeAway"]: c for c in comp["competitors"]}
            h, a = names(side["home"]["team"]["displayName"]), names(side["away"]["team"]["displayName"])
            if h is None:
                unknown.add(side["home"]["team"]["displayName"])
            if a is None:
                unknown.add(side["away"]["team"]["displayName"])
            if h is None or a is None:
                continue
            if (h, a) not in fixtures:
                stray.append(f"{h} v {a} ({ev['date'][:10]})")
                continue
            played[(h, a)] = (int(side["home"]["score"]), int(side["away"]["score"]))
    return played, sorted(unknown), stray


def table(played):
    t = {}
    for (h, a), (hg, ag) in played.items():
        for n in (h, a):
            t.setdefault(n, {"p": 0, "pts": 0, "gf": 0, "ga": 0})
        t[h]["p"] += 1; t[a]["p"] += 1
        t[h]["gf"] += hg; t[h]["ga"] += ag; t[a]["gf"] += ag; t[a]["ga"] += hg
        t[h]["pts"] += 3 if hg > ag else (1 if hg == ag else 0)
        t[a]["pts"] += 3 if ag > hg else (1 if hg == ag else 0)
    return t


def check_standings(played, names: Names):
    """Compare our table with ESPN's standings. Returns a list of mismatches."""
    data = get_json(STANDINGS)
    entries = data["children"][0]["standings"]["entries"]
    ours = table(played)
    problems = []
    for e in entries:
        n = names(e["team"]["displayName"])
        if n is None:
            problems.append(f"standings: unknown team {e['team']['displayName']}")
            continue
        st = {s["name"]: s.get("value") for s in e["stats"]}
        theirs = {"p": int(st["gamesPlayed"]), "pts": int(st["points"]), "gf": int(st["pointsFor"]), "ga": int(st["pointsAgainst"])}
        mine = ours.get(n, {"p": 0, "pts": 0, "gf": 0, "ga": 0})
        if theirs != mine:
            problems.append(f"{n}: ESPN table {theirs} vs results {mine}")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(ROOT / "data" / "teams.csv", newline="", encoding="utf-8") as fh:
        teams = [r["team"].strip() for r in csv.DictReader(fh)]
    with open(ROOT / "data" / "fixtures.csv", newline="", encoding="utf-8") as fh:
        order = [(r["home"].strip(), r["away"].strip()) for r in csv.DictReader(fh)]
    names = Names(teams)

    played, unknown, stray = fetch_results(set(order), names, datetime.now(timezone.utc).date())
    if unknown:
        sys.exit("Unknown ESPN team names (add them to ALIASES): " + ", ".join(unknown))
    if stray:
        sys.exit("Finished games that are not in data/fixtures.csv: " + "; ".join(stray))
    problems = check_standings(played, names)
    if problems:
        sys.exit("Results disagree with ESPN's standings, nothing written:\n  " + "\n  ".join(problems))

    path = ROOT / "data" / "results.csv"
    old = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as fh:
            old = {(r["home"], r["away"]): (int(r["home_goals"]), int(r["away_goals"])) for r in csv.DictReader(fh) if r.get("home")}
    added = [f for f in order if f in played and f not in old]
    changed = [f for f in order if f in played and f in old and played[f] != old[f]]
    missing = [f for f in old if f not in played]

    for h, a in added:
        print(f"  new      {h} {played[(h, a)][0]}-{played[(h, a)][1]} {a}")
    for h, a in changed:
        print(f"  changed  {h} v {a}: {old[(h, a)]} -> {played[(h, a)]}")
    for h, a in missing:
        print(f"  WARNING  {h} v {a} is in results.csv but not in ESPN's feed (kept)")
        played[(h, a)] = old[(h, a)]
    dirty = bool(added or changed)
    print(f"{len(played)} results from ESPN, standings cross-check passed. "
          + ("Updated." if dirty and not args.dry_run else "No changes." if not dirty else "Dry run, not written."))

    meta_path = ROOT / "data" / "source.json"
    if (dirty or not meta_path.exists()) and not args.dry_run:
        meta = {"source": "ESPN", "url": "https://www.espn.com/soccer/standings/_/league/uefa.champions",
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "results": len(played)}
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    if dirty and not args.dry_run:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["home", "away", "home_goals", "away_goals"])
            for f in order:
                if f in played:
                    w.writerow([f[0], f[1], *played[f]])

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"changed={'true' if dirty and not args.dry_run else 'false'}\n")


if __name__ == "__main__":
    main()
