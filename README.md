# UCL 2026-27 Predictor

**Live: [ucl-2026-27-odds.vercel.app](https://ucl-2026-27-odds.vercel.app)**

A Monte Carlo model of the 2026-27 Champions League. It locks in every real result so far, then plays out the rest of the season 50,000 times: the league phase, the play-offs, the bracket, and the final in Madrid on 5 June 2027. Plain Python 3.9+, no dependencies.

## Current prediction (after matchday 4, 72 of 144 league games played)

| # | Club | Pts | Rating (pre → now) | Top 8 | Last 16 | QF | SF | Final | **Win** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **Paris Saint-Germain** | 12 | 2005 → 2047 | 97.9% | 99.6% | 82.1% | 59.1% | 38.4% | **22.5%** |
| 2 | Arsenal | 10 | 1990 → 2009 | 88.3% | 97.9% | 75.0% | 47.9% | 28.3% | **15.5%** |
| 3 | Real Madrid | 12 | 1950 → 1977 | 96.4% | 99.0% | 73.4% | 44.2% | 23.4% | **11.9%** |
| 4 | Bayern Munich | 8 | 1975 → 1989 | 73.4% | 94.5% | 67.9% | 40.1% | 22.3% | **11.7%** |
| 5 | Barcelona | 9 | 1960 → 1977 | 75.3% | 94.6% | 66.8% | 38.7% | 20.6% | **10.6%** |
| 6 | Manchester City | 9 | 1945 → 1954 | 62.8% | 90.8% | 59.5% | 31.4% | 15.4% | **7.4%** |
| 7 | Liverpool | 9 | 1935 → 1941 | 67.2% | 91.0% | 58.3% | 29.7% | 14.3% | **6.6%** |
| 8 | Inter Milan | 6 | 1895 → 1891 | 19.5% | 70.4% | 32.9% | 14.4% | 6.1% | **2.7%** |
| 9 | Atlético Madrid | 4 | 1880 → 1869 | 7.3% | 58.5% | 23.9% | 10.2% | 4.2% | **1.9%** |
| 10 | Aston Villa | 9 | 1835 → 1852 | 44.2% | 77.9% | 35.9% | 13.4% | 4.8% | **1.8%** |

PSG are favourites for a third straight title. They were at 16.6% before matchday 1 and have climbed after a perfect 12 points. The most likely final is Arsenal v PSG (7.4%). The full 36-club table is on the site and in `output/report.md`.

## Run it

```bash
python predict.py --fixtures data/fixtures.csv --results data/results.csv   # live prediction -> output/
python build_site.py                                                        # same run + matchday history -> site/data.js
python -m unittest discover -s tests                                        # tests
```

`python predict.py` with no flags ignores the real season and simulates a generated draw from scratch.

## After each matchday

1. Add the new scores to `data/results.csv` (`home,away,home_goals,away_goals`, names as in `data/teams.csv`).
2. Run `python build_site.py`.
3. Deploy: `cd site && npx vercel deploy --prod`.

## How the model works

- **Ratings.** Each club has a strength rating (`data/teams.csv`). These are my own estimates for autumn 2026, from recent European results, league form and squad quality.
- **Goals.** The rating gap plus home advantage (60 points) sets each side's expected goals: `λ = 1.40 · exp(±0.18 · d)`, where `d` is the gap in hundreds of points. Scores come from a Poisson model with the **Dixon-Coles** low-score fix (ρ = −0.12), which produces realistic numbers of 0-0 and 1-1 draws.
- **Ratings learn.** After every match, ratings move Elo-style: `Δ = K · G · (W − E)`, with K = 20 and G a goal-margin multiplier. E comes from the same goal model. The real results are replayed first, so every simulation starts from today's form, and form keeps changing inside each simulated season.
- **Uncertainty.** Each simulated season also shifts every rating by a random amount (SD 45) to stand for the things the ratings miss.
- **Format.** League-phase tie-breakers. 9th-24th play two-legged play-offs, and the bracket is fixed with the higher seed at home in the second leg. Level ties go to extra time, then near coin-flip penalties. The final is at the Metropolitano, with a small venue edge for Atlético and Real Madrid.

| Flag | Default | |
|---|---|---|
| `--sims` | 50000 | simulated seasons |
| `--elo-k` | 20 | Elo K-factor (0 = static ratings) |
| `--rho` | −0.12 | Dixon-Coles correction (0 = plain Poisson) |
| `--noise` | 45 | SD of the season-level rating shock |
| `--winter-noise` | 0 | extra shock before the knockouts |
| `--home-advantage` | 60 | in rating points |

## Layout

```
predict.py               CLI: run the model, write output/
build_site.py            run the model + matchday-by-matchday history, write site/data.js
ucl_predictor/           model.py (goals, Dixon-Coles, Elo) · simulate.py (season) · draw.py · report.py
data/                    teams.csv · fixtures.csv (real draw, matchday order) · results.csv
site/                    the website: static HTML/CSS/JS, no build step
tests/                   draw rules, stage totals, fixed results, sampler accuracy, Elo updates
```

## Notes

- Fixtures and results come from the [2026-27 league phase page on Wikipedia](https://en.wikipedia.org/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase), checked against [UEFA](https://www.uefa.com/uefachampionsleague/news/02a8-2174c9e9019d-f909a77bd77a-1000--2026-27-champions-league-all-the-league-phase-fixtures-a/).
- The ratings are subjective, and the model has not yet been backtested on past seasons. The in-season Elo updates and the season-level shock overlap a little, so the odds are probably slightly too spread out.
- The site uses club colors for identification only, with no crests or trademarks.
- These are probabilities, not betting advice.
