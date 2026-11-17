"""
Tigris & Euphrates: what the scoring rule does, and does not, imply.

Every result below is tagged with the kind of claim it can support. The tags
are load-bearing. Blur them and you will draw board-game advice out of a
boardless toy process.

  [RULE]  Follows from the published rules, by argument or exhaustive check.
          True of the game itself.
  [MODEL] A property of the declared allocation process in `simulate()`.
          True of that process. Says nothing directly about the game.
  [HYP]   A conjecture about real play. Stated so it could be tested against
          game records or a rules-complete engine. Not tested here.

Rules used, from the Z-Man / Fantasy Flight rulebook (2014):

  1. "Each player determines in which sphere they possess the fewest number of
     victory points... The player whose lowest sphere has the highest number of
     victory points is the winner. In the case of a tie, the tied players
     compare their second lowest spheres, and so on." (p. 14)

     That is a lexicographic comparison of the ascending-sorted four-vector,
     not a comparison of scalars. A player's result is a VECTOR. This module
     never reduces it to `min()`.

  2. Treasures are wild: "you may allocate each treasure individually to any
     victory point type of your choice." (p. 12)

  3. The bag holds 153 civilisation tiles: 57 red temples, 36 blue farms,
     30 green markets, 30 black settlements. (p. 3)

Deliberately NOT modelled, and therefore not claimed: the board, kingdoms,
adjacency, leaders, monuments, opponents, or hidden information. Two sections
that look inviting from here are omitted outright rather than qualified:

  - A "count the bag" calculation. The rulebook makes this illegal and
    impossible: "The number of tiles in the bag is hidden information; players
    cannot deliberately count the tiles in the bag" and "Tiles that are removed
    from the game... are kept facedown in the box and cannot be viewed by any
    player." (p. 9) Tiles leave the game face down via replacement, revolts,
    and wars, so the unseen pool's composition is not computable.

  - A war expected-value curve. It was one hand-picked scenario, omitted the
    priest/treasure exception (p. 10), and priced a multi-point windfall by the
    marginal value of a single point.

Run:  python3 tigris_sim.py
Out:  sim_results.json, written beside this file, plus a report on stdout.
"""

import itertools
import json
from pathlib import Path

import numpy as np

SEED = 20260807
TRIALS = 60_000
OUT_PATH = Path(__file__).resolve().parent / "sim_results.json"

COLORS = ["red", "blue", "green", "black"]
BAG = {"red": 57, "blue": 36, "green": 30, "black": 30}
TOTAL_TILES = sum(BAG.values())                       # 153
BAG_P = np.array([BAG[c] for c in COLORS]) / TOTAL_TILES


# ============================================================ the scoring rule
# Everything in this section is [RULE]: it is the rulebook's comparison,
# implemented directly, with no simulation involved.


def leximin_key(pts):
    """The comparison key: victory points sorted ascending.

    Rulebook p. 14 compares lowest spheres, then second-lowest, and so on.
    That is exactly lexicographic order on the ascending-sorted vector.
    """
    return np.sort(pts, axis=-1)


def leximin_cmp(a, b):
    """-1 if portfolio `a` loses to `b`, +1 if it beats it, 0 if tied.

    Elementwise on the sorted keys, first difference decides.
    """
    ka, kb = np.sort(a), np.sort(b)
    for x, y in zip(ka, kb):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0


def allocate_wilds(pts, wilds):
    """Allocate `wilds` treasures to maximise the portfolio under leximin.

    Water-filling: repeatedly add one to a sphere currently at the floor.
    `verify_waterfilling_is_optimal()` checks this exhaustively rather than
    asking you to take it on faith.
    """
    p = pts.copy()
    rows = np.arange(p.shape[0])
    for _ in range(wilds):
        p[rows, np.argmin(p, axis=1)] += 1
    return p


def verify_waterfilling_is_optimal(max_pt=6, max_wilds=4):
    """[RULE] Exhaustive check that greedy water-filling is leximin-optimal.

    Over every portfolio with entries in [0, max_pt] and every wild count up to
    max_wilds, compare greedy against every possible allocation. Returns the
    number of portfolios checked and the number of counterexamples found.
    """
    checked = 0
    failures = 0
    for base in itertools.product(range(max_pt + 1), repeat=4):
        arr = np.array(base, dtype=np.int32)
        for w in range(max_wilds + 1):
            greedy = allocate_wilds(arr.reshape(1, 4), w)[0]
            # every way to split w wilds across 4 spheres
            for split in itertools.combinations_with_replacement(range(4), w):
                cand = arr.copy()
                for c in split:
                    cand[c] += 1
                if leximin_cmp(cand, greedy) > 0:
                    failures += 1
            checked += 1
    return {"portfolios_checked": checked, "counterexamples": failures,
            "max_pt": max_pt, "max_wilds": max_wilds}


def floor_multiplicities(pts):
    """How many spheres hold the floor value."""
    return (pts == pts.min(axis=1, keepdims=True)).sum(axis=1)


def improvement_level(before, after):
    """[RULE] Which leximin criterion a change improves: 1 = the lowest
    sphere, 2 = the next criterion, and so on. 0 = no improvement.

    This is the function a scalar `min` cannot provide. It is why "a windfall
    into a level floor is worth exactly zero" was wrong: the lowest sphere is
    unchanged, but a later criterion moves, and later criteria decide games.
    """
    kb, ka = np.sort(before), np.sort(after)
    for i in range(4):
        if ka[i] > kb[i]:
            return i + 1
        if ka[i] < kb[i]:
            return 0
    return 0


def windfall_levels(max_pt=9, budget=4):
    """[RULE] For every portfolio shape, which criterion does a `budget`-point
    single-sphere windfall into a lowest sphere improve?

    Reported by floor multiplicity. The accurate statement: the lowest sphere
    moves only when one sphere holds the floor alone, but a later criterion
    moves in every case.
    """
    by_multiplicity = {w: {"n": 0, "levels": [0, 0, 0, 0, 0]} for w in range(1, 5)}
    for base in itertools.product(range(max_pt + 1), repeat=4):
        arr = np.array(base, dtype=np.int32)
        w = int((arr == arr.min()).sum())
        after = arr.copy()
        after[int(np.argmin(arr))] += budget
        lvl = improvement_level(arr, after)
        by_multiplicity[w]["n"] += 1
        by_multiplicity[w]["levels"][lvl] += 1
    out = []
    for w in range(1, 5):
        rec = by_multiplicity[w]
        if rec["n"] == 0:
            continue
        out.append({
            "floor_multiplicity": w,
            "portfolios": rec["n"],
            "share_improving_criterion_1": rec["levels"][1] / rec["n"],
            "share_improving_criterion_2_plus": sum(rec["levels"][2:]) / rec["n"],
            "share_improving_nothing": rec["levels"][0] / rec["n"],
        })
    return {"budget": budget, "max_pt": max_pt, "by_floor_multiplicity": out}


# =========================================================== the propositions
# Three closed-form results, each proved in the article and checked here by
# brute force. The proofs are short; the checks exist because short proofs are
# exactly the ones that hide an unconsidered case.


def waterfill_level(x, t):
    """Proposition 3: the level to which `t` treasures raise the floor.

        lambda* = max { lambda : sum_i max(0, lambda - x_i) <= t }
    """
    m = int(min(x))
    best = m
    for lam in range(m, m + t + 1):
        if sum(max(0, lam - v) for v in x) <= t:
            best = lam
    return best


def verify_floor_cost(max_pt=7):
    """[RULE] Proposition 1: raising the lowest sphere by exactly 1 costs
    exactly w points, where w is the number of spheres holding the floor value.

    One point into each sphere at the floor, and nothing cheaper works, because any
    sphere left at the old minimum still sets the minimum.
    """
    checked = failures = 0
    for base in itertools.product(range(max_pt + 1), repeat=4):
        x = np.array(base, dtype=np.int32)
        w = int((x == x.min()).sum())
        need = None
        for k in range(1, 9):
            if allocate_wilds(x.reshape(1, 4), k)[0].min() > x.min():
                need = k
                break
        checked += 1
        if need != w:
            failures += 1
    return {"portfolios_checked": checked, "counterexamples": failures}


def verify_criterion_index(max_pt=7, max_budget=6):
    """[RULE] Proposition 2: a windfall of b >= 1 points into a single lowest
    sphere improves exactly criterion w, where w is the floor multiplicity.

    If the sorted vector is (m, ..., m, ...) with m appearing w times, adding
    b to one of those copies leaves positions 1..w-1 equal to m and lifts
    position w strictly above m. The first difference is at index w.
    """
    checked = failures = 0
    for base in itertools.product(range(max_pt + 1), repeat=4):
        x = np.array(base, dtype=np.int32)
        w = int((x == x.min()).sum())
        for b in range(1, max_budget + 1):
            y = x.copy()
            y[int(np.argmin(x))] += b
            checked += 1
            if improvement_level(x, y) != w:
                failures += 1
    return {"cases_checked": checked, "counterexamples": failures,
            "max_budget": max_budget}


def verify_waterfill_level(max_pt=9, max_t=8):
    """[RULE] Proposition 3, checked against the greedy allocator."""
    checked = failures = 0
    for base in itertools.product(range(max_pt + 1), repeat=4):
        x = np.array(base, dtype=np.int32)
        for t in range(max_t + 1):
            checked += 1
            if allocate_wilds(x.reshape(1, 4), t)[0].min() != waterfill_level(x, t):
                failures += 1
    return {"cases_checked": checked, "counterexamples": failures}


def waterfill_example(x=(3, 5, 9, 5), t=6):
    """A worked case for the article's diagram.

    Spheres are given in play order (red, blue, green, black); the formula
    cares only about the multiset.
    """
    xa = np.array(x, dtype=np.int32)
    lam = waterfill_level(xa, t)
    spent = int(sum(max(0, lam - v) for v in xa))
    final = allocate_wilds(xa.reshape(1, 4), t)[0]
    return {
        "start": [int(v) for v in xa],
        "treasures": t,
        "level": lam,
        "spent_reaching_level": spent,
        "leftover": t - spent,
        "final": [int(v) for v in final],
        "colours": COLORS,
        "cost_curve": [
            {"level": L, "cost": int(sum(max(0, L - v) for v in xa))}
            for L in range(int(min(xa)), int(min(xa)) + t + 2)
        ],
    }


# ====================================================== the toy model, declared
# Everything below is [MODEL]. It is an online allocation process, not the game.


def rand_argmin(p, noise):
    """argmin with ties broken uniformly at random.

    numpy's argmin returns the lowest index, so a player steering into "the
    weakest colour" would silently always prefer red over black when tied,
    starving the last colour in the list. Adding noise from [0, 1) randomises
    ties without ever reordering genuinely different integer counts.
    """
    return np.argmin(p + noise, axis=1)


def simulate(n_points, steer, trials, rng):
    """Accumulate `n_points` colour-tagged points across `trials` parallel runs.

    On a steered step the point goes to a current-weakest colour. On an
    unsteered step it is drawn from BAG_P.

    THE BAG_P ASSUMPTION IS THE MODEL'S LARGEST LEAP and it is not a rule.
    Tile frequency is not victory-point arrival frequency: points require an
    eligible leader or king, kings collect for absent colours, revolts pay red
    regardless of size, wars pay in bursts, monuments pay repeatedly without
    consuming tiles, and traders control the wild treasures. Any result that
    leans on BAG_P is [HYP] at best, never [RULE].
    """
    pts = np.zeros((trials, 4), dtype=np.int32)
    rows = np.arange(trials)
    for step in range(n_points):
        if isinstance(steer, (float, int)):
            steered = rng.random(trials) < steer
        else:
            steered = np.full(trials, bool(steer[step]))
        drift = rng.choice(4, size=trials, p=BAG_P)
        idx = np.where(steered, rand_argmin(pts, rng.random((trials, 4))), drift)
        pts[rows, idx] += 1
    return pts


def binding_colour(n_points=36, steer=0.0, trials=TRIALS):
    """[MODEL] Which colour ends up lowest, reported two ways.

    Quoting only the share conditional on a unique floor, then calling it a
    share of games, overstates it. Both denominators are given here.
    """
    rng = np.random.default_rng(SEED)
    pts = simulate(n_points, float(steer), trials, rng)
    mins = pts.min(axis=1, keepdims=True)
    at_floor = pts == mins
    unique = at_floor.sum(axis=1) == 1
    unique_share = float(unique.mean())

    idx = np.argmin(pts[unique], axis=1)
    cond = np.bincount(idx, minlength=4) / max(1, unique.sum())

    # unconditional: share of ALL runs where this colour is at the floor alone
    uncond = cond * unique_share

    scarce = float(uncond[COLORS.index("green")] + uncond[COLORS.index("black")])
    return {
        "n_points": n_points, "steer": steer,
        "unique_floor_share": unique_share,
        "bag_share": {c: BAG[c] / TOTAL_TILES for c in COLORS},
        "sole_floor_given_unique": {c: float(cond[i]) for i, c in enumerate(COLORS)},
        "sole_floor_unconditional": {c: float(uncond[i]) for i, c in enumerate(COLORS)},
        "green_or_black_unconditional": scarce,
    }


def balance_efficiency(n_points=36, steers=(0.0, 0.25, 0.5, 0.75, 1.0),
                       trials=TRIALS):
    """[MODEL] Same points, different allocation discipline.

    NOTE ON THE METRIC. It is tempting to call `4 * min / n_points` the share
    of raw points "converted into score". It is not: it is the lowest sphere as
    a fraction of the perfectly balanced maximum (n_points / 4). Both are
    reported here under honest names. With 36 points a perfect 9 is 100%
    balance efficiency but only 25% of raw points, so the two differ by
    construction, and the conversion reading overstates by roughly 4x.
    """
    out = []
    perfect = n_points / 4
    for s in steers:
        rng = np.random.default_rng(SEED + int(s * 1000))
        pts = simulate(n_points, float(s), trials, rng)
        floor = pts.min(axis=1).astype(float)
        out.append({
            "steer": float(s),
            "mean_lowest_sphere": float(floor.mean()),
            "balance_efficiency": float(floor.mean()) / perfect,
            "share_of_raw_points": float(floor.mean()) / n_points,
            "mean_floor_multiplicity": float(floor_multiplicities(pts).mean()),
        })
    return {"n_points": n_points, "perfect_floor": perfect, "rows": out}


def continue_sim(pts, steps, steer_rand, drift_rand, tie_rand):
    """Play `steps` further points onto existing portfolios, reusing a fixed
    random stream so variants can be compared as a paired experiment."""
    p = pts.copy()
    rows = np.arange(p.shape[0])
    for t in range(steps):
        idx = np.where(steer_rand[t], rand_argmin(p, tie_rand[t]), drift_rand[t])
        p[rows, idx] += 1
    return p


def marginal_value_horizon(n_now=24, horizons=(0, 2, 4, 8, 12, 20),
                           steer=0.35, trials=30_000):
    """[MODEL] What one extra point does to the PRIMARY SPHERE, by the rank of
    the colour it lands in, at different distances from the end.

    The quantity is named precisely: this is the effect on the lowest sphere
    only. It is not "the value of a point", which would require opponents.
    At horizon 0 the non-floor ranks read zero by construction -- that is an
    artefact of stopping the clock, and it is reported, not interpreted.
    """
    rows = []
    for h in horizons:
        rng = np.random.default_rng(SEED + 400 + h)
        pts = simulate(n_now, float(steer), trials, rng)
        order = np.argsort(pts, axis=1)
        idx_rows = np.arange(trials)
        steer_rand = rng.random((max(h, 1), trials)) < steer
        drift_rand = rng.choice(4, size=(max(h, 1), trials), p=BAG_P)
        tie_rand = rng.random((max(h, 1), trials, 4))
        base = continue_sim(pts, h, steer_rand, drift_rand, tie_rand).min(axis=1)
        entry = {"horizon": h}
        for rank in range(1, 5):
            q = pts.copy()
            q[idx_rows, order[:, rank - 1]] += 1
            fin = continue_sim(q, h, steer_rand, drift_rand, tie_rand).min(axis=1)
            entry[f"rank_{rank}"] = float((fin - base).mean())
        rows.append(entry)
    return {"n_now": n_now, "steer": steer, "measures": "lowest sphere only",
            "rows": rows}


def windfall_vs_spread(n_points=36, steer=0.35, budget=4, trials=TRIALS):
    """[MODEL] A single-sphere windfall against the same points placed freely,
    scored three ways.

    Measuring only the change in `min` leads to the conclusion that a windfall
    into a level floor is "worth exactly zero". Two of the three measures here
    show why that is wrong.
    """
    rng = np.random.default_rng(SEED + 13)
    pts = simulate(n_points, float(steer), trials, rng)
    fm = floor_multiplicities(pts)
    rows = np.arange(trials)

    windfall = pts.copy()
    windfall[rows, np.argmin(windfall, axis=1)] += budget

    spread = pts.copy()
    for _ in range(budget):
        spread[rows, np.argmin(spread, axis=1)] += 1

    d_floor_windfall = (windfall.min(axis=1) - pts.min(axis=1)).astype(float)
    d_floor_spread = (spread.min(axis=1) - pts.min(axis=1)).astype(float)

    # does the windfall improve ANY leximin criterion, and which?
    lvl_windfall = np.array([improvement_level(pts[i], windfall[i])
                          for i in range(min(trials, 20_000))])

    by_multiplicity = []
    for w in range(1, 5):
        m = fm == w
        if m.sum() < 50:
            continue
        mm = m[:len(lvl_windfall)]
        by_multiplicity.append({
            "floor_multiplicity": w,
            "share": float(m.mean()),
            "windfall_floor_gain": float(d_floor_windfall[m].mean()),
            "spread_floor_gain": float(d_floor_spread[m].mean()),
            "windfall_improves_some_criterion": float((lvl_windfall[mm] > 0).mean()),
            "windfall_improves_criterion_1": float((lvl_windfall[mm] == 1).mean()),
        })
    return {"budget": budget, "n_points": n_points, "steer": steer,
            "by_floor_multiplicity": by_multiplicity}


def windfall_head_to_head(n_points=36, steer=0.35, budget=4, trials=20_000):
    """[MODEL] The question the lowest-sphere measure cannot answer: does the
    windfall change who WINS?

    Each run draws a portfolio and an independent opponent, then compares under
    the real rulebook comparison, with and without the windfall. Reported by
    floor multiplicity. Where the lowest sphere is unchanged, the head-to-head result
    still moves -- which is the whole point of the tiebreak rule.
    """
    rng = np.random.default_rng(SEED + 29)
    me = simulate(n_points, float(steer), trials, rng)
    opp = simulate(n_points, float(steer), trials, rng)
    fm = floor_multiplicities(me)
    rows = np.arange(trials)

    windfall = me.copy()
    windfall[rows, np.argmin(windfall, axis=1)] += budget

    before = np.array([leximin_cmp(me[i], opp[i]) for i in range(trials)])
    after = np.array([leximin_cmp(windfall[i], opp[i]) for i in range(trials)])

    out = []
    for w in range(1, 5):
        m = fm == w
        if m.sum() < 50:
            continue
        out.append({
            "floor_multiplicity": w,
            "share": float(m.mean()),
            "win_rate_before": float((before[m] > 0).mean()),
            "win_rate_after": float((after[m] > 0).mean()),
            "result_changed": float((after[m] != before[m]).mean()),
        })
    return {"budget": budget, "trials": trials, "by_floor_multiplicity": out}


def phase_strategy(n_points=44, steer_budget=12, trials=TRIALS):
    """[MODEL] Spending a fixed steering budget late rather than evenly.

    IMPORTANT SCOPE LIMIT. "Steering" is a coupon in this process: both
    policies are handed the same number of points AND the same number of
    steered opportunities regardless of earlier choices. Nothing in the game
    works that way -- control over colour comes from leaders, position,
    monuments, treasure access and opponents, and early actions create the
    board that makes late scoring possible. The number below is a property of
    online allocation with a fixed budget. It is not points available "for
    free" at a table.
    """
    level_sched = np.zeros(n_points, dtype=bool)
    level_sched[np.linspace(0, n_points - 1, steer_budget).round().astype(int)] = True

    phased_sched = np.zeros(n_points, dtype=bool)
    phased_sched[-steer_budget:] = True

    rng = np.random.default_rng(SEED + 17)
    level = simulate(n_points, level_sched, trials, rng).min(axis=1)
    rng = np.random.default_rng(SEED + 17)          # same drift stream
    phased = simulate(n_points, phased_sched, trials, rng).min(axis=1)

    return {"n_points": n_points, "steer_budget": steer_budget,
            "level_mean_floor": float(level.mean()),
            "phased_mean_floor": float(phased.mean()),
            "phased_edge": float(phased.mean() - level.mean()),
            "measures": "lowest sphere only"}


def sensitivity(budget=4, trials=20_000):
    """[MODEL] The headline shapes under varied assumptions.

    The review that prompted this rewrite noted that almost no consequential
    parameter was varied. These sweeps let a reader see which conclusions are
    robust to the arbitrary choices and which are artefacts of them.
    """
    out = {"n_points": [], "steer": [], "arrival": []}

    for n in (24, 36, 48, 60):
        r = binding_colour(n_points=n, steer=0.0, trials=trials)
        out["n_points"].append({"n_points": n,
                                "unique_floor_share": r["unique_floor_share"],
                                "green_or_black": r["green_or_black_unconditional"]})

    for s in (0.0, 0.2, 0.35, 0.5):
        r = binding_colour(n_points=36, steer=s, trials=trials)
        out["steer"].append({"steer": s,
                             "unique_floor_share": r["unique_floor_share"],
                             "green_or_black": r["green_or_black_unconditional"]})

    # what if points do NOT arrive in bag proportions?
    global BAG_P
    saved = BAG_P.copy()
    alternatives = {
        "bag_proportions": saved,
        "uniform": np.array([0.25, 0.25, 0.25, 0.25]),
        "halfway_to_uniform": (saved + 0.25) / 2,
    }
    for name, p in alternatives.items():
        BAG_P = p / p.sum()
        r = binding_colour(n_points=36, steer=0.0, trials=trials)
        out["arrival"].append({"arrival": name,
                               "p": [float(x) for x in BAG_P],
                               "green_or_black": r["green_or_black_unconditional"]})
    BAG_P = saved
    return out


# ==================================================================== reporting


def main():
    results = {
        "_meta": {
            "seed": SEED,
            "trials": TRIALS,
            "claim_tiers": {
                "RULE": "follows from the published rules; true of the game",
                "MODEL": "a property of the toy allocation process only",
                "HYP": "a conjecture about real play; not tested here",
            },
            "not_modelled": ["board", "adjacency", "kingdoms", "leaders",
                             "monuments", "opponents' choices",
                             "hidden information", "action costs"],
        },
        "rule_waterfilling_optimal": verify_waterfilling_is_optimal(),
        "rule_windfall_levels": windfall_levels(),
        "rule_floor_cost": verify_floor_cost(),
        "rule_criterion_index": verify_criterion_index(),
        "rule_waterfill_level": verify_waterfill_level(),
        "rule_waterfill_example": waterfill_example(),
        "model_binding_colour": binding_colour(),
        "model_balance_efficiency": balance_efficiency(),
        "model_marginal_value_horizon": marginal_value_horizon(),
        "model_windfall_vs_spread": windfall_vs_spread(),
        "model_windfall_head_to_head": windfall_head_to_head(),
        "model_phase_strategy": phase_strategy(),
        "model_sensitivity": sensitivity(),
    }

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    # Numbering follows the article's propositions, not the order the checks
    # happen to run in.
    for key, label in [("rule_waterfill_level", "P1  floor after t treasures"),
                       ("rule_waterfilling_optimal", "P2  greedy filling is optimal"),
                       ("rule_floor_cost", "P3  cost to lift the floor = w"),
                       ("rule_criterion_index", "P4  windfall improves criterion w")]:
        r = results[key]
        n = r.get("cases_checked", r.get("portfolios_checked"))
        print(f"[RULE] {label}: {r['counterexamples']} counterexamples in {n} cases")

    ex = results["rule_waterfill_example"]
    print(f"       worked example: {ex['start']} + {ex['treasures']} treasures "
          f"-> level {ex['level']} (spent {ex['spent_reaching_level']}, "
          f"leftover {ex['leftover']}), final {ex['final']}")

    print("\n[RULE] a 4-point single-sphere windfall, by floor multiplicity:")
    for r in results["rule_windfall_levels"]["by_floor_multiplicity"]:
        print(f"  multiplicity {r['floor_multiplicity']}: criterion 1 moves "
              f"{r['share_improving_criterion_1']:6.1%} | criterion 2+ moves "
              f"{r['share_improving_criterion_2_plus']:6.1%} | nothing moves "
              f"{r['share_improving_nothing']:6.1%}")

    b = results["model_binding_colour"]
    print(f"\n[MODEL] unique floor in {b['unique_floor_share']:.1%} of runs; "
          f"green or black alone at the floor in "
          f"{b['green_or_black_unconditional']:.1%} of ALL runs")

    print("\n[MODEL] balance efficiency (NOT 'share of raw points'):")
    for r in results["model_balance_efficiency"]["rows"]:
        print(f"  steer {r['steer']:.2f}: floor {r['mean_lowest_sphere']:5.2f} | "
              f"efficiency {r['balance_efficiency']:6.1%} | "
              f"raw points {r['share_of_raw_points']:6.1%}")

    print("\n[MODEL] windfall head-to-head against an independent opponent:")
    for r in results["model_windfall_head_to_head"]["by_floor_multiplicity"]:
        print(f"  multiplicity {r['floor_multiplicity']}: win {r['win_rate_before']:.1%} -> "
              f"{r['win_rate_after']:.1%} | result changed "
              f"{r['result_changed']:.1%}")

    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
