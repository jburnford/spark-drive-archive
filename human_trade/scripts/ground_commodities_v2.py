#!/usr/bin/env python3
"""
Ground Layer-1 (`human_transcribed`) archival commodity concepts (`htc:0001`..`htc:2066`)
against:
  1. Verified `ceylon/spine` commodity & taxon groundings (kept as highest priority)
  2. Local Wikidata 2026-11-09 slim Parquet dump (`/mnt/data/jic823/wikidata/20261109/slim/*.parquet`)
     via DuckDB (strictly filtered to materials/commodities/foods/crops/taxa/goods; ZERO QIDs from memory)
  3. Live Wikidata `wbgetentities` enrichment (50 QIDs/call) for verified external LOD anchors:
     - `P1582`: natural product of taxon (bridged to Catalogue of Life where available)
     - `P4112`: FAO AGROVOC concept ID
     - `P1014`: Getty Art & Architecture Thesaurus (AAT) ID
     - `P225` / `P10585`: Linnaean taxon name & Catalogue of Life ID

Preserves the Two-Layer Archival SKOS model:
  - Layer A: Local opaque `skos:Concept` (`htc:0001`..`htc:2066`) with verbatim printed customs label,
    decomposed `processing_state`, `substance_head`, SITC Rev. 4 `broadMatch`, Theodoridis (2018) bucket,
    and Ghost Acres book domain.
  - Layer B: Reversible SKOS mapping links (`skos:exactMatch`, `skos:closeMatch`, `skos:broadMatch`)
    plus AGROVOC, Getty AAT, and biological source taxa (`P1582`).
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
UA = "OpenEmpireLODGrounding/0.2 (University of Saskatchewan HGIS Lab; jim.clifford@usask.ca)"


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


# Catch-all customs residuals (never falsely map to a concrete commodity QID)
RESIDUAL_RE = re.compile(
    r"^(other articles|other goods|other woods|other timber|other sorts|other kinds|other descriptions|"
    r"other manufactures|other animals|other grains|other seeds|other fruits|other fish|other meats|"
    r"other oils|other furs|other skins|other hides|other metals|other minerals|other chemicals|"
    r"goods unenumerated|articles unenumerated|unenumerated|miscellaneous|sundries|all other.*|"
    r"non enumerated.*|other unenumerated.*)$",
    re.I,
)

# 19th-century British/Canadian customs terms -> modern standard English lookup terms (NO QIDs hardcoded!)
CUSTOMS_TERM_MAP = {
    "planks and boards": [("lumber", "skos:closeMatch")],
    "planks": [("plank", "skos:closeMatch"), ("lumber", "skos:broadMatch")],
    "boards": [("lumber", "skos:broadMatch")],
    "deals": [("lumber", "skos:broadMatch")],
    "deals and battens": [("lumber", "skos:broadMatch")],
    "deal ends": [("lumber", "skos:broadMatch")],
    "battens": [("batten", "skos:closeMatch")],
    "staves": [("barrel", "skos:broadMatch")],
    "staves other": [("barrel", "skos:broadMatch")],
    "staves standard": [("barrel", "skos:broadMatch")],
    "standard staves": [("barrel", "skos:broadMatch")],
    "wood and timber staves": [("barrel", "skos:broadMatch")],
    "staves west india": [("barrel", "skos:broadMatch")],
    "scantling": [("lumber", "skos:closeMatch")],
    "saw logs": [("timber", "skos:closeMatch")],
    "logs": [("timber", "skos:closeMatch")],
    "wood manufactures": [("wood", "skos:broadMatch")],
    "woollen manufactures": [("wool", "skos:broadMatch")],
    "woolen manufactures": [("wool", "skos:broadMatch")],
    "cotton manufactures": [("cotton", "skos:broadMatch")],
    "linen manufactures": [("linen", "skos:broadMatch")],
    "silk manufactures": [("silk", "skos:broadMatch")],
    "leather manufactures": [("leather", "skos:broadMatch")],
    "iron manufactures": [("iron", "skos:broadMatch")],
    "manufactures": [("manufactured good", "skos:broadMatch")],
    "shingles": [("wood shingle", "skos:exactMatch")],
    "laths": [("lath", "skos:exactMatch")],
    "lathwood": [("lath", "skos:closeMatch")],
    "firewood": [("firewood", "skos:exactMatch")],
    "sleepers": [("railroad tie", "skos:exactMatch")],
    "railway ties": [("railroad tie", "skos:exactMatch")],
    "masts": [("mast", "skos:exactMatch")],
    "spars": [("spar", "skos:exactMatch")],
    "oars": [("oar", "skos:exactMatch")],
    "handspikes": [("wood", "skos:broadMatch")],
    "knees and futtocks": [("timber", "skos:broadMatch")],
    "pulpwood": [("pulpwood", "skos:exactMatch")],
    "wood pulp": [("pulp", "skos:closeMatch")],
    "timber oak": [("quercus", "skos:closeMatch")],
    "oak": [("quercus", "skos:closeMatch")],
    "timber pine": [("pine", "skos:closeMatch")],
    "timber white pine": [("pinus strobus", "skos:closeMatch")],
    "white pine": [("pinus strobus", "skos:closeMatch")],
    "red pine": [("pinus resinosa", "skos:closeMatch")],
    "timber red pine": [("pinus resinosa", "skos:closeMatch")],
    "timber elm": [("elm", "skos:closeMatch")],
    "elm": [("elm", "skos:closeMatch")],
    "timber ash": [("ash wood", "skos:closeMatch"), ("fraxinus", "skos:closeMatch")],
    "timber birch": [("birch", "skos:closeMatch")],
    "birch": [("birch", "skos:closeMatch")],
    "timber tamarac": [("larix laricina", "skos:closeMatch")],
    "timber tamarack": [("larix laricina", "skos:closeMatch")],
    "tamarac": [("larix laricina", "skos:closeMatch")],
    "timber maple": [("maple", "skos:closeMatch")],
    "timber walnut": [("walnut", "skos:closeMatch")],
    "timber fir": [("fir", "skos:closeMatch")],
    "timber cedar": [("cedar", "skos:closeMatch")],
    "timber spruce": [("spruce", "skos:closeMatch")],
    "timber hemlock": [("tsuga", "skos:closeMatch")],
    "timber basswood": [("tilia", "skos:closeMatch")],
    "timber butternut": [("juglans cinerea", "skos:closeMatch")],
    "timber hickory": [("hickory", "skos:closeMatch")],
    "timber beech": [("beech", "skos:closeMatch")],
    "timber poplar": [("poplar", "skos:closeMatch")],
    "sawed or split": [("lumber", "skos:broadMatch")],
    "hewn": [("timber", "skos:broadMatch")],
    "wood hewn": [("timber", "skos:broadMatch")],
    "wood sawn or split": [("lumber", "skos:broadMatch")],
    "wood and timber": [("timber", "skos:closeMatch")],
    "mahogany": [("mahogany", "skos:exactMatch")],
    "teak": [("teak", "skos:exactMatch")],
    "logwood": [("haematoxylum campechianum", "skos:closeMatch")],
    "fustic": [("maclura tinctoria", "skos:closeMatch")],
    "rosewood": [("rosewood", "skos:exactMatch")],
    "ebony": [("ebony", "skos:exactMatch")],
    "boxwood": [("boxwood", "skos:exactMatch")],
    "lignum vitae": [("lignum vitae", "skos:exactMatch")],
    "dyewoods": [("dye", "skos:broadMatch")],
    "dye woods": [("dye", "skos:broadMatch")],
    "dye woods logwood": [("haematoxylum campechianum", "skos:closeMatch")],
    "bark for tanners and dyers use": [("tanbark", "skos:exactMatch")],
    "bark for tanners": [("tanbark", "skos:exactMatch")],
    "bark for tanning": [("tanbark", "skos:exactMatch")],
    "tanning bark": [("tanbark", "skos:exactMatch")],
    "oak bark": [("tanbark", "skos:closeMatch")],
    "hemlock bark": [("tanbark", "skos:closeMatch")],
    "mimosa bark": [("tanbark", "skos:closeMatch")],
    "valonia": [("quercus ithaburensis", "skos:closeMatch")],
    "cutch": [("catechu", "skos:exactMatch")],
    "terra japonica": [("catechu", "skos:exactMatch")],
    "gambier": [("uncaria gambir", "skos:closeMatch")],
    "sumach": [("sumac", "skos:closeMatch")],
    "shumach": [("sumac", "skos:closeMatch")],
    "sumac": [("sumac", "skos:closeMatch")],
    "myrobalans": [("terminalia chebula", "skos:closeMatch")],
    "divi divi": [("libidibia coriaria", "skos:closeMatch")],
    "wheat meal and flour": [("wheat flour", "skos:exactMatch")],
    "wheat flour": [("wheat flour", "skos:exactMatch")],
    "flour": [("flour", "skos:exactMatch")],
    "meal": [("flour", "skos:broadMatch")],
    "oatmeal": [("oatmeal", "skos:exactMatch")],
    "corn meal": [("cornmeal", "skos:exactMatch")],
    "indian corn": [("maize", "skos:exactMatch")],
    "indian corn or maize": [("maize", "skos:exactMatch")],
    "maize": [("maize", "skos:exactMatch")],
    "barley and rye": [("hordeum vulgare", "skos:relatedMatch"), ("secale cereale", "skos:relatedMatch")],
    "pease": [("pea", "skos:exactMatch")],
    "peas": [("pea", "skos:exactMatch")],
    "beans": [("bean", "skos:exactMatch")],
    "oats": [("oat", "skos:exactMatch")],
    "wheat": [("wheat", "skos:exactMatch")],
    "barley": [("hordeum vulgare", "skos:exactMatch")],
    "rye": [("secale cereale", "skos:exactMatch")],
    "buckwheat": [("buckwheat", "skos:exactMatch")],
    "malt": [("malt", "skos:exactMatch")],
    "hops": [("hops", "skos:exactMatch")],
    "bran": [("bran", "skos:exactMatch")],
    "hay": [("hay", "skos:exactMatch")],
    "horned cattle": [("cattle", "skos:exactMatch")],
    "neat cattle": [("cattle", "skos:exactMatch")],
    "oxen and bulls": [("cattle", "skos:closeMatch")],
    "cows": [("cattle", "skos:closeMatch")],
    "calves": [("calf", "skos:exactMatch")],
    "swine": [("pig", "skos:exactMatch")],
    "hogs": [("pig", "skos:exactMatch")],
    "pigs": [("pig", "skos:exactMatch")],
    "sheep": [("sheep", "skos:exactMatch")],
    "sheep and lambs": [("sheep", "skos:exactMatch")],
    "horses": [("horse", "skos:exactMatch")],
    "poultry": [("poultry", "skos:exactMatch")],
    "eggs in shell": [("egg as food", "skos:exactMatch")],
    "eggs": [("egg as food", "skos:exactMatch")],
    "hams": [("ham", "skos:exactMatch")],
    "bacon and hams": [("bacon", "skos:relatedMatch"), ("ham", "skos:relatedMatch")],
    "bacon": [("bacon", "skos:exactMatch")],
    "pork": [("pork", "skos:exactMatch")],
    "beef": [("beef", "skos:exactMatch")],
    "mutton": [("lamb and mutton", "skos:exactMatch")],
    "meat": [("meat", "skos:exactMatch")],
    "tongues": [("beef tongue", "skos:broadMatch")],
    "butter": [("butter", "skos:exactMatch")],
    "cheese": [("cheese", "skos:exactMatch")],
    "lard": [("lard", "skos:exactMatch")],
    "tallow and stearine": [("tallow", "skos:closeMatch"), ("stearin", "skos:relatedMatch")],
    "tallow": [("tallow", "skos:exactMatch")],
    "stearine": [("stearin", "skos:exactMatch")],
    "hides": [("hide", "skos:exactMatch")],
    "hides or pieces of": [("hide", "skos:closeMatch")],
    "hides raw": [("hide", "skos:closeMatch")],
    "hides tanned": [("leather", "skos:closeMatch")],
    "leather": [("leather", "skos:exactMatch")],
    "skins furs pelts seal": [("sealskin", "skos:exactMatch")],
    "skins seal": [("sealskin", "skos:exactMatch")],
    "skins furs pelts goat": [("goatskin", "skos:exactMatch")],
    "skins goat": [("goatskin", "skos:exactMatch")],
    "skins furs pelts sheep": [("sheepskin", "skos:exactMatch")],
    "skins sheep": [("sheepskin", "skos:exactMatch")],
    "skins furs pelts lamb": [("sheepskin", "skos:closeMatch")],
    "skins furs pelts calf": [("calfskin", "skos:exactMatch")],
    "skins furs pelts deer": [("buckskin", "skos:closeMatch")],
    "skins furs pelts": [("fur", "skos:broadMatch")],
    "furs": [("fur", "skos:exactMatch")],
    "pelts": [("hide", "skos:closeMatch")],
    "horns": [("horn", "skos:exactMatch")],
    "hoofs": [("hoof", "skos:exactMatch")],
    "bones": [("bone", "skos:exactMatch")],
    "bristles": [("bristle", "skos:exactMatch")],
    "wool sheep and lambs": [("wool", "skos:exactMatch")],
    "wool": [("wool", "skos:exactMatch")],
    "cotton": [("cotton", "skos:exactMatch")],
    "cotton raw": [("cotton", "skos:exactMatch")],
    "flax": [("flax", "skos:exactMatch")],
    "hemp": [("hemp", "skos:exactMatch")],
    "jute": [("jute", "skos:exactMatch")],
    "silk": [("silk", "skos:exactMatch")],
    "linen": [("linen", "skos:exactMatch")],
    "rags": [("rag", "skos:exactMatch")],
    "esparto": [("esparto", "skos:exactMatch")],
    "ashes pot": [("potash", "skos:exactMatch")],
    "ashes pearl": [("potassium carbonate", "skos:closeMatch")],
    "pot and pearl ashes": [("potash", "skos:exactMatch")],
    "ashes": [("potash", "skos:closeMatch")],
    "barilla": [("barilla", "skos:exactMatch")],
    "alkali": [("alkali", "skos:exactMatch")],
    "soda": [("sodium carbonate", "skos:closeMatch")],
    "saltpetre": [("potassium nitrate", "skos:exactMatch")],
    "cubic nitre": [("sodium nitrate", "skos:exactMatch")],
    "nitrate of soda": [("sodium nitrate", "skos:exactMatch")],
    "brimstone": [("sulfur", "skos:exactMatch")],
    "guano": [("guano", "skos:exactMatch")],
    "oil palm": [("palm oil", "skos:exactMatch")],
    "palm oil": [("palm oil", "skos:exactMatch")],
    "oil olive": [("olive oil", "skos:exactMatch")],
    "olive oil": [("olive oil", "skos:exactMatch")],
    "oil train": [("whale oil", "skos:exactMatch")],
    "oil whale": [("whale oil", "skos:exactMatch")],
    "whale oil": [("whale oil", "skos:exactMatch")],
    "oil spermaceti": [("sperm oil", "skos:exactMatch")],
    "oil cod": [("cod liver oil", "skos:exactMatch")],
    "oil seal": [("seal oil", "skos:exactMatch")],
    "oil linseed": [("linseed oil", "skos:exactMatch")],
    "oil seed": [("vegetable oil", "skos:broadMatch")],
    "oil cocoa nut": [("coconut oil", "skos:exactMatch")],
    "oil turpentine": [("turpentine", "skos:exactMatch")],
    "oil mineral": [("petroleum", "skos:closeMatch")],
    "petroleum": [("petroleum", "skos:exactMatch")],
    "coal oil": [("kerosene", "skos:exactMatch")],
    "flaxseed and linseed": [("flax seed", "skos:exactMatch")],
    "linseed": [("flax seed", "skos:exactMatch")],
    "flaxseed": [("flax seed", "skos:exactMatch")],
    "flax seeds": [("flax seed", "skos:exactMatch")],
    "rapeseed": [("rapeseed", "skos:exactMatch")],
    "clover seed": [("clover", "skos:closeMatch")],
    "seeds": [("seed", "skos:broadMatch")],
    "oilseed cake": [("press cake", "skos:exactMatch")],
    "oil cake": [("press cake", "skos:exactMatch")],
    "oilcake": [("press cake", "skos:exactMatch")],
    "caoutchouc": [("natural rubber", "skos:exactMatch")],
    "india rubber": [("natural rubber", "skos:exactMatch")],
    "gutta percha": [("gutta-percha", "skos:exactMatch")],
    "cinchona": [("cinchona", "skos:exactMatch")],
    "peruvian bark": [("cinchona", "skos:exactMatch")],
    "dye stuffs": [("dye", "skos:broadMatch")],
    "dyestuffs": [("dye", "skos:broadMatch")],
    "indigo": [("indigo dye", "skos:exactMatch")],
    "madder": [("rubia tinctorum", "skos:closeMatch")],
    "cochineal": [("cochineal", "skos:exactMatch")],
    "turpentine": [("turpentine", "skos:exactMatch")],
    "rosin": [("rosin", "skos:exactMatch")],
    "tar": [("tar", "skos:exactMatch")],
    "pitch": [("pitch", "skos:exactMatch")],
    "beeswax": [("beeswax", "skos:exactMatch")],
    "wax": [("wax", "skos:exactMatch")],
    "whalebone": [("baleen", "skos:exactMatch")],
    "whale fins": [("baleen", "skos:exactMatch")],
    "ivory": [("ivory", "skos:exactMatch")],
    "elephants teeth": [("ivory", "skos:exactMatch")],
    "herrings": [("herring", "skos:exactMatch")],
    "cod": [("cod", "skos:exactMatch")],
    "salmon": [("salmon", "skos:exactMatch")],
    "mackerel": [("mackerel", "skos:exactMatch")],
    "lobsters": [("nephropidae", "skos:closeMatch")],
    "lobsters canned": [("nephropidae", "skos:closeMatch")],
    "oysters": [("oyster", "skos:exactMatch")],
    "fish": [("fish as food", "skos:closeMatch"), ("fish", "skos:broadMatch")],
    "apples": [("apple", "skos:exactMatch")],
    "potatoes": [("potato", "skos:exactMatch")],
    "onions": [("onion", "skos:exactMatch")],
    "oranges": [("orange", "skos:exactMatch")],
    "lemons": [("lemon", "skos:exactMatch")],
    "oranges and lemons": [("orange", "skos:relatedMatch"), ("lemon", "skos:relatedMatch")],
    "raisins": [("raisin", "skos:exactMatch")],
    "currants": [("zante currant", "skos:exactMatch")],
    "figs": [("fig", "skos:exactMatch")],
    "almonds": [("almond", "skos:exactMatch")],
    "sugar": [("sugar", "skos:exactMatch")],
    "sugar total": [("sugar", "skos:exactMatch")],
    "molasses": [("molasses", "skos:exactMatch")],
    "spirits rum": [("rum", "skos:exactMatch")],
    "spirits brandy": [("brandy", "skos:exactMatch")],
    "spirits geneva": [("jenever", "skos:exactMatch")],
    "rum": [("rum", "skos:exactMatch")],
    "brandy": [("brandy", "skos:exactMatch")],
    "whisky": [("whisky", "skos:exactMatch")],
    "whiskey": [("whisky", "skos:exactMatch")],
    "wine": [("wine", "skos:exactMatch")],
    "spirits": [("distilled beverage", "skos:broadMatch")],
    "ale beer and cider": [("beer", "skos:relatedMatch"), ("cider", "skos:relatedMatch")],
    "ale and beer": [("beer", "skos:exactMatch")],
    "coffee": [("coffee", "skos:exactMatch")],
    "tea": [("tea", "skos:exactMatch")],
    "cocoa": [("cocoa bean", "skos:closeMatch")],
    "tobacco": [("tobacco", "skos:exactMatch")],
    "rice": [("rice", "skos:exactMatch")],
    "pepper": [("black pepper", "skos:exactMatch")],
    "cinnamon": [("cinnamon", "skos:exactMatch")],
    "cloves": [("clove", "skos:exactMatch")],
    "ginger": [("ginger", "skos:exactMatch")],
    "nutmegs": [("nutmeg", "skos:exactMatch")],
    "pimento": [("allspice", "skos:exactMatch")],
    "sago": [("sago", "skos:exactMatch")],
    "tapioca": [("tapioca", "skos:exactMatch")],
    "arrowroot": [("arrowroot", "skos:exactMatch")],
    "opium": [("opium", "skos:exactMatch")],
    "salt": [("salt", "skos:exactMatch")],
    "coal": [("coal", "skos:exactMatch")],
    "iron": [("iron", "skos:exactMatch")],
    "iron pig": [("pig iron", "skos:exactMatch")],
    "pig and scrap iron": [("pig iron", "skos:closeMatch")],
    "iron bar": [("wrought iron", "skos:closeMatch")],
    "steel": [("steel", "skos:exactMatch")],
    "copper": [("copper", "skos:exactMatch")],
    "copper ore": [("copper ore", "skos:exactMatch")],
    "tin": [("tin", "skos:exactMatch")],
    "lead": [("lead", "skos:exactMatch")],
    "zinc": [("zinc", "skos:exactMatch")],
    "spelter": [("zinc", "skos:exactMatch")],
    "quicksilver": [("mercury", "skos:exactMatch")],
    "antimony": [("antimony", "skos:exactMatch")],
    "manganese": [("manganese", "skos:exactMatch")],
    "plumbago": [("graphite", "skos:exactMatch")],
    "gypsum": [("gypsum", "skos:exactMatch")],
    "plaster": [("gypsum", "skos:closeMatch")],
    "lime": [("calcium oxide", "skos:exactMatch")],
    "cement": [("cement", "skos:exactMatch")],
    "slate": [("slate", "skos:exactMatch")],
    "marble": [("marble", "skos:exactMatch")],
    "stone": [("stone", "skos:broadMatch")],
    "glass": [("glass", "skos:exactMatch")],
    "paper": [("paper", "skos:exactMatch")],
    "soap": [("soap", "skos:exactMatch")],
    "candles": [("candle", "skos:exactMatch")],
    "starch": [("starch", "skos:exactMatch")],
    "glue": [("adhesive", "skos:closeMatch")],
    "cordage": [("rope", "skos:exactMatch")],
    "canvas": [("canvas", "skos:exactMatch")],
    "machinery": [("machine", "skos:broadMatch")],
    "machinery manufactures": [("machine", "skos:broadMatch")],
    "carriages": [("carriage", "skos:exactMatch")],
    "hardware": [("household hardware", "skos:broadMatch")],
    "agricultural implements": [("agricultural machinery", "skos:exactMatch")],
    "boots and shoes": [("footwear", "skos:closeMatch")],
    "books": [("book", "skos:exactMatch")],
    "furniture": [("furniture", "skos:exactMatch")],
    "earthenware": [("earthenware", "skos:exactMatch")],
    "chinaware": [("porcelain", "skos:exactMatch")],
    "gunpowder": [("gunpowder", "skos:exactMatch")],
    "cork": [("cork", "skos:exactMatch")],
    "feathers": [("feather", "skos:exactMatch")],
    "hair": [("hair", "skos:exactMatch")],
    "sponge": [("sponge", "skos:closeMatch")],
    "lac": [("lac", "skos:exactMatch")],
    "shellac": [("shellac", "skos:exactMatch")],
    "gum arabic": [("gum arabic", "skos:exactMatch")],
    "gum": [("natural gum", "skos:broadMatch")],
    "resin": [("resin", "skos:exactMatch")],
    "camphor": [("camphor", "skos:exactMatch")],
    "borax": [("borax", "skos:exactMatch")],
    "alum": [("alum", "skos:exactMatch")],
    "arsenic": [("arsenic", "skos:exactMatch")],
    "quercitron": [("quercus velutina", "skos:closeMatch")],
    "annatto": [("annatto", "skos:exactMatch")],
    "turmeric": [("turmeric", "skos:exactMatch")],
    "safflower": [("safflower", "skos:exactMatch")],
    "orchil": [("orseille", "skos:exactMatch")],
    "indigo": [("indigo dye", "skos:exactMatch")],
    "madder root": [("rubia tinctorum", "skos:closeMatch")],
    "garancine": [("rubia tinctorum", "skos:closeMatch")],
    "senna": [("senna", "skos:closeMatch")],
    "rhubarb": [("rhubarb", "skos:exactMatch")],
    "jalap": [("ipomoea purga", "skos:closeMatch")],
    "ipecacuanha": [("carapichea ipecacuanha", "skos:closeMatch")],
    "sarsaparilla": [("smilax", "skos:closeMatch")],
    "liquorice": [("liquorice", "skos:exactMatch")],
    "licorice": [("liquorice", "skos:exactMatch")],
    "honey": [("honey", "skos:exactMatch")],
    "vinegar": [("vinegar", "skos:exactMatch")],
    "cider": [("cider", "skos:exactMatch")],
    "oil": [("oil", "skos:broadMatch")],
}

BAD_COMM_DESC_RE = re.compile(
    r"\b(film|movie|song|album|single|band|musician|singer|actor|actress|politician|painter|writer|novel|"
    r"poem|television|tv series|episode|video game|comic|magazine|newspaper|painting|sculpture|"
    r"given name|family name|surname|disambiguation|wikimedia|city|town|village|municipality|hamlet|"
    r"county|province|state of|country|river|lake|mountain|island|electoral district|railway station|"
    r"airport|university|college|school|church|racehorse|crater|asteroid|planet|natural monument|"
    r"heraldic|heraldry|oil platform|musical notation|constellation|company|corporation|brand|football|"
    r"basketball|baseball|hockey|tennis|boxing|cricket|play by|opera|symphony|character|fictional|"
    r"mytholog|deity|saint|pope|king|queen|duke|earl|baron|battle of|treaty of|war of|year|century|"
    r"language|dialect|letter of|alphabet|programming language|software|website|font|typeface|currency|"
    r"coin|unit of|postcode|zodiac|sign of the|human person|person who)\b",
    re.I,
)

GOOD_COMM_DESC_RE = re.compile(
    r"\b(material|substance|chemical|element|compound|mineral|metal|alloy|ore|rock|stone|fuel|oil|fat|wax|"
    r"resin|gum|dye|pigment|tannin|bark|wood|timber|lumber|plank|fiber|fibre|textile|fabric|cloth|yarn|"
    r"leather|hide|skin|fur|pelt|wool|silk|cotton|flax|hemp|jute|paper|pulp|glass|ceramic|pottery|brick|"
    r"food|crop|grain|cereal|flour|meal|powder|grinding|bread|meat|beef|pork|ham|bacon|fish|seafood|dairy|"
    r"milk|butter|cheese|egg|fruit|vegetable|nut|seed|spice|herb|tea|coffee|cocoa|sugar|syrup|alcohol|drink|"
    r"beverage|wine|beer|spirit|liquor|tobacco|drug|medicine|alkaloid|plant|tree|shrub|grass|animal|mammal|"
    r"livestock|ungulate|crustacean|bird|poultry|species|genus|family of|taxon|domesticated|cultivated|"
    r"product|commodity|goods|fertilizer|explosive|adhesive|soap|candle|rope|cordage|tool|implement|machine|"
    r"machinery|footwear|clothing|apparel|furniture|container|barrel|stave|shingle|railroad|agricultural|"
    r"industrial|natural|organic|dried|salted|cured|processed|rendered|edible|culinary|botanical|extract|"
    r"tincture|acid|salt|oxide|carbonate|nitrate|sulfate|sulphate|building material|construction|structural|"
    r"board|beam|lath|rigging|pole|propulsion|transport|vehicle|medium for recording|bound pages)\b",
    re.I,
)


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


def extract_lookup_targets(concept: dict):
    """Return list of (search_term, skos_rel) candidates for a Layer-1 commodity concept."""
    raw = concept["skos_prefLabel"]
    facets = concept.get("facets") or {}
    bridge = concept.get("skos_1866_bridge") or {}
    k_raw = norm_key(raw)
    k_head = norm_key(facets.get("substance_head", ""))
    k_skos = norm_key(bridge.get("prefLabel") or bridge.get("skos_concept") or "")
    has_state = facets.get("processing_state") not in (None, "", "raw_unprocessed", "unspecified")

    # 1. Explicit residual check
    if RESIDUAL_RE.match(k_raw) or RESIDUAL_RE.match(k_head):
        return [("__RESIDUAL__", "customs_residual_category")]

    # 2. Direct customs term map on full normalized string or substance head
    for k in (k_raw, k_head, k_skos):
        if k and k in CUSTOMS_TERM_MAP:
            return CUSTOMS_TERM_MAP[k]

    # 3. Prefix match on high-confidence customs heads (e.g. "wheat ...", "butter ...", "timber oak ...")
    for prefix_len in (3, 2, 1):
        toks = k_head.split()
        if len(toks) >= prefix_len:
            pref = " ".join(toks[:prefix_len])
            if pref in CUSTOMS_TERM_MAP:
                out = []
                for term, rel in CUSTOMS_TERM_MAP[pref]:
                    new_rel = "skos:closeMatch" if (len(toks) > prefix_len or has_state) else rel
                    out.append((term, new_rel))
                return out

    # 4. General lexical fallback: SKOS 1866 label, substance head, singularized head
    cands = []
    if k_skos:
        cands.append((k_skos, "skos:closeMatch"))
        cands.append((singularize(k_skos), "skos:closeMatch"))
    if k_head:
        rel = "skos:closeMatch" if has_state else "skos:exactMatch"
        cands.append((k_head, rel))
        if " " not in k_head:
            s = singularize(k_head)
            if s != k_head:
                cands.append((s, rel))
        else:
            parts = k_head.split()
            parts[-1] = singularize(parts[-1])
            s_phrase = " ".join(parts)
            if s_phrase != k_head:
                cands.append((s_phrase, rel))
    seen = set()
    uniq = []
    for t, r in cands:
        if t and len(t) >= 3 and t not in seen:
            seen.add(t)
            uniq.append((t, r))
    return uniq


def query_wikidata_commodities(search_terms: set):
    clean = sorted({t.lower().strip() for t in search_terms if t and t != "__RESIDUAL__" and len(t.strip()) >= 3})
    print(f"Querying Wikidata {WD_SNAPSHOT} slim Parquet for {len(clean):,} commodity terms...", flush=True)
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
      AND description_en IS NOT NULL
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


def pick_best_wd_commodity(term, cands, rejections):
    scored = []
    for c in cands:
        if (norm_key(term), c["qid"]) in rejections:
            continue
        desc = c["desc"]
        if BAD_COMM_DESC_RE.search(desc):
            continue
        if not GOOD_COMM_DESC_RE.search(desc):
            continue
        score = c["sitelinks"] * 1.5
        # Prefer substances/materials/foods/commodities over abstract classes
        if re.search(r"\b(commodity|material|food|grain|cereal|meat|wood|timber|lumber|metal|mineral|chemical|oil|fat|resin|dye|fibre|fiber|fabric|leather|hide|skin|fur|spice|beverage|crop|species|genus|taxon|livestock|domesticated)\b", desc, re.I):
            score += 40.0
        # Slight penalty for overly generic "genus of ..." when a concrete food/product exists with high sitelinks
        if re.search(r"^(genus|family|order|class) of\b", desc, re.I):
            score -= 10.0
        scored.append((score, c))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def enrich_qids_wikidata_api(qids: list, cache_path: Path):
    """Fetch P1582 (source taxon), P4112 (AGROVOC), P1014 (Getty AAT), P225 (taxon name), P10585 (CoL) via wbgetentities."""
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


def main():
    rejections = load_rejections()
    concepts = [json.loads(line) for line in open(GROUND / "commodities_concepts.jsonl", encoding="utf-8") if line.strip()]

    # Re-evaluate everything except verified ceylon/spine anchors (so fixes replace any prior slim match)
    targets_by_cid = {}
    all_terms = set()
    for c in concepts:
        anchor = c.get("wikidata_anchor")
        if anchor and anchor.get("qid") and c.get("status") in ("grounded_exact", "grounded_substance_head"):
            continue
        # Reset prior slim-pass state before re-matching
        if c.get("status") in ("grounded_wikidata_slim", "grounded_compound_commodity", "customs_residual_category"):
            c["wikidata_anchor"] = None
            c["status"] = "skos_1866_bridged_needs_wd" if c.get("skos_1866_bridge") else "local_concept_only_needs_wd"
        tlist = extract_lookup_targets(c)
        targets_by_cid[c["concept_id"]] = tlist
        for term, _ in tlist:
            if term != "__RESIDUAL__":
                all_terms.add(term)

    wd_by_term = query_wikidata_commodities(all_terms)

    # Apply verified Wikidata slim-dump matches
    newly_matched_audit = []
    for c in concepts:
        anchor = c.get("wikidata_anchor")
        if anchor and anchor.get("qid") and c.get("status") in ("grounded_exact", "grounded_substance_head"):
            continue
        tlist = targets_by_cid.get(c["concept_id"], [])
        if tlist and tlist[0][0] == "__RESIDUAL__":
            c["status"] = "customs_residual_category"
            c["wikidata_anchor"] = None
            continue

        is_multi = len(tlist) >= 2 and all(r == "skos:relatedMatch" for _, r in tlist)
        if is_multi:
            comps = []
            for term, rel in tlist:
                best = pick_best_wd_commodity(term, wd_by_term.get(term.lower(), []), rejections)
                if best:
                    comps.append({
                        "qid": best["qid"],
                        "wd_label": best["label"],
                        "wd_description": best["desc"],
                        "mapping_relation": rel,
                    })
            if comps:
                c["status"] = "grounded_compound_commodity"
                c["wikidata_anchor"] = {
                    "mapping_relation": "skos:relatedMatch",
                    "qid": comps[0]["qid"],
                    "wd_label": " + ".join(x["wd_label"] for x in comps),
                    "wd_description": " | ".join(x["wd_description"] for x in comps),
                    "component_substances": comps,
                    "source_taxa": [],
                    "source_authority": f"wikidata_slim:{WD_SNAPSHOT}",
                }
                newly_matched_audit.append((c["total_rows"], c["skos_prefLabel"], "+".join(x["qid"] for x in comps), c["wikidata_anchor"]["wd_label"], "multi"))
                continue

        for term, rel in tlist:
            best = pick_best_wd_commodity(term, wd_by_term.get(term.lower(), []), rejections)
            if best:
                c["status"] = "grounded_wikidata_slim"
                c["wikidata_anchor"] = {
                    "mapping_relation": rel,
                    "qid": best["qid"],
                    "wd_label": best["label"],
                    "wd_description": best["desc"],
                    "matched_via_term": term,
                    "source_taxa": [],
                    "source_authority": f"wikidata_slim:{WD_SNAPSHOT}",
                }
                newly_matched_audit.append((c["total_rows"], c["skos_prefLabel"], best["qid"], best["label"], best["desc"][:45]))
                break

    # Enrich all matched commodity QIDs with live Wikidata external LOD anchors (P1582, P4112 AGROVOC, P1014 AAT)
    all_qids = []
    for c in concepts:
        a = c.get("wikidata_anchor")
        if a and a.get("qid"):
            all_qids.append(a["qid"])
            for comp in a.get("component_substances", []):
                if comp.get("qid"):
                    all_qids.append(comp["qid"])

    enrich_cache = enrich_qids_wikidata_api(all_qids, GROUND / "wd_commodity_enrichment_cache.jsonl")

    taxon_qids = []
    for q in set(all_qids):
        ec = enrich_cache.get(q, {})
        for tq in ec.get("P1582_source_taxon", []):
            taxon_qids.append(tq)
    if taxon_qids:
        enrich_cache = enrich_qids_wikidata_api(taxon_qids, GROUND / "wd_commodity_enrichment_cache.jsonl")

    agrovoc_linked = 0
    stw_linked = 0
    aat_linked = 0
    taxon_linked = 0

    for c in concepts:
        a = c.get("wikidata_anchor")
        if not a or not a.get("qid"):
            continue
        q = a["qid"]
        ec = enrich_cache.get(q)
        if not ec:
            continue
        if ec.get("description_en") and not a.get("wd_description"):
            a["wd_description"] = ec["description_en"]
        ext = {}
        if ec.get("P8061_agrovoc"):
            ext["agrovoc_ids"] = ec["P8061_agrovoc"]
            ext["agrovoc_uris"] = [f"http://aims.fao.org/aos/agrovoc/c_{x}" for x in ec["P8061_agrovoc"]]
            agrovoc_linked += 1
        if ec.get("P3911_stw"):
            ext["stw_ids"] = ec["P3911_stw"]
            ext["stw_uris"] = [f"http://zbw.eu/stw/descriptor/{x}" for x in ec["P3911_stw"]]
            stw_linked += 1
        if ec.get("P1014_getty_aat"):
            ext["getty_aat_ids"] = ec["P1014_getty_aat"]
            ext["getty_aat_uris"] = [f"http://vocab.getty.edu/aat/{x}" for x in ec["P1014_getty_aat"]]
            aat_linked += 1
        if ext:
            c["external_lod_anchors"] = ext

        taxa = list(a.get("source_taxa") or [])
        existing_tq = {t.get("qid") for t in taxa if isinstance(t, dict)}
        if ec.get("P225_taxon_name") and q not in existing_tq:
            taxa.append({
                "qid": q,
                "taxon_name": ec["P225_taxon_name"][0],
                "col_id": (ec.get("P10585_col_id") or [""])[0],
                "relation": "is_taxon",
            })
            existing_tq.add(q)
        for tq in ec.get("P1582_source_taxon", []):
            if tq not in existing_tq:
                tec = enrich_cache.get(tq, {})
                taxa.append({
                    "qid": tq,
                    "taxon_name": (tec.get("P225_taxon_name") or [tec.get("label_en", "")])[0],
                    "col_id": (tec.get("P10585_col_id") or [""])[0],
                    "relation": "P1582_natural_product_of_taxon",
                })
                existing_tq.add(tq)
        if taxa:
            a["source_taxa"] = taxa
            taxon_linked += 1

    with open(GROUND / "commodities_concepts.jsonl", "w", encoding="utf-8") as fh:
        for c in concepts:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    review_q = []
    status_cnt = Counter()
    status_rows = Counter()
    for c in concepts:
        st = c["status"]
        status_cnt[st] += 1
        status_rows[st] += c["total_rows"]
        a = c.get("wikidata_anchor")
        if (not a or not a.get("qid")) and st != "customs_residual_category":
            facets = c.get("facets") or {}
            bridge = c.get("skos_1866_bridge") or {}
            review_q.append((
                c["total_rows"],
                st,
                c["concept_id"],
                c["skos_prefLabel"],
                facets.get("substance_head", ""),
                bridge.get("skos_concept", ""),
                c.get("skos_broadMatch_sitc", ""),
            ))
    review_q.sort(reverse=True)
    with open(GROUND / "commodities_review_queue.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["total_rows", "queue_type", "concept_id", "commodity_as_printed", "substance_head", "skos_1866_concept", "sitc_broad"])
        w.writerows(review_q)

    tot_rows = sum(status_rows.values())
    grounded_statuses = ("grounded_exact", "grounded_substance_head", "grounded_wikidata_slim", "grounded_compound_commodity")
    g_cnt = sum(status_cnt[s] for s in grounded_statuses)
    g_rows = sum(status_rows[s] for s in grounded_statuses)
    res_rows = status_rows["customs_residual_category"]

    print("\n=== COMMODITIES GROUNDING v2 SUMMARY ===")
    print(f"Total Layer-1 concepts: {len(concepts):,} ({tot_rows:,} rows)")
    for st, cnt in status_cnt.most_common():
        print(f"  {st:30s}: {cnt:4d} concepts | {status_rows[st]:7,d} rows ({status_rows[st]/tot_rows*100:5.1f}%)")
    print(f"  TOTAL GROUNDED TO WIKIDATA    : {g_cnt:4d} concepts | {g_rows:7,d} rows ({g_rows/tot_rows*100:5.1f}%)")
    print(f"  GROUNDED + RESIDUALS          : {g_cnt+status_cnt['customs_residual_category']:4d} concepts | {g_rows+res_rows:7,d} rows ({(g_rows+res_rows)/tot_rows*100:5.1f}%)")
    print(f"  Multi-anchor LOD coverage     : AGROVOC={agrovoc_linked} | STW Economics={stw_linked} | Getty AAT={aat_linked} | Taxa/P1582={taxon_linked}")

    print("\n=== TOP 45 NEWLY MATCHED COMMODITIES (AUDIT) ===")
    newly_matched_audit.sort(reverse=True)
    for cnt, raw, qid, lbl, desc in newly_matched_audit[:45]:
        print(f"  {cnt:6d}  {raw:44s} -> {qid:16s} {lbl:22s} [{desc}]")

    print("\n=== TOP 25 REMAINING UNMATCHED COMMODITIES ===")
    for r in review_q[:25]:
        print(f"  {r[0]:6d}  {r[2]:8s} {r[3]:44s} head={r[4]}")


if __name__ == "__main__":
    main()
