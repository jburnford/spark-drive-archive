#!/usr/bin/env python3
"""
Mine all 6 parsed 19th-century commercial dictionaries (27,325 entries, 1,190 verified
Catalogue of Life / Wikidata taxa) to systematically unpack the major "Unenumerated"
catch-all categories in the Layer-1 British & Canadian customs trade ledgers.

Produces:
  - dictionaries/unenumerated_commodities_from_books.jsonl
  - dictionaries/unenumerated_commodities_from_books.tsv
  - dictionaries/UNENUMERATED_COMMODITIES_REPORT.md
"""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/home/jic823/Documents/open_empire")
DICT_DIR = ROOT / "dictionaries"
GROUND = ROOT / "human_trade" / "layer1_human" / "grounding"

LEXICON_PATH = DICT_DIR / "commercial_dictionaries_lexicon.jsonl"
BINOM_PATH = DICT_DIR / "dictionary_binomials_grounded.jsonl"
CONCEPTS_PATH = GROUND / "commodities_concepts.jsonl"

OUT_JSONL = DICT_DIR / "unenumerated_commodities_from_books.jsonl"
OUT_TSV = DICT_DIR / "unenumerated_commodities_from_books.tsv"
OUT_MD = DICT_DIR / "UNENUMERATED_COMMODITIES_REPORT.md"

# Major Layer-1 Unenumerated / Catch-All customs headings to unpack
CATCHALLS = {
    "htc:0122": {
        "label": "Drugs Unenumerated",
        "group": "htc:grp_drugs_medicinal_botanicals",
        "rows": 263,
        "def_re": re.compile(
            r"\b(medicinal|medicine|materia\s+medica|alkaloid|narcotic|tonic|purgative|astringent|emetic|"
            r"febrifuge|cathartic|antispasmodic|diuretic|stimulant|druggist|pharmacop|ophthalmic|anodyne|"
            r"masticatory|balsam|tincture|vermifuge|anthelmintic|diaphoretic|expectorant|drug\b)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(coca|cocaine|nux\s+vomica|strychnin|belladonna|atropin|ipecac|cubeb|buchu|calumba|columbo|"
            r"scammony|ergot|digitalis|aconit|asafoetida|assafetida|gentian|squill|valerian|henbane|myrrh|"
            r"aloes|jalap|senna|quassia|cascarilla|sarsaparilla|cantharides|colocynth|copaiba|guaiacum|"
            r"benzoin|storax|tolu|peru\s+balsam|tragacanth|catechu|kino|menthol|thymol|quinine|cinchona|"
            r"morphia|morphine|codeine|chloroform|iodine|bromine|bismuth|calomel|corrosive\s+sublimate|"
            r"chamomile|camomile|dandelion|taraxacum|hemlock|conium|stramonium|lobelia|podophyll|chaulmoogra|"
            r"kousso|kameela|kamala|cardamom|cubebs|pareira|simaruba|angostura|coto|jaborandi|strophanthus|"
            r"kola|guarana|mate|yerba|areca|betel|ginseng|kava|patchouli)\b",
            re.I,
        ),
    },
    "htc:0054": {
        "label": "Dye Stuffs & Dye Woods Unenumerated",
        "also_ids": ["htc:0088"],
        "group": "htc:grp_natural_dyestuffs",
        "rows": 830,  # 482 + 348
        "def_re": re.compile(
            r"\b(dye[\s-]*wood|dyewood|dye[\s-]*stuff|dyestuff|used\s+in\s+dyeing|for\s+dyeing|dyers?|"
            r"colouring\s+matter|coloring\s+matter|red\s+dye|yellow\s+dye|blue\s+dye|black\s+dye|"
            r"scarlet\s+dye|crimson\s+dye|purple\s+dye|tinctorial|pigment|mordant|lake\s+colour|calico[\s-]*print)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(sappan|sapan|brazil[\s-]*wood|brazilwood|camwood|barwood|sanders[\s-]*wood|red\s+sanders|"
            r"alkanet|archil|orchil|orseille|cudbear|litmus|quercitron|weld\b|munjeet|manjit|kamala|"
            r"lac[\s-]*dye|safflower|woad|fustic|young\s+fustic|peachwood|nicaragua\s+wood|lima\s+wood|"
            r"pernambuco|kermes|vermilion|cinnabar|orpiment|realgar|gamboge|ochre|umber|sienna|bistre|"
            r"sepia|carmine|carthamine|alizarin|garancine|chay[\s-]*root|morinda|aal\b|turmeric|annatto|"
            r"persian\s+berries|avignon\s+berries|yellow\s+berries|buckthorn|rhamnus|lo[\s-]*kao|chinese\s+green|"
            r"picric|magenta|fuchsine|mauve|rosaniline|prussian\s+blue|cobalt\s+blue|smalt|zaf+re)\b",
            re.I,
        ),
    },
    "htc:0220": {
        "label": "Gum, Resin & Elastic-Gum Unenumerated",
        "group": "htc:grp_gums_resins_naval_stores",
        "rows": 165,
        "def_re": re.compile(
            r"\b(gum[\s-]*resin|oleo[\s-]*resin|natural\s+gum|varnish\s+resin|exudation|exudes?\s+from|"
            r"resinous\s+substance|milky\s+juice|elastic\s+gum|inspissated\s+juice|copal|dammar|kauri|"
            r"used\s+in\s+varnish|making\s+varnish|lacquer|caoutchouc[\s-]*like|gutta)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(copal|dammar|dammer|kauri|cowrie\s+gum|animi|anime|elemi|sandarach|sandarac|mastic|"
            r"mastich|olibanum|frankincense|benzoin|benjamin|myrrh|bdellium|galbanum|ammoniacum|"
            r"opopanax|sagapenum|tragacanth|gum\s+senegal|gum\s+gedda|gum\s+geddah|gum\s+suakin|"
            r"gum\s+kino|dragon.?s\s+blood|balata|jelutong|pontianak|chicle|accroides|grass[\s-]*tree\s+gum|"
            r"acacia\s+gum|gamboge|euphorbium|labdanum|ladanum|tacmahac|tacamahaca|caranna|chagual|"
            r"seed[\s-]*lac|stick[\s-]*lac|button[\s-]*lac|piney\s+varnish|black\s+dammar|white\s+dammar)\b",
            re.I,
        ),
    },
    "htc:0124": {
        "label": "Oil & Essential Oil Unenumerated",
        "also_ids": ["htc:0186"],
        "group": "htc:grp_vegetable_oils",
        "rows": 445,  # 259 + 186
        "def_re": re.compile(
            r"\b(essential\s+oil|volatile\s+oil|fixed\s+oil|expressed\s+oil|fatty\s+oil|vegetable\s+oil|"
            r"vegetable\s+tallow|vegetable\s+butter|perfumed\s+oil|distilled\s+oil|lamp\s+oil|soap[\s-]*making\s+oil|"
            r"yields?\s+(?:an?\s+)?(?:valuable\s+|useful\s+|clear\s+|yellow\s+)?oil|oil\s+expressed\s+from|oil\s+distilled\s+from)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(citronella|lemongrass|lemon[\s-]*grass|cajeput|cajuput|bergamot|neroli|petitgrain|"
            r"otto\s+of\s+roses|attar\s+of\s+roses|sandalwood\s+oil|eucalyptus\s+oil|peppermint\s+oil|"
            r"spearmint|wintergreen|gaultheria|clove\s+oil|cinnamon\s+oil|cassia\s+oil|anise\s+oil|"
            r"star[\s-]*anise|fennel\s+oil|caraway\s+oil|lavender\s+oil|rosemary\s+oil|thyme\s+oil|"
            r"geranium\s+oil|palmarosa|rusa\s+oil|vetiver|cuscus|ylang|patchouli\s+oil|sassafras\s+oil|"
            r"gingelly|sesame\s+oil|til\s+oil|ground[\s-]*nut\s+oil|arachis\s+oil|peanut\s+oil|"
            r"niger[\s-]*seed\s+oil|mahua|mowra|bassia|illipe|shea\s+butter|galam\s+butter|kokum\s+butter|"
            r"tung\s+oil|wood\s+oil|gurjun|candlenut|kukui|ben\s+oil|moringa|colza|cameline|gold[\s-]*of[\s-]*pleasure|"
            r"poppy[\s-]*seed\s+oil|sunflower\s+oil|safflower\s+oil|croton\s+oil|chaulmoogra\s+oil|"
            r"neem\s+oil|margosa|pongam|karanj|macassar\s+oil|carapa|crab[\s-]*oil|andiroba|touloucouna|"
            r"menhaden|dugong\s+oil|porpoise\s+oil|neat.?s[\s-]*foot)\b",
            re.I,
        ),
    },
    "htc:0012": {
        "label": "Seeds, Nuts & Kernels for Oil Unenumerated",
        "also_ids": ["htc:0223"],
        "group": "htc:grp_oilseeds",
        "rows": 1120,  # 956 + 164
        "def_re": re.compile(
            r"\b(oil[\s-]*seed|oilseed|oleaginous\s+seed|oleaginous\s+nut|seeds?\s+(?:yield|contain|produce|afford)\s+(?:an?\s+)?oil|"
            r"kernels?\s+(?:yield|contain|produce)\s+(?:an?\s+)?oil|for\s+expressing\s+oil|crushed\s+for\s+oil|"
            r"aromatic\s+seed|carminative\s+seed|spice\s+seed|bird[\s-]*seed)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(sesame|sesamum|gingelly|til\s+seed|teel\s+seed|benne|ground[\s-]*nut|earth[\s-]*nut|"
            r"arachis|monkey[\s-]*nut|palm\s+kernel|copra|copperah|castor\s+bean|castor\s+seed|ricinus|"
            r"niger\s+seed|guizotia|ramtil|poppy\s+seed|mowra|mahua|illipe|shea\s+nut|dika\s+nut|"
            r"candlenut|aleurites|physic\s+nut|jatropha|croton\s+seed|coriander|cumin|cummin|fenugreek|"
            r"fennel|aniseed|dill\s+seed|ajowan|ajwain|cardamom|grains\s+of\s+paradise|melegueta|"
            r"canary\s+seed|millet|sainfoin|lucerne|alfalfa|dodder|cameline|madia|sunflower\s+seed|"
            r"safflower\s+seed|soya|soy\s+bean|tonka\s+bean|tonquin\s+bean|calabar\s+bean|st\.\s*ignatius|"
            r"coquilla|corozo|ivory\s+nut|vegetable\s+ivory|marking\s+nut|cashew|pistachio|brazil\s+nut|"
            r"sapucaia|souari|butter[\s-]*nut|pecan|betel[\s-]*nut|areca\s+nut|kola\s+nut)\b",
            re.I,
        ),
    },
    "htc:0070": {
        "label": "Wood & Cabinet Timber Unenumerated",
        "group": "htc:grp_hewn_round_timber",
        "rows": 417,
        "def_re": re.compile(
            r"\b(cabinet[\s-]*wood|cabinet[\s-]*making|furniture\s+wood|fancy\s+wood|hard[\s-]*wood|hardwood|"
            r"ship[\s-]*building\s+timber|valuable\s+timber|durable\s+timber|ornamental\s+wood|turnery|"
            r"veneer(?:s|ing)?|wood\s+is\s+(?:very\s+)?(?:hard|heavy|durable|close[\s-]*grained|fragrant))\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(greenheart|jarrah|karri|blue\s+gum|ironbark|red\s+gum|satinwood|lancewood|sandalwood|"
            r"padauk|padouk|ironwood|cocus[\s-]*wood|cocuswood|snakewood|letterwood|tulipwood|kingwood|"
            r"zebra[\s-]*wood|zebrawood|violet[\s-]*wood|purpleheart|amaranth\s+wood|sabicu|mora\s+wood|"
            r"bullet[\s-]*wood|balata\s+wood|sal\s+wood|deodar|toon\s+wood|sissoo|blackwood|calamander|"
            r"coromandel\s+wood|amboyna|thuya|partridge[\s-]*wood|beefwood|camphor[\s-]*wood|pencil\s+cedar|"
            r"huon\s+pine|kauri\s+pine|totara|rimu|puriri|blackbutt|tallowwood|turpentine\s+tree|"
            r"mahoe|manchineel|fiddlewood|crabwood|wallaba|locust\s+wood|courbaril|quebracho|"
            r"persimmon\s+wood|dogwood|hornbeam|yew\b|holly\s+wood|pearwood|applewood|olive[\s-]*wood|"
            r"brier[\s-]*root|briar[\s-]*root)\b",
            re.I,
        ),
    },
    "htc:0041": {
        "label": "Tanning Barks & Extracts Unenumerated",
        "group": "htc:grp_vegetable_tannins",
        "rows": 556,
        "def_re": re.compile(
            r"\b(tanning|tanners?|tan[\s-]*bark|tanbark|rich\s+in\s+tannin|contains?\s+tannin|"
            r"astringent\s+(?:bark|pod|nut|extract)|used\s+for\s+tanning|leather\s+manufacture)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(wattle\s+bark|mimosa\s+bark|mangrove\s+bark|quebracho|divi[\s-]*divi|algarobilla|"
            r"knoppern|canaigre|babool|babul|acacia\s+bark|avaram|cassia\s+auriculata|cassia\s+bark|"
            r"chestnut\s+extract|larch\s+bark|birch\s+bark|willow\s+bark|alder\s+bark|cork[\s-]*tree\s+bark|"
            r"pomegranate\s+rind|tamarisk\s+gall|pistacia\s+gall|chinese\s+gall|japanese\s+gall|"
            r"nut[\s-]*gall|oak[\s-]*gall|kino|mallet\s+bark)\b",
            re.I,
        ),
    },
    "htc:fibres_unenum": {
        "label": "Vegetable Fibres Unenumerated (incl. Hemp/Paper/Brush Fibres)",
        "also_ids": ["htc:0822"],
        "group": "htc:grp_bast_plant_fibres",
        "rows": 350,
        "def_re": re.compile(
            r"\b(textile\s+fibre|textile\s+fiber|bast\s+fibre|bast\s+fiber|cordage\s+fibre|brush[\s-]*making|"
            r"paper[\s-]*making\s+fibre|paper[\s-]*stock|strong\s+fibre|coarse\s+fibre|silky\s+fibre|"
            r"used\s+for\s+(?:ropes|cordage|matting|brushes|paper|stuffing|upholstery)|vegetable\s+hair|"
            r"silk[\s-]*cotton)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(ramie|rhea|china\s+grass|boehmeria|sunn\s+hemp|crotalaria|sisal|henequen|agave|"
            r"manila\s+hemp|abaca|musa\s+textilis|new\s+zealand\s+flax|phormium|kapok|silk[\s-]*cotton|"
            r"bombax|eriodendron|piassava|piassaba|kittool|kittul|caryota|palmyra\s+fibre|borassus|"
            r"coir|raf+ia|raffia|raphia|alfa\s+grass|esparto|bowstring\s+hemp|sansevieria|pita\s+fibre|"
            r"istle|ixtle|tampico\s+fibre|mexican\s+fibre|crin\s+vegetal|vegetable\s+horsehair|"
            r"aloe\s+fibre|pineapple\s+fibre|ananas|banana\s+fibre|plantain\s+fibre|ejoo|gomuti|"
            r"arenga|hibiscus\s+fibre|ambari|bimlipatam|kenaf|mesta|uvena|calotropis|yercum|mudar|"
            r"nettle\s+fibre|mulberry\s+bark|broussonetia|tapa|bassine|broom[\s-]*corn|rice[\s-]*root|"
            r"zacaton|loofah|luffa|teasel|teazle)\b",
            re.I,
        ),
    },
}

GEO_PATTERNS = [
    ("India", r"\b(india|indian|bengal|bombay|madras|assam|malabar|coromandel|deccan|punjab|mysore|travancore|calcutta)\b"),
    ("Ceylon", r"\b(ceylon|singhalese|sinhalese)\b"),
    ("Burma", r"\b(burma|burmah|burmese|pegu|rangoon|moulmein|tenasserim)\b"),
    ("Malaya / Straits / Borneo", r"\b(malay|malacca|singapore|penang|straits|borneo|sarawak|sumatra|java|moluccas|eastern\s+archipelago)\b"),
    ("China / East Asia", r"\b(china|chinese|canton|formosa|japan|japanese|manchuria)\b"),
    ("Peru / Bolivia / Andes", r"\b(peru|peruvian|bolivia|andes|quito|ecuador|colombia|new\s+granada)\b"),
    ("Brazil / Guiana / South America", r"\b(brazil|brazilian|para|bahia|pernambuco|guiana|demerara|surinam|venezuela|paraguay|argentin|chili|chile|south\s+america)\b"),
    ("West Indies / Central America / Mexico", r"\b(west\s+indies|jamaica|trinidad|barbados|cuba|hayti|haiti|honduras|nicaragua|mexico|mexican|yucatan|campeachy|guatemala|central\s+america)\b"),
    ("West Africa", r"\b(west\s+africa|sierra\s+leone|gold\s+coast|senegal|gambia|nigeria|lagos|gaboon|congo|angola|guinea|liberia)\b"),
    ("East & Southern Africa", r"\b(zanzibar|mozambique|madagascar|cape\s+of\s+good\s+hope|natal|south\s+africa|abyssinia|somaliland|egypt|sudan|suakin)\b"),
    ("Australasia", r"\b(australia|australian|new\s+south\s+wales|victoria|queensland|tasmania|van\s+diemen|new\s+zealand|swan\s+river)\b"),
    ("Mediterranean / Levant / Persia", r"\b(turkey|turkish|levant|smyrna|syria|persia|persian|arabia|arabian|morocco|algeria|barbary|spain|spanish|italy|italian|sicily|greece|greek|cyprus)\b"),
    ("North America", r"\b(canada|canadian|united\s+states|virginia|carolina|florida|georgia|louisiana|california|newfoundland|nova\s+scotia|north\s+america)\b"),
]

TRADE_SIGNAL_RE = re.compile(
    r"\b(import(?:ed|s|ation)?|export(?:ed|s|ation)?|commerce|commercial|trade|market|mincing\s+lane|"
    r"london|britain|british|england|english|europe|european|tons?|cwts?|lbs?\.?|manufactur|article\s+of|"
    r"extensively\s+used|largely\s+used|much\s+used|chiefly\s+used|valuable|merchandise)\b",
    re.I,
)

# Noise / non-commodity dictionary entries (laws, shipping terms, currencies, grammar, places, cross-ref stubs)
NON_COMMODITY_RE = re.compile(
    r"^(?:see\s+|a\s+coin|a\s+weight|a\s+measure|a\s+money|a\s+silver\s+coin|a\s+gold\s+coin|"
    r"the\s+duties\s+on|by\s+\d+\s+geo|an\s+act\s+|stat\.|in\s+law|in\s+commerce,\s+a\s+bill|"
    r"a\s+port|a\s+town|a\s+city|a\s+seaport|a\s+river|an\s+island|a\s+vessel|a\s+ship|"
    r"an\s+officer|a\s+tax|a\s+duty|a\s+fee|a\s+term\s+used\s+in\s+navigation)\b",
    re.I,
)


def norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def singularize(w: str) -> str:
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("ches", "shes", "xes", "zes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is", "as")):
        return w[:-1]
    return w


def main():
    # 1. Load all already-enumerated Layer-1 headings + altLabels + substance heads
    enumerated_keys = set()
    enumerated_tokens = set()
    for line in open(CONCEPTS_PATH, encoding="utf-8"):
        if not line.strip():
            continue
        c = json.loads(line)
        # Skip generic "unenumerated" / "other sorts" headings themselves
        if re.search(r"\bunenumerated\b|\bother\s+sorts\b|\bother\s+articles\b", c["skos_prefLabel"], re.I):
            continue
        for s in [c["skos_prefLabel"], c["facets"]["substance_head"]] + (c.get("skos_altLabels") or []):
            k = norm_key(s)
            if k:
                enumerated_keys.add(k)
                if " " not in k:
                    enumerated_keys.add(singularize(k))
                    enumerated_tokens.add(k)
                    enumerated_tokens.add(singularize(k))

    # 2. Load 1,190 grounded binomials
    binom_map = {}
    for line in open(BINOM_PATH, encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            if d.get("qid"):
                binom_map[d["binomial"].lower()] = d

    # 3. Group all 27,325 dictionary entries by normalized headword
    by_hw = defaultdict(list)
    for line in open(LEXICON_PATH, encoding="utf-8"):
        if not line.strip():
            continue
        d = json.loads(line)
        defn = (d.get("definition") or "").strip()
        hw = (d.get("headword") or "").strip()
        k = d.get("norm_headword") or norm_key(hw)
        if not k or len(k) < 3 or len(k) > 42 or len(defn) < 40:
            continue
        if NON_COMMODITY_RE.search(defn):
            continue
        # Skip index-like entries (mostly page numbers, e.g. Watt index fragments)
        if len(re.findall(r"\b\d{2,4}\b", defn)) >= 5 and len(defn) < 260:
            continue
        by_hw[k].append(d)

    # 4. Classify non-enumerated headwords into catch-all buckets!
    results = []
    by_bucket = defaultdict(list)

    for k, entries in sorted(by_hw.items()):
        # Skip if already enumerated directly in Layer-1 customs ledgers
        if k in enumerated_keys or (len(k.split()) == 1 and singularize(k) in enumerated_keys):
            continue
        # Skip noisy OCR fragments or sub-clause headwords starting with articles/prepositions
        if re.match(r"^(of|the|in|to|for|or|and|by|at|on|from|see|a|an)\b", k):
            continue
        # Skip pure index / section headers
        if re.search(r"\b(index|chapter|table|appendix|page|vol|edition|section)\b", k):
            continue

        works = sorted({e["source_work"] for e in entries})
        # Combine text from top entries for classification
        prio = {"simmonds_1892": 100, "watt_1908": 95, "simmonds_1854": 90, "ure_gutenberg": 85, "mcculloch_1880": 80, "mortimer_1823": 75}
        entries.sort(key=lambda x: (prio.get(x["source_work"], 50) + (25 if x.get("latin_binomials") else 0) + min(len(x["definition"]), 400) / 20), reverse=True)
        best = entries[0]
        combined_text = " ".join(e["definition"][:500] for e in entries[:4])

        # Score each catch-all bucket
        bucket_scores = {}
        for cid, cfg in CATCHALLS.items():
            sc = 0
            if cfg["hw_re"].search(k):
                sc += 50
            def_hits = cfg["def_re"].findall(combined_text)
            if def_hits:
                sc += min(35, len(def_hits) * 12)
            if sc > 0:
                bucket_scores[cid] = sc

        if not bucket_scores:
            continue

        best_bucket = max(bucket_scores.items(), key=lambda x: x[1])[0]
        bscore = bucket_scores[best_bucket]

        # Extract verified Linnaean taxa
        taxa = []
        seen_tq = set()
        for e in entries[:4]:
            for b in e.get("latin_binomials") or []:
                bg = binom_map.get(b.lower())
                if bg and bg["qid"] not in seen_tq:
                    seen_tq.add(bg["qid"])
                    taxa.append({
                        "taxon_name": bg["taxon_name"],
                        "qid": bg["qid"],
                        "col_id": bg.get("col_id", ""),
                    })

        # Trade signals & geographic origins
        trade_hits = sorted({m.group(0).lower() for m in TRADE_SIGNAL_RE.finditer(combined_text)})
        origins = [geo for geo, pat in GEO_PATTERNS if re.search(pat, combined_text, re.I)]

        # Quality gate: require EITHER curated headword match (bscore >= 50), OR multi-book corroboration + def hit,
        # OR verified Linnaean taxon + trade signal + def hit!
        has_strong_signal = (
            bscore >= 50
            or (len(works) >= 2 and bscore >= 12)
            or (len(taxa) >= 1 and len(trade_hits) >= 1 and bscore >= 12)
            or (len(trade_hits) >= 2 and bscore >= 24)
        )
        if not has_strong_signal:
            continue

        # Composite scholarly relevance score
        rank_score = (
            len(works) * 35
            + (45 if bscore >= 50 else 0)
            + min(bscore, 35)
            + (25 if taxa else 0)
            + min(len(trade_hits), 5) * 6
            + min(len(origins), 3) * 5
        )

        # Clean display headword
        disp = best["headword"].strip(" .,;:-")
        if disp.isupper():
            disp = disp.title()

        rec = {
            "candidate_id": f"htc:doc_{re.sub(r'[^a-z0-9]+', '_', k).strip('_')}",
            "headword": disp,
            "norm_headword": k,
            "subsumed_in_customs_id": best_bucket,
            "subsumed_in_customs_label": CATCHALLS[best_bucket]["label"],
            "target_commodity_group": CATCHALLS[best_bucket]["group"],
            "book_count": len(works),
            "source_works": works,
            "verified_taxa": taxa[:4],
            "origins_mentioned": origins[:5],
            "trade_signals": trade_hits[:6],
            "rank_score": rank_score,
            "definition": best["definition"][:420],
            "primary_citation": best["source_citation"],
            "primary_uri": best["source_uri"],
            "all_sources": [
                {"work": e["source_work"], "citation": e["source_citation"], "uri": e["source_uri"]}
                for e in entries[:4]
            ],
        }
        results.append(rec)
        by_bucket[best_bucket].append(rec)

    results.sort(key=lambda r: (-r["rank_score"], -r["book_count"], r["norm_headword"]))

    # Write JSONL
    with open(OUT_JSONL, "w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Write TSV
    with open(OUT_TSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow([
            "candidate_id", "headword", "subsumed_in_customs_id", "subsumed_in_customs_label",
            "target_commodity_group", "book_count", "source_works", "rank_score",
            "verified_taxa", "origins_mentioned", "primary_citation", "primary_uri", "definition",
        ])
        for r in results:
            w.writerow([
                r["candidate_id"], r["headword"], r["subsumed_in_customs_id"], r["subsumed_in_customs_label"],
                r["target_commodity_group"], r["book_count"], ";".join(r["source_works"]), r["rank_score"],
                "; ".join(f"{t['taxon_name']} ({t['qid']})" for t in r["verified_taxa"]),
                "; ".join(r["origins_mentioned"]),
                r["primary_citation"], r["primary_uri"], r["definition"][:240],
            ])

    # Write Markdown Report
    md = [
        "# Unpacking the \"Unenumerated\": Minor 19th-Century Commodities Mined from 6 Commercial Books",
        "",
        "Generated automatically by `scripts/unpack_unenumerated_from_books.py` from our 6 parsed 19th-century commercial dictionaries (**27,325 entries**, **1,190 verified Catalogue of Life / Wikidata taxa** — Simmonds 1892, Simmonds 1854, Mortimer 1823, Ure 1840, McCulloch 1880, Watt 1908), excluding commodities already enumerated in Layer-1 British & Canadian customs ledgers (`htc:0001`–`htc:2066`).",
        "",
        f"- **Total book-attested non-enumerated commodities surfaced:** **{len(results):,}**",
        f"- **Corroborated by ≥ 2 independent commercial books:** **{sum(1 for r in results if r['book_count'] >= 2):,}**",
        f"- **With verified Linnaean `oe:sourceTaxon` (Wikidata / CoL):** **{sum(1 for r in results if r['verified_taxa']):,}**",
        "",
        "## Summary by Layer-1 Catch-All Customs Category",
        "| Catch-All Customs Heading | Layer-1 Rows | Book-Attested Minor Commodities | ≥ 2 Books | Verified Taxa |",
        "|---|---:|---:|---:|---:|",
    ]
    for cid, cfg in CATCHALLS.items():
        lst = by_bucket[cid]
        md.append(
            f"| `{cid}` **{cfg['label']}** | {cfg['rows']:,} | **{len(lst):,}** | "
            f"{sum(1 for x in lst if x['book_count'] >= 2):,} | "
            f"{sum(1 for x in lst if x['verified_taxa']):,} |"
        )

    for cid, cfg in CATCHALLS.items():
        lst = sorted(by_bucket[cid], key=lambda r: (-r["rank_score"], -r["book_count"], r["norm_headword"]))
        md.extend([
            "",
            f"## {cfg['label']} (`{cid}` → `{cfg['group']}`)",
            f"Top 20 book-attested commodities absent from Layer-1 Parliamentary Papers (of {len(lst):,} surfaced):",
            "",
            "| Commodity | Books | Verified Taxon | Origins Mentioned | Primary Definition & Citation |",
            "|---|---:|---|---|---|",
        ])
        for r in lst[:20]:
            tx = ", ".join(f"*{t['taxon_name']}* (`{t['qid']}`)" for t in r["verified_taxa"][:2]) or "—"
            org = ", ".join(r["origins_mentioned"][:3]) or "—"
            defn = r["definition"][:145].replace("|", "/").replace("\n", " ")
            md.append(f"| **{r['headword']}** | {r['book_count']} | {tx} | {org} | {defn}… ([source]({r['primary_uri']})) |")

    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"=== UNENUMERATED BOOK MINING COMPLETE ===")
    print(f"Total surfaced: {len(results):,} | >=2 books: {sum(1 for r in results if r['book_count'] >= 2):,} | w/ verified taxa: {sum(1 for r in results if r['verified_taxa']):,}")
    for cid, cfg in CATCHALLS.items():
        lst = sorted(by_bucket[cid], key=lambda r: (-r["rank_score"], -r["book_count"], r["norm_headword"]))
        top5 = [f"{x['headword']} ({x['book_count']}b)" for x in lst[:8]]
        print(f"  {cid:18s} {cfg['label'][:36]:36s} -> {len(lst):4d} items | top: {', '.join(top5)}")


if __name__ == "__main__":
    main()
