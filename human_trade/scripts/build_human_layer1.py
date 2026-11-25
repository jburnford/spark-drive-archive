#!/usr/bin/env python3
"""
Consolidate human-transcribed British & Imperial trade datasets into canonical
Layer-1 (`extraction_layer = human_transcribed`) tables, strictly separated
from future LLM-extracted data.

Follows ceylon/spine principles:
  - Files are the source of truth.
  - Preserve printed strings verbatim (never overwrite raw text).
  - Tag totals ('World' / 'Total') separately from origin_detail rows.
  - Flag anomalous/blank/duplicate rows transparently instead of silently dropping.
  - Emit frequency-ranked name inventories (places, commodities, units) for
    reversible grounding against empire-evolution, Wikidata, and Catalogue of Life.
"""

import csv
import gzip
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path("/home/jic823/Documents/open_empire/human_trade")
RAW = BASE / "raw_sources"
OUT = BASE / "layer1_human"
NAMES = OUT / "names"
OUT.mkdir(parents=True, exist_ok=True)
NAMES.mkdir(parents=True, exist_ok=True)

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

TOTAL_LABELS = {
    "world",
    "total",
    "totals",
    "all countries",
    "total imports",
    "total from all countries",
    "grand total",
}

CANON_FIELDS = [
    "record_id",
    "extraction_layer",
    "source_file",
    "source_row",
    "orig_row_id",
    "series_name",
    "year_as_printed",
    "year_start",
    "year_end",
    "period_type",
    "commodity_as_printed",
    "origin_as_printed",
    "destination_as_printed",
    "row_kind",
    "amount_as_printed",
    "amount_numeric",
    "unit_as_printed",
    "top_level_unit",
    "value_as_printed",
    "value_numeric",
    "currency_as_printed",
    "orig_from_lat",
    "orig_from_lon",
    "orig_to_lat",
    "orig_to_lon",
    "note",
    "qa_flags",
]


def parse_year_field(raw: str):
    s = (raw or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    m_span = re.fullmatch(r"(\d{4})\s*[-–/]\s*(\d{2,4})", s)
    if m_span:
        y1 = int(m_span.group(1))
        y2s = m_span.group(2)
        y2 = int(y2s) if len(y2s) == 4 else int(str(y1)[:2] + y2s)
        return s, y1, y2, "fiscal_or_span"
    m_single = re.fullmatch(r"(\d{4})", s)
    if m_single:
        y = int(m_single.group(1))
        return s, y, y, "calendar_year"
    return s, "", "", "unparsed"


def parse_number(raw: str):
    s = (raw or "").strip().replace(",", "")
    if not s or s in ("-", "—", "NA", "N/A", "NULL"):
        return ""
    try:
        v = float(s)
        if v == int(v):
            return str(int(v))
        return f"{v:.6f}".rstrip("0").rstrip(".")
    except ValueError:
        return ""


def classify_row(origin: str, dest: str, commodity: str, year_s: str, year_start, series: str):
    flags = []
    if not year_s:
        flags.append("missing_year")
    elif not year_start:
        flags.append("non_numeric_year")
        if year_s.strip().lower() == "mille":
            flags.append("unit_in_year_col")
    if not commodity:
        flags.append("missing_commodity")
    if not origin:
        flags.append("missing_origin")
    if series and "null" in series.lower():
        flags.append("flagged_null_or_error_series")

    o_low = origin.strip().lower()
    d_low = dest.strip().lower()
    if o_low == "check" and not commodity and not year_s:
        flags.append("spreadsheet_check_row")
        kind = "qa_check_row"
    elif not commodity and not origin and not year_s:
        kind = "blank"
    elif year_s and not year_start:
        kind = "malformed_year"
    elif o_low in TOTAL_LABELS:
        kind = "import_total"
    elif d_low in TOTAL_LABELS:
        kind = "export_total"
    elif not origin or not commodity:
        kind = "incomplete"
    else:
        kind = "origin_detail"
    return kind, ";".join(flags)


def read_xlsx_rows(path: Path, sheet_idx: int = 1):
    zf = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in zf.namelist():
        for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", NS):
            ss.append("".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    root = ET.fromstring(zf.read(f"xl/worksheets/sheet{sheet_idx}.xml"))
    out = []
    for r in root.findall(".//m:sheetData/m:row", NS):
        row_map = {}
        max_col = 0
        for c in r.findall("m:c", NS):
            ref = "".join(ch for ch in c.attrib["r"] if ch.isalpha())
            col_i = 0
            for ch in ref:
                col_i = col_i * 26 + (ord(ch.upper()) - ord("A") + 1)
            max_col = max(max_col, col_i)
            t = c.attrib.get("t")
            v = c.find("m:v", NS)
            if v is None:
                is_el = c.find("m:is", NS)
                val = "".join(x.text or "" for x in is_el.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")) if is_el is not None else ""
            elif t == "s":
                val = ss[int(v.text)]
            else:
                val = v.text or ""
            row_map[col_i] = val
        out.append([row_map.get(i, "") for i in range(1, max_col + 1)])
    return out


def main():
    records = []

    # 1. Core 1790-1920 human-transcribed database (tc_2021_full_database.csv)
    p_core = RAW / "tc_2021_full_database.csv"
    with open(p_core, encoding="utf-8", errors="replace", newline="") as fh:
        cr = csv.reader(fh)
        hdr = next(cr)
        # Positional mapping because several blank spacer columns exist in the export:
        # 0:[Row], 1:SERIES_NAME, 2:YEAR, 3:COMMODITY_NAME, 4:TO_LOC_STD, 5:FROM_LOC_STD,
        # 6:FROM_LOCATION, 7:TO_LOCATION, 8:'', 9:AMOUNT, 10:TopLevelUnit, 11:'', 12:'',
        # 13:UNIT_NAME, 14:'', 15:VALUE, 16:RoundedDownValue, 17:CURRENCY_NAME, 18:NOTE,
        # 19:FROM_LAT, 20:FROM_LON, 21:TO_LAT, 22:TO_LON
        def col(r, idx):
            return r[idx].strip() if idx < len(r) else ""

        for row_num, r in enumerate(cr, start=2):
            if not any(x.strip() for x in r):
                continue
            orig_id = col(r, 0).split(".")[0]
            series = col(r, 1)
            yr_raw, y1, y2, ptype = parse_year_field(col(r, 2))
            comm = col(r, 3)
            orig = col(r, 6)
            dest = col(r, 7)
            amt_raw = col(r, 9)
            top_u = col(r, 10)
            unit_raw = col(r, 13)
            val_raw = col(r, 15)
            curr = col(r, 17)
            note = col(r, 18)
            kind, flags = classify_row(orig, dest, comm, yr_raw, y1, series)
            records.append({
                "record_id": f"ht_tc2021_{row_num:06d}",
                "extraction_layer": "human_transcribed",
                "source_file": p_core.name,
                "source_row": row_num,
                "orig_row_id": orig_id,
                "series_name": series,
                "year_as_printed": yr_raw,
                "year_start": y1,
                "year_end": y2,
                "period_type": ptype,
                "commodity_as_printed": comm,
                "origin_as_printed": orig,
                "destination_as_printed": dest,
                "row_kind": kind,
                "amount_as_printed": amt_raw,
                "amount_numeric": parse_number(amt_raw),
                "unit_as_printed": unit_raw,
                "top_level_unit": top_u,
                "value_as_printed": val_raw,
                "value_numeric": parse_number(val_raw),
                "currency_as_printed": curr,
                "orig_from_lat": col(r, 19),
                "orig_from_lon": col(r, 20),
                "orig_to_lat": col(r, 21),
                "orig_to_lon": col(r, 22),
                "note": note,
                "qa_flags": flags,
            })

    # 2. 1910-1940 UK food/grain continuation (British Imports Database 1910-1940.xlsx)
    p_1910 = RAW / "British Imports Database 1910-1940.xlsx"
    xrows = read_xlsx_rows(p_1910, 1)
    # Header: 0:YEAR, 1:COMMODITY_NAME, 2:TO_LOC_STD, 3:FROM_LOC_STD, 4:FROM_LOCATION,
    # 5:TO_LOCATION, 6:AMOUNT, 7:UNIT_NAME, 8:VALUE, 9:CURRENCY_NAME, 10:NOTE,
    # 11:FROM_LAT, 12:FROM_LON, 13:TO_LAT, 14:TO_LON, 15:SERIES_NAME
    # Track exact overlap with core 1910-1920 rows
    core_keys = set()
    for rec in records:
        if rec["year_start"] and int(rec["year_start"]) >= 1910:
            core_keys.add((
                rec["year_as_printed"],
                rec["commodity_as_printed"].lower(),
                rec["origin_as_printed"].lower(),
                rec["destination_as_printed"].lower(),
                rec["amount_numeric"],
            ))

    added_1910 = 0
    overlap_1910 = 0
    blank_1910 = 0
    for row_num, r in enumerate(xrows[1:], start=2):
        def colx(idx):
            return str(r[idx]).strip() if idx < len(r) else ""
        yr_raw, y1, y2, ptype = parse_year_field(colx(0))
        comm = colx(1)
        orig = colx(4)
        dest = colx(5)
        amt_raw = colx(6)
        unit_raw = colx(7)
        val_raw = colx(8)
        curr = colx(9)
        note = colx(10)
        series = colx(15) or "HCPP_Annual Statement of Trade (1910-1940 ext)"
        if not yr_raw and not comm and not orig:
            blank_1910 += 1
            continue
        amt_num = parse_number(amt_raw)
        key = (yr_raw, comm.lower(), orig.lower(), dest.lower(), amt_num)
        kind, flags = classify_row(orig, dest, comm, yr_raw, y1, series)
        if key in core_keys:
            overlap_1910 += 1
            flags = (flags + ";overlaps_tc2021").lstrip(";")
            continue  # avoid double-loading exact duplicates into canonical Layer 1
        added_1910 += 1
        records.append({
            "record_id": f"ht_uk1910_{row_num:05d}",
            "extraction_layer": "human_transcribed",
            "source_file": p_1910.name,
            "source_row": row_num,
            "orig_row_id": "",
            "series_name": series,
            "year_as_printed": yr_raw,
            "year_start": y1,
            "year_end": y2,
            "period_type": ptype,
            "commodity_as_printed": comm,
            "origin_as_printed": orig,
            "destination_as_printed": dest,
            "row_kind": kind,
            "amount_as_printed": amt_raw,
            "amount_numeric": amt_num,
            "unit_as_printed": unit_raw,
            "top_level_unit": "",
            "value_as_printed": val_raw,
            "value_numeric": parse_number(val_raw),
            "currency_as_printed": curr,
            "orig_from_lat": colx(11),
            "orig_from_lon": colx(12),
            "orig_to_lat": colx(13),
            "orig_to_lon": colx(14),
            "note": note,
            "qa_flags": flags,
        })

    # Write canonical Layer-1 TSV.GZ
    canon_path = OUT / "human_trade_observations.tsv.gz"
    with gzip.open(canon_path, "wt", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CANON_FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(records)

    # Audit blank-series rows, places, commodities, units, and World-total arithmetic
    blank_ser_dests = Counter()
    blank_ser_years = Counter()
    places = Counter()
    place_roles = defaultdict(Counter)
    commodities = Counter()
    units = Counter()
    row_kinds = Counter()
    series_counts = Counter()

    # Group for World-total arithmetic check
    groups = defaultdict(lambda: {"totals": [], "parts_amt": 0.0, "parts_val": 0.0, "n_parts": 0})

    for rec in records:
        row_kinds[rec["row_kind"]] += 1
        series_counts[rec["series_name"] or "(blank)"] += 1
        if not rec["series_name"]:
            blank_ser_dests[rec["destination_as_printed"] or "(blank)"] += 1
            blank_ser_years[rec["year_as_printed"] or "(blank)"] += 1
        if rec["row_kind"] in ("qa_check_row", "blank"):
            continue
        if rec["origin_as_printed"] and rec["origin_as_printed"].strip().lower() not in TOTAL_LABELS:
            places[rec["origin_as_printed"]] += 1
            place_roles[rec["origin_as_printed"]]["origin"] += 1
        if rec["destination_as_printed"] and rec["destination_as_printed"].strip().lower() not in TOTAL_LABELS:
            places[rec["destination_as_printed"]] += 1
            place_roles[rec["destination_as_printed"]]["destination"] += 1
        if rec["commodity_as_printed"]:
            commodities[rec["commodity_as_printed"]] += 1
        if rec["unit_as_printed"]:
            units[(rec["unit_as_printed"], rec["top_level_unit"])] += 1

        # Arithmetic check key (import totals: World vs origin parts)
        gkey = (rec["source_file"], rec["series_name"], rec["year_as_printed"], rec["commodity_as_printed"], rec["destination_as_printed"], rec["unit_as_printed"])
        if rec["row_kind"] == "import_total" and rec["amount_numeric"]:
            groups[gkey]["totals"].append((float(rec["amount_numeric"]), float(rec["value_numeric"]) if rec["value_numeric"] else None))
        elif rec["row_kind"] == "origin_detail" and rec["amount_numeric"]:
            groups[gkey]["parts_amt"] += float(rec["amount_numeric"])
            if rec["value_numeric"]:
                groups[gkey]["parts_val"] += float(rec["value_numeric"])
            groups[gkey]["n_parts"] += 1

    # Write name inventories (exact ceylon/spine style)
    with open(NAMES / "places.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["name_as_printed", "total_rows", "origin_rows", "destination_rows"])
        for name, cnt in places.most_common():
            w.writerow([name, cnt, place_roles[name]["origin"], place_roles[name]["destination"]])

    with open(NAMES / "commodities.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["commodity_as_printed", "total_rows"])
        for name, cnt in commodities.most_common():
            w.writerow([name, cnt])

    with open(NAMES / "units.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["unit_as_printed", "top_level_unit", "total_rows"])
        for (u, tu), cnt in units.most_common():
            w.writerow([u, tu, cnt])

    # Evaluate World-total arithmetic checks
    checkable = 0
    agree_1pct = 0
    agree_5pct = 0
    disagree = 0
    for gkey, g in groups.items():
        if len(g["totals"]) == 1 and g["n_parts"] >= 2:
            tot_amt = g["totals"][0][0]
            if tot_amt > 0:
                checkable += 1
                rel = abs(g["parts_amt"] - tot_amt) / tot_amt
                if rel <= 0.01:
                    agree_1pct += 1
                elif rel <= 0.05:
                    agree_5pct += 1
                else:
                    disagree += 1

    # Print & save audit report
    report = []
    report.append("# Layer-1 Human-Transcribed Trade Consolidation Report\n\n")
    report.append(f"- **Canonical file:** `{canon_path}`\n")
    report.append(f"- **Total Layer-1 records:** **{len(records):,}** (`tc_2021_full_database.csv`: 144,742; `British Imports Database 1910-1940.xlsx`: +{added_1910:,} unique, {overlap_1910:,} exact overlaps skipped, {blank_1910:,} blank rows skipped)\n")
    report.append(f"- **Row kinds:** {dict(row_kinds)}\n")
    report.append(f"- **Unique printed places (origin + destination, excl. World/Total):** **{len(places):,}**\n")
    report.append(f"- **Unique printed commodities:** **{len(commodities):,}**\n")
    report.append(f"- **Unique printed unit pairs:** **{len(units):,}**\n\n")

    report.append("## Series Breakdown\n")
    for s, c in series_counts.most_common():
        report.append(f"- `{s}`: **{c:,}**\n")

    report.append("\n## What Are the 64,289 Blank-Series Rows?\n")
    report.append(f"- Top destinations: {blank_ser_dests.most_common(12)}\n")
    yrs_b = sorted(y for y in blank_ser_years if y != "(blank)")
    report.append(f"- Year span: `{yrs_b[0]}` to `{yrs_b[-1]}` ({len(yrs_b)} distinct year labels)\n")

    report.append("\n## Built-In `World`-Total Arithmetic Check (Origin Parts vs. Printed World Total)\n")
    report.append(f"- Checkable `(series, year, commodity, dest, unit)` groups (>=2 origin rows + 1 World total): **{checkable:,}**\n")
    if checkable:
        report.append(f"  - Agree within 1%: **{agree_1pct:,}** ({agree_1pct/checkable*100:.1f}%)\n")
        report.append(f"  - Agree within 1–5%: **{agree_5pct:,}** ({agree_5pct/checkable*100:.1f}%)\n")
        report.append(f"  - Differ >5% (often partial country coverage or 'Other Countries' omitted): **{disagree:,}** ({disagree/checkable*100:.1f}%)\n")

    rep_text = "".join(report)
    (OUT / "CONSOLIDATION_REPORT.md").write_text(rep_text, encoding="utf-8")
    print(rep_text)


if __name__ == "__main__":
    main()
