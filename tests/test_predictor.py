import random
import unittest
from pathlib import Path

from ucl_predictor.draw import generate_draw, validate_draw
from ucl_predictor.model import MatchModel, load_teams
from ucl_predictor.simulate import SimConfig, Simulator

ROOT = Path(__file__).resolve().parents[1]
TEAMS = load_teams(ROOT / "data" / "teams.csv")


class DrawTests(unittest.TestCase):
    def test_many_draws_are_valid(self):
        for seed in range(25):
            validate_draw(TEAMS, generate_draw(TEAMS, random.Random(seed)))  # raises if invalid


class SimulationTests(unittest.TestCase):
    def _run(self, played=None, n=400):
        fixtures = generate_draw(TEAMS, random.Random(1))
        sim = Simulator(TEAMS, MatchModel(), fixtures, played, SimConfig(n_sims=n, seed=3))
        return sim.run(), fixtures

    def test_stage_counts_add_up(self):
        res, _ = self._run()
        n = res.n_sims
        expected = {"top8": 8, "top24": 24, "r16": 16, "qf": 8, "sf": 4, "final": 2, "champion": 1}
        for stage, k in expected.items():
            total = sum(res.stage_counts[t.name][stage] for t in TEAMS)
            self.assertEqual(total, k * n, stage)

    def test_played_results_are_respected(self):
        _, fixtures = self._run(n=1)
        # Give the weakest team (Sabah) wins in all of its games.
        played = {}
        for h, a in fixtures:
            if h == "Sabah":
                played[(h, a)] = (5, 0)
            elif a == "Sabah":
                played[(h, a)] = (0, 5)
        res, _ = self._run(played=played, n=200)
        self.assertEqual(res.points_sum["Sabah"] / res.n_sims, 24)
        self.assertEqual(res.prob("Sabah", "top8"), 1.0)


class MatchModelTests(unittest.TestCase):
    def test_dixon_coles_sampler_matches_exact_probabilities(self):
        m, rng = MatchModel(rho=-0.12), random.Random(7)
        w, d, _ = m.score_probs(1850, 1800)
        n = 60000
        draws = sum(1 for _ in range(n) if (lambda s: s[0] == s[1])(m.play(rng, 1850, 1800)))
        self.assertAlmostEqual(draws / n, d, delta=0.01)

    def test_dixon_coles_raises_draw_rate(self):
        _, d_dc, _ = MatchModel(rho=-0.12).score_probs(1800, 1800)
        _, d_ip, _ = MatchModel(rho=0.0).score_probs(1800, 1800)
        self.assertGreater(d_dc, d_ip)

    def test_elo_update_direction_and_margin(self):
        m = MatchModel()
        self.assertLess(m.elo_delta(0, 3, 2000, 1550), 0)              # favourite loses at home -> drops
        self.assertGreater(m.elo_delta(1, 0, 1550, 2000), 0)           # underdog wins -> rises
        self.assertGreater(m.elo_delta(9, 1, 1700, 1700), m.elo_delta(1, 0, 1700, 1700))  # bigger margin, bigger move
        self.assertEqual(MatchModel(elo_k=0).elo_delta(5, 0, 1700, 1700), 0.0)

    def test_real_results_move_starting_ratings(self):
        fixtures = generate_draw(TEAMS, random.Random(1))
        h, a = next(f for f in fixtures if f[0] == "Sabah")
        sim = Simulator(TEAMS, MatchModel(), fixtures, {(h, a): (4, 0)}, SimConfig(n_sims=1))
        before = {t.name: t.rating for t in TEAMS}
        self.assertGreater(sim.start_ratings["Sabah"], before["Sabah"])
        self.assertLess(sim.start_ratings[a], before[a])
        self.assertAlmostEqual(sum(sim.start_ratings.values()), sum(before.values()))


if __name__ == "__main__":
    unittest.main()
