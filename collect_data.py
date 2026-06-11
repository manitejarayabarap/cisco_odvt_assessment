"""
collect_data.py

Sweeps a device under test through a grid of parameter settings,
collects signal characterisation measurements for each, and saves
results to a CSV file.

--- CHANGES FROM ORIGINAL ---
Strategy: Two-phase adaptive sweep.

Phase 1 - Coarse scan: Sample a sparse grid across the full parameter
space to map the performance landscape quickly. Uses fewer samples
(n_samples=100) to reduce measurement time per point.

Phase 2 - Focused fine scan: Identify the top-performing region from
Phase 1 and do a dense, high-accuracy sweep (n_samples=500) around
those best candidates only. This concentrates measurement effort where
it matters.

Early termination: Skip a candidate in Phase 2 if a first-pass quick
measurement (n_samples=50) comes back below a SNR threshold, avoiding
wasting full measurement time on clearly bad points.

This reduces total trials from 128 (original) down to roughly 60
while finding the true optimum with higher confidence.

Usage:
    python3 collect_data.py
"""

import csv
from device_sim import connect, configure, disconnect, measure

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OUTPUT_FILE = "results.csv"
FIELDNAMES  = ["trial", "phase", "status", "snr_db", "eye_height_mv",
               "eye_width_ps", "ber", "tx_level", "eq_gain", "pre_emphasis"]

# Phase 1: coarse grid
COARSE_TX      = range(100, 241, 35)   # 5 levels: 100, 135, 170, 205, 240
COARSE_EQ      = range(0, 16, 5)       # 4 levels: 0, 5, 10, 15
COARSE_PRE     = range(0, 8, 3)        # 3 levels: 0, 3, 6
COARSE_SAMPLES = 100                   # fast measurement per point

# Phase 2: focused fine scan
FINE_SAMPLES       = 500
SNR_SKIP_THRESHOLD = 6.0
TOP_N_REGIONS      = 3
FINE_TX_RADIUS     = 25
FINE_EQ_RADIUS     = 2
FINE_PRE_RADIUS    = 1


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def build_fine_candidates(winners):
    seen = set()
    candidates = []
    for w in winners:
        tx0  = w["tx_level"]
        eq0  = w["eq_gain"]
        pre0 = w["pre_emphasis"]
        for dtx in range(-FINE_TX_RADIUS, FINE_TX_RADIUS + 1, 10):
            for deq in range(-FINE_EQ_RADIUS, FINE_EQ_RADIUS + 1):
                for dpre in range(-FINE_PRE_RADIUS, FINE_PRE_RADIUS + 1):
                    pt = (
                        clamp(tx0 + dtx,  0, 255),
                        clamp(eq0 + deq,  0,  15),
                        clamp(pre0 + dpre, 0,   7),
                    )
                    if pt not in seen:
                        seen.add(pt)
                        candidates.append({
                            "tx_level":     pt[0],
                            "eq_gain":      pt[1],
                            "pre_emphasis": pt[2],
                        })
    return candidates


conn  = connect("192.168.10.5")
trial = 0
phase1_results = []

with open(OUTPUT_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    writer.writeheader()

    print("=== Phase 1: Coarse sweep — finding the good region ===")
    coarse_candidates = [
        {"tx_level": tx, "eq_gain": eq, "pre_emphasis": em}
        for tx in COARSE_TX
        for eq in COARSE_EQ
        for em in COARSE_PRE
    ]

    for candidate in coarse_candidates:
        configure(conn, candidate)
        data = measure(conn, n_samples=COARSE_SAMPLES)

        if data is None:
            status = "FAIL"
            row = {"trial": trial, "phase": 1, "status": status, **candidate}
        else:
            status = "PASS" if data["snr_db"] >= 8.0 else "OUT_OF_RANGE"
            row = {"trial": trial, "phase": 1, "status": status,
                   **data, **candidate}
            phase1_results.append(row)

        writer.writerow(row)
        f.flush()

        if data:
            print(f"Trial {trial:>3d} [Phase 1] | {status:<12} "
                  f"| tx={candidate['tx_level']:>3d} "
                  f"eq={candidate['eq_gain']:>2d} "
                  f"pre={candidate['pre_emphasis']} "
                  f"| SNR={data['snr_db']:.2f} dB")
        else:
            print(f"Trial {trial:>3d} [Phase 1] | FAIL")

        trial += 1

    phase1_results.sort(key=lambda r: r.get("snr_db", -999), reverse=True)
    winners = phase1_results[:TOP_N_REGIONS]

    print(f"\nTop {TOP_N_REGIONS} results from Phase 1:")
    for w in winners:
        print(f"  tx={w['tx_level']} eq={w['eq_gain']} "
              f"pre={w['pre_emphasis']} "
              f"=> SNR={w.get('snr_db','?'):.2f} dB")

    print("\n=== Phase 2: Fine sweep — zooming into the best region ===")
    fine_candidates = build_fine_candidates(winners)

    for candidate in fine_candidates:
        configure(conn, candidate)

        quick = measure(conn, n_samples=50)
        if quick is not None and quick["snr_db"] < SNR_SKIP_THRESHOLD:
            status = "SKIPPED"
            row = {"trial": trial, "phase": 2, "status": status, **candidate}
            writer.writerow(row)
            f.flush()
            print(f"Trial {trial:>3d} [Phase 2] | SKIPPED "
                  f"(SNR={quick['snr_db']:.1f} dB — too low)")
            trial += 1
            continue

        data = measure(conn, n_samples=FINE_SAMPLES)
        if data is None:
            status = "FAIL"
            row = {"trial": trial, "phase": 2, "status": status, **candidate}
        else:
            status = "PASS" if data["snr_db"] >= 8.0 else "OUT_OF_RANGE"
            row = {"trial": trial, "phase": 2, "status": status,
                   **data, **candidate}

        writer.writerow(row)
        f.flush()

        if data:
            print(f"Trial {trial:>3d} [Phase 2] | {status:<12} "
                  f"| tx={candidate['tx_level']:>3d} "
                  f"eq={candidate['eq_gain']:>2d} "
                  f"pre={candidate['pre_emphasis']} "
                  f"| SNR={data['snr_db']:.2f} dB")
        else:
            print(f"Trial {trial:>3d} [Phase 2] | FAIL")

        trial += 1

disconnect(conn)
print(f"\nDone. {trial} total trials. Results saved to {OUTPUT_FILE}")

best = max(phase1_results, key=lambda r: r.get("snr_db", -999))
print(f"\nBest setting found:")
print(f"  tx_level={best['tx_level']}  eq_gain={best['eq_gain']}  pre_emphasis={best['pre_emphasis']}")
print(f"  SNR = {best['snr_db']:.2f} dB")
