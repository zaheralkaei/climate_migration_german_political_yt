r"""
Step 03b: scrub residual @-mentions from the sampled corpus.

Step 03 rewrites @-mentions through the per-collection author map, but its
coverage is incomplete for three reasons:

  1. the mention runs straight into the following word with no space, so the
     greedy token is "handle + word" and misses the map (the dominant cause);
  2. the mention names a user in the *other* channel-group collection, whose
     map was not loaded during that run;
  3. Step 03's regex `@([\w][\w\-\.]*)` cannot match a handle that begins with
     a hyphen, so a handle written `@-Name` is never even considered.

This script repairs the shipped corpus in place. 

Usage:
    python 03b_mention_scrub.py            # dry run: report only, writes nothing
    python 03b_mention_scrub.py --apply    # rewrite files 

Outputs (with --apply):
    <file>.bak                                    per-file backup
    09_manual_annotations/mention_scrub_log.tsv   every substitution made
    09_manual_annotations/mention_ext_map.json    placeholder -> original token
"""
import argparse
import json
import os
import re
import shutil
from collections import Counter, OrderedDict
from pathlib import Path

from utils.jsonl_io import load_jsonl, save_jsonl

MAPS = {
    "AfD":   Path("data_a_b/03_anonymized/username_map.json"),
    "Linke": Path("data_c_d/03_anonymized/username_map.json"),
}
FILES = [
    Path("08_pairs/sampled_pairs.jsonl"),
    Path("08_pairs/sampled_threads.jsonl"),
    Path("09_manual_annotations/gold_standard.jsonl"),
    Path("09_manual_annotations/gold_standard_a.jsonl"),
    Path("09_manual_annotations/gold_standard_z.jsonl"),
    Path("10_llm_annotations/llm_annotated_subset.jsonl"),
    Path("10_llm_annotations/stability_run2.jsonl"),
    Path("11_llm_annotations/llm_annotated_rest.jsonl"),
]
# The LLM's free-text reasoning can quote a handle it saw in the comment, and
# an annotator note can too, so both are scrubbed alongside the comment text.
TEXT_FIELDS = ("ParentText", "ChildText", "InteractionReasoning", "AnnotatorNote")

# 08_pairs/sampled_threads.jsonl keeps the whole thread in a nested list, so its
# comment text is not reachable through TEXT_FIELDS.
NESTED_LIST = "comments"
NESTED_TEXT_FIELDS = ("CommentText",)
LOG_FILE = Path("09_manual_annotations/mention_scrub_log.tsv")
EXT_FILE = Path("09_manual_annotations/mention_ext_map.json")

# Optional list of tokens to treat as handles even though they carry no digit
# or suffix marker (purely alphabetic handles). One token per line, without the
# leading '@'; blank lines and '#' comments ignored.

OVERRIDE_FILE = Path("09_manual_annotations/_private/mention_overrides.txt")

# A token is treated as a real handle when it carries a marker YouTube itself
# introduces: a digit run, or an auto-generated "-xxxxx" suffix, or an
# underscore. Purely alphabetic tokens are treated as names being used to
# address someone and are left alone.
HANDLE_SHAPED = re.compile(r"\d|_|-[A-Za-z0-9]{4,}$")
# '@' is today's syntax; '+' is the legacy Google+ form YouTube used for years
# and it still appears in older comments.
MENTION = re.compile(r"[@+]([A-Za-z0-9_\-.]+)")
MIN_HANDLE = 4          # do not resolve a prefix shorter than this

# Handles that also occur with NO prefix at all, so the mention regex cannot see
# them (a comment that opens "SomeHandle123 du hast wohl eine Meise", with the
# handle typed without any prefix). Reviewed by hand, because a bare
# token is otherwise indistinguishable from an ordinary German word — several
# real handles collide with words like "unterhaltung" or "ihresgleichen", and
# those must NOT be rewritten. One token per line; not tracked.
BARE_FILE = Path("09_manual_annotations/_private/mention_bare_tokens.txt")


def load_namespaces():
    ns = {}
    for party, path in MAPS.items():
        raw = json.load(open(path, encoding="utf-8"))
        exact = {k.lstrip("@"): v for k, v in raw.items()}
        ns[party] = (exact, {k.lower(): v for k, v in exact.items()})
    return ns


def longest_prefix(token, exact, lower):
    """Longest prefix of token that is a known handle -> (prefix, pseudonym)."""
    for end in range(len(token), MIN_HANDLE - 1, -1):
        cand = token[:end]
        if cand in exact:
            return cand, exact[cand]
        if cand.lower() in lower:
            return cand, lower[cand.lower()]
    return None, None


def load_tokens(path):
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lstrip("@+")
        if line:
            out.add(line)
    return out


def load_existing_ext():
    """Resume the placeholder series. Without this a second run would restart at
    User_EXT_01 and collide with ids already written into the corpus."""
    if not EXT_FILE.exists():
        return OrderedDict()
    raw = json.load(open(EXT_FILE, encoding="utf-8"))          # id -> token
    pairs = sorted(raw.items(), key=lambda kv: kv[0])
    return OrderedDict((tok, pid) for pid, tok in pairs)


class Scrubber:
    def __init__(self, ns, overrides=frozenset(), ext=None, bare=frozenset()):
        self.ns = ns
        self.overrides = overrides
        self.bare = bare
        self.ext = ext if ext is not None else OrderedDict()
        self.stats = Counter()
        self.log = []

    def placeholder(self, token):
        if token not in self.ext:
            self.ext[token] = f"User_EXT_{len(self.ext) + 1:02d}"
        return self.ext[token]

    def scrub(self, text, party, pair_id, field):
        if not text:
            return text

        if "@" not in text and "+" not in text:
            return self.scrub_bare(text, party, pair_id, field)
        own, own_l = self.ns[party]
        other_party = "Linke" if party == "AfD" else "AfD"
        oth, oth_l = self.ns[other_party]

        out, i = [], 0
        for m in MENTION.finditer(text):
            token = m.group(1)
            prefix = text[m.start()]
            if token.startswith("User_"):
                continue

            if len(token) < MIN_HANDLE or not any(c.isalpha() for c in token):
                continue
            pre, pid = longest_prefix(token, own, own_l)
            if pre:
                kind = "own"
            else:
                pre_o, _ = longest_prefix(token, oth, oth_l)
                pre_e = None
                for seen in sorted(self.ext, key=len, reverse=True):
                    if token.startswith(seen):
                        pre_e = seen
                        break
                if pre_o:
                    pre, pid, kind = pre_o, self.placeholder(pre_o), "other->ext"
                elif pre_e:
                    pre, pid, kind = pre_e, self.ext[pre_e], "unknown->ext (reused)"
                elif prefix == "+":
                    self.stats["left: '+' not a known handle"] += 1
                    continue
                elif HANDLE_SHAPED.search(token):
                    pre, pid, kind = token, self.placeholder(token), "unknown->ext"
                elif token in self.overrides:
                    pre, pid, kind = token, self.placeholder(token), "override->ext"
                else:
                    self.stats["left: name-shaped"] += 1
                    self.log.append((pair_id, field, party, token, "", "left (name-shaped)"))
                    continue
            start = m.start(1)
            out.append(text[i:start])
            out.append(pid)
            i = start + len(pre)
            self.stats[f"replaced: {kind}"] += 1
            self.log.append((pair_id, field, party, token, pid,
                             f"{kind}; kept '{token[len(pre):]}'" if len(pre) < len(token) else kind))
        out.append(text[i:])
        return self.scrub_bare("".join(out), party, pair_id, field)

    def scrub_bare(self, text, party, pair_id, field):
        """Second pass: handles that appear with no prefix at all.

        Only tokens on the reviewed bare list, or tokens that already carry an
        EXT placeholder, are touched. Matching is whole-token so a handle that
        is also a German substring cannot corrupt surrounding words.
        """
        if not text:
            return text
        own, own_l = self.ns[party]
        for tok in sorted(self.bare | set(self.ext), key=len, reverse=True):
            if tok not in text:
                continue
            pid = self.ext.get(tok) or own.get(tok) or own_l.get(tok.lower())
            if not pid:
                pid = self.placeholder(tok)
            pattern = r"(?<![A-Za-z0-9_@+.\-])" + re.escape(tok) + r"(?![A-Za-z0-9_])"
            text, n = re.subn(pattern, pid, text)
            if n:
                self.stats["replaced: bare token"] += n
                for _ in range(n):
                    self.log.append((pair_id, field, party, tok, pid, "bare (no prefix)"))
        return text


def main():
    ap = argparse.ArgumentParser(description="Scrub residual @-mentions (Step 03b).")
    ap.add_argument("--apply", action="store_true",
                    help="rewrite the files; without it this is a dry run")
    args = ap.parse_args()

    missing = [p for p in MAPS.values() if not p.exists()]
    if missing:
        print("Author map(s) not found — Step 03 output is required:")
        for p in missing:
            print("   ", p)
        return

    ns = load_namespaces()
    print(f"author namespaces: " +
          ", ".join(f"{k}={len(v[0])}" for k, v in ns.items()))

    overrides = load_tokens(OVERRIDE_FILE)
    bare = load_tokens(BARE_FILE)
    existing = load_existing_ext()
    print(f"manual overrides loaded: {len(overrides)} prefixed, {len(bare)} bare")
    if existing:
        print(f"resuming placeholder series from {len(existing)} existing entries")

    s = Scrubber(ns, overrides, existing, bare)
    per_file = []
    for path in FILES:
        if not path.exists():
            print(f"  skip (absent): {path}")
            continue
        records = load_jsonl(str(path))
        changed = 0
        for r in records:
            party = r.get("party")
            if party not in ns:
                continue
            for field in TEXT_FIELDS:
                before = r.get(field)
                after = s.scrub(before, party, r.get("PairID", "?"), field)
                if after != before:
                    r[field] = after
                    changed += 1
            # Thread-level records nest the full conversation in a "comments"
            # list, so the comment text sits one level down rather than in the
            # flat ParentText / ChildText fields.
            for c in (r.get(NESTED_LIST) or []):
                for field in NESTED_TEXT_FIELDS:
                    before = c.get(field)
                    after = s.scrub(before, party,
                                    r.get("thread_id") or r.get("PairID", "?"), field)
                    if after != before:
                        c[field] = after
                        changed += 1
        per_file.append((path, len(records), changed))
        print(f"  {str(path):50} {len(records):>6} records, {changed:>4} text fields changed")
        if args.apply and changed:
            shutil.copy2(path, str(path) + ".bak")
            save_jsonl(records, str(path))

    print("\noutcomes (mention occurrences):")
    for k in sorted(s.stats):
        print(f"   {k:28} {s.stats[k]:>4}")
    print(f"   {'TOTAL considered':28} {sum(s.stats.values()):>4}")

    if s.ext:
        print(f"\nreserved placeholders assigned: {len(s.ext)}")
        for tok, pid in s.ext.items():
            print(f"   @{tok:34} -> {pid}")

    if args.apply:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8", newline="") as f:
            f.write("PairID\tField\tParty\tOriginalToken\tReplacement\tNote\n")
            for row in s.log:
                f.write("\t".join(str(x) for x in row) + "\n")
        json.dump({v: k for k, v in s.ext.items()}, open(EXT_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"\nlog  -> {LOG_FILE}  ({len(s.log)} rows)")
        print(f"map  -> {EXT_FILE}")
        print("backups written alongside each modified file (.bak)")
    else:
        print("\nDRY RUN — nothing written. Re-run with --apply to rewrite the files.")


if __name__ == "__main__":
    main()
