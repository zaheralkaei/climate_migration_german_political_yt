# Climate and Migration on German Political YouTube: A Corpus for Stance, Propaganda, and Divisiveness Annotation

Supporting code and data for the resource paper. This repository contains the end-to-end pipeline used to **build and annotate the corpus** of German-language YouTube comment pairs from the channels of two ideologically opposed parties (AfD and Die Linke) on two contested policy domains (climate and migration), together with the scripts that reproduce the numbers reported in the paper. 

The pipeline is organized as numbered steps that run in sequence, from data collection through the three-task annotation (interaction quality, stance, propaganda) and the descriptive corpus statistics. 

---

## Repository Structure

```
.
├── 01_channel_enumerator.py       # Step 01 – discover channel video IDs
├── 02_german_scraper.py           # Step 02 – scrape comments + transcripts via YouTube API
├── 03_anonymizer.py               # Step 03 – pseudonymize usernames (User_00001, …)
├── 03b_mention_scrub.py           # Step 03b – repair @-mentions Step 03 missed (runs after Step 11)
├── 04_username_fixer.py           # Step 04 – normalize @-mention / double-@@ artifacts
├── 05_relation_builder.py         # Step 05 – reconstruct parent–child reply pairs
├── 06_topic_filter.py             # Step 06 – BERTopic topic modeling on transcripts
├── 07_topic_mapper.py             # Step 07 – map videos to climate / migration
├── 08_pair_creator.py             # Step 08 – stratified sampling (500 threads / stratum, seed 42)
├── 09_annotation_tool.py          # Step 09 – Streamlit UI for manual annotation (two annotators)
├── iaa_analysis.py                # inter-annotator agreement -> 09_manual_annotations/iaa_results.json
├── conflict_resolver.py           # Streamlit UI to reconcile A/Z labels -> gold_standard.jsonl
├── 10_llm_annotator_gold_eval.py  # Step 10 – LLM annotates the 700 gold pairs + LLM-vs-gold evaluation
├── 10b_stability_check.py         # Step 10b – LLM self-consistency re-run (Sec 4.4); needs API access
├── 11_llm_annotator_rest.py       # Step 11 – LLM annotates the remaining 6,577 pairs
├── 11_dedup_annotations.py        # retry/deduplicate incomplete Step 11 annotations
├── 12_thread_scores.py            # Step 12 – aggregate pair scores to thread level + quality bins
├── 13_overview_report.py          # Step 13 – corpus statistics report
├── 13b_paper_numbers.py           # supplement: reproduces paper numbers not in Step 13
├── prompts/                       # annotation prompts (interaction quality, stance, techniques)
├── topic_validation/              # blind topic-assignment check: sheet, key, results (read by 13b §16)
├── utils/                         # shared helpers (JSONL I/O, API wrappers)
├── data_a_b/                      # AfD channels: video metadata (01_channel_videos/) + step 02–05 outputs
├── data_c_d/                      # Die Linke channels: video metadata + step 02–05 outputs
├── requirements.txt
└── LICENSE                        # CC BY-NC 4.0 (data) + MIT (code)
```

Output directories (`06_bertopic_output/`, `07_filtered/`, `08_pairs/`, `09_manual_annotations/`, `10_llm_annotations/`, `11_llm_annotations/`, `12_thread_scores/`, `13_overview/`) are created automatically when each step runs.

---

## Reproducing the paper's numbers

```bash
python 13_overview_report.py     # -> 13_overview/overview_report.txt (+ .json)
python 13b_paper_numbers.py      # -> 13_overview/paper_numbers.txt
```

### Tables and figures

| Paper item | Content | Reproduced by |
|---|---|---|
| Table 1 | BERTopic categories / keywords | `06_bertopic_output/topic_overview.csv`, `mapping.txt` |
| Table 2 | Stratified sampling design and yield | `paper_numbers.txt` §18 — the table's *Clean Pairs* column is post-deduplication, while `overview_report.txt` §2 reports the pre-dedup yield (7,299) |
| Table 3 | Interaction-quality definitions | `prompts/` (definitional) |
| Table 4 | Gold-standard label distribution | `paper_numbers.txt` §2 |
| Table 5 | Representative example pairs | `09_manual_annotations/gold_standard.jsonl` |
| Table 6 | LLM-vs-gold agreement | `10_llm_annotations/evaluation_report.json` (Step 10) |
| Table 7 | Thread-quality bins, overall | `paper_numbers.txt` §4 |
| Table 8 | Thread bins + mean score per stratum | `paper_numbers.txt` §4; bins also `overview_report.txt` §5 |
| Table 9 | 5-class IQ + child stance per stratum | `paper_numbers.txt` §5; also `overview_report.txt` §4 |
| Table 10 | Relation / style axis collapse | `paper_numbers.txt` §6 |
| Table 11 | Technique prevalence per stratum | `paper_numbers.txt` §7; also `overview_report.txt` §4 |
| Table 12 | Stance relation by topic, same-stance decomposed | `paper_numbers.txt` §8 |
| Table 13 | Constructive-thread share by year and topic | `paper_numbers.txt` §10 |
| Table 14 | Corpus composition by channel | `overview_report.txt` §1 (`08_pairs/statistics_report.csv`) |
| Table 15 | Annotation coverage by stratum | `overview_report.txt` §3 |
| Table 16 | Most-frequent techniques, corpus-wide | `paper_numbers.txt` §7; also `overview_report.txt` §4b |
| Figure 1 | IQ distribution by party × topic | |
| Table 17 | Stance definitions | `prompts/` |
| Table 18 | Propaganda technique definitions | `prompts/` |
| Table 19 | Constructive-thread share by year and stratum | `paper_numbers.txt` §10 |
| Table 20 | Stance relation per party × topic | `paper_numbers.txt` §9 |
| Table 21 | Inter-annotator agreement summary | `iaa_analysis.py` → `09_manual_annotations/iaa_results.json` |
| Table 22 | (a) A/Z confusion matrix; (b) per-label LLM *F₁* | `iaa_results.json` (a); `evaluation_report.json` (b) |

### Values reported in the paper

| Paper location | Content | Reproduced by |
|---|---|---|
| Sec 3.1 | Raw collection totals (videos, comments, transcripts, authors) | Steps 01–03 outputs — **not shipped**, see Known gaps |
| Sec 3.4 | 52 topics + outlier class | `06_bertopic_output/topic_overview.csv` |
| Sec 3.4 | Blind topic check (75.0% on-topic) | `paper_numbers.txt` §16 |
| Sec 3.5 | Eligible-thread pool, 91.7% AfD, smallest stratum 723 | `paper_numbers.txt` §1 |
| Sec 4.3 | Pre-adjudication agreement (56.9%, κ, α, Jaccard) | `iaa_results.json` |
| Sec 4.3 | Adjudication split (75 identical / 625 discussed) | `paper_numbers.txt` §18 |
| Sec 4.4 | 200-pair stability check (93.0%, κ = 0.906; 96.0%, κ = 0.930) | `10b_stability_check.py --run` → `paper_numbers.txt` §19 |
| Sec 5.1 | Doubt / fear appeals by topic; climate skepticism | `paper_numbers.txt` §12 |
| Sec 5.1 | Stance-relation means and the climate finding | `paper_numbers.txt` §8, §9 |
| Sec 5.1 | Same-stance decomposition: NN masking (−0.29 / −0.38), AfD severity vs volume (−0.28 vs −0.05), and the climate-vs-migration opposing contrast (Welch *t* = 2.28, *p* = 0.02) | `paper_numbers.txt` §20 |
| Sec 5.2 | χ²(3) = 5.15, p = 0.16 | `paper_numbers.txt` §11 |
| Limitations 4 | Style-only recoding robustness | `paper_numbers.txt` §13 |
| Limitations 5 | Sample composition by year | `paper_numbers.txt` §14 |
| Appendix (IAA) | A/Z strictness offset and its stability tests | `paper_numbers.txt` §15 |
| Appendix (topic) | Off-topic impact on the stance layer | `paper_numbers.txt` §16 |
| Ethics | Party-aware human vs party-blind LLM comparison | `paper_numbers.txt` §17 |

### The stability check (Sec 4.4)

`10b_stability_check.py` re-annotates a fixed-seed 200-pair sample of the Step-10
output through the *same* pipeline and measures run-1 vs run-2 agreement. 

```bash
python 10b_stability_check.py              # dry run: prints the plan, calls nothing
python 10b_stability_check.py --run        # ~800 calls for the 200-pair sample
python 10b_stability_check.py --report-only  # recompute metrics from a finished run
```

Completed pairs are appended to `10_llm_annotations/stability_run2.jsonl` as they
finish, so interrupting is safe and `--run` resumes. Metrics land in
`stability_report.json`, which `13b_paper_numbers.py` §19 reads back. 

### A rounding note

Two figures in Sec 4.3 use round-half-up, which is the normal convention but
differs from Python's default formatting. `iaa_results.json` stores the stance
kappas as `0.6395` (child) and `0.6655` (parent); the paper reports `0.640` and
`0.666`, whereas `f"{v:.3f}"` yields `0.639` and `0.665`. Both are correct — the
stored four-decimal values are the reference.

### Known gaps

Three items cannot be regenerated from what this repository ships:

1. **Sec 3.1–3.2 raw collection totals** (14,280 videos; 4,638,722 comments;
   12,621 transcripts; 476,330 pseudonymized authors). Steps 01–05 are included,
   but their outputs are not: the pre-pseudonymization scrape contains real
   usernames and spans several GB. Re-running Steps 01–03 against the live
   YouTube API will not return these figures either, because the channels have
   continued to publish since the 06–13 March 2026 collection window.
2. **Step 03b is not exactly reproducible.** Its inputs are the Step 03 author
   maps (not shipped: they map pseudonyms back to real usernames) and a
   hand-reviewed override list of five purely alphabetic handles. Re-running `03b_mention_scrub.py` against the shipped corpus
   therefore reports no changes: the corpus is already scrubbed, and the script
   is idempotent. It is included so the method is auditable, not so the result
   can be recomputed.

---

## Data Availability

This repository ships the **released corpus and annotations**: sampled pairs (`08_pairs/`), the manual gold standard and IAA results (`09_manual_annotations/`), the LLM annotations and evaluation (`10_llm_annotations/`, `11_llm_annotations/`), thread-level scores (`12_thread_scores/`), BERTopic outputs (`06_bertopic_output/`), category assignments (`07_filtered/category_report.csv`), the blind topic check (`topic_validation/`), and channel/video metadata (`data_a_b/01_channel_videos/`, `data_c_d/01_channel_videos/`). All released text is pseudonymized.

`category_report.csv` is the only part of `07_filtered/` that the reporting
scripts read, and it is the only part tracked.

Not included (regenerable, excluded for size/privacy — see `.gitignore`):

- **Steps 02–05 raw outputs** (`data_a_b/`, `data_c_d/` subfolders `02_raw_scraped`–`05_relations`) — raw scraped comments contain real usernames prior to pseudonymization and span several GB. Regenerate via Steps 02–05 (requires `YOUTUBE_API_KEY`).
- **Per-video comment dumps** (`07_filtered/climate/`, `07_filtered/migration/`) — pseudonymized but privacy-sensitive at volume; regenerable via Step 07.
- **BERTopic model artifact** (`06_bertopic_output/bertopic_model`) — regenerated by Step 06.

### Author identifiers

Author pseudonyms (`ParentAuthor`, `ChildAuthor`) are assigned **per channel-group
collection**, not globally. Steps 01–05 run once over the two AfD channels
(`data_a_b/`) and once over the two Die Linke channels (`data_c_d/`), and each run
numbers its authors independently from `User_00001`. The design is deliberate:
each collection is self-contained, so further parties can be added later without
renumbering the existing corpus.

Four consequences:

1. **The person key is the pair `(party, author_id)`, not the id alone.** Within a
   party the ids are unique; across parties they are two separate namespaces. We
   verified this holds for all 13,154 author references in the released corpus:
   every id resolves inside its own party's namespace, with no exceptions.

2. **476,330 pseudonyms were assigned; 447,478 distinct authors.** The paper's
   figure is the total number of pseudonyms issued across the two collections
   (386,213 for the AfD channels + 90,117 for Die Linke). Because 28,852 authors
   commented on channels in both collections, they received one pseudonym in each,
   so the number of distinct people is 447,478. Anyone recomputing the author
   count will get the smaller figure; both are correct under their own scope.

3. **Eight ids occur under both parties in the released corpus** and denote
   different people in each. That is 8 of 5,030 distinct ids (0.16%); the party
   qualifier resolves them.

4. **Cross-party author linkage is not supported.** Because a person active on
   both parties' channels carries two ids, the corpus cannot be used to identify
   users who participate in both. Analyses of shared participation would
   under-count them and should not be attempted on this release.

### `@`-mentions inside comment text

Step 03 rewrites `@`-mentions through the per-collection author map, but its
coverage was incomplete: 250 mentions across 248 of the 7,277 pairs still
carried their original handle. Three causes, in order of frequency:

- the mention runs straight into the following word with no space, so the token
  extracted for lookup is the handle plus that word and misses the map;
- the mention names a user in the *other* collection, whose map was not loaded
  during that run;
- Step 03's regex cannot match a handle that begins with a hyphen.

**Step 03b (`03b_mention_scrub.py`) repairs this**, resolving 227 of the 250
occurrences. Resolution is party-aware: because pseudonyms are assigned per
collection, the same handle can exist in both maps with *different* ids — 68 of
these mentions do — so each is resolved against its own record's collection,
giving the id a consumer would get from the `(party, author_id)` key.

After Step 03b the corpus contains three kinds of `@`-token:

| token | meaning |
|---|---|
| `@User_NNNNN` | a pseudonymized author, resolvable via `(party, id)` |
| `@User_EXT_NN` | a handle with no pseudonym, because that user never authored a comment in either collection, or is known only in the other collection |
| anything else | not a handle: `@` used to address someone by name, where only the first word was captured (for example `@Die Linke im Bundestag`, or a first name followed by a surname) |

Do not treat any `@`-token as a stable author reference; `ParentAuthor` and
`ChildAuthor` are the only reliable ones.

---

## License

| Material | Terms |
|---|---|
| Annotations and everything derived from them (labels, scores, bins, guidelines, prompts, reports) | **CC BY-NC 4.0** — share and adapt for non-commercial purposes, with attribution |
| Source code (pipeline steps, annotation tools, reporting scripts) | **MIT** — so the pipeline is reusable without the non-commercial restriction |
| Underlying comment, title and transcript text | **Not ours to license.** Copyright remains with the YouTube users who posted it; redistributed pseudonymized for non-commercial research only |

If you authored a comment in this
corpus and want it removed, write to **alkaei@uni-potsdam.de** quoting the
`PairID` if you have it; the record will be removed and an updated release published.

---

## Requirements

**Python ≥ 3.10**

```bash
pip install -r requirements.txt
```

### API keys

Copy `.env.example` to `.env` and fill in:

| Variable | Used by | Purpose |
|---|---|---|
| `YOUTUBE_API_KEY` | Steps 01–02 | YouTube Data API v3 (collection) |
| `ANTHROPIC_API_KEY` | Steps 10, 10b, 11 | Claude (`claude-opus-4-6`) LLM annotation |

---

## Running the pipeline

Each script reads the output of the previous step:

```bash
python 01_channel_enumerator.py
python 02_german_scraper.py
# ... 03–08 ...
python 08_pair_creator.py
```

Steps 01–05 run **twice**, once per party: set `BASE_DATA_DIR=./data_a_b` with the AfD channel IDs, run 01–05, then switch `.env` to `BASE_DATA_DIR=./data_c_d` with the Die Linke channel IDs and rerun (see `.env.example`). Steps 06 onward process `data_a_b/` and `data_c_d/` together.

**Annotation.** After Step 09, the two annotators each produce a `gold_standard_*.jsonl`. Run `iaa_analysis.py` for inter-annotator agreement, then `streamlit run conflict_resolver.py` to reconcile conflicts into `gold_standard.jsonl`. Run Step 10 (LLM on the gold subset + evaluation), optionally Step 10b (`10b_stability_check.py --run`, the Sec 4.4 self-consistency check), then Step 11 (LLM on the rest), and `11_dedup_annotations.py` to retry any incomplete pairs. Then run `03b_mention_scrub.py --apply` once, which repairs the `@`-mentions Step 03 could not resolve (it needs the Step 03 author maps and runs after Step 11 so that every text-carrying file is corrected together). Finally, Step 12 aggregates thread scores and Steps 13 / 13b produce the statistics reports.
