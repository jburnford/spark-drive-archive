"""Curated corrections to dictionary headwords that the OCR misread.

Applied wherever commercial_dictionaries_lexicon.jsonl is read to build published artifacts, so the lexicon itself
stays the unedited parser output. Table: dictionaries/curated_headword_corrections.tsv
(source_work, headword_as_extracted, corrected_headword, evidence).
"""
import csv
import re
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "dictionaries" / "curated_headword_corrections.tsv"


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (s or "").lower())).strip()


def load():
    """{(source_work, normalised extracted headword): corrected headword}; every row needs evidence."""
    fixes = {}
    if not PATH.exists():
        return fixes
    with open(PATH, encoding="utf-8") as fh:
        for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
            if not (r["corrected_headword"] or "").strip() or not (r["evidence"] or "").strip():
                raise ValueError(f"curated_headword_corrections.tsv: {r['headword_as_extracted']!r} needs a correction and evidence")
            key = (r["source_work"], _norm(r["headword_as_extracted"]))
            if key in fixes:
                raise ValueError(f"curated_headword_corrections.tsv: duplicate row for {key}")
            fixes[key] = r["corrected_headword"].strip()
    return fixes


def apply(entry, fixes, used=None):
    """Correct one lexicon entry in place (headword and norm_headword); returns the entry."""
    key = (entry.get("source_work"), _norm(entry.get("headword") or entry.get("norm_headword") or ""))
    if key in fixes:
        entry["headword_as_extracted"] = entry.get("headword")
        entry["headword"] = fixes[key]
        entry["norm_headword"] = _norm(fixes[key])
        if used is not None:
            used.add(key)
    return entry


def check_all_used(fixes, used):
    stale = sorted(set(fixes) - set(used))
    if stale:
        raise ValueError(f"curated_headword_corrections.tsv: rows matched no lexicon entry: {stale}")
