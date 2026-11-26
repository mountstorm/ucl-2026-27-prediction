# UCL 2026-27 Predictor

**Live: [ucl-2026-27-odds.vercel.app](https://ucl-2026-27-odds.vercel.app)**

A Monte Carlo model of the 2026-27 Champions League. It locks in every real result so far, then plays out the rest of the season 50,000 times: the league phase, the play-offs, the bracket, and the final in Madrid on 5 June 2027. Plain Python 3.9+, no dependencies.

<!-- prediction:start -->
## Current prediction (after matchday 5, 90 of 144 league games played)

| # | Club | Pts | Rating (pre → now) | Top 8 | Last 16 | QF | SF | Final | **Win** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **Paris Saint-Germain** | 13 | 2005 → 2040 | 96.4% | 99.4% | 80.3% | 56.6% | 36.3% | **21.5%** |
| 2 | Arsenal | 11 | 1990 → 2004 | 81.6% | 96.5% | 71.8% | 44.5% | 25.9% | **14.2%** |
| 3 | Real Madrid | 15 | 1950 → 1985 | 99.7% | 99.9% | 74.4% | 46.4% | 25.4% | **13.1%** |
| 4 | Barcelona | 12 | 1960 → 1982 | 85.1% | 96.7% | 69.7% | 41.7% | 22.8% | **11.8%** |
| 5 | Bayern Munich | 8 | 1975 → 1974 | 42.2% | 87.0% | 56.2% | 31.3% | 17.2% | **8.8%** |
| 6 | Liverpool | 12 | 1935 → 1954 | 89.5% | 97.2% | 66.6% | 36.5% | 18.2% | **8.6%** |
| 7 | Manchester City | 10 | 1945 → 1949 | 51.3% | 87.7% | 54.0% | 28.3% | 14.4% | **7.1%** |
| 8 | Inter Milan | 9 | 1895 → 1901 | 33.1% | 78.0% | 39.7% | 18.0% | 7.8% | **3.3%** |
| 9 | Atlético Madrid | 7 | 1880 → 1875 | 11.5% | 61.8% | 26.7% | 11.6% | 4.8% | **2.2%** |
| 10 | Como | 12 | 1805 → 1849 | 51.1% | 80.0% | 37.2% | 13.7% | 4.8% | **1.8%** |

Favourite: **Paris Saint-Germain** (21.5%, 16.6% before matchday 1). Most likely final: Paris Saint-Germain v Real Madrid (6.8%). Results from ESPN, fetched 2026-11-26T04:13Z.
<!-- prediction:end -->

## Run it

```bash
python update_results.py                                                    # pull finished games from ESPN -> data/results.csv
python predict.py --fixtures data/fixtures.csv --results data/results.csv   # live prediction -> output/
python build_site.py                                                        # same run + matchday history -> site/data.js and the table above
python -m unittest discover -s tests                                        # tests
```

`python predict.py` with no flags ignores the real season and simulates a generated draw from scratch.

## Live results

Results come from ESPN's public scoreboard feed. `update_results.py` keeps only finished games and matches each one to the real draw in `data/fixtures.csv`. It then checks the table it builds against ESPN's own standings and writes nothing if they disagree.

A GitHub Action (`.github/workflows/update.yml`) does this automatically, about 30 minutes after the last kickoff on match nights and every morning as a catch-up. When there are new results it reruns the model, rebuilds the site and this README table, runs the tests, and commits. Vercel redeploys on every push. You can also start it by hand from the Actions tab.

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
update_results.py        fetch finished results from ESPN, cross-checked with ESPN standings
predict.py               CLI: run the model, write output/
build_site.py            run the model + matchday-by-matchday history, write site/data.js
ucl_predictor/           model.py (goals, Dixon-Coles, Elo) · simulate.py (season) · draw.py · report.py
data/                    teams.csv · fixtures.csv (real draw, matchday order) · results.csv · source.json
site/                    the website: static HTML/CSS/JS, no build step
tests/                   draw rules, stage totals, fixed results, sampler accuracy, Elo updates
```

## Notes

- Results: [ESPN](https://www.espn.com/soccer/standings/_/league/uefa.champions). The fixture list comes from the [2026-27 league phase page on Wikipedia](https://en.wikipedia.org/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase), checked against [UEFA](https://www.uefa.com/uefachampionsleague/news/02a8-2174c9e9019d-f909a77bd77a-1000--2026-27-champions-league-all-the-league-phase-fixtures-a/).
- The ratings are subjective, and the model has not yet been backtested on past seasons. The in-season Elo updates and the season-level shock overlap a little, so the odds are probably slightly too spread out.
- The site uses club colors for identification only, with no crests or trademarks.
- These are probabilities, not betting advice.
