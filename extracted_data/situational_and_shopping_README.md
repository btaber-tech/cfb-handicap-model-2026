# Situational Bias + Line Shopping Tests (2022-2025 CFBD data)

Follow-up to `backtest_README.md`, digging into what an actual ATS edge
would require. Scripts: `situational_ats.py`, `line_shopping.py`. Data:
`situational_games.csv` (3,615 graded games), `line_shopping_games.csv`
(3,863 games with ≥2 books quoting a closing spread).

## Situational biases: none hold up

Tested 12 classic handicapping angles against the closing line across four
seasons (favorite/dog, home dog, spread-size buckets, neutral site,
conference vs. non-conference, rest advantage, "follow the line move",
early/mid/late season). **Every one landed within noise of 50%** — no
p-value below 0.05, one borderline result at p=0.09 (mid-season favorites,
47.4%) that isn't safe to trust given 12 tests were run. CFB closing lines
are efficient with respect to these angles; none of them is a rule to bet
by. Full table in the conversation / re-run `situational_ats.py` for the
printout.

## Line shopping: a real but small, non-sufficient edge

Compared "always bet the consensus (average) closing number" vs. "always
bet the best number available across quoted books" for both sides of every
game (avg. 3.0 books quoted per game in this dataset; median gap between
best and worst number was 0.5 pts, avg 0.73 pts, max 26 pts on some
outlier lines).

| | Consensus cover% | Best-shopped cover% | Lift |
|---|---|---|---|
| Betting home | 50.1% | 51.1% | +1.0 pt |
| Betting away | 49.9% | 50.7% | +0.8 pt |

Shopping alone flipped a would-be loss into a win/push in ~0.5-0.6% of
games. **This is a real, mechanical edge — always shop — but it's not
sufficient by itself**: standard -110 vig requires 52.38% to break even,
and best-shopped cover% (~51%) is still below that. It reduces the hole you
have to climb out of, it doesn't fill it.

**Caveat:** this dataset only carries ~3 books per game (CFBD's free-tier
line providers, mainly DraftKings/Bovada/ESPN Bet). Shopping across a
realistic real-world set of 6-10 books (FanDuel, MGM, Caesars, PointsBet,
offshore books, etc.) would very plausibly show a larger gap than what's
measured here — this result is a floor, not a ceiling, on shopping's value.

## Opening-line softness: no, that's not it either

Built a market-independent "fair spread" from CFBD's pregame Elo ratings
(updated game-to-game, no lookahead) — `margin = 3.38 + 0.041 * elo_diff`,
R²=0.332 in-sample, a genuinely decent predictive fit on its own. Then
tested: whenever this model disagreed with the market by ≥1/2/3/5/7 points,
does betting that side beat the number you'd actually have gotten — the
open if betting the open, the close if betting the close?

**No threshold, either line, showed a significant edge** (best: 51.3%
cover at a 2-3pt disagreement vs. the open, p≈0.22-0.28). And the closing
line moved *toward* the Elo fair value in only 42.4% of games — less than
half, meaning the market moves away from a naive Elo estimate more often
than toward it. That's not inefficiency; it's the market pricing in real
information (injuries, weather, personnel) that a box-score-derived model
doesn't see. Script: `opening_line_test.py`,
`opening_line_test_games.csv`.

This is the strongest result of the three tests: a model that explains a
third of the variance in game margins *still* doesn't convert into an ATS
edge against either the open or the close. Predictive skill about team
strength and market efficiency are different axes — this dataset says CFB
closing (and opening) lines already embed that skill.

## Bottom line for the handicapping model

Four independent tests, same verdict: team quality (backtest #1),
situational bias, opening-vs-closing line disagreement using a model that
explains 33% of margin variance, and — the one exception — line shopping,
which is real but too small to clear the vig alone. Nothing testable from
CFBD alone gets you to a profitable ATS model. A genuine edge would need
information the market hasn't already absorbed:
- real-time news/injury/lineup timing — needs a data source not in CFBD;
- deep specialization in a narrow slice (e.g. one conference, or
  totals/props) where the market is thinner and less studied;
- or accept that the realistic payoff of this project is a strong
  straight-up win probability / projected margin model (well-supported by
  the data) plus disciplined line shopping, not a "beat the spread"
  system.
