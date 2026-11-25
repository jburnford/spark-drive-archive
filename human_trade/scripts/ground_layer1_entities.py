#!/usr/bin/env python3
"""
Ground Layer-1 (`human_transcribed`) printed places (502) and commodities (2,066)
strictly against verified local Base World files (ZERO QIDs from memory):

  Places:
    - ceylon/spine/bluebook/trade_place_senses.tsv
    - ceylon/empire-evolution/data/qid_manifest.tsv
    - ceylon/spine/grounding/places_tier1.jsonl, places_tier1b.jsonl, places_tier2.jsonl
    - ceylon/spine/gazetteer/col_places_wikidata.jsonl
    - honors ceylon/spine/grounding/name_rejections.jsonl

  Commodities (Two-Layer Archival SKOS + Multi-Anchor Model):
    - Layer A: Local opaque skos:Concept (htc:0001..htc:2066) preserving printed
      customs heading verbatim, with decomposed processing_state facet,
      substance_head, SITC Rev. 4 broadMatch, and Theodoridis (2018) category.
    - Layer B: Verified Wikidata QID + P1582 source_taxa from ceylon/spine
      (commodity_wd.jsonl, taxon_wd.jsonl, name_decisions.jsonl) + bridge to
      SKOS_from_Custom_Records.xlsx (414 curated 1866 customs concepts).
"""

import csv
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "human_trade"
LAYER1 = BASE / "layer1_human"
NAMES = LAYER1 / "names"
GROUND = LAYER1 / "grounding"
GROUND.mkdir(parents=True, exist_ok=True)

CEYLON_SPINE = Path("/home/jic823/Documents/ceylon/spine")
EMPIRE_DATA = Path("/home/jic823/Documents/ceylon/empire-evolution/data")
SKOS_XLSX = BASE / "raw_sources" / "SKOS_from_Custom_Records.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_rejections():
    rej = set()
    p = CEYLON_SPINE / "grounding" / "name_rejections.jsonl"
    if p.exists():
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            k = norm_key(d.get("key") or d.get("name") or "")
            q = d.get("qid") or ""
            if k and q:
                rej.add((k, q))
    return rej


def load_base_world_places(rejections):
    """Build lookup: norm_key -> verified place record (from local Base World files only)."""
    lookup = {}

    def register(key_raw, qid, label, source, priority, extra=None):
        k = norm_key(key_raw)
        if not k or not qid:
            return
        if (k, qid) in rejections:
            return
        cur = lookup.get(k)
        if cur is None or priority > cur["_prio"]:
            rec = {
                "qid": qid,
                "label": label or key_raw,
                "source_authority": source,
                "_prio": priority,
            }
            if extra:
                rec.update(extra)
            lookup[k] = rec

    # 1. Empire Evolution territories (priority 90)
    ee_path = EMPIRE_DATA / "qid_manifest.tsv"
    ee_by_qid = defaultdict(list)
    if ee_path.exists():
        for r in csv.DictReader(open(ee_path, encoding="utf-8"), delimiter="\t"):
            qid = (r.get("wikidata_id") or "").strip()
            cid = (r.get("colony_id") or "").strip()
            name = (r.get("name") or r.get("canonical_name") or "").strip()
            if qid and cid:
                ee_by_qid[qid].append({
                    "colony_id": cid,
                    "name": name,
                    "start": r.get("established_year", "").strip(),
                    "end": (r.get("end_date") or "").strip()[:4],
                })
            if qid and name:
                register(name, qid, name, "empire_evolution_qid_manifest", 90)
                if r.get("canonical_name"):
                    register(r["canonical_name"], qid, name, "empire_evolution_qid_manifest", 88)

    # 2. Ceylon spine trade_place_senses.tsv (highest priority: 100)
    tps = CEYLON_SPINE / "bluebook" / "trade_place_senses.tsv"
    unlinked_senses = {}
    if tps.exists():
        for r in csv.DictReader(open(tps, encoding="utf-8"), delimiter="\t"):
            k = norm_key(r.get("label_key", ""))
            if r.get("action") == "unlink":
                unlinked_senses[k] = r.get("basis", "")
            elif r.get("action") == "link" and r.get("qid"):
                register(k, r["qid"].strip(), r.get("place_label", ""), "ceylon_trade_place_senses", 100)

    # 3. Ceylon spine places_tier1, tier1b, tier2 (priority 80, 78, 70)
    for fname, prio in [
        ("places_tier1.jsonl", 80),
        ("places_tier1b.jsonl", 78),
        ("places_tier2.jsonl", 70),
    ]:
        fp = CEYLON_SPINE / "grounding" / fname
        if not fp.exists():
            continue
        for line in open(fp, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("status") != "matched":
                continue
            qid = d.get("qid") or ""
            label = d.get("label") or d.get("wd_label") or d.get("key") or ""
            if qid:
                register(d.get("key", ""), qid, label, f"ceylon_spine:{fname}", prio)
                if label:
                    register(label, qid, label, f"ceylon_spine:{fname}", prio - 2)

    # 4. col_places_wikidata.jsonl (priority 65)
    cpw = CEYLON_SPINE / "gazetteer" / "col_places_wikidata.jsonl"
    if cpw.exists():
        for line in open(cpw, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            qid = d.get("qid") or d.get("id") or ""
            label = d.get("label") or ""
            if qid and label:
                register(label, qid, label, "ceylon_gazetteer:col_places_wikidata", 65)
                for al in (d.get("aliases") or [])[:15]:
                    if isinstance(al, str) and len(al) >= 3:
                        register(al, qid, label, "ceylon_gazetteer:col_places_wikidata_alias", 60)

    return lookup, ee_by_qid, unlinked_senses


AGGREGATE_PATTERNS = [
    r"^(world|all countries|total|totals|check|other parts|other countries|other foreign countries|other british possessions|other english ports|other ports(\s+on|\s+qc)?|foreign countries|british possessions|not specified|unknown|miscellaneous|various|deep sea fisheries|whale fisheries.*|northern whale fisheries|southern whale fisheries)$",
    r"^other\s+",
    r"\bexc\b|\bexcluding\b|\bnot elsewhere\b",
]

# Explicit synonym normalizations ONLY mapping printed historical spelling -> key that MUST exist in verified Base World lookup
PLACE_SPELLING_ALIASES = {
    "united states of america": "united states",
    "u s a": "united states",
    "usa": "united states",
    "holland": "netherlands",
    "argentine republic": "argentina",
    "british east indies": "british india",
    "british india madras": "madras",
    "british india bengal": "bengal",
    "british india bombay": "bombay",
    "british india burmah": "burma",
    "british india burma": "burma",
    "british possessions in south africa": "cape of good hope",
    "cape of good hope": "cape colony",
    "great britain": "united kingdom",
    "st pierre": "saint pierre and miquelon",
    "saint pierre": "saint pierre and miquelon",
    "british north america": "canada",
    "new granada": "colombia",
    "monte video": "uruguay",
    "buenos ayres": "argentina",
    "hayti": "haiti",
    "siam": "thailand",
    "persia": "iran",
    "austria hungary": "austria-hungary",
    "austrian territories": "austria-hungary",
    "russia northern ports": "russia",
    "russia southern ports": "russia",
    "russia ports on the black sea": "russia",
    "prussia": "germany",
    "hanseatic towns": "hamburg",
    "turkey in europe": "ottoman empire",
    "turkey in asia": "ottoman empire",
    "turkey": "ottoman empire",
    "egypt": "egypt",
    "west coast of africa": "west africa",
    "british west africa": "west africa",
    "straits settlements": "straits settlements",
    "australasia": "australia",
}


def ground_places(rejections):
    lookup, ee_by_qid, unlinked_senses = load_base_world_places(rejections)
    rows = list(csv.DictReader(open(NAMES / "places.tsv", encoding="utf-8"), delimiter="\t"))

    decisions = []
    review = []
    matched_rows = 0
    agg_rows = 0
    can_port_rows = 0
    unmatched_rows = 0
    total_rows = 0

    for r in rows:
        raw = r["name_as_printed"]
        cnt = int(r["total_rows"])
        total_rows += cnt
        k = norm_key(raw)

        # 1. Check aggregate / non-geographic category
        if any(re.search(pat, k) for pat in AGGREGATE_PATTERNS) or k in unlinked_senses:
            agg_rows += cnt
            decisions.append({
                "name_as_printed": raw,
                "total_rows": cnt,
                "status": "aggregate_category",
                "relation": "aggregate_category",
                "qid": None,
                "wd_label": None,
                "source_authority": "rule:aggregate_or_unlinked_category",
                "confidence": "high",
                "empire_evolution_ids": [],
            })
            continue

        # 2. Direct lookup in verified Base World
        hit = lookup.get(k)
        rel = "exact"
        rule = "direct_base_world"

        # 3. Try historical spelling alias -> still MUST resolve inside verified Base World!
        if not hit and k in PLACE_SPELLING_ALIASES:
            ak = norm_key(PLACE_SPELLING_ALIASES[k])
            hit = lookup.get(ak)
            if hit:
                rel = "close_historical_heading" if k in ("british north america", "british possessions in south africa", "russia northern ports", "russia southern ports", "prussia", "hanseatic towns") else "exact"
                rule = f"historical_alias->{ak}"

        # 4. Canadian customs port suffix pattern (e.g., "Quebec QC", "Kingston ON")
        if not hit and re.search(r"\b(qc|on|nb|ns|pe|mb|bc|ab|sk|nl|yk|nt)$", k):
            base_city = re.sub(r"\s+(qc|on|nb|ns|pe|mb|bc|ab|sk|nl|yk|nt)$", "", k).strip()
            prov = k.split()[-1].upper()
            can_port_rows += cnt
            decisions.append({
                "name_as_printed": raw,
                "total_rows": cnt,
                "status": "canadian_port_queue",
                "relation": "needs_canada_kg_link",
                "qid": None,
                "wd_label": None,
                "source_authority": f"pattern:canadian_customs_port_{prov}",
                "confidence": "pending",
                "parsed_port_name": base_city,
                "parsed_province": prov,
                "empire_evolution_ids": [],
            })
            review.append((cnt, "canadian_port", raw, f"port={base_city}, prov={prov}"))
            continue

        if hit:
            matched_rows += cnt
            qid = hit["qid"]
            ee = ee_by_qid.get(qid, [])
            decisions.append({
                "name_as_printed": raw,
                "total_rows": cnt,
                "status": "matched",
                "relation": rel,
                "qid": qid,
                "wd_label": hit["label"],
                "source_authority": hit["source_authority"],
                "rule": rule,
                "confidence": "high" if rel == "exact" else "medium",
                "empire_evolution_ids": [e["colony_id"] for e in ee],
            })
        else:
            unmatched_rows += cnt
            decisions.append({
                "name_as_printed": raw,
                "total_rows": cnt,
                "status": "needs_review",
                "relation": "unmatched",
                "qid": None,
                "wd_label": None,
                "source_authority": None,
                "confidence": "none",
                "empire_evolution_ids": [],
            })
            review.append((cnt, "unmatched_place", raw, ""))

    with open(GROUND / "places_grounding.jsonl", "w", encoding="utf-8") as fh:
        for d in decisions:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    with open(GROUND / "places_review_queue.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["total_rows", "queue_type", "name_as_printed", "notes"])
        for item in sorted(review, reverse=True):
            w.writerow(item)

    return {
        "unique_places": len(rows),
        "matched_unique": sum(1 for d in decisions if d["status"] == "matched"),
        "aggregate_unique": sum(1 for d in decisions if d["status"] == "aggregate_category"),
        "can_port_unique": sum(1 for d in decisions if d["status"] == "canadian_port_queue"),
        "unmatched_unique": sum(1 for d in decisions if d["status"] == "needs_review"),
        "total_mentions": total_rows,
        "matched_mentions": matched_rows,
        "aggregate_mentions": agg_rows,
        "can_port_mentions": can_port_rows,
        "unmatched_mentions": unmatched_rows,
    }


def load_skos_customs():
    """Load Jim's curated 1866 SKOS_from_Custom_Records.xlsx (414 concepts)."""
    zf = zipfile.ZipFile(SKOS_XLSX)
    ss = []
    if "xl/sharedStrings.xml" in zf.namelist():
        for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", NS):
            ss.append("".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    by_label = {}
    for idx, r in enumerate(root.findall(".//m:sheetData/m:row", NS)):
        if idx == 0:
            continue
        vals = {}
        for c in r.findall("m:c", NS):
            ref = "".join(ch for ch in c.attrib["r"] if ch.isalpha())
            t = c.attrib.get("t")
            v = c.find("m:v", NS)
            val = "" if v is None else (ss[int(v.text)] if t == "s" else (v.text or ""))
            vals[ref] = val.strip()
        concept = vals.get("A", "")
        pref = vals.get("B", "")
        alts = [a.strip() for a in vals.get("C", "").split(",") if a.strip()]
        broader = vals.get("D", "")
        state = vals.get("E", "")
        src_of = vals.get("F", "")
        rec = {
            "skos_concept": concept,
            "prefLabel": pref,
            "broaderConcept": broader,
            "state": state,
            "sourceOf": src_of,
        }
        for lbl in [concept, pref] + alts:
            nk = norm_key(lbl)
            if nk and nk not in by_label:
                by_label[nk] = rec
    return by_label


def load_base_world_commodities(rejections):
    """Load verified Wikidata commodities & taxa from ceylon/spine/grounding/."""
    lookup = {}

    def register(key_raw, qid, label, desc, kind, source_taxa, source, prio):
        k = norm_key(key_raw)
        if not k or not qid or (k, qid) in rejections:
            return
        cur = lookup.get(k)
        if cur is None or prio > cur["_prio"]:
            lookup[k] = {
                "qid": qid,
                "wd_label": label,
                "wd_description": desc,
                "kind": kind,
                "source_taxa": source_taxa or [],
                "source_authority": source,
                "_prio": prio,
            }

    for fname, prio in [
        ("name_decisions.jsonl", 95),
        ("commodity_wd.jsonl", 90),
        ("taxon_wd.jsonl", 80),
    ]:
        fp = CEYLON_SPINE / "grounding" / fname
        if not fp.exists():
            continue
        for line in open(fp, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("status") not in ("matched", "approved"):
                continue
            qid = d.get("qid") or ""
            if not qid:
                continue
            label = d.get("label") or d.get("wd_label") or ""
            desc = d.get("description") or ""
            kind = d.get("kind") or d.get("type") or ""
            taxa = d.get("source_taxa") or []
            register(d.get("key", ""), qid, label, desc, kind, taxa, f"ceylon_spine:{fname}", prio)
            if label:
                register(label, qid, label, desc, kind, taxa, f"ceylon_spine:{fname}:label", prio - 2)
    return lookup


# Controlled processing-state facet extraction (Layer A)
STATE_RULES = [
    ("unenumerated", r"\b(unenumerated|other sorts|not otherwise described|n\.o\.s\.|miscellaneous)\b"),
    ("live", r"\b(living|live|oxen|bulls|cows|calves|horses|mares|geldings|sheep|lambs|swine|hogs|pigs|asses|mules|poultry|horned cattle)\b"),
    ("dressed_tanned", r"\b(tanned|tawed|curried|dressed|morocco|leather)\b"),
    ("wet_salted", r"\b(wet|salted|pickled|in brine|corned)\b"),
    ("dried_cured", r"\b(dry|dried|smoked|cured|salted|bacon|hams)\b"),
    ("sawn_milled", r"\b(sawn|split|planed|dressed|deals|battens|boards|planks|staves|shingles|scantling|laths|meal|flour|bran|oatmeal|ground)\b"),
    ("refined_extract", r"\b(refined|extract|sulphate|acid|oil|spirits|distilled|brandy|rum|whiskey|gin|sugar refined|tallow|stearine|lard|butter|cheese|soap|candles|creosote|tar|pitch|rosin|turpentine)\b"),
    ("raw_unprocessed", r"\b(raw|untanned|undressed|unmanufactured|hewn|rough|unrefined|crude|ore|bark|seeds|nuts|beans|peas|wheat|barley|oats|maize|rye|rice|flax|hemp|jute|wool|cotton|hides|skins|pelts|furs|caoutchouc|gutta|galls|sumac|valonia|myrobalans|cutch|gambier)\b"),
    ("manufactured", r"\b(manufactures|machinery|carriages|hardware|instruments|paper|books|cloth|linen|woollen|silk manufactures|boots|shoes|gloves|apparel|glass|earthenware|china|iron manufactures|watches|clocks)\b"),
]

# Macro rollup -> (SITC Rev 4 division, Theodoridis 5-category, Ghost Acres book domain)
MACRO_RULES = [
    (r"\b(wheat|barley|oats|rye|maize|indian corn|rice|paddy|flour|meal|bran|oatmeal|malt|biscuit|bread|grain|corn)\b", "SITC_04_Cereals", "grain_and_flour", "food_grain"),
    (r"\b(butter|cheese|eggs|bacon|hams|pork|beef|mutton|meat|lard|fish|herring|cod|salmon|cattle|horses|sheep|swine|cows|oxen|calves|poultry|animals living|milk)\b", "SITC_00-03_Animals_Dairy_Meat_Fish", "animals_and_animal_products", "food_animal"),
    (r"\b(sugar|molasses|coffee|tea|cocoa|cacao|spices|pepper|cinnamon|cloves|nutmeg|mace|ginger|fruit|apples|oranges|lemons|raisins|currants|figs|almonds|nuts|potatoes|peas|beans|onions|hops|wine|spirits|rum|brandy|whiskey|beer|ale|tobacco|cigars|snuff|salt|vinegar|honey|maple sugar)\b", "SITC_05-12_Other_Food_Drink_Tobacco", "other_food_drink_spices", "food_colonial_grocery"),
    (r"\b(hide|hides|skin|skins|pelt|pelts|fur|furs|leather|bark for tanner|oak bark|valonia|sumac|shumac|cutch|catechu|gambier|terra japonica|myrobalan|divi divi|wattle|galls)\b", "SITC_21_61_29_Hides_Leather_Tannins", "raw_materials", "tannins_leather"),
    (r"\b(tallow|stearine|palm oil|coconut oil|cocoa-nut oil|train oil|whale|blubber|sperm|linseed|flaxseed|cotton seed|cottonseed|rapeseed|olive oil|castor oil|oil seed|oilseed|rosin|resin|turpentine|soap|candles|wax|beeswax|grease)\b", "SITC_4_22_Fats_Oils_Oilseeds", "raw_materials", "fats_oils_soap"),
    (r"\b(timber|wood|deals|battens|boards|planks|staves|spars|masts|oars|shingles|scantling|laths|mahogany|teak|cedar|oak|pine|fir|spruce|elm|birch|ash|firewood|pit wood|pit props|sleepers|cork|logwood|fustic|dyewood|wood pulp|ashes pot|pearl and pot ash|potash)\b", "SITC_24_Cork_and_Wood", "raw_materials", "timber_forestry"),
    (r"\b(cinchona|peruvian bark|quinine|opium|rhubarb|camphor|ipecac|sarsaparilla|senna|drugs|caoutchouc|india rubber|rubber|gutta percha|gum|gums|lac|shellac|indigo|cochineal|madder|annatto|dye|dyes|alizarin|aniline|alkali|barilla|brimstone|sulphur|saltpetre|nitre|guano|manure|bones|chemical|acid|alum|borax|soda)\b", "SITC_23_29_5_Botanicals_Drugs_Rubber_Chemicals", "raw_materials", "drugs_botanicals_chemicals"),
    (r"\b(cotton|wool|flax|hemp|jute|silk|linen|yarn|rags|coir|esparto|fibre|fiber|tow|hair|bristles|feathers)\b", "SITC_26_65_Textile_Fibres", "raw_materials", "fibres_textiles"),
    (r"\b(iron|copper|tin|lead|zinc|spelter|silver|gold|platina|quicksilver|mercury|antimony|manganese|cobalt|ore|metal|coal|coke|petroleum|paraffin|shale|stone|marble|slate|clay|cement|plumbago|graphite)\b", "SITC_27_28_3_68_Minerals_Metals_Energy", "raw_materials", "minerals_metals_energy"),
    (r"\b(machinery|carriages|hardware|cutlery|clocks|watches|musical instruments|books|paper|glass|earthenware|china|porcelain|boots|shoes|gloves|hats|apparel|manufactures|toys|pictures|prints)\b", "SITC_6-8_Manufactured_Goods", "manufactured_articles", "manufactured_goods"),
]


def classify_commodity_facets(raw: str):
    low = raw.lower()
    state = "unspecified"
    for st, pat in STATE_RULES:
        if re.search(pat, low):
            state = st
            break

    sitc, theo, domain = "SITC_9_Unclassified", "unclassified", "other"
    for pat, s, t, d in MACRO_RULES:
        if re.search(pat, low):
            sitc, theo, domain = s, t, d
            break

    # Extract clean substance head (strip qualifying adjectives/clauses while keeping raw intact)
    head = raw
    head = re.split(r"\s*[-–(:]\s*|\s+not\s+|\s+other\s+than\s+|\s+for\s+", head, maxsplit=1)[0]
    head = re.sub(r"\b(raw|untanned|undressed|unmanufactured|dry|wet|salted|pickled|dressed|tanned|refined|unrefined|crude|unenumerated|other sorts|fresh|green|living)\b", "", head, flags=re.I)
    head = re.sub(r"\s+", " ", head).strip(" ,;-")
    return state, head or raw, sitc, theo, domain


def ground_commodities(rejections):
    bw_comm = load_base_world_commodities(rejections)
    skos_customs = load_skos_customs()
    rows = list(csv.DictReader(open(NAMES / "commodities.tsv", encoding="utf-8"), delimiter="\t"))

    concepts = []
    review = []
    total_rows = 0
    exact_wd_rows = 0
    close_wd_rows = 0
    skos_only_rows = 0
    unmatched_rows = 0

    for idx, r in enumerate(rows, start=1):
        raw = r["commodity_as_printed"]
        cnt = int(r["total_rows"])
        total_rows += cnt
        cid = f"htc:{idx:04d}"
        state, head, sitc, theo, domain = classify_commodity_facets(raw)

        k_full = norm_key(raw)
        k_head = norm_key(head)

        # Check Base World Wikidata (ceylon/spine)
        wd_hit = bw_comm.get(k_full)
        wd_rel = None
        if wd_hit:
            wd_rel = "skos:exactMatch"
        else:
            # Try singular/head
            for cand in [k_full.rstrip("s"), k_head, k_head.rstrip("s")]:
                if cand and cand in bw_comm:
                    wd_hit = bw_comm[cand]
                    wd_rel = "skos:closeMatch" if cand == k_full.rstrip("s") else "skos:broadMatch"
                    break

        # Check Jim's curated 1866 SKOS customs table
        skos_hit = skos_customs.get(k_full) or skos_customs.get(k_head) or skos_customs.get(k_head.rstrip("s"))

        if wd_hit and wd_rel == "skos:exactMatch":
            exact_wd_rows += cnt
            status = "grounded_exact"
        elif wd_hit:
            close_wd_rows += cnt
            status = "grounded_substance_head"
        elif skos_hit:
            skos_only_rows += cnt
            status = "skos_1866_bridged_needs_wd"
            review.append((cnt, "needs_wd_from_skos", cid, raw, head, skos_hit["skos_concept"], sitc))
        else:
            unmatched_rows += cnt
            status = "local_concept_only_needs_wd"
            review.append((cnt, "needs_wd_and_dict", cid, raw, head, "", sitc))

        concepts.append({
            "concept_id": cid,
            "rdf_type": "skos:Concept",
            "skos_prefLabel": raw,
            "total_rows": cnt,
            "facets": {
                "substance_head": head,
                "processing_state": state,
                "ghost_acres_domain": domain,
                "theodoridis_category": theo,
            },
            "skos_broadMatch_sitc": sitc,
            "wikidata_anchor": {
                "mapping_relation": wd_rel,
                "qid": wd_hit["qid"],
                "wd_label": wd_hit["wd_label"],
                "wd_description": wd_hit["wd_description"],
                "source_taxa": wd_hit["source_taxa"],
                "source_authority": wd_hit["source_authority"],
            } if wd_hit else None,
            "skos_1866_bridge": skos_hit,
            "status": status,
        })

    with open(GROUND / "commodities_concepts.jsonl", "w", encoding="utf-8") as fh:
        for c in concepts:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    with open(GROUND / "commodities_review_queue.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["total_rows", "queue_type", "concept_id", "commodity_as_printed", "substance_head", "skos_1866_concept", "sitc_broad"])
        for item in sorted(review, reverse=True):
            w.writerow(item)

    return {
        "unique_commodities": len(rows),
        "exact_wd_unique": sum(1 for c in concepts if c["status"] == "grounded_exact"),
        "close_wd_unique": sum(1 for c in concepts if c["status"] == "grounded_substance_head"),
        "skos_only_unique": sum(1 for c in concepts if c["status"] == "skos_1866_bridged_needs_wd"),
        "unmatched_unique": sum(1 for c in concepts if c["status"] == "local_concept_only_needs_wd"),
        "total_rows": total_rows,
        "exact_wd_rows": exact_wd_rows,
        "close_wd_rows": close_wd_rows,
        "skos_only_rows": skos_only_rows,
        "unmatched_rows": unmatched_rows,
        "by_domain": Counter(c["facets"]["ghost_acres_domain"] for c in concepts),
        "rows_by_domain": Counter({d: sum(c["total_rows"] for c in concepts if c["facets"]["ghost_acres_domain"] == d) for d in set(c["facets"]["ghost_acres_domain"] for c in concepts)}),
    }


def main():
    rej = load_rejections()
    p_stats = ground_places(rej)
    c_stats = ground_commodities(rej)

    lines = ["# Layer-1 Human Trade Entity Grounding Report\n\n"]
    lines.append("All QIDs strictly read from verified local Base World files (`ceylon/spine`, `empire-evolution`, `col_matching`) — zero QIDs from memory.\n\n")

    lines.append("## 1. Places & Polities (502 Unique Printed Names)\n")
    tm = p_stats["total_mentions"]
    lines.append(f"- **Matched to verified Base World QID:** {p_stats['matched_unique']} places — **{p_stats['matched_mentions']:,} / {tm:,} mentions ({p_stats['matched_mentions']/tm*100:.1f}%)**\n")
    lines.append(f"- **Explicit Aggregate / Non-Geographic Categories (`All Countries`, `World`, `Other Foreign Countries`, etc.):** {p_stats['aggregate_unique']} labels — **{p_stats['aggregate_mentions']:,} mentions ({p_stats['aggregate_mentions']/tm*100:.1f}%)**\n")
    lines.append(f"- **Canadian Customs Ports (`<City> QC/ON/...` queued for Canada KG link):** {p_stats['can_port_unique']} ports — **{p_stats['can_port_mentions']:,} mentions ({p_stats['can_port_mentions']/tm*100:.1f}%)**\n")
    lines.append(f"- **Remaining unmatched places (`places_review_queue.tsv`):** {p_stats['unmatched_unique']} places — **{p_stats['unmatched_mentions']:,} mentions ({p_stats['unmatched_mentions']/tm*100:.1f}%)**\n\n")

    lines.append("## 2. Two-Layer Archival Commodities (2,066 Unique Printed Headings)\n")
    ct = c_stats["total_rows"]
    lines.append(f"- **Layer A (Local Archival `skos:Concept` + facets + SITC/Theodoridis rollup):** **2,066 / 2,066 (100%)**\n")
    lines.append(f"- **Layer B — Exact Wikidata Match (from `ceylon/spine`):** {c_stats['exact_wd_unique']} concepts — **{c_stats['exact_wd_rows']:,} rows ({c_stats['exact_wd_rows']/ct*100:.1f}%)**\n")
    lines.append(f"- **Layer B — Close/Broad Substance-Head Match (Wikidata + `P1582` taxa):** {c_stats['close_wd_unique']} concepts — **{c_stats['close_wd_rows']:,} rows ({c_stats['close_wd_rows']/ct*100:.1f}%)**\n")
    lines.append(f"- **Bridged via 1866 `SKOS_from_Custom_Records.xlsx` (ready for Wikidata/Simmonds lookup):** {c_stats['skos_only_unique']} concepts — **{c_stats['skos_only_rows']:,} rows ({c_stats['skos_only_rows']/ct*100:.1f}%)**\n")
    lines.append(f"- **Local Concept Only (queued for Wikidata + Simmonds/McCulloch/Ure grounding):** {c_stats['unmatched_unique']} concepts — **{c_stats['unmatched_rows']:,} rows ({c_stats['unmatched_rows']/ct*100:.1f}%)**\n\n")

    lines.append("### Layer-1 Rows by Ghost Acres Book Domain\n")
    for dom, cnt in c_stats["rows_by_domain"].most_common():
        lines.append(f"- `{dom}`: **{cnt:,}** rows ({c_stats['by_domain'][dom]} concepts)\n")

    rep = "".join(lines)
    (GROUND / "GROUNDING_REPORT.md").write_text(rep, encoding="utf-8")
    print(rep)


if __name__ == "__main__":
    main()
