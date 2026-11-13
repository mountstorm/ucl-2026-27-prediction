"""Monte Carlo simulation of the 2026-27 Champions League.

Format (unchanged since 2024-25):
  * League phase: 36 teams, 8 games each, one table.
  * 1st-8th go straight to the round of 16. 9th-24th play a two-legged
    knockout play-off. 25th-36th are eliminated.
  * Play-offs: 9/10 v 23/24, 11/12 v 21/22, 13/14 v 19/20, 15/16 v 17/18.
  * Round of 16: 1/2 v winners of 15/16-17/18, 3/4 v 13/14-19/20,
    5/6 v 11/12-21/22, 7/8 v 9/10-23/24. The fixed bracket runs to the final.
  * Every knockout tie is two legs, with the higher-ranked team at home in
    the second leg. The final is one match in Madrid (Metropolitano,
    5 June 2027).
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field

from .draw import Fixture, generate_draw
from .model import MatchModel, Team

STAGES = ["top8", "top24", "r16", "qf", "sf", "final", "champion"]

# Teams that get part of the home advantage in the final (Madrid 2027 is at
# the Metropolitano, Atletico's ground). The value is a share of home_advantage.
FINAL_VENUE_BOOST = {"Atletico Madrid": 0.5, "Real Madrid": 0.15}


@dataclass
class SimConfig:
    n_sims: int = 50000
    seed: int = 2027
    rating_noise: float = 45.0      # sd of the per-season rating shock (model uncertainty)
    winter_noise: float = 0.0       # sd of an extra shock before the knockouts (January window, injuries)
    resample_draw: bool = False     # new random draw each sim (when real fixtures are unknown)


@dataclass
class Results:
    teams: list[Team]
    n_sims: int
    stage_counts: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    points_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    position_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    position_hist: dict[str, list[int]] = field(default_factory=dict)
    finals: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    start_ratings: dict[str, float] = field(default_factory=dict)   # input ratings after real results

    def prob(self, team: str, stage: str) -> float:
        return self.stage_counts[team][stage] / self.n_sims


class Simulator:
    def __init__(
        self,
        teams: list[Team],
        model: MatchModel,
        fixtures: list[Fixture] | None,
        played: dict[Fixture, tuple[int, int]] | None,
        config: SimConfig,
    ):
        self.teams = teams
        self.by_name = {t.name: t for t in teams}
        self.model = model
        self.config = config
        self.rng = random.Random(config.seed)
        self.played = played or {}
        if fixtures is None:
            fixtures = generate_draw(teams, self.rng)
        self.fixtures = fixtures
        self.start_ratings = self._learn_from_played()

    def _learn_from_played(self) -> dict[str, float]:
        """Elo-update the input ratings with the real results, in fixture order.

        Fixtures are listed by matchday, so this replays the season as it
        happened. These updated ratings are each simulation's starting point.
        """
        ratings = {t.name: t.rating for t in self.teams}
        for h, a in self.fixtures:
            res = self.played.get((h, a))
            if res is not None:
                self._update(ratings, h, a, *res)
        return ratings

    def _update(self, ratings, home: str, away: str, hg: int, ag: int, home_adv=None) -> None:
        delta = self.model.elo_delta(hg, ag, ratings[home], ratings[away], home_adv)
        ratings[home] += delta
        ratings[away] -= delta

    # ---------------------------------------------------------------- league
    def _league(self, ratings: dict[str, float], fixtures: list[Fixture]):
        pts = defaultdict(int)
        gf = defaultdict(int)
        ga = defaultdict(int)
        wins = defaultdict(int)
        away_gf = defaultdict(int)
        rng, model = self.rng, self.model
        for h, a in fixtures:
            res = self.played.get((h, a))
            if res is None:
                hg, ag = model.play(rng, ratings[h], ratings[a])
                self._update(ratings, h, a, hg, ag)
            else:
                hg, ag = res
            gf[h] += hg; ga[h] += ag
            gf[a] += ag; ga[a] += hg
            away_gf[a] += ag
            if hg > ag:
                pts[h] += 3; wins[h] += 1
            elif hg < ag:
                pts[a] += 3; wins[a] += 1
            else:
                pts[h] += 1; pts[a] += 1
        # UEFA tie-breakers (simplified): points, goal difference, goals
        # scored, away goals, wins, then a random draw of lots.
        names = [t.name for t in self.teams]
        lots = {n: rng.random() for n in names}
        names.sort(
            key=lambda n: (pts[n], gf[n] - ga[n], gf[n], away_gf[n], wins[n], lots[n]),
            reverse=True,
        )
        return names, pts

    # -------------------------------------------------------------- knockout
    def _two_legs(self, ratings, seeded: str, other: str) -> str:
        """Seeded team hosts the second leg. Returns the winner."""
        m, rng = self.model, self.rng
        rs, ro = ratings[seeded], ratings[other]
        g1o, g1s = m.play(rng, ro, rs)      # leg 1 at `other`
        self._update(ratings, other, seeded, g1o, g1s)
        rs, ro = ratings[seeded], ratings[other]
        g2s, g2o = m.play(rng, rs, ro)      # leg 2 at `seeded`
        self._update(ratings, seeded, other, g2s, g2o)
        rs, ro = ratings[seeded], ratings[other]
        agg_s, agg_o = g1s + g2s, g1o + g2o
        if agg_s == agg_o:
            es, eo = m.extra_time(rng, rs, ro)
            agg_s += es; agg_o += eo
            if agg_s == agg_o:
                return seeded if m.penalties(rng, rs, ro) else other
        return seeded if agg_s > agg_o else other

    def _final(self, ratings, a: str, b: str) -> str:
        m, rng = self.model, self.rng
        ha = m.home_advantage * (FINAL_VENUE_BOOST.get(a, 0.0) - FINAL_VENUE_BOOST.get(b, 0.0))
        ga_, gb = m.play(rng, ratings[a], ratings[b], home_adv=ha)
        if ga_ == gb:
            ea, eb = m.extra_time(rng, ratings[a], ratings[b], home_adv=ha)
            ga_ += ea; gb += eb
            if ga_ == gb:
                return a if m.penalties(rng, ratings[a], ratings[b]) else b
        return a if ga_ > gb else b

    def _knockouts(self, ratings, table: list[str]):
        rng = self.rng
        pos = {name: i + 1 for i, name in enumerate(table)}   # 1-based rank
        rank = lambda r: table[r - 1]                          # noqa: E731

        def split(pair):
            p = list(pair)
            rng.shuffle(p)
            return p

        # Knockout play-off round: seeded pair (9,10) is drawn against (23,24), etc.
        po_pairs = [((9, 10), (23, 24)), ((11, 12), (21, 22)), ((13, 14), (19, 20)), ((15, 16), (17, 18))]
        po_winner = {}  # keyed by seeded rank of the tie
        for seeded_pair, unseeded_pair in po_pairs:
            s, u = split(seeded_pair), split(unseeded_pair)
            for sr, ur in zip(s, u):
                po_winner[sr] = self._two_legs(ratings, rank(sr), rank(ur))

        # Round of 16: each top-8 pair meets the winners from one play-off band.
        r16_link = {(1, 2): (15, 16), (3, 4): (13, 14), (5, 6): (11, 12), (7, 8): (9, 10)}
        halves = {}
        for top_pair, po_seeds in r16_link.items():
            t, p = split(top_pair), split(po_seeds)
            for half, (tr, pr) in enumerate(zip(t, p)):
                halves.setdefault(half, []).append((rank(tr), po_winner[pr]))
        # Fixed bracket: within each half, tie 1/2 meets tie 7/8 and 3/4 meets 5/6 in the QF.
        bracket = []
        for half in (0, 1):
            ties = halves[half]           # order: (1/2), (3/4), (5/6), (7/8)
            bracket += [ties[0], ties[3], ties[1], ties[2]]

        def seeded_order(a, b):
            return (a, b) if pos[a] < pos[b] else (b, a)

        r16 = [self._two_legs(ratings, *seeded_order(a, b)) for a, b in bracket]
        qf = [self._two_legs(ratings, *seeded_order(r16[i], r16[i + 1])) for i in range(0, 8, 2)]
        sf = [self._two_legs(ratings, *seeded_order(qf[i], qf[i + 1])) for i in range(0, 4, 2)]
        finalists = (sf[0], sf[1])
        champion = self._final(ratings, *finalists)
        participants = [team for tie in bracket for team in tie]
        return participants, r16, qf, sf, finalists, champion

    # ------------------------------------------------------------------- run
    def run(self) -> Results:
        cfg, rng = self.config, self.rng
        res = Results(teams=self.teams, n_sims=cfg.n_sims, start_ratings=dict(self.start_ratings))
        res.position_hist = {t.name: [0] * 36 for t in self.teams}
        for _ in range(cfg.n_sims):
            # Ratings change as the simulated season goes on (Elo update after each match).
            ratings = {n: r + rng.gauss(0.0, cfg.rating_noise) for n, r in self.start_ratings.items()}
            fixtures = generate_draw(self.teams, rng) if cfg.resample_draw else self.fixtures
            table, pts = self._league(ratings, fixtures)
            for i, name in enumerate(table):
                res.points_sum[name] += pts[name]
                res.position_sum[name] += i + 1
                res.position_hist[name][i] += 1
                if i < 8:
                    res.stage_counts[name]["top8"] += 1
                if i < 24:
                    res.stage_counts[name]["top24"] += 1
            if cfg.winter_noise:
                for n in ratings:
                    ratings[n] += rng.gauss(0.0, cfg.winter_noise)
            last16, r16, qf, sf, finalists, champ = self._knockouts(ratings, table)
            for name in last16:
                res.stage_counts[name]["r16"] += 1
            for name in r16:
                res.stage_counts[name]["qf"] += 1
            for name in qf:
                res.stage_counts[name]["sf"] += 1
            for name in sf:
                res.stage_counts[name]["final"] += 1
            res.stage_counts[champ]["champion"] += 1
            res.finals[tuple(sorted(finalists))] += 1
        return res
