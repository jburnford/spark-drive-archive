#!/usr/bin/env python3
"""
Read-only extractor that caches structured commodity/synonym/description rows from
Danika's Drugs Project (`Drugs.xlsx`, `Drugs descriptions.docx`, `1866 Commodities.xlsx`)
into a clean local JSON snapshot (`dictionaries/danika_and_1866_extracted.json`).
Raw spreadsheets/docx remain untouched on `/datastore` and are never committed to GitHub.
"""

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DANIKA_DIR = Path("/datastore/HGISLab/HGIS LAB/Clifford/Danika_Leather_Work/Drugs Project")
OUT_PATH = ROOT / "dictionaries" / "danika_and_1866_extracted.json"


def norm_key(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"['’`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def read_xlsx_sheet(path: Path, sheet_xml: str):
    NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    zf = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in zf.namelist():
        for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", NS):
            ss.append("".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    root = ET.fromstring(zf.read(sheet_xml))
    rows = []
    for r in root.findall(".//m:sheetData/m:row", NS):
        rmap, mx = {}, 0
        for c in r.findall("m:c", NS):
            ref = "".join(ch for ch in c.attrib["r"] if ch.isalpha())
            ci = 0
            for ch in ref:
                ci = ci * 26 + (ord(ch.upper()) - ord("A") + 1)
            mx = max(mx, ci)
            v = c.find("m:v", NS)
            val = "" if v is None else (ss[int(v.text)] if c.attrib.get("t") == "s" else (v.text or ""))
            rmap[ci] = val.strip()
        row = [rmap.get(i, "") for i in range(1, mx + 1)]
        if any(row):
            rows.append(row)
    return rows


def read_danika_descriptions(path: Path):
    if not path.exists():
        return {}
    zf = zipfile.ZipFile(path)
    root = ET.fromstring(zf.read("word/document.xml"))
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paras = ["".join(t.text or "" for t in p.iter(W + "t")).strip() for p in root.iter(W + "p")]
    paras = [p for p in paras if p and not p.startswith("<ref>") and not p.startswith("==")]
    descs = {}
    cur = None
    buf = []
    for p in paras:
        if len(p) <= 35 and not p.endswith(".") and re.match(r"^[A-Z][A-Za-z\s\-]+$", p):
            if cur and buf:
                descs[norm_key(cur)] = " ".join(buf)[:420]
            cur = p
            buf = []
        elif cur:
            buf.append(p)
    if cur and buf:
        descs[norm_key(cur)] = " ".join(buf)[:420]
    return descs


def main():
    descs = read_danika_descriptions(DANIKA_DIR / "Drugs descriptions.docx")
    items = {}

    def upsert(name, alts=None, roles=None, notes="", src="", defn=""):
        k = norm_key(name)
        if not k or len(k) < 3 or k in ("red not in pharm", "concept", "name", "1866 list"):
            return
        rec = items.setdefault(k, {
            "label": name.strip(),
            "alts": [],
            "roles": [],
            "notes": [],
            "sources": [],
            "definition": "",
        })
        for a in (alts or []):
            a = a.strip(" .,;-")
            if a and len(a) >= 3 and a.lower() != rec["label"].lower() and a.lower() not in {x.lower() for x in rec["alts"]}:
                rec["alts"].append(a)
        for r in (roles or []):
            r = r.strip()
            if r and r.lower() not in {x.lower() for x in rec["roles"]}:
                rec["roles"].append(r)
        if notes and notes not in rec["notes"]:
            rec["notes"].append(notes)
        if src and src not in rec["sources"]:
            rec["sources"].append(src)
        if defn and not rec["definition"]:
            rec["definition"] = defn
        elif k in descs and not rec["definition"]:
            rec["definition"] = f"{descs[k]} [Danika Drugs Project: British Pharmacopoeia (1867) / Savory (1865)]"

    # 1. Drugs.xlsx Sheet 1
    s1 = read_xlsx_sheet(DANIKA_DIR / "Drugs.xlsx", "xl/worksheets/sheet1.xml")
    for r in s1[2:]:
        name = (r[0] if len(r) > 0 else "").strip()
        forms = (r[1] if len(r) > 1 else "").strip()
        notes = (r[2] if len(r) > 2 else "").strip()
        if not name or name.lower().startswith("red ="):
            continue
        alts = []
        if forms and len(forms) < 40 and "," not in forms:
            alts.append(forms)
        upsert(name, alts=alts, roles=["Drug"], notes=notes, src="Danika Drugs.xlsx (British Pharmacopoeia 1867 / Savory 1865)")
        row_txt = (notes + " " + " ".join(r[3:])).lower()
        if "strychnine" in row_txt:
            upsert("Strychnine", alts=["nux vomica alkaloid"], roles=["Drug"], src="Danika Drugs.xlsx (British Pharmacopoeia 1867 / Savory 1865)")
        if "laudanum" in row_txt:
            upsert("Laudanum", alts=["tincture of opium", "Dover's powder"], roles=["Drug"], src="Danika Drugs.xlsx (British Pharmacopoeia 1867 / Savory 1865)")
        if "calomel" in row_txt:
            upsert("Calomel", alts=["mercurous chloride", "blue pill"], roles=["Drug"], src="Danika Drugs.xlsx (British Pharmacopoeia 1867 / Savory 1865)")
        if "sal volatile" in row_txt:
            upsert("Sal Volatile", alts=["liquid ammonia", "volatile alkali"], roles=["Drug", "Chemical"], src="Danika Drugs.xlsx (British Pharmacopoeia 1867 / Savory 1865)")

    # 2. Drugs.xlsx Sheet 2
    s2 = read_xlsx_sheet(DANIKA_DIR / "Drugs.xlsx", "xl/worksheets/sheet2.xml")
    for r in s2[1:]:
        name = (r[0] if len(r) > 0 else "").strip()
        pref = (r[1] if len(r) > 1 else "").strip()
        alt_s = (r[2] if len(r) > 2 else "").strip()
        role_s = (r[5] if len(r) > 5 else "").strip()
        note = (r[6] if len(r) > 6 else "").strip()
        alts = [x.strip() for x in re.split(r"[,;]", alt_s) if x.strip() and x.strip().lower() not in ("plant", "fruit", "bark", "seed", "tuber", "timber")]
        if pref and pref.lower() != name.lower():
            alts.insert(0, pref)
        roles = [x.strip() for x in re.split(r"[,;]", role_s) if x.strip() and len(x.strip()) < 25]
        upsert(name, alts=alts, roles=roles or ["Drug"], notes=note, src="Danika Drugs.xlsx (SKOS Sheet)")

    # 3. 1866 Commodities.xlsx Sheet 1
    c1 = read_xlsx_sheet(DANIKA_DIR / "1866 Commodities.xlsx", "xl/worksheets/sheet1.xml")
    for r in c1[1:]:
        name = (r[0] if len(r) > 0 else "").strip()
        pref = (r[1] if len(r) > 1 else "").strip()
        alt_s = (r[2] if len(r) > 2 else "").strip()
        broader = (r[3] if len(r) > 3 else "").strip()
        role_s = (r[5] if len(r) > 5 else "").strip()
        note = (r[6] if len(r) > 6 else "").strip()
        if not name or len(name) < 3 or name.lower() in ("animal", "ingots", "joiners", "juice", "kid", "lamb", "other", "unenumerated"):
            continue
        alts = [x.strip() for x in re.split(r"[,;]", alt_s) if x.strip() and len(x.strip()) >= 3]
        if pref and pref.lower() != name.lower():
            alts.insert(0, pref)
        roles = [x.strip() for x in re.split(r"[,;]", role_s) if x.strip() and len(x.strip()) < 25]
        if broader and len(broader) < 25 and not roles:
            roles = [broader]
        upsert(name, alts=alts, roles=roles, notes=note, src="1866 British Customs Commodities List (Danika / HGIS Lab)")

    OUT_PATH.write_text(json.dumps({"descriptions_count": len(descs), "items": items}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Extracted {len(items)} structured Danika/1866 entries + {len(descs)} pharmacopoeia descriptions -> {OUT_PATH}")


if __name__ == "__main__":
    main()
