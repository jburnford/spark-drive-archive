#!/usr/bin/env python3
"""
Build Layer-A archival SKOS concepts (v3) for Layer-1 (`human_transcribed`) commodities:
  1. Freezes persistent opaque IDs (`htc:0001`..`htc:2066`) in `htc_id_registry.tsv`
     keyed on verbatim `commodity_as_printed` (never re-derived from frequency rank!).
  2. Extracts exact archival provenance from `human_trade_observations.tsv.gz`
     (`first_attested`, `last_attested`, `series_list`, `row_count`) and reconciles
     the full Layer-1 observation count transparently.
  3. Fixes every Opus P0/P1 Layer-A facet defect:
     - `substance_head`: never splits intra-word hyphens (`Cocoa-nut`, `Kiln-Dried`, `Gold-bearing`).
     - `processing_state`: fixes rule order (skins/hides/wool before `live`; `copper in pigs`
       guarded; `manufactured` before `raw`; context-dependent `dressed`; separates `sawn_hewn`
       from `milled_ground`; `processed_pulp`, `dairy_processed`, `byproduct_cake`).
     - `ghost_acres_domain`: guards substring collisions (`cocoa butter`, `soda ash`, `bolts and nuts`,
       `cordage not of iron`, `wool cotton`, `cotton seed`), runs `manufactured_goods` & `tannins_leather`
       before raw fibres/metals/animals, adds `fodder_feed` & `fisheries_marine`, expands ~200 plural-tolerant
       customs terms (cutting `other` by ~75%).
     - Adds `oe:landBasis` (`terrestrial_crop`/`terrestrial_pasture`/`terrestrial_forest`/`marine`/
       `mineral`/`industrial_manufactured`/`unclassified`) and `oe:isAggregate` for `Total` headings.
     - Decouples real SITC Rev. 4 division codes (`SITC4_00`..`SITC4_89`, never misusing SITC 9
       for classifier failures) and derives Theodoridis (2018) buckets from corrected domain + state.
"""

import csv
import gzip
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path("/home/jic823/Documents/open_empire/human_trade")
LAYER1 = BASE / "layer1_human"
GROUND = LAYER1 / "grounding"
GROUND.mkdir(parents=True, exist_ok=True)
SKOS_XLSX = BASE / "raw_sources" / "SKOS_from_Custom_Records.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_or_freeze_id_registry(existing_concepts_path: Path, registry_path: Path, all_headings: list):
    """Load frozen htc ID registry, or bootstrap once from existing commodities_concepts.jsonl."""
    reg = {}
    max_num = 0
    if registry_path.exists():
        for r in csv.DictReader(open(registry_path, encoding="utf-8"), delimiter="\t"):
            reg[r["commodity_as_printed"]] = r["concept_id"]
            m = re.search(r"(\d+)$", r["concept_id"])
            if m:
                max_num = max(max_num, int(m.group(1)))
    elif existing_concepts_path.exists():
        for line in open(existing_concepts_path, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            lbl = d["skos_prefLabel"]
            cid = d["concept_id"]
            reg[lbl] = cid
            m = re.search(r"(\d+)$", cid)
            if m:
                max_num = max(max_num, int(m.group(1)))

    # Append any new headings strictly at the end (never renumber existing IDs!)
    for h in sorted(all_headings):
        if h not in reg:
            max_num += 1
            reg[h] = f"htc:{max_num:04d}"

    with open(registry_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["concept_id", "commodity_as_printed"])
        for lbl, cid in sorted(reg.items(), key=lambda x: x[1]):
            w.writerow([cid, lbl])
    return reg


def load_1866_skos():
    """Read curated 1866 SKOS_from_Custom_Records.xlsx (414 concepts + 54 broader concepts)."""
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
        rmap = {}
        mx = 0
        for c in r.findall("m:c", NS):
            ref = "".join(ch for ch in c.attrib["r"] if ch.isalpha())
            ci = 0
            for ch in ref:
                ci = ci * 26 + (ord(ch.upper()) - ord("A") + 1)
            mx = max(mx, ci)
            v = c.find("m:v", NS)
            if v is None:
                val = ""
            elif c.attrib.get("t") == "s":
                val = ss[int(v.text)]
            else:
                val = v.text or ""
            rmap[ci] = val.strip()
        rows.append([rmap.get(i, "") for i in range(1, mx + 1)])
    hdr = rows[0]
    idx = {h.strip(): i for i, h in enumerate(hdr)}
    for r in rows[1:]:
        def g(col):
            i = idx.get(col)
            return r[i].strip() if i is not None and i < len(r) else ""
        concept = g("Concept") or g("skos:Concept") or (r[0] if r else "")
        pref = g("prefLabel") or g("skos:prefLabel") or concept
        broader = g("broader") or g("broaderConcept") or g("skos:broader")
        state = g("state") or g("State")
        src_of = g("sourceOf") or g("SourceOf")
        if not concept:
            continue
        rec = {
            "skos_concept": concept,
            "prefLabel": pref,
            "broaderConcept": broader,
            "state": state,
            "sourceOf": src_of,
        }
        for k in {norm_key(concept), norm_key(pref)}:
            if k:
                by_label[k] = rec
    return by_label


def extract_substance_head(raw: str) -> str:
    """Split on spaced delimiters (' - ', ' — ', ': ', '(') ONLY — never intra-word hyphens!"""
    s = (raw or "").strip()
    # Keep "Cocoa-nut", "Coco-nut", "Kiln-Dried", "Gold-bearing", "re-manufactured" intact
    s = re.split(r"\s+[-–—]\s+|\s*\(|\s*:\s*", s, maxsplit=1)[0].strip()
    # Strip trailing boilerplate qualifiers
    s = re.sub(
        r"\b(unenumerated|other sorts|other descriptions|other kinds|not elsewhere specified|"
        r"raw or undressed|undressed|unmanufactured|manufactured|not otherwise enumerated|"
        r"for manufacturing|not fresh|in shell)\b.*$",
        "",
        s,
        flags=re.I,
    ).strip(" ,;-")
    return s or raw.strip()


def classify_facets_v3(raw: str, head: str):
    """Return (processing_state, ghost_acres_domain, land_basis, sitc_code, theodoridis_bucket, is_aggregate)."""
    lo = raw.lower().strip()
    hlo = head.lower().strip()

    is_agg = bool(re.search(r"\btotal\b|\ball kinds\b|\ball sorts\b", lo))

    # --- 1. Context-aware domain classification (guard substring collisions & order carefully!) ---
    domain = "other"

    # Explicit collision guards first
    if re.search(r"\bcocoa\s*butter\b", lo):
        domain = "food_colonial_grocery"
    elif re.search(r"\bsoda\s*ash\b|\bpot\s*ash\b|\bpearl\s*ash|\bashes?\s*(pot|pearl)\b|\b(pearl|pot)\s+and\s+(pot|pearl)\s+ashes?\b|\bpotash\b", lo):
        domain = "drugs_botanicals_chemicals"
    elif re.search(r"\bbolts?\s+and\s+nuts?\b|\bnails?\b|\bstoves?\b|\banchors?\b|\bwire\b|\bcutlery\b|\btools?\b|\bhardware\b|\bmachinery\b|\bsewing machines?\b|\bmusical instruments?\b|\bcarriages?\b|\bclocks?\b|\bwatches?\b|\btoys?\b|\bbooks?\b|\bstationery\b|\bprints?\b|\bpictures?\b|\bcurios?\b|\bmatches?\b|\bglasses?\b|\bglassware\b|\bearthenware\b|\bchinaware\b|\bporcelain\b|\bpottery\b|\bpaper\b(?!.*making materials)|\bfurniture\b|\bboots?\b|\bshoes?\b|\bgloves?\b|\bclothing\b|\bapparel\b|\bhaberdashery\b|\bhats?\b|\bcordage\b|\bropes?\b|\btwine\b|\bcables?\b|\bcanvas\b|\bsailcloth\b|\bpiece goods\b|\byarns?\b|\bcloth\b|\bfabrics?\b|\bmanufactures?\b|\bmanufactured\b|\bcastings?\b|\btype\b|\bshot\b|\bgunpowder\b|\bfirearms?\b|\barms\b|\bammunition\b|\bships?\b|\bboats?\b|\bvehicles?\b|\bcycles?\b|\bbicycles?\b|\brailway carriages?\b|\bsteam engines?\b|\bagricultural implements?\b|\bhousehold furniture\b|\bglass\b|\bbuttons?\b|\bbeads?\b|\bbugles?\b|\bumbrellas?\b|\bbrooms?\b|\bbrushes?\b|\bbaskets?\b|\btrunks?\b|\bpipes?\b|\bbricks?\b|\btiles?\b|\bcement\b|\bsoap\b|\bcandles?\b|\bstarch\b|\bglue\b|\bvarnish\b|\bpaints?\b|\bcolours?\b|\bblacking\b|\bink\b", lo) and not re.search(r"\bunmanufactured\b|\braw\b|\bore\b|\bpig iron\b|\bscrap\b|\btimber\b|\bwood pulp\b|\bpulp of wood\b|\bpaper making\b", lo):
        # Refine soap/candles to fats_oils_soap
        if re.search(r"\b(soap|candles?)\b", lo):
            domain = "fats_oils_soap"
        else:
            domain = "manufactured_goods"
    # Fodder & animal feed (hinge between imported feed and domestic livestock)
    elif re.search(r"\b(oil\s*seed\s*cakes?|oil\s*cakes?|oilcake|linseed\s*cake|cotton\s*seed\s*cake|rapeseed\s*cake|press\s*cake|hay|straw|bran|pollard|fodder|forage|clover\s*seeds?|grass\s*seeds?|turnip\s*seeds?|mangold|vetches|tares|oil\s*meal)\b", lo):
        domain = "fodder_feed"
    # Fisheries & marine ghost acres (fish, marine mammals, fish/whale/seal oils, sealskins, whalebone, isinglass, sounds)
    elif re.search(r"\b(codfish|cod\b|herrings?|mackerel|salmon|lobsters?|oysters?|halibut|haddock|ling\b|pollock|sardines?|anchovies|pilchards?|sprats?|eels?|trout|shad|alewives|smelts?|fish\b|fisheries|whale\s*oil|seal\s*oil|cod\s*oil|train\s*oil|blubber|spermaceti|porpoise|whalebone|whale\s*fins?|sealskins?|skins?.*seal|seal\s*skins?|isinglass|tongues\s+and\s+sounds|cod\s+sounds|tongues\b|sponge|sponges|coral|mother\s+of\s+pearl|shellfish)\b", lo):
        domain = "fisheries_marine"
    # Tannins, hides, skins, furs, leather (TEST BEFORE live animals so Sheep Skins / Pelts aren't food_animal!)
    elif re.search(r"\b(hides?|skins?|pelts?|furs?|leather|tanning|tanners?|tanbark|bark\s+for\s+tanner|oak\s*bark|hemlock\s*bark|mimosa\s*bark|valonia|cutch|gambier|terra\s*japonica|sumach|shumach|sumac|myr[ao]balans?|divi[\s-]*divi|quercitron|galls?|gallnuts?|nutgalls?|catechu|kino|buffalo\s*robes?|parchment|vellum|chamois)\b", lo):
        domain = "tannins_leather"
    # Raw textile fibres & wool (TEST BEFORE live animals so Wool Sheep and Lambs goes here!)
    elif re.search(r"\b(wool\b|woollen|woolen|cotton\b(?!.*seed)|flax\b(?!.*seed)|hemp\b|jute\b|silk\b|linen\b|tow\b|coir\b|sisal|manila|esparto|rags?\b|oakum|ramie|kapok|alpaca|mohair|vicuna|shoddy|mungo|hair\b|bristles?|feathers?|down\b)\b", lo):
        domain = "fibres_textiles"
    # Fats, oils, oilseeds, waxes (including coconut oil, cottonseed, linseed, tallow, palm/olive oil)
    elif re.search(r"\b(cocoa[\s-]*nut\s*oil|coco[\s-]*nut\s*oil|coconut\s*oil|cotton\s*seeds?|linseed|flax\s*seeds?|flaxseed|rape\s*seeds?|rapeseed|palm\s*oil|olive\s*oil|seed\s*oil|linseed\s*oil|castor\s*oil|tallow|stearin|stearine|lard|grease|suet|dripping|margarine|oleomargarine|oil\b|oils\b|wax|beeswax|paraffin|glycerine|oil\s*seeds?|sesame|ground\s*nuts?|peanuts?|copra|palm\s*kernels?|hemp\s*seed|poppy\s*seed|mustard\s*seed|sunflower\s*seed|seeds?\b)\b", lo):
        domain = "fats_oils_soap"
    # Timber, forestry, wood pulp, naval stores wood
    elif re.search(r"\b(timber|lumber|planks?|boards?|deals?|deal\s*ends?|battens?|staves?|shingles?|laths?|lathwood|scantling|saw\s*logs?|logs?\b|firewood|pulpwood|wood\s*pulp|pulp\s+of\s+wood|paper\s*making\s*materials|masts?|spars?|oars?|handspikes?|knees|futtocks?|sleepers?|railway\s*ties?|railroad\s*ties?|pit\s*wood|pit\s*props?|hoops?|shooks?|headings?|pickets?|palings?|poles?|posts?|rails?|veneers?|other\s+woods?|wood\b|oak\b|pine\b|elm\b|ash\b|birch\b|maple\b|walnut\b|fir\b|spruce\b|cedar\b|hemlock\b|tamarack?|basswood|butternut|hickory|beech\b|poplar|mahogany|teak\b|rosewood|ebony|boxwood|lignum\s*vitae|cork\b|charcoal|bark\b)\b", lo) and not re.search(r"\b(peruvian\s*bark|cinchona|jesuits?\s*bark|cassia|cinnamon)\b", lo) and not (re.search(r"\bwalnuts?\b", lo) and not re.search(r"\b(timber|wood|lumber)\b", lo)):
        domain = "timber_forestry"
    # Grains & cereals (including flour, meal, biscuits, malt, buckwheat, arrowroot, sago, tapioca)
    elif re.search(r"\b(wheat|oats?|barley|rye|maize|indian\s*corn|corn\b|flour|meal\b|oatmeal|cornmeal|semolina|biscuits?|bread|grains?|cereals?|malt\b|buckwheat|rice\b|sago|tapioca|arrowroot|farina|vermicelli|macaroni|peas?\b|pease|beans?|lentils?|pulse|millet|sorghum|groats|grits|hominy|bran)\b", lo):
        domain = "food_grain"
    # Drugs, botanicals, dyestuffs, resins, rubber, chemicals, fertilizers
    elif re.search(r"\b(cinchona|peruvian\s*bark|quinine|opium|caoutchouc|india\s*rubber|rubber|gutta[\s-]*percha|balsam|gum\b|gums\b|resin|rosin|turpentine|tar\b|pitch\b|camphor|shellac|lac\b|indigo|madder|garancine|cochineal|logwood|fustic|brazil\s*wood|sapan|annatto|turmeric|safflower|orch[ai]l|cudbear|woad|weld|dye\s*stuffs?|dyestuffs?|dye\s*woods?|dyewoods?|dyes?\b|colouring|coloring|chemical|alkali|soda\b|barilla|kelp|saltpetre|nitre|nitrate|brimstone|sulphur|sulfur|alum\b|borax|arsenic|vitriol|acid\b|ammonia|bleaching|chloride|carbonate|sulphate|sulfate|bicarbonate|caustic|potash|guano|manure|phosphate|bone\s*ash|bones?\b|horns?\b|hoofs?\b|ivory|elephants?\s*teeth|castor\b|castoreum|manna|senna|rhubarb|jalap|ipecacuanha|sarsaparilla|liquorice|licorice|aloe|aloes|myrrh|frankincense|opium|drugs?\b|medicines?|medicinal|apothecary|leeches|blue\b)\b", lo):
        domain = "drugs_botanicals_chemicals"
    # Colonial groceries, fruits, vegetables, beverages, tobacco, spices
    elif re.search(r"\b(sugar|molasses|treacle|maple\s*sugar|syrup|honey|coffee|tea\b|cocoa|chocolate|chicory|tobacco|cigars?|snuff|spices?|pepper|cinnamon|cassia|cloves?|ginger|nutmegs?|mace\b|pimento|allspice|cardamom|vanilla|saffron|mustard|wine|rum\b|brandy|whiske?y|gin\b|geneva|spirits?|beer|ale\b|porter|cider|vinegar|hops?|fruits?|apples?|pears?|plums?|prunes?|cherries|peaches|cranberries|berries|grapes?|raisins?|currants?|figs?|dates?|oranges?|lemons?|limes?|citrons?|bananas?|pineapples?|almonds?|walnuts?|chestnuts?|filberts?|hazelnuts?|nuts?\b|coconuts?|cocoa[\s-]*nuts?|vegetables?|potatoes?|onions?|turnips?|cabbages?|tomatoes?|pickles?|sauces?|confectionery|jams?|marmalade|preserves?|groceries|provisions)\b", lo):
        domain = "food_colonial_grocery"
    # Livestock, meats, dairy, eggs
    elif re.search(r"\b(cattle|oxen|bulls?|cows?|calves?|steers?|heifers?|sheep|lambs?|swine|hogs?|pigs?(?!\s+iron|\s+lead|\s+copper)|horses?|mares?|geldings?|stallions?|colts?|mules?|asses?|poultry|fowls?|turkeys?|geese|ducks?|game\b|venison|rabbits?|hares?|beef|pork|mutton|veal|bacon|hams?|meats?|sausages?|butter|cheese|milk|cream|eggs?|animals?\s+living|live\s+animals?)\b", lo):
        domain = "food_animal"
    # Minerals, metals, ores, coal, stone, salt, clay, petroleum
    elif re.search(r"\b(coal\b|coals\b|coke\b|cinders?|peat\b|petroleum|kerosene|naphtha|asphalt|bitumen|iron\b|steel\b|copper\b|tin\b|lead\b|zinc\b|spelter|quicksilver|mercury|silver\b|gold\b|platinum|antimony|manganese|cobalt|nickel|bismuth|brass|bronze|pewter|plumbago|graphite|ore\b|ores\b|pyrites|quartz|gypsum|plaster|lime\b|limestone|chalk|slate|marble|granite|stone\b|stones\b|sand\b|gravel|clay\b|mica\b|asbestos|salt\b|minerals?|metals?|bullion|specie|precious\s*stones?|diamonds?)\b", lo):
        domain = "minerals_metals_energy"

    # --- 2. Context-aware processing_state (fixed rule order per Opus §3.2) ---
    state = "unspecified"
    if domain == "manufactured_goods" or re.search(r"\b(manufactures?|manufactured|piece goods|boots?|shoes?|gloves?|stoves?|nails?|anchors?|furniture|carriages?|machinery|hardware|books?|clocks?|watches?|toys?|cordage|ropes?|twine|cloth|yarn|clothing|apparel|biscuits?|canned|bottled|preserved|castings?|soap|candles?)\b", lo) and not re.search(r"\bunmanufactured\b", lo):
        state = "manufactured"
    elif re.search(r"\b(wood\s*pulp|pulp\s+of\s+wood)\b", lo):
        state = "processed_pulp"
    elif re.search(r"\b(butter|cheese)\b", lo) and domain == "food_animal":
        state = "dairy_processed"
    elif re.search(r"\b(oil\s*seed\s*cakes?|oil\s*cakes?|oilcake|press\s*cake|bran|pollard)\b", lo):
        state = "byproduct_cake"
    elif re.search(r"\b(tanned|tawed|curried|varnished|japanned|enamelled|morocco)\b", lo) or (re.search(r"\bdressed\b", lo) and domain == "tannins_leather"):
        state = "dressed_tanned"
    elif re.search(r"\b(dressed|hackled|heckled|carded|combed|scutched)\b", lo) and domain == "fibres_textiles":
        state = "processed_fibre"
    elif re.search(r"\b(planks?|boards?|deals?|battens?|staves?|shingles?|laths?|scantling|sawn|sawed|hewn|planed|dressed|veneers?|sleepers?|ties)\b", lo) and domain == "timber_forestry":
        state = "sawn_hewn"
    elif re.search(r"\b(flour|meal|oatmeal|cornmeal|semolina|ground|crushed|powdered|milled|split\s*peas?)\b", lo):
        state = "milled_ground"
    elif re.search(r"\b(refined|distilled|rectified|extract|essence|oil\b|oils\b|spirits?|wine|rum|brandy|whiske?y|gin|beer|ale|cider|molasses|syrup|sugar\s+refined)\b", lo) and not re.search(r"\bunrefined\b|\braw\b|\bcrude\b|\boil\s*seed|\boil\s*cake", lo):
        state = "refined_extract"
    elif re.search(r"\b(salted|pickled|wet\s+salted|brine|corned)\b", lo) and "pulp" not in lo:
        state = "wet_salted"
    elif re.search(r"\b(dried|dry\b|smoked|cured|kiln[\s-]*dried|roasted|desiccated)\b", lo) and "pulp" not in lo:
        state = "dried_cured"
    elif re.search(r"\b(smelted|pig\s+iron|bar\s+iron|sheet|plate|ingot|bars?|rods?|regulus|wrought)\b", lo) and domain == "minerals_metals_energy":
        state = "smelted_semi"
    elif re.search(r"\b(ore|ores)\b", lo) and domain == "minerals_metals_energy":
        state = "raw_ore"
    elif domain == "food_animal" and re.search(r"\b(cattle|oxen|bulls?|cows?|calves?|sheep|lambs?|swine|hogs?|pigs?|horses?|mares?|geldings?|stallions?|mules?|poultry|fowls?|animals?\s+living|live)\b", lo) and not re.search(r"\b(beef|pork|mutton|veal|bacon|ham|meat|lard|tallow|butter|cheese|milk|egg|tongues?|salted|fresh\s+meat|frozen|canned)\b", lo):
        state = "live"
    elif re.search(r"\b(raw|undressed|unrefined|unmanufactured|crude|unwrought|green|fresh|in\s+shell)\b", lo) or (domain in ("food_grain", "fodder_feed") and not re.search(r"\b(flour|meal|cake|biscuit|malt|bran)\b", lo)):
        state = "raw_unprocessed"

    # --- 3. Independent land_basis (ghost acres ecological basis) ---
    if domain == "fisheries_marine":
        land_basis = "marine"
    elif domain == "timber_forestry":
        land_basis = "terrestrial_forest"
    elif domain == "minerals_metals_energy":
        land_basis = "mineral"
    elif domain == "manufactured_goods":
        land_basis = "industrial_manufactured"
    elif domain == "food_animal":
        land_basis = "terrestrial_pasture"
    elif domain == "tannins_leather":
        land_basis = "terrestrial_forest" if re.search(r"\b(bark|valonia|cutch|gambier|terra|sumach|shumach|sumac|myr[ao]balan|divi|quercitron|gall|catechu|kino)\b", lo) else ("marine" if "seal" in lo else "terrestrial_pasture")
    elif domain in ("food_grain", "food_colonial_grocery", "fodder_feed"):
        land_basis = "terrestrial_crop"
    elif domain == "fibres_textiles":
        land_basis = "terrestrial_pasture" if re.search(r"\b(wool|alpaca|mohair|hair|bristle|feather|silk)\b", lo) else "terrestrial_crop"
    elif domain == "fats_oils_soap":
        land_basis = "terrestrial_pasture" if re.search(r"\b(tallow|stearin|lard|grease|suet|beeswax)\b", lo) else ("mineral" if re.search(r"\b(paraffin|mineral|petroleum|coal\s*oil)\b", lo) else "terrestrial_crop")
    elif domain == "drugs_botanicals_chemicals":
        land_basis = "mineral" if re.search(r"\b(soda|alkali|saltpetre|nitre|nitrate|brimstone|sulphur|sulfur|alum|borax|arsenic|vitriol|acid|ammonia|chloride|carbonate|sulphate|bicarbonate|caustic|phosphate|guano)\b", lo) else "terrestrial_forest"
    else:
        land_basis = "unclassified"

    # --- 4. Independent real SITC Rev. 4 division code (never misusing SITC 9 for classifier gaps!) ---
    sitc = "oe:sitcUnassigned"
    if domain == "food_animal":
        if state == "live":
            sitc = "SITC4_00_Live_Animals"
        elif re.search(r"\b(butter|cheese|milk|cream|eggs?)\b", lo):
            sitc = "SITC4_02_Dairy_and_Eggs"
        else:
            sitc = "SITC4_01_Meat_and_Preparations"
    elif domain == "fisheries_marine":
        if re.search(r"\b(oil|oils|blubber|spermaceti)\b", lo):
            sitc = "SITC4_41_Animal_Oils_and_Fats"
        elif re.search(r"\b(skins?|pelts?|furs?)\b", lo):
            sitc = "SITC4_21_Hides_Skins_Furskins_Raw"
        elif re.search(r"\b(whalebone|whale\s*fins?|isinglass|sponge|coral|shell)\b", lo):
            sitc = "SITC4_29_Crude_Animal_Vegetable_Materials"
        else:
            sitc = "SITC4_03_Fish_and_Seafood"
    elif domain == "food_grain":
        sitc = "SITC4_05_Vegetables_and_Fruit" if re.search(r"\b(peas?|pease|beans?|lentils?|pulse)\b", lo) else "SITC4_04_Cereals_and_Preparations"
    elif domain == "food_colonial_grocery":
        if re.search(r"\b(sugar|molasses|treacle|syrup|honey|confectionery)\b", lo):
            sitc = "SITC4_06_Sugars_and_Honey"
        elif re.search(r"\b(coffee|tea|cocoa|chocolate|chicory|spices?|pepper|cinnamon|cloves?|ginger|nutmeg|mace|pimento|allspice)\b", lo):
            sitc = "SITC4_07_Coffee_Tea_Cocoa_Spices"
        elif re.search(r"\b(wine|rum|brandy|whiske?y|gin|geneva|spirits?|beer|ale|porter|cider)\b", lo):
            sitc = "SITC4_11_Beverages"
        elif re.search(r"\b(tobacco|cigars?|snuff)\b", lo):
            sitc = "SITC4_12_Tobacco"
        else:
            sitc = "SITC4_05_Vegetables_and_Fruit"
    elif domain == "fodder_feed":
        sitc = "SITC4_08_Animal_Feeding_Stuff"
    elif domain == "tannins_leather":
        if re.search(r"\b(leather|parchment|vellum|chamois)\b", lo) or state == "dressed_tanned":
            sitc = "SITC4_61_Leather_and_Dressed_Furskins"
        elif re.search(r"\b(bark|valonia|cutch|gambier|terra|sumach|shumach|sumac|myr[ao]balan|divi|quercitron|gall|catechu|kino)\b", lo):
            sitc = "SITC4_29_Crude_Animal_Vegetable_Materials"
        else:
            sitc = "SITC4_21_Hides_Skins_Furskins_Raw"
    elif domain == "fats_oils_soap":
        if re.search(r"\b(soap|candles?)\b", lo):
            sitc = "SITC4_55_Oils_Perfumes_Cleansing"
        elif re.search(r"\b(seeds?|linseed|flaxseed|rapeseed|copra|kernels?|peanuts?|ground\s*nuts?)\b", lo) and "oil" not in lo:
            sitc = "SITC4_22_Oil_Seeds_and_Oleaginous_Fruits"
        elif re.search(r"\b(tallow|stearin|lard|grease|suet|beeswax)\b", lo):
            sitc = "SITC4_41_Animal_Oils_and_Fats"
        else:
            sitc = "SITC4_42_Fixed_Vegetable_Fats_and_Oils"
    elif domain == "timber_forestry":
        if re.search(r"\b(pulp|paper\s*making)\b", lo):
            sitc = "SITC4_25_Pulp_and_Waste_Paper"
        elif re.search(r"\b(veneers?|staves?|shingles?|hoops?|shooks?|headings?)\b", lo):
            sitc = "SITC4_63_Cork_and_Wood_Manufactures"
        else:
            sitc = "SITC4_24_Cork_and_Wood"
    elif domain == "fibres_textiles":
        sitc = "SITC4_26_Textile_Fibres"
    elif domain == "minerals_metals_energy":
        if re.search(r"\b(coal|coals|coke|cinders?|peat)\b", lo):
            sitc = "SITC4_32_Coal_Coke_Briquettes"
        elif re.search(r"\b(petroleum|kerosene|naphtha)\b", lo):
            sitc = "SITC4_33_Petroleum"
        elif re.search(r"\b(ore|ores|pyrites)\b", lo):
            sitc = "SITC4_28_Metalliferous_Ores"
        elif re.search(r"\b(iron|steel)\b", lo):
            sitc = "SITC4_67_Iron_and_Steel"
        elif re.search(r"\b(copper|tin|lead|zinc|spelter|silver|gold|platinum|antimony|nickel|brass|bronze|mercury|quicksilver)\b", lo):
            sitc = "SITC4_68_Non_Ferrous_Metals"
        else:
            sitc = "SITC4_27_Crude_Fertilizers_and_Minerals"
    elif domain == "drugs_botanicals_chemicals":
        if re.search(r"\b(caoutchouc|rubber|gutta)\b", lo):
            sitc = "SITC4_23_Crude_Rubber"
        elif re.search(r"\b(indigo|madder|cochineal|logwood|fustic|dye|annatto|turmeric|safflower|orch[ai]l|woad|paint|colour)\b", lo):
            sitc = "SITC4_53_Dyeing_Tanning_Colouring"
        elif re.search(r"\b(cinchona|quinine|opium|drugs?|medicines?|senna|rhubarb|jalap|ipecac|sarsaparilla|manna|castoreum|castor)\b", lo):
            sitc = "SITC4_54_Medicinal_Pharmaceutical"
        elif re.search(r"\b(guano|manure|phosphate)\b", lo):
            sitc = "SITC4_27_Crude_Fertilizers_and_Minerals"
        elif re.search(r"\b(gum|resin|rosin|tar|pitch|turpentine|camphor|shellac|lac|balsam|bones?|horns?|hoofs?|ivory)\b", lo):
            sitc = "SITC4_29_Crude_Animal_Vegetable_Materials"
        else:
            sitc = "SITC4_51_52_Chemicals"
    elif domain == "manufactured_goods":
        if re.search(r"\b(cotton|silk|wool|woollen|linen|yarn|cloth|fabric|piece goods|cordage|rope|twine|cable|canvas|textile)\b", lo):
            sitc = "SITC4_65_Textile_Yarn_and_Fabrics"
        elif re.search(r"\b(boots?|shoes?|footwear)\b", lo):
            sitc = "SITC4_85_Footwear"
        elif re.search(r"\b(clothing|apparel|gloves?|hats?|haberdashery)\b", lo):
            sitc = "SITC4_84_Apparel_and_Clothing"
        elif re.search(r"\b(iron|steel|copper|brass|tin|hardware|nails?|bolts?|stoves?|anchors?|cutlery|tools?|wire|castings?)\b", lo):
            sitc = "SITC4_69_Manufactures_of_Metal"
        elif re.search(r"\b(machinery|machine|engines?|implements?|carriages?|vehicles?|ships?|boats?)\b", lo):
            sitc = "SITC4_7_Machinery_and_Transport_Equipment"
        elif re.search(r"\b(paper|books?|stationery|prints?|pictures?)\b", lo):
            sitc = "SITC4_64_Paper_and_Paperboard"
        elif re.search(r"\b(glass|earthenware|porcelain|chinaware|pottery|bricks?|tiles?|cement)\b", lo):
            sitc = "SITC4_66_Non_Metallic_Mineral_Manufactures"
        elif re.search(r"\b(furniture|wood)\b", lo):
            sitc = "SITC4_82_Furniture_and_Wood_Articles"
        else:
            sitc = "SITC4_89_Miscellaneous_Manufactured_Articles"

    # --- 5. Theodoridis (2018) 5-bucket rollup (derived from corrected domain + state) ---
    if domain == "manufactured_goods" or state == "manufactured":
        theodoridis = "manufactured_articles"
    elif domain == "food_grain":
        theodoridis = "grain_and_flour"
    elif domain in ("food_animal", "fisheries_marine") and sitc not in ("SITC4_21_Hides_Skins_Furskins_Raw", "SITC4_29_Crude_Animal_Vegetable_Materials", "SITC4_41_Animal_Oils_and_Fats"):
        theodoridis = "animals_and_animal_products"
    elif domain == "food_colonial_grocery":
        theodoridis = "other_food_drink_spices"
    elif domain in ("timber_forestry", "tannins_leather", "fibres_textiles", "fats_oils_soap", "minerals_metals_energy", "drugs_botanicals_chemicals", "fodder_feed") or domain == "fisheries_marine":
        theodoridis = "raw_materials"
    else:
        theodoridis = "unclassified"

    return state, domain, land_basis, sitc, theodoridis, is_agg


def main():
    # Collect exact provenance & counts from canonical Layer-1 observations
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
            d["series"][ser] += 1

    all_headings = list(comm_stats.keys())
    reg = load_or_freeze_id_registry(
        GROUND / "commodities_concepts.jsonl",
        GROUND / "htc_id_registry.tsv",
        all_headings,
    )
    skos_1866 = load_1866_skos()

    concepts = []
    dom_rows = Counter()
    dom_cnt = Counter()
    theo_rows = Counter()
    land_rows = Counter()
    state_cnt = Counter()
    agg_cnt = 0

    for comm in sorted(all_headings, key=lambda c: reg[c]):
        cid = reg[comm]
        st = comm_stats[comm]
        head = extract_substance_head(comm)
        pstate, domain, land_basis, sitc, theodoridis, is_agg = classify_facets_v3(comm, head)
        if is_agg:
            agg_cnt += 1

        # Check 1866 SKOS bridge: exact normalized heading OR head match
        k_raw = norm_key(comm)
        k_head = norm_key(head)
        bridge = skos_1866.get(k_raw) or skos_1866.get(k_head)
        bridge_rel = None
        if bridge:
            bp = norm_key(bridge["prefLabel"])
            if bp == k_raw or bp == k_head and pstate in ("unspecified", "raw_unprocessed"):
                bridge_rel = "exact_or_synonym"
            else:
                bridge_rel = "broader_1866_concept"

        yrs = sorted(st["years"])
        rec = {
            "concept_id": cid,
            "notation": cid.split(":")[1],
            "rdf_type": "skos:Concept",
            "skos_prefLabel": comm,
            "total_rows": st["rows"],
            "provenance": {
                "first_attested": yrs[0] if yrs else None,
                "last_attested": yrs[-1] if yrs else None,
                "series": [s for s, _ in st["series"].most_common()],
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
            "status": "local_concept_only",
        }
        concepts.append(rec)
        dom_rows[domain] += st["rows"]
        dom_cnt[domain] += 1
        theo_rows[theodoridis] += st["rows"]
        land_rows[land_basis] += st["rows"]
        state_cnt[pstate] += 1

    with open(GROUND / "commodities_concepts_v3.jsonl", "w", encoding="utf-8") as fh:
        for c in concepts:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    tot_comm_rows = sum(c["total_rows"] for c in concepts)
    print(f"Layer-1 reconciliation: {total_obs:,} total obs - {dict(excluded)} = {tot_comm_rows:,} commodity-bearing rows ({len(concepts):,} unique concepts)")
    print(f"Persistent ID registry frozen at: {GROUND / 'htc_id_registry.tsv'} ({len(reg):,} IDs)")
    print(f"Aggregate Total headings flagged: {agg_cnt}")
    print("\n=== DOMAINS v3 ===")
    for d, rcnt in dom_rows.most_common():
        print(f"  {d:28s}: {rcnt:7,d} rows ({rcnt/tot_comm_rows*100:5.1f}%) | {dom_cnt[d]:4d} concepts")
    print("\n=== LAND BASIS v3 ===")
    for lb, rcnt in land_rows.most_common():
        print(f"  {lb:28s}: {rcnt:7,d} rows ({rcnt/tot_comm_rows*100:5.1f}%)")
    print("\n=== THEODORIDIS 5 BUCKETS v3 ===")
    for tb, rcnt in theo_rows.most_common():
        print(f"  {tb:28s}: {rcnt:7,d} rows ({rcnt/tot_comm_rows*100:5.1f}%)")
    print("\n=== PROCESSING STATES v3 ===")
    for ps, cnt in state_cnt.most_common():
        print(f"  {ps:24s}: {cnt:4d} concepts")


if __name__ == "__main__":
    main()
