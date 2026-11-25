#!/usr/bin/env python3
"""
Ground Layer-1 (`human_transcribed`) archival commodity concepts (`htc:0001`..`htc:2066`) — v3.

Fixes every P0 and P1 Layer-B defect from OPUS_SKOS_REVIEW.md:
  - Uses `instance_of` class filtering from Wikidata 2026-11-09 slim Parquet (rejects genes,
    software, games, data structures, companies/brands, rockets, soft drinks, settlements,
    films/songs/albums, colors, biblical figures, disambiguation pages, and taxa-as-anchor).
  - Separates biological taxa (`Q16521`) strictly into `source_taxa` (`oe:sourceTaxon`) — ZERO
    taxa anchored in `skos:exactMatch`/`closeMatch`/`broadMatch`.
  - Honors explicit `commodity_rejections.tsv` + `ceylon/spine/grounding/name_rejections.jsonl`
    and re-validates ALL concepts uniformly (including ceylon/spine tiers).
  - Handles manufactured goods via product-class match + `made_of_material` (`oe:madeOfMaterial`),
    ores via ore items (never elements), and staves via `skos:relatedMatch` (never `broadMatch` to barrel).
  - Runs curated 1866 SKOS concept lookup and compound `X and Y` detection BEFORE prefix matching.
  - Fixes prefix-match direction: extra tokens or qualifying `processing_state` -> `skos:broadMatch`.
  - Enforces strict `skos:exactMatch` uniqueness (no two concepts assert `exactMatch` to the same QID;
    no non-raw processing state asserts `exactMatch`).
  - Fixes AGROVOC `c_c_` double-prefix bug (`P8061` values already start with `c_`).
  - Composes external LOD (AGROVOC `P8061`, STW Economics `P3911`, Getty AAT `P1014`) relation strength
    with the Wikidata mapping relation (`exact->close`, `close->close`, `broad->broad`, `related->related`)
    and collects LOD + taxa across ALL components of compound commodities.

ZERO QIDs from memory: every QID is read strictly from local Wikidata 2026-11-09 slim Parquet
or verified `ceylon/spine` files (re-checked against `instance_of` & rejections).
"""

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

BASE = Path("/home/jic823/Documents/open_empire/human_trade")
LAYER1 = BASE / "layer1_human"
GROUND = LAYER1 / "grounding"
CEYLON_SPINE = Path("/home/jic823/Documents/ceylon/spine")
WD_SLIM_GLOB = "/mnt/data/jic823/wikidata/20261109/slim/*.parquet"
WD_SNAPSHOT = "2026-11-09"
WD_API = "https://www.wikidata.org/w/api.php"
UA = "OpenEmpireLODGrounding/0.3 (University of Saskatchewan HGIS Lab; jim.clifford@usask.ca)"


def norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def singularize(w: str) -> str:
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ves") and len(w) > 4:
        return w[:-3] + "f"
    if w.endswith(("ches", "shes", "xes", "zes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is", "as")):
        return w[:-1]
    return w


# Explicitly logged bad QIDs identified during Opus audit (stored to commodity_rejections.tsv)
AUDIT_REJECTIONS = [
    ("plumbago", "Q2039140", "plant genus Plumbago, not graphite"),
    ("tar", "Q3338507", "tobacco smoke tar, not wood/coal tar"),
    ("clover", "Q5135861", "Clover dairy company, not clover crop"),
    ("rope", "Q1156047", "rope data structure, not textile cordage"),
    ("cordage", "Q1156047", "rope data structure, not textile cordage"),
    ("toy", "Q6516633", "Swedish Toy chewing gum brand"),
    ("clock", "Q14908739", "CLOCK protein-coding gene"),
    ("castor", "Q48970", "Castor solid-fuel rocket stage"),
    ("picture", "Q96742522", "Pictures 2019 board game"),
    ("watch", "Q1934809", "GNU watch CLI tool"),
    ("hoop", "Q2553153", "rhythmic gymnastics hoop"),
    ("match", "Q6786204", "Match soft drink"),
    ("curio", "Q5676387", "Curio plant genus"),
    ("cement", "Q189310", "geological sediment cement, not building cement"),
    ("leech", "Q1640028", "leech edge of sail, not medicinal leech"),
    ("clay", "Q1627382", "Clay species of moth (Mythimna ferrago)"),
    ("bead", "Q4876048", "woodworking moulding bead, not ornament bead"),
    ("shot", "Q7502422", "shot silk fabric, not lead shot"),
    ("blue", "Q15178353", "Blue soft drink"),
    ("veneer", "Q1686140", "dental veneer, not wood veneer"),
    ("bugle", "Q4843841", "Bugles corn snack by General Mills"),
    ("type", "Q3707858", "taxonomic type, not printing type"),
    ("manna", "Q241156", "biblical manna, not Fraxinus ornus drug exudate"),
    ("bone", "Q881659", "corset whalebone boning, not animal bone"),
    ("casting", "Q496098", "casting manufacturing process, not cast articles"),
    ("sponge", "Q1210980", "synthetic cleaning sponge, not natural marine sponge"),
    ("cinder", "Q16742056", "volcanic cinder rock, not coal cinders"),
    ("cocoa nut oil", "Q42385", "Theobroma cacao tree, not coconut oil"),
    ("cochineal", "Q320617", "carmine derived lake pigment, not cochineal dye"),
    ("salt", "Q12370", "generic chemistry ionic salt class, not table salt / NaCl"),
    ("sumac", "Q16131953", "culinary sumac fruit spice, not tanning sumach leaves"),
    ("beef tongue", "Q1558649", "beef tongue, not Canadian cod tongues"),
    ("oak", "Q55488372", "botanical natural monument in Poltava Oblast"),
    ("spar", "Q3965941", "spar oil platform"),
    ("oar", "Q10802255", "Oar genus of insects"),
    ("lobster", "Q3621241", "heraldic lobster"),
    ("mast", "Q1907811", "forest mast fruit, not ship mast"),
    ("nail", "Q36864", "fingernail anatomy, not metal fastener nail"),
    ("anchor", "Q1422055", "climbing anchor, not ship mooring anchor"),
]

# Forbidden Wikidata `instance_of` QIDs (never valid commodity/material/product anchors!)
FORBIDDEN_INSTANCE_OF = {
    "Q4167410",   # Wikimedia disambiguation page
    "Q11424",     # film
    "Q482994",    # album
    "Q134556",    # single
    "Q105543609", # musical work / composition / song
    "Q7187",      # gene
    "Q8054",      # protein
    "Q7397",      # software
    "Q341",       # free software
    "Q18343316",  # Unix/GNU utility
    "Q620615",    # mobile app
    "Q1371279",   # blogging software
    "Q235557",    # file format
    "Q188860",    # software library / font tech
    "Q1028939",   # markup language
    "Q175263",    # data structure
    "Q131436",    # board game
    "Q7889",      # video game
    "Q4830453",   # business
    "Q783794",    # company
    "Q431289",    # brand
    "Q507619",    # supermarket chain
    "Q18043413",  # retail chain
    "Q41291",     # rocket
    "Q697175",    # rocket family / launch vehicle
    "Q147538",    # soft drink
    "Q5",         # human
    "Q1093829",   # city of the US
    "Q486972",    # human settlement
    "Q15127012",  # town in the US
    "Q515",       # city
    "Q532",       # village
    "Q3957",      # town
    "Q12479774",  # regency of Indonesia
    "Q101352",    # family name
    "Q202444",    # given name
    "Q12308941",  # male given name
    "Q11879590",  # female given name
    "Q3297186",   # comic book series
    "Q376346",    # web color / color
    "Q1075",      # color
    "Q20643955",  # human biblical figure
    "Q169930",    # EP
    "Q8366",      # algorithm
    "Q1979154",   # machine learning algorithm
    "Q98400282",  # package manager
    "Q215380",    # musical group / band
    "Q112826905", # anatomical structure (used to avoid fingernail Q36864 unless bone!)
}

TAXON_CLASS_QID = "Q16521"  # Wikidata 'taxon' — goes ONLY into oe:sourceTaxon, never skos:*Match!

BAD_COMM_DESC_RE = re.compile(
    r"\b(film|movie|song|album|single|band|musician|singer|actor|actress|politician|painter|writer|novel|"
    r"poem|television|tv series|drama series|episode|video game|board game|card game|comic|magazine|"
    r"newspaper|scientific journal|journal published|painting by|given name|family name|surname|"
    r"disambiguation|wikimedia|human settlement|unincorporated community|city|town|village|municipality|"
    r"hamlet|county|province|state of|country|river|lake|mountain|island|electoral district|"
    r"railway station|airport|university|college|school|church|racehorse|crater|asteroid|planet|"
    r"natural monument|heraldic|heraldry|oil platform|musical notation|constellation|company|corporation|"
    r"brand|supermarket|retail chain|department store|manufacturer and marketer|football|basketball|"
    r"baseball|hockey|tennis|boxing|cricket|play by|opera|symphony|character|fictional|mytholog|deity|"
    r"saint|pope|king|queen|duke|earl|baron|battle of|treaty of|war of|year|century|language|dialect|"
    r"letter of|alphabet|programming language|software|command-line tool|data structure|markup language|"
    r"file format|package manager|website|font|typeface|currency|coin|unit of|postcode|zodiac|sign of the|"
    r"protein-coding gene|rocket|mars rover|spacecraft|nasa|cellular automaton|soft drink|chewing gum|"
    r"corn snack|rhythmic gymnastics|dental|coating for the teeth|burning of tobacco|volcanic|igneous|"
    r"chemical precipitate between grains|particulate matter produced|biblical|climbing equipment|"
    r"hard projection of digit|anchoring point of a taxonomic|corset|rope in the side of a sail|"
    r"woodworking decorative treatment|species of moth|genus of insects|region around the kneecap)\b",
    re.I,
)

# Catch-all customs residuals (never map to a concrete commodity QID)
RESIDUAL_RE = re.compile(
    r"^(other articles|other goods|other woods|other timber|other sorts|other kinds|other descriptions|"
    r"other manufactures|other animals|other grains|other seeds|other fruits|other fish|other meats|"
    r"other oils|other furs|other skins|other hides|other metals|other minerals|other chemicals|"
    r"goods unenumerated.*|articles unenumerated.*|unenumerated|miscellaneous|sundries|all other.*|"
    r"non enumerated.*|other unenumerated.*|manufactures unenumerated|value of articles.*)$",
    re.I,
)

# Compound customs headings -> list of (commodity_term, optional_taxon_term)
COMPOUND_HEADINGS = {
    "barley and rye": [("cereal", "hordeum vulgare"), ("cereal", "secale cereale")],
    "bacon and hams": [("bacon", None), ("ham", None)],
    "ale beer and cider": [("beer", None), ("cider", None)],
    "ale and beer": [("beer", None)],
    "beans and peas": [("bean", None), ("pea", "pisum sativum")],
    "peas and beans": [("pea", "pisum sativum"), ("bean", None)],
    "oranges and lemons": [("orange", None), ("lemon", None)],
    "lemons and oranges": [("lemon", None), ("orange", None)],
    "cutch and gambier": [("catechu", None), ("catechu", "uncaria gambir")],
    "tallow and stearine": [("tallow", None), ("stearin", None)],
    "masts and spars": [("mast", None), ("spar", None)],
    "furs and skins": [("fur", None), ("hide", None)],
    "planks and boards": [("lumber", None)],
    "flaxseed and linseed": [("seed", "linum usitatissimum")],
    "pearl and pot ashes": [("potash", None), ("potassium carbonate", None)],
    "pot and pearl ashes": [("potash", None), ("potassium carbonate", None)],
    "pig and scrap iron": [("pig iron", None)],
    "boots and shoes": [("footwear", None)],
    "leather manufactures boots and shoes": [("footwear", None)],
    "wood and timber basswood butternut and hickory": [("wood", "tilia"), ("wood", "juglans cinerea"), ("wood", "carya")],
    "codfish including haddock ling pollock": [("cod", None)],
}

# Curated, unambiguous customs term -> (non-taxon commodity_term, optional_source_taxon_term, base_relation)
# ZERO QIDs hardcoded: every term is looked up dynamically in local Wikidata 2026-11-09 slim Parquet!
CANONICAL_SUBSTANCE_MAP = {
    # Timber & forestry (non-taxon wood/timber items + exact botanical source taxa)
    "planks": ("lumber", None, "skos:broadMatch"),
    "boards": ("lumber", None, "skos:broadMatch"),
    "deals": ("lumber", None, "skos:broadMatch"),
    "deal ends": ("lumber", None, "skos:broadMatch"),
    "deals and battens": ("lumber", None, "skos:broadMatch"),
    "battens": ("batten", None, "skos:closeMatch"),
    "scantling": ("lumber", None, "skos:broadMatch"),
    "shingles": ("wood shingle", None, "skos:exactMatch"),
    "laths": ("lath", None, "skos:exactMatch"),
    "lathwood": ("lath", None, "skos:broadMatch"),
    "lath lathwood": ("lath", None, "skos:broadMatch"),
    "saw logs": ("wood", None, "skos:broadMatch"),
    "logs": ("wood", None, "skos:broadMatch"),
    "knees": ("wood", None, "skos:broadMatch"),
    "shooks": ("wood", None, "skos:broadMatch"),
    "timber": ("wood", None, "skos:broadMatch"),
    "tamarack": ("wood", "larix laricina", "skos:broadMatch"),
    "seeds": ("seed", None, "skos:broadMatch"),
    "spirits": ("distilled beverage", None, "skos:broadMatch"),
    "drugs": ("medication", None, "skos:broadMatch"),
    "gum": ("natural gum", None, "skos:broadMatch"),
    "skins": ("hide", None, "skos:broadMatch"),
    "cows": ("cattle", None, "skos:broadMatch"),
    "firewood": ("firewood", None, "skos:exactMatch"),
    "sleepers": ("railroad tie", None, "skos:exactMatch"),
    "railway ties": ("railroad tie", None, "skos:exactMatch"),
    "railroad ties": ("railroad tie", None, "skos:exactMatch"),
    "masts": ("mast", None, "skos:exactMatch"),
    "spars": ("spar", None, "skos:exactMatch"),
    "oars": ("oar", None, "skos:exactMatch"),
    "staves": ("barrel", None, "skos:relatedMatch"),  # part/whole -> relatedMatch ONLY!
    "standard staves": ("barrel", None, "skos:relatedMatch"),
    "staves other": ("barrel", None, "skos:relatedMatch"),
    "wood and timber staves": ("barrel", None, "skos:relatedMatch"),
    "hoop": ("barrel", None, "skos:relatedMatch"),
    "hoops": ("barrel", None, "skos:relatedMatch"),
    "veneers": ("wood veneer", None, "skos:exactMatch"),
    "pulpwood": ("pulpwood", None, "skos:exactMatch"),
    "wood pulp": ("pulp", None, "skos:broadMatch"),
    "pulp of wood": ("pulp", None, "skos:broadMatch"),
    "paper making materials pulp of wood": ("pulp", None, "skos:broadMatch"),
    "timber oak": ("wood", "quercus", "skos:broadMatch"),
    "oak": ("wood", "quercus", "skos:broadMatch"),
    "timber walnut": ("wood", "juglans", "skos:broadMatch"),
    "timber pine": ("wood", "pinus", "skos:broadMatch"),
    "white pine": ("wood", "pinus strobus", "skos:broadMatch"),
    "timber white pine": ("wood", "pinus strobus", "skos:broadMatch"),
    "red pine": ("wood", "pinus resinosa", "skos:broadMatch"),
    "timber elm": ("wood", "ulmus", "skos:broadMatch"),
    "elm": ("wood", "ulmus", "skos:broadMatch"),
    "timber ash": ("wood", "fraxinus", "skos:broadMatch"),
    "timber birch": ("wood", "betula", "skos:broadMatch"),
    "birch": ("wood", "betula", "skos:broadMatch"),
    "timber tamarac": ("wood", "larix laricina", "skos:broadMatch"),
    "timber tamarack": ("wood", "larix laricina", "skos:broadMatch"),
    "tamarac": ("wood", "larix laricina", "skos:broadMatch"),
    "timber maple": ("wood", "acer", "skos:broadMatch"),
    "timber fir": ("wood", "abies", "skos:broadMatch"),
    "wood and timber hewn fir": ("wood", "abies", "skos:broadMatch"),
    "timber cedar": ("wood", "cedrus", "skos:broadMatch"),
    "timber spruce": ("wood", "picea", "skos:broadMatch"),
    "timber hemlock": ("wood", "tsuga", "skos:broadMatch"),
    "timber beech": ("wood", "fagus", "skos:broadMatch"),
    "timber hickory": ("wood", "carya", "skos:broadMatch"),
    "mahogany": ("mahogany", None, "skos:exactMatch"),
    "teak": ("teak", None, "skos:exactMatch"),
    "rosewood": ("rosewood", None, "skos:exactMatch"),
    "ebony": ("ebony", None, "skos:exactMatch"),
    "boxwood": ("boxwood", None, "skos:exactMatch"),
    "lignum vitae": ("lignum vitae", None, "skos:exactMatch"),
    "cork": ("cork", None, "skos:exactMatch"),
    "wood hewn": ("wood", None, "skos:broadMatch"),
    "wood sawn or split": ("lumber", None, "skos:broadMatch"),
    "wood and timber": ("wood", None, "skos:broadMatch"),

    # Tannins, hides, skins, furs, leather
    "bark for tanners and dyers use": ("tanbark", None, "skos:exactMatch"),
    "bark for tanners": ("tanbark", None, "skos:exactMatch"),
    "bark for tanning": ("tanbark", None, "skos:exactMatch"),
    "oak bark": ("tanbark", "quercus", "skos:broadMatch"),
    "hemlock bark": ("tanbark", "tsuga", "skos:broadMatch"),
    "valonia": ("tanbark", "quercus ithaburensis", "skos:broadMatch"),
    "cutch": ("catechu", None, "skos:exactMatch"),
    "terra japonica": ("catechu", None, "skos:exactMatch"),
    "gambier": ("catechu", "uncaria gambir", "skos:closeMatch"),
    "sumach": ("tannin", "rhus coriaria", "skos:broadMatch"),
    "shumach": ("tannin", "rhus coriaria", "skos:broadMatch"),
    "sumac": ("tannin", "rhus coriaria", "skos:broadMatch"),
    "myrobalans": ("tannin", "terminalia chebula", "skos:broadMatch"),
    "myrabolans": ("tannin", "terminalia chebula", "skos:broadMatch"),
    "divi divi": ("tannin", "libidibia coriaria", "skos:broadMatch"),
    "quercitron": ("dye", "quercus velutina", "skos:broadMatch"),
    "galls": ("gall", None, "skos:exactMatch"),
    "hides": ("hide", None, "skos:exactMatch"),
    "hides or pieces of": ("hide", None, "skos:broadMatch"),
    "leather": ("leather", None, "skos:exactMatch"),
    "sheeps pelts": ("sheepskin", None, "skos:exactMatch"),
    "sheep s pelts": ("sheepskin", None, "skos:exactMatch"),
    "sheep skins": ("sheepskin", None, "skos:closeMatch"),
    "sheep and lamb skins": ("sheepskin", None, "skos:broadMatch"),
    "skins furs pelts sheep": ("sheepskin", None, "skos:broadMatch"),
    "skins furs pelts lamb": ("sheepskin", None, "skos:broadMatch"),
    "skins furs pelts goat": ("goatskin", None, "skos:broadMatch"),
    "skins furs pelts seal": ("sealskin", None, "skos:broadMatch"),
    "skins seal": ("sealskin", None, "skos:broadMatch"),
    "skins furs pelts calf": ("calfskin", None, "skos:broadMatch"),
    "skins furs pelts": ("fur", None, "skos:broadMatch"),
    "furs": ("fur", None, "skos:exactMatch"),
    "furs or skins of fish": ("hide", None, "skos:broadMatch"),
    "pelts": ("hide", None, "skos:closeMatch"),

    # Grains, cereals, flours, legumes (commodity item + taxon strictly in source_taxa!)
    "wheat": ("wheat", "triticum aestivum", "skos:exactMatch"),
    "wheat meal and flour": ("wheat flour", "triticum aestivum", "skos:exactMatch"),
    "wheat flour": ("wheat flour", "triticum aestivum", "skos:exactMatch"),
    "flour": ("flour", None, "skos:exactMatch"),
    "meal": ("flour", None, "skos:broadMatch"),
    "oatmeal": ("oatmeal", "avena sativa", "skos:exactMatch"),
    "corn meal": ("cornmeal", "zea mays", "skos:exactMatch"),
    "maize or indian corn meal": ("cornmeal", "zea mays", "skos:exactMatch"),
    "barley meal": ("flour", "hordeum vulgare", "skos:broadMatch"),
    "barley meal and flour": ("flour", "hordeum vulgare", "skos:broadMatch"),
    "rye meal": ("flour", "secale cereale", "skos:broadMatch"),
    "oats": ("cereal", "avena sativa", "skos:broadMatch"),
    "barley": ("cereal", "hordeum vulgare", "skos:broadMatch"),
    "rye": ("cereal", "secale cereale", "skos:broadMatch"),
    "indian corn": ("cereal", "zea mays", "skos:broadMatch"),
    "indian corn or maize": ("cereal", "zea mays", "skos:broadMatch"),
    "maize": ("cereal", "zea mays", "skos:broadMatch"),
    "buckwheat": ("cereal", "fagopyrum esculentum", "skos:broadMatch"),
    "rice": ("rice", None, "skos:exactMatch"),
    "pease": ("pea", "pisum sativum", "skos:exactMatch"),
    "peas": ("pea", "pisum sativum", "skos:exactMatch"),
    "beans": ("bean", None, "skos:exactMatch"),
    "malt": ("malt", None, "skos:exactMatch"),
    "hops": ("hops", None, "skos:exactMatch"),
    "biscuits": ("biscuit", None, "skos:exactMatch"),
    "sago": ("sago", None, "skos:exactMatch"),
    "tapioca": ("tapioca", None, "skos:exactMatch"),
    "arrowroot": ("arrowroot", None, "skos:exactMatch"),

    # Fodder & animal feed
    "oil seed cakes": ("press cake", None, "skos:exactMatch"),
    "oil seed cake": ("press cake", None, "skos:exactMatch"),
    "oilseed cake": ("press cake", None, "skos:exactMatch"),
    "oil cake": ("press cake", None, "skos:exactMatch"),
    "oilcake": ("press cake", None, "skos:exactMatch"),
    "linseed cake": ("press cake", "linum usitatissimum", "skos:broadMatch"),
    "cotton seed cake": ("press cake", None, "skos:broadMatch"),
    "hay": ("hay", None, "skos:exactMatch"),
    "straw": ("straw", None, "skos:exactMatch"),
    "bran": ("bran", None, "skos:exactMatch"),
    "clover seeds": ("seed", "trifolium", "skos:broadMatch"),
    "clover seed": ("seed", "trifolium", "skos:broadMatch"),

    # Fats, oils, oilseeds, soap
    "cocoa nut oil": ("coconut oil", "cocos nucifera", "skos:exactMatch"),
    "coco nut oil": ("coconut oil", "cocos nucifera", "skos:exactMatch"),
    "coconut oil": ("coconut oil", "cocos nucifera", "skos:exactMatch"),
    "palm oil": ("palm oil", "elaeis guineensis", "skos:exactMatch"),
    "oil palm": ("palm oil", "elaeis guineensis", "skos:exactMatch"),
    "olive oil": ("olive oil", "olea europaea", "skos:exactMatch"),
    "oil olive": ("olive oil", "olea europaea", "skos:exactMatch"),
    "linseed oil": ("linseed oil", "linum usitatissimum", "skos:exactMatch"),
    "oil linseed": ("linseed oil", "linum usitatissimum", "skos:exactMatch"),
    "cotton seed oil": ("cottonseed oil", None, "skos:exactMatch"),
    "cotton seeds": ("cottonseed", None, "skos:exactMatch"),
    "cotton seed": ("cottonseed", None, "skos:exactMatch"),
    "linseed": ("seed", "linum usitatissimum", "skos:broadMatch"),
    "flaxseed": ("seed", "linum usitatissimum", "skos:broadMatch"),
    "flax seeds": ("seed", "linum usitatissimum", "skos:broadMatch"),
    "rapeseed": ("rapeseed", None, "skos:exactMatch"),
    "seeds rape": ("rapeseed", None, "skos:exactMatch"),
    "seed oil": ("vegetable oil", None, "skos:broadMatch"),
    "oil seed": ("seed", None, "skos:broadMatch"),
    "oil turpentine": ("turpentine", None, "skos:exactMatch"),
    "tallow": ("tallow", None, "skos:exactMatch"),
    "stearine": ("stearin", None, "skos:exactMatch"),
    "lard": ("lard", None, "skos:exactMatch"),
    "beeswax": ("beeswax", None, "skos:exactMatch"),
    "wax": ("wax", None, "skos:exactMatch"),
    "soap": ("soap", None, "skos:exactMatch"),
    "candles": ("candle", None, "skos:exactMatch"),

    # Fisheries & marine oils/products
    "fish oil": ("fish oil", None, "skos:exactMatch"),
    "fish oil cod": ("cod liver oil", None, "skos:closeMatch"),
    "oil cod": ("cod liver oil", None, "skos:closeMatch"),
    "fish oil seal": ("seal oil", None, "skos:exactMatch"),
    "oil seal": ("seal oil", None, "skos:exactMatch"),
    "fish oil whale": ("whale oil", None, "skos:exactMatch"),
    "oil whale": ("whale oil", None, "skos:exactMatch"),
    "oil train": ("whale oil", None, "skos:exactMatch"),
    "train or blubber": ("whale oil", None, "skos:closeMatch"),
    "train oil": ("whale oil", None, "skos:exactMatch"),
    "oil spermaceti": ("sperm oil", None, "skos:exactMatch"),
    "fish oil herring": ("fish oil", None, "skos:broadMatch"),
    "fish oil porpoise": ("whale oil", None, "skos:broadMatch"),
    "fish oil dog": ("fish oil", None, "skos:broadMatch"),
    "fish oil unenumerated": ("fish oil", None, "skos:broadMatch"),
    "cod": ("cod", None, "skos:exactMatch"),
    "codfish": ("cod", None, "skos:exactMatch"),
    "herrings": ("herring", None, "skos:exactMatch"),
    "herring": ("herring", None, "skos:exactMatch"),
    "salmon": ("salmon", None, "skos:exactMatch"),
    "mackerel": ("mackerel", None, "skos:exactMatch"),
    "oysters": ("oyster", None, "skos:exactMatch"),
    "lobsters": ("lobster", "nephropidae", "skos:closeMatch"),
    "whalebone": ("baleen", None, "skos:exactMatch"),
    "whale fins": ("baleen", None, "skos:exactMatch"),
    "isinglass": ("isinglass", None, "skos:exactMatch"),
    "tongues": ("fish as food", None, "skos:broadMatch"),  # Canadian cod tongues (verified from ledger!)
    "tongues and sounds": ("fish as food", None, "skos:broadMatch"),
    "cod sounds": ("fish as food", None, "skos:broadMatch"),
    "fish": ("fish as food", None, "skos:broadMatch"),

    # Livestock, meats, dairy, eggs
    "horned cattle": ("cattle", None, "skos:exactMatch"),
    "neat cattle": ("cattle", None, "skos:exactMatch"),
    "cattle": ("cattle", None, "skos:exactMatch"),
    "swine": ("pig", None, "skos:exactMatch"),
    "hogs": ("pig", None, "skos:exactMatch"),
    "pigs": ("pig", None, "skos:exactMatch"),
    "sheep": ("sheep", None, "skos:exactMatch"),
    "sheep and lambs": ("sheep", None, "skos:broadMatch"),
    "horses": ("horse", None, "skos:exactMatch"),
    "poultry": ("poultry", None, "skos:exactMatch"),
    "beef": ("beef", None, "skos:exactMatch"),
    "pork": ("pork", None, "skos:exactMatch"),
    "bacon": ("bacon", None, "skos:exactMatch"),
    "hams": ("ham", None, "skos:exactMatch"),
    "mutton": ("lamb and mutton", None, "skos:exactMatch"),
    "meat": ("meat", None, "skos:exactMatch"),
    "butter": ("butter", None, "skos:exactMatch"),
    "cheese": ("cheese", None, "skos:exactMatch"),
    "eggs": ("egg as food", None, "skos:exactMatch"),
    "eggs in shell": ("egg as food", None, "skos:closeMatch"),

    # Fibres & raw textiles
    "wool": ("wool", None, "skos:exactMatch"),
    "wool sheep and lambs": ("wool", None, "skos:broadMatch"),
    "wool cotton": ("cotton", None, "skos:closeMatch"),  # raw cotton wool!
    "cotton": ("cotton", None, "skos:exactMatch"),
    "flax": ("flax", "linum usitatissimum", "skos:exactMatch"),
    "hemp": ("hemp", None, "skos:exactMatch"),
    "jute": ("jute", None, "skos:exactMatch"),
    "silk": ("silk", None, "skos:exactMatch"),
    "linen": ("linen", None, "skos:exactMatch"),
    "rags": ("rag", None, "skos:exactMatch"),
    "esparto": ("esparto", None, "skos:exactMatch"),
    "feathers": ("feather", None, "skos:exactMatch"),
    "bristles": ("bristle", None, "skos:exactMatch"),
    "hair": ("hair", None, "skos:exactMatch"),

    # Drugs, botanicals, chemicals, dyes, naval stores
    "plumbago": ("graphite", None, "skos:exactMatch"),
    "lead black": ("graphite", None, "skos:closeMatch"),
    "tar": ("tar", None, "skos:exactMatch"),
    "pitch": ("pitch", None, "skos:exactMatch"),
    "rosin": ("rosin", None, "skos:exactMatch"),
    "turpentine": ("turpentine", None, "skos:exactMatch"),
    "coal tar": ("coal tar", None, "skos:exactMatch"),
    "coal tar dyes": ("dye", None, "skos:broadMatch"),
    "ashes pot": ("potash", None, "skos:exactMatch"),
    "ashes pearl": ("potassium carbonate", None, "skos:closeMatch"),
    "pearl ashes": ("potassium carbonate", None, "skos:closeMatch"),
    "soda bicarbonate": ("sodium bicarbonate", None, "skos:exactMatch"),
    "soda caustic": ("sodium hydroxide", None, "skos:exactMatch"),
    "soda sulphate": ("sodium sulfate", None, "skos:exactMatch"),
    "soda ash": ("sodium carbonate", None, "skos:exactMatch"),
    "soda": ("sodium carbonate", None, "skos:broadMatch"),
    "barilla": ("barilla", None, "skos:exactMatch"),
    "saltpetre": ("potassium nitrate", None, "skos:exactMatch"),
    "nitrate of soda": ("sodium nitrate", None, "skos:exactMatch"),
    "cubic nitre": ("sodium nitrate", None, "skos:exactMatch"),
    "brimstone": ("sulfur", None, "skos:exactMatch"),
    "guano": ("guano", None, "skos:exactMatch"),
    "caoutchouc": ("natural rubber", None, "skos:exactMatch"),
    "india rubber": ("natural rubber", None, "skos:exactMatch"),
    "gutta percha": ("gutta-percha", None, "skos:exactMatch"),
    "cinchona": ("cinchona", None, "skos:exactMatch"),
    "peruvian bark": ("cinchona", None, "skos:closeMatch"),
    "opium": ("opium", None, "skos:exactMatch"),
    "castor": ("castoreum", None, "skos:exactMatch"),  # verified from KEW_CUST 4 Canada/Hudsons Bay!
    "manna": ("manna", "fraxinus ornus", "skos:relatedMatch"),
    "indigo": ("indigo dye", None, "skos:exactMatch"),
    "cochineal": ("dye", "dactylopius coccus", "skos:broadMatch"),
    "madder": ("dye", "rubia tinctorum", "skos:broadMatch"),
    "logwood": ("dye", "haematoxylum campechianum", "skos:broadMatch"),
    "dye woods logwood": ("dye", "haematoxylum campechianum", "skos:broadMatch"),
    "fustic": ("dye", "maclura tinctoria", "skos:broadMatch"),
    "dye stuffs": ("dye", None, "skos:broadMatch"),
    "dye woods": ("dye", None, "skos:broadMatch"),
    "annatto": ("annatto", None, "skos:exactMatch"),
    "turmeric": ("turmeric", None, "skos:exactMatch"),
    "camphor": ("camphor", None, "skos:exactMatch"),
    "borax": ("borax", None, "skos:exactMatch"),
    "alum": ("alum", None, "skos:exactMatch"),
    "arsenic": ("arsenic", None, "skos:exactMatch"),
    "gum arabic": ("gum arabic", None, "skos:exactMatch"),
    "shellac": ("shellac", None, "skos:exactMatch"),
    "lac": ("lac", None, "skos:exactMatch"),
    "ivory": ("ivory", None, "skos:exactMatch"),
    "bones": ("bone", None, "skos:exactMatch"),
    "bones except whalebone": ("bone", None, "skos:broadMatch"),
    "horns": ("horn", None, "skos:exactMatch"),
    "hoofs": ("hoof", None, "skos:exactMatch"),
    "senna": ("herbal medicine", "senna alexandrina", "skos:broadMatch"),
    "rhubarb": ("rhubarb", None, "skos:exactMatch"),
    "sarsaparilla": ("herbal medicine", "smilax", "skos:broadMatch"),
    "liquorice": ("liquorice", None, "skos:exactMatch"),
    "licorice": ("liquorice", None, "skos:exactMatch"),

    # Colonial groceries, fruits, beverages, spices, tobacco
    "sugar": ("sugar", None, "skos:exactMatch"),
    "sugar total": ("sugar", None, "skos:broadMatch"),
    "maple sugar": ("maple sugar", None, "skos:exactMatch"),
    "molasses": ("molasses", None, "skos:exactMatch"),
    "honey": ("honey", None, "skos:exactMatch"),
    "coffee": ("coffee", None, "skos:exactMatch"),
    "tea": ("tea", None, "skos:exactMatch"),
    "cocoa": ("cocoa bean", "theobroma cacao", "skos:closeMatch"),
    "cocoa butter": ("cocoa butter", "theobroma cacao", "skos:exactMatch"),
    "tobacco": ("tobacco", None, "skos:exactMatch"),
    "rum": ("rum", None, "skos:exactMatch"),
    "spirits rum": ("rum", None, "skos:exactMatch"),
    "brandy": ("brandy", None, "skos:exactMatch"),
    "spirits brandy": ("brandy", None, "skos:exactMatch"),
    "whisky": ("whisky", None, "skos:exactMatch"),
    "whiskey": ("whisky", None, "skos:exactMatch"),
    "gin": ("gin", None, "skos:exactMatch"),
    "wine": ("wine", None, "skos:exactMatch"),
    "beer": ("beer", None, "skos:exactMatch"),
    "cider": ("cider", None, "skos:exactMatch"),
    "vinegar": ("vinegar", None, "skos:exactMatch"),
    "apples": ("apple", "malus domestica", "skos:exactMatch"),
    "potatoes": ("potato", None, "skos:exactMatch"),
    "onions": ("onion", None, "skos:exactMatch"),
    "oranges": ("orange", None, "skos:exactMatch"),
    "lemons": ("lemon", None, "skos:exactMatch"),
    "raisins": ("raisin", None, "skos:exactMatch"),
    "currants": ("zante currant", None, "skos:exactMatch"),
    "figs": ("fig", "ficus carica", "skos:exactMatch"),
    "almonds": ("almond", None, "skos:exactMatch"),
    "walnuts": ("walnut", "juglans", "skos:exactMatch"),
    "pepper": ("black pepper", None, "skos:exactMatch"),
    "cinnamon": ("cinnamon", None, "skos:exactMatch"),
    "cloves": ("clove", None, "skos:exactMatch"),
    "ginger": ("ginger", None, "skos:exactMatch"),
    "nutmegs": ("nutmeg", None, "skos:exactMatch"),
    "pimento": ("allspice", None, "skos:exactMatch"),

    # Minerals, ores, metals, fuels
    "salt": ("table salt", None, "skos:exactMatch"),
    "salt rock and white": ("table salt", None, "skos:broadMatch"),
    "coal": ("coal", None, "skos:exactMatch"),
    "coals": ("coal", None, "skos:exactMatch"),
    "petroleum": ("petroleum", None, "skos:exactMatch"),
    "coal oil": ("kerosene", None, "skos:exactMatch"),
    "clay": ("clay", None, "skos:exactMatch"),
    "gypsum": ("gypsum", None, "skos:exactMatch"),
    "plaster": ("gypsum", None, "skos:closeMatch"),
    "slate": ("slate", None, "skos:exactMatch"),
    "marble": ("marble", None, "skos:exactMatch"),
    "iron ore": ("iron ore", None, "skos:exactMatch"),
    "copper ore": ("copper ore", None, "skos:exactMatch"),
    "lead ore": ("lead ore", None, "skos:exactMatch"),
    "tin ore": ("tin ore", None, "skos:exactMatch"),
    "silver ore": ("silver ore", None, "skos:exactMatch"),
    "cobalt ore": ("cobalt ore", None, "skos:exactMatch"),
    "zinc ore": ("ore", None, "skos:broadMatch"),
    "manganese ore": ("ore", None, "skos:broadMatch"),
    "antimony ore": ("ore", None, "skos:broadMatch"),
    "iron pig": ("pig iron", None, "skos:exactMatch"),
    "iron bar": ("wrought iron", None, "skos:closeMatch"),
    "iron": ("iron", None, "skos:exactMatch"),
    "steel": ("steel", None, "skos:exactMatch"),
    "copper": ("copper", None, "skos:exactMatch"),
    "tin": ("tin", None, "skos:exactMatch"),
    "lead": ("lead", None, "skos:exactMatch"),
    "zinc": ("zinc", None, "skos:exactMatch"),
    "spelter": ("zinc", None, "skos:exactMatch"),
    "quicksilver": ("mercury", None, "skos:exactMatch"),
    "antimony": ("antimony", None, "skos:exactMatch"),
    "manganese": ("manganese", None, "skos:exactMatch"),

    # Manufactured articles (product classes — NEVER raw elements or fibers!)
    "cordage": ("rope", None, "skos:exactMatch"),
    "rope": ("rope", None, "skos:exactMatch"),
    "twine": ("twine", None, "skos:exactMatch"),
    "toys": ("toy", None, "skos:exactMatch"),
    "clocks": ("clock", None, "skos:exactMatch"),
    "watches": ("watch", None, "skos:exactMatch"),
    "matches": ("match", None, "skos:exactMatch"),
    "cement": ("cement", None, "skos:exactMatch"),
    "beads": ("bead", None, "skos:exactMatch"),
    "bugles": ("bead", None, "skos:broadMatch"),
    "type": ("movable type", None, "skos:closeMatch"),
    "pictures": ("painting", None, "skos:broadMatch"),
    "books": ("book", None, "skos:exactMatch"),
    "paper": ("paper", None, "skos:exactMatch"),
    "glass": ("glass", None, "skos:exactMatch"),
    "earthenware": ("earthenware", None, "skos:exactMatch"),
    "chinaware": ("porcelain", None, "skos:exactMatch"),
    "furniture": ("furniture", None, "skos:exactMatch"),
    "wood household furniture": ("furniture", None, "skos:broadMatch"),
    "carriages": ("carriage", None, "skos:exactMatch"),
    "sewing machines": ("sewing machine", None, "skos:exactMatch"),
    "musical instruments": ("musical instrument", None, "skos:exactMatch"),
    "machinery": ("machine", None, "skos:broadMatch"),
    "machinery manufactures": ("machine", None, "skos:broadMatch"),
    "hardware": ("household hardware", None, "skos:broadMatch"),
    "agricultural implements": ("agricultural machinery", None, "skos:exactMatch"),
    "gunpowder": ("gunpowder", None, "skos:exactMatch"),
    "starch": ("starch", None, "skos:exactMatch"),
    "glue": ("adhesive", None, "skos:closeMatch"),
    "canvas": ("canvas", None, "skos:exactMatch"),
    "clothing": ("clothing", None, "skos:exactMatch"),
    "manufactures clothing": ("clothing", None, "skos:exactMatch"),
    "cotton manufactures": ("textile", None, "skos:broadMatch"),
    "silk manufactures": ("textile", None, "skos:broadMatch"),
    "woollen manufactures": ("textile", None, "skos:broadMatch"),
    "linen manufactures": ("textile", None, "skos:broadMatch"),
    "leather manufactures gloves": ("glove", None, "skos:exactMatch"),
    "gloves": ("glove", None, "skos:exactMatch"),
    "iron stoves": ("stove", None, "skos:broadMatch"),
    "iron nails": ("nail", None, "skos:broadMatch"),
    "iron anchors": ("anchor", None, "skos:broadMatch"),
    "iron and steel bolts and nuts": ("fastener", None, "skos:broadMatch"),
}

MATERIAL_DETECT = [
    (r"\b(iron|steel)\b", "iron"),
    (r"\bcopper\b", "copper"),
    (r"\blead\b", "lead"),
    (r"\btin\b", "tin"),
    (r"\bzinc\b", "zinc"),
    (r"\bsilk\b", "silk"),
    (r"\bcotton\b", "cotton"),
    (r"\b(wool|woollen|woolen)\b", "wool"),
    (r"\blinen\b", "linen"),
    (r"\bleather\b", "leather"),
    (r"\b(wood|wooden|timber)\b", "wood"),
    (r"\bglass\b", "glass"),
]


def load_rejections():
    rej = set()
    # Write/save explicit commodity_rejections.tsv
    rej_path = GROUND / "commodity_rejections.tsv"
    with open(rej_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["term_norm", "rejected_qid", "reason"])
        for t, q, why in AUDIT_REJECTIONS:
            w.writerow([norm_key(t), q, why])
            rej.add((norm_key(t), q))
            rej.add(("*", q))  # block globally bad homonym QIDs like CLOCK gene / GNU watch / Toy gum / Clay moth!

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


def query_wikidata_terms(terms: set):
    clean = sorted({t.lower().strip() for t in terms if t and len(t.strip()) >= 3})
    print(f"Querying Wikidata {WD_SNAPSHOT} slim Parquet for {len(clean):,} commodity & taxon terms...", flush=True)
    con = duckdb.connect()
    con.execute("CREATE TEMP TABLE want(term VARCHAR)")
    con.executemany("INSERT INTO want VALUES (?)", [(t,) for t in clean])

    sql = f"""
    SELECT
        lower(label_en) AS lkey,
        qid,
        label_en,
        description_en,
        sitelinks,
        instance_of
    FROM '{WD_SLIM_GLOB}'
    WHERE lower(label_en) IN (SELECT term FROM want)
      AND sitelinks >= 2
    """
    rows = con.execute(sql).fetchall()
    by_term = defaultdict(list)
    for lkey, qid, label_en, desc_en, sitelinks, inst in rows:
        by_term[lkey].append({
            "qid": qid,
            "label": label_en,
            "desc": desc_en or "",
            "sitelinks": int(sitelinks or 0),
            "instance_of": list(inst) if inst is not None else [],
        })
    print(f"  Retrieved {len(rows):,} candidate rows across {len(by_term):,} terms.", flush=True)
    return by_term


def pick_commodity_candidate(term: str, cands: list, rejections: set, require_lowercase: bool = True):
    """Pick best NON-TAXON commodity/material/product candidate using instance_of + lowercase common-noun guard + rejections."""
    k = norm_key(term)
    scored = []
    for c in cands:
        qid = c["qid"]
        if (k, qid) in rejections or ("*", qid) in rejections:
            continue
        # On Wikidata, common nouns (commodities/materials/foods) are lowercase; Title-Case labels are proper nouns (paintings/shows/journals/towns)!
        if require_lowercase and c["label"] and c["label"] != c["label"].lower():
            continue
        inst = set(c["instance_of"])
        # Strict P0 rule: NEVER pick a forbidden class or a biological taxon (Q16521) as commodity anchor!
        if inst & FORBIDDEN_INSTANCE_OF:
            continue
        if TAXON_CLASS_QID in inst:
            continue
        desc = c["desc"]
        if BAD_COMM_DESC_RE.search(desc):
            continue
        score = c["sitelinks"] * 2.0
        if desc:
            score += 15.0
        scored.append((score, c))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def pick_taxon_candidate(term: str, cands: list):
    """Pick verified biological taxon (`Q16521` in `instance_of`) strictly for `oe:sourceTaxon`."""
    scored = []
    for c in cands:
        if TAXON_CLASS_QID in set(c["instance_of"]):
            scored.append((c["sitelinks"], c))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def enrich_qids_wikidata_api(qids: list, cache_path: Path):
    """Fetch P1582 (source taxon), P8061 (AGROVOC), P3911 (STW Economics), P1014 (Getty AAT), P225, P10585."""
    cache = {}
    if cache_path.exists():
        for line in open(cache_path, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                cache[d["qid"]] = d

    todo = [q for q in dict.fromkeys(qids) if q and q.startswith("Q") and q not in cache]
    print(f"Enriching {len(todo)} QIDs via Wikidata wbgetentities (cached: {len(cache)})...", flush=True)
    if not todo:
        return cache

    def claim_vals(claims, pid):
        out = []
        for c in claims.get(pid, []):
            v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(v, dict) and "id" in v:
                out.append(v["id"])
            elif isinstance(v, str):
                out.append(v)
        return out

    with open(cache_path, "a", encoding="utf-8") as fh:
        for i in range(0, len(todo), 50):
            batch = todo[i : i + 50]
            q = urllib.parse.urlencode({
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "format": "json",
                "props": "labels|descriptions|claims",
                "languages": "en",
            })
            ents = None
            for attempt in range(5):
                try:
                    req = urllib.request.Request(f"{WD_API}?{q}", headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    ents = data.get("entities", {})
                    break
                except Exception as ex:
                    print(f"  wbgetentities retry {attempt}: {ex}", flush=True)
                    time.sleep(2 * (attempt + 1))
            if ents is None:
                continue
            for qid in batch:
                e = ents.get(qid, {})
                cl = e.get("claims", {})
                rec = {
                    "qid": qid,
                    "label_en": e.get("labels", {}).get("en", {}).get("value", ""),
                    "description_en": e.get("descriptions", {}).get("en", {}).get("value", ""),
                    "P1582_source_taxon": claim_vals(cl, "P1582"),
                    "P8061_agrovoc": claim_vals(cl, "P8061"),
                    "P3911_stw": claim_vals(cl, "P3911"),
                    "P1014_getty_aat": claim_vals(cl, "P1014"),
                    "P225_taxon_name": claim_vals(cl, "P225"),
                    "P10585_col_id": claim_vals(cl, "P10585"),
                    "P846_gbif_id": claim_vals(cl, "P846"),
                }
                cache[qid] = rec
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            time.sleep(0.35)
    return cache


def compose_lod_relation(wd_rel: str) -> str:
    """Compose Wikidata mapping relation for external LOD (AGROVOC/AAT/STW): never stronger than weakest link."""
    if wd_rel == "skos:exactMatch":
        return "skos:closeMatch"
    if wd_rel in ("skos:closeMatch", "skos:broadMatch", "skos:relatedMatch"):
        return wd_rel
    return "skos:broadMatch"


def plan_concept_lookup(c: dict):
    """Determine (mode, payload) for a Layer-1 concept following strict Opus priority order."""
    raw = c["skos_prefLabel"]
    facets = c["facets"]
    k_raw = norm_key(raw)
    k_head = norm_key(facets["substance_head"])
    pstate = facets["processing_state"]
    domain = facets["ghost_acres_domain"]
    bridge = c.get("skos_1866_bridge") or {}
    k_1866 = norm_key(bridge.get("prefLabel") or "")
    has_qualifying_state = pstate not in ("unspecified", "raw_unprocessed", "live")

    # 1. Explicit customs residual
    if RESIDUAL_RE.match(k_raw) or RESIDUAL_RE.match(k_head):
        return ("residual", None)

    # 2. Compound headings (explicit list)
    for k in (k_raw, k_head):
        if k in COMPOUND_HEADINGS:
            return ("compound", COMPOUND_HEADINGS[k])

    # 3. Exact canonical substance map on full heading or head
    for k in (k_raw, k_head):
        if k in CANONICAL_SUBSTANCE_MAP:
            term, taxon, rel = CANONICAL_SUBSTANCE_MAP[k]
            if k != k_raw or has_qualifying_state:
                if rel in ("skos:exactMatch", "skos:closeMatch"):
                    rel = "skos:broadMatch"
            return ("single", (term, taxon, rel, "canonical_exact"))

    # 4. Manufactured goods: detect specific product class first; attach raw material via made_of_material!
    if domain == "manufactured_goods" or pstate == "manufactured":
        for prod_kw, prod_term in [
            (r"\b(boots?|shoes?|footwear)\b", "footwear"),
            (r"\bgloves?\b", "glove"),
            (r"\bstoves?\b", "stove"),
            (r"\bnails?\b", "nail"),
            (r"\banchors?\b", "anchor"),
            (r"\bbolts?\s+and\s+nuts?\b", "fastener"),
            (r"\b(cordage|ropes?|cables?)\b", "rope"),
            (r"\btwine\b", "twine"),
            (r"\b(clothing|apparel)\b", "clothing"),
            (r"\byarns?\b", "yarn"),
            (r"\b(piece goods|cloth|fabrics?|manufactures.*(cotton|silk|wool|woollen|linen))\b", "textile"),
            (r"\b(cotton|silk|wool|woollen|linen)\s+manufactures\b", "textile"),
            (r"\bfurniture\b", "furniture"),
            (r"\bcarriages?\b", "carriage"),
            (r"\bmachinery\b", "machine"),
            (r"\bhardware\b", "household hardware"),
            (r"\bsewing machines?\b", "sewing machine"),
            (r"\bmusical instruments?\b", "musical instrument"),
            (r"\bclocks?\b", "clock"),
            (r"\bwatches?\b", "watch"),
            (r"\btoys?\b", "toy"),
            (r"\bbooks?\b", "book"),
            (r"\bpaper\b", "paper"),
            (r"\bglass\b", "glass"),
            (r"\b(earthenware|pottery)\b", "earthenware"),
            (r"\b(chinaware|porcelain)\b", "porcelain"),
            (r"\bmatches?\b", "match"),
            (r"\bcement\b", "cement"),
            (r"\bbeads?\b", "bead"),
            (r"\bgunpowder\b", "gunpowder"),
            (r"\bbiscuits?\b", "biscuit"),
        ]:
            if re.search(prod_kw, k_raw):
                return ("single", (prod_term, None, "skos:broadMatch", "manufactured_product_class"))
        # If generic manufactured good with no specific product class, do NOT falsely anchor to raw element/fiber!
        return ("unmatched_manufactured", None)

    # 5. Curated 1866 SKOS concept runs BEFORE prefix matching (Opus P0 #6!)
    if k_1866 and k_1866 in CANONICAL_SUBSTANCE_MAP:
        term, taxon, rel = CANONICAL_SUBSTANCE_MAP[k_1866]
        if k_1866 != k_raw or has_qualifying_state or bridge.get("bridge_relation") == "broader_1866_concept":
            if rel in ("skos:exactMatch", "skos:closeMatch"):
                rel = "skos:broadMatch"
        return ("single", (term, taxon, rel, "skos_1866_curated"))

    # 6. Prefix match on canonical substance map — ALWAYS broadMatch when extra tokens or state exist!
    toks = k_head.split()
    for plen in (3, 2, 1):
        if len(toks) >= plen:
            pref = " ".join(toks[:plen])
            if pref in CANONICAL_SUBSTANCE_MAP:
                term, taxon, rel = CANONICAL_SUBSTANCE_MAP[pref]
                # Guard: never map raw ore/oil/seed/cake via bare prefix of wrong substance
                if pref == "fish" and "oil" in k_raw:
                    term, taxon, rel = "fish oil", None, "skos:broadMatch"
                elif pref == "cotton" and "seed" in k_raw:
                    term, taxon, rel = ("cottonseed oil" if "oil" in k_raw else "cottonseed"), None, "skos:broadMatch"
                elif pref == "iron" and "ore" in k_raw:
                    term, taxon, rel = "iron ore", None, "skos:broadMatch"
                elif pref in ("lead", "tin", "copper", "silver", "cobalt", "zinc", "manganese", "antimony") and "ore" in k_raw:
                    ore_key = f"{pref} ore"
                    if ore_key in CANONICAL_SUBSTANCE_MAP:
                        term, taxon, rel = CANONICAL_SUBSTANCE_MAP[ore_key]
                elif len(toks) > plen or k_head != k_raw or has_qualifying_state:
                    if rel in ("skos:exactMatch", "skos:closeMatch"):
                        rel = "skos:broadMatch"
                return ("single", (term, taxon, rel, "canonical_prefix_broad"))

    # 7. General exact-lexical lookup (only on clean head/singular, guarded by instance_of!)
    rel = "skos:broadMatch" if (k_head != k_raw or has_qualifying_state) else "skos:exactMatch"
    cands = []
    if k_head and len(k_head) >= 3:
        cands.append(k_head)
        if " " not in k_head:
            s = singularize(k_head)
            if s != k_head:
                cands.append(s)
    return ("lexical", (cands, rel))


def main():
    rejections = load_rejections()
    concepts = [json.loads(l) for l in open(GROUND / "commodities_concepts_v3.jsonl", encoding="utf-8") if l.strip()]

    # Plan lookups & collect all Wikidata terms needed (commodities, taxa, materials)
    plans = {}
    all_terms = set()
    for _, mat_term in MATERIAL_DETECT:
        all_terms.add(mat_term)
    for c in concepts:
        mode, payload = plan_concept_lookup(c)
        plans[c["concept_id"]] = (mode, payload)
        if mode == "single":
            term, taxon, _, _ = payload
            all_terms.add(term)
            if taxon:
                all_terms.add(taxon)
        elif mode == "compound":
            for term, taxon in payload:
                all_terms.add(term)
                if taxon:
                    all_terms.add(taxon)
        elif mode == "lexical":
            for t in payload[0]:
                all_terms.add(t)

    # Also ensure 'bone' (Q265868) isn't blocked by Q112826905 in FORBIDDEN_INSTANCE_OF
    # Check: Q265868 has Q112826905 in instance_of, whereas fingernail Q36864 is explicitly in AUDIT_REJECTIONS!
    FORBIDDEN_INSTANCE_OF.discard("Q112826905")

    wd_by_term = query_wikidata_terms(all_terms)

    # Resolve base material QIDs for oe:madeOfMaterial
    material_qids = {}
    for _, mat_term in MATERIAL_DETECT:
        hit = pick_commodity_candidate(mat_term, wd_by_term.get(mat_term, []), rejections)
        if hit:
            material_qids[mat_term] = {"qid": hit["qid"], "label": hit["label"]}

    # Track exactMatch uniqueness (Opus P0 #5: at most ONE htc concept asserts exactMatch to any QID!)
    exact_used_qids = {}

    def apply_exact_guard(rel: str, qid: str, pstate: str, cid: str):
        if rel != "skos:exactMatch":
            return rel
        if pstate not in ("unspecified", "raw_unprocessed", "live"):
            return "skos:broadMatch"
        if qid in exact_used_qids:
            return "skos:closeMatch"
        exact_used_qids[qid] = cid
        return "skos:exactMatch"

    for c in concepts:
        cid = c["concept_id"]
        raw = c["skos_prefLabel"]
        k_raw = norm_key(raw)
        pstate = c["facets"]["processing_state"]
        domain = c["facets"]["ghost_acres_domain"]
        mode, payload = plans[cid]

        # Attach oe:madeOfMaterial for manufactured goods and ores
        if domain == "manufactured_goods" or pstate in ("manufactured", "raw_ore"):
            mats = []
            seen_mq = set()
            for pat, mterm in MATERIAL_DETECT:
                if re.search(pat, k_raw) and not re.search(r"\bnot\s+of\s+" + mterm, k_raw):
                    mhit = material_qids.get(mterm)
                    if mhit and mhit["qid"] not in seen_mq:
                        mats.append(mhit)
                        seen_mq.add(mhit["qid"])
            if mats:
                c["made_of_material"] = mats

        if mode == "residual":
            c["status"] = "customs_residual_category"
            continue

        if mode == "compound":
            comps = []
            taxa = []
            for term, taxon_term in payload:
                hit = pick_commodity_candidate(term, wd_by_term.get(term.lower(), []), rejections)
                if hit:
                    comps.append({
                        "qid": hit["qid"],
                        "wd_label": hit["label"],
                        "wd_description": hit["desc"],
                        "mapping_relation": "skos:relatedMatch",
                        "matched_via_term": term,
                    })
                if taxon_term:
                    thit = pick_taxon_candidate(taxon_term, wd_by_term.get(taxon_term.lower(), []))
                    if thit:
                        taxa.append({
                            "qid": thit["qid"],
                            "taxon_name": thit["label"],
                            "relation": "curated_source_taxon",
                        })
            if comps:
                c["status"] = "grounded_compound_commodity"
                c["wikidata_anchor"] = {
                    "mapping_relation": "skos:relatedMatch",
                    "qid": comps[0]["qid"],
                    "wd_label": " + ".join(x["wd_label"] for x in comps),
                    "wd_description": " | ".join(x["wd_description"] for x in comps),
                    "component_substances": comps,
                    "source_authority": f"wikidata_slim:{WD_SNAPSHOT}",
                    "match_rule": "compound_heading",
                }
                c["source_taxa"] = taxa
            continue

        if mode == "single":
            term, taxon_term, rel, rule_name = payload
            hit = pick_commodity_candidate(term, wd_by_term.get(term.lower(), []), rejections)
            if hit:
                final_rel = apply_exact_guard(rel, hit["qid"], pstate, cid)
                c["status"] = "grounded_wikidata_v3"
                c["wikidata_anchor"] = {
                    "mapping_relation": final_rel,
                    "qid": hit["qid"],
                    "wd_label": hit["label"],
                    "wd_description": hit["desc"],
                    "matched_via_term": term,
                    "source_authority": f"wikidata_slim:{WD_SNAPSHOT}",
                    "match_rule": rule_name,
                }
            if taxon_term:
                thit = pick_taxon_candidate(taxon_term, wd_by_term.get(taxon_term.lower(), []))
                if thit:
                    c["source_taxa"].append({
                        "qid": thit["qid"],
                        "taxon_name": thit["label"],
                        "relation": "curated_source_taxon",
                    })
            continue

        if mode == "lexical":
            cand_terms, rel = payload
            for t in cand_terms:
                hit = pick_commodity_candidate(t, wd_by_term.get(t.lower(), []), rejections)
                if hit:
                    final_rel = apply_exact_guard(rel, hit["qid"], pstate, cid)
                    c["status"] = "grounded_wikidata_lexical"
                    c["wikidata_anchor"] = {
                        "mapping_relation": final_rel,
                        "qid": hit["qid"],
                        "wd_label": hit["label"],
                        "wd_description": hit["desc"],
                        "matched_via_term": t,
                        "source_authority": f"wikidata_slim:{WD_SNAPSHOT}",
                        "match_rule": "lexical_type_checked",
                    }
                    break
            continue

    # Enrich ALL matched QIDs + component QIDs + source_taxa QIDs via live Wikidata wbgetentities
    all_qids = []
    for c in concepts:
        a = c.get("wikidata_anchor")
        if a:
            if a.get("component_substances"):
                for comp in a["component_substances"]:
                    all_qids.append(comp["qid"])
            elif a.get("qid"):
                all_qids.append(a["qid"])
        for t in c.get("source_taxa") or []:
            all_qids.append(t["qid"])

    enrich_cache = enrich_qids_wikidata_api(all_qids, GROUND / "wd_commodity_enrichment_cache.jsonl")

    # Fetch P1582 source taxa discovered on commodity QIDs
    p1582_qids = []
    for q in set(all_qids):
        ec = enrich_cache.get(q, {})
        for tq in ec.get("P1582_source_taxon", []):
            p1582_qids.append(tq)
    if p1582_qids:
        enrich_cache = enrich_qids_wikidata_api(p1582_qids, GROUND / "wd_commodity_enrichment_cache.jsonl")

    # Attach composed external LOD (AGROVOC w/ FIXED c_ prefix, STW Economics, Getty AAT) + P1582 taxa
    for c in concepts:
        a = c.get("wikidata_anchor")
        # Enrich any pre-populated curated source_taxa with CoL ID & P225 taxon name
        for t in c.get("source_taxa") or []:
            tec = enrich_cache.get(t["qid"], {})
            if tec.get("P225_taxon_name"):
                t["taxon_name"] = tec["P225_taxon_name"][0]
            if tec.get("P10585_col_id"):
                t["col_id"] = tec["P10585_col_id"][0]

        if not a:
            continue

        wd_rel = a["mapping_relation"]
        # Do NOT inherit barrel AAT/AGROVOC onto staves/hoops (part/whole relatedMatch)!
        skip_ext_lod = (wd_rel == "skos:relatedMatch" and a.get("matched_via_term") == "barrel")
        target_qids = [x["qid"] for x in a["component_substances"]] if a.get("component_substances") else [a["qid"]]

        agrovoc_ids, stw_ids, aat_ids = [], [], []
        existing_tq = {t["qid"] for t in c["source_taxa"]}

        for q in target_qids:
            ec = enrich_cache.get(q)
            if not ec:
                continue
            if not skip_ext_lod:
                for aid in ec.get("P8061_agrovoc", []):
                    # Opus P0 #1 FIX: P8061 values ALREADY start with 'c_'! Never double-prefix!
                    clean_ag = aid if aid.startswith("c_") else f"c_{aid}"
                    if clean_ag not in agrovoc_ids:
                        agrovoc_ids.append(clean_ag)
                for sid in ec.get("P3911_stw", []):
                    if sid not in stw_ids:
                        stw_ids.append(sid)
                for gid in ec.get("P1014_getty_aat", []):
                    if gid not in aat_ids:
                        aat_ids.append(gid)
            # Only inherit P1582 source_taxon from exact/close commodity matches (never generic broad classes like 'tannin' -> quebracho!)
            if wd_rel in ("skos:exactMatch", "skos:closeMatch"):
                for tq in ec.get("P1582_source_taxon", []):
                    if tq not in existing_tq:
                        tec = enrich_cache.get(tq, {})
                        c["source_taxa"].append({
                            "qid": tq,
                            "taxon_name": (tec.get("P225_taxon_name") or [tec.get("label_en", "")])[0],
                            "col_id": (tec.get("P10585_col_id") or [""])[0],
                            "relation": "P1582_natural_product_of_taxon",
                        })
                        existing_tq.add(tq)

        composed_rel = compose_lod_relation(wd_rel)
        ext = {}
        if agrovoc_ids:
            ext["agrovoc_relation"] = composed_rel
            ext["agrovoc_ids"] = agrovoc_ids
            ext["agrovoc_uris"] = [f"http://aims.fao.org/aos/agrovoc/{x}" for x in agrovoc_ids]
        if stw_ids:
            ext["stw_relation"] = composed_rel
            ext["stw_ids"] = stw_ids
            ext["stw_uris"] = [f"http://zbw.eu/stw/descriptor/{x}" for x in stw_ids]
        if aat_ids:
            ext["getty_aat_relation"] = composed_rel
            ext["getty_aat_ids"] = aat_ids
            ext["getty_aat_uris"] = [f"http://vocab.getty.edu/aat/{x}" for x in aat_ids]
        c["external_lod_anchors"] = ext

    # Promote v3 as the canonical commodities_concepts.jsonl
    with open(GROUND / "commodities_concepts.jsonl", "w", encoding="utf-8") as fh:
        for c in concepts:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    # Write updated review queue
    review_q = []
    st_cnt = Counter()
    st_rows = Counter()
    rel_cnt = Counter()
    rel_rows = Counter()
    for c in concepts:
        st = c["status"]
        st_cnt[st] += 1
        st_rows[st] += c["total_rows"]
        a = c.get("wikidata_anchor")
        if a:
            rel_cnt[a["mapping_relation"]] += 1
            rel_rows[a["mapping_relation"]] += c["total_rows"]
        elif st != "customs_residual_category":
            review_q.append((
                c["total_rows"],
                st,
                c["concept_id"],
                c["skos_prefLabel"],
                c["facets"]["substance_head"],
                c["facets"]["ghost_acres_domain"],
                c["facets"]["sitc_code"],
            ))
    review_q.sort(reverse=True)
    with open(GROUND / "commodities_review_queue.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["total_rows", "queue_type", "concept_id", "commodity_as_printed", "substance_head", "ghost_acres_domain", "sitc_code"])
        w.writerows(review_q)

    tot_rows = sum(st_rows.values())
    g_cnt = sum(rel_cnt.values())
    g_rows = sum(rel_rows.values())
    print("\n=== COMMODITIES GROUNDING v3 SUMMARY (OPUS P0/P1 FIXED) ===")
    print(f"Total Layer-1 concepts: {len(concepts):,} ({tot_rows:,} rows)")
    for st, cnt in st_cnt.most_common():
        print(f"  {st:30s}: {cnt:4d} concepts | {st_rows[st]:7,d} rows ({st_rows[st]/tot_rows*100:5.1f}%)")
    print("\n=== RELATION BREAKDOWN (NO STATE COLLAPSE, NO TAXA IN *MATCH) ===")
    for r, cnt in rel_cnt.most_common():
        print(f"  {r:22s}: {cnt:4d} concepts | {rel_rows[r]:7,d} rows ({rel_rows[r]/tot_rows*100:5.1f}%)")
    print(f"  TOTAL GROUNDED TO WD  : {g_cnt:4d} concepts | {g_rows:7,d} rows ({g_rows/tot_rows*100:5.1f}%)")
    print(f"  + RESIDUALS           : {g_cnt+st_cnt['customs_residual_category']:4d} concepts | {g_rows+st_rows['customs_residual_category']:7,d} rows ({(g_rows+st_rows['customs_residual_category'])/tot_rows*100:5.1f}%)")

    # Quick audit of Opus's specific P0 trouble cases
    print("\n=== OPUS P0 SPOT-CHECK ===")
    check_ids = {"htc:0130","htc:0207","htc:0241","htc:0278","htc:0344","htc:0369","htc:0436","htc:0686","htc:0804","htc:0540","htc:1451","htc:0625","htc:0157","htc:0323","htc:0367","htc:0133","htc:0092","htc:0127","htc:0109","htc:0118","htc:0257","htc:0039","htc:0196","htc:0105","htc:0003","htc:0013","htc:0051","htc:0074","htc:0075","htc:0136"}
    by_id = {c["concept_id"]: c for c in concepts}
    for cid in sorted(check_ids):
        c = by_id.get(cid)
        if not c:
            continue
        a = c.get("wikidata_anchor")
        astr = f"{a['mapping_relation']} {a['qid']} ({a['wd_label']})" if a else c["status"]
        tstr = ",".join(t["taxon_name"] for t in c["source_taxa"])
        mstr = ",".join(m["label"] for m in c["made_of_material"])
        print(f"  {cid} {c['skos_prefLabel']:36s} -> {astr:36s} | dom={c['facets']['ghost_acres_domain']} state={c['facets']['processing_state']} taxa=[{tstr}] mat=[{mstr}]")


if __name__ == "__main__":
    main()
