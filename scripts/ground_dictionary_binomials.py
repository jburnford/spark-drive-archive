#!/usr/bin/env python3
"""
Ground Latin binomials extracted from the 6 commercial dictionaries against:
  1. Local Wikidata 2026-11-09 slim Parquet (`/mnt/data/jic823/wikidata/20261109/slim/*.parquet`,
     strictly filtered to `Q16521` taxon items!)
  2. `ceylon/spine/grounding/taxa_col.jsonl` (Catalogue of Life accepted names & synonyms!)

Outputs `/home/jic823/Documents/open_empire/dictionaries/dictionary_binomials_grounded.jsonl`.
ZERO QIDs from memory.
"""

import json
from collections import Counter
from pathlib import Path

import duckdb

DICT_DIR = Path("/home/jic823/Documents/open_empire/dictionaries")
LEX_PATH = DICT_DIR / "commercial_dictionaries_lexicon.jsonl"
OUT_PATH = DICT_DIR / "dictionary_binomials_grounded.jsonl"
CEYLON_COL = Path("/home/jic823/Documents/ceylon/spine/grounding/taxa_col.jsonl")
WD_SLIM_GLOB = "/mnt/data/jic823/wikidata/20261109/slim/*.parquet"


def main():
    binoms = Counter()
    for line in open(LEX_PATH, encoding="utf-8"):
        if not line.strip():
            continue
        d = json.loads(line)
        for b in d.get("latin_binomials") or []:
            binoms[b] += 1

    print(f"Unique candidate binomials from 6 dictionaries: {len(binoms):,}", flush=True)

    # Load Catalogue of Life lookup from ceylon/spine (if present)
    col_by_name = {}
    if CEYLON_COL.exists():
        for line in open(CEYLON_COL, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            nm = (d.get("scientific_name") or d.get("key") or d.get("name") or "").strip().lower()
            if nm and d.get("col_id"):
                col_by_name[nm] = {
                    "col_id": d["col_id"],
                    "accepted_name": d.get("accepted_name") or d.get("scientific_name") or nm,
                    "status": d.get("status", ""),
                }

    # Query Wikidata 2026-11-09 slim Parquet strictly for Q16521 (taxon) items matching binomials
    con = duckdb.connect()
    con.execute("CREATE TEMP TABLE want(b VARCHAR)")
    con.executemany("INSERT INTO want VALUES (?)", [(b.lower(),) for b in binoms])

    sql = f"""
    SELECT
        lower(label_en) AS lkey,
        qid,
        label_en,
        description_en,
        sitelinks
    FROM '{WD_SLIM_GLOB}'
    WHERE lower(label_en) IN (SELECT b FROM want)
      AND list_contains(instance_of, 'Q16521')
    ORDER BY lkey, sitelinks DESC, length(qid), qid
    """
    rows = con.execute(sql).fetchall()
    wd_by_b = {}
    for lkey, qid, lbl, desc, sl in rows:
        if lkey not in wd_by_b:
            wd_by_b[lkey] = {
                "qid": qid,
                "taxon_name": lbl,
                "description": desc or "",
                "sitelinks": int(sl or 0),
            }

    matched = 0
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        for b, cnt in binoms.most_common():
            bl = b.lower()
            wd = wd_by_b.get(bl)
            col = col_by_name.get(bl)
            if wd or col:
                matched += 1
                rec = {
                    "binomial": b,
                    "dict_mentions": cnt,
                    "qid": wd["qid"] if wd else "",
                    "taxon_name": wd["taxon_name"] if wd else b,
                    "description": wd["description"] if wd else "",
                    "col_id": col["col_id"] if col else "",
                    "col_accepted": col["accepted_name"] if col else "",
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Grounded {matched:,} / {len(binoms):,} dictionary Latin binomials to verified Wikidata Q16521 taxa / CoL -> {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
