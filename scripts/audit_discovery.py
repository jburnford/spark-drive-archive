#!/usr/bin/env python3
"""Audit Waves 1-3 discovery TSVs and print breakdowns by series, colony, year, and source."""

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DISC_DIR = BASE_DIR / "manifests" / "discovery"
CEYLON_BB = Path("/home/jic823/Documents/ceylon/spine/bluebook/volumes.tsv")


def main():
    ceylon_ids = set()
    if CEYLON_BB.exists():
        for r in csv.DictReader(open(CEYLON_BB, encoding="utf-8"), delimiter="\t"):
            for k in ("ia_id", "identifier", "item_id"):
                if r.get(k):
                    ceylon_ids.add(r[k].strip())
    print(f"Existing Ceylon Blue Book IA IDs loaded: {len(ceylon_ids)}\n")

    for p in sorted(DISC_DIR.glob("wave*.tsv")):
        rows = list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))
        open_rows = [r for r in rows if r["restricted"] == "0"]
        years = sorted(y for y in {r["year"] for r in open_rows if r["year"]})
        yr_range = f"{years[0]}..{years[-1]}" if years else "none"
        total_gb = sum(int(r["item_size"]) for r in open_rows if r["item_size"].isdigit()) / (1024**3)
        print(f"=== {p.name}: open={len(open_rows)}/{len(rows)}, years={yr_range}, total_item_size={total_gb:.2f} GiB ===")

        cols = Counter()
        for r in open_rows:
            for c in r["collections"].split("; "):
                if c in (
                    "biodiversity",
                    "pub_kew-bulletin",
                    "colonial-office-gb-publications",
                    "digitallibraryindia",
                    "americana",
                    "toronto",
                    "jstor_ejc",
                    "southasiaopenarchives",
                    "sim_microfilm",
                    "pub_journal-of-the-royal-society-of-arts",
                    "pub_journal-of-the-society-of-arts",
                    "pub_bulletin-of-the-imperial-institute",
                    "pub_indian-forester",
                    "biostor",
                ):
                    cols[c] += 1
        if cols:
            print("  key collections:", dict(cols))

        # Special breakdown for colonial_office_gb_collection
        if "colonial_office_gb" in p.name or "blue_books" in p.name:
            by_colony = Counter()
            blue_books = []
            for r in open_rows:
                t = r["title"]
                if "blue book" in t.lower():
                    blue_books.append(r)
                    # heuristic colony name
                    m = re.sub(r"(?i)\b(blue\s*book|for\s+the\s+year|colony\s+and\s+protectorate\s+of|colony\s+of|island\s+of|british|protectorate\s+of|\d{4}[-–]\d{2,4}|\d{4})\b", " ", t)
                    m = re.sub(r"[^A-Za-z\s]", " ", m)
                    m = " ".join(m.split()[:3]).strip()
                    by_colony[m or "OTHER"] += 1
            print(f"  Blue Book items: {len(blue_books)} (overlap w/ ceylon={sum(1 for r in blue_books if r['identifier'] in ceylon_ids)})")
            print("  Top Blue Book titles/colonies:", by_colony.most_common(25))

        for r in open_rows[:5]:
            print(f"  [{r['year']}] {r['identifier']} | pg={r['imagecount']} | {r['title'][:90]}")
        print()


if __name__ == "__main__":
    main()
