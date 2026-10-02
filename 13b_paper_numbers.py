"""
All paper-numbers that are not already produced by 13_overview_report.py.

Outputs: 13_overview/paper_numbers.txt

"""
import csv, glob, json, os, random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from utils.jsonl_io import load_jsonl

TOPICS = ("climate", "migration"); PARTIES = ("AfD", "Linke")
STRATA = [(t, p) for t in TOPICS for p in PARTIES]
AFD_CH = {"AfD TV", "AfD-Fraktion Bundestag"}
BINS = ["Constructive", "Slight/Neutral", "Moderately Destructive", "Highly Destructive"]
C5 = ["CD", "CA", "N", "DA", "DD"]
NAME = {0: "Against", 1: "Neutral", 2: "Support"}

def c5(s):
    s = float(s)
    return "CD" if s >= 1 else "CA" if s >= 0.5 else "N" if s >= 0 else "DA" if s >= -0.5 else "DD"
def vbin(m):
    m = float(m)
    return BINS[0] if m >= 0.25 else BINS[1] if m >= -0.25 else BINS[2] if m >= -0.75 else BINS[3]
def pct(n, t): return 100.0 * n / t if t else 0.0

L = []
def w(s=""): L.append(s)
def head(n, title): w("\n" + "=" * 70); w(f"{n}. {title}"); w("=" * 70)

# Every value printed with a "<- paper:" annotation used to be checked by eye, so a
# number could drift out of step with the paper without the script noticing. chk()
# compares against the published value and makes the run fail instead.
CHECKS = []
def chk(label, got, want, tol=0.05):
    ok = got is not None and abs(float(got) - float(want)) <= tol
    CHECKS.append((ok, label, got, want))
    return ok

# loaders
def video_map():
    vm = {}; csv.field_size_limit(10 ** 7)
    with open("07_filtered/category_report.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("category") in TOPICS:
                ch = r.get("channelName", "")
                vm[r["videoId"]] = {"topic": r["category"],
                                    "party": "AfD" if ch in AFD_CH else "Linke", "year": None}
    for p in glob.glob("data_*/01_channel_videos/[Cc]ombined_videos.csv"):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                v = r.get("videoId")
                if v in vm:
                    d = (r.get("publishedAt") or "")[:4]
                    vm[v]["year"] = int(d) if d.isdigit() else None
    return vm

def merged():
    rec = {}
    for p in ["11_llm_annotations/llm_annotated_rest.jsonl",
              "10_llm_annotations/llm_annotated_subset.jsonl",
              "09_manual_annotations/gold_standard.jsonl"]:
        if Path(p).exists():
            for r in load_jsonl(p): rec[r["PairID"]] = r
    return list(rec.values())

vm = video_map(); pairs = merged()
def tp(r):
    m = vm.get(r.get("VideoID"), {}); return (m.get("topic"), m.get("party"))
def rel(r):
    a, c = r.get("ParentStanceLabel"), r.get("StanceLabel")
    if a not in (0, 1, 2) or c not in (0, 1, 2): return None
    if a == c: return "same"
    if {a, c} == {0, 2}: return "opposing"
    return "one-neutral"
def stat(rows):
    n = len(rows)
    if not n: return None
    sc = [float(r["InteractionScore"]) for r in rows if r.get("InteractionScore") is not None]
    m = sum(sc) / len(sc)
    C = pct(sum(1 for s in sc if s > 0), len(sc)); D = pct(sum(1 for s in sc if s < 0), len(sc))
    return n, m, C, D

threads = []
for path in sorted(glob.glob("12_thread_scores/thread_scores_*.jsonl")):
    vid = Path(path).stem.replace("thread_scores_", "")
    meta = vm.get(vid)
    if not meta: continue
    for r in load_jsonl(path):
        r["topic"] = meta["topic"]; r["party"] = meta["party"]; r["year"] = meta["year"]
        threads.append(r)

w("=" * 70); w("PAPER NUMBERS (supplement to overview_report.txt)")
w(f"Generated: {datetime.now(timezone.utc).isoformat()}")
w(f"pairs={len(pairs)}  threads={len(threads)}"); w("=" * 70)

# 1  Sec 3.5
head(1, "Sec 3.5  eligible-thread pool")
elig = Counter()
try:
    with open("08_pairs/sample_summary.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = r.get("stratum") or f"{r.get('category')}_{r.get('party')}"
            for key in ("available", "Available", "eligible"):
                if key in r and str(r[key]).strip().isdigit():
                    elig[k] = int(r[key]); break
except Exception as e:
    w(f"   (sample_summary.csv unavailable: {e})")
if elig:
    tot = sum(elig.values())
    for k, v in sorted(elig.items()): w(f"   {k:20} {v:6}  ({pct(v,tot):.1f}%)")
    afd = sum(v for k, v in elig.items() if "AfD" in k)
    w(f"   total eligible threads      {tot}")
    w(f"   from AfD channels           {afd}  ({pct(afd,tot):.1f}%)   <- paper: 91.7%")
    cl = [v for k, v in elig.items() if "climate" in k.lower() and "linke" in k.lower()]
    if cl: w(f"   smallest stratum (climate x Linke) {cl[0]}  ({pct(cl[0],tot):.1f}%)  <- paper: 723 / 1.8%")

# 2 Table 4
head(2, "Table 4  gold-standard label distribution (n=700)")
gold = list(load_jsonl("09_manual_annotations/gold_standard.jsonl"))
iq = Counter(c5(r["InteractionScore"]) for r in gold if r.get("InteractionScore") is not None)
for c in C5: w(f"   IQ {c:3} {iq[c]:4}  {pct(iq[c],len(gold)):5.1f}%")
st = Counter(r.get("StanceLabel") for r in gold)
for v in (2, 1, 0): w(f"   stance {NAME[v]:8} {st[v]:4}  {pct(st[v],len(gold)):5.1f}%")
tc = Counter(t for r in gold for t in set(r.get("Techniques") or []))
top = tc.most_common(1)[0]
w(f"   top technique {top[0]} {top[1]}  {pct(top[1],len(gold)):.1f}%   <- paper: Loaded_Language 332 / 47.4%")

# 3 Table 6
head(3, "Table 6  LLM vs gold  (10_llm_annotations/evaluation_report.json)")
try:
    ev = json.load(open("10_llm_annotations/evaluation_report.json", encoding="utf-8"))
    i, s, p_, t_ = ev["interaction"], ev["stance"], ev["parent_stance"], ev["techniques"]
    w(f"   IQ      quad={i['kappa_quadratic']:.3f} unweighted={i['kappa_unweighted']:.3f} "
      f"MAE={i['mae']:.3f} r={i['pearson_r']:.3f}")
    w(f"   child   kappa={s['kappa']:.3f} macroF1={s['macro_f1']:.3f} "
      f"F1={s['per_class_f1']['Against']:.3f}/{s['per_class_f1']['Neutral']:.3f}/{s['per_class_f1']['Support']:.3f}")
    w(f"   parent  kappa={p_['kappa']:.3f} macroF1={p_['macro_f1']:.3f} "
      f"F1={p_['per_class_f1']['Against']:.3f}/{p_['per_class_f1']['Neutral']:.3f}/{p_['per_class_f1']['Support']:.3f} "
      f"n={p_['n_evaluated']}")
    w(f"   prop    macroF1={t_['macro_f1']:.4f} hamming={t_['hamming_loss']:.4f}")
except Exception as e:
    w(f"   (unavailable: {e})")

# 4  Tables 7 and 8
head(4, "Tables 7 & 8  thread-quality bins")
ab = Counter(vbin(t["MeanScore"]) for t in threads if t.get("MeanScore") is not None)
N = sum(ab.values())
for b in BINS: w(f"   {b:24} {ab[b]:5}  {pct(ab[b],N):5.1f}%")
w(f"   total threads {N}")
w("")
for t_, p_ in STRATA:
    sub = [x for x in threads if x["topic"] == t_ and x["party"] == p_ and x.get("MeanScore") is not None]
    c = Counter(vbin(x["MeanScore"]) for x in sub)
    ms = sum(float(x["MeanScore"]) for x in sub) / len(sub)
    w(f"   {t_[:4]}x{p_:5} n={len(sub):4} " +
      " ".join(f"{b.split('/')[0][:4]}={pct(c[b],len(sub)):4.1f}" for b in BINS) + f"  mean={ms:+.3f}")

# 5  Table 9
head(5, "Table 9  pair-level IQ + child stance per stratum")
for t_, p_ in STRATA:
    sub = [r for r in pairs if tp(r) == (t_, p_)]
    q = Counter(c5(r["InteractionScore"]) for r in sub if r.get("InteractionScore") is not None)
    sc = Counter(r.get("StanceLabel") for r in sub)
    miss = sum(1 for r in sub if r.get("StanceLabel") not in (0, 1, 2))
    w(f"   {t_[:4]}x{p_:5} n={len(sub):5} " + " ".join(f"{k}={q[k]:4}" for k in C5) +
      f" | Ag={sc[0]:4} Ne={sc[1]:4} Su={sc[2]:4} miss={miss}")
    w(f"       stance%  Against={pct(sc[0],len(sub)):.1f} Neutral={pct(sc[1],len(sub)):.1f} Support={pct(sc[2],len(sub)):.1f}")

# 6 Table 10
head(6, "Table 10  agreement/style axis collapse (% of pairs)")
for t_, p_ in STRATA:
    sub = [r for r in pairs if tp(r) == (t_, p_) and r.get("InteractionScore") is not None]
    q = Counter(c5(r["InteractionScore"]) for r in sub); n = len(sub)
    agree = q["CA"] + q["DA"]; dis = q["CD"] + q["DD"]
    con = q["CD"] + q["CA"]; des = q["DA"] + q["DD"]
    w(f"   {t_[:4]}x{p_:5} agree={pct(agree,n):5.1f} disag={pct(dis,n):5.1f} "
      f"constr={pct(con,n):5.1f} destr={pct(des,n):5.1f} neut={pct(q['N'],n):5.1f}")

# 7  Table 11 and Table 21
head(7, "Table 11 (per stratum) & Table 16 (corpus-wide) technique prevalence")
allc = Counter(t for r in pairs for t in set(r.get("Techniques") or []))
for k, v in allc.most_common():
    w(f"   {k:38} {v:5}  {pct(v,len(pairs)):5.1f}%")
w("")
for t_, p_ in STRATA:
    sub = [r for r in pairs if tp(r) == (t_, p_)]; n = len(sub)
    c = Counter(t for r in sub for t in set(r.get("Techniques") or []))
    w(f"   {t_[:4]}x{p_:5} (n={n}): " + ", ".join(f"{k}={pct(c[k],n):.1f}%" for k, _ in allc.most_common(4)))

# 8 Table 12
head(8, "Table 12  stance relation by topic (same-stance decomposed)")
for t_ in TOPICS:
    sub = [r for r in pairs if tp(r)[0] == t_ and r.get("InteractionScore") is not None]
    w(f"   {t_.upper()}")
    for k in ("opposing", "same", "one-neutral"):
        s = stat([r for r in sub if rel(r) == k])
        if s: w(f"      {k:12} n={s[0]:5} mean={s[1]:+.3f} C/D={s[2]:.0f}/{s[3]:.0f}")
    for v in (0, 1, 2):
        s = stat([r for r in sub if r.get("ParentStanceLabel") == v and r.get("StanceLabel") == v])
        if s: w(f"        {NAME[v]}-{NAME[v]:8} n={s[0]:5} mean={s[1]:+.3f} C/D={s[2]:.0f}/{s[3]:.0f}")

# 9 Table 20
head(9, "Table 20  stance relation per party x topic")
for t_, p_ in STRATA:
    sub = [r for r in pairs if tp(r) == (t_, p_) and r.get("InteractionScore") is not None]
    w(f"   {t_} x {p_}")
    for k in ("opposing", "same", "one-neutral"):
        s = stat([r for r in sub if rel(r) == k])
        if s: w(f"      {k:12} mean={s[1]:+.3f} C/D={s[2]:.0f}/{s[3]:.0f} n={s[0]}")

# 10 Tables 13/19
head(10, "Tables 13 & 19  constructive-thread share by year")
def share(items):
    by = defaultdict(lambda: [0, 0])
    for x in items:
        if x.get("year") is None or x.get("MeanScore") is None: continue
        by[x["year"]][0] += (vbin(x["MeanScore"]) == BINS[0]); by[x["year"]][1] += 1
    return by
for t_ in TOPICS:
    b = share([x for x in threads if x["topic"] == t_])
    w(f"   {t_:9} " + "  ".join(f"{y}:{pct(c,n):.1f}%(n{n})" for y, (c, n) in sorted(b.items()) if n >= 15))
w("")
for t_, p_ in STRATA:
    b = share([x for x in threads if x["topic"] == t_ and x["party"] == p_])
    w(f"   {t_[:4]}x{p_:5} " + "  ".join(f"{y}:{pct(c,n):.1f}(n{n})" for y, (c, n) in sorted(b.items())))

# 11 Sec 5.2
head(11, "Sec 5.2  chi-square, thread-quality distribution by topic")
obs = []
for t_ in TOPICS:
    c = Counter(vbin(x["MeanScore"]) for x in threads
                if x["topic"] == t_ and x.get("MeanScore") is not None)
    obs.append([c[b] for b in BINS])
    w(f"   {t_:9} " + " ".join(f"{b.split('/')[0][:4]}={c[b]}" for b in BINS) + f"  n={sum(c.values())}")
rt = [sum(r) for r in obs]; ct = [sum(o[j] for o in obs) for j in range(4)]; g = sum(rt)
chi = sum((obs[i][j] - rt[i] * ct[j] / g) ** 2 / (rt[i] * ct[j] / g) for i in range(2) for j in range(4))
w(f"   chi2(3) = {chi:.4f}    <- paper: 5.15")
try:
    from scipy.stats import chi2_contingency
    c2, pv, dof, _ = chi2_contingency(obs, correction=False)
    w(f"   scipy: chi2={c2:.4f} dof={dof} p={pv:.4f}    <- paper: p = 0.16")
except Exception as e:
    w(f"   (scipy unavailable: {e})")

# 12  Sec 5.1
head(12, "Sec 5.1  Doubt / Fear by topic; climate skepticism")
for t_ in TOPICS:
    sub = [r for r in pairs if tp(r)[0] == t_]; n = len(sub)
    c = Counter(t for r in sub for t in set(r.get("Techniques") or []))
    w(f"   {t_:9} n={n} Doubt={pct(c['Doubt'],n):.1f}% Fear={pct(c['Appeal_to_fear-prejudice'],n):.1f}%")
for p_ in PARTIES:
    sub = [r for r in pairs if tp(r) == ("climate", p_)]
    ag = sum(1 for r in sub if r.get("StanceLabel") == 0)
    w(f"   climate x {p_:5} Against={ag}/{len(sub)} = {pct(ag,len(sub)):.1f}%")

# 13  Limitations 4
head(13, "Limitations 4  style-only recoding robustness")
for t_ in TOPICS:
    sub = [r for r in pairs if tp(r)[0] == t_ and r.get("InteractionScore") is not None]
    w(f"   {t_.upper()}")
    for k in ("opposing", "same", "one-neutral"):
        g2 = [float(r["InteractionScore"]) for r in sub if rel(r) == k]
        if not g2: continue
        style = (sum(1 for s in g2 if s > 0) - sum(1 for s in g2 if s < 0)) / len(g2)
        w(f"      {k:12} style-only mean={style:+.3f}   (original {sum(g2)/len(g2):+.3f})")

# 14 Limitations 5
head(14, "Limitations 5  sample composition by year")
byy = defaultdict(Counter)
for r in pairs:
    m = vm.get(r.get("VideoID"))
    if m and m["year"]: byy[m["year"]][m["party"]] += 1
for y in sorted(byy):
    a, l = byy[y]["AfD"], byy[y]["Linke"]; t = a + l
    if t >= 50:
        w(f"   {y}  AfD={a:5} Linke={l:5}  AfD share={pct(a,t):.1f}%  "
          f"Linke share={pct(l,t):.1f}%")
w("   <- paper: 2020 is 99% AfD, 2025 is 83% Die Linke")

# 15  Appendix annotators
head(15, "Appendix  annotator A vs Z")
try:
    A = {r["PairID"]: r for r in load_jsonl("09_manual_annotations/gold_standard_a.jsonl")}
    Z = {r["PairID"]: r for r in load_jsonl("09_manual_annotations/gold_standard_z.jsonl")}
    G = {r["PairID"]: r for r in load_jsonl("09_manual_annotations/gold_standard.jsonl")}
    ids = [p for p in G if p in A and p in Z
           and A[p].get("InteractionScore") is not None and Z[p].get("InteractionScore") is not None]
    a = [float(A[p]["InteractionScore"]) for p in ids]; z = [float(Z[p]["InteractionScore"]) for p in ids]
    w(f"   n={len(ids)}  mean A={sum(a)/len(a):+.3f}  mean Z={sum(z)/len(z):+.3f}")
    ca = Counter(c5(x) for x in a); cz = Counter(c5(x) for x in z)
    w("   " + "  ".join(f"{k}: A={ca[k]} Z={cz[k]}" for k in C5))
    ex = pct(sum(1 for x, y in zip(a, z) if x == y), len(ids))
    def style(s): return "C" if s > 0 else ("D" if s < 0 else "N")
    def relx(s): return "dis" if s in (1.0, -1.0) else ("agr" if s in (0.5, -0.5) else "neu")
    w(f"   exact={ex:.1f}%  style-axis={pct(sum(1 for x,y in zip(a,z) if style(x)==style(y)),len(ids)):.1f}%"
      f"  relation-axis={pct(sum(1 for x,y in zip(a,z) if relx(x)==relx(y)),len(ids)):.1f}%")
    dc = Counter((c5(x), c5(y)) for x, y in zip(a, z) if x != y)
    w("   top disagreements A->Z: " + ", ".join(f"{k[0]}->{k[1]}:{v}" for k, v in dc.most_common(3)))
    # A-minus-Z offset, split by topic and by party. The paper claims the offset
    # is a uniform strictness threshold, not a content-linked bias, so the two
    # halves of each split must not differ significantly.
    def gap(field, value):
        return [float(A[p]["InteractionScore"]) - float(Z[p]["InteractionScore"])
                for p in ids if G[p].get(field) == value]
    for field, values, paper_p in (("category", TOPICS, "0.44"), ("party", PARTIES, "0.15")):
        gs = [gap(field, v) for v in values]
        for v, d in zip(values, gs):
            w(f"   gap {v:9} = {sum(d)/len(d):+.4f} (n={len(d)})")
        try:
            from scipy.stats import ttest_ind
            t_stat, pv = ttest_ind(gs[0], gs[1], equal_var=False)
            w(f"   offset stable across {field}: Welch t={t_stat:.3f} p={pv:.4f}"
              f"    <- paper: p = {paper_p}")
        except Exception as e:
            w(f"   (scipy unavailable for {field} test: {e})")
    ta = [len(A[p].get("Techniques") or []) for p in ids]
    tz = [len(Z[p].get("Techniques") or []) for p in ids]
    w(f"   techniques per pair: A={sum(ta)/len(ta):.2f}  Z={sum(tz)/len(tz):.2f}")
except Exception as e:
    w(f"   (unavailable: {e})")

# 16  Appendix topic validation
head(16, "Appendix  topic-assignment validation")
TV = Path("topic_validation")
try:
    krows = list(csv.DictReader((TV / "topic_check_key.csv").open(encoding="utf-8")))
    key = {r["id"]: r["assigned_category"] for r in krows}
    vid_of = {r["id"]: r["videoId"] for r in krows}
    rows = []
    for r in csv.DictReader((TV / "topic_check_sheet.csv").open(encoding="utf-8-sig")):
        rows.append((r["id"], (r.get("judgment") or "").strip().upper() or "N", key[r["id"]]))
    want = {"climate": "C", "migration": "M"}
    asg = [x for x in rows if x[2] in want]
    ok = sum(1 for x in asg if x[1] == want[x[2]] or x[1] == "B")
    w(f"   assigned videos n={len(asg)}  on-topic={ok} = {pct(ok,len(asg)):.1f}%   <- paper: 75.0%")
    for cat in TOPICS:
        s = [x for x in asg if x[2] == cat]
        k = sum(1 for x in s if x[1] == want[cat] or x[1] == "B")
        w(f"     {cat:10} {k}/{len(s)} = {pct(k,len(s)):.1f}%")
    oth = [x for x in rows if x[2] == "other"]
    miss = sum(1 for x in oth if x[1] in ("C", "M", "B"))
    w(f"   unassigned videos n={len(oth)}  actually on-topic={miss}")

    # Off-topic impact on the stance layer (Appendix): pairs drawn from the same
    # 75 judged videos, split by whether the judge found the video on-topic.
    # The paper argues off-topic videos inflate Neutral but contribute no
    # opposing-stance pairs.
    judged = {vid_of[i]: (j in ("C", "M", "B")) for i, j, _ in rows}
    grp = {True: [], False: []}
    for r in pairs:
        v = r.get("VideoID")
        if v in judged:
            grp[judged[v]].append(r)
    w(f"   pairs from the {len(judged)} judged videos: {sum(len(g) for g in grp.values())}")
    n_opp_total = 0
    for on_topic in (True, False):
        g = grp[on_topic]
        if not g: continue
        neu = pct(sum(1 for r in g if r.get("StanceLabel") == 1), len(g))
        opp = sum(1 for r in g if rel(r) == "opposing")
        n_opp_total += opp
        lbl = "on-topic (C/M/B)" if on_topic else "off-topic (N)"
        w(f"     {lbl:18} n={len(g):4}  Neutral child={neu:.1f}%  opposing pairs={opp}")
    w(f"   opposing-stance pairs from these videos: {n_opp_total}"
      f"    <- paper: 27, none from off-topic videos")
except Exception as e:
    w(f"   (topic_validation sheet unavailable: {e})")

# 17  Ethics, party bias
head(17, "Ethics  party-aware human vs party-blind LLM labels")
try:
    G = {r["PairID"]: r for r in load_jsonl("09_manual_annotations/gold_standard.jsonl")}
    M = {r["PairID"]: r for r in load_jsonl("10_llm_annotations/llm_annotated_subset.jsonl")}
    ids = [p for p in G if p in M
           and G[p].get("InteractionScore") is not None and M[p].get("InteractionScore") is not None]
    # Confirmation bias would make humans HARSHER than the party-blind LLM on the
    # disfavored party, i.e. human-minus-LLM negative on the AfD strata.
    def diff(p_):
        return [float(G[p]["InteractionScore"]) - float(M[p]["InteractionScore"])
                for p in ids if G[p].get("party") == p_]
    ds = [diff(p_) for p_ in PARTIES]
    for p_, d in zip(PARTIES, ds):
        w(f"   mean human-minus-LLM {p_:6} = {sum(d)/len(d):+.4f} (n={len(d)})")
    m0, m1 = sum(ds[0]) / len(ds[0]), sum(ds[1]) / len(ds[1])
    w(f"   difference = {abs(m0-m1):.4f}    <- paper: 0.063 on a [-1,+1] scale")
    try:
        from scipy.stats import ttest_ind
        t_stat, pv = ttest_ind(ds[0], ds[1], equal_var=False)
        w(f"   Welch t={t_stat:.3f} p={pv:.4f}    <- paper: t = 1.19, p = 0.24")
    except Exception as e:
        w(f"   (scipy unavailable: {e})")
    afd = [p for p in ids if G[p].get("party") == "AfD"]
    for src, lbl, paper in ((M, "party-blind LLM", "67.4"), (G, "human annotators", "58.3")):
        d = pct(sum(1 for p in afd if float(src[p]["InteractionScore"]) < 0), len(afd))
        w(f"   destructive share of AfD pairs, {lbl:16} = {d:.1f}%   <- paper: {paper}%")
except Exception as e:
    w(f"   (unavailable: {e})")

# 18 Table 2 and Sec 4.3 residual values
head(18, "Table 2 (sampling yield) & Sec 4.3 adjudication split")
# Table 2's Clean Pairs column is POST-deduplication, whereas sample_summary.csv
# records the pre-dedup yield. 
try:
    pre = {}
    with open("08_pairs/sample_summary.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pre[r["stratum"]] = (int(r["sampled"]), int(r["total_comments"]),
                                 int(r["total_pairs"]))
    post = Counter(f"{t}_{p}" for t, p in (tp(r) for r in pairs) if t)
    tot_thr = tot_com = tot_pre = tot_post = 0
    w("   stratum          threads  comments  pairs(pre-dedup)  pairs(clean)")
    for t_, p_ in STRATA:
        k = f"{t_}_{p_}"
        thr, com, prep = pre.get(k, (0, 0, 0))
        cl = post.get(k, 0)
        tot_thr += thr; tot_com += com; tot_pre += prep; tot_post += cl
        w(f"   {k:16} {thr:7} {com:9} {prep:17} {cl:13}")
    w(f"   {'TOTAL':16} {tot_thr:7} {tot_com:9} {tot_pre:17} {tot_post:13}")
    w(f"   duplicates removed: {tot_pre - tot_post}"
      f"    <- paper: 7,299 pairs, 22 duplicates, 7,277 clean")
    w(f"   <- paper Table 2: threads 2,000  comments 10,210  clean pairs 7,277")
except Exception as e:
    w(f"   (sample_summary unavailable: {e})")

# Sec 4.3: how the 700 gold pairs were resolved
try:
    g = load_jsonl("09_manual_annotations/gold_standard.jsonl")
    by = Counter(r.get("resolved_by") for r in g)
    n = len(g)
    w(f"   gold pairs = {n}")
    for k, lbl, paper in (("auto", "identical on all three tasks", "75 / 10.7%"),
                          ("manual", "adjudicated by discussion", "625 / 89.3%")):
        w(f"   {lbl:30} {by.get(k,0):4}  {pct(by.get(k,0),n):.1f}%   <- paper: {paper}")
except Exception as e:
    w(f"   (gold standard unavailable: {e})")

# 19 Sec 4.4 stability
head(19, "Sec 4.4  LLM stability (self-consistency) check")
SR = Path("10_llm_annotations/stability_report.json")
if SR.exists():
    s = json.loads(SR.read_text(encoding="utf-8"))
    m = s.get("metadata", {})
    w(f"   sample n={m.get('n_sampled')} (seed {m.get('seed')})  compared={m.get('n_compared')}"
      f"  model={m.get('model')}")
    # The figures as printed in Sec 4.4. Kept here
    PAPER = {"interaction_exact": "93.0%", "interaction_kappa": "0.906",
             "stance_child": "96.0% / 0.930"}
    i = s.get("interaction") or {}
    if i:
        w(f"   interaction  exact={i['exact_agreement_pct']:.1f}%"
          f"   <- paper: {PAPER['interaction_exact']}")
        w(f"                quad-weighted kappa={i['kappa_quadratic']:.4f}"
          f"   <- paper: {PAPER['interaction_kappa']}")
    for k, lbl in (("stance_child", "stance (child)"),
                   ("stance_parent", "stance (parent)"),
                   ("stance_pooled", "stance (pooled)")):
        d = s.get(k)
        if d:
            note = f"   <- paper: {PAPER[k]}" if k in PAPER else ""
            w(f"   {lbl:16} exact={d['exact_agreement_pct']:.1f}% "
              f"kappa={d['kappa_unweighted']:.4f}{note}")
else:
    w("   not run: 10_llm_annotations/stability_report.json absent.")
    w("   Regenerate with:  python 10b_stability_check.py --run")
    w("   (requires ANTHROPIC_API_KEY; ~800 API calls for the 200-pair sample)")

# 20  Sec 5.1 same-stance decomposition 
head(20, "Sec 5.1  same-stance decomposition (NN masking; AfD severity vs volume)")

try:
    for t_ in TOPICS:
        sub = [r for r in pairs if tp(r)[0] == t_ and rel(r) == "same"
               and r.get("InteractionScore") is not None]
        nn = [r for r in sub if r.get("StanceLabel") == 1]
        wo = [r for r in sub if r.get("StanceLabel") != 1]
        f = lambda g: sum(float(r["InteractionScore"]) for r in g) / len(g)
        w(f"   {t_:9} same={f(sub):+.3f} (n={len(sub)})  NN={f(nn):+.3f} (n={len(nn)})  "
          f"same without NN={f(wo):+.3f}")
    w("   <- paper: excluding NN the same-stance mean falls to -0.29 climate / -0.38 migration")

    w("")
    cells = {0: "AA", 1: "NN", 2: "SS"}
    share, sev = {}, {}
    for p_ in PARTIES:
        sub = [r for r in pairs if tp(r) == ("climate", p_) and rel(r) == "same"
               and r.get("InteractionScore") is not None]
        n = len(sub)
        share[p_] = {c: sum(1 for r in sub if r.get("StanceLabel") == c) / n for c in cells}
        sev[p_] = {}
        for c in cells:
            g = [float(r["InteractionScore"]) for r in sub if r.get("StanceLabel") == c]
            sev[p_][c] = sum(g) / len(g) if g else 0.0
        w(f"   climate x {p_:5} same-stance n={n}  " +
          "  ".join(f"{cells[c]}: {share[p_][c]*100:.1f}% @ {sev[p_][c]:+.3f}" for c in cells))
    mA = sum(share["AfD"][c] * sev["AfD"][c] for c in cells)
    mL = sum(share["Linke"][c] * sev["Linke"][c] for c in cells)
    comp = sum(share["AfD"][c] * sev["Linke"][c] for c in cells)
    sevr = sum(share["Linke"][c] * sev["AfD"][c] for c in cells)
    gap = mA - mL
    w(f"   gap AfD-Linke = {gap:+.3f}   composition explains {(comp-mL)/gap*100:.0f}%,"
      f" severity explains {(sevr-mL)/gap*100:.0f}%")
    w(f"   <- paper: Against-Against and Neutral-Neutral are both harsher on AfD;"
      f" NN alone -0.28 vs -0.05")


    w("")
    for t_ in TOPICS:
        cellmeans = {}
        for p_ in PARTIES:
            for c in cells:
                g = [float(r["InteractionScore"]) for r in pairs
                     if tp(r) == (t_, p_) and r.get("ParentStanceLabel") == c
                     and r.get("StanceLabel") == c and r.get("InteractionScore") is not None]
                cellmeans[(p_, c)] = (sum(g) / len(g), len(g)) if g else (None, 0)
        for c in cells:
            (a_, na), (l_, nl) = cellmeans[("AfD", c)], cellmeans[("Linke", c)]
            if a_ is None or l_ is None:
                continue
            harsher = a_ < l_
            w(f"   {t_:9} {cells[c]}  AfD={a_:+.3f} (n={na:4})  Linke={l_:+.3f} (n={nl:4})"
              f"   harsher on AfD: {'yes' if harsher else 'NO'}")

            if cells[c] in ("AA", "NN"):
                CHECKS.append((harsher, f"Sec 5.1 {t_} {cells[c]} harsher on AfD",
                               f"{a_:+.3f} vs {l_:+.3f}", "AfD lower"))
    w("   <- paper names only Against-Against and Neutral-Neutral here;"
      " Support-Support is the exception and is deliberately not claimed")

    # Sec 5.1 asserts that the climate/migration OPPOSING means differ significantly.
    # The individual means are not distinguishable from zero, so the inferential
    # weight sits on this contrast, not on either point estimate.
    w("")
    opp = {}
    for t_ in TOPICS:
        opp[t_] = [float(r["InteractionScore"]) for r in pairs
                   if tp(r)[0] == t_ and rel(r) == "opposing"
                   and r.get("InteractionScore") is not None]
    import statistics as _st
    for t_, v in opp.items():
        m = _st.mean(v); se = _st.stdev(v) / len(v) ** 0.5
        w(f"   {t_:9} opposing mean={m:+.3f} n={len(v)} se={se:.4f}"
          f"  95% CI [{m-1.96*se:+.3f},{m+1.96*se:+.3f}]"
          f"  excludes 0: {abs(m) > 1.96*se}")
    try:
        from scipy.stats import ttest_ind
        t_stat, pv = ttest_ind(opp["climate"], opp["migration"], equal_var=False)
        w(f"   climate vs migration opposing: Welch t={t_stat:.3f} p={pv:.4f}"
          f"    <- paper: t = 2.28, p = 0.02")
    except Exception as e:
        w(f"   (scipy unavailable: {e})")
except Exception as e:
    w(f"   (unavailable: {e})")

# 21 Sec 3.1 collection counts
head(21, "Sec 3.1  collection counts (counted from the raw stage outputs)")
vid = {}
for coll, party in (("data_a_b", "AfD"), ("data_c_d", "Linke")):
    p = Path(coll) / "01_channel_videos" / "combined_videos.csv"
    if not p.exists():
        w(f"   {p}: ABSENT"); continue
    with open(p, encoding="utf-8") as f:
        vid[party] = {r["videoId"] for r in csv.DictReader(f)}
    w(f"   {party:5} videos = {len(vid[party]):6}")
if len(vid) == 2:
    tot = len(vid["AfD"]) + len(vid["Linke"])
    w(f"   total videos = {tot}    <- paper: 14,280 (10,856 AfD; 3,424 Die Linke)")
    chk("Sec 3.1 videos total", tot, 14280, 0)
    chk("Sec 3.1 videos AfD", len(vid["AfD"]), 10856, 0)
    chk("Sec 3.1 videos Linke", len(vid["Linke"]), 3424, 0)

# The comment count walks every scraped file
if os.environ.get("SKIP_SLOW_CHECKS"):
    w("   comments: skipped (SKIP_SLOW_CHECKS set)")
else:
    nc = 0
    for coll in ("data_a_b", "data_c_d"):
        for fp in glob.glob(os.path.join(coll, "02_raw_scraped", "comments_*.jsonl")):
            with open(fp, encoding="utf-8") as f:
                nc += sum(1 for line in f if line.strip())
    w(f"   total comments = {nc}    <- paper: 4,638,722")
    chk("Sec 3.1 comments total", nc, 4638722, 0)

tpath = Path("06_bertopic_output/video_topics.csv")
if tpath.exists():
    with open(tpath, encoding="utf-8") as f:
        ntr = sum(1 for _ in csv.DictReader(f))
    w(f"   transcripts modeled = {ntr}    <- paper: 12,621")
    chk("Sec 3.1 transcripts", ntr, 12621, 0)

# 22 Sec 3.2 pseudonymization
head(22, "Sec 3.2  pseudonymized author identities per party namespace")
maps = {"AfD": Path("data_a_b/03_anonymized/username_map.json"),
        "Linke": Path("data_c_d/03_anonymized/username_map.json")}
if all(p.exists() for p in maps.values()):
    ns = {k: set(json.load(open(p, encoding="utf-8"))) for k, p in maps.items()}
    a, l = len(ns["AfD"]), len(ns["Linke"])
    both = len(ns["AfD"] & ns["Linke"])
    w(f"   AfD namespace   = {a}")
    w(f"   Linke namespace = {l}")
    w(f"   sum (author-party pairs) = {a + l}    <- paper: 476,330 / 386,213 / 90,117")
    w(f"   display names in both namespaces = {both}  ->  distinct names = {len(ns['AfD'] | ns['Linke'])}")
    chk("Sec 3.2 AfD namespace", a, 386213, 0)
    chk("Sec 3.2 Linke namespace", l, 90117, 0)
    chk("Sec 3.2 total identities", a + l, 476330, 0)

# 23 Table 14 corpus composition
head(23, "Table 14  topic-relevant composition (report arithmetic + paper totals)")
sp = Path("08_pairs/statistics_report.csv")
if sp.exists():
    with open(sp, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    COLS = ("videos", "comments", "threads", "pairs")
    chan = [r for r in rows if r["channel"] not in ("SUBTOTAL", "")]
    subs = [r for r in rows if r["channel"] == "SUBTOTAL"]
    total = [r for r in rows if r["category"] == "TOTAL"]
    # each subtotal must equal the sum of its own channels, and the total the subtotals
    for s in subs:
        mine = [r for r in chan if r["category"] == s["category"] and r["party"] == s["party"]]
        for c in COLS:
            got = sum(int(r[c]) for r in mine)
            chk(f"Table 14 subtotal {s['category'][:4]}x{s['party']} {c}", got, int(s[c]), 0)
    if total:
        for c in COLS:
            got = sum(int(r[c]) for r in subs)
            w(f"   total {c:9} = {got:8}  (report says {int(total[0][c]):8})")
            chk(f"Table 14 total {c}", got, int(total[0][c]), 0)
        for c, want in (("videos", 1143), ("comments", 526259), ("threads", 385320), ("pairs", 125967)):
            chk(f"Sec 3.5 {c}", int(total[0][c]), want, 0)
    w("   <- paper Table 14 / Sec 3.5: 1,143 videos, 526,259 comments, 385,320 threads, 125,967 pairs")

# 24 Table 15 annotation coverage
head(24, "Table 15  annotation coverage per stratum (pairs = gold + LLM)")
gold = load_jsonl("09_manual_annotations/gold_standard.jsonl") \
    if Path("09_manual_annotations/gold_standard.jsonl").exists() else []
gid = {r["PairID"] for r in gold}
tg = tl = 0
for t_, p_ in STRATA:
    sub = [r for r in pairs if tp(r) == (t_, p_)]
    g = sum(1 for r in sub if r["PairID"] in gid)
    w(f"   {t_[:4]}x{p_:5} pairs={len(sub):5} gold={g:4} llm={len(sub)-g:5}")
    chk(f"Table 15 gold {t_[:4]}x{p_}", g, 175, 0)
    tg += g; tl += len(sub) - g
w(f"   TOTAL      pairs={len(pairs):5} gold={tg:4} llm={tl:5}    <- paper: 7,277 / 700 / 6,577")
chk("Table 15 gold total", tg, 700, 0)
chk("Table 15 llm total", tl, 6577, 0)

# 25 Sec 4.4 and Table 21 inter-annotator agreement
head(25, "Sec 4.4 & Table 21  inter-annotator agreement (recomputed from A and Z)")


def _kappa(x, y, quad=False):
    cats = sorted(set(x) | set(y)); k = len(cats); n = len(x)
    ix = {c: i for i, c in enumerate(cats)}
    O = [[0.0] * k for _ in range(k)]
    for a_, b_ in zip(x, y): O[ix[a_]][ix[b_]] += 1
    rx = [sum(r) for r in O]; ry = [sum(O[i][j] for i in range(k)) for j in range(k)]
    E = [[rx[i] * ry[j] / n for j in range(k)] for i in range(k)]
    W = ([[((i - j) / (k - 1)) ** 2 for j in range(k)] for i in range(k)] if quad
         else [[0.0 if i == j else 1.0 for j in range(k)] for i in range(k)])
    num = sum(W[i][j] * O[i][j] for i in range(k) for j in range(k))
    den = sum(W[i][j] * E[i][j] for i in range(k) for j in range(k))
    return 1 - num / den if den else float("nan")


def _alpha(ps):
    """Krippendorff's alpha, nominal metric, two coders, no missing values."""
    cnt = Counter()
    for a_, b_ in ps: cnt[a_] += 1; cnt[b_] += 1
    n = 2 * len(ps)
    Do = sum(1 for a_, b_ in ps if a_ != b_) / len(ps)
    De = 1 - sum(c * (c - 1) for c in cnt.values()) / (n * (n - 1))
    return 1 - Do / De if De else float("nan")


pa, pz = (Path("09_manual_annotations/gold_standard_a.jsonl"),
          Path("09_manual_annotations/gold_standard_z.jsonl"))
if pa.exists() and pz.exists():
    A = {r["PairID"]: r for r in load_jsonl(str(pa))}
    Z = {r["PairID"]: r for r in load_jsonl(str(pz))}
    ids = sorted(set(A) & set(Z))
    w(f"   overlapping pairs = {len(ids)}")

    iq = [(float(A[i]["InteractionScore"]), float(Z[i]["InteractionScore"])) for i in ids
          if A[i].get("InteractionScore") is not None and Z[i].get("InteractionScore") is not None]
    x = [p[0] for p in iq]; y = [p[1] for p in iq]
    ex = 100 * sum(1 for a_, b_ in iq if a_ == b_) / len(iq)
    # printed to 4 dp
    w(f"   IQ            exact={ex:.1f}%  kappa={_kappa(x, y):.4f}  "
      f"quad={_kappa(x, y, True):.4f}  alpha={_alpha(iq):.4f}")
    w(f"                 <- paper: 56.9% / 0.456 / 0.494 / 0.453")
    chk("Sec 4.4 IQ exact", ex, 56.9, 0.06)
    chk("Sec 4.4 IQ kappa", _kappa(x, y), 0.456, 0.001)
    chk("Sec 4.4 IQ quad kappa", _kappa(x, y, True), 0.494, 0.001)
    chk("Table 21 IQ alpha", _alpha(iq), 0.453, 0.001)

    for nm, fld, wex, wk, wa in (("stance parent", "ParentStanceLabel", 87.0, 0.666, 0.665),
                                 ("stance child", "StanceLabel", 87.4, 0.640, 0.639)):
        p2 = [(A[i].get(fld), Z[i].get(fld)) for i in ids]
        p2 = [(a_, b_) for a_, b_ in p2 if a_ is not None and b_ is not None]
        x2 = [p[0] for p in p2]; y2 = [p[1] for p in p2]
        e2 = 100 * sum(1 for a_, b_ in p2 if a_ == b_) / len(p2)
        w(f"   {nm:13} exact={e2:.1f}%  kappa={_kappa(x2, y2):.4f}  alpha={_alpha(p2):.4f}"
          f"    <- paper: {wex}% / {wk} / {wa}")
        chk(f"Sec 4.4 {nm} exact", e2, wex, 0.06)
        chk(f"Sec 4.4 {nm} kappa", _kappa(x2, y2), wk, 0.001)
        chk(f"Table 21 {nm} alpha", _alpha(p2), wa, 0.001)

    def _tset(r):
        return frozenset(str(t).strip() for t in (r.get("Techniques") or []) if str(t).strip())

    js, f1s, exs = [], [], 0
    for i in ids:
        sa, sz = _tset(A[i]), _tset(Z[i])
        exs += (sa == sz)
        u = len(sa | sz); inter = len(sa & sz)
        js.append(1.0 if u == 0 else inter / u)
        if not sa and not sz: f1s.append(1.0)
        elif inter == 0: f1s.append(0.0)
        else:
            pr, rc = inter / len(sz), inter / len(sa)
            f1s.append(2 * pr * rc / (pr + rc))
    mj, mf, pe = sum(js) / len(js), sum(f1s) / len(f1s), 100 * exs / len(ids)
    w(f"   propaganda    exact-set={pe:.1f}%  mean Jaccard={mj:.4f}  mean F1={mf:.4f}"
      f"    <- paper: 19.3% / 0.335 / 0.392")
    chk("Table 21 propaganda exact-set", pe, 19.3, 0.06)
    chk("Sec 4.4 propaganda Jaccard", mj, 0.335, 0.001)
    chk("Sec 4.4 propaganda F1", mf, 0.392, 0.001)

    # Appendix prose names the three largest per-technique divergences between A and Z.
    ca = Counter(t for i in ids for t in _tset(A[i]))
    cz = Counter(t for i in ids for t in _tset(Z[i]))
    top3 = sorted(set(ca) | set(cz), key=lambda t: -abs(cz[t] - ca[t]))[:3]
    w("   largest A/Z technique divergences: "
      + ", ".join(f"{t}({cz[t]-ca[t]:+})" for t in top3))
    w("                 <- paper: Loaded_Language and Causal_Oversimplification (Z), Doubt (A)")
    CHECKS.append((set(top3) == {"Loaded_Language", "Causal_Oversimplification", "Doubt"},
                   "Table 22 prose: three largest A/Z divergences", sorted(top3),
                   "Loaded_Language, Causal_Oversimplification, Doubt"))

# 26 full stance cell matrix
head(26, "Sec 5.1  all nine parent->child stance cells per topic")
# Sec 5.1 calls Against-Against the most destructive configuration reported. The
# full decomposition is printed so that claim stays checkable
for t_ in TOPICS:
    cells = []
    for a_ in (0, 1, 2):
        for c_ in (0, 1, 2):
            g = [float(r["InteractionScore"]) for r in pairs
                 if tp(r)[0] == t_ and r.get("ParentStanceLabel") == a_
                 and r.get("StanceLabel") == c_ and r.get("InteractionScore") is not None]
            if g: cells.append((NAME[a_][0] + "->" + NAME[c_][0], sum(g) / len(g), len(g)))
    cells.sort(key=lambda z: z[1])
    w(f"   {t_.upper()}  (most destructive first)")
    for nm, m, n in cells:
        w(f"      {nm:8} mean={m:+.3f}  n={n:5}")
    w(f"      most destructive cell: {cells[0][0]}  (A->A is {'' if cells[0][0]=='A->A' else 'NOT '}the minimum)")

# verdict 
w("\n" + "=" * 70)
w("SELF-CHECK")
w("=" * 70)
bad = [c for c in CHECKS if not c[0]]
for ok, label, got, want in CHECKS:
    if not ok: w(f"   FAIL  {label}: got {got}, paper says {want}")
w(f"   {len(CHECKS) - len(bad)}/{len(CHECKS)} checks passed")
if bad:
    w("   *** the paper and the data disagree; fix one of them ***")

Path("13_overview").mkdir(exist_ok=True)
Path("13_overview/paper_numbers.txt").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
raise SystemExit(1 if bad else 0)
