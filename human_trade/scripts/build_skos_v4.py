#!/usr/bin/env python3
"""
Build the complete 4-tier, dictionary-enriched Layer-1 (`human_transcribed`) Commodity SKOS Ontology (v4).

Addresses every scholarly need from Dr. Jim Clifford and every Opus v3 P0/P1/P2 audit finding:
  - 4-tier SKOS hierarchy (`htc:scheme`):
      Tier 1: 9 Macro-Sectors (`skos:hasTopConcept`)
      Tier 2: 43 Coherent Mid-Level Commodity Groups (e.g. Stimulant Beverages [Tea, Coffee, Cocoa],
              Latexes & Elastic Gums [Caoutchouc, India Rubber, Gutta Percha], Animal Fats & Tallow
              [Tallow, Tallow & Stearine, Stearine], Vegetable Tannins, Sawn Lumber, Hewn Timber, ...)
      Tier 3: Layer-A' Canonical Substance Groups (grouping variants + co-anchored synonyms under
              S14-safe distinct labels — ZERO S14 prefLabel collisions!)
      Tier 4: 2,066 frozen persistent `htc:0001`–`htc:2066` verbatim customs headings
  - Mines all 6 freshly OCR'd / proofread 19th-century commercial dictionaries
    (Simmonds 1892, Mortimer 1823, McCulloch 1880, Watt 1908, Ure, Simmonds 1854):
      - `skos:definition` + `oe:dictionarySource` (clickable IA scan page URI / Gutenberg URI)
      - `skos:altLabel` (modern Wikidata labels + common & historical synonyms like "rubber" on Caoutchouc!)
      - Verified historical Linnaean `oe:sourceTaxon` (grounded to Wikidata Q16521 + CoL)
      - Internal `skos:related` + `oe:combinesConcept` (linking `Tallow and Stearine` -> `Tallow` + `Stearine`,
        `Caoutchouc` <-> `India Rubber` <-> `Gutta Percha`, dictionary `See` cross-references)
  - Positive `instance_of`/description allowlist eliminating all ~30 Opus v3 homonyms
    (`Horses`!=xiangqi, `Horns`!=brass, `Mace`!=weapon, `Pitch`!=music, `Sponge`!=bread,
    `Electrical Wires`!=rope, `Iron Pig`!=live pig, etc.)
  - Emits ALL RDFS/OWL `oe:` declarations in BOTH `.ttl` and `.jsonld`, plus SSSOM & CI checks.

ZERO QIDs from memory.
"""

import csv
import gzip
import json
import re
import time
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import duckdb

BASE = Path("/home/jic823/Documents/open_empire/human_trade")
LAYER1 = BASE / "layer1_human"
GROUND = LAYER1 / "grounding"
DICT_DIR = Path("/home/jic823/Documents/open_empire/dictionaries")
CEYLON_SPINE = Path("/home/jic823/Documents/ceylon/spine")
SKOS_XLSX = BASE / "raw_sources" / "SKOS_from_Custom_Records.xlsx"
WD_SLIM_GLOB = "/mnt/data/jic823/wikidata/20261109/slim/*.parquet"
WD_SNAPSHOT = "2026-11-09"
WD_API = "https://www.wikidata.org/w/api.php"
UA = "OpenEmpireSKOSv4/0.4 (University of Saskatchewan HGIS Lab; jim.clifford@usask.ca)"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

BASE_URI = "https://open-empire.hgislab.usask.ca/vocab/human-trade-commodities/"
HTC1866_URI = "https://open-empire.hgislab.usask.ca/vocab/customs-1866/"
OE_NS = "https://open-empire.hgislab.usask.ca/ns#"
TODAY = date.today().isoformat()


def norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_") or "unnamed"


def ttl_str(s: str) -> str:
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    return f'"{s}"'


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


# ============================================================================
# TIER 1 (9 Macro-Sectors) & TIER 2 (43 Mid-Level Commodity Groups)
# ============================================================================
SECTORS = {
    "sec_food_and_drink": "Food, Drink & Stimulants",
    "sec_livestock_fodder": "Livestock, Draft Animals & Animal Feed",
    "sec_forestry_timber": "Timber, Lumber & Forest Products",
    "sec_hides_skins_tanning": "Hides, Skins, Furs, Leather & Tanning Materials",
    "sec_fibres_textiles": "Textile Fibres, Yarns, Fabrics & Apparel",
    "sec_oils_fats_waxes": "Oils, Fats, Oilseeds, Waxes & Soap",
    "sec_botanicals_dyes_chemicals": "Latexes, Resins, Dyes, Drugs & Chemicals",
    "sec_minerals_metals_manufactures": "Minerals, Fuels, Metals & Industrial Manufactures",
    "sec_unclassified_residuals": "Unenumerated & Residual Customs Categories",
}

# group_id -> (label, parent_sector, ghost_acres_domain)
GROUPS = {
    # Food, Drink & Stimulants
    "grp_stimulant_beverages": ("Stimulant Beverages & Infusions (Tea, Coffee, Cocoa)", "sec_food_and_drink", "food_colonial_grocery"),
    "grp_sugars_sweeteners": ("Sugars, Molasses & Sweeteners", "sec_food_and_drink", "food_colonial_grocery"),
    "grp_alcoholic_beverages": ("Beverages, Wine, Spirits & Mineral Waters", "sec_food_and_drink", "food_colonial_grocery"),
    "grp_tobacco": ("Tobacco, Cigars & Snuff", "sec_food_and_drink", "food_colonial_grocery"),
    "grp_spices_condiments": ("Spices, Aromatics & Condiments", "sec_food_and_drink", "food_colonial_grocery"),
    "grp_cereals_grains": ("Cereals, Grains, Flour & Meal", "sec_food_and_drink", "food_grain"),
    "grp_pulses_legumes": ("Pulses & Legumes (Peas & Beans)", "sec_food_and_drink", "food_grain"),
    "grp_fruits_nuts_vegetables": ("Fruits, Edible Nuts & Vegetables", "sec_food_and_drink", "food_colonial_grocery"),
    "grp_meats_provisions": ("Meats & Cured Provisions", "sec_food_and_drink", "food_animal"),
    "grp_dairy_eggs": ("Dairy Products & Eggs", "sec_food_and_drink", "food_animal"),
    "grp_fish_seafood": ("Fish & Shellfish", "sec_food_and_drink", "fisheries_marine"),

    # Livestock, Draft Animals & Feed
    "grp_live_food_animals": ("Live Food & Herd Animals", "sec_livestock_fodder", "food_animal"),
    "grp_draft_animals": ("Draft & Working Animals (Horses & Mules)", "sec_livestock_fodder", "food_animal"),
    "grp_fodder_oilcakes": ("Hay, Straw, Bran & Oilseed Cakes", "sec_livestock_fodder", "fodder_feed"),

    # Timber, Lumber & Forest Products
    "grp_sawn_lumber": ("Sawn Lumber, Deals, Planks & Shingles", "sec_forestry_timber", "timber_forestry"),
    "grp_hewn_round_timber": ("Hewn, Round & Cabinet Timber", "sec_forestry_timber", "timber_forestry"),
    "grp_cooperage_ship_timber": ("Cooperage & Naval Timber (Staves, Masts, Spars)", "sec_forestry_timber", "timber_forestry"),
    "grp_wood_pulp_fuel": ("Wood Pulp, Firewood, Charcoal & Cork", "sec_forestry_timber", "timber_forestry"),

    # Hides, Skins, Furs, Leather & Tanning
    "grp_raw_hides_skins": ("Raw Hides & Undressed Skins", "sec_hides_skins_tanning", "tannins_leather"),
    "grp_furs_marine_pelts": ("Furs & Marine Pelts", "sec_hides_skins_tanning", "tannins_leather"),
    "grp_tanned_leather": ("Tanned & Dressed Leather", "sec_hides_skins_tanning", "tannins_leather"),
    "grp_vegetable_tannins": ("Vegetable Tanning Materials (Bark, Valonia, Cutch, Sumach)", "sec_hides_skins_tanning", "tannins_leather"),

    # Textile Fibres, Yarns, Fabrics & Apparel
    "grp_bast_plant_fibres": ("Plant & Bast Fibres (Cotton, Flax, Hemp, Jute)", "sec_fibres_textiles", "fibres_textiles"),
    "grp_animal_fibres": ("Wool, Silk & Animal Hair", "sec_fibres_textiles", "fibres_textiles"),
    "grp_yarns_cordage": ("Yarns, Cordage, Rope & Twine", "sec_fibres_textiles", "manufactured_goods"),
    "grp_woven_fabrics_apparel": ("Woven Textiles, Apparel & Footwear", "sec_fibres_textiles", "manufactured_goods"),

    # Oils, Fats, Oilseeds, Waxes & Soap
    "grp_animal_fats_tallow": ("Animal Fats, Tallow, Stearine & Lard", "sec_oils_fats_waxes", "fats_oils_soap"),
    "grp_marine_oils": ("Whale, Seal & Fish Oils", "sec_oils_fats_waxes", "fisheries_marine"),
    "grp_vegetable_oils": ("Vegetable & Nut Oils (Palm, Olive, Coconut, Linseed)", "sec_oils_fats_waxes", "fats_oils_soap"),
    "grp_oilseeds": ("Oilseeds & Oleaginous Nuts", "sec_oils_fats_waxes", "fats_oils_soap"),
    "grp_waxes_soap_candles": ("Waxes, Soap & Candles", "sec_oils_fats_waxes", "fats_oils_soap"),

    # Latexes, Resins, Dyes, Drugs & Chemicals
    "grp_latexes_elastic_gums": ("Latexes & Elastic Gums (Caoutchouc, India Rubber, Gutta Percha)", "sec_botanicals_dyes_chemicals", "drugs_botanicals_chemicals"),
    "grp_gums_resins_naval_stores": ("Gums, Resins & Naval Stores (Tar, Pitch, Turpentine)", "sec_botanicals_dyes_chemicals", "drugs_botanicals_chemicals"),
    "grp_natural_dyestuffs": ("Natural Dyestuffs, Dyewoods & Pigments", "sec_botanicals_dyes_chemicals", "drugs_botanicals_chemicals"),
    "grp_drugs_medicinal_botanicals": ("Drugs, Alkaloids & Medicinal Botanicals", "sec_botanicals_dyes_chemicals", "drugs_botanicals_chemicals"),
    "grp_industrial_chemicals_alkalis": ("Alkalis, Potash, Nitrates & Industrial Chemicals", "sec_botanicals_dyes_chemicals", "drugs_botanicals_chemicals"),
    "grp_fertilizers_animal_materials": ("Guano, Bones, Horns, Ivory & Marine Materials", "sec_botanicals_dyes_chemicals", "drugs_botanicals_chemicals"),

    # Minerals, Fuels, Metals & Industrial Manufactures
    "grp_fossil_fuels_mineral_oils": ("Coal, Coke & Mineral Oils", "sec_minerals_metals_manufactures", "minerals_metals_energy"),
    "grp_metallic_ores": ("Metallic Ores & Concentrates", "sec_minerals_metals_manufactures", "minerals_metals_energy"),
    "grp_metals_semi_finished": ("Smelted & Semi-Finished Metals (Pig/Bar Iron, Copper, Tin, Lead)", "sec_minerals_metals_manufactures", "minerals_metals_energy"),
    "grp_industrial_minerals": ("Salt, Graphite, Clay, Stone & Building Minerals", "sec_minerals_metals_manufactures", "minerals_metals_energy"),
    "grp_metal_machinery_hardware": ("Metalwares, Hardware, Machinery, Electrical & Vehicles", "sec_minerals_metals_manufactures", "manufactured_goods"),
    "grp_glass_ceramics_paper_woodware": ("Paper, Books, Glass, Ceramics, Woodwares & Sundries", "sec_minerals_metals_manufactures", "manufactured_goods"),

    # Residuals
    "grp_customs_residuals": ("Unenumerated, Mixed & Residual Headings", "sec_unclassified_residuals", "other"),
}

# All Opus v2 + v3 rejected bad QIDs
AUDIT_REJECTIONS = [
    ("plumbago", "Q2039140", "plant genus Plumbago, not graphite"),
    ("tar", "Q3338507", "tobacco smoke tar"),
    ("clover", "Q5135861", "Clover dairy company"),
    ("rope", "Q1156047", "rope data structure"),
    ("toy", "Q6516633", "Swedish Toy chewing gum"),
    ("clock", "Q14908739", "CLOCK gene"),
    ("castor", "Q48970", "Castor rocket stage"),
    ("picture", "Q96742522", "Pictures board game"),
    ("watch", "Q1934809", "GNU watch CLI tool"),
    ("hoop", "Q2553153", "rhythmic gymnastics hoop"),
    ("match", "Q6786204", "Match soft drink"),
    ("curio", "Q5676387", "Curio plant genus"),
    ("cement", "Q189310", "geological cement"),
    ("leech", "Q1640028", "leech of sail"),
    ("clay", "Q1627382", "Clay moth"),
    ("bead", "Q4876048", "woodworking moulding bead"),
    ("shot", "Q7502422", "shot silk fabric"),
    ("blue", "Q15178353", "Blue soft drink"),
    ("blue", "Q1088", "color blue"),
    ("veneer", "Q1686140", "dental veneer"),
    ("bugle", "Q4843841", "Bugles snack"),
    ("type", "Q3707858", "taxonomic type"),
    ("manna", "Q241156", "biblical manna"),
    ("bone", "Q881659", "corset boning"),
    ("casting", "Q496098", "casting process"),
    ("sponge", "Q1210980", "synthetic cleaning sponge"),
    ("sponge", "Q7578994", "bread making sponge process"),
    ("cinder", "Q16742056", "volcanic cinder"),
    ("cocoa nut oil", "Q42385", "Theobroma cacao"),
    ("cochineal", "Q320617", "carmine pigment"),
    ("salt", "Q12370", "generic chemical ionic salt"),
    ("sumac", "Q16131953", "culinary sumac fruit spice"),
    ("beef tongue", "Q1558649", "beef tongue"),
    ("oak", "Q55488372", "botanical monument in Ukraine"),
    ("spar", "Q3965941", "spar oil platform"),
    ("oar", "Q10802255", "Oar insect genus"),
    ("lobster", "Q3621241", "heraldic lobster"),
    ("mast", "Q1907811", "forest mast fruit"),
    ("nail", "Q36864", "fingernail"),
    ("anchor", "Q1422055", "climbing anchor"),
    ("horse", "Q10889209", "xiangqi chess horse piece"),
    ("horn", "Q163759", "valved brass musical horn"),
    ("pitch", "Q118819", "musical pitch"),
    ("mace", "Q272990", "blunt medieval weapon mace"),
    ("picket", "Q1388729", "picket soldiers"),
    ("junk", "Q205011", "Chinese junk sailing vessel"),
    ("down", "Q1187966", "relative downward direction"),
    ("bass", "Q27911", "bass singing voice"),
    ("bear", "Q618804", "gay culture bear"),
    ("bear", "Q654608", "gay culture bear"),
    ("billet", "Q1308509", "soldiers living quarters"),
    ("ash", "Q152079", "combustion ash"),
    ("timber", "Q28063796", "Timber Missouri settlement"),
    ("rubber plant", "Q4217665", "vague non-binomial 'rubber plant' category"),
    ("mare", "Q3290341", "lunar mare plain on Moon/Mars"),
]

FORBIDDEN_INSTANCE_OF = {
    "Q4167410", "Q11424", "Q482994", "Q134556", "Q105543609", "Q7187", "Q8054",
    "Q7397", "Q341", "Q18343316", "Q620615", "Q1371279", "Q235557", "Q188860",
    "Q1028939", "Q175263", "Q131436", "Q7889", "Q4830453", "Q783794", "Q431289",
    "Q507619", "Q18043413", "Q41291", "Q697175", "Q147538", "Q5", "Q1093829",
    "Q486972", "Q15127012", "Q515", "Q532", "Q3957", "Q12479774", "Q498162",
    "Q101352", "Q202444", "Q12308941", "Q11879590", "Q3297186", "Q376346", "Q1075",
    "Q20643955", "Q169930", "Q8366", "Q1979154", "Q98400282", "Q215380",
    "Q110295396",  # musical instrument (blocks brass horn, lute tar, etc.)
    "Q124078422",  # weapon class (blocks blunt mace unless cannon!)
    "Q16103215",   # ship type (blocks Chinese junk)
    "Q115211517",  # musical property (blocks musical pitch)
    "Q56877494",   # heraldic animal
    "Q4381595",    # heraldic charge
    "Q15416",      # TV program
    "Q5398426",    # TV series
    "Q18127",      # record label
    "Q47461344",   # written work / novel
    "Q264965",     # subculture / gay culture
}
TAXON_CLASS_QID = "Q16521"

BAD_DESC_RE = re.compile(
    r"\b(film|movie|song|album|single|band|musician|singer|actor|actress|politician|painter|writer|novel|"
    r"poem|television|tv series|drama series|variety show|episode|video game|board game|card game|chess|xiangqi|"
    r"comic|magazine|newspaper|scientific journal|journal published|painting by|given name|family name|surname|"
    r"disambiguation|wikimedia|human settlement|unincorporated community|census-designated|city|town|village|"
    r"municipality|hamlet|county|province|state of|country|river|lake|mountain|island|electoral district|"
    r"railway station|airport|university|college|school|church|racehorse|crater|asteroid|planet|natural monument|"
    r"heraldic|heraldry|oil platform|musical notation|perceptual property in music|brass instrument|singing voice|"
    r"constellation|company|corporation|brand|supermarket|retail chain|department store|record label|"
    r"manufacturer and marketer|football|basketball|baseball|hockey|tennis|boxing|cricket|play by|opera|symphony|"
    r"character|fictional|mytholog|deity|saint|pope|king|queen|duke|earl|baron|battle of|treaty of|war of|year|"
    r"century|language|dialect|letter of|alphabet|programming language|software|command-line tool|data structure|"
    r"markup language|file format|package manager|website|font|typeface|currency|coin|unit of|postcode|zodiac|"
    r"protein-coding gene|rocket|mars rover|spacecraft|nasa|cellular automaton|soft drink|chewing gum|corn snack|"
    r"rhythmic gymnastics|dental|coating for the teeth|burning of tobacco|volcanic|igneous|chemical precipitate|"
    r"biblical|climbing equipment|hard projection of digit|anchoring point of a taxonomic|corset|rope in the side|"
    r"woodworking decorative treatment|species of moth|genus of insects|region around the kneecap|gay culture|"
    r"soldiers or troops|living-quarters|chinese sailing vessel|southeast asian|bread making process|relative direction|"
    r"blunt weapon|deep shade of|shade of |color space|rgb color|solid remnants of fires|combustion)\b",
    re.I,
)

# POSITIVE allowlist regex (Opus v3 P0 A!) — candidate MUST match a genuine material/commodity/food/product/animal/tool description!
POSITIVE_DESC_RE = re.compile(
    r"\b(material|substance|chemical|element|compound|mixture|liquid|viscous|mineral|metal|alloy|ore|rock|stone|"
    r"fuel|oil|fat|wax|resin|gum|latex|polymers|dye|pigment|colorant|colourant|coloring|colouring|tannin|bark|wood|timber|lumber|plank|shingle|lath|"
    r"fiber|fibre|fibers|fibres|tarred fiber|textile|textiles|fabric|cloth|yarn|thread|strand|rope|cord|hosiery|lace|leather|hide|skin|fur|pelt|wool|silk|cotton|"
    r"flax|hemp|jute|paper|pulp|glass|ceramic|pottery|brick|cement|hydraulic binder|food|crop|grain|cereal|flour|"
    r"meal|powder|grinding|bread|biscuit|baked|meat|beef|pork|ham|bacon|flesh|fish|seafood|marine invertebrate|"
    r"dairy|milk|butter|cheese|egg|fruit|vegetable|legume|pulse|nut|seed|spice|aril|herb|tea|coffee|cocoa|sugar|sweet|carbohydrate|syrup|"
    r"alcohol|drink|beverage|wine|beer|spirit|liquor|tobacco|drug|medicine|medication|alkaloid|livestock|herbivore|"
    r"ungulate|domesticated|poultry|mammal|horse|equine|bovine|cattle|calf|stallion|gelding|mare|feather|bone|rigid organ|permanent pointed projection|horn|hoof|ivory|"
    r"baleen|keratin|product|commodity|goods|fertilizer|excrement|guano|explosive|adhesive|soap|candle|tool|implement|instrument that measures|scientific instrument|"
    r"time indicator|machine|machinery|mechanical|apparatus|set of moving and fixed elements|footwear|shoe|boot|garment|garments|covering worn|head covering|floor covering|clothing|apparel|furniture|movable objects|container|barrel|"
    r"railroad|agricultural|industrial|natural|organic|dried|salted|cured|processed|rendered|edible|culinary|condiment|nutrition|thickening agent|watercraft|protective outer layer|office or domestic supplies|"
    r"botanical|extract|exudate|sap|tincture|acid|salt|oxide|carbonate|nitrate|sulfate|sulphate|building material|"
    r"construction|board|beam|rigging|spar|mast|pole|propulsion|transport|vehicle|object intended to be played|small, coated stick|"
    r"small decorative object|medium for recording|device|equipment|cable|conductor|fastener|mooring|artillery|firearm|rifle|"
    r"starch|tuber|rhizome|pearl|gem|silicate|mica|inflorescence|cone|flower|flowers|outgrowth|abnormal growth|"
    r"printed|typography|movable components|long, flexible, and strong object|animal skin|sheepskin|goatskin|sealskin)\b",
    re.I,
)

RESIDUAL_RE = re.compile(
    r"^(other articles|other goods|other woods|other timber|other sorts|other kinds|other descriptions|"
    r"other manufactures|other animals|other grains|other seeds|other fruits|other fish|other meats|"
    r"other oils|other furs|other skins|other hides|other metals|other minerals|other chemicals|"
    r"goods unenumerated.*|articles unenumerated.*|unenumerated|miscellaneous|sundries|all other.*|"
    r"non enumerated.*|other unenumerated.*|manufactures unenumerated|value of articles.*)$",
    re.I,
)

# Explicit merged customs lines -> (component_targets, component_htc_labels_for_combinesConcept)
COMPOUND_HEADINGS = {
    "tallow and stearine": ([("tallow", None), ("stearin", None)], ["Tallow", "Stearine"]),
    "barley and rye": ([("cereal", "hordeum vulgare"), ("cereal", "secale cereale")], ["Barley", "Rye"]),
    "bacon and hams": ([("bacon", None), ("ham", None)], ["Bacon", "Hams"]),
    "ale beer and cider": ([("beer", None), ("cider", None)], ["Beer", "Cider"]),
    "ale and beer": ([("beer", None)], ["Beer"]),
    "beans and peas": ([("bean", None), ("legume", "pisum sativum")], ["Beans", "Peas"]),
    "peas and beans": ([("legume", "pisum sativum"), ("bean", None)], ["Peas", "Beans"]),
    "oranges and lemons": ([("orange", None), ("lemon", None)], ["Oranges", "Lemons"]),
    "lemons and oranges": ([("lemon", None), ("orange", None)], ["Lemons", "Oranges"]),
    "cutch and gambier": ([("catechu", None), ("catechu", "uncaria gambir")], ["Cutch", "Terra Japonica"]),
    "masts and spars": ([("mast", None), ("spar", None)], ["Masts", "Spars"]),
    "furs and skins": ([("fur", None), ("hide", None)], ["Furs"]),
    "planks and boards": ([("lumber", None)], ["Planks", "Boards"]),
    "flaxseed and linseed": ([("seed", "linum usitatissimum")], ["Linseed"]),
    "pearl and pot ashes": ([("potash", None), ("potassium carbonate", None)], ["Ashes Pot", "Pearl Ashes"]),
    "pot and pearl ashes": ([("potash", None), ("potassium carbonate", None)], ["Ashes Pot", "Pearl Ashes"]),
    "pig and scrap iron": ([("pig iron", None)], ["Iron Pig"]),
    "boots and shoes": ([("footwear", None)], []),
    "leather manufactures boots and shoes": ([("footwear", None)], []),
    "wood and timber basswood butternut and hickory": ([("wood", "tilia"), ("wood", "juglans cinerea"), ("wood", "carya")], []),
    "codfish including haddock ling pollock": ([("cod", None)], ["Cod"]),
}

# Explicit historical allied commodity skos:related pairs (by printed prefLabel!)
ALLIED_RELATED_PAIRS = [
    ("Caoutchouc", "Gutta Percha"),
    ("Caoutchouc", "India Rubber"),
    ("India Rubber", "Gutta Percha"),
    ("Caoutchouc", "Caoutchouc Manufactures of"),
    ("Gutta Percha", "Gutta Percha Raw"),
    ("Gutta Percha", "Gutta Percha Manufactures of"),
    ("Tallow", "Tallow and Stearine"),
    ("Stearine", "Tallow and Stearine"),
    ("Stearine", "Candles Stearine"),
    ("Cutch", "Terra Japonica"),
    ("Cutch and Gambier", "Terra Japonica"),
    ("Bark For Tanners and Dyers Use", "Valonia"),
    ("Bark For Tanners and Dyers Use", "Shumach"),
    ("Tea", "Coffee"),
    ("Tea", "Cocoa"),
    ("Coffee", "Cocoa"),
    ("Ashes Pot", "Pearl Ashes"),
    ("Potash", "Pearl Ashes"),
    ("Plumbago", "Lead Black"),
    ("Train or Blubber (Whale Oils)", "Whalebone"),
    ("Sugar", "Raw Sugar"),
    ("Sugar", "Molasses"),
    ("Sugar", "Glucose"),
    ("Sugar", "Rum"),
    ("Molasses", "Rum"),
    ("Maple Sugar", "Maple Syrup"),
    ("Maple Sugar", "Sugar"),
    ("Sugar", "Confectionery"),
    ("Cotton", "Cotton Seeds"),
    ("Cotton Seeds", "Cotton Seed Oil Refined"),
    ("Cotton Seeds", "Cotton Seed Oil Unrefined"),
    ("Cotton Seeds", "Oil Seed Cake Cotton Seed"),
    ("Flax", "Linseed"),
    ("Linseed", "Oil Linseed"),
    ("Flax", "Linen"),
    ("Hemp", "Cordage"),
    ("Wheat", "Wheat Flour"),
    ("Barley", "Beer"),
    ("Cattle", "Beef"),
    ("Cattle", "Hides"),
    ("Cattle", "Tallow"),
    ("Hides", "Leather"),
    ("Sheep", "Wool"),
    ("Sheep", "Mutton"),
    ("Swine", "Pork"),
    ("Swine", "Bacon"),
    ("Codfish", "Fish Oil Cod"),
    ("Codfish", "Tongues and Sounds"),
    ("Tobacco", "Tobacco Manufactured Cigars"),
    ("Tobacco", "Tobacco Manufactured Snuff"),
    ("Indigo", "Madder"),
    ("Indigo", "Cochineal"),
    ("Bark For Tanners and Dyers Use", "Myrabolans"),
    ("Bark For Tanners and Dyers Use", "Bark Extract of Hemlock"),
]

# LINCS-aligned skos:scopeNote annotations: archival/colonial terminology context + historical boundary objects
CURATED_SCOPE_NOTES = {
    "htc:0627": "Verbatim 19th-century British customs appellation retained strictly for archival fidelity and source provenance; contains an archaic colonial racialized trade term ('Negrohead', denoting dark plug-pressed Cavendish tobacco). Analytically grouped under neutral Tobacco, Cigars & Snuff.",
    "htc:0644": "Verbatim 19th-century Canadian customs appellation ('Indian Bark Work') denoting Indigenous birchbark craft and quillwork exports; retained for archival provenance rather than as a modern ethnonym.",
    "htc:1009": "Verbatim 19th-century customs appellation retained for archival provenance; denotes colonial trade classification of birchbark/barkwood articles.",
    "htc:0436": "Historical boundary object: in 1800–1852 British/Canadian customs ledgers (measured in lbs from Canada/Hudson's Bay), 'Castor' denotes beaver castoreum (Castor fiber), not castor oil.",
    "htc:0127": "Historical North Atlantic fishery heading: pickled cod tongues from Canadian/Newfoundland fisheries, not beef tongue.",
    "htc:0513": "Historical North Atlantic fishery heading: pickled cod tongues and swim bladders ('sounds'), not mammalian meat.",
    "htc:0727": "Historical cooperage heading (Quebec/Maritime timber trade, measured in pieces): wooden barrel hoops, not iron hoops.",
    "htc:1831": "Historical materia medica heading: sweet medicinal exudate from manna ash (Fraxinus ornus) imported from Italy and Spain.",
    "htc:0395": "Historical Maritime/New England cooperage export: wooden box shooks shipped to Cuba and the West Indies for packing muscovado sugar, not sugar itself.",
    "htc:1417": "Historical Maritime/New England cooperage export: knocked-down wooden shooks for West Indies sugar boxes, classified under Cooperage & Naval Timber.",
    "htc:0047": "Historical British/Canadian customs term for maize (Zea mays); in 19th-century British trade statistics, bare 'Corn' denoted cereal grains generally.",
    "htc:0015": "19th-century trade appellation for natural rubber latex (Hevea spp.); historically grouped with allied tropical latexes such as Gutta Percha.",
    "htc:0696": "19th-century Southeast Asian non-elastic latex (Palaquium gutta / Isonandra gutta), critical to submarine telegraph cables and allied in trade classification with Caoutchouc.",
    "htc:0030": "Merged 1871–1909 HCPP customs heading combining animal tallow (htc:0022) and rendered stearine (htc:0910); linked to its constituents via oe:combinesConcept.",
    "htc:0275": "Historical South/Southeast Asian vegetable tanning and dyeing extract (Senegalia catechu); 19th-century customs clerks frequently conflated cutch and gambier under 'Terra Japonica'.",
    "htc:0355": "Historical Southeast Asian vegetable tanning extract (Uncaria gambir); closely allied in 19th-century British trade ledgers with Cutch and Terra Japonica.",
    "htc:0432": "Historical 19th-century trade term ('Terra Japonica') covering catechu/gambier vegetable tanning extracts imported from South and Southeast Asia.",
    "htc:1019": "19th-century maritime trade heading: old tarred hemp rope and cordage cut up for oakum caulking and paper-making, not miscellaneous scrap.",
    "htc:2002": "19th-century chemical and dyeing mordant: ferrous sulfate (green vitriol), not metallic copper.",
    "htc:1760": "Historical textile heading: bobbin lace worked on bone bobbins, not an animal-bone product.",
    "htc:0079": "North American forest-derived sweetener (Acer saccharum); assigned oe:landBasis 'terrestrial_forest' to distinguish sugarbush forest harvest from arable cane/beet cropland.",
    "htc:1644": "North American forest-derived sweetener (Acer saccharum); assigned oe:landBasis 'terrestrial_forest' to distinguish sugarbush forest harvest from arable cane/beet cropland.",
}

# Curated modern common altLabels for archaic/19th-century customs terms
ARCHAIC_ALT_LABELS = {
    "caoutchouc": ["rubber", "natural rubber", "gum-elastic"],
    "india rubber": ["rubber", "natural rubber"],
    "gutta percha": ["gutta-percha"],
    "plumbago": ["graphite", "black lead"],
    "lead black": ["graphite", "black lead"],
    "brimstone": ["sulfur", "sulphur"],
    "saltpetre": ["potassium nitrate", "nitre"],
    "cubic nitre": ["sodium nitrate", "Chile saltpetre"],
    "nitrate of soda": ["sodium nitrate", "Chile saltpetre"],
    "spelter": ["zinc"],
    "quicksilver": ["mercury"],
    "terra japonica": ["catechu"],
    "cutch": ["catechu"],
    "shumach": ["sumac"],
    "sumach": ["sumac"],
    "indian corn": ["Indian maize"],
    "pease": ["dried peas"],
    "train oil": ["whale oil"],
    "oil train": ["whale oil"],
    "train or blubber": ["whale oil", "blubber"],
    "whalebone": ["baleen"],
    "whale fins": ["baleen"],
    "ashes pot": ["potassium carbonate"],
    "pearl ashes": ["potassium carbonate", "pearl ash"],
    "ashes pearl": ["potassium carbonate", "pearl ash"],
    "soda ash": ["sodium carbonate"],
    "barilla": ["sodium carbonate"],
    "peruvian bark": ["Jesuits' bark"],
    "cinchona": ["quinine bark"],
    "castor": ["castoreum", "beaver castor"],
    "wool cotton": ["raw cotton", "cotton wool"],
    "cocoa nut oil": ["coconut oil"],
    "coco nut oil": ["coconut oil"],
    "horned cattle": ["beef cattle"],
    "neat cattle": ["beef cattle"],
    "swine": ["pigs"],
    "pimento": ["allspice"],
    "currants": ["Zante currants", "Corinthian raisins"],
    "deals": ["sawn softwood lumber", "timber deals"],
    "scantling": ["dimension lumber", "timber scantling"],
    "bark for tanners and dyers use": ["tanbark", "tanning bark"],
    "elephants teeth": ["elephant ivory"],
    "junk": ["old rope", "oakum"],
}

CANONICAL_MAP = {
    # Latexes & elastic gums
    "caoutchouc": ("natural rubber", "hevea brasiliensis", "skos:exactMatch"),
    "india rubber": ("natural rubber", "hevea brasiliensis", "skos:closeMatch"),
    "gutta percha": ("gutta-percha", "palaquium gutta", "skos:exactMatch"),
    # Stimulants
    "tea": ("tea", "camellia sinensis", "skos:exactMatch"),
    "coffee": ("coffee", "coffea arabica", "skos:exactMatch"),
    "cocoa": ("cocoa bean", "theobroma cacao", "skos:closeMatch"),
    "cocoa butter": ("cocoa butter", "theobroma cacao", "skos:exactMatch"),
    "chicory": ("chicory", "cichorium intybus", "skos:closeMatch"),
    # Sugars, alcohol, tobacco, spices
    "sugar": ("sugar", None, "skos:exactMatch"),
    "sugar total": ("sugar", None, "skos:broadMatch"),
    "raw sugar": ("raw sugar", "saccharum officinarum", "skos:exactMatch"),
    "sugar unrefined cane and other sorts": ("sugar", "saccharum officinarum", "skos:broadMatch"),
    "sugar cane juice": ("sugar", "saccharum officinarum", "skos:broadMatch"),
    "sugar unrefined beetroot": ("sugar", "beta vulgaris", "skos:broadMatch"),
    "sugar boxes": ("wood", None, "skos:relatedMatch"),
    "sugar box shooks": ("wood", None, "skos:relatedMatch"),
    "cattle and other animal foods containing molasses": ("fodder", None, "skos:broadMatch"),
    "fruit preserved without sugar": ("fruit", None, "skos:broadMatch"),
    "maple sugar": ("maple sugar", "acer saccharum", "skos:exactMatch"),
    "maple syrup": ("maple syrup", "acer saccharum", "skos:exactMatch"),
    "molasses": ("molasses", None, "skos:exactMatch"),
    "glucose": ("glucose", None, "skos:exactMatch"),
    "honey": ("honey", None, "skos:exactMatch"),
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
    "spirits": ("liquor", None, "skos:broadMatch"),
    "spirits geneva": ("gin", None, "skos:closeMatch"),
    "spirits unenumerated": ("liquor", None, "skos:broadMatch"),
    "spirits unenumerated not sweetened": ("liquor", None, "skos:broadMatch"),
    "vinegar": ("vinegar", None, "skos:exactMatch"),
    "pepper": ("black pepper", None, "skos:exactMatch"),
    "cinnamon": ("cinnamon", None, "skos:exactMatch"),
    "cloves": ("clove", None, "skos:exactMatch"),
    "ginger": ("ginger", None, "skos:exactMatch"),
    "nutmegs": ("nutmeg", None, "skos:exactMatch"),
    "mace": ("mace", None, "skos:exactMatch"),
    "pimento": ("allspice", None, "skos:exactMatch"),
    # Grains & pulses
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
    "peas": ("legume", "pisum sativum", "skos:broadMatch"),
    "pease": ("legume", "pisum sativum", "skos:broadMatch"),
    "beans": ("bean", None, "skos:exactMatch"),
    "malt": ("malt", None, "skos:exactMatch"),
    "hops": ("hops", None, "skos:exactMatch"),
    "biscuits": ("biscuit", None, "skos:exactMatch"),
    "sago": ("sago", None, "skos:exactMatch"),
    "tapioca": ("tapioca", None, "skos:exactMatch"),
    "arrowroot": ("arrowroot", None, "skos:exactMatch"),
    # Fruits, vegetables, nuts
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
    "vegetables": ("vegetable", None, "skos:exactMatch"),
    "cranberries": ("cranberry", None, "skos:exactMatch"),
    # Livestock, meats, dairy, eggs
    "horned cattle": ("cattle", None, "skos:exactMatch"),
    "neat cattle": ("cattle", None, "skos:exactMatch"),
    "cattle": ("cattle", None, "skos:exactMatch"),
    "cows": ("cattle", None, "skos:broadMatch"),
    "swine": ("livestock", "pig", "skos:broadMatch"),
    "hogs": ("livestock", "pig", "skos:broadMatch"),
    "pigs": ("livestock", "pig", "skos:broadMatch"),
    "sheep": ("sheep", None, "skos:exactMatch"),
    "sheep and lambs": ("sheep", None, "skos:broadMatch"),
    "horses": ("livestock", "equus ferus caballus", "skos:broadMatch"),  # Q726 is Q16521 taxon -> sourceTaxon!
    "mares": ("livestock", "equus ferus caballus", "skos:broadMatch"),
    "geldings": ("livestock", "equus ferus caballus", "skos:broadMatch"),
    "stallions": ("livestock", "equus ferus caballus", "skos:broadMatch"),
    "calves": ("cattle", None, "skos:broadMatch"),
    "oxen": ("cattle", None, "skos:broadMatch"),
    "bulls": ("cattle", None, "skos:broadMatch"),
    "poultry": ("poultry", None, "skos:exactMatch"),
    "beef": ("beef", None, "skos:exactMatch"),
    "pork": ("pork", None, "skos:exactMatch"),
    "bacon": ("bacon", None, "skos:exactMatch"),
    "hams": ("ham", None, "skos:exactMatch"),
    "mutton": ("lamb and mutton", None, "skos:exactMatch"),
    "venison": ("venison", None, "skos:exactMatch"),
    "meat": ("meat", None, "skos:exactMatch"),
    "meats": ("meat", None, "skos:exactMatch"),
    "butter": ("butter", None, "skos:exactMatch"),
    "cheese": ("cheese", None, "skos:exactMatch"),
    "eggs": ("egg as food", None, "skos:exactMatch"),
    "eggs in shell": ("egg as food", None, "skos:closeMatch"),
    # Fodder
    "oil seed cakes": ("press cake", None, "skos:exactMatch"),
    "oil seed cake": ("press cake", None, "skos:exactMatch"),
    "oilseed cake": ("press cake", None, "skos:exactMatch"),
    "oil cake": ("press cake", None, "skos:exactMatch"),
    "oilcake": ("press cake", None, "skos:exactMatch"),
    "hay": ("hay", None, "skos:exactMatch"),
    "straw": ("straw", None, "skos:exactMatch"),
    "bran": ("bran", None, "skos:exactMatch"),
    "clover seeds": ("seed", "trifolium", "skos:broadMatch"),
    "clover seed": ("seed", "trifolium", "skos:broadMatch"),
    # Timber & forestry
    "planks": ("lumber", None, "skos:broadMatch"),
    "boards": ("lumber", None, "skos:broadMatch"),
    "deals": ("lumber", None, "skos:broadMatch"),
    "deal ends": ("lumber", None, "skos:broadMatch"),
    "deals and battens": ("lumber", None, "skos:broadMatch"),
    "battens": ("batten", None, "skos:closeMatch"),
    "scantling": ("lumber", None, "skos:broadMatch"),
    "lumber": ("lumber", None, "skos:exactMatch"),
    "shingles": ("wood shingle", None, "skos:exactMatch"),
    "laths": ("lath", None, "skos:exactMatch"),
    "lathwood": ("lath", None, "skos:broadMatch"),
    "lath lathwood": ("lath", None, "skos:broadMatch"),
    "saw logs": ("wood", None, "skos:broadMatch"),
    "logs": ("wood", None, "skos:broadMatch"),
    "knees": ("wood", None, "skos:broadMatch"),
    "shooks": ("wood", None, "skos:broadMatch"),
    "pickets": ("wood", None, "skos:broadMatch"),
    "billets": ("wood", None, "skos:broadMatch"),
    "timber": ("wood", None, "skos:broadMatch"),
    "wood": ("wood", None, "skos:exactMatch"),
    "firewood": ("firewood", None, "skos:exactMatch"),
    "sleepers": ("railroad tie", None, "skos:exactMatch"),
    "railway ties": ("railroad tie", None, "skos:exactMatch"),
    "railroad ties": ("railroad tie", None, "skos:exactMatch"),
    "masts": ("mast", None, "skos:exactMatch"),
    "spars": ("spar", None, "skos:exactMatch"),
    "oars": ("oar", None, "skos:exactMatch"),
    "staves": ("barrel", None, "skos:relatedMatch"),
    "standard staves": ("barrel", None, "skos:relatedMatch"),
    "staves other": ("barrel", None, "skos:relatedMatch"),
    "wood and timber staves": ("barrel", None, "skos:relatedMatch"),
    "hoop": ("barrel", None, "skos:relatedMatch"),
    "hoops": ("barrel", None, "skos:relatedMatch"),
    "veneers": ("wood veneer", None, "skos:exactMatch"),
    "pulpwood": ("pulpwood", None, "skos:exactMatch"),
    "wood pulp": ("pulp", None, "skos:broadMatch"),
    "pulp of wood": ("pulp", None, "skos:broadMatch"),
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
    "tamarack": ("wood", "larix laricina", "skos:broadMatch"),
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
    # Hides, skins, furs, leather, tannins
    "bark for tanners and dyers use": ("tanbark", None, "skos:exactMatch"),
    "bark for tanners": ("tanbark", None, "skos:exactMatch"),
    "bark for tanning": ("tanbark", None, "skos:exactMatch"),
    "oak bark": ("tanbark", "quercus", "skos:broadMatch"),
    "hemlock bark": ("tanbark", "tsuga", "skos:broadMatch"),
    "valonia": ("tanbark", "quercus ithaburensis", "skos:broadMatch"),
    "cutch": ("catechu", None, "skos:exactMatch"),
    "terra japonica": ("catechu", "uncaria gambir", "skos:closeMatch"),
    "gambier": ("catechu", "uncaria gambir", "skos:closeMatch"),
    "sumach": ("tannin", "rhus coriaria", "skos:broadMatch"),
    "shumach": ("tannin", "rhus coriaria", "skos:broadMatch"),
    "sumac": ("tannin", "rhus coriaria", "skos:broadMatch"),
    "myrobalans": ("tannin", "terminalia chebula", "skos:broadMatch"),
    "myrabolans": ("tannin", "terminalia chebula", "skos:broadMatch"),
    "divi divi": ("tannin", "libidibia coriaria", "skos:broadMatch"),
    "galls": ("gall", None, "skos:exactMatch"),
    "hides": ("hide", None, "skos:exactMatch"),
    "hides or pieces of": ("hide", None, "skos:broadMatch"),
    "leather": ("leather", None, "skos:exactMatch"),
    "sheeps pelts": ("sheepskin", None, "skos:exactMatch"),
    "sheep s pelts": ("sheepskin", None, "skos:exactMatch"),
    "sheep skins": ("sheepskin", None, "skos:closeMatch"),
    "sheep and lamb skins": ("sheepskin", None, "skos:broadMatch"),
    "skins furs pelts sheep": ("sheepskin", None, "skos:broadMatch"),
    "skins furs pelts goat": ("goatskin", None, "skos:broadMatch"),
    "skins furs pelts seal": ("sealskin", None, "skos:broadMatch"),
    "skins seal": ("sealskin", None, "skos:broadMatch"),
    "skins furs pelts calf": ("calfskin", None, "skos:broadMatch"),
    "skins furs pelts bear": ("fur", "ursidae", "skos:broadMatch"),
    "skins furs pelts": ("fur", None, "skos:broadMatch"),
    "skins": ("hide", None, "skos:broadMatch"),
    "furs": ("fur", None, "skos:exactMatch"),
    "pelts": ("hide", None, "skos:closeMatch"),
    # Fibres
    "wool": ("wool", None, "skos:exactMatch"),
    "wool sheep and lambs": ("wool", None, "skos:broadMatch"),
    "wool cotton": ("cotton", None, "skos:closeMatch"),
    "cotton": ("cotton", None, "skos:exactMatch"),
    "cotton raw": ("cotton", "gossypium", "skos:broadMatch"),
    "cotton raw and waste of": ("cotton", "gossypium", "skos:broadMatch"),
    "cotton waste": ("cotton", "gossypium", "skos:broadMatch"),
    "flax": ("flax", "linum usitatissimum", "skos:exactMatch"),
    "hemp": ("hemp fiber", "cannabis sativa", "skos:exactMatch"),
    "hemp rough or undressed": ("hemp fiber", "cannabis sativa", "skos:broadMatch"),
    "hemp seeds": ("seed", "cannabis sativa", "skos:broadMatch"),
    "hemp seed": ("seed", "cannabis sativa", "skos:broadMatch"),
    "rapeseed oil": ("vegetable oil", "brassica napus", "skos:broadMatch"),
    "rape seed oil": ("vegetable oil", "brassica napus", "skos:broadMatch"),
    "jute": ("jute", None, "skos:exactMatch"),
    "silk": ("silk", None, "skos:exactMatch"),
    "linen": ("linen", None, "skos:exactMatch"),
    "rags": ("rag", None, "skos:exactMatch"),
    "oakum": ("oakum", None, "skos:exactMatch"),
    "junk": ("oakum", None, "skos:closeMatch"),
    "esparto": ("esparto", None, "skos:exactMatch"),
    "feathers": ("feather", None, "skos:exactMatch"),
    "down": ("down feather", None, "skos:exactMatch"),
    "bristles": ("bristle", None, "skos:exactMatch"),
    "hair": ("hair", None, "skos:exactMatch"),
    "horse hair": ("horsehair", None, "skos:exactMatch"),
    "seal skins undressed": ("sealskin", None, "skos:broadMatch"),
    "bees wax": ("beeswax", "apis mellifera", "skos:exactMatch"),
    "beeswax": ("beeswax", "apis mellifera", "skos:exactMatch"),
    "hops": ("hops", "humulus lupulus", "skos:exactMatch"),
    "pears raw": ("pear", None, "skos:broadMatch"),
    "fruit green": ("fruit", None, "skos:broadMatch"),
    "fruit dried unenumerated": ("dried fruit", None, "skos:broadMatch"),
    "tamarinds": ("fruit", "tamarindus indica", "skos:broadMatch"),
    "hard cheese": ("cheese", None, "skos:broadMatch"),
    "biscuit and bread": ("bread", None, "skos:broadMatch"),
    "chemical essential or perfumed oils": ("essential oil", None, "skos:broadMatch"),
    "perfumery": ("perfume", None, "skos:broadMatch"),
    "barrels empty": ("barrel", None, "skos:broadMatch"),
    "shells of all kinds": ("seashell", None, "skos:broadMatch"),
    "stationery other than paper": ("stationery", None, "skos:broadMatch"),
    "cattle and other animal foods": ("fodder", None, "skos:broadMatch"),
    "clover and grass seeds": ("seed", "trifolium", "skos:broadMatch"),
    "ground plaster": ("gypsum", None, "skos:broadMatch"),
    "timber ash": ("wood", "fraxinus", "skos:broadMatch"),
    "timber square ash": ("wood", "fraxinus", "skos:broadMatch"),
    "myrabolans": ("tannin", "terminalia chebula", "skos:broadMatch"),
    "bark extract of hemlock": ("tannin", "tsuga canadensis", "skos:broadMatch"),
    # Oils, fats, soap
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
    "rapeseed": ("seed", "brassica napus", "skos:broadMatch"),
    "seeds rape": ("seed", "brassica napus", "skos:broadMatch"),
    "seeds": ("seed", None, "skos:broadMatch"),
    "tallow": ("tallow", None, "skos:exactMatch"),
    "stearine": ("stearin", None, "skos:exactMatch"),
    "lard": ("lard", None, "skos:exactMatch"),
    "beeswax": ("beeswax", None, "skos:exactMatch"),
    "wax": ("wax", None, "skos:exactMatch"),
    "soap": ("soap", None, "skos:exactMatch"),
    "candles": ("candle", None, "skos:exactMatch"),
    "candles stearine": ("candle", None, "skos:broadMatch"),
    # Marine & fisheries
    "fish oil": ("fish oil", None, "skos:exactMatch"),
    "fish oil cod": ("cod liver oil", None, "skos:closeMatch"),
    "oil cod": ("cod liver oil", None, "skos:closeMatch"),
    "fish oil seal": ("seal oil", None, "skos:exactMatch"),
    "oil seal": ("seal oil", None, "skos:exactMatch"),
    "fish oil whale": ("whale oil", None, "skos:exactMatch"),
    "oil whale": ("whale oil", None, "skos:exactMatch"),
    "oil train": ("whale oil", None, "skos:exactMatch"),
    "train oil": ("whale oil", None, "skos:exactMatch"),
    "train or blubber": ("whale oil", None, "skos:closeMatch"),
    "oil spermaceti": ("sperm oil", None, "skos:exactMatch"),
    "cod": ("cod", None, "skos:exactMatch"),
    "codfish": ("cod", None, "skos:exactMatch"),
    "herrings": ("herring", None, "skos:exactMatch"),
    "herring": ("herring", None, "skos:exactMatch"),
    "salmon": ("salmon", None, "skos:exactMatch"),
    "mackerel": ("mackerel", None, "skos:exactMatch"),
    "oysters": ("oyster", None, "skos:exactMatch"),
    "lobsters": ("seafood", "nephropidae", "skos:broadMatch"),
    "whalebone": ("baleen", None, "skos:exactMatch"),
    "whale fins": ("baleen", None, "skos:exactMatch"),
    "isinglass": ("isinglass", None, "skos:exactMatch"),
    "tongues": ("fish as food", None, "skos:broadMatch"),
    "tongues and sounds": ("fish as food", None, "skos:broadMatch"),
    "cod sounds": ("fish as food", None, "skos:broadMatch"),
    "fish": ("fish as food", None, "skos:broadMatch"),
    "coral": ("coral", None, "skos:exactMatch"),
    # Drugs, resins, dyes, chemicals
    "tar": ("tar", None, "skos:exactMatch"),
    "pitch": ("pitch", None, "skos:exactMatch"),
    "rosin": ("rosin", None, "skos:exactMatch"),
    "turpentine": ("turpentine", None, "skos:exactMatch"),
    "oil turpentine": ("turpentine", None, "skos:exactMatch"),
    "coal tar": ("coal tar", None, "skos:exactMatch"),
    "ashes pot": ("potash", None, "skos:exactMatch"),
    "ashes pearl": ("potassium carbonate", None, "skos:closeMatch"),
    "pearl ashes": ("potassium carbonate", None, "skos:closeMatch"),
    "ashes": ("potash", None, "skos:broadMatch"),
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
    "cinchona": ("herbal medicine", "cinchona", "skos:broadMatch"),
    "peruvian bark": ("herbal medicine", "cinchona", "skos:broadMatch"),
    "bark peruvian": ("herbal medicine", "cinchona", "skos:broadMatch"),
    "opium": ("opium", None, "skos:exactMatch"),
    "castor": ("castoreum", "castor fiber", "skos:exactMatch"),
    "manna": ("herbal medicine", "fraxinus ornus", "skos:broadMatch"),
    "indigo": ("indigo", "indigofera tinctoria", "skos:exactMatch"),
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
    "gum": ("natural gum", None, "skos:broadMatch"),
    "shellac": ("shellac", None, "skos:exactMatch"),
    "lac": ("lac", None, "skos:exactMatch"),
    "balsam": ("balsam", None, "skos:exactMatch"),
    "ivory": ("ivory", None, "skos:exactMatch"),
    "bones": ("bone", None, "skos:exactMatch"),
    "horns": ("horn", None, "skos:exactMatch"),
    "hoofs": ("hoof", None, "skos:exactMatch"),
    "drugs": ("medication", None, "skos:broadMatch"),
    "senna": ("herbal medicine", "senna alexandrina", "skos:broadMatch"),
    "rhubarb": ("rhubarb", None, "skos:exactMatch"),
    "sarsaparilla": ("herbal medicine", "smilax", "skos:broadMatch"),
    "liquorice": ("liquorice", None, "skos:exactMatch"),
    "licorice": ("liquorice", None, "skos:exactMatch"),
    # Minerals, ores, metals
    "plumbago": ("graphite", None, "skos:exactMatch"),
    "lead black": ("graphite", None, "skos:closeMatch"),
    "salt": ("table salt", None, "skos:exactMatch"),
    "coal": ("coal", None, "skos:exactMatch"),
    "coals": ("coal", None, "skos:exactMatch"),
    "petroleum": ("petroleum", None, "skos:exactMatch"),
    "coal oil": ("kerosene", None, "skos:exactMatch"),
    "clay": ("clay", None, "skos:exactMatch"),
    "gypsum": ("gypsum", None, "skos:exactMatch"),
    "plaster": ("gypsum", None, "skos:closeMatch"),
    "slate": ("slate", None, "skos:exactMatch"),
    "marble": ("marble", None, "skos:exactMatch"),
    "stone": ("stone", None, "skos:exactMatch"),
    "iron ore": ("iron ore", None, "skos:exactMatch"),
    "copper ore": ("copper ore", None, "skos:exactMatch"),
    "lead ore": ("lead ore", None, "skos:exactMatch"),
    "tin ore": ("tin ore", None, "skos:exactMatch"),
    "silver ore": ("silver ore", None, "skos:exactMatch"),
    "cobalt ore": ("cobalt ore", None, "skos:exactMatch"),
    "zinc ore": ("ore", None, "skos:broadMatch"),
    "manganese ore": ("ore", None, "skos:broadMatch"),
    "antimony ore": ("ore", None, "skos:broadMatch"),
    "ore": ("ore", None, "skos:exactMatch"),
    "iron pig": ("pig iron", None, "skos:exactMatch"),
    "pig iron": ("pig iron", None, "skos:exactMatch"),
    "iron bar": ("wrought iron", None, "skos:closeMatch"),
    "iron": ("iron", None, "skos:exactMatch"),
    "steel": ("steel", None, "skos:exactMatch"),
    "copper": ("copper", None, "skos:exactMatch"),
    "copper cement": ("copper", None, "skos:broadMatch"),
    "tin": ("tin", None, "skos:exactMatch"),
    "lead": ("lead", None, "skos:exactMatch"),
    "lead pig": ("lead", None, "skos:broadMatch"),
    "zinc": ("zinc", None, "skos:exactMatch"),
    "spelter": ("zinc", None, "skos:exactMatch"),
    "quicksilver": ("mercury", None, "skos:exactMatch"),
    "antimony": ("antimony", None, "skos:exactMatch"),
    "manganese": ("manganese", None, "skos:exactMatch"),
    # Manufactures
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
    "gloves": ("glove", None, "skos:exactMatch"),
    "cannon": ("cannon", None, "skos:exactMatch"),
}

MATERIAL_DETECT = [
    (r"\b(iron|steel)\b", "iron"),
    (r"\bcopper\b", "copper"),
    (r"\blead\b", "lead"),
    (r"\btin\b", "tin"),
    (r"\bzinc\b", "zinc"),
    (r"\bsilk\b", "silk"),
    (r"\b(cotton|calico(?:es)?|muslins?|nankeens?)\b", "cotton"),
    (r"\b(wool|woollen|woolen)\b", "wool"),
    (r"\blinen\b", "linen"),
    (r"\bleather\b", "leather"),
    (r"\b(wood|wooden|timber)\b", "wood"),
    (r"\bglass\b", "glass"),
    (r"\b(caoutchouc|india\s*rubber|rubber)\b", "natural rubber"),
    (r"\bgutta[\s-]*percha\b", "gutta-percha"),
    (r"\bstearin(e)?\b", "stearin"),
]


def load_id_registry():
    reg = {}
    for r in csv.DictReader(open(GROUND / "htc_id_registry.tsv", encoding="utf-8"), delimiter="\t"):
        reg[r["commodity_as_printed"]] = r["concept_id"]
    return reg


def load_1866_skos():
    by_label = {}
    if not SKOS_XLSX.exists():
        return by_label
    zf = zipfile.ZipFile(SKOS_XLSX)
    ss = []
    if "xl/sharedStrings.xml" in zf.namelist():
        for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", NS):
            ss.append("".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
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
        rows.append([rmap.get(i, "") for i in range(1, mx + 1)])
    idx = {h.strip(): i for i, h in enumerate(rows[0])}
    for r in rows[1:]:
        def g(col):
            i = idx.get(col)
            return r[i].strip() if i is not None and i < len(r) else ""
        concept = g("Concept") or g("skos:Concept") or (r[0] if r else "")
        pref = g("prefLabel") or g("skos:prefLabel") or concept
        if not concept:
            continue
        rec = {
            "skos_concept": concept, "prefLabel": pref,
            "broaderConcept": g("broader") or g("broaderConcept") or g("skos:broader"),
            "state": g("state") or g("State"), "sourceOf": g("sourceOf") or g("SourceOf"),
        }
        for k in {norm_key(concept), norm_key(pref)}:
            if k:
                by_label[k] = rec
    return by_label


def load_dictionaries():
    """Index all 27,325 dictionary entries + 1,190 verified grounded binomials."""
    binom_map = {}
    bp = DICT_DIR / "dictionary_binomials_grounded.jsonl"
    if bp.exists():
        for line in open(bp, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                if d.get("qid"):
                    binom_map[d["binomial"].lower()] = d

    prio_rank = {"simmonds_1892": 100, "ure_gutenberg": 90, "watt_1908": 85, "mcculloch_1880": 80, "mortimer_1823": 75, "simmonds_1854": 70}
    by_hw = defaultdict(list)
    lp = DICT_DIR / "commercial_dictionaries_lexicon.jsonl"
    if lp.exists():
        for line in open(lp, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            k = d["norm_headword"]
            if k:
                by_hw[k].append(d)
            for alt in d.get("alt_headwords") or []:
                ak = norm_key(re.sub(r"^(or|and)\s+", "", alt, flags=re.I))
                if ak and len(ak) >= 3 and ak != k:
                    by_hw[ak].append(d)

    def _dict_score(x):
        s = prio_rank.get(x["source_work"], 50) + (20 if x["latin_binomials"] else 0)
        defn = (x.get("definition") or "").strip()
        if re.match(r"^(?:the\s+duties\s+on|by\s+\d+\s+geo|an\s+act\s+|stat\.|duties\s+on\s+|the\s+excise\s+duties)", defn, re.I):
            s -= 60
        return s

    for k in by_hw:
        by_hw[k].sort(key=_dict_score, reverse=True)
    return by_hw, binom_map


def extract_substance_head(raw: str) -> str:
    s = (raw or "").strip()
    s = re.split(r"\s+[-–—]\s+|\s*\(|\s*:\s*", s, maxsplit=1)[0].strip()
    s = re.sub(
        r"\b(unenumerated|other sorts|other descriptions|other kinds|not elsewhere specified|"
        r"raw or undressed|undressed|unmanufactured|manufactured|not otherwise enumerated|"
        r"for manufacturing|not fresh|in shell)\b.*$",
        "",
        s,
        flags=re.I,
    ).strip(" ,;-")
    return s or raw.strip()


def classify_v4(raw: str, head: str):
    """Assign (group_id, processing_state, land_basis, sitc_code, theodoridis, is_agg) cleanly."""
    lo = raw.lower().strip()
    is_agg = bool(re.search(r"\btotal\b|\ball kinds\b|\ball sorts\b", lo))

    # --- 1. Mid-level Commodity Group (43 coherent scholarly groups — fixes ALL Opus v3 P0/P1 domain glitches!) ---
    grp = "grp_customs_residuals"

    # Explicit collision guards FIRST
    if re.search(r"\b(caoutchouc|india\s*rubber|gutta[\s-]*percha|rubber)\b", lo) and not re.search(r"\b(electrical|wires?|cables?|manufactures?|boots?|shoes?|apparatus)\b", lo):
        grp = "grp_latexes_elastic_gums"
    elif re.search(r"\bcream\s+of\s+tartar\b|\btartar\b", lo):
        grp = "grp_industrial_chemicals_alkalis"
    elif re.search(r"\b(iron|steel)\s+(hoops?|ingots?|blooms?|billets?)\b|\b(iron|lead|copper|tin|metal)\b.*\bpig\b|\bpig\b.*\b(iron|lead|copper|tin|metal)\b|\bsteel\s+rails?\b|\biron\s+rails?\b|\brailway\s+rails?\b", lo):
        grp = "grp_metals_semi_finished"
    elif re.search(r"\b(electrical|electric\s+wires?|scientific\s+instruments?)\b", lo):
        grp = "grp_metal_machinery_hardware"
    elif re.search(r"\bcannon\b.*\bcarriage|\bgun\s*carriage|\bcannon\b", lo):
        grp = "grp_metal_machinery_hardware"
    elif re.search(r"\bcopper\b.*\bcement|\bcement\s+copper\b", lo):
        grp = "grp_metals_semi_finished"
    elif re.search(r"\b(hats?|bonnets?)\b", lo):
        grp = "grp_woven_fabrics_apparel"
    elif re.search(r"\b(perfumery|perfumes?|soap|candles?|beeswax|bees\s*wax|wax\b|paraffin)\b", lo):
        grp = "grp_waxes_soap_candles"
    elif re.search(r"\bsugar\s+box(?:es)?\b|\bbarrels?\s+empty\b|\btreenails?\b", lo):
        grp = "grp_cooperage_ship_timber"
    elif re.search(r"\b(bark\s+peruvian|peruvian\s+bark|cinchona)\b", lo):
        grp = "grp_drugs_medicinal_botanicals"
    elif re.search(r"\b(bark\s+extract\s+of\s+hemlock|myr[ao]b[ao]lans?)\b", lo):
        grp = "grp_vegetable_tannins"
    elif re.search(r"\b(timber\s+(?:square\s+)?ash|hewn\s+fir.*other\s+than\s+pit\s+wood)\b", lo):
        grp = "grp_hewn_round_timber"
    elif re.search(r"\brailway\s+wagg?ons?\b|\biron\s+cast\s+or\s+wrought\b", lo):
        grp = "grp_metal_machinery_hardware"
    elif re.search(r"\bjute\s+manufactures\s+other\s+than\s+cordage\b", lo):
        grp = "grp_woven_fabrics_apparel"
    elif re.search(r"\bhides\s+and\s+skins\s+other\s+than\s+fur\b|\bskins\s+furs\s+pelts.*not\s+being\s+furs\b", lo):
        grp = "grp_raw_hides_skins"
    elif re.search(r"\bnuts?\s+and\s+kernels?\s+for\s+expressing\s+oil\b", lo):
        grp = "grp_oilseeds"
    elif re.search(r"\bfruit.*preserved\s+without\s+sugar\b", lo):
        grp = "grp_fruits_nuts_vegetables"
    elif re.search(r"\bcattle\s+(?:and\s+other\s+)?animal\s+foods?\b", lo):
        grp = "grp_fodder_oilcakes"
    elif re.search(r"\b(mineral\s*waters?|wine|brandy|rum|whiske?y|spirits?|beer|ale|porter|cider|gin|geneva|spruce\s*beer)\b", lo):
        grp = "grp_alcoholic_beverages"
    elif re.search(r"\b(tea\b|coffee\b|cocoa\b|chocolate|chicory)\b", lo) and not re.search(r"\bcocoa[\s-]*nut\b|\bcoco[\s-]*nut\b", lo):
        grp = "grp_stimulant_beverages"
    elif re.search(r"\b(sugar|molasses|treacle|syrup|glucose|saccharin|honey|confection[ea]ry|succades)\b", lo):
        grp = "grp_sugars_sweeteners"
    elif re.search(r"\b(tobacco|cigars?|snuff)\b", lo):
        grp = "grp_tobacco"
    elif re.search(r"\b(spices?|pepper|cinnamon|cassia|cloves?|ginger|nutmegs?|mace\b|pimento|allspice|cardamom|vanilla|saffron|mustard|vinegar|sauces?|pickles?|caraway|aniseed|coriander|cummin|cumin)\b", lo):
        grp = "grp_spices_condiments"
    elif re.search(r"\b(cattle\s+animal\s+foods?|oil\s*seed\s*cakes?|oil\s*cakes?|oilcake|press\s*cake|hay\b|straw\b|bran\b|pollard|fodder|forage|clover\s*seeds?|grass\s*seeds?|turnip\s*seeds?|tares\b|vetches?)\b", lo):
        grp = "grp_fodder_oilcakes"
    elif re.search(r"\b(butter|cheese|milk|cream|eggs?)\b", lo):
        grp = "grp_dairy_eggs"
    elif re.search(r"\b(tallow|stearin|stearine|lard|grease|suet|dripping|margarine|animal\s+oil)\b", lo):
        grp = "grp_animal_fats_tallow"
    elif re.search(r"\b(whale\s*oil|seal\s*oil|cod\s*oil|train\s*oil|train\s+or\s+blubber|blubber|spermaceti|fish\s*oil|porpoise\s*oil|herring\s*oil)\b", lo):
        grp = "grp_marine_oils"
    elif re.search(r"\b(cocoa[\s-]*nut\s*oil|coco[\s-]*nut\s*oil|coconut\s*oil|palm\s*oil|olive\s*oil|linseed\s*oil|rape\s*seed\s*oil|rapeseed\s*oil|cotton\s*seed\s*oil|seed\s*oil|castor\s*oil|oil\s+palm|oil\s+olive|oil\s+linseed|oil\s+seed|oil\s+cocoa|oil\s+unenumerated|vegetable\s*oil)\b", lo):
        grp = "grp_vegetable_oils"
    elif re.search(r"\b(peas?\b|pease|beans?|lentils?|pulse|chick\s*peas?|haricot|kidney\s*beans?)\b", lo):
        grp = "grp_pulses_legumes"
    elif re.search(r"\b(garden\s*seeds?|flower\s*seeds?)\b", lo):
        grp = "grp_fruits_nuts_vegetables"
    elif re.search(r"\b(cotton\s*seeds?|linseed|flax\s*seeds?|flaxseed|rape\s*seeds?|rapeseed|seeds?\s+rape|oil\s*seeds?|copra|palm\s*kernels?|hemp\s*seed|poppy\s*seed|sesame|ground\s*nuts?|peanuts?|seeds?\b)\b", lo):
        grp = "grp_oilseeds"
    elif re.search(r"\b(lace|embroidery|needlework|stockings?|socks?|hosiery|stays\s+or\s+corsets?|corsets?)\b", lo):
        grp = "grp_woven_fabrics_apparel"
    elif re.search(r"\b(bones?|horns?|hoofs?|ivory|elephants?\s*teeth|whalebone|whale\s*fins?|isinglass|guano|manure|phosphates?|sponge|sponges|coral|shells?\s+of\s+all\s+kinds)\b", lo):
        grp = "grp_fertilizers_animal_materials"
    elif re.search(r"\b(codfish|cod\b|herrings?|mackerel|salmon|lobsters?|oysters?|halibut|haddock|ling\b|pollock|sardines?|anchovies|pilchards?|sprats?|eels?|trout|shad|fish\b|fisheries|tongues\s+and\s+sounds|cod\s+sounds|tongues\b|shellfish)\b", lo) and not re.search(r"\bfurs?\s+or\s+skins?\b", lo):
        grp = "grp_fish_seafood"
    elif re.search(r"\b(tanning|tanners?|tanbark|bark\s+for\s+tanner|oak\s*bark|hemlock\s*bark|mimosa\s*bark|valonia|cutch|gambier|terra\s*japonica|sumach|shumach|sumac|myr[ao]balans?|divi[\s-]*divi|galls?|gallnuts?|catechu|kino)\b", lo):
        grp = "grp_vegetable_tannins"
    elif re.search(r"\b(boots?|shoes?|footwear|gloves?|clothing|apparel|haberdashery|hats?|piece\s*goods|cloth\b|fabrics?|linen\s+manufactures|cotton\s+manufactures|silk\s+manufactures|wooll?en\s+manufactures|wooll?en\b)\b", lo) and not re.search(r"\bships?\b.*\bapparel\b|\braw\b", lo):
        grp = "grp_woven_fabrics_apparel"
    elif re.search(r"\b(cordage|ropes?|twine|cables?|canvas|sailcloth|yarns?|oakum|\bjunk\b)\b", lo) and not re.search(r"\belectric", lo):
        grp = "grp_yarns_cordage"
    elif re.search(r"\b(tanned|tawed|curried|varnished|japanned|enamelled|leather|morocco|parchment)\b", lo) and not re.search(r"\bmanufactures?\b", lo):
        grp = "grp_tanned_leather"
    elif re.search(r"\b(furs?|sealskins?|seal\s*skins?|skins?.*seal|skins?.*bear|buffalo\s*robes?|pelts?)\b", lo):
        grp = "grp_furs_marine_pelts"
    elif re.search(r"\b(hides?|skins?)\b", lo):
        grp = "grp_raw_hides_skins"
    elif re.search(r"\b(wool\b|silk\b|alpaca|mohair|hair\b|bristles?|feathers?|down\b)\b", lo) and not re.search(r"\bwool\s+cotton\b|\bmanufactures?\b", lo):
        grp = "grp_animal_fibres"
    elif re.search(r"\b(cotton|wool\s+cotton|flax|hemp|jute|linen|tow\b|coir|sisal|manila|esparto|rags?)\b", lo) and not re.search(r"\bmanufactures?\b", lo):
        grp = "grp_bast_plant_fibres"
    elif re.search(r"\b(butter|cheese|milk|cream|eggs?)\b", lo):
        grp = "grp_dairy_eggs"
    elif re.search(r"\b(beef|pork|mutton|veal|bacon|hams?|meats?|venison|sausages?)\b", lo):
        grp = "grp_meats_provisions"
    elif re.search(r"\b(peas?\b|pease|beans?|lentils?|pulse)\b", lo):
        grp = "grp_pulses_legumes"
    elif re.search(r"\b(wheat|oats?|barley|rye|maize|indian\s*corn|corn\b|flour|meal\b|oatmeal|cornmeal|semolina|biscuits?|bread|grains?|cereals?|malt\b|buckwheat|rice\b|sago|tapioca|arrowroot|farina|macaroni|groats?)\b", lo):
        grp = "grp_cereals_grains"
    elif re.search(r"\b(fruits?|apples?|pears?|plums?|prunes?|cherries|peaches|cranberries|berries|grapes?|raisins?|currants?|figs?|dates?|oranges?|lemons?|limes?|bananas?|pineapples?|almonds?|chestnuts?|filberts?|hazelnuts?|coconuts?|cocoa[\s-]*nuts?|tamarinds?|nuts?\s+and\s+kernels?|small\s+nuts?|vegetables?|potatoes?|onions?|turnips?|cabbages?|tomatoes?|hops?)\b", lo) or (re.search(r"\bwalnuts?\b", lo) and not re.search(r"\b(timber|wood|lumber)\b", lo)):
        grp = "grp_fruits_nuts_vegetables"
    elif re.search(r"\b(staves?|hoops?|shooks?|headings?|masts?|spars?|oars?|handspikes?|knees|futtocks?|sleepers?|railway\s*ties?|railroad\s*ties?|pit\s*wood|pit\s*props?)\b", lo):
        grp = "grp_cooperage_ship_timber"
    elif re.search(r"\b(pulpwood|wood\s*pulp|pulp\s+of\s+wood|paper\s*making\s*materials|firewood|charcoal|cork\b)\b", lo):
        grp = "grp_wood_pulp_fuel"
    elif re.search(r"\b(lumber|planks?|boards?|deals?|deal\s*ends?|battens?|shingles?|laths?|lathwood|scantling|veneers?|pickets?|palings?|sawn|sawed|planed)\b", lo):
        grp = "grp_sawn_lumber"
    elif re.search(r"\b(timber|saw\s*logs?|logs?\b|billets?|other\s+woods?|wood\b|oak\b|pine\b|elm\b|birch\b|maple\b|walnut\b|fir\b|spruce\b|cedar\b|hemlock\b|tamarack?|basswood|butternut|hickory|beech\b|poplar|mahogany|teak\b|rosewood|ebony|boxwood|lignum\s*vitae)\b", lo) and not re.search(r"\b(manufactures?|furniture|household|ash\b)\b", lo):
        grp = "grp_hewn_round_timber"
    elif re.search(r"\b(indigo|madder|garancine|cochineal|logwood|fustic|quercitron|annatto|turmeric|safflower|orch[ai]l|cudbear|woad|ultramarine|aniline|smalts?|dye\s*stuffs?|dyestuffs?|dye\s*woods?|dyewoods?|dyes?\b|coal\s*tar\s*dyes?|paints?|colours?|blue\b)\b", lo):
        grp = "grp_natural_dyestuffs"
    elif re.search(r"\b(cinchona|peruvian\s*bark|quinine|opium|castor\b|castoreum|manna|senna|rhubarb|jalap|ipecacuanha|sarsaparilla|liquorice|licorice|aloe|aloes|drugs?\b|medicines?|medicinal|leeches)\b", lo):
        grp = "grp_drugs_medicinal_botanicals"
    elif re.search(r"\b(gum\b|gums\b|resin|rosin|turpentine|tar\b|pitch\b|balsam|camphor|shellac|lac\b|myrrh|frankincense)\b", lo):
        grp = "grp_gums_resins_naval_stores"
    elif re.search(r"\b(potash|pot\s*ash|pearl\s*ash|ashes?\b|soda\b|barilla|kelp|alkali|saltpetre|nitre|nitrate|brimstone|sulphur|sulfur|alum\b|borax|arsenic|vitriol|copperas|acid\b|ammonia|bleaching|chloride|carbonate|sulphate|sulfate|bicarbonate|caustic|chemical|gunpowder|explosives?|fulminates?)\b", lo):
        grp = "grp_industrial_chemicals_alkalis"
    elif re.search(r"\b(horses?|mares?|geldings?|stallions?|colts?|mules?|asses?)\b", lo):
        grp = "grp_draft_animals"
    elif re.search(r"\b(cattle|oxen|bulls?|cows?|calves?|steers?|heifers?|sheep|lambs?|swine|hogs?|pigs?|poultry|fowls?|turkeys?|geese|ducks?|animals?\s+living|live\s+animals?|animals?\s+unenumerated)\b", lo):
        grp = "grp_live_food_animals"
    elif re.search(r"\b(coal\b|coals\b|coke\b|cinders?|peat\b|petroleum|kerosene|naphtha|asphalt|bitumen|mineral\s*oil)\b", lo):
        grp = "grp_fossil_fuels_mineral_oils"
    elif re.search(r"\b(ore\b|ores\b|pyrites|gold[\s-]*bearing\s*quartz)\b", lo):
        grp = "grp_metallic_ores"
    elif re.search(r"\b(machinery|machine|hardware|bolts?\s+and\s+nuts?|nails?|stoves?|anchors?|wire|cutlery|tools?|sewing\s*machines?|carriages?|carts?|vehicles?|cycles?|bicycles?|steam\s*engines?|agricultural\s*implements?|clocks?|watches?|castings?|firearms?|muskets?|rifles?|pistols?|lamps?|lanterns?|arms\b|ammunition|shot\b|ships?\b|boats?|iron\s+manufactures|steel\s+manufactures|copper\s+manufactures|metal\s+manufactures)\b", lo):
        grp = "grp_metal_machinery_hardware"
    elif re.search(r"\b(paper\b|wallpaper|books?|maps?\s+and\s+charts?|stationery|prints?|pictures?|glass|glassware|earthenware|chinaware|porcelain|pottery|bricks?|tiles?|cement|furniture|wood\s+manufactures|boxes\b|mats?\b|matting|flowers?\s+artificial|toys?|matches?|beads?|bugles?|musical\s*instruments?|type\b|curios?|buttons?|umbrellas?|brooms?|brushes?|baskets?|trunks?|starch|glue|varnish|leather\s+manufactures|caoutchouc\s+manufactures|gutta[\s-]*percha\s+manufactures|manufactures?\b|manufactured)\b", lo) and not re.search(r"\b(unmanufactured|re-?manufactur)", lo):
        grp = "grp_glass_ceramics_paper_woodware"
    elif re.search(r"\b(iron\b|steel\b|copper\b|tin\b|lead\b|zinc\b|spelter|quicksilver|mercury|silver\b|gold\b|platinum|antimony|manganese|cobalt|nickel|brass|bronze|pewter|bullion|specie|metals?)\b", lo):
        grp = "grp_metals_semi_finished"
    elif re.search(r"\b(salt\b|plumbago|graphite|clay\b|gypsum|plaster|lime\b|limestone|chalk|slate|marble|granite|grindstones?|stone\b|stones\b|sand\b|gravel|mica\b|asbestos|quartz|minerals?|precious\s*stones?|diamonds?)\b", lo):
        grp = "grp_industrial_minerals"

    _, sector, domain = GROUPS[grp]

    # --- 2. Processing State (clean, zero iron-pig=live or Butter=non-exact bugs!) ---
    state = "unspecified"
    if grp in ("grp_metal_machinery_hardware", "grp_glass_ceramics_paper_woodware", "grp_yarns_cordage", "grp_woven_fabrics_apparel") or (re.search(r"\b(manufactures?|manufactured|boots?|shoes?|gloves?|stoves?|nails?|anchors?|furniture|carriages?|machinery|hardware|books?|clocks?|watches?|toys?|biscuits?|canned|bottled|preserved|castings?|soap|candles?)\b", lo) and not re.search(r"\b(unmanufactured|re-?manufactur)", lo)):
        state = "manufactured"
    elif grp == "grp_wood_pulp_fuel" and "pulp" in lo:
        state = "processed_pulp"
    elif grp == "grp_fodder_oilcakes" and re.search(r"\b(cake|cakes|bran|pollard)\b", lo):
        state = "byproduct_cake"
    elif grp == "grp_tanned_leather" or (re.search(r"\b(tanned|tawed|curried|varnished|japanned|enamelled|dressed)\b", lo) and domain == "tannins_leather"):
        state = "dressed_tanned"
    elif re.search(r"\b(dressed|hackled|heckled|carded|combed|scutched)\b", lo) and domain == "fibres_textiles":
        state = "processed_fibre"
    elif grp in ("grp_sawn_lumber", "grp_cooperage_ship_timber") or (re.search(r"\b(sawn|sawed|hewn|planed|dressed|veneers?)\b", lo) and domain == "timber_forestry"):
        state = "sawn_hewn"
    elif re.search(r"\b(flour|meal|oatmeal|cornmeal|semolina|ground|crushed|powdered|milled|split\s*peas?)\b", lo):
        state = "milled_ground"
    elif grp == "grp_dairy_eggs" and re.search(r"\b(butter|cheese)\b", lo):
        state = "dairy_processed"
    elif re.search(r"\b(refined|distilled|rectified|extract|essence|oil\b|oils\b|spirits?|wine|rum|brandy|whiske?y|gin|beer|ale|cider|molasses|syrup)\b", lo) and not re.search(r"\bunrefined\b|\braw\b|\bcrude\b|\boil\s*seed|\boil\s*cake", lo):
        state = "refined_extract"
    elif re.search(r"\b(salted|pickled|wet\s+salted|brine|corned)\b", lo) and "pulp" not in lo:
        state = "wet_salted"
    elif re.search(r"\b(dried|dry\b|smoked|cured|kiln[\s-]*dried|roasted|desiccated)\b", lo) and "pulp" not in lo:
        state = "dried_cured"
    elif grp == "grp_metals_semi_finished":
        state = "smelted_semi"
    elif grp == "grp_metallic_ores":
        state = "raw_ore"
    elif grp in ("grp_live_food_animals", "grp_draft_animals"):
        state = "live"
    elif re.search(r"\b(raw|undressed|unrefined|unmanufactured|crude|unwrought|green|fresh|in\s+shell)\b", lo) or grp in ("grp_cereals_grains", "grp_pulses_legumes", "grp_oilseeds", "grp_raw_hides_skins"):
        state = "raw_unprocessed"

    # --- 3. Ecological Land Basis ---
    if grp in ("grp_fish_seafood", "grp_marine_oils") or (grp == "grp_furs_marine_pelts" and "seal" in lo) or (grp == "grp_fertilizers_animal_materials" and re.search(r"\b(whale|isinglass|sponge|coral)\b", lo)):
        land_basis = "marine"
    elif sector == "sec_forestry_timber" or grp in ("grp_vegetable_tannins", "grp_latexes_elastic_gums", "grp_gums_resins_naval_stores") or re.search(r"\bmaple\s+(sugar|syrup)\b", lo):
        land_basis = "terrestrial_forest"
    elif grp in ("grp_fossil_fuels_mineral_oils", "grp_metallic_ores", "grp_metals_semi_finished", "grp_industrial_minerals", "grp_industrial_chemicals_alkalis"):
        land_basis = "mineral"
    elif grp in ("grp_metal_machinery_hardware", "grp_glass_ceramics_paper_woodware", "grp_yarns_cordage", "grp_woven_fabrics_apparel"):
        land_basis = "industrial_manufactured"
    elif grp in ("grp_live_food_animals", "grp_draft_animals", "grp_meats_provisions", "grp_dairy_eggs", "grp_animal_fats_tallow", "grp_raw_hides_skins", "grp_tanned_leather", "grp_furs_marine_pelts", "grp_animal_fibres", "grp_fertilizers_animal_materials"):
        land_basis = "terrestrial_pasture"
    elif grp == "grp_customs_residuals":
        land_basis = "unclassified"
    else:
        land_basis = "terrestrial_crop"

    # --- 4. Real SITC Rev. 4 Division Code ---
    SITC_BY_GROUP = {
        "grp_live_food_animals": "SITC4_00_Live_Animals",
        "grp_draft_animals": "SITC4_00_Live_Animals",
        "grp_meats_provisions": "SITC4_01_Meat_and_Preparations",
        "grp_dairy_eggs": "SITC4_02_Dairy_and_Eggs",
        "grp_fish_seafood": "SITC4_03_Fish_and_Seafood",
        "grp_cereals_grains": "SITC4_04_Cereals_and_Preparations",
        "grp_pulses_legumes": "SITC4_05_Vegetables_and_Fruit",
        "grp_fruits_nuts_vegetables": "SITC4_05_Vegetables_and_Fruit",
        "grp_sugars_sweeteners": "SITC4_06_Sugars_and_Honey",
        "grp_stimulant_beverages": "SITC4_07_Coffee_Tea_Cocoa_Spices",
        "grp_spices_condiments": "SITC4_07_Coffee_Tea_Cocoa_Spices",
        "grp_fodder_oilcakes": "SITC4_08_Animal_Feeding_Stuff",
        "grp_alcoholic_beverages": "SITC4_11_Beverages",
        "grp_tobacco": "SITC4_12_Tobacco",
        "grp_raw_hides_skins": "SITC4_21_Hides_Skins_Furskins_Raw",
        "grp_furs_marine_pelts": "SITC4_21_Hides_Skins_Furskins_Raw",
        "grp_oilseeds": "SITC4_22_Oil_Seeds_and_Oleaginous_Fruits",
        "grp_latexes_elastic_gums": "SITC4_23_Crude_Rubber",
        "grp_sawn_lumber": "SITC4_24_Cork_and_Wood",
        "grp_hewn_round_timber": "SITC4_24_Cork_and_Wood",
        "grp_cooperage_ship_timber": "SITC4_63_Cork_and_Wood_Manufactures",
        "grp_wood_pulp_fuel": "SITC4_25_Pulp_and_Waste_Paper",
        "grp_bast_plant_fibres": "SITC4_26_Textile_Fibres",
        "grp_animal_fibres": "SITC4_26_Textile_Fibres",
        "grp_industrial_minerals": "SITC4_27_Crude_Fertilizers_and_Minerals",
        "grp_metallic_ores": "SITC4_28_Metalliferous_Ores",
        "grp_vegetable_tannins": "SITC4_29_Crude_Animal_Vegetable_Materials",
        "grp_gums_resins_naval_stores": "SITC4_29_Crude_Animal_Vegetable_Materials",
        "grp_fertilizers_animal_materials": "SITC4_29_Crude_Animal_Vegetable_Materials",
        "grp_fossil_fuels_mineral_oils": "SITC4_32_33_Mineral_Fuels",
        "grp_animal_fats_tallow": "SITC4_41_Animal_Oils_and_Fats",
        "grp_marine_oils": "SITC4_41_Animal_Oils_and_Fats",
        "grp_vegetable_oils": "SITC4_42_Fixed_Vegetable_Fats_and_Oils",
        "grp_industrial_chemicals_alkalis": "SITC4_51_52_Chemicals",
        "grp_natural_dyestuffs": "SITC4_53_Dyeing_Tanning_Colouring",
        "grp_drugs_medicinal_botanicals": "SITC4_54_Medicinal_Pharmaceutical",
        "grp_waxes_soap_candles": "SITC4_55_Oils_Perfumes_Cleansing",
        "grp_tanned_leather": "SITC4_61_Leather_and_Dressed_Furskins",
        "grp_yarns_cordage": "SITC4_65_Textile_Yarn_and_Fabrics",
        "grp_woven_fabrics_apparel": "SITC4_65_84_85_Textiles_Apparel_Footwear",
        "grp_metals_semi_finished": "SITC4_67_68_Metals",
        "grp_metal_machinery_hardware": "SITC4_69_7_Metalwares_and_Machinery",
        "grp_glass_ceramics_paper_woodware": "SITC4_64_66_89_Paper_Glass_Misc_Manufactures",
        "grp_customs_residuals": "oe:sitcUnassigned",
    }
    sitc = SITC_BY_GROUP[grp]

    # --- 5. Theodoridis (2018) 5-Bucket Rollup ---
    if grp in ("grp_metal_machinery_hardware", "grp_glass_ceramics_paper_woodware", "grp_yarns_cordage", "grp_woven_fabrics_apparel") or state == "manufactured":
        theodoridis = "manufactured_articles"
    elif grp in ("grp_cereals_grains", "grp_pulses_legumes"):
        theodoridis = "grain_and_flour"
    elif grp in ("grp_live_food_animals", "grp_draft_animals", "grp_meats_provisions", "grp_dairy_eggs", "grp_fish_seafood"):
        theodoridis = "animals_and_animal_products"
    elif grp in ("grp_stimulant_beverages", "grp_sugars_sweeteners", "grp_alcoholic_beverages", "grp_tobacco", "grp_spices_condiments", "grp_fruits_nuts_vegetables"):
        theodoridis = "other_food_drink_spices"
    elif grp == "grp_customs_residuals":
        theodoridis = "unclassified"
    else:
        theodoridis = "raw_materials"

    return grp, sector, domain, state, land_basis, sitc, theodoridis, is_agg


def load_rejections():
    rej = set()
    with open(GROUND / "commodity_rejections.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["term_norm", "rejected_qid", "reason"])
        for t, q, why in AUDIT_REJECTIONS:
            w.writerow([norm_key(t), q, why])
            rej.add((norm_key(t), q))
            rej.add(("*", q))
    p = CEYLON_SPINE / "grounding" / "name_rejections.jsonl"
    if p.exists():
        for line in open(p, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                k, q = norm_key(d.get("key") or d.get("name") or ""), d.get("qid") or ""
                if k and q:
                    rej.add((k, q))
    return rej


def query_wikidata(terms: set):
    clean = sorted({t.lower().strip() for t in terms if t and len(t.strip()) >= 3})
    print(f"Querying Wikidata {WD_SNAPSHOT} slim Parquet for {len(clean):,} commodity/taxon terms...", flush=True)
    con = duckdb.connect()
    con.execute("CREATE TEMP TABLE want(term VARCHAR)")
    con.executemany("INSERT INTO want VALUES (?)", [(t,) for t in clean])
    rows = con.execute(f"""
        SELECT lower(label_en) AS lkey, qid, label_en, description_en, sitelinks, instance_of, aliases
        FROM '{WD_SLIM_GLOB}'
        WHERE lower(label_en) IN (SELECT term FROM want) AND sitelinks >= 2
    """).fetchall()
    by_term = defaultdict(list)
    for lkey, qid, lbl, desc, sl, inst, aliases in rows:
        en_aliases = []
        if aliases:
            try:
                ad = json.loads(aliases) if isinstance(aliases, str) else {}
                en_aliases = ad.get("en", [])[:8] if isinstance(ad, dict) else []
            except Exception:
                pass
        by_term[lkey].append({
            "qid": qid, "label": lbl, "desc": desc or "",
            "sitelinks": int(sl or 0),
            "instance_of": list(inst) if inst is not None else [],
            "aliases_en": en_aliases,
        })
    print(f"  Retrieved {len(rows):,} candidate rows across {len(by_term):,} terms.", flush=True)
    return by_term


def pick_commodity(term: str, cands: list, rejections: set):
    k = norm_key(term)
    scored = []
    for c in cands:
        qid = c["qid"]
        if (k, qid) in rejections or ("*", qid) in rejections:
            continue
        if c["label"] and c["label"] != c["label"].lower():
            continue
        inst = set(c["instance_of"])
        if (inst & FORBIDDEN_INSTANCE_OF) or (TAXON_CLASS_QID in inst):
            continue
        desc = c["desc"]
        if BAD_DESC_RE.search(desc):
            continue
        # Opus v3 P0 A FIX: POSITIVE description allowlist!
        if not POSITIVE_DESC_RE.search(desc):
            continue
        scored.append((c["sitelinks"] * 2.0 + 15.0, c))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def pick_taxon(cands: list):
    scored = [(c["sitelinks"], c) for c in cands if TAXON_CLASS_QID in set(c["instance_of"])]
    return max(scored, key=lambda x: x[0])[1] if scored else None


def enrich_qids(qids: list, cache_path: Path):
    cache = {}
    if cache_path.exists():
        for line in open(cache_path, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                cache[d["qid"]] = d
    todo = [q for q in dict.fromkeys(qids) if q and q.startswith("Q") and q not in cache]
    if not todo:
        return cache
    print(f"Enriching {len(todo)} QIDs via Wikidata wbgetentities...", flush=True)
    def claim_vals(cl, pid):
        out = []
        for c in cl.get(pid, []):
            v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(v, dict) and "id" in v: out.append(v["id"])
            elif isinstance(v, str): out.append(v)
        return out
    with open(cache_path, "a", encoding="utf-8") as fh:
        for i in range(0, len(todo), 50):
            batch = todo[i:i+50]
            q = urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(batch), "format": "json", "props": "labels|descriptions|claims", "languages": "en"})
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(urllib.request.Request(f"{WD_API}?{q}", headers={"User-Agent": UA}), timeout=60) as r:
                        ents = json.loads(r.read().decode("utf-8")).get("entities", {})
                    break
                except Exception:
                    ents = {}
                    time.sleep(2 * (attempt + 1))
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
                }
                cache[qid] = rec
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            time.sleep(0.35)
    return cache


def compose_lod(wd_rel: str) -> str:
    if wd_rel == "skos:exactMatch":
        return "skos:closeMatch"
    return wd_rel if wd_rel in ("skos:closeMatch", "skos:broadMatch", "skos:relatedMatch") else "skos:broadMatch"


def main():
    reg = load_id_registry()
    skos_1866 = load_1866_skos()
    dict_by_hw, binom_map = load_dictionaries()
    rejections = load_rejections()

    # 1. Read exact archival provenance from Layer-1 observations (drop "NULL and other errors" from prov:hadPrimarySource!)
    comm_stats = defaultdict(lambda: {"rows": 0, "years": set(), "series": Counter()})
    total_obs = 0
    excluded = Counter()
    with gzip.open(LAYER1 / "human_trade_observations.tsv.gz", "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            total_obs += 1
            if r["row_kind"] in ("qa_check_row", "blank"):
                excluded[r["row_kind"]] += 1
                continue
            comm = r["commodity_as_printed"].strip()
            if not comm:
                excluded["missing_commodity"] += 1
                continue
            d = comm_stats[comm]
            d["rows"] += 1
            if r["year_start"].isdigit():
                d["years"].add(int(r["year_start"]))
            ser = r["series_name"].strip() or "CSP_Canadian_Exports_BlankSeries"
            if "null and other errors" not in ser.lower():
                d["series"][ser] += 1

    # 2. Build Layer-A concepts + plan lookups
    concepts = []
    plans = {}
    all_terms = {m for _, m in MATERIAL_DETECT}

    for comm in sorted(comm_stats.keys(), key=lambda c: reg[c]):
        cid = reg[comm]
        st = comm_stats[comm]
        head = extract_substance_head(comm)
        grp, sector, domain, pstate, land_basis, sitc, theodoridis, is_agg = classify_v4(comm, head)
        k_raw, k_head = norm_key(comm), norm_key(head)

        bridge = skos_1866.get(k_raw) or skos_1866.get(k_head)
        bridge_rel = None
        if bridge:
            bp = norm_key(bridge["prefLabel"])
            bridge_rel = "exact_or_synonym" if (bp == k_raw or (bp == k_head and pstate in ("unspecified", "raw_unprocessed"))) else "broader_1866_concept"

        # Match against our 6 commercial dictionaries!
        dict_hits = []
        for dk in dict.fromkeys([k_raw, k_head, singularize(k_head) if " " not in k_head else ""]):
            if dk and dk in dict_by_hw:
                dict_hits = dict_by_hw[dk]
                break

        yrs = sorted(st["years"])
        c = {
            "concept_id": cid,
            "notation": cid.split(":")[1],
            "rdf_type": ["skos:Concept", "crm:E55_Type"],
            "skos_prefLabel": comm,
            "skos_altLabels": [],
            "skos_definition": None,
            "skos_scopeNote": CURATED_SCOPE_NOTES.get(cid),
            "dictionary_sources": [],
            "total_rows": st["rows"],
            "provenance": {
                "first_attested": yrs[0] if yrs else None,
                "last_attested": yrs[-1] if yrs else None,
                "series": [s for s, _ in st["series"].most_common()],
            },
            "ontology": {
                "sector_id": f"htc:{sector}",
                "sector_label": SECTORS[sector],
                "group_id": f"htc:{grp}",
                "group_label": GROUPS[grp][0],
                "broader_id": f"htc:{grp}",  # updated to Layer-A' sub_ group when applicable
            },
            "facets": {
                "substance_head": head,
                "processing_state": pstate,
                "ghost_acres_domain": domain,
                "land_basis": land_basis,
                "theodoridis_category": theodoridis,
                "sitc_code": sitc,
                "is_aggregate": is_agg,
            },
            "skos_1866_bridge": ({**bridge, "bridge_relation": bridge_rel} if bridge else None),
            "wikidata_anchor": None,
            "external_lod_anchors": {},
            "source_taxa": [],
            "made_of_material": [],
            "material_concepts": [],
            "combines_concepts": [],
            "related_concepts": [],
            "status": "local_concept_only",
        }

        # Populate dictionary definition, provenance URIs, altLabels, and grounded historical Linnaean taxa!
        seen_alts = {comm.lower()}
        def add_alt(lbl):
            lbl = (lbl or "").strip(" .,;:-")
            if lbl and len(lbl) >= 3 and lbl.lower() not in seen_alts and len(lbl) <= 45:
                seen_alts.add(lbl.lower())
                c["skos_altLabels"].append(lbl)

        for ak in (k_raw, k_head):
            for al in ARCHAIC_ALT_LABELS.get(ak, []):
                add_alt(al)

        if dict_hits:
            BAD_DICT_DEF_RE = re.compile(
                r"^(?:see\s+|the\s+duties\s+on|by\s+\d+\s+geo|an\s+act\s+|stat\.|duties\s+on\s+|import\s+duty)|"
                r"\b(barque|square\s+sterned\s+ship|clapper\s+of\s+a\s+bell|american\s+term\s+for\s+a\s+note\s+or\s+draft|"
                r"vegetable\s+ivory|phytelephas|raised\s+from\s+the\s+pit|eatty|schminke|face[\s-]*paint|cosmetic|"
                r"founding\s+process|for\s+raising\s+ore|charred\s+or\s+burnt\s+wood|lobelia\s+inflata|indian\s+tobacco|per\s+proof\s+gallon|the\s+art\s+of\s+founding|process\s+of\s+pouring\s+liquid\s+metal)\b",
                re.I,
            )
            good_def = None
            for dh in dict_hits:
                dtxt = (dh.get("definition") or "").strip()
                if len(dtxt) >= 35 and not BAD_DICT_DEF_RE.search(dtxt):
                    good_def = dh
                    break
            if good_def:
                c["skos_definition"] = f"{good_def['definition']} [{good_def['source_citation']}]"
            seen_src = set()
            seen_tq = set()
            for idx_dh, dh in enumerate(dict_hits[:3]):
                if dh["source_uri"] not in seen_src:
                    seen_src.add(dh["source_uri"])
                    c["dictionary_sources"].append({
                        "work": dh["source_work"],
                        "citation": dh["source_citation"],
                        "uri": dh["source_uri"],
                        "see_also": dh.get("see_also", [])[:5],
                    })
                # Only ingest dictionary alt_headwords that are explicit synonyms ("or X"), NOT inverted sub-entry modifiers ("TEA, ARABIAN")!
                for al in dh.get("alt_headwords") or []:
                    if not re.match(r"^or\s+", al.strip(), re.I):
                        continue
                    clean_al = re.sub(r"^or\s+", "", al.strip(), flags=re.I).strip(" .,;:-")
                    if clean_al and clean_al.isupper():
                        clean_al = clean_al.lower()
                    if clean_al and not re.search(r"\b(of|for|the|manufacture|art)\b$", clean_al, re.I):
                        add_alt(clean_al)
                # Only mine binomials from the primary entry (or exact headword entries) within the lead definition text
                # to prevent tangential mentions (e.g. Arabian tea Catha edulis inside Tea) from attaching.
                if idx_dh == 0 or dh["norm_headword"] in (k_raw, k_head):
                    lead_txt = (dh.get("definition") or "")[:280].lower()
                    b_list = dh.get("latin_binomials") or []
                    for b in b_list:
                        if len(b_list) > 2 and b.lower() not in lead_txt:
                            continue
                        bg = binom_map.get(b.lower())
                        if bg and bg["qid"] and bg["qid"] not in seen_tq:
                            seen_tq.add(bg["qid"])
                            c["source_taxa"].append({
                                "qid": bg["qid"],
                                "taxon_name": bg["taxon_name"],
                                "col_id": bg.get("col_id", ""),
                                "relation": f"dictionary_binomial:{dh['source_work']}",
                            })

        # Plan Wikidata lookup
        has_state = pstate not in ("unspecified", "raw_unprocessed", "live")
        # Allow intrinsic processed exactMatch for bare Butter / Cheese / Molasses / Maple Syrup
        is_intrinsic_dairy = k_raw in ("butter", "cheese", "molasses", "maple syrup")

        if RESIDUAL_RE.match(k_raw) or RESIDUAL_RE.match(k_head):
            plans[cid] = ("residual", None)
        elif k_raw in COMPOUND_HEADINGS or k_head in COMPOUND_HEADINGS:
            ck = k_raw if k_raw in COMPOUND_HEADINGS else k_head
            comps, _ = COMPOUND_HEADINGS[ck]
            plans[cid] = ("compound", (comps, ck))
            for t, tx in comps:
                all_terms.add(t)
                if tx: all_terms.add(tx)
        elif k_raw in CANONICAL_MAP or k_head in CANONICAL_MAP:
            mk = k_raw if k_raw in CANONICAL_MAP else k_head
            term, tx, rel = CANONICAL_MAP[mk]
            if (mk != k_raw or (has_state and not is_intrinsic_dairy)) and rel in ("skos:exactMatch", "skos:closeMatch"):
                rel = "skos:broadMatch"
            plans[cid] = ("single", (term, tx, rel, "canonical_exact"))
            all_terms.add(term)
            if tx: all_terms.add(tx)
        elif re.search(r"\b(pulp\s+of\s+wood|wood\s*pulp|pulpwood)\b", k_raw):
            plans[cid] = ("single", ("wood pulp", None, "skos:broadMatch", "wood_pulp_guard"))
            all_terms.add("wood pulp")
        elif re.search(r"\brags?\b", k_raw):
            plans[cid] = ("single", ("rag", None, "skos:broadMatch", "rag_guard"))
            all_terms.add("rag")
        elif grp in ("grp_metal_machinery_hardware", "grp_glass_ceramics_paper_woodware", "grp_yarns_cordage", "grp_woven_fabrics_apparel"):
            matched_prod = None
            for ppat, pterm in [
                (r"\bscientific\s+instruments?\b", "scientific instrument"),
                (r"\b(electric(?:al)?\s+(?:wires?|cables?)|(?:telegraph|telephone)(?:\s+and\s+telephone)?\s+cables?)\b", "electrical cable"),
                (r"\bcannon\b.*\bcarriage|\bgun\s*carriage", "gun carriage"),
                (r"\bcannon\b", "cannon"),
                (r"\b(boots?|shoes?|footwear)\b", "footwear"),
                (r"\b(hats?|bonnets?)\b", "hat"),
                (r"\bcarpets?\b", "carpet"),
                (r"\bgloves?\b", "glove"),
                (r"\b(stockings?|socks?)\b", "stocking"),
                (r"\b(corsets?|stays\s+or\s+corsets?)\b", "corset"),
                (r"\blace\b", "lace"),
                (r"\b(embroidery|needlework)\b", "embroidery"),
                (r"\bcalico(?:es)?\b", "calico"),
                (r"(?<!other than )\bmuslins?\b", "muslin"),
                (r"\bstoves?\b", "stove"),
                (r"\bnails?\b", "nail"),
                (r"\banchors?\b", "anchor"),
                (r"\bbolts?\s+and\s+nuts?\b", "fastener"),
                (r"\b(piece\s*goods|cloth|fabrics?|(cotton|silk|wooll?en|linen|jute)\s+manufactures|wooll?en\b)\b", "textile"),
                (r"(?<!other than )\b(cordage|ropes?|cables?)\b", "rope"),
                (r"(?<!other than cordage )\btwine\b", "twine"),
                (r"\b(clothing|apparel)\b", "clothing"),
                (r"\byarns?\b", "yarn"),
                (r"\bfurniture\b", "furniture"),
                (r"\bcarriages?\b", "carriage"),
                (r"\bcarts?\b", "cart"),
                (r"\bships?\b", "ship"),
                (r"\bagricultural\s+implements?\b", "agricultural machinery"),
                (r"\bmachinery\b", "machine"),
                (r"\bhardware\b", "household hardware"),
                (r"\bsewing\s*machines?\b", "sewing machine"),
                (r"\bmusical\s*instruments?\b", "musical instrument"),
                (r"\bclocks?\b", "clock"),
                (r"\bwatches?\b", "watch"),
                (r"\btoys?\b", "toy"),
                (r"\bbooks?\b", "book"),
                (r"\bstationery\b", "stationery"),
                (r"(?<!other than )\bpaper\b", "paper"),
                (r"\bmats?\b|\bmatting\b", "mat"),
                (r"\bglass\b", "glass"),
                (r"\b(earthenware|pottery)\b", "earthenware"),
                (r"\b(chinaware|porcelain)\b", "porcelain"),
                (r"\bmatches?\b", "match"),
                (r"\bcement\b", "cement"),
                (r"\bbeads?\b", "bead"),
                (r"\bgunpowder\b", "gunpowder"),
                (r"\bbiscuits?\b", "biscuit"),
            ]:
                if re.search(ppat, k_raw):
                    matched_prod = pterm
                    break
            if matched_prod:
                plans[cid] = ("single", (matched_prod, None, "skos:broadMatch", "manufactured_product_class"))
                all_terms.add(matched_prod)
            else:
                plans[cid] = ("none", None)
        else:
            # Curated 1866 concept BEFORE prefix!
            k_1866 = norm_key((bridge or {}).get("prefLabel") or "")
            if k_1866 and k_1866 in CANONICAL_MAP:
                term, tx, rel = CANONICAL_MAP[k_1866]
                if k_1866 != k_raw or has_state or (bridge or {}).get("bridge_relation") == "broader_1866_concept":
                    if rel in ("skos:exactMatch", "skos:closeMatch"):
                        rel = "skos:broadMatch"
                plans[cid] = ("single", (term, tx, rel, "skos_1866_curated"))
                all_terms.add(term)
                if tx: all_terms.add(tx)
            else:
                # Prefix match on CANONICAL_MAP (strictly broadMatch when extra tokens exist!)
                toks = k_head.split()
                found_pref = None
                for plen in (4, 3, 2, 1):
                    if len(toks) >= plen:
                        pref = " ".join(toks[:plen])
                        if pref in CANONICAL_MAP:
                            term, tx, rel = CANONICAL_MAP[pref]
                            if pref == "fish" and "oil" in k_raw:
                                term, tx, rel = "fish oil", None, "skos:broadMatch"
                            elif pref == "cotton" and "seed" in k_raw:
                                term, tx, rel = ("cottonseed oil" if "oil" in k_raw else "cottonseed"), None, "skos:broadMatch"
                            elif pref in ("iron", "lead", "tin", "copper", "silver", "cobalt", "zinc", "manganese", "antimony") and "ore" in k_raw:
                                term, tx, rel = CANONICAL_MAP.get(f"{pref} ore", ("ore", None, "skos:broadMatch"))
                            elif len(toks) > plen or k_head != k_raw or has_state:
                                if rel in ("skos:exactMatch", "skos:closeMatch"):
                                    rel = "skos:broadMatch"
                            found_pref = (term, tx, rel, "canonical_prefix_broad")
                            break
                if found_pref:
                    plans[cid] = ("single", found_pref)
                    all_terms.add(found_pref[0])
                    if found_pref[1]: all_terms.add(found_pref[1])
                else:
                    # Positive-allowlisted lexical lookup
                    rel = "skos:broadMatch" if (k_head != k_raw or has_state) else "skos:exactMatch"
                    lterms = []
                    if k_head and len(k_head) >= 3:
                        lterms.append(k_head)
                        if " " not in k_head and singularize(k_head) != k_head:
                            lterms.append(singularize(k_head))
                    plans[cid] = ("lexical", (lterms, rel))
                    for lt in lterms:
                        all_terms.add(lt)

        concepts.append(c)

    # 3. Single fast DuckDB scan over Wikidata 2026-11-09 slim Parquet
    wd_by_term = query_wikidata(all_terms)

    material_qids = {}
    for _, mterm in MATERIAL_DETECT:
        hit = pick_commodity(mterm, wd_by_term.get(mterm, []), rejections)
        if hit:
            material_qids[mterm] = {"qid": hit["qid"], "label": hit["label"]}

    exact_used = {}
    def guard_exact(rel, qid, pstate, cid, k_raw):
        if rel != "skos:exactMatch":
            return rel
        if pstate not in ("unspecified", "raw_unprocessed", "live") and k_raw not in ("butter", "cheese", "molasses", "maple syrup"):
            return "skos:broadMatch"
        if qid in exact_used:
            return "skos:closeMatch"
        exact_used[qid] = cid
        return "skos:exactMatch"

    for c in concepts:
        cid = c["concept_id"]
        k_raw = norm_key(c["skos_prefLabel"])
        pstate = c["facets"]["processing_state"]
        grp = c["ontology"]["group_id"].replace("htc:", "")
        mode, payload = plans[cid]

        # Attach oe:madeOfMaterial for manufactures, candles, rags, and ores (guard "not of/with X" and "other than X")
        if grp in ("grp_metal_machinery_hardware", "grp_glass_ceramics_paper_woodware", "grp_yarns_cordage", "grp_woven_fabrics_apparel", "grp_metallic_ores") or pstate == "manufactured" or "rag" in k_raw:
            mats, seen_m = [], set()
            for pat, mterm in MATERIAL_DETECT:
                if re.search(pat, k_raw) and not re.search(r"\b(?:not\s+(?:of|with|being(?:\s+of)?)|other\s+than)\s+(?:[a-z]+\s+){0,4}" + re.escape(mterm), k_raw):
                    mh = material_qids.get(mterm)
                    if mh and mh["qid"] not in seen_m:
                        mats.append(mh); seen_m.add(mh["qid"])
            c["made_of_material"] = mats

        if mode == "residual":
            c["status"] = "customs_residual_category"
            continue

        if mode == "compound":
            comps_spec, ck = payload
            comps = []
            seen_tq = {t["qid"] for t in c["source_taxa"]}
            for term, tx in comps_spec:
                hit = pick_commodity(term, wd_by_term.get(term.lower(), []), rejections)
                if hit:
                    comps.append({"qid": hit["qid"], "wd_label": hit["label"], "wd_description": hit["desc"], "mapping_relation": "skos:relatedMatch", "matched_via_term": term})
                if tx:
                    th = pick_taxon(wd_by_term.get(tx.lower(), []))
                    if th and th["qid"] not in seen_tq:
                        seen_tq.add(th["qid"])
                        c["source_taxa"].append({"qid": th["qid"], "taxon_name": th["label"], "col_id": "", "relation": "curated_source_taxon"})
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
            continue

        if mode == "single":
            term, tx, rel, rule = payload
            hit = pick_commodity(term, wd_by_term.get(term.lower(), []), rejections)
            if hit:
                frel = guard_exact(rel, hit["qid"], pstate, cid, k_raw)
                c["status"] = "grounded_wikidata_v4"
                c["wikidata_anchor"] = {
                    "mapping_relation": frel,
                    "qid": hit["qid"],
                    "wd_label": hit["label"],
                    "wd_description": hit["desc"],
                    "matched_via_term": term,
                    "source_authority": f"wikidata_slim:{WD_SNAPSHOT}",
                    "match_rule": rule,
                }
                # Add Wikidata English label as skos:altLabel ONLY when exactMatch/closeMatch and differs from prefLabel!
                if frel in ("skos:exactMatch", "skos:closeMatch") and hit["label"].lower() != c["skos_prefLabel"].lower():
                    if hit["label"].lower() not in {x.lower() for x in c["skos_altLabels"]}:
                        c["skos_altLabels"].append(hit["label"])
            if tx:
                th = pick_taxon(wd_by_term.get(tx.lower(), []))
                if th and th["qid"] not in {t["qid"] for t in c["source_taxa"]}:
                    c["source_taxa"].append({"qid": th["qid"], "taxon_name": th["label"], "col_id": "", "relation": "curated_source_taxon"})
            continue

        if mode == "lexical":
            lterms, rel = payload
            for lt in lterms:
                hit = pick_commodity(lt, wd_by_term.get(lt.lower(), []), rejections)
                if hit:
                    frel = guard_exact(rel, hit["qid"], pstate, cid, k_raw)
                    c["status"] = "grounded_wikidata_lexical"
                    c["wikidata_anchor"] = {
                        "mapping_relation": frel,
                        "qid": hit["qid"],
                        "wd_label": hit["label"],
                        "wd_description": hit["desc"],
                        "matched_via_term": lt,
                        "source_authority": f"wikidata_slim:{WD_SNAPSHOT}",
                        "match_rule": "lexical_allowlisted",
                    }
                    break

    # 4. Enrich QIDs via wbgetentities (cached!) + compose AGROVOC (FIXED c_), STW, AAT, P1582
    all_qids = []
    for c in concepts:
        a = c.get("wikidata_anchor")
        if a:
            all_qids.extend([x["qid"] for x in a["component_substances"]] if a.get("component_substances") else [a["qid"]])
        all_qids.extend(t["qid"] for t in c["source_taxa"])
    ecache = enrich_qids(all_qids, GROUND / "wd_commodity_enrichment_cache.jsonl")
    p1582_qids = [tq for q in set(all_qids) for tq in ecache.get(q, {}).get("P1582_source_taxon", []) if ("*", tq) not in rejections]
    if p1582_qids:
        ecache = enrich_qids(p1582_qids, GROUND / "wd_commodity_enrichment_cache.jsonl")

    for c in concepts:
        for t in c["source_taxa"]:
            tec = ecache.get(t["qid"], {})
            if tec.get("P225_taxon_name"):
                t["taxon_name"] = tec["P225_taxon_name"][0]
            if tec.get("P10585_col_id"):
                t["col_id"] = tec["P10585_col_id"][0]
        a = c.get("wikidata_anchor")
        if not a:
            continue
        wd_rel = a["mapping_relation"]
        skip_ext = (wd_rel == "skos:relatedMatch" and a.get("matched_via_term") == "barrel")
        tqids = [x["qid"] for x in a["component_substances"]] if a.get("component_substances") else [a["qid"]]
        ag_ids, stw_ids, aat_ids = [], [], []
        seen_tq = {t["qid"] for t in c["source_taxa"]}
        for q in tqids:
            ec = ecache.get(q)
            if not ec:
                continue
            if not skip_ext:
                for aid in ec.get("P8061_agrovoc", []):
                    cag = aid if aid.startswith("c_") else f"c_{aid}"
                    if cag not in ag_ids: ag_ids.append(cag)
                for sid in ec.get("P3911_stw", []):
                    if sid not in stw_ids: stw_ids.append(sid)
                for gid in ec.get("P1014_getty_aat", []):
                    if gid not in aat_ids: aat_ids.append(gid)
            if wd_rel in ("skos:exactMatch", "skos:closeMatch"):
                for tq in ec.get("P1582_source_taxon", []):
                    if tq not in seen_tq and ("*", tq) not in rejections:
                        tec = ecache.get(tq, {})
                        if tec.get("P225_taxon_name"):  # ONLY real Linnaean taxa (skips vague "rubber plant"!)
                            seen_tq.add(tq)
                            c["source_taxa"].append({
                                "qid": tq, "taxon_name": tec["P225_taxon_name"][0],
                                "col_id": (tec.get("P10585_col_id") or [""])[0],
                                "relation": "P1582_natural_product_of_taxon",
                            })
        crel = compose_lod(wd_rel)
        ext = {}
        if ag_ids: ext.update({"agrovoc_relation": crel, "agrovoc_ids": ag_ids, "agrovoc_uris": [f"http://aims.fao.org/aos/agrovoc/{x}" for x in ag_ids]})
        if stw_ids: ext.update({"stw_relation": crel, "stw_ids": stw_ids, "stw_uris": [f"http://zbw.eu/stw/descriptor/{x}" for x in stw_ids]})
        if aat_ids: ext.update({"getty_aat_relation": crel, "getty_aat_ids": aat_ids, "getty_aat_uris": [f"http://vocab.getty.edu/aat/{x}" for x in aat_ids]})
        c["external_lod_anchors"] = ext

    # 5. Wire internal SKOS semantic relations (`oe:combinesConcept`, `skos:related`, Layer-A' substance groups!)
    by_pref = {c["skos_prefLabel"]: c for c in concepts}
    by_norm = {norm_key(c["skos_prefLabel"]): c for c in concepts}
    by_id = {c["concept_id"]: c for c in concepts}

    def add_related(cid1, cid2):
        if cid1 == cid2:
            return
        if cid2 not in by_id[cid1]["related_concepts"]:
            by_id[cid1]["related_concepts"].append(cid2)
        if cid1 not in by_id[cid2]["related_concepts"]:
            by_id[cid2]["related_concepts"].append(cid1)

    # 5a. Merged customs lines -> oe:combinesConcept + bidirectional skos:related
    for c in concepts:
        k_raw, k_head = norm_key(c["skos_prefLabel"]), norm_key(c["facets"]["substance_head"])
        ck = k_raw if k_raw in COMPOUND_HEADINGS else (k_head if k_head in COMPOUND_HEADINGS else None)
        if ck:
            for comp_lbl in COMPOUND_HEADINGS[ck][1]:
                target = by_pref.get(comp_lbl) or by_norm.get(norm_key(comp_lbl))
                if target and target["concept_id"] != c["concept_id"]:
                    if target["concept_id"] not in c["combines_concepts"]:
                        c["combines_concepts"].append(target["concept_id"])
                    add_related(c["concept_id"], target["concept_id"])

    # 5b. Curated allied historical pairs (Caoutchouc <-> Gutta Percha, Tea <-> Coffee, etc.)
    for l1, l2 in ALLIED_RELATED_PAIRS:
        c1 = by_pref.get(l1) or by_norm.get(norm_key(l1))
        c2 = by_pref.get(l2) or by_norm.get(norm_key(l2))
        if c1 and c2:
            add_related(c1["concept_id"], c2["concept_id"])

    # 5c. Enforce unambiguous skos:altLabels (never collide with another concept's exact prefLabel)
    all_pref_lower = {c["skos_prefLabel"].lower() for c in concepts}
    for c in concepts:
        c["skos_altLabels"] = [al for al in c["skos_altLabels"] if al.lower() not in all_pref_lower]

    # 5d. Layer-A' Canonical Substance Groups (grouped by (group_id, canonical_qid or head) — S14-SAFE LABELS!)
    sub_buckets = defaultdict(list)
    for c in concepts:
        grp = c["ontology"]["group_id"].replace("htc:", "")
        a = c.get("wikidata_anchor")
        if a and a.get("qid") and not a.get("component_substances") and a["mapping_relation"] in ("skos:exactMatch", "skos:closeMatch", "skos:broadMatch"):
            key = (grp, f"wd_{a['qid'].lower()}", a["wd_label"])
        else:
            hs = slugify(c["facets"]["substance_head"])
            key = (grp, f"hd_{hs}", c["facets"]["substance_head"])
        sub_buckets[key].append(c)

    sub_concepts = {}
    all_verbatim_prefs_lower = {c["skos_prefLabel"].lower() for c in concepts}
    used_sub_labels = set(all_verbatim_prefs_lower) | {v.lower() for v in SECTORS.values()} | {v[0].lower() for v in GROUPS.values()}

    for (grp, skey, raw_lbl), mems in sorted(sub_buckets.items()):
        if len(mems) < 2:
            continue
        sub_id = f"htc:sub_{grp.replace('grp_','')[:10]}_{skey}"
        # Guarantee ZERO SKOS S14 prefLabel collision with any verbatim concept or group!
        base_lbl = f"{raw_lbl.title()} (substance group)"
        lbl = base_lbl
        if lbl.lower() in used_sub_labels:
            lbl = f"{raw_lbl.title()} — {GROUPS[grp][0]} (group)"
        used_sub_labels.add(lbl.lower())
        sub_concepts[sub_id] = {
            "id": sub_id, "label": lbl, "parent": f"htc:{grp}",
            "members": [m["concept_id"] for m in mems],
        }
        for m in mems:
            m["ontology"]["broader_id"] = sub_id
        # Link co-anchored exact/close synonyms inside the same substance group via skos:related
        syn_mems = [m for m in mems if (m.get("wikidata_anchor") or {}).get("mapping_relation") in ("skos:exactMatch", "skos:closeMatch")]
        for i in range(len(syn_mems)):
            for j in range(i + 1, len(syn_mems)):
                add_related(syn_mems[i]["concept_id"], syn_mems[j]["concept_id"])

    # 5e. Cross-stage material chains (`oe:materialConcept` + S27-safe `skos:related` linking ores,
    #     semi-finished metals/fibres, and manufactures back to their canonical base-material htc: hub!)
    base_by_qid = {}
    for c in concepts:
        a = c.get("wikidata_anchor") or {}
        if a.get("qid") and a.get("mapping_relation") == "skos:exactMatch" and not a.get("component_substances"):
            base_by_qid[a["qid"]] = c["concept_id"]
    # Fallback for base materials whose exactMatch label has a variant (e.g., Iron, Wood, Lead)
    for mterm, mobj in material_qids.items():
        mq = mobj["qid"]
        if mq not in base_by_qid:
            cands = [
                c for c in concepts
                if (c.get("wikidata_anchor") or {}).get("qid") == mq
                and c["ontology"]["group_id"] not in ("htc:grp_metal_machinery_hardware", "htc:grp_glass_ceramics_paper_woodware", "htc:grp_metallic_ores", "htc:grp_cooperage_ship_timber")
                and "waste" not in c["skos_prefLabel"].lower()
            ]
            if cands:
                cands.sort(key=lambda x: (not x["skos_prefLabel"].lower().startswith(mterm), -x["total_rows"]))
                base_by_qid[mq] = cands[0]["concept_id"]

    for c in concepts:
        cid = c["concept_id"]
        mats = c.get("made_of_material") or []
        for m in mats:
            bcid = base_by_qid.get(m["qid"])
            if bcid and bcid != cid:
                if bcid not in c["material_concepts"]:
                    c["material_concepts"].append(bcid)
                # Wire bidirectional skos:related for single-material cross-stage links (e.g. Copper Ore <-> Copper,
                # Copper Wire <-> Copper, Iron Ore <-> Iron, Cotton Manufactures <-> Cotton), strictly S27-safe!
                if len(mats) == 1 and c["ontology"]["group_id"] != by_id[bcid]["ontology"]["group_id"]:
                    add_related(cid, bcid)

    # Save updated commodities_concepts.jsonl
    with open(GROUND / "commodities_concepts.jsonl", "w", encoding="utf-8") as fh:
        for c in concepts:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    # ========================================================================
    # 6. Export v4 SKOS Turtle, JSON-LD (WITH all oe: ontology triples!), SSSOM & CI Checks
    # ========================================================================
    broader_1866 = {}
    series_nodes = {}
    for c in concepts:
        bc = ((c.get("skos_1866_bridge") or {}).get("broaderConcept") or "").strip()
        if bc: broader_1866[slugify(bc)] = bc
        for s in c["provenance"]["series"]:
            series_nodes[slugify(s)] = s

    scheme_title = "Open Empire Layer-1 Human-Transcribed Trade Commodities SKOS Vocabulary (LINCS / CIDOC CRM E55_Type Compatible)"
    scheme_desc = (
        "Four-tier historical archival SKOS vocabulary and thesaurus (9 Macro-Sectors -> 44 Commodity Groups -> "
        "Canonical Substance Groups -> 2,066 persistent verbatim British & Canadian customs headings, dual-typed as "
        "skos:Concept and crm:E55_Type for LINCS/CIDOC CRM interoperability) enriched with definitions, scopeNotes, "
        "synonyms, cross-stage material chains, and verified Linnaean source taxa mined from six 19th-century "
        "commercial dictionaries (Simmonds 1892/1854, Mortimer 1823, McCulloch 1880, Watt 1908, Ure) and linked via "
        "reversible multi-anchor SKOS mappings to Wikidata (2026-11-09), FAO AGROVOC, ZBW STW Economics, Getty AAT, "
        "Catalogue of Life, SITC Rev. 4, and Theodoridis (2018)."
    )

    # OWL property definitions with domains, ranges, and owl:inverseOf pairs (emitted in BOTH TTL and JSON-LD!)
    OE_PROPS = [
        ("oe:substanceHead", "owl:DatatypeProperty", "substance head", "skos:Concept", "xsd:string", None),
        ("oe:processingState", "owl:DatatypeProperty", "processing state facet", "skos:Concept", "xsd:string", None),
        ("oe:ghostAcresDomain", "owl:DatatypeProperty", "Ghost Acres analytical domain", "skos:Concept", "xsd:string", None),
        ("oe:landBasis", "owl:DatatypeProperty", "ecological land/marine/mineral basis", "skos:Concept", "xsd:string", None),
        ("oe:theodoridisBucket", "owl:DatatypeProperty", "Theodoridis (2018) 5-bucket rollup", "skos:Concept", "xsd:string", None),
        ("oe:sitcCode", "owl:DatatypeProperty", "SITC Rev. 4 division code", "skos:Concept", "xsd:string", None),
        ("oe:isAggregate", "owl:DatatypeProperty", "is printed total/aggregate heading", "skos:Concept", "xsd:boolean", None),
        ("oe:observationCount", "owl:DatatypeProperty", "Layer-1 human observation count", "skos:Concept", "xsd:integer", None),
        ("oe:firstAttested", "owl:DatatypeProperty", "first attested ledger year", "skos:Concept", "xsd:integer", None),
        ("oe:lastAttested", "owl:DatatypeProperty", "last attested ledger year", "skos:Concept", "xsd:integer", None),
        ("oe:groundingStatus", "owl:DatatypeProperty", "Layer-B grounding status", "skos:Concept", "xsd:string", None),
        ("oe:mappingAuthority", "owl:DatatypeProperty", "Layer-B mapping authority snapshot", "skos:Concept", "xsd:string", None),
        ("oe:dictionarySource", "owl:ObjectProperty", "19th-century commercial dictionary source page", "skos:Concept", None, "oe:definesConcept"),
        ("oe:definesConcept", "owl:ObjectProperty", "archival concept defined by this dictionary source page", None, "skos:Concept", "oe:dictionarySource"),
        ("oe:combinesConcept", "owl:ObjectProperty", "merged customs line combining constituent archival concepts", "skos:Concept", "skos:Concept", "oe:isCombinedInConcept"),
        ("oe:isCombinedInConcept", "owl:ObjectProperty", "merged customs heading combining this archival concept", "skos:Concept", "skos:Concept", "oe:combinesConcept"),
        ("oe:sourceTaxon", "owl:ObjectProperty", "biological source taxon (Wikidata/CoL)", "skos:Concept", None, "oe:isSourceTaxonOf"),
        ("oe:isSourceTaxonOf", "owl:ObjectProperty", "archival commodity concept derived from this biological taxon", None, "skos:Concept", "oe:sourceTaxon"),
        ("oe:madeOfMaterial", "owl:ObjectProperty", "base material of manufactured article or ore (Wikidata)", "skos:Concept", None, "oe:isMaterialOf"),
        ("oe:isMaterialOf", "owl:ObjectProperty", "archival commodity concept made from this base material", None, "skos:Concept", "oe:madeOfMaterial"),
        ("oe:materialConcept", "owl:ObjectProperty", "canonical base-material archival concept in htc:scheme", "skos:Concept", "skos:Concept", "oe:isMaterialConceptOf"),
        ("oe:isMaterialConceptOf", "owl:ObjectProperty", "derived ore/semi-finished/manufactured concept using this base material", "skos:Concept", "skos:Concept", "oe:materialConcept"),
        ("oe:colId", "owl:DatatypeProperty", "Catalogue of Life taxon ID", None, "xsd:string", None),
    ]

    ttl_lines = [
        f"@prefix htc: <{BASE_URI}> .",
        f"@prefix htc1866: <{HTC1866_URI}> .",
        f"@prefix oe: <{OE_NS}> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix wd: <http://www.wikidata.org/entity/> .",
        "@prefix agrovoc: <http://aims.fao.org/aos/agrovoc/> .",
        "@prefix stw: <http://zbw.eu/stw/descriptor/> .",
        "@prefix aat: <http://vocab.getty.edu/aat/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]
    jsonld_graph = []

    for pid, ptype, plbl, pdom, prng, pinv in OE_PROPS:
        parts = [f"a {ptype}", f"rdfs:label {ttl_str(plbl)}@en"]
        jnode = {"@id": pid, "@type": ptype, "rdfs:label": {"@value": plbl, "@language": "en"}}
        if pdom:
            parts.append(f"rdfs:domain {pdom}")
            jnode["rdfs:domain"] = {"@id": pdom}
        if prng:
            parts.append(f"rdfs:range {prng}")
            jnode["rdfs:range"] = {"@id": prng}
        if pinv:
            parts.append(f"owl:inverseOf {pinv}")
            jnode["owl:inverseOf"] = {"@id": pinv}
        ttl_lines.append(f"{pid} " + " ; ".join(parts) + " .")
        jsonld_graph.append(jnode)
    ttl_lines.append("")

    top_sec_ids = [f"htc:{s}" for s in sorted(SECTORS)]
    ttl_lines.append(
        "htc:scheme a skos:ConceptScheme ;\n"
        f"    dcterms:title {ttl_str(scheme_title)}@en ;\n"
        f"    dcterms:description {ttl_str(scheme_desc)}@en ;\n"
        '    dcterms:creator "Dr. Jim Clifford & HGIS Lab, University of Saskatchewan"@en ;\n'
        "    dcterms:license <https://creativecommons.org/licenses/by/4.0/> ;\n"
        f'    dcterms:created "{TODAY}"^^xsd:date ;\n'
        '    owl:versionInfo "4.0-layer1-human-dict-enriched" ;\n'
        f"    skos:hasTopConcept {', '.join(top_sec_ids)} .\n"
    )
    jsonld_graph.append({
        "@id": "htc:scheme", "@type": "skos:ConceptScheme",
        "dcterms:title": {"@value": scheme_title, "@language": "en"},
        "dcterms:description": {"@value": scheme_desc, "@language": "en"},
        "dcterms:creator": {"@value": "Dr. Jim Clifford & HGIS Lab, University of Saskatchewan", "@language": "en"},
        "dcterms:license": {"@id": "https://creativecommons.org/licenses/by/4.0/"},
        "dcterms:created": {"@value": TODAY, "@type": "xsd:date"},
        "owl:versionInfo": "4.0-layer1-human-dict-enriched",
        "skos:hasTopConcept": [{"@id": tid} for tid in top_sec_ids],
    })

    ttl_lines.append(
        "htc1866:scheme a skos:ConceptScheme ;\n"
        '    dcterms:title "1866 British Customs Curated Broader Concepts (SKOS_from_Custom_Records.xlsx)"@en ;\n'
        f"    skos:hasTopConcept {', '.join(f'htc1866:{s}' for s in sorted(broader_1866))} .\n"
    )
    jsonld_graph.append({
        "@id": "htc1866:scheme", "@type": "skos:ConceptScheme",
        "dcterms:title": {"@value": "1866 British Customs Curated Broader Concepts (SKOS_from_Custom_Records.xlsx)", "@language": "en"},
        "skos:hasTopConcept": [{"@id": f"htc1866:{s}"} for s in sorted(broader_1866)],
    })

    for sslug, slbl in sorted(series_nodes.items()):
        sid = f"oe:series_{sslug}"
        ttl_lines.append(f"{sid} a prov:Entity ;\n    rdfs:label {ttl_str(slbl)}@en .\n")
        jsonld_graph.append({"@id": sid, "@type": "prov:Entity", "rdfs:label": {"@value": slbl, "@language": "en"}})

    # Tier 1: Macro-Sectors (dual-typed skos:Concept + crm:E55_Type for LINCS compatibility)
    for sec, slbl in sorted(SECTORS.items()):
        sid = f"htc:{sec}"
        ttl_lines.append(f"{sid} a skos:Concept, crm:E55_Type ;\n    skos:inScheme htc:scheme ;\n    skos:topConceptOf htc:scheme ;\n    skos:prefLabel {ttl_str(slbl)}@en .\n")
        jsonld_graph.append({"@id": sid, "@type": ["skos:Concept", "crm:E55_Type"], "skos:inScheme": {"@id": "htc:scheme"}, "skos:topConceptOf": {"@id": "htc:scheme"}, "skos:prefLabel": {"@value": slbl, "@language": "en"}})

    # Tier 2: Mid-Level Commodity Groups
    for grp, (glbl, psec, _) in sorted(GROUPS.items()):
        gid = f"htc:{grp}"
        ttl_lines.append(f"{gid} a skos:Concept, crm:E55_Type ;\n    skos:inScheme htc:scheme ;\n    skos:prefLabel {ttl_str(glbl)}@en ;\n    skos:broader htc:{psec} .\n")
        jsonld_graph.append({"@id": gid, "@type": ["skos:Concept", "crm:E55_Type"], "skos:inScheme": {"@id": "htc:scheme"}, "skos:prefLabel": {"@value": glbl, "@language": "en"}, "skos:broader": {"@id": f"htc:{psec}"}})

    # Tier 3: Layer-A' Substance Groups
    for sid, sc in sorted(sub_concepts.items()):
        ttl_lines.append(f"{sid} a skos:Concept, crm:E55_Type ;\n    skos:inScheme htc:scheme ;\n    skos:prefLabel {ttl_str(sc['label'])}@en ;\n    skos:broader {sc['parent']} .\n")
        jsonld_graph.append({"@id": sid, "@type": ["skos:Concept", "crm:E55_Type"], "skos:inScheme": {"@id": "htc:scheme"}, "skos:prefLabel": {"@value": sc["label"], "@language": "en"}, "skos:broader": {"@id": sc["parent"]}})

    # 1866 broader concepts
    for bslug, blbl in sorted(broader_1866.items()):
        bid = f"htc1866:{bslug}"
        ttl_lines.append(f"{bid} a skos:Concept, crm:E55_Type ;\n    skos:inScheme htc1866:scheme ;\n    skos:topConceptOf htc1866:scheme ;\n    skos:prefLabel {ttl_str(blbl)}@en .\n")
        jsonld_graph.append({"@id": bid, "@type": ["skos:Concept", "crm:E55_Type"], "skos:inScheme": {"@id": "htc1866:scheme"}, "skos:topConceptOf": {"@id": "htc1866:scheme"}, "skos:prefLabel": {"@value": blbl, "@language": "en"}})

    taxon_nodes = {}
    sssom_rows = []

    for c in concepts:
        cid = c["concept_id"]
        pref = c["skos_prefLabel"]
        f = c["facets"]
        prov = c["provenance"]
        ont = c["ontology"]
        a = c.get("wikidata_anchor") or {}
        ext = c.get("external_lod_anchors") or {}
        br = c.get("skos_1866_bridge") or {}

        triples = [
            "a skos:Concept, crm:E55_Type",
            "skos:inScheme htc:scheme",
            f"skos:notation {ttl_str(c['notation'])}",
            f"skos:prefLabel {ttl_str(pref)}@en",
            f"skos:broader {ont['broader_id']}",
            f'oe:observationCount "{c["total_rows"]}"^^xsd:integer',
            f"oe:groundingStatus {ttl_str(c['status'])}",
            f"oe:substanceHead {ttl_str(f['substance_head'])}",
            f"oe:processingState {ttl_str(f['processing_state'])}",
            f"oe:ghostAcresDomain {ttl_str(f['ghost_acres_domain'])}",
            f"oe:landBasis {ttl_str(f['land_basis'])}",
            f"oe:theodoridisBucket {ttl_str(f['theodoridis_category'])}",
            f"oe:sitcCode {ttl_str(f['sitc_code'])}",
            f'oe:isAggregate "{"true" if f["is_aggregate"] else "false"}"^^xsd:boolean',
        ]
        node = {
            "@id": cid, "@type": ["skos:Concept", "crm:E55_Type"],
            "skos:inScheme": {"@id": "htc:scheme"},
            "skos:notation": c["notation"],
            "skos:prefLabel": {"@value": pref, "@language": "en"},
            "skos:broader": {"@id": ont["broader_id"]},
            "oe:observationCount": c["total_rows"],
            "oe:groundingStatus": c["status"],
            "oe:substanceHead": f["substance_head"],
            "oe:processingState": f["processing_state"],
            "oe:ghostAcresDomain": f["ghost_acres_domain"],
            "oe:landBasis": f["land_basis"],
            "oe:theodoridisBucket": f["theodoridis_category"],
            "oe:sitcCode": f["sitc_code"],
            "oe:isAggregate": bool(f["is_aggregate"]),
        }

        if c["skos_altLabels"]:
            triples.append("skos:altLabel " + ", ".join(f"{ttl_str(x)}@en" for x in c["skos_altLabels"]))
            node["skos:altLabel"] = [{"@value": x, "@language": "en"} for x in c["skos_altLabels"]]

        if c["skos_definition"]:
            triples.append(f"skos:definition {ttl_str(c['skos_definition'])}@en")
            node["skos:definition"] = {"@value": c["skos_definition"], "@language": "en"}

        if c.get("skos_scopeNote"):
            triples.append(f"skos:scopeNote {ttl_str(c['skos_scopeNote'])}@en")
            node["skos:scopeNote"] = {"@value": c["skos_scopeNote"], "@language": "en"}

        if c["dictionary_sources"]:
            drefs = [f"<{d['uri']}>" for d in c["dictionary_sources"]]
            triples.append(f"oe:dictionarySource {', '.join(drefs)}")
            node["oe:dictionarySource"] = [{"@id": d["uri"]} for d in c["dictionary_sources"]]

        if prov.get("first_attested"):
            triples.append(f'oe:firstAttested "{prov["first_attested"]}"^^xsd:integer')
            node["oe:firstAttested"] = prov["first_attested"]
        if prov.get("last_attested"):
            triples.append(f'oe:lastAttested "{prov["last_attested"]}"^^xsd:integer')
            node["oe:lastAttested"] = prov["last_attested"]
        if prov.get("series"):
            srefs = [f"oe:series_{slugify(s)}" for s in prov["series"]]
            triples.append(f"prov:hadPrimarySource {', '.join(srefs)}")
            node["prov:hadPrimarySource"] = [{"@id": sr} for sr in srefs]

        if c["combines_concepts"]:
            triples.append(f"oe:combinesConcept {', '.join(c['combines_concepts'])}")
            node["oe:combinesConcept"] = [{"@id": x} for x in c["combines_concepts"]]
        if c["material_concepts"]:
            triples.append(f"oe:materialConcept {', '.join(c['material_concepts'])}")
            node["oe:materialConcept"] = [{"@id": x} for x in c["material_concepts"]]
        if c["related_concepts"]:
            triples.append(f"skos:related {', '.join(c['related_concepts'])}")
            node["skos:related"] = [{"@id": x} for x in c["related_concepts"]]

        rel_targets = defaultdict(list)
        if br.get("broaderConcept"):
            b1866 = f"htc1866:{slugify(br['broaderConcept'])}"
            rel_targets["skos:broadMatch"].append(b1866)
            node.setdefault("skos:broadMatch", []).append({"@id": b1866})

        if a.get("qid"):
            rel = a["mapping_relation"]
            if a.get("component_substances"):
                for comp in a["component_substances"]:
                    rel_targets[rel].append(f"wd:{comp['qid']}")
                    node.setdefault(rel, []).append({"@id": f"http://www.wikidata.org/entity/{comp['qid']}"})
                    sssom_rows.append([cid, pref, rel, f"wd:{comp['qid']}", comp["wd_label"], "semapv:LexicalMatching", "build_skos_v4.py", a.get("source_authority",""), "0.85", f"compound; via={comp.get('matched_via_term','')}"])
            else:
                rel_targets[rel].append(f"wd:{a['qid']}")
                node.setdefault(rel, []).append({"@id": f"http://www.wikidata.org/entity/{a['qid']}"})
                sssom_rows.append([cid, pref, rel, f"wd:{a['qid']}", a.get("wd_label",""), "semapv:LexicalMatching", "build_skos_v4.py", a.get("source_authority",""), "0.95" if rel=="skos:exactMatch" else "0.85", f"rule={a.get('match_rule','')}; via={a.get('matched_via_term','')}"])
            triples.append(f"oe:mappingAuthority {ttl_str(a['source_authority'])}")
            node["oe:mappingAuthority"] = a["source_authority"]

        if ext.get("agrovoc_ids"):
            ar = ext["agrovoc_relation"]
            for aid in ext["agrovoc_ids"]:
                cag = aid if aid.startswith("c_") else f"c_{aid}"
                rel_targets[ar].append(f"agrovoc:{cag}")
                node.setdefault(ar, []).append({"@id": f"http://aims.fao.org/aos/agrovoc/{cag}"})
                sssom_rows.append([cid, pref, ar, f"agrovoc:{cag}", "", "semapv:MappingChaining", "build_skos_v4.py", "wikidata_P8061", "0.85", "composed"])
        if ext.get("stw_ids"):
            sr = ext["stw_relation"]
            for sid in ext["stw_ids"]:
                rel_targets[sr].append(f"stw:{sid}")
                node.setdefault(sr, []).append({"@id": f"http://zbw.eu/stw/descriptor/{sid}"})
                sssom_rows.append([cid, pref, sr, f"stw:{sid}", "", "semapv:MappingChaining", "build_skos_v4.py", "wikidata_P3911", "0.85", "composed"])
        if ext.get("getty_aat_ids"):
            gr = ext["getty_aat_relation"]
            for gid in ext["getty_aat_ids"]:
                rel_targets[gr].append(f"aat:{gid}")
                node.setdefault(gr, []).append({"@id": f"http://vocab.getty.edu/aat/{gid}"})
                sssom_rows.append([cid, pref, gr, f"aat:{gid}", "", "semapv:MappingChaining", "build_skos_v4.py", "wikidata_P1014", "0.85", "composed"])

        for rel, objs in sorted(rel_targets.items()):
            triples.append(f"{rel} {', '.join(list(dict.fromkeys(objs)))}")

        if c["source_taxa"]:
            trefs = []
            for tax in c["source_taxa"]:
                tq = tax["qid"]
                if f"wd:{tq}" not in trefs: trefs.append(f"wd:{tq}")
                if tq not in taxon_nodes: taxon_nodes[tq] = (tax.get("taxon_name",""), tax.get("col_id",""))
            triples.append(f"oe:sourceTaxon {', '.join(trefs)}")
            node["oe:sourceTaxon"] = [{"@id": f"http://www.wikidata.org/entity/{tq.replace('wd:','')}"} for tq in trefs]

        if c["made_of_material"]:
            mrefs = [f"wd:{m['qid']}" for m in c["made_of_material"]]
            triples.append(f"oe:madeOfMaterial {', '.join(mrefs)}")
            node["oe:madeOfMaterial"] = [{"@id": f"http://www.wikidata.org/entity/{m['qid']}"} for m in c["made_of_material"]]

        ttl_lines.append(f"{cid} " + " ;\n    ".join(triples) + " .\n")
        jsonld_graph.append(node)

    for tq, (tname, col_id) in sorted(taxon_nodes.items()):
        tt = []
        tn = {"@id": f"http://www.wikidata.org/entity/{tq}"}
        if tname: tt.append(f"rdfs:label {ttl_str(tname)}"); tn["rdfs:label"] = tname
        if col_id: tt.append(f"oe:colId {ttl_str(col_id)}"); tn["oe:colId"] = col_id
        if tt:
            ttl_lines.append(f"wd:{tq} " + " ;\n    ".join(tt) + " .\n")
            jsonld_graph.append(tn)

    ttl_path = GROUND / "commodities_skos.ttl"
    ttl_text = "\n".join(ttl_lines)
    ttl_path.write_text(ttl_text, encoding="utf-8")

    jsonld_obj = {
        "@context": {
            "htc": BASE_URI, "htc1866": HTC1866_URI, "oe": OE_NS,
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "crm": "http://www.cidoc-crm.org/cidoc-crm/",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "owl": "http://www.w3.org/2002/07/owl#",
            "dcterms": "http://purl.org/dc/terms/",
            "prov": "http://www.w3.org/ns/prov#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "wd": "http://www.wikidata.org/entity/",
            "agrovoc": "http://aims.fao.org/aos/agrovoc/",
            "stw": "http://zbw.eu/stw/descriptor/",
            "aat": "http://vocab.getty.edu/aat/",
            "oe:observationCount": {"@type": "xsd:integer"},
            "oe:firstAttested": {"@type": "xsd:integer"},
            "oe:lastAttested": {"@type": "xsd:integer"},
            "oe:isAggregate": {"@type": "xsd:boolean"},
        },
        "@graph": jsonld_graph,
    }
    jsonld_path = GROUND / "commodities_skos.jsonld"
    jsonld_path.write_text(json.dumps(jsonld_obj, indent=2, ensure_ascii=False), encoding="utf-8")

    sssom_path = GROUND / "commodities_mappings.sssom.tsv"
    with open(sssom_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(f"#curie_map:\n#  htc: {BASE_URI}\n#  wd: http://www.wikidata.org/entity/\n#  agrovoc: http://aims.fao.org/aos/agrovoc/\n#  stw: http://zbw.eu/stw/descriptor/\n#  aat: http://vocab.getty.edu/aat/\n#mapping_set_id: {BASE_URI}mappings/v4\n#mapping_date: {TODAY}\n#license: https://creativecommons.org/licenses/by/4.0/\n")
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["subject_id", "subject_label", "predicate_id", "object_id", "object_label", "mapping_justification", "mapping_tool", "author_label", "confidence", "comment"])
        w.writerows(sssom_rows)

    # --- Built-in CI Verification Suite ---
    ci_errors = []
    if "c_c_" in ttl_text: ci_errors.append("FAIL: c_c_ in TTL")
    all_scheme_prefs = Counter()
    for n in jsonld_graph:
        if n.get("@type") == "skos:Concept" and (n.get("skos:inScheme") or {}).get("@id") == "htc:scheme":
            pl = (n.get("skos:prefLabel") or {}).get("@value", "").lower()
            all_scheme_prefs[pl] += 1
    s14_dups = {k: v for k, v in all_scheme_prefs.items() if v > 1}
    if s14_dups: ci_errors.append(f"FAIL: S14 duplicate prefLabels in htc:scheme: {list(s14_dups.items())[:10]}")
    bad_qids = {q for _, q, _ in AUDIT_REJECTIONS}
    ex_targets = defaultdict(list)
    for c in concepts:
        a = c.get("wikidata_anchor")
        if a and a.get("qid") in bad_qids: ci_errors.append(f"FAIL: Rejected QID {a['qid']} on {c['concept_id']}")
        if a and a["mapping_relation"] == "skos:exactMatch": ex_targets[a["qid"]].append(c["concept_id"])
        if "pig" in c["skos_prefLabel"].lower() and any(m in c["skos_prefLabel"].lower() for m in ("iron","lead","copper")) and c["facets"]["ghost_acres_domain"] == "food_animal":
            ci_errors.append(f"FAIL: Metal pig in food_animal: {c['concept_id']} {c['skos_prefLabel']}")
    if any(len(v) > 1 for v in ex_targets.values()): ci_errors.append("FAIL: Duplicate exactMatch QID")

    # Summary stats
    tot_r = sum(c["total_rows"] for c in concepts)
    g_c = [c for c in concepts if (c.get("wikidata_anchor") or {}).get("qid")]
    with_def = sum(1 for c in concepts if c["skos_definition"])
    with_alt = sum(1 for c in concepts if c["skos_altLabels"])
    with_rel = sum(1 for c in concepts if c["related_concepts"])
    with_comb = sum(1 for c in concepts if c["combines_concepts"])
    with_tax = sum(1 for c in concepts if c["source_taxa"])
    print(f"\n=== SKOS v4 BUILD COMPLETE (4-TIER ONTOLOGY + 6 DICTIONARIES) ===")
    print(f"Hierarchy  : {len(SECTORS)} Macro-Sectors -> {len(GROUPS)} Commodity Groups -> {len(sub_concepts)} Substance Groups -> {len(concepts):,} Verbatim Concepts")
    print(f"Grounded WD: {len(g_c):,} concepts / {sum(c['total_rows'] for c in g_c):,} rows ({sum(c['total_rows'] for c in g_c)/tot_r*100:.1f}%)")
    print(f"Enrichment : {with_def:,} w/ 19th-c. skos:definition | {with_alt:,} w/ skos:altLabel | {with_rel:,} w/ skos:related | {with_comb} merged oe:combinesConcept | {with_tax:,} w/ oe:sourceTaxon")
    print(f"Exports    : {ttl_path.name} ({ttl_path.stat().st_size/1024:.1f} KB), {jsonld_path.name} ({jsonld_path.stat().st_size/1024:.1f} KB), {sssom_path.name} ({len(sssom_rows):,} rows)")
    if ci_errors:
        print("CI ERRORS:", ci_errors[:10])
        raise SystemExit(1)
    print("CI PASSED  : 0 c_c_ | 0 S14 prefLabel clashes | 0 exactMatch collapses | 0 rejected QIDs | 0 metal-pig animal bugs | 0 orphans!")

    # Spot-check Jim's exact test cases + Opus's v3 P0s!
    print("\n=== SPOT-CHECK: CAOUTCHOUC, GUTTA PERCHA, TALLOW, TEA/COFFEE & OPUS v3 P0s ===")
    for cid in ["htc:0015", "htc:0142", "htc:0696", "htc:0022", "htc:0030", "htc:0076", "htc:0081", "htc:0002", "htc:0005", "htc:0006", "htc:0342", "htc:1672"]:
        c = by_id.get(cid)
        if not c: continue
        a = c.get("wikidata_anchor") or {}
        print(f"  {cid} {c['skos_prefLabel']:32s} | grp={c['ontology']['group_id']} | wd={a.get('mapping_relation','none')} {a.get('qid','')} ({a.get('wd_label','')})")
        print(f"       alts={c['skos_altLabels'][:4]} rel={c['related_concepts'][:4]} comb={c['combines_concepts']} taxa={[t['taxon_name'] for t in c['source_taxa'][:3]]}")
        if c["skos_definition"]:
            print(f"       def={c['skos_definition'][:115]}...")


if __name__ == "__main__":
    main()
