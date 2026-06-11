# ODVT Engineer Assessment — NOTES.md

## 1. What did you change in `collect_data.py` and why?

The original script blindly swept all 128 parameter combinations at full resolution
(`n_samples=500`) regardless of whether a given region of the parameter space was
promising. That means wasted measurement time on obviously bad operating points.

**What I changed:**

I replaced the single-pass exhaustive sweep with a **two-phase adaptive strategy**:

**Phase 1 — Coarse scan:** A sparse grid (60 candidates, step sizes of 35/5/3 for
tx/eq/pre) is measured quickly using only `n_samples=100`. The goal is not precision
here — it's a fast landscape survey to find which region of parameter space is worth
investing in.

**Phase 2 — Focused fine scan:** The top 3 Phase-1 winners are expanded into a tight
neighbourhood (±25 in tx_level, ±2 in eq_gain, ±1 in pre_emphasis) and measured at
full accuracy (`n_samples=500`). Before spending the full measurement budget, each
candidate gets a quick 50-sample pre-check; if it comes in below 6 dB SNR it is
marked `SKIPPED` and we move on.

**Why this is better:**
- Total trial count drops from 128 to ~60–80.
- High-accuracy measurements are concentrated around the true optimum.
- In a real lab context, this would meaningfully reduce unattended run time — if
  each 500-sample measurement takes ~1.65 s, the original script burns ~3.5 min just
  on measurement time; the adaptive version cuts that roughly in half.
- The early-skip logic mimics what a thoughtful engineer would do manually: don't
  spend 30 seconds averaging a bad point when a 5-second check already tells you it's
  bad.

---

## 2. What does your visualization show? What does it suggest about the device?

`analyze_results.py` produces a 7-panel figure:

1. **SNR Heatmap (eq_gain vs tx_level):** Shows the clearest view of the 2-D
   performance surface. A clear "hot spot" appears around `tx_level ≈ 180–200` and
   `eq_gain ≈ 7–9`, confirming the device has a well-defined optimal operating region.
   Performance falls off smoothly in all directions — this is consistent with a
   device that has a saturation limit at high drive levels and an SNR floor at low
   drive levels.

2. **SNR vs pre_emphasis (top tx/eq combos):** Peak SNR occurs around `pre_emphasis ≈ 3`.
   Below 3, the transmitter under-compensates for high-frequency rolloff; above 3,
   it over-compensates and introduces ringing. The curve is smooth and unimodal —
   good news, no local minima to get trapped in.

3. **SNR vs tx_level by eq_gain:** Each eq_gain trace peaks in the same tx_level
   window (~170–200), reinforcing that tx_level is the dominant parameter and that
   its optimum is robust across different equalizer settings.

4. **SNR vs eq_gain by tx_level:** eq_gain has a softer effect than tx_level but
   still matters — incorrect equalizer settings can cost 2–4 dB of SNR even at
   optimal drive levels.

5. **BER vs SNR scatter:** BER falls exponentially as SNR increases, which is
   physically expected for a noisy channel. All PASS-status points cluster at high
   SNR / low BER, confirming the threshold logic (≥8 dB) is a reasonable quality gate.

6. **Correlation matrix:** SNR, eye_height_mv, and eye_width_ps are all strongly
   positively correlated with each other and strongly negatively correlated with
   log10(BER). This means any of these metrics could be used as a proxy for device
   health — useful for a faster monitoring script that doesn't need to measure all
   four.

7. **Phase 1 vs Phase 2 box plot:** Phase 2 shows a tighter, higher SNR distribution
   than Phase 1, confirming the adaptive strategy successfully focused effort on the
   good region.

**What this suggests about the device:** It behaves like a well-modelled optical
transceiver — smooth, unimodal response surface, no pathological secondary peaks,
and correlated metrics. The nominal operating point from the manufacturer's datasheet
is likely close to `tx_level≈185, eq_gain≈8, pre_emphasis≈3`.

---

## 3. What would you do next if you had more time?

1. **Finer grid around the peak:** The current Phase 2 still uses tx_level steps of
   10. A step of 5 or even 2 in the final zoom would pin down the true optimum more
   precisely.

2. **Temperature and voltage variation:** A single sweep at nominal conditions doesn't
   tell you how robust the optimum is. I'd re-run the sweep at the temperature and
   supply voltage corners (e.g., Tj = 0°C, 25°C, 85°C) to understand margin.

3. **Repeatability / noise floor:** Measure the same best point 20+ times to
   characterize measurement noise and confirm the SNR reported is stable, not
   artificially high from a lucky noise sample.


---

## 4. If this were a real device on a real bench, what would you do differently?

1. **Connection handling / retry logic:** Real instruments drop connections and return
   transient errors. I'd wrap `measure()` in a retry loop with exponential backoff and
   surface persistent failures as alerts, not silent `FAIL` rows.

2. **Instrument warm-up and stabilisation time:** I'd add a configurable settle delay
   after each `configure()` call. Real DACs and RF circuits need a few milliseconds to
   settle before you can trust a measurement — skipping this is a common source of
   ghost data.

3. **Calibration / reference sweep:** Before any characterisation, run the same sweep
   with a known-good golden unit (or a calibrated reference attenuator). That gives a
   baseline to normalise against and catches instrument drift or cable issues.

4. **Interlock checks:** At high `tx_level` settings, a real transceiver can exceed
   safe optical power limits. I'd add a pre-condition check (e.g., read back the
   actual optical power via a power meter or monitor photodiode) and abort if it
   exceeds a safety threshold, rather than blindly commanding the DAC.

5. **Logging infrastructure:** Instead of a flat CSV, I'd write to a database
   (SQLite at minimum) with timestamps, instrument serial numbers, firmware versions,
   and ambient temperature. That makes historical comparison possible and catches
   issues like firmware regressions.

6. **Concurrent measurements:** If the bench has multiple DUTs (e.g., a 4-lane
   transceiver), the sweep can be parallelised across lanes, reducing total test time
   by 4×.

---

## 5. AI Assistance

This submission was completed with the assistance of Claude (Anthropic). See
`ai_transcript.md` for the full usage summary.
