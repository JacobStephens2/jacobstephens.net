"""Generate the post's chart-data block from sim_results.json.

Without this, the article has three sources of truth: the Python output,
sim_results.json, and a `D` object transcribed into the article's JavaScript
by hand. The third one drifts silently. This removes it.

  python3 build_chart_data.py           rewrite the block in the post
  python3 build_chart_data.py --check   exit 1 if the block is out of date

The block is delimited in the post by the two marker comments below and is
the only part of the article this script will touch.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "sim_results.json"
POSTS_DIR = HERE.parent

BEGIN = "      /* @generated from sim_results.json by build_chart_data.py - do not edit */"
END = "      /* @end generated */"

NAMES = {"red": "Red temples", "blue": "Blue farms",
         "green": "Green markets", "black": "Black settlements"}
ORDER = ["red", "blue", "green", "black"]


def render(results):
    bag = results["model_binding_colour"]
    balance = results["model_balance_efficiency"]["rows"]
    horizon = results["model_marginal_value_horizon"]["rows"]
    h2h = results["model_windfall_head_to_head"]["by_floor_multiplicity"]

    lines = [BEGIN, "      var D = {"]

    lines.append("        bag: [")
    for c in ORDER:
        lines.append(
            f"          {{ name: '{NAMES[c]}', bag: {bag['bag_share'][c]:.4f},"
            f" floor: {bag['sole_floor_unconditional'][c]:.4f} }},"
        )
    lines.append("        ],")

    lines.append("        balance: [")
    for r in balance:
        lines.append(
            f"          {{ steer: {r['steer']:.2f},"
            f" floor: {r['mean_lowest_sphere']:.3f},"
            f" eff: {r['balance_efficiency']:.4f},"
            f" raw: {r['share_of_raw_points']:.4f} }},"
        )
    lines.append("        ],")

    lines.append("        horizon: [")
    for r in horizon:
        v = ", ".join(f"{r[f'rank_{k}']:.3f}" for k in range(1, 5))
        lines.append(f"          {{ h: {r['horizon']}, v: [{v}] }},")
    lines.append("        ],")

    wf = results["rule_waterfill_example"]
    order = wf["colours"]
    lines.append("        waterfill: {")
    lines.append(f"          level: {wf['level']}, treasures: {wf['treasures']},"
                 f" spent: {wf['spent_reaching_level']}, leftover: {wf['leftover']},")
    lines.append("          spheres: [")
    for i, c in enumerate(order):
        lines.append(
            f"            {{ name: '{c}', start: {wf['start'][i]},"
            f" final: {wf['final'][i]} }},"
        )
    lines.append("          ],")
    lines.append("        },")

    lines.append("        h2h: [")
    for r in h2h:
        lines.append(
            f"          {{ w: {r['floor_multiplicity']}, share: {r['share']:.4f},"
            f" before: {r['win_rate_before']:.4f},"
            f" after: {r['win_rate_after']:.4f},"
            f" changed: {r['result_changed']:.4f} }},"
        )
    lines.append("        ],")

    lines.append("      };")
    lines.append(END)
    return "\n".join(lines)


def targets():
    """Every post carrying the generated block. Both the full article and the
    Simplified Technical English version share one source of truth."""
    found = sorted(p for p in POSTS_DIR.glob("*/index.html")
                   if BEGIN in p.read_text())
    if not found:
        sys.exit(f"no post under {POSTS_DIR} contains the generated marker")
    return found


def main():
    check = "--check" in sys.argv
    results = json.loads(RESULTS.read_text())
    block = render(results)

    stale = []
    for post in targets():
        html = post.read_text()
        i, j = html.find(BEGIN), html.find(END)
        if j == -1:
            sys.exit(f"end marker not found in {post}")
        if html[i:j + len(END)] == block:
            print(f"up to date: {post.parent.name}")
            continue
        if check:
            stale.append(post.parent.name)
            continue
        post.write_text(html[:i] + block + html[j + len(END):])
        print(f"updated:    {post.parent.name}")

    if stale:
        sys.exit("STALE: chart data does not match sim_results.json in "
                 + ", ".join(stale) + ". Run: python3 build_chart_data.py")


if __name__ == "__main__":
    main()
