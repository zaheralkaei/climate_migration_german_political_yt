"""
Step 10b: LLM self-consistency (stability) check for Sec 4.4 of the paper.

Re-annotates a random sample of pairs that Step 10 already annotated, using the
*same* model, prompts and decoding settings, then measures how far run 2 agrees
with run 1. This is a self-consistency measure, not an accuracy measure: it
separates "the model is unstable" from "the task is subjective", which is the
argument Sec 4.4 makes about the moderate LLM-vs-gold agreement.

Identical settings are guaranteed by construction: the annotation functions are
imported from 10_llm_annotator_gold_eval.py rather than reimplemented here, so
the prompts, tool schema, max_tokens, retry logic and parsers cannot drift.

Outputs (both under 10_llm_annotations/):
  stability_run2.jsonl    — run-2 annotations, appended as they complete
  stability_report.json   — agreement metrics, read back by 13b_paper_numbers.py

Reported metrics, matching the claims in Sec 4.4:
  interaction quality — exact agreement, quadratic-weighted and unweighted kappa, MAE
  child / parent stance — exact agreement, unweighted kappa
  techniques — exact-set match, mean Jaccard (not claimed in the paper; context)

COST. The check makes 4 API calls per pair (child stance, parent stance,
techniques, interaction), so the default 200-pair sample is ~800 calls against
claude-opus-4-6. The script therefore does nothing until it is given --run:

    python 10b_stability_check.py                 # dry run: show the plan, call nothing
    python 10b_stability_check.py --run           # execute (costs money)
    python 10b_stability_check.py --run -n 50     # smaller sample
    python 10b_stability_check.py --report-only   # recompute metrics from a finished run

Interrupting is safe: completed pairs are appended to stability_run2.jsonl as
they finish, and re-running with --run resumes from where it stopped.
"""
import argparse
import importlib.util
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from utils.jsonl_io import load_jsonl, append_jsonl

# --- sample definition -------------------------------------------------------
# Fixed so the sample is identical on every run and can be audited. Seed 42
# matches the sampling seed used in Step 08.
SEED = 42
N_DEFAULT = 200

RUN1_FILE = Path("./10_llm_annotations/llm_annotated_subset.jsonl")
PAIRS_FILE = Path("./08_pairs/sampled_pairs.jsonl")
GOLD_FILE = Path("./09_manual_annotations/gold_standard.jsonl")
OUT_DIR = Path("./10_llm_annotations")
RUN2_FILE = OUT_DIR / "stability_run2.jsonl"
REPORT_FILE = OUT_DIR / "stability_report.json"

SCORE_ORDINAL = [-1.0, -0.5, 0.0, 0.5, 1.0]


def load_step10():
    """Import 10_llm_annotator_gold_eval.py (name starts with a digit)."""
    path = Path(__file__).with_name("10_llm_annotator_gold_eval.py")
    spec = importlib.util.spec_from_file_location("step10", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["step10"] = mod
    spec.loader.exec_module(mod)
    return mod


def to_ordinal(score):
    return min(range(len(SCORE_ORDINAL)), key=lambda i: abs(SCORE_ORDINAL[i] - float(score)))


def pick_sample(n):
    """The n PairIDs to re-annotate: a fixed-seed sample of what Step 10 completed."""
    run1 = {r["PairID"]: r for r in load_jsonl(str(RUN1_FILE))
            if r.get("InteractionScore") is not None}
    ids = sorted(run1)                      # sort first: dict order must not leak in
    n = min(n, len(ids))
    chosen = random.Random(SEED).sample(ids, n)
    return sorted(chosen), run1


def pair_source():
    """Raw pair text, preferred from 08_pairs so no gold labels leak into run 2."""
    src = {}
    if PAIRS_FILE.exists():
        src = {r["PairID"]: r for r in load_jsonl(str(PAIRS_FILE))}
    if GOLD_FILE.exists():
        for r in load_jsonl(str(GOLD_FILE)):
            src.setdefault(r["PairID"], r)
    return src


LABEL_FIELDS = ("InteractionScore", "InteractionLabel", "InteractionReasoning",
                "StanceLabel", "ParentStanceLabel", "Techniques",
                "AnnotatorNote", "resolved_by", "ResolvedAt")


def clean_pair(rec):
    """Strip any existing labels so run 2 starts from text only."""
    return {k: v for k, v in rec.items() if k not in LABEL_FIELDS}


# --- metrics -----------------------------------------------------------------

def kappa(a, b, weights=None):
    from sklearn.metrics import cohen_kappa_score
    return round(float(cohen_kappa_score(a, b, weights=weights)), 4)


def pct(n, t):
    return round(100.0 * n / t, 1) if t else 0.0


def jaccard(s1, s2):
    s1, s2 = set(s1 or []), set(s2 or [])
    if not s1 and not s2:
        return 1.0
    return len(s1 & s2) / len(s1 | s2)


def compute_report(ids, run1, run2):
    import numpy as np

    paired = [(run1[i], run2[i]) for i in ids if i in run1 and i in run2]
    out = {
        "metadata": {
            "n_sampled": len(ids),
            "n_compared": len(paired),
            "seed": SEED,
            "run1_source": str(RUN1_FILE),
            "run2_source": str(RUN2_FILE),
            "model": (paired[0][1].get("ModelUsed") if paired else None),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
    }

    # interaction quality
    both = [(a, b) for a, b in paired
            if a.get("InteractionScore") is not None and b.get("InteractionScore") is not None]
    if both:
        g = [to_ordinal(a["InteractionScore"]) for a, _ in both]
        l = [to_ordinal(b["InteractionScore"]) for _, b in both]
        raw_g = np.array([float(a["InteractionScore"]) for a, _ in both])
        raw_l = np.array([float(b["InteractionScore"]) for _, b in both])
        out["interaction"] = {
            "n": len(both),
            "exact_agreement_pct": pct(sum(1 for x, y in zip(g, l) if x == y), len(both)),
            "kappa_quadratic": kappa(g, l, "quadratic"),
            "kappa_unweighted": kappa(g, l),
            "mae": round(float(np.mean(np.abs(raw_g - raw_l))), 4),
        }

    # stance, child and parent
    for field, name in (("StanceLabel", "stance_child"), ("ParentStanceLabel", "stance_parent")):
        sub = [(a, b) for a, b in paired
               if a.get(field) is not None and b.get(field) is not None]
        if not sub:
            continue
        g = [int(a[field]) for a, _ in sub]
        l = [int(b[field]) for _, b in sub]
        out[name] = {
            "n": len(sub),
            "exact_agreement_pct": pct(sum(1 for x, y in zip(g, l) if x == y), len(sub)),
            "kappa_unweighted": kappa(g, l),
        }

    # both stance layers pooled — the paper says "stance labels" without
    # specifying a layer, so report the pooled figure too and let the text cite
    # whichever it means.
    pooled_g, pooled_l = [], []
    for field in ("StanceLabel", "ParentStanceLabel"):
        for a, b in paired:
            if a.get(field) is not None and b.get(field) is not None:
                pooled_g.append(int(a[field]))
                pooled_l.append(int(b[field]))
    if pooled_g:
        out["stance_pooled"] = {
            "n": len(pooled_g),
            "exact_agreement_pct": pct(sum(1 for x, y in zip(pooled_g, pooled_l) if x == y),
                                       len(pooled_g)),
            "kappa_unweighted": kappa(pooled_g, pooled_l),
        }

    # techniques
    if paired:
        ex = sum(1 for a, b in paired
                 if set(a.get("Techniques") or []) == set(b.get("Techniques") or []))
        js = [jaccard(a.get("Techniques"), b.get("Techniques")) for a, b in paired]
        out["techniques"] = {
            "n": len(paired),
            "exact_set_agreement_pct": pct(ex, len(paired)),
            "mean_jaccard": round(sum(js) / len(js), 4),
        }
    return out


def print_report(rep):
    m = rep["metadata"]
    print("\n" + "=" * 70)
    print("LLM STABILITY CHECK (Sec 4.4)")
    print("=" * 70)
    print(f"  sample n={m['n_sampled']} (seed {m['seed']}), compared={m['n_compared']}, "
          f"model={m['model']}")
    i = rep.get("interaction")
    if i:
        print(f"\n  interaction quality (n={i['n']})")
        print(f"    exact agreement       {i['exact_agreement_pct']:.1f}%"
              f"      <- paper: 93.0%")
        print(f"    quadratic-weighted k  {i['kappa_quadratic']:.4f}"
              f"      <- paper: 0.895")
        print(f"    unweighted k          {i['kappa_unweighted']:.4f}")
        print(f"    MAE                   {i['mae']:.4f}")
    for key, lbl in (("stance_child", "child stance"),
                     ("stance_parent", "parent stance"),
                     ("stance_pooled", "stance, both layers pooled")):
        s = rep.get(key)
        if s:
            note = "      <- paper: 96.5% / 0.940" if key == "stance_child" else ""
            print(f"\n  {lbl} (n={s['n']})")
            print(f"    exact agreement       {s['exact_agreement_pct']:.1f}%{note}")
            print(f"    unweighted k          {s['kappa_unweighted']:.4f}")
    t = rep.get("techniques")
    if t:
        print(f"\n  techniques (n={t['n']}), not claimed in the paper")
        print(f"    exact-set agreement   {t['exact_set_agreement_pct']:.1f}%")
        print(f"    mean Jaccard          {t['mean_jaccard']:.4f}")
    print("=" * 70)


# --- main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="LLM self-consistency check (Sec 4.4).")
    ap.add_argument("--run", action="store_true",
                    help="actually make API calls (costs money); without it this is a dry run")
    ap.add_argument("--report-only", action="store_true",
                    help="recompute metrics from an existing stability_run2.jsonl")
    ap.add_argument("-n", type=int, default=N_DEFAULT,
                    help=f"sample size (default {N_DEFAULT})")
    args = ap.parse_args()

    if not RUN1_FILE.exists():
        print(f"{RUN1_FILE} not found — run Step 10 first.")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ids, run1 = pick_sample(args.n)
    done = {}
    if RUN2_FILE.exists():
        done = {r["PairID"]: r for r in load_jsonl(str(RUN2_FILE))
                if r.get("InteractionScore") is not None}
    pending = [i for i in ids if i not in done]

    print(f"stability sample: {len(ids)} pairs (seed {SEED}) out of "
          f"{len(run1)} Step-10 annotations")
    print(f"already re-annotated: {len(done)}   pending: {len(pending)}")

    if args.report_only or (not pending and not args.run):
        if not done:
            print("\nNothing to report yet: no run-2 annotations found.")
            if not args.run:
                print("Re-run with --run to execute the check.")
            return
        rep = compute_report(ids, run1, done)
        REPORT_FILE.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport written to {REPORT_FILE}")
        print_report(rep)
        return

    if not args.run:
        print(f"\nDRY RUN. Would make {len(pending) * 4} API calls "
              f"({len(pending)} pairs x 4 tasks) against the Step-10 model.")
        print("Re-run with --run to execute. Nothing was called and nothing was written.")
        return

    step10 = load_step10()
    if not step10.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY is not set (see .env.example).")
        return

    import anthropic
    client = anthropic.Anthropic(api_key=step10.ANTHROPIC_API_KEY,
                                 base_url="https://api.anthropic.com")
    prompts = step10.load_prompts()
    video_topics = step10.load_video_topics()
    src = pair_source()

    missing = [i for i in pending if i not in src]
    if missing:
        print(f"[WARNING] {len(missing)} sampled pairs have no source text; skipping them.")
        pending = [i for i in pending if i in src]

    print(f"\nRe-annotating {len(pending)} pairs ({len(pending) * 4} API calls)...")
    for n, pid in enumerate(pending, 1):
        result = step10.annotate_pair(client, clean_pair(src[pid]), prompts, video_topics)
        result["StabilityRun"] = 2
        append_jsonl(result, str(RUN2_FILE))
        done[pid] = result
        if n % 10 == 0 or n == len(pending):
            print(f"  [{n}/{len(pending)}] {pid} — "
                  f"{'OK' if result.get('InteractionScore') is not None else 'PARTIAL'}")

    rep = compute_report(ids, run1, done)
    REPORT_FILE.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport written to {REPORT_FILE}")
    print_report(rep)


if __name__ == "__main__":
    main()
