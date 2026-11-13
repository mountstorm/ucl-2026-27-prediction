"""Team data and the match model (Elo-style ratings -> Poisson goals)."""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Team:
    name: str
    country: str
    pot: int
    rating: float


def load_teams(path: str | Path) -> list[Team]:
    teams = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            teams.append(
                Team(
                    name=row["team"].strip(),
                    country=row["country"].strip(),
                    pot=int(row["pot"]),
                    rating=float(row["rating"]),
                )
            )
    if len(teams) != 36:
        raise ValueError(f"Expected 36 teams, found {len(teams)} in {path}")
    for pot in (1, 2, 3, 4):
        n = sum(1 for t in teams if t.pot == pot)
        if n != 9:
            raise ValueError(f"Pot {pot} must contain 9 teams, found {n}")
    return teams


class MatchModel:
    """Expected goals from a rating gap, then Dixon-Coles adjusted Poisson scores.

    With d = (R_home + home_adv - R_away) / 100:
        lambda_home = base_goals * exp( beta * d)
        lambda_away = base_goals * exp(-beta * d)

    Independent Poisson draws too few 0-0 and 1-1 games. The Dixon-Coles
    factor tau (rho < 0) moves probability from 1-0 and 0-1 onto those draws:
        tau(0,0) = 1 - lh*la*rho    tau(0,1) = 1 + lh*rho
        tau(1,0) = 1 + la*rho       tau(1,1) = 1 - rho
    The adjusted probabilities still sum to 1, and scores are sampled exactly
    by rejection.

    After each match the ratings can be updated Elo-style (see elo_delta).
    The expected score comes from this same goal model, so the update is
    consistent with how matches are actually simulated.
    """

    def __init__(
        self,
        base_goals: float = 1.40,
        beta: float = 0.18,
        home_advantage: float = 60.0,
        extra_time_factor: float = 1.0 / 3.0,
        penalty_skill: float = 0.0004,
        rho: float = -0.12,
        elo_k: float = 20.0,
    ):
        self.base_goals = base_goals
        self.beta = beta
        self.home_advantage = home_advantage
        self.extra_time_factor = extra_time_factor
        # A 100-point edge adds 0.04 to the shootout win chance: almost a coin flip.
        self.penalty_skill = penalty_skill
        self.rho = rho
        self.elo_k = elo_k
        self._es_table = self._build_expected_score_table()

    def expected_goals(self, r_home: float, r_away: float, home_adv: float | None = None):
        ha = self.home_advantage if home_adv is None else home_adv
        d = (r_home + ha - r_away) / 100.0
        return self.base_goals * math.exp(self.beta * d), self.base_goals * math.exp(-self.beta * d)

    def _tau(self, x: int, y: int, lh: float, la: float) -> float:
        rho = self.rho
        if x == 0 and y == 0:
            return max(0.0, 1.0 - lh * la * rho)
        if x == 0 and y == 1:
            return max(0.0, 1.0 + lh * rho)
        if x == 1 and y == 0:
            return max(0.0, 1.0 + la * rho)
        if x == 1 and y == 1:
            return max(0.0, 1.0 - rho)
        return 1.0

    def play(self, rng: random.Random, r_home: float, r_away: float, home_adv: float | None = None):
        lh, la = self.expected_goals(r_home, r_away, home_adv)
        if self.rho == 0.0:
            return poisson(rng, lh), poisson(rng, la)
        rho = self.rho
        t_max = max(1.0, 1.0 - lh * la * rho, 1.0 + lh * rho, 1.0 + la * rho, 1.0 - rho)
        # Rejection sampling: propose from independent Poisson, accept with
        # probability tau / t_max. Accepted scores follow the Dixon-Coles pmf.
        while True:
            x, y = poisson(rng, lh), poisson(rng, la)
            if rng.random() * t_max < self._tau(x, y, lh, la):
                return x, y

    def extra_time(self, rng: random.Random, r_home: float, r_away: float, home_adv: float | None = None):
        lh, la = self.expected_goals(r_home, r_away, home_adv)
        f = self.extra_time_factor
        return poisson(rng, lh * f), poisson(rng, la * f)

    def penalties(self, rng: random.Random, r_a: float, r_b: float) -> bool:
        """Return True if team A wins the shootout."""
        p_a = 0.5 + self.penalty_skill * (r_a - r_b)
        return rng.random() < min(0.6, max(0.4, p_a))

    # ------------------------------------------------------------ Elo update
    def score_probs(self, r_home: float, r_away: float, home_adv: float | None = None, max_goals: int = 15):
        """(P home win, P draw, P away win) under the Dixon-Coles model."""
        lh, la = self.expected_goals(r_home, r_away, home_adv)
        ph = [math.exp(-lh) * lh ** k / math.factorial(k) for k in range(max_goals + 1)]
        pa = [math.exp(-la) * la ** k / math.factorial(k) for k in range(max_goals + 1)]
        w = d = l = 0.0
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                p = ph[x] * pa[y] * self._tau(x, y, lh, la)
                if x > y:
                    w += p
                elif x == y:
                    d += p
                else:
                    l += p
        return w, d, l

    _ES_RANGE = 1000  # table covers effective gaps of -1000..+1000 rating points

    def _build_expected_score_table(self):
        table = []
        for gap in range(-self._ES_RANGE, self._ES_RANGE + 1):
            w, d, _ = self.score_probs(gap, 0.0, home_adv=0.0)
            table.append(w + 0.5 * d)
        return table

    def expected_score(self, r_home: float, r_away: float, home_adv: float | None = None) -> float:
        """Home side's expected points share (win = 1, draw = 0.5)."""
        ha = self.home_advantage if home_adv is None else home_adv
        gap = int(round(r_home + ha - r_away))
        gap = max(-self._ES_RANGE, min(self._ES_RANGE, gap))
        return self._es_table[gap + self._ES_RANGE]

    def elo_delta(self, hg: int, ag: int, r_home: float, r_away: float, home_adv: float | None = None) -> float:
        """Rating points the home side gains (the away side loses the same).

        delta = K * G * (W - E), with the World Football Elo margin multiplier
        G = 1 (margin 0-1), 1.5 (margin 2), (11 + margin) / 8 (margin 3+).
        """
        if self.elo_k == 0.0:
            return 0.0
        w = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        margin = abs(hg - ag)
        g = 1.0 if margin <= 1 else (1.5 if margin == 2 else (11 + margin) / 8)
        return self.elo_k * g * (w - self.expected_score(r_home, r_away, home_adv))


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth's Poisson sampler; fast enough for the small means used here."""
    limit = math.exp(-lam)
    k = 0
    p = rng.random()
    while p > limit:
        k += 1
        p *= rng.random()
    return k
