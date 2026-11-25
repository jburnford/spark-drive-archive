#!/usr/bin/env python3
"""
Curate deduplicated, clean open-access manifests for Waves 1-3 from the raw
Internet Archive discovery snapshots in manifests/discovery/.

Outputs:
  manifests/wave1_economic_botany.tsv
  manifests/wave2_colonial_bluebooks.tsv
  manifests/wave3_regional_ghost_acres.tsv
  manifests/curation_report.md
"""

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path("/home/jic823/Documents/open_empire")
DISC_DIR = BASE_DIR / "manifests" / "discovery"
MAN_DIR = BASE_DIR / "manifests"
CEYLON_BB = Path("/home/jic823/Documents/ceylon/spine/bluebook/volumes.tsv")

OUT_FIELDS = [
    "wave",
    "series",
    "sub_group",
    "year",
    "identifier",
    "title",
    "creator",
    "volume",
    "imagecount",
    "item_size_mb",
    "source_collection",
    "rights_tier",
    "status",
    "notes",
]


def load_rows(filename):
    p = DISC_DIR / filename
    if not p.exists():
        return []
    rows = list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))
    return [r for r in rows if r["restricted"] == "0"]


def parse_year(r):
    for field in (r.get("year", ""), r.get("title", ""), r.get("date", ""), r.get("identifier", "")):
        m = re.search(r"\b(17\d{2}|18\d{2}|19[0-4]\d)\b", field or "")
        if m:
            return int(m.group(1))
    return None


def size_mb(r):
    s = r.get("item_size", "")
    return round(int(s) / (1024 * 1024), 1) if s.isdigit() else 0.0


def primary_collection(r):
    cols = [c.strip() for c in r.get("collections", "").split(";") if c.strip()]
    priority = [
        "colonial-office-gb-publications",
        "biodiversity",
        "toronto",
        "americana",
        "digitallibraryindia",
        "pub_kew-bulletin",
        "jstor_ejc",
        "sim_microfilm",
        "southasiaopenarchives",
    ]
    for p in priority:
        if p in cols:
            return p
    return cols[0] if cols else ""


def rank_scan(r):
    """Higher is better: prefer BHL/toronto/americana bound scans with page counts over fragmented or microfilm scans."""
    col = primary_collection(r)
    col_score = {
        "colonial-office-gb-publications": 100,
        "biodiversity": 95,
        "toronto": 85,
        "americana": 80,
        "digitallibraryindia": 70,
        "pub_kew-bulletin": 60,
        "jstor_ejc": 50,
        "sim_microfilm": 30,
    }.get(col, 40)
    pg = int(r["imagecount"]) if r.get("imagecount", "").isdigit() else 0
    # Slightly penalize bub_gb_* Google Books if a BHL/university scan exists
    gb_penalty = -10 if r["identifier"].startswith("bub_gb_") else 0
    return (col_score + gb_penalty, pg)


def curate_wave1():
    out = []

    # 1. Kew Bulletin: take BHL/bound annual volumes (1887-1927) + 1887-1918 Index + any pub_kew-bulletin issues only for missing years?
    # Actually check both bound volumes (pages >= 150 or biodiversity/americana/dli) and note pub_kew-bulletin issue runs cleanly.
    kew_rows = load_rows("wave1_kew_bulletin.tsv")
    kew_bound = []
    kew_issues = []
    for r in kew_rows:
        yr = parse_year(r)
        if yr and yr > 1927:
            continue
        col = primary_collection(r)
        pg = int(r["imagecount"]) if r.get("imagecount", "").isdigit() else 0
        if "index" in r["title"].lower() or "additional series" in r["title"].lower():
            kew_bound.append((yr, r))
        elif col in ("biodiversity", "americana", "toronto", "digitallibraryindia") or pg >= 150:
            kew_bound.append((yr, r))
        elif col == "pub_kew-bulletin" and yr and 1887 <= yr <= 1924:
            kew_issues.append((yr, r))

    # Deduplicate bound Kew volumes by identifier; keep all unique BHL/bound vols up to 1927
    seen = set()
    for yr, r in sorted(kew_bound, key=lambda x: (x[0] or 9999, -rank_scan(x[1])[0], -rank_scan(x[1])[1])):
        if r["identifier"] in seen:
            continue
        seen.add(r["identifier"])
        out.append({
            "wave": "wave1",
            "series": "kew_bulletin",
            "sub_group": "bound_volume",
            "year": yr or "",
            "identifier": r["identifier"],
            "title": r["title"],
            "creator": r["creator"],
            "volume": r["volume"],
            "imagecount": r["imagecount"],
            "item_size_mb": size_mb(r),
            "source_collection": primary_collection(r),
            "rights_tier": "tier1_open",
            "status": "queued",
            "notes": f"pub_kew-bulletin issues also available ({len(kew_issues)} pre-1925 issues)",
        })

    # 2. Bulletin of the Imperial Institute (1903-1927): keep toronto + best DLI per year/vol
    imp_rows = load_rows("wave1_imperial_institute.tsv")
    by_yr_vol = defaultdict(list)
    for r in imp_rows:
        yr = parse_year(r)
        if yr and yr > 1927:
            continue
        # Extract volume number from title/volume/identifier
        m_vol = re.search(r"(?:vol\.?|v\.?)\s*([0-9]+|[ivxlc]+)", r["title"] + " " + r["volume"], re.I)
        if not m_vol:
            m_vol = re.search(r"bulletinofimperi(\d{2})", r["identifier"], re.I)
        vkey = m_vol.group(1).lstrip("0").lower() if m_vol else f"yr{yr}"
        by_yr_vol[vkey].append((yr, r))

    for vkey, items in sorted(by_yr_vol.items()):
        # pick best scan per volume key (keep up to 1 best)
        items.sort(key=lambda x: rank_scan(x[1]), reverse=True)
        yr, r = items[0]
        if r["identifier"] in seen:
            continue
        seen.add(r["identifier"])
        out.append({
            "wave": "wave1",
            "series": "imperial_institute",
            "sub_group": f"vol_{vkey}",
            "year": yr or "",
            "identifier": r["identifier"],
            "title": r["title"],
            "creator": r["creator"],
            "volume": r["volume"] or vkey,
            "imagecount": r["imagecount"],
            "item_size_mb": size_mb(r),
            "source_collection": primary_collection(r),
            "rights_tier": "tier1_open",
            "status": "queued",
            "notes": f"deduped from {len(items)} candidate scans",
        })

    # 3. Straits / Malaya Agricultural Bulletin (1891-1927): keep all BHL/bound + unique pre-1928
    straits_rows = load_rows("wave1_straits_ag_bulletin.tsv")
    for r in sorted(straits_rows, key=lambda x: (parse_year(x) or 9999, x["identifier"])):
        yr = parse_year(r)
        if yr and yr > 1927:
            continue
        if r["identifier"] in seen:
            continue
        seen.add(r["identifier"])
        out.append({
            "wave": "wave1",
            "series": "straits_ag_bulletin",
            "sub_group": primary_collection(r),
            "year": yr or "",
            "identifier": r["identifier"],
            "title": r["title"],
            "creator": r["creator"],
            "volume": r["volume"],
            "imagecount": r["imagecount"],
            "item_size_mb": size_mb(r),
            "source_collection": primary_collection(r),
            "rights_tier": "tier1_open",
            "status": "queued",
            "notes": "",
        })

    # 4. Watt's Dictionary of Economic Products of India (dedup by volume/part)
    watt_rows = load_rows("wave1_watt_dict_india.tsv")
    watt_groups = defaultdict(list)
    for r in watt_rows:
        t = (r["title"] + " " + r["volume"]).lower()
        # normalize volume + part
        m = re.search(r"vol(?:ume)?\.?\s*[-:]?\s*([1-6]|vi|iv|v|iii|ii|i)\b.*?(?:part|pt\.?)\s*[-:]?\s*([1-4]|iv|iii|ii|i)\b", t)
        if m:
            key = f"v{m.group(1)}_p{m.group(2)}"
        else:
            m2 = re.search(r"vol(?:ume)?\.?\s*[-:]?\s*([1-6]|vi|iv|v|iii|ii|i)\b", t)
            if "index" in t:
                key = "index"
            elif m2:
                key = f"v{m2.group(1)}"
            else:
                key = f"other_{r['identifier'][:12]}"
        # normalize roman numerals
        roman = {"vi": "6", "iv": "4", "v": "5", "iii": "3", "ii": "2", "i": "1"}
        for rk, rv in roman.items():
            key = re.sub(rf"\b([vp]){rk}\b", rf"\g<1>{rv}", key)
            key = re.sub(rf"([vp]){rk}(_|$)", rf"\g<1>{rv}\2", key)
        watt_groups[key].append(r)

    for key, items in sorted(watt_groups.items()):
        items.sort(key=rank_scan, reverse=True)
        r = items[0]
        if r["identifier"] in seen:
            continue
        seen.add(r["identifier"])
        out.append({
            "wave": "wave1",
            "series": "watt_dict_india",
            "sub_group": key,
            "year": parse_year(r) or "",
            "identifier": r["identifier"],
            "title": r["title"],
            "creator": r["creator"],
            "volume": r["volume"] or key,
            "imagecount": r["imagecount"],
            "item_size_mb": size_mb(r),
            "source_collection": primary_collection(r),
            "rights_tier": "tier1_open",
            "status": "queued",
            "notes": f"deduped from {len(items)} scans",
        })

    # 5. Agricultural Ledger (India, 1892-1912)
    ag_rows = load_rows("wave1_agricultural_ledger.tsv")
    for r in sorted(ag_rows, key=lambda x: (parse_year(x) or 9999, x["title"])):
        yr = parse_year(r)
        if yr and yr > 1920:
            continue
        if r["identifier"] in seen:
            continue
        seen.add(r["identifier"])
        out.append({
            "wave": "wave1",
            "series": "agricultural_ledger",
            "sub_group": str(yr or "undated"),
            "year": yr or "",
            "identifier": r["identifier"],
            "title": r["title"],
            "creator": r["creator"],
            "volume": r["volume"],
            "imagecount": r["imagecount"],
            "item_size_mb": size_mb(r),
            "source_collection": primary_collection(r),
            "rights_tier": "tier1_open",
            "status": "queued",
            "notes": "",
        })

    # 6. Journal of the Society of Arts (bound annual volumes 1852-1925, skip single-article jstor_ejc fragments if bound volumes exist)
    jsa_rows = load_rows("wave1_journal_society_of_arts.tsv")
    for r in sorted(jsa_rows, key=lambda x: (parse_year(x) or 9999, x["identifier"])):
        col = primary_collection(r)
        pg = int(r["imagecount"]) if r.get("imagecount", "").isdigit() else 0
        if col == "jstor_ejc" and pg < 100:
            continue  # skip tiny single-issue/article JSTOR EJC snippets; keep full volumes
        if r["identifier"] in seen:
            continue
        seen.add(r["identifier"])
        out.append({
            "wave": "wave1",
            "series": "journal_society_of_arts",
            "sub_group": "bound_volume",
            "year": parse_year(r) or "",
            "identifier": r["identifier"],
            "title": r["title"],
            "creator": r["creator"],
            "volume": r["volume"],
            "imagecount": r["imagecount"],
            "item_size_mb": size_mb(r),
            "source_collection": col,
            "rights_tier": "tier1_open",
            "status": "queued",
            "notes": "",
        })

    return out


COLONY_PATTERNS = [
    ("Ceylon", r"\bceylon\b"),
    ("Straits Settlements", r"\bstraits\s+settlements\b|\bfederated\s+malay\b"),
    ("Gold Coast", r"\bgold\s+coast\b"),
    ("Nigeria", r"\bnigeria\b|\blagos\b"),
    ("Sierra Leone", r"\bsierra\s+leone\b"),
    ("Gambia", r"\bgambia\b"),
    ("Jamaica", r"\bjamaica\b"),
    ("British Guiana", r"\bguiana\b"),
    ("Trinidad and Tobago", r"\btrinidad\b"),
    ("Barbados", r"\bbarbados\b"),
    ("Mauritius", r"\bmauritius\b"),
    ("Natal", r"\bnatal\b"),
    ("Cape Colony", r"\bcape\s+of\s+good\s+hope\b|\bcape\s+colony\b"),
    ("Hong Kong", r"\bhong\s*kong\b"),
    ("Cyprus", r"\bcyprus\b"),
    ("Malta", r"\bmalta\b"),
    ("Tanganyika", r"\btanganyika\b"),
    ("Uganda", r"\buganda\b"),
    ("Kenya", r"\bkenya\b|\beast\s+africa\s+protectorate\b"),
    ("Nyasaland", r"\bnyasaland\b"),
    ("Zanzibar", r"\bzanzibar\b"),
    ("Palestine", r"\bpalestine\b"),
    ("Fiji", r"\bfiji\b"),
    ("Gibraltar", r"\bgibraltar\b"),
    ("Bermuda", r"\bbermuda\b"),
    ("Bahamas", r"\bbahamas\b"),
    ("British Honduras", r"\bbritish\s+honduras\b"),
    ("Falkland Islands", r"\bfalkland\b"),
    ("St Helena", r"\bst\.?\s*helena\b"),
    ("Seychelles", r"\bseychelles\b"),
    ("Leeward / Windward Islands", r"\bleeward\b|\bwindward\b|\bgrenada\b|\bst\.?\s*lucia\b|\bst\.?\s*vincent\b|\bdominica\b|\bantigua\b"),
    ("Northern / Southern Rhodesia", r"\brhodesia\b"),
]


def detect_colony(title, identifier):
    txt = f"{title} {identifier}".lower()
    for name, pat in COLONY_PATTERNS:
        if re.search(pat, txt):
            return name
    return "Other / Multi-Colony"


def curate_wave2():
    ceylon_existing_ids = set()
    ceylon_existing_years = set()
    if CEYLON_BB.exists():
        for r in csv.DictReader(open(CEYLON_BB, encoding="utf-8"), delimiter="\t"):
            for k, v in r.items():
                if not v:
                    continue
                if "id" in k.lower() or "item" in k.lower() or "archive" in k.lower():
                    ceylon_existing_ids.add(v.strip())
                if "year" in k.lower() and re.fullmatch(r"\d{4}", v.strip()):
                    ceylon_existing_years.add(int(v.strip()))

    combined = load_rows("wave2_colonial_office_gb_collection.tsv") + load_rows("wave2_blue_books_british_world.tsv")
    seen = set()
    out = []
    for r in combined:
        iid = r["identifier"]
        if iid in seen:
            continue
        t_low = r["title"].lower()
        if "blue book" not in t_low:
            continue
        if "clark" in t_low and "boston" in t_low:
            continue  # false positive
        seen.add(iid)
        colony = detect_colony(r["title"], iid)
        yr = parse_year(r)
        notes = ""
        status = "queued"
        if colony == "Ceylon":
            if iid in ceylon_existing_ids or (yr and yr in ceylon_existing_years):
                status = "already_in_ceylon"
                notes = "already present in /home/jic823/Documents/ceylon"
            else:
                status = "ceylon_gap_candidate"
                notes = "POTENTIAL MISSING CEYLON BLUE BOOK YEAR!"
        out.append({
            "wave": "wave2",
            "series": "colonial_blue_book",
            "sub_group": colony,
            "year": yr or "",
            "identifier": iid,
            "title": r["title"],
            "creator": r["creator"],
            "volume": r["volume"],
            "imagecount": r["imagecount"],
            "item_size_mb": size_mb(r),
            "source_collection": primary_collection(r),
            "rights_tier": "tier1_open",
            "status": status,
            "notes": notes,
        })

    out.sort(key=lambda x: (x["sub_group"], x["year"] or 9999, x["identifier"]))
    return out


def curate_wave3():
    out = []
    seen = set()
    files = [
        ("indian_forester", "wave3_indian_forester.tsv"),
        ("burma_rice_forest_trade", "wave3_burma_rice_forest_trade.tsv"),
        ("west_africa_commodities", "wave3_west_africa_commodities.tsv"),
        ("australasia_pastoral_stats", "wave3_australasia_pastoral_stats.tsv"),
        ("bhl_economic_botany", "wave3_saoa_and_bhl_imperial_botany.tsv"),
    ]
    for series, fname in files:
        rows = load_rows(fname)
        for r in sorted(rows, key=lambda x: (parse_year(x) or 9999, x["identifier"])):
            iid = r["identifier"]
            if iid in seen:
                continue
            t_low = r["title"].lower()
            # Filter obvious false positives in australasia (e.g. "Queen Victoria" Canadian pamphlets)
            if series == "australasia_pastoral_stats":
                if not re.search(r"new south wales|nsw|queensland|qld|victoria|austral|new zealand|tasmania|sydney|melbourne|brisbane", t_low):
                    continue
                if "canad" in t_low or "british american" in t_low or "british columbia" in t_low:
                    continue
            yr = parse_year(r)
            if yr and yr > 1935:
                continue
            seen.add(iid)
            sub = series
            if series == "australasia_pastoral_stats":
                if "queensland" in t_low or "qld" in t_low:
                    sub = "Queensland"
                elif "new south wales" in t_low or "nsw" in t_low:
                    sub = "New South Wales"
                elif "victoria" in t_low or "vic." in t_low:
                    sub = "Victoria"
                elif "new zealand" in t_low:
                    sub = "New Zealand"
                else:
                    sub = "Australasia_General"
            out.append({
                "wave": "wave3",
                "series": series,
                "sub_group": sub,
                "year": yr or "",
                "identifier": iid,
                "title": r["title"],
                "creator": r["creator"],
                "volume": r["volume"],
                "imagecount": r["imagecount"],
                "item_size_mb": size_mb(r),
                "source_collection": primary_collection(r),
                "rights_tier": "tier1_open",
                "status": "queued",
                "notes": "",
            })
    return out


def write_tsv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS, delimiter="\t")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    w1 = curate_wave1()
    w2 = curate_wave2()
    w3 = curate_wave3()

    write_tsv(MAN_DIR / "wave1_economic_botany.tsv", w1)
    write_tsv(MAN_DIR / "wave2_colonial_bluebooks.tsv", w2)
    write_tsv(MAN_DIR / "wave3_regional_ghost_acres.tsv", w3)

    # Build concise curation report
    lines = ["# Open Empire Curated Discovery Report (2026-11-23)\n"]
    lines.append(f"- **Wave 1 (Imperial Economic Botany & Raw-Materials Serials):** {len(w1)} curated open volumes\n")
    for s, c in Counter(r["series"] for r in w1).most_common():
        yrs = [r["year"] for r in w1 if r["series"] == s and r["year"]]
        yr_str = f"{min(yrs)}–{max(yrs)}" if yrs else "n/a"
        lines.append(f"  - `{s}`: {c} volumes ({yr_str})\n")

    lines.append(f"\n- **Wave 2 (Colonial Blue Books):** {len(w2)} open Blue Books across {len(set(r['sub_group'] for r in w2))} colonies\n")
    for col, c in Counter(r["sub_group"] for r in w2).most_common():
        yrs = [r["year"] for r in w2 if r["sub_group"] == col and r["year"]]
        yr_str = f"{min(yrs)}–{max(yrs)}" if yrs else "n/a"
        lines.append(f"  - **{col}**: {c} volumes ({yr_str})\n")

    ceylon_gaps = [r for r in w2 if r["status"] == "ceylon_gap_candidate"]
    if ceylon_gaps:
        lines.append(f"\n### Potential Missing Ceylon Blue Books Found on IA ({len(ceylon_gaps)})\n")
        for r in ceylon_gaps:
            lines.append(f"- `{r['year']}` | `{r['identifier']}` | {r['title']}\n")

    lines.append(f"\n- **Wave 3 (Regional 'Ghost Acres of Ghost Acres'):** {len(w3)} curated open volumes\n")
    for s, c in Counter(r["series"] for r in w3).most_common():
        yrs = [r["year"] for r in w3 if r["series"] == s and r["year"]]
        yr_str = f"{min(yrs)}–{max(yrs)}" if yrs else "n/a"
        lines.append(f"  - `{s}`: {c} volumes ({yr_str})\n")

    rep_path = MAN_DIR / "curation_report.md"
    rep_path.write_text("".join(lines), encoding="utf-8")
    print("".join(lines))


if __name__ == "__main__":
    main()
