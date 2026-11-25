#!/usr/bin/env python3
"""
Audit all staged human-transcribed trade sources under human_trade/raw_sources/.
Compares full_database_2020_10.xlsx vs tc_2021_full_database.csv, inspects
British Imports Database 1910-1940.xlsx, 1709-1710, terra_japonica, and SKOS.
"""

import csv
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "human_trade" / "raw_sources"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_xlsx_sheet(path: Path, sheet_idx: int = 1):
    zf = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in zf.namelist():
        for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", NS):
            ss.append("".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    sheets = [(s.attrib["name"], i + 1) for i, s in enumerate(wb.findall(".//m:sheet", NS))]
    sp = f"xl/worksheets/sheet{sheet_idx}.xml"
    root = ET.fromstring(zf.read(sp))
    rows_out = []
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
        if any(str(v).strip() for v in row_map.values()):
            rows_out.append([row_map.get(i, "") for i in range(1, max_col + 1)])
    return sheets, rows_out


def main():
    # 1. Inspect 1910-1940
    p1910 = RAW / "British Imports Database 1910-1940.xlsx"
    sheets, rows = read_xlsx_sheet(p1910, 1)
    print(f"=== {p1910.name} ===\nSheets: {[s[0] for s in sheets]}")
    print(f"Sheet 1 rows (incl header): {len(rows):,}")
    if rows:
        hdr = rows[0]
        print("Header:", hdr)
        for sample in rows[1:4]:
            print("  sample:", sample[:14])
        # Summarize years & commodities
        yr_idx = next((i for i, h in enumerate(hdr) if "year" in h.lower()), None)
        com_idx = next((i for i, h in enumerate(hdr) if "comm" in h.lower() or "article" in h.lower()), None)
        orig_idx = next((i for i, h in enumerate(hdr) if "from" in h.lower() or "country" in h.lower() or "origin" in h.lower() or "source" in h.lower()), None)
        if yr_idx is not None:
            yc = Counter(str(r[yr_idx]).split(".")[0].strip() for r in rows[1:] if len(r) > yr_idx)
            print("Years:", sorted(yc.items()))
        if com_idx is not None:
            cc = Counter(str(r[com_idx]).strip() for r in rows[1:] if len(r) > com_idx and str(r[com_idx]).strip())
            print(f"Unique commodities: {len(cc)}, top 10:", cc.most_common(10))
        if orig_idx is not None:
            oc = Counter(str(r[orig_idx]).strip() for r in rows[1:] if len(r) > orig_idx and str(r[orig_idx]).strip())
            print(f"Unique origins: {len(oc)}, top 10:", oc.most_common(10))

    # 2. Inspect 1709-1710 and terra_japonica and SKOS
    print("\n=== 1709-1710 British Commodity Imports.xlsx ===")
    s17, r17 = read_xlsx_sheet(RAW / "1709-1710 British Commodity Imports.xlsx", 1)
    print("Sheets:", [s[0] for s in s17], "Rows:", len(r17))
    for x in r17[:4]:
        print(" ", x[:10])

    print("\n=== terra_japonica_imports_1810-1844.csv ===")
    tj_rows = list(csv.reader(open(RAW / "terra_japonica_imports_1810-1844.csv", encoding="utf-8", errors="replace")))
    print("Rows:", len(tj_rows))
    for x in tj_rows[:4]:
        print(" ", x)

    print("\n=== SKOS_from_Custom_Records.xlsx ===")
    sskos, rskos = read_xlsx_sheet(RAW / "SKOS_from_Custom_Records.xlsx", 1)
    print("Sheets:", [s[0] for s in sskos], "Rows:", len(rskos))
    for x in rskos[:5]:
        print(" ", x[:10])

    # 3. Compare full_database_2020_10.xlsx Sheet 1 vs tc_2021_full_database.csv
    print("\n=== Comparing full_database_2020_10.xlsx vs tc_2021_full_database.csv ===")
    _, xrows = read_xlsx_sheet(RAW / "full_database_2020_10.xlsx", 1)
    xhdr = xrows[0]
    print("XLSX header:", xhdr)
    x_by_yr = Counter()
    x_by_ser = Counter()
    x_rowids = set()
    x_world = 0
    for r in xrows[1:]:
        rid = str(r[0]).split(".")[0].strip() if len(r) > 0 else ""
        ser = str(r[1]).strip() if len(r) > 1 else ""
        yr = str(r[2]).split(".")[0].strip() if len(r) > 2 else ""
        fl = str(r[6]).strip() if len(r) > 6 else ""
        x_rowids.add(rid)
        x_by_yr[yr] += 1
        x_by_ser[ser or "(blank)"] += 1
        if fl.lower() in ("world", "total", "all countries"):
            x_world += 1

    c_by_yr = Counter()
    c_by_ser = Counter()
    c_rowids = set()
    with open(RAW / "tc_2021_full_database.csv", encoding="utf-8", errors="replace", newline="") as fh:
        cr = csv.reader(fh)
        chdr = next(cr)
        for r in cr:
            if not any(x.strip() for x in r):
                continue
            rid = r[0].split(".")[0].strip() if len(r) > 0 else ""
            ser = r[1].strip() if len(r) > 1 else ""
            yr = r[2].split(".")[0].strip() if len(r) > 2 else ""
            c_rowids.add(rid)
            c_by_yr[yr] += 1
            c_by_ser[ser or "(blank)"] += 1

    print(f"XLSX data rows: {len(xrows)-1:,} (unique [Row] IDs: {len(x_rowids):,}, World/Total rows: {x_world:,})")
    print(f"CSV  data rows: {sum(c_by_yr.values()):,} (unique [Row] IDs: {len(c_rowids):,})")
    print("XLSX series counts:", x_by_ser.most_common(15))
    print("CSV  series counts:", c_by_ser.most_common(15))
    diff_yrs = {y: x_by_yr[y] - c_by_yr[y] for y in sorted(set(x_by_yr) | set(c_by_yr)) if x_by_yr[y] != c_by_yr[y]}
    print("Year count diffs (XLSX - CSV):", diff_yrs)


if __name__ == "__main__":
    main()
