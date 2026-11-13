"""League-phase draw generator that follows UEFA's main constraints.

* Each team plays 8 opponents: 2 from each pot, one at home and one away.
* No team plays a club from its own country.
* No team plays more than 2 clubs from any one other country.

UEFA's software also balances kickoff dates and TV slots. Those rules do not
change who plays whom, so they are left out here.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path

from .model import Team

Fixture = tuple[str, str]  # (home, away)


class _State:
    def __init__(self, teams: list[Team]):
        self.by_name = {t.name: t for t in teams}
        self.country_count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.opponents: dict[str, set[str]] = defaultdict(set)

    def can_pair(self, a: Team, b: Team) -> bool:
        if a.name == b.name or a.country == b.country:
            return False
        if b.name in self.opponents[a.name]:
            return False
        if self.country_count[a.name][b.country] >= 2:
            return False
        if self.country_count[b.name][a.country] >= 2:
            return False
        return True

    def add(self, a: Team, b: Team, sign: int = 1) -> None:
        self.country_count[a.name][b.country] += sign
        self.country_count[b.name][a.country] += sign
        if sign > 0:
            self.opponents[a.name].add(b.name)
            self.opponents[b.name].add(a.name)
        else:
            self.opponents[a.name].discard(b.name)
            self.opponents[b.name].discard(a.name)


class _Budget(Exception):
    pass


def _matching(left, right, state, rng, budget, extra_ok=None):
    """Random backtracking search for a bijection left[i] -> right[j]."""
    n = len(left)
    used = [False] * n
    out: list[int] = [-1] * n
    steps = [0]

    def rec(i: int) -> bool:
        if i == n:
            return True
        steps[0] += 1
        if steps[0] > budget:
            raise _Budget
        a = left[i]
        order = list(range(n))
        rng.shuffle(order)
        for j in order:
            if used[j]:
                continue
            b = right[j]
            if not state.can_pair(a, b):
                continue
            if extra_ok is not None and not extra_ok(i, j, out):
                continue
            used[j] = True
            out[i] = j
            state.add(a, b, +1)
            if rec(i + 1):
                return True
            state.add(a, b, -1)
            used[j] = False
            out[i] = -1
        return False

    try:
        ok = rec(0)
    except _Budget:
        # Undo whatever is still applied.
        for i, j in enumerate(out):
            if j >= 0:
                state.add(left[i], right[j], -1)
        return None
    return out if ok else None


def _undo(state, pairs):
    for a, b in pairs:
        state.add(a, b, -1)


def _draw_cross_pot(pa, pb, state, rng, tries=40, budget=4000):
    """Each team in pa hosts one team from pb and visits another."""
    for _ in range(tries):
        first = _matching(pa, pb, state, rng, budget)          # pa home
        if first is None:
            continue
        second = _matching(pb, pa, state, rng, budget)         # pb home
        if second is None:
            _undo(state, [(pa[i], pb[j]) for i, j in enumerate(first)])
            continue
        fx = [(pa[i].name, pb[j].name) for i, j in enumerate(first)]
        fx += [(pb[i].name, pa[j].name) for i, j in enumerate(second)]
        return fx
    return None


def _draw_same_pot(pot, state, rng, tries=40, budget=4000):
    """A derangement sigma with no 2-cycles: team i hosts sigma(i), visits sigma^-1(i)."""

    def no_two_cycle(i, j, out):
        return out[j] != i

    for _ in range(tries):
        sigma = _matching(pot, pot, state, rng, budget, extra_ok=no_two_cycle)
        if sigma is None:
            continue
        return [(pot[i].name, pot[j].name) for i, j in enumerate(sigma)]
    return None


def generate_draw(teams: list[Team], rng: random.Random, max_restarts: int = 500) -> list[Fixture]:
    pots = {p: [t for t in teams if t.pot == p] for p in (1, 2, 3, 4)}
    pairs = [(i, j) for i in (1, 2, 3, 4) for j in (1, 2, 3, 4) if i <= j]
    for _ in range(max_restarts):
        state = _State(teams)
        fixtures: list[Fixture] = []
        order = pairs[:]
        rng.shuffle(order)
        ok = True
        for i, j in order:
            fx = _draw_same_pot(pots[i], state, rng) if i == j else _draw_cross_pot(pots[i], pots[j], state, rng)
            if fx is None:
                ok = False
                break
            fixtures.extend(fx)
        if ok:
            validate_draw(teams, fixtures)
            return fixtures
    raise RuntimeError("Could not generate a valid league-phase draw")


def validate_draw(teams: list[Team], fixtures: list[Fixture]) -> None:
    by_name = {t.name: t for t in teams}
    if len(fixtures) != 144:
        raise ValueError(f"Expected 144 fixtures, got {len(fixtures)}")
    home = defaultdict(int)
    away = defaultdict(int)
    vs_pot = defaultdict(lambda: defaultdict(int))
    vs_country = defaultdict(lambda: defaultdict(int))
    seen = set()
    for h, a in fixtures:
        if h not in by_name or a not in by_name:
            raise ValueError(f"Unknown team in fixture {h} v {a}")
        key = frozenset((h, a))
        if key in seen:
            raise ValueError(f"{h} and {a} meet twice")
        seen.add(key)
        th, ta = by_name[h], by_name[a]
        if th.country == ta.country:
            raise ValueError(f"Same-country fixture {h} v {a}")
        home[h] += 1
        away[a] += 1
        vs_pot[h][ta.pot] += 1
        vs_pot[a][th.pot] += 1
        vs_country[h][ta.country] += 1
        vs_country[a][th.country] += 1
    for t in teams:
        if home[t.name] != 4 or away[t.name] != 4:
            raise ValueError(f"{t.name} must have 4 home and 4 away games")
        for p in (1, 2, 3, 4):
            if vs_pot[t.name][p] != 2:
                raise ValueError(f"{t.name} must face 2 teams from pot {p}")
        for c, n in vs_country[t.name].items():
            if n > 2:
                raise ValueError(f"{t.name} faces {n} teams from {c}")


def load_fixtures(path: str | Path) -> list[Fixture]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [(r["home"].strip(), r["away"].strip()) for r in csv.DictReader(fh)]


def save_fixtures(path: str | Path, fixtures: list[Fixture]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["home", "away"])
        w.writerows(fixtures)
