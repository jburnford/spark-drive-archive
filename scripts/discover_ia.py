#!/usr/bin/env python3
"""
Discover open public-domain historical serials and archival volumes on the
Internet Archive (including BHL and Colonial Office collections) across
Waves 1-3 for the Open Empire project.

Writes raw discovery JSONL and clean summary TSVs into ../manifests/discovery/.
"""

import csv
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "manifests" / "discovery"
OUT_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "OpenEmpireResearchBot/0.1 (University of Saskatchewan HGIS Lab; jim.clifford@usask.ca)"

FIELDS = [
    "identifier",
    "title",
    "date",
    "year",
    "creator",
    "collection",
    "mediatype",
    "imagecount",
    "item_size",
    "language",
    "licenseurl",
    "rights",
    "source",
    "publicdate",
    "volume",
    "access-restricted-item",
]

QUERIES = [
    # Wave 1: Imperial Economic Botany & Raw-Materials Serials
    (
        "wave1",
        "kew_bulletin",
        'mediatype:texts AND ((title:("Bulletin of miscellaneous information") AND (title:("Kew") OR creator:("Kew") OR subject:("Kew"))) OR title:("Kew bulletin"))',
        1000,
    ),
    (
        "wave1",
        "imperial_institute",
        'mediatype:texts AND title:("Bulletin of the Imperial Institute")',
        500,
    ),
    (
        "wave1",
        "straits_ag_bulletin",
        'mediatype:texts AND (title:("Agricultural bulletin of the Straits") OR title:("Gardens\' bulletin, Straits Settlements") OR title:("Agricultural bulletin of the Malay Peninsula"))',
        500,
    ),
    (
        "wave1",
        "watt_dict_india",
        'mediatype:texts AND title:("Dictionary of the economic products of India")',
        200,
    ),
    (
        "wave1",
        "agricultural_ledger",
        'mediatype:texts AND title:("Agricultural ledger")',
        500,
    ),
    (
        "wave1",
        "journal_society_of_arts",
        'mediatype:texts AND (title:("Journal of the Society of Arts") OR title:("Journal of the Royal Society of Arts")) AND date:[1850-01-01 TO 1927-12-31]',
        1000,
    ),
    # Wave 2: Colonial Blue Books & Colonial Office Publications beyond Ceylon
    (
        "wave2",
        "colonial_office_gb_collection",
        "collection:(colonial-office-gb-publications) AND mediatype:texts",
        2500,
    ),
    (
        "wave2",
        "blue_books_british_world",
        'mediatype:texts AND title:("Blue Book") AND (title:("Straits Settlements") OR title:("Gold Coast") OR title:("Nigeria") OR title:("Lagos") OR title:("Sierra Leone") OR title:("Jamaica") OR title:("British Guiana") OR title:("Mauritius") OR title:("Natal") OR title:("Cape of Good Hope") OR title:("Trinidad") OR title:("Federated Malay States") OR title:("Fiji") OR title:("Hong Kong") OR title:("Gambia") OR title:("Barbados"))',
        2000,
    ),
    # Wave 3: Regional "Ghost Acres of Ghost Acres"
    (
        "wave3",
        "indian_forester",
        'mediatype:texts AND title:("Indian forester") AND date:[1875-01-01 TO 1927-12-31]',
        600,
    ),
    (
        "wave3",
        "burma_rice_forest_trade",
        'mediatype:texts AND title:("Burma") AND (title:("Forest") OR title:("Rice") OR title:("Trade and Navigation") OR title:("Season and Crop") OR title:("Agriculture")) AND date:[1860-01-01 TO 1935-12-31]',
        800,
    ),
    (
        "wave3",
        "west_africa_commodities",
        'mediatype:texts AND (title:("palm oil") OR title:("Gold Coast") OR title:("Southern Nigeria") OR title:("Northern Nigeria") OR title:("Lagos") OR title:("Sierra Leone") OR title:("West Africa")) AND (title:("forest") OR title:("rubber") OR title:("agriculture") OR title:("botanical") OR title:("trade") OR title:("products") OR title:("timber") OR title:("economic")) AND date:[1850-01-01 TO 1927-12-31]',
        800,
    ),
    (
        "wave3",
        "australasia_pastoral_stats",
        'mediatype:texts AND (title:("New South Wales") OR title:("Queensland") OR title:("Victoria") OR title:("Australasia") OR title:("New Zealand")) AND (title:("Statistical Register") OR title:("Year Book") OR title:("pastoral") OR title:("tallow") OR title:("wool") OR title:("drought") OR title:("stock")) AND date:[1860-01-01 TO 1920-12-31]',
        800,
    ),
    (
        "wave3",
        "saoa_and_bhl_imperial_botany",
        'mediatype:texts AND (collection:("southasiaopenarchives") OR (collection:("biodiversity") AND (title:("economic products") OR title:("tanning") OR title:("cinchona") OR title:("caoutchouc") OR title:("gutta percha") OR title:("gambier") OR title:("palm oil"))))',
        800,
    ),
]


def norm_val(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    return str(v)


def is_restricted(doc):
    if str(doc.get("access-restricted-item", "")).lower() == "true":
        return True
    cols = doc.get("collection") or []
    if isinstance(cols, str):
        cols = [cols]
    col_set = set(cols)
    if "inlibrary" in col_set or "printdisabled" in col_set:
        return True
    return False


def query_ia(q, max_rows=1000):
    docs = []
    page = 1
    rows_per_page = min(500, max_rows)
    total = None
    while len(docs) < max_rows:
        params = [
            ("q", q),
            ("output", "json"),
            ("rows", str(rows_per_page)),
            ("page", str(page)),
            ("sort[]", "date asc"),
        ]
        for f in FIELDS:
            params.append(("fl[]", f))
        url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        response = data.get("response", {})
        if total is None:
            total = response.get("numFound", 0)
        batch = response.get("docs", [])
        if not batch:
            break
        docs.extend(batch)
        if len(docs) >= total:
            break
        page += 1
        time.sleep(0.5)
    return total or 0, docs[:max_rows]


def main():
    summary_rows = []
    for wave, series, q, max_rows in QUERIES:
        print(f"Querying [{wave}/{series}] ...", flush=True)
        try:
            total, docs = query_ia(q, max_rows=max_rows)
        except Exception as exc:
            print(f"  ERROR: {exc}", flush=True)
            summary_rows.append((wave, series, -1, 0, 0, str(exc)))
            continue

        open_docs = [d for d in docs if not is_restricted(d)]
        restricted_count = len(docs) - len(open_docs)

        jsonl_path = OUT_DIR / f"{wave}_{series}.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as fh:
            for d in docs:
                d["_wave"] = wave
                d["_series"] = series
                d["_restricted"] = is_restricted(d)
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")

        tsv_path = OUT_DIR / f"{wave}_{series}.tsv"
        tsv_fields = [
            "identifier",
            "restricted",
            "year",
            "date",
            "title",
            "creator",
            "volume",
            "imagecount",
            "item_size",
            "collections",
            "licenseurl",
            "source",
        ]
        with open(tsv_path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(tsv_fields)
            for d in docs:
                w.writerow([
                    norm_val(d.get("identifier")),
                    "1" if is_restricted(d) else "0",
                    norm_val(d.get("year")),
                    norm_val(d.get("date")),
                    norm_val(d.get("title")).replace("\t", " ").replace("\n", " "),
                    norm_val(d.get("creator")).replace("\t", " ").replace("\n", " "),
                    norm_val(d.get("volume")),
                    norm_val(d.get("imagecount")),
                    norm_val(d.get("item_size")),
                    norm_val(d.get("collection")).replace("\t", " "),
                    norm_val(d.get("licenseurl")),
                    norm_val(d.get("source")).replace("\t", " ").replace("\n", " "),
                ])

        print(
            f"  found={total}, fetched={len(docs)}, open={len(open_docs)}, restricted={restricted_count}",
            flush=True,
        )
        summary_rows.append((wave, series, total, len(docs), len(open_docs), restricted_count))
        time.sleep(0.6)

    summary_path = OUT_DIR / "discovery_summary.tsv"
    with open(summary_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["wave", "series", "num_found", "fetched", "open_count", "restricted_or_err"])
        for row in summary_rows:
            w.writerow(row)
    print(f"\nWrote summary to {summary_path}")


if __name__ == "__main__":
    main()
