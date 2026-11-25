#!/usr/bin/env python3
"""Discover clean public-domain 19th-century commercial dictionaries on Internet Archive
(Simmonds, McCulloch, Ure, Mortimer) for Chandra OCR -> SKOS/LOD commodity grounding."""

import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "manifests"
USER_AGENT = "OpenEmpireResearchBot/0.2 (University of Saskatchewan HGIS Lab; jim.clifford@usask.ca)"

FIELDS = ["identifier", "title", "date", "year", "creator", "collection", "imagecount", "item_size", "volume", "access-restricted-item"]

QUERIES = [
    ("simmonds_trade_products", 'mediatype:texts AND title:("Commercial Dictionary of Trade Products")'),
    ("simmonds_vegetable_kingdom", 'mediatype:texts AND title:("Commercial Products of the Vegetable Kingdom")'),
    ("mcculloch_commerce", 'mediatype:texts AND creator:("McCulloch") AND title:("Dictionary, Practical, Theoretical, and Historical, of Commerce")'),
    ("ure_arts_manufactures", 'mediatype:texts AND creator:("Ure") AND title:("Dictionary of Arts, Manufactures, and Mines")'),
    ("mortimer_commerce", 'mediatype:texts AND title:("General Dictionary of Commerce, Trade, and Manufactures")'),
]


def norm(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    return str(v)


def is_restricted(d):
    if str(d.get("access-restricted-item", "")).lower() == "true":
        return True
    cols = d.get("collection") or []
    if isinstance(cols, str):
        cols = [cols]
    return bool({"inlibrary", "printdisabled"} & set(cols))


def main():
    rows = []
    seen = set()
    for series, q in QUERIES:
        params = [("q", q), ("output", "json"), ("rows", "100"), ("page", "1"), ("sort[]", "date asc")]
        for f in FIELDS:
            params.append(("fl[]", f))
        url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            docs = json.loads(resp.read().decode("utf-8")).get("response", {}).get("docs", [])
        open_docs = [d for d in docs if not is_restricted(d)]
        print(f"[{series}] found={len(docs)}, open={len(open_docs)}", flush=True)
        for d in open_docs:
            iid = d.get("identifier", "")
            if iid in seen:
                continue
            seen.add(iid)
            sz = d.get("item_size", "")
            sz_mb = round(int(sz) / (1024 * 1024), 1) if str(sz).isdigit() else 0.0
            rows.append({
                "wave": "wave1b",
                "series": series,
                "sub_group": "commercial_dictionary",
                "year": norm(d.get("year")),
                "identifier": iid,
                "title": norm(d.get("title")).replace("\t", " ").replace("\n", " "),
                "creator": norm(d.get("creator")).replace("\t", " "),
                "volume": norm(d.get("volume")),
                "imagecount": norm(d.get("imagecount")),
                "item_size_mb": sz_mb,
                "source_collection": norm(d.get("collection")).split(";")[0].strip(),
                "rights_tier": "tier1_open",
                "status": "queued",
                "notes": "For Chandra OCR -> (trade_term, latin_binomial, skos:altLabel) extraction",
            })
        time.sleep(0.5)

    out_path = OUT_DIR / "wave1b_commercial_dictionaries.tsv"
    fields = ["wave", "series", "sub_group", "year", "identifier", "title", "creator", "volume", "imagecount", "item_size_mb", "source_collection", "rights_tier", "status", "notes"]
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} open dictionary editions to {out_path}")


if __name__ == "__main__":
    main()
