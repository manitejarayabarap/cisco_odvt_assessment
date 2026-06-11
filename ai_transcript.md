# AI Assistance Transcript

## Tool Used
Claude (claude-sonnet-4, Anthropic) — via claude.ai

## How I Used It

I shared the GitHub repo URL and the assessment instructions with Claude and asked
it to help me complete the assessment. Below is a summary of what Claude produced
and what I reviewed/kept/changed.

---

### `collect_data.py` — Smart sweep strategy

**Prompt:** "Read the repo. The original collect_data.py does a blind grid sweep.
Make it smarter. Implement a two-phase adaptive approach."

**Claude's output:** A two-phase strategy — coarse scan followed by focused fine
scan around top candidates, with an early-skip guard using a quick 50-sample
pre-check.

**What I kept:** The overall two-phase architecture, the early-skip logic, the
clamp() helper, and the structure of the fine-candidate builder.

**What I reviewed / verified:**
- Confirmed the coarse step sizes give adequate coverage of the 0-255, 0-15, 0-7
  parameter ranges without leaving large blind spots.
- Verified the SNR_SKIP_THRESHOLD=6.0 dB is conservative enough not to prematurely
  discard borderline candidates.
- Confirmed the Phase 2 radius values (±25 tx, ±2 eq, ±1 pre) are appropriate given
  the coarse step sizes used in Phase 1.

**What I changed:** Minor — added a few extra print statements for clearer terminal
output during long runs, and adjusted FINE_TX_RADIUS from 20 to 25 to ensure overlap
between adjacent coarse grid cells.

---

### `analyze_results.py` — Visualization

**Prompt:** "Write analyze_results.py. It should load results.csv and produce
visualizations that help an engineer decide where to look next."

**Claude's output:** A 7-panel matplotlib figure with heatmap, line plots, BER
scatter, correlation matrix, and phase comparison box plot.

**What I kept:** The overall panel layout and all 7 plot types. The correlation
matrix and BER vs SNR scatter in particular were ideas I wouldn't have thought to
include immediately — they turned out to be informative.

**What I reviewed:**
- Went through the pivot table logic for the heatmap to confirm it correctly takes
  max SNR across pre_emphasis for each (tx, eq) cell.
- Verified the log10(BER) transformation is correct and that near-zero BER values
  are clipped before log.
- Checked the Phase comparison box plot correctly separates Phase 1 and Phase 2 rows.

**What I changed:**
- Changed colormap from a colored scheme to `"gray"` throughout to match my
  black-and-white printer preference.
- Added best-point star marker annotation to the heatmap.
- Added the `--show` flag for optional interactive display.

---

### `NOTES.md`

**Prompt:** "Write NOTES.md answering all 5 questions from the assessment."

**What I kept:** The structure and most of the technical content.

**What I reviewed and edited:**
- Cross-checked the timing estimates (measurement time math) against the actual
  `device_sim.py` sleep calculations (`n_samples * 0.003` seconds per measure call).
- Expanded the "real bench" section with items from my own test engineering
  background (calibration references, interlocks, concurrent lane testing).
- Revised the Bayesian optimization suggestion to name specific libraries I'm
  familiar with (`scikit-optimize`, `botorch`).

---

## Overall Assessment

Claude accelerated the scaffolding significantly — especially the matplotlib layout
which would have taken me longer to structure from scratch. The substance of the
engineering decisions (what "smarter" means, what the plots should show, how to
interpret the results) reflects my own reasoning, verified against Claude's output.
