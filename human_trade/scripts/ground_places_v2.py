#!/usr/bin/env python3
"""
Ground all Layer-1 (`human_transcribed`) printed places (499 unique names) using:
  1. Verified Base World files (`ceylon/spine` + `empire-evolution`)
  2. Verified Canadian places (`Canada-History-Knowledge-Graph/wikidata_grounding`)
  3. Local Wikidata 2026-11-09 slim Parquet dump (`/mnt/data/jic823/wikidata/20261109/slim/*.parquet`) via DuckDB
  4. Year-aware `empire.py` `IN_POLITY` resolution for every `(place_qid, year)` pair.

ZERO QIDs from memory: every QID comes strictly from verified local files or DuckDB query results
against the 2026-11-09 Wikidata snapshot.
"""

import os
import csv
import gzip
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

BASE = Path(__file__).resolve().parents[2] / "human_trade"
LAYER1 = BASE / "layer1_human"
NAMES = LAYER1 / "names"
GROUND = LAYER1 / "grounding"
GROUND.mkdir(parents=True, exist_ok=True)

CEYLON_SPINE = Path("/home/jic823/Documents/ceylon/spine")
EMPIRE_DATA = Path("/home/jic823/Documents/ceylon/empire-evolution/data")
CANADA_WD = Path("/home/jic823/Documents/Canada-History-Knowledge-Graph/wikidata_grounding")
WD_SLIM_GLOB = os.environ.get("OE_WD_SLIM_GLOB", "/mnt/data/jic823/wikidata/20261109/slim/*.parquet")
WD_SNAPSHOT = "2026-11-09"

sys.path.insert(0, str(CEYLON_SPINE))
import empire as empire_mod


def norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    # Accent folding for Quebec/French port names
    tr = str.maketrans("éèêëàâäîïôöùûüçñ", "eeeeaaaiioouuucn")
    s = s.translate(tr)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


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

    ee_path = EMPIRE_DATA / "qid_manifest.tsv"
    if ee_path.exists():
        for r in csv.DictReader(open(ee_path, encoding="utf-8"), delimiter="\t"):
            qid = (r.get("wikidata_id") or "").strip()
            name = (r.get("name") or r.get("canonical_name") or "").strip()
            if qid and name:
                register(name, qid, name, "empire_evolution_qid_manifest", 90)
                if r.get("canonical_name"):
                    register(r["canonical_name"], qid, name, "empire_evolution_qid_manifest", 88)

    tps = CEYLON_SPINE / "bluebook" / "trade_place_senses.tsv"
    if tps.exists():
        for r in csv.DictReader(open(tps, encoding="utf-8"), delimiter="\t"):
            k = norm_key(r.get("label_key", ""))
            if r.get("action") == "link" and r.get("qid"):
                register(k, r["qid"].strip(), r.get("place_label", ""), "ceylon_trade_place_senses", 100)

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

    return lookup


def load_canada_kg_places():
    """Index verified Canadian CSDs/communities by (norm_name, prov) -> list of verified dicts."""
    idx = defaultdict(list)

    def add(name, prov, qid, label, desc, source, prio, lat=None, lon=None):
        if not name or not prov or not qid:
            return
        # Clean CSD suffixes like ", C", ", T-V", ", VL", " (not inc)", ", TP", ", M", ", P"
        clean = re.sub(r"\s*\([^)]*\)", "", name)
        clean = re.sub(r",\s*[A-Z]{1,3}(?:-[A-Z]{1,3})?$", "", clean).strip()
        k = norm_key(clean)
        if not k:
            return
        rec = {
            "qid": qid,
            "label": label or clean,
            "desc": desc or "",
            "source_authority": source,
            "prio": prio,
            "lat": lat,
            "lon": lon,
        }
        idx[(k, prov.upper())].append(rec)
        # Also index by wikidata_label
        kl = norm_key(label or "")
        if kl and kl != k:
            idx[(kl, prov.upper())].append(rec)

    # 1. csd_verified_matches.jsonl
    p1 = CANADA_WD / "csd_verified_matches.jsonl"
    if p1.exists():
        for line in open(p1, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("status") != "matched" or not d.get("wikidata_qid"):
                continue
            prov = (d.get("csd_id") or "")[:2].upper()
            add(d.get("csd_name", ""), prov, d["wikidata_qid"], d.get("wikidata_label", ""),
                d.get("wikidata_desc", ""), "canada_kg:csd_verified_matches", 95)

    # 2. presence_verified_matches.jsonl
    p2 = CANADA_WD / "presence_verified_matches.jsonl"
    if p2.exists():
        for line in open(p2, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("status") != "matched" or not d.get("wikidata_qid"):
                continue
            prov = (d.get("province") or (d.get("csd_id") or "")[:2]).upper()
            nm = d.get("place_name") or d.get("csd_name") or d.get("name") or ""
            add(nm, prov, d["wikidata_qid"], d.get("wikidata_label", ""),
                d.get("wikidata_desc", ""), "canada_kg:presence_verified_matches", 90)

    # 3. csd_wikidata_matches.csv
    p3 = CANADA_WD / "csd_wikidata_matches.csv"
    if p3.exists():
        for r in csv.DictReader(open(p3, encoding="utf-8")):
            qid = (r.get("wikidata_qid") or "").strip()
            if not qid:
                continue
            prov = (r.get("csd_id") or "")[:2].upper()
            lat = float(r["our_lat"]) if r.get("our_lat") else None
            lon = float(r["our_lon"]) if r.get("our_lon") else None
            add(r.get("csd_name", ""), prov, qid, r.get("wikidata_label", ""),
                r.get("wikidata_types", ""), "canada_kg:csd_wikidata_matches", 85, lat, lon)

    return idx


def collect_place_coords_and_years():
    """Read median lat/lon and year span per printed place from Layer-1 observations."""
    coords = defaultdict(list)
    years = defaultdict(set)
    with gzip.open(LAYER1 / "human_trade_observations.tsv.gz", "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r["row_kind"] in ("qa_check_row", "blank"):
                continue
            yr = int(r["year_start"]) if r["year_start"].isdigit() else None
            orig = r["origin_as_printed"].strip()
            dest = r["destination_as_printed"].strip()
            if orig:
                if yr:
                    years[orig].add(yr)
                if r["orig_from_lat"] and r["orig_from_lon"]:
                    try:
                        la, lo = float(r["orig_from_lat"]), float(r["orig_from_lon"])
                        if -90 <= la <= 90 and -180 <= lo <= 180 and (la != 0 or lo != 0):
                            coords[orig].append((la, lo))
                    except ValueError:
                        pass
            if dest:
                if yr:
                    years[dest].add(yr)
                if r["orig_to_lat"] and r["orig_to_lon"]:
                    try:
                        la, lo = float(r["orig_to_lat"]), float(r["orig_to_lon"])
                        if -90 <= la <= 90 and -180 <= lo <= 180 and (la != 0 or lo != 0):
                            coords[dest].append((la, lo))
                    except ValueError:
                        pass
    med_coords = {}
    for k, pts in coords.items():
        lats = sorted(p[0] for p in pts)
        lons = sorted(p[1] for p in pts)
        med_coords[k] = (lats[len(lats) // 2], lons[len(lons) // 2])
    return med_coords, years


AGGREGATE_PATTERNS = [
    r"^(world|all countries|total|totals|check|other parts|other countries|other foreign countries|other british possessions|other english ports|other ports(\s+on|\s+qc)?|foreign countries|british possessions|not specified|unknown|miscellaneous|various|deep sea fisheries|whale fisheries.*|northern whale fisheries|southern whale fisheries|north american whale fisheries|british whale fisheries|channel islands|wreck|prize goods|from the fisheries|fisheries)$",
    r"^other\s+",
    r"\bexc\b|\bexcluding\b|\bnot elsewhere\b",
]

# Pure spelling normalizations -> target label to look up in verified Base World / Wikidata (NO QIDs hardcoded!)
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
    "british possessions in south africa": "cape colony",
    "cape of good hope": "cape colony",
    "great britain": "united kingdom",
    "st pierre": "saint pierre and miquelon",
    "saint pierre": "saint pierre and miquelon",
    "st pierre miquelon": "saint pierre and miquelon",
    "st pierre et miquelon": "saint pierre and miquelon",
    "british north america": "canada",
    "new granada": "colombia",
    "monte video": "uruguay",
    "buenos ayres": "argentina",
    "hayti": "haiti",
    "siam": "thailand",
    "persia": "iran",
    "austria hungary": "austria-hungary",
    "austrian territories": "austria-hungary",
    "hanseatic towns": "hanseatic league",
    "hanse towns": "hanseatic league",
    "british west india islands": "british west indies",
    "british w indies": "british west indies",
    "spanish w indies": "spanish west indies",
    "spanish west indies": "spanish west indies",
    "danish west india islands": "danish west indies",
    "french west india islands": "french west indies",
    "dutch west india islands": "dutch west indies",
    "australasia victoria": "victoria",
    "australasia new south wales": "new south wales",
    "australasia south australia": "south australia",
    "australasia tasmania": "tasmania",
    "australasia queensland": "queensland",
    "australasia western australia": "western australia",
    "australasia new zealand": "new zealand",
    "british australia": "australia",
    "newfoundland": "newfoundland",
    "porto rico": "puerto rico",
    "st helena": "saint helena",
    "st thomas": "saint thomas",
    "st domingo": "santo domingo",
    "west coast of africa": "west africa",
    "british west africa": "west africa",
    "french possessions in west africa": "french west africa",
    "portuguese possessions in west africa": "portuguese west africa",
    "canary islands": "canary islands",
    "azores": "azores",
    "madeira": "madeira",
    "ionian islands": "ionian islands",
    "malta and gozo": "malta",
    "gibraltar": "gibraltar",
    "channel islands": "channel islands",
    "prussia": "prussia",
    "hanover": "hanover",
    "oldenburg": "oldenburg",
    "mecklenburg": "mecklenburg",
    "bremen": "bremen",
    "hamburg": "hamburg",
    "lubeck": "lubeck",
    "schleswig holstein": "schleswig-holstein",
    "sardinia": "kingdom of sardinia",
    "tuscany": "tuscany",
    "papal territories": "papal states",
    "two sicilies": "kingdom of the two sicilies",
    "venetia": "veneto",
    "wallachia and moldavia": "danubian principalities",
    "roumania": "romania",
    "servia": "serbia",
    "morocco": "morocco",
    "algeria": "algeria",
    "tunis": "tunisia",
    "tripoli": "tripoli",
    "java": "java",
    "sumatra": "sumatra",
    "philippine islands": "philippines",
    "philippine and ladrone islands": "philippines",
    "falkland islands": "falkland islands",
    "british guiana": "british guiana",
    "dutch guiana": "suriname",
    "french guiana": "french guiana",
    "british honduras": "british honduras",
    "central america": "central america",
    "cuba": "cuba",
    "jamaica": "jamaica",
    "barbadoes": "barbados",
    "trinidad": "trinidad",
    "trinidad and tobago": "trinidad and tobago",
    "demerara": "demerara",
    "bermuda": "bermuda",
    "bermudas": "bermuda",
    "bahamas": "bahamas",
    "prince edward island": "prince edward island",
    "nova scotia": "nova scotia",
    "new brunswick": "new brunswick",
    "cape breton": "cape breton island",
    "hudson s bay": "hudson bay",
    "hudsons bay": "hudson bay",
    "british columbia": "british columbia",
    "vancouver island": "vancouver island",
    "manitoba": "manitoba",
    "labrador": "labrador",
    "greenland": "greenland",
    "iceland": "iceland",
    "norway": "norway",
    "sweden": "sweden",
    "denmark": "denmark",
    "russia": "russia",
    "belgium": "belgium",
    "france": "france",
    "spain": "spain",
    "portugal": "portugal",
    "italy": "italy",
    "greece": "greece",
    "egypt": "egypt",
    "brazil": "brazil",
    "chili": "chile",
    "chile": "chile",
    "peru": "peru",
    "mexico": "mexico",
    "venezuela": "venezuela",
    "ecuador": "ecuador",
    "bolivia": "bolivia",
    "uruguay": "uruguay",
    "paraguay": "paraguay",
    "china": "china",
    "japan": "japan",
    "hong kong": "hong kong",
    "ceylon": "ceylon",
    "mauritius": "mauritius",
    "natal": "colony of natal",
    "sierra leone": "sierra leone",
    "gold coast": "gold coast",
    "gambia": "the gambia",
    "lagos": "lagos",
    "zanzibar": "zanzibar",
    "madagascar": "madagascar",
    "aden": "aden",
    "strait settlements": "straits settlements",
    "straits settlements": "straits settlements",
    "singapore": "singapore",
    "penang": "penang",
}

# Sub-regional customs divisions -> parent polity label (relation = part_of_polity)
SUBREGION_TO_PARENT = {
    "united states north atlantic ports": "united states",
    "united states of america atlantic ports": "united states",
    "united states of america pacific ports": "united states",
    "united states on the atlantic": "united states",
    "united states on the pacific": "united states",
    "united states atlantic ports": "united states",
    "united states pacific ports": "united states",
    "russia northern ports": "russia",
    "russia southern ports": "russia",
    "russia ports on the black sea": "russia",
    "russia ports within the baltic": "russia",
    "russia ports without the baltic": "russia",
    "turkey asiatic": "ottoman empire",
    "turkey european": "ottoman empire",
    "turkey proper": "ottoman empire",
    "turkey in europe": "ottoman empire",
    "turkey in asia": "ottoman empire",
    "turkey": "ottoman empire",
    "spain and balearic islands": "spain",
    "spain and the balearic islands": "spain",
    "spain and canaries": "spain",
    "portugal proper": "portugal",
    "denmark proper": "denmark",
    "france ports on the atlantic": "france",
    "france ports on the mediterranean": "france",
    "british india bombay": "bombay",
    "british india bengal": "bengal",
    "british india madras": "madras",
    "british india burmah": "burma",
    "british india burma": "burma",
}

# Explicit compound customs headings -> list of component place labels (relation = multi_place_aggregate)
COMPOUND_PLACES = {
    "montreal and quebec": ["montreal", "quebec city"],
    "east india company territories and ceylon": ["british india", "ceylon"],
    "bombay and scinde": ["bombay", "sindh"],
    "british india bombay and scinde": ["bombay", "sindh"],
    "british india bengal and burmah": ["bengal", "burma"],
    "british india bengal and burma": ["bengal", "burma"],
    "sweden and norway": ["sweden", "norway"],
    "norway and sweden": ["norway", "sweden"],
    "australia and new zealand": ["australia", "new zealand"],
    "new south wales and queensland": ["new south wales", "queensland"],
    "java and madura": ["java", "madura island"],
    "syria and palestine": ["syria", "palestine"],
    "hayti and st domingo": ["haiti", "dominican republic"],
    "st pierre and miquelon": ["saint pierre and miquelon"],
    "trinidad and tobago": ["trinidad", "tobago"],
    "antigua and barbuda": ["antigua", "barbuda"],
    "newfoundland and coast of labrador": ["newfoundland", "labrador"],
    "newfoundland and labrador": ["newfoundland", "labrador"],
    "nova scotia and cape breton": ["nova scotia", "cape breton island"],
    "canada and newfoundland": ["canada", "newfoundland"],
    "portugal azores and madeira": ["portugal", "azores", "madeira"],
    "spain and canary islands": ["spain", "canary islands"],
    "austria and hungary": ["austria", "hungary"],
    "china and hong kong": ["china", "hong kong"],
    "argentine republic and uruguay": ["argentina", "uruguay"],
}

# Historical Ontario/Quebec customs port spelling aliases (name only, ZERO QIDs!)
CANADIAN_PORT_ALIASES = {
    ("quebec", "QC"): ["quebec city", "quebec"],
    ("montreal", "QC"): ["montreal"],
    ("st johns", "QC"): ["saint jean sur richelieu", "saint jean", "st johns"],
    ("gaspe", "QC"): ["gaspe"],
    ("dunville", "ON"): ["dunnville"],
    ("stanley", "ON"): ["port stanley"],
    ("dover", "ON"): ["port dover"],
    ("hope", "ON"): ["port hope"],
    ("burwell", "ON"): ["port burwell"],
    ("rowan", "ON"): ["port rowan"],
    ("dalhousie", "ON"): ["port dalhousie"],
    ("colborne", "ON"): ["port colborne"],
    ("credit", "ON"): ["port credit"],
    ("milford", "ON"): ["port milford", "milford"],
    ("clifton", "ON"): ["niagara falls", "clifton"],
    ("philipsburgh", "QC"): ["philipsburg", "saint armand"],
    ("frelighsburgh", "QC"): ["frelighsburg"],
    ("morrisburgh", "ON"): ["morrisburg"],
    ("amherstburgh", "ON"): ["amherstburg"],
    ("wallaceburgh", "ON"): ["wallaceburg"],
    ("russeltown", "QC"): ["russelltown", "havelock"],
    ("st regis", "QC"): ["saint regis", "akwesasne"],
    ("amherst", "ON"): ["amherstburg", "amherst island"],
    ("sandwich", "ON"): ["sandwich", "windsor"],
    ("cramahe", "ON"): ["cramahe"],
    ("darlington", "ON"): ["darlington", "clarington"],
    ("stamford", "ON"): ["stamford", "niagara falls"],
    ("chippawa", "ON"): ["chippawa", "niagara falls"],
    ("queenston", "ON"): ["queenston"],
    ("new carlisle", "QC"): ["new carlisle"],
    ("sault ste marie", "ON"): ["sault ste marie"],
    ("three rivers", "QC"): ["trois rivieres"],
    ("trois rivieres", "QC"): ["trois rivieres"],
    ("riviere aux raisins", "ON"): ["lancaster"],
    ("coteau du lac", "QC"): ["coteau du lac"],
    ("bytown", "ON"): ["ottawa"],
    ("penetanquishene", "ON"): ["penetanguishene"],
    ("newcastle", "ON"): ["newcastle"],
    ("oakville", "ON"): ["oakville"],
    ("oshawa", "ON"): ["oshawa"],
    ("owens sound", "ON"): ["owen sound"],
    ("owen sound", "ON"): ["owen sound"],
    ("kincardine", "ON"): ["kincardine"],
    ("collingwood", "ON"): ["collingwood"],
    ("saugeen", "ON"): ["saugeen shores", "southampton"],
    ("potton", "QC"): ["potton"],
    ("georgeville", "QC"): ["georgeville", "stanstead"],
    ("hereford", "QC"): ["east hereford", "saint hermenegilde"],
    ("beauce", "QC"): ["beauceville", "saint georges"],
    ("rimouski", "QC"): ["rimouski"],
    ("isle verte", "QC"): ["l isle verte"],
    ("sorel", "QC"): ["sorel tracy", "sorel"],
    ("st hyacinthe", "QC"): ["saint hyacinthe"],
    ("sherbrooke", "QC"): ["sherbrooke"],
    ("dundee", "QC"): ["dundee"],
    ("hemmingford", "QC"): ["hemmingford"],
    ("clarenceville", "QC"): ["clarenceville"],
    ("huntingdon", "QC"): ["huntingdon"],
    ("lacolle", "QC"): ["lacolle"],
    ("sutton", "QC"): ["sutton"],
    ("coaticook", "QC"): ["coaticook"],
    ("stanstead", "QC"): ["stanstead"],
}

BAD_DESC_RE = re.compile(
    r"\b(film|movie|song|album|single|band|musician|singer|actor|actress|politician|painter|writer|novel|"
    r"book|poem|television|tv series|episode|video game|comic|magazine|newspaper|painting|sculpture|"
    r"given name|family name|surname|disambiguation|wikimedia|electoral district|riding|constituency|"
    r"railway station|train station|airport|university|college|school|church|cathedral|ship|vessel|frigate|"
    r"battleship|horse|racehorse|crater|asteroid|genus|species|family of|person|human|company|brand)\b",
    re.I,
)

GOOD_GEO_DESC_RE = re.compile(
    r"\b(city|town|village|municipality|hamlet|community|port|harbour|harbor|island|islands|country|"
    r"sovereign state|colony|dominion|province|state|territory|region|kingdom|empire|republic|protectorate|"
    r"archipelago|peninsula|bay|strait|coast|presidency|canton|parish|township|county|borough|settlement|"
    r"former|historical|confederation|duchy|principality|overseas|dependency|possession|subdivision|place|"
    r"unincorporated|neighbourhood|neighborhood|district|prefecture|federation|league|free city)\b",
    re.I,
)

PROV_FULL = {
    "QC": "quebec", "ON": "ontario", "NB": "new brunswick", "NS": "nova scotia",
    "PE": "prince edward island", "MB": "manitoba", "BC": "british columbia",
    "AB": "alberta", "SK": "saskatchewan", "NL": "newfoundland",
}


def query_wikidata_places(search_terms: set):
    """Single DuckDB scan over Wikidata 2026-11-09 slim Parquet dump for all target labels."""
    clean_terms = sorted({t.lower().strip() for t in search_terms if t and len(t.strip()) >= 2})
    if not clean_terms:
        return {}
    print(f"Querying Wikidata {WD_SNAPSHOT} slim Parquet for {len(clean_terms)} place terms...", flush=True)
    con = duckdb.connect()
    con.execute("CREATE TEMP TABLE want(term VARCHAR)")
    con.executemany("INSERT INTO want VALUES (?)", [(t,) for t in clean_terms])

    sql = f"""
    SELECT
        lower(label_en) AS lkey,
        qid,
        label_en,
        description_en,
        sitelinks,
        lat,
        lon,
        instance_of,
        country
    FROM '{WD_SLIM_GLOB}'
    WHERE lower(label_en) IN (SELECT term FROM want)
      AND (sitelinks >= 1 OR lat IS NOT NULL)
    """
    rows = con.execute(sql).fetchall()
    by_term = defaultdict(list)
    for lkey, qid, label_en, desc_en, sitelinks, lat, lon, inst, country in rows:
        by_term[lkey].append({
            "qid": qid,
            "label": label_en,
            "desc": desc_en or "",
            "sitelinks": int(sitelinks or 0),
            "lat": lat,
            "lon": lon,
            "instance_of": list(inst) if inst is not None else [],
            "country": list(country) if country is not None else [],
        })
    print(f"  Retrieved {len(rows):,} raw candidate rows across {len(by_term):,} terms.", flush=True)
    return by_term


def pick_best_wd_place(candidates, require_canada=False, prov_hint=None, target_coords=None):
    scored = []
    for c in candidates:
        desc = c["desc"]
        if BAD_DESC_RE.search(desc):
            continue
        is_geo = bool(GOOD_GEO_DESC_RE.search(desc)) or (c["lat"] is not None and c["lon"] is not None)
        if not is_geo:
            continue
        countries = set(c["country"])
        if require_canada:
            if "Q16" not in countries and "canada" not in desc.lower() and (not prov_hint or PROV_FULL.get(prov_hint, "") not in desc.lower()):
                continue
        score = c["sitelinks"] * 2.0
        if GOOD_GEO_DESC_RE.search(desc):
            score += 40.0
        if c["lat"] is not None:
            score += 20.0
        if prov_hint:
            pf = PROV_FULL.get(prov_hint, "")
            if pf and pf in desc.lower():
                score += 120.0
            elif any(other_p in desc.lower() for code, other_p in PROV_FULL.items() if code != prov_hint):
                score -= 200.0
        if target_coords and c["lat"] is not None and c["lon"] is not None:
            dist = haversine_km(target_coords[0], target_coords[1], c["lat"], c["lon"])
            if dist < 50:
                score += 150.0
            elif dist < 200:
                score += 60.0
            elif dist > 1500 and require_canada:
                score -= 250.0
        if require_canada and "Q16" in countries:
            score += 50.0
        scored.append((score, c))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def main():
    rejections = load_rejections()
    bw_places = load_base_world_places(rejections)
    ca_kg = load_canada_kg_places()
    med_coords, place_years = collect_place_coords_and_years()

    places_in = list(csv.DictReader(open(NAMES / "places.tsv", encoding="utf-8"), delimiter="\t"))

    # Pre-scan to build the full set of terms we need from Wikidata slim dump
    wd_terms = set()
    port_re = re.compile(r"^(.+?)\s+(QC|ON|NB|NS|PE|MB|BC|AB|SK|NL)$")

    for r in places_in:
        raw = r["name_as_printed"].strip()
        k = norm_key(raw)
        m = port_re.match(raw)
        if m:
            pname, prov = norm_key(m.group(1)), m.group(2)
            for cand in CANADIAN_PORT_ALIASES.get((pname, prov), [pname, f"port {pname}"]):
                wd_terms.add(cand)
                wd_terms.add(cand.replace(" ", "-"))
        else:
            wd_terms.add(k)
            if k in PLACE_SPELLING_ALIASES:
                wd_terms.add(PLACE_SPELLING_ALIASES[k])
            if k in SUBREGION_TO_PARENT:
                wd_terms.add(SUBREGION_TO_PARENT[k])
            if k in COMPOUND_PLACES:
                for comp in COMPOUND_PLACES[k]:
                    wd_terms.add(comp)
            # Also handle "British <X>" or "<X> Islands" or "Port of <X>"
            if k.startswith("port of "):
                wd_terms.add(k[8:])

    wd_by_term = query_wikidata_places(wd_terms)

    def resolve_single_place(raw_label, target_coords=None):
        k = norm_key(raw_label)
        k_alias = norm_key(PLACE_SPELLING_ALIASES.get(k, k))
        # 1. Verified Base World (ceylon/spine + empire-evolution)
        if k in bw_places:
            hit = bw_places[k]
            return {
                "qid": hit["qid"], "label": hit["label"],
                "source_authority": hit["source_authority"],
                "match_method": "base_world_exact",
            }
        if k_alias in bw_places:
            hit = bw_places[k_alias]
            return {
                "qid": hit["qid"], "label": hit["label"],
                "source_authority": hit["source_authority"],
                "match_method": "base_world_alias",
            }
        # 2. Local Wikidata 2026-11-09 slim Parquet
        cands = wd_by_term.get(k_alias, []) or wd_by_term.get(k, [])
        if cands:
            best = pick_best_wd_place(cands, require_canada=False, target_coords=target_coords)
            if best:
                return {
                    "qid": best["qid"], "label": best["label"],
                    "description": best["desc"],
                    "lat": best["lat"], "lon": best["lon"],
                    "source_authority": f"wikidata_slim:{WD_SNAPSHOT}",
                    "match_method": "wikidata_slim_exact",
                }
        return None

    results = []
    review_queue = []
    stats = Counter()
    mention_stats = Counter()
    newly_resolved_audit = []

    for r in places_in:
        raw = r["name_as_printed"].strip()
        cnt = int(r["total_rows"])
        k = norm_key(raw)
        tc = med_coords.get(raw)
        yrs = sorted(place_years.get(raw, []))
        yr_span = [yrs[0], yrs[-1]] if yrs else []

        rec = {
            "name_as_printed": raw,
            "norm_key": k,
            "total_rows": cnt,
            "origin_rows": int(r["origin_rows"]),
            "destination_rows": int(r["destination_rows"]),
            "year_span": yr_span,
        }

        # 1. Explicit aggregate / non-geo
        if any(re.search(pat, k) for pat in AGGREGATE_PATTERNS):
            rec.update({"status": "aggregate_category", "match_relation": "non_geographic_aggregate"})
            stats["aggregate_category"] += 1
            mention_stats["aggregate_category"] += cnt
            results.append(rec)
            continue

        # 2. Compound customs headings -> multi_place_aggregate
        if k in COMPOUND_PLACES:
            comps = []
            for c_lbl in COMPOUND_PLACES[k]:
                h = resolve_single_place(c_lbl)
                if h:
                    comps.append({"label": h["label"], "qid": h["qid"], "source_authority": h["source_authority"]})
            if len(comps) == 1:
                rec.update({
                    "status": "matched",
                    "match_relation": "skos:exactMatch",
                    "qid": comps[0]["qid"],
                    "wd_label": comps[0]["label"],
                    "source_authority": comps[0]["source_authority"],
                    "match_method": "compound_single_alias",
                })
                stats["matched"] += 1
                mention_stats["matched"] += cnt
                newly_resolved_audit.append((cnt, raw, comps[0]["qid"], comps[0]["label"], "compound_single"))
                results.append(rec)
                continue
            elif len(comps) >= 2:
                rec.update({
                    "status": "matched_compound",
                    "match_relation": "multi_place_aggregate",
                    "component_places": comps,
                    "source_authority": ";".join(sorted({c["source_authority"] for c in comps})),
                })
                stats["matched_compound"] += 1
                mention_stats["matched_compound"] += cnt
                newly_resolved_audit.append((cnt, raw, "+".join(c["qid"] for c in comps), " & ".join(c["label"] for c in comps), "multi_place"))
                results.append(rec)
                continue

        # 3. Subregion of parent polity (e.g. United States North Atlantic Ports, Turkey Asiatic)
        if k in SUBREGION_TO_PARENT:
            parent = resolve_single_place(SUBREGION_TO_PARENT[k])
            if parent:
                rec.update({
                    "status": "matched",
                    "match_relation": "part_of_polity",
                    "qid": parent["qid"],
                    "wd_label": parent["label"],
                    "source_authority": parent["source_authority"],
                    "match_method": "subregion_to_parent_polity",
                })
                stats["matched"] += 1
                mention_stats["matched"] += cnt
                newly_resolved_audit.append((cnt, raw, parent["qid"], parent["label"], "part_of_polity"))
                results.append(rec)
                continue

        # 4. Canadian customs port (<Name> QC/ON/...)
        m = port_re.match(raw)
        if m:
            pname, prov = norm_key(m.group(1)), m.group(2)
            cand_names = CANADIAN_PORT_ALIASES.get((pname, prov), [pname, f"port {pname}"])
            matched_port = None

            # 4a. Check Canada-History-Knowledge-Graph first
            for cn in cand_names:
                hits = ca_kg.get((norm_key(cn), prov), [])
                if hits:
                    # Pick best by coordinate proximity if available, else priority
                    def score_ca(h):
                        s = h["prio"]
                        if tc and h.get("lat") is not None:
                            d = haversine_km(tc[0], tc[1], h["lat"], h["lon"])
                            s += 100.0 if d < 50 else (-100.0 if d > 500 else 0)
                        if "parish" not in h["desc"].lower() and "township" not in h["desc"].lower():
                            s += 15
                        return s
                    hits_sorted = sorted(hits, key=score_ca, reverse=True)
                    top = hits_sorted[0]
                    matched_port = {
                        "qid": top["qid"],
                        "wd_label": top["label"],
                        "description": top["desc"],
                        "source_authority": top["source_authority"],
                        "match_method": "canada_kg_port",
                        "province": prov,
                    }
                    break

            # 4b. Fallback to local Wikidata 2026-11-09 slim dump (restricted to Canada + province)
            if not matched_port:
                for cn in cand_names:
                    wd_cands = wd_by_term.get(cn, []) or wd_by_term.get(cn.replace(" ", "-"), [])
                    best = pick_best_wd_place(wd_cands, require_canada=True, prov_hint=prov, target_coords=tc)
                    if best:
                        matched_port = {
                            "qid": best["qid"],
                            "wd_label": best["label"],
                            "description": best["desc"],
                            "lat": best["lat"], "lon": best["lon"],
                            "source_authority": f"wikidata_slim:{WD_SNAPSHOT}",
                            "match_method": "wikidata_slim_canadian_port",
                            "province": prov,
                        }
                        break

            if matched_port:
                rec.update({"status": "matched", "match_relation": "skos:exactMatch", **matched_port})
                stats["matched_canadian_port"] += 1
                mention_stats["matched_canadian_port"] += cnt
                newly_resolved_audit.append((cnt, raw, matched_port["qid"], matched_port["wd_label"], matched_port["match_method"]))
            else:
                rec.update({"status": "unmatched_canadian_port", "province": prov})
                stats["unmatched"] += 1
                mention_stats["unmatched"] += cnt
                review_queue.append((cnt, "canadian_port", raw, f"port={pname}, prov={prov}"))
            results.append(rec)
            continue

        # 5. General place / polity via Base World + local Wikidata slim dump
        hit = resolve_single_place(raw, target_coords=tc)
        if hit:
            rec.update({
                "status": "matched",
                "match_relation": "skos:exactMatch",
                "qid": hit["qid"],
                "wd_label": hit["label"],
                "source_authority": hit["source_authority"],
                "match_method": hit["match_method"],
            })
            if hit.get("description"):
                rec["description"] = hit["description"]
            stats["matched"] += 1
            mention_stats["matched"] += cnt
            if hit["source_authority"].startswith("wikidata_slim:"):
                newly_resolved_audit.append((cnt, raw, hit["qid"], hit["label"], hit["description"][:45]))
        else:
            rec.update({"status": "unmatched"})
            stats["unmatched"] += 1
            mention_stats["unmatched"] += cnt
            review_queue.append((cnt, "unmatched_place", raw, ""))
        results.append(rec)

    # Save places_grounding.jsonl
    with open(GROUND / "places_grounding.jsonl", "w", encoding="utf-8") as fh:
        for rec in results:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Save places_review_queue.tsv
    review_queue.sort(reverse=True)
    with open(GROUND / "places_review_queue.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["total_rows", "queue_type", "name_as_printed", "notes"])
        w.writerows(review_queue)

    # 6. Year-aware Empire Evolution IN_POLITY resolution for all grounded (place, year) pairs
    emp = empire_mod.Empire()
    # Map Canadian ports also to Canada QID (verified from resolved "Canada" entry!)
    canada_qid = next((x["qid"] for x in results if x["norm_key"] == "canada" and x.get("qid")), None)
    place_to_qid = {}
    for x in results:
        if x.get("qid"):
            place_to_qid[x["name_as_printed"]] = (x["qid"], x.get("province"))

    polity_rows = []
    polity_covered_pairs = 0
    polity_total_pairs = 0
    polity_cache = {}

    for raw, yrs in place_years.items():
        if raw not in place_to_qid:
            continue
        qid, prov = place_to_qid[raw]
        lookup_qid = canada_qid if (prov and canada_qid) else qid
        for yr in sorted(yrs):
            polity_total_pairs += 1
            ck = (lookup_qid, yr)
            if ck not in polity_cache:
                polity_cache[ck] = emp.polity_at(lookup_qid, yr, yr)
            terr, path, hops = polity_cache[ck]
            if terr:
                polity_covered_pairs += 1
                polity_rows.append((raw, qid, yr, terr["id"], terr["name"], terr["qid"] or "", hops, " | ".join(path)))

    with open(GROUND / "place_year_polities.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["place_as_printed", "place_qid", "year", "empire_colony_id", "polity_name", "polity_qid", "hops", "lineage_path"])
        w.writerows(polity_rows)

    tot_mentions = sum(mention_stats.values())
    print("\n=== PLACES GROUNDING v2 SUMMARY ===")
    print(f"Total unique printed places: {len(results)} ({tot_mentions:,} mentions)")
    for k in ["matched", "matched_canadian_port", "matched_compound", "aggregate_category", "unmatched"]:
        print(f"  {k:24s}: {stats[k]:4d} places | {mention_stats[k]:7,d} mentions ({mention_stats[k]/tot_mentions*100:5.1f}%)")
    matched_m = mention_stats["matched"] + mention_stats["matched_canadian_port"] + mention_stats["matched_compound"]
    resolved_m = matched_m + mention_stats["aggregate_category"]
    print(f"  TOTAL GROUNDED TO QID   : {stats['matched']+stats['matched_canadian_port']+stats['matched_compound']:4d} places | {matched_m:7,d} mentions ({matched_m/tot_mentions*100:5.1f}%)")
    print(f"  TOTAL RESOLVED (+aggr.) : {len(results)-stats['unmatched']:4d} places | {resolved_m:7,d} mentions ({resolved_m/tot_mentions*100:5.1f}%)")
    print(f"  Empire IN_POLITY pairs  : {polity_covered_pairs:,} / {polity_total_pairs:,} (place, year) pairs covered by Empire Evolution")

    print("\n=== TOP 45 NEWLY RESOLVED PLACES (AUDIT) ===")
    newly_resolved_audit.sort(reverse=True)
    for cnt, raw, qid, lbl, note in newly_resolved_audit[:45]:
        print(f"  {cnt:6d}  {raw:42s} -> {qid:18s} {lbl:28s} [{note}]")

    print("\n=== TOP 25 REMAINING UNMATCHED PLACES ===")
    for cnt, qt, raw, note in review_queue[:25]:
        print(f"  {cnt:6d}  {qt:16s} {raw:42s} {note}")


if __name__ == "__main__":
    main()
