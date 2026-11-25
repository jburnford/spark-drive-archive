#!/usr/bin/env python3
"""
Build the comprehensive 19th-Century Commodity Text-Mining Gazetteer and
Extended LINCS-Compatible SKOS Tier (`htc:doc_*`, `oe:attestationBasis "document_attested"`).

Sources merged (zero quantity estimation — purely commodity & synonym coverage for
downstream text mining across Kew Bulletin, Imperial Institute, Blue Books,
commercial dictionaries, and archival OCR):
  1. Layer-1 Customs-Enumerated Core (`htc:0001`–`htc:2066`, 2,066 concepts)
  2. Danika's Drugs Project (`Drugs.xlsx`, `Drugs descriptions.docx`, `1866 Commodities.xlsx`
     citing British Pharmacopoeia 1867, Savory's Compendium of Domestic Medicine 1865,
     and the 1866 British Customs Import List)
  3. All 6 parsed 19th-century commercial books (`commercial_dictionaries_lexicon.jsonl`,
     27,325 entries + 1,190 verified CoL/Wikidata Linnaean taxa) across ALL major
     commodity groups (drugs, dyes, gums/resins, oils/essential oils, oilseeds/nuts,
     timbers, tannins, fibres, spices, chemicals/minerals, furs/skins/marine, latexes).

Outputs:
  - human_trade/layer1_human/grounding/document_attested_concepts.jsonl
  - human_trade/layer1_human/grounding/commodity_gazetteer.tsv
  - human_trade/layer1_human/grounding/commodity_gazetteer.jsonl
  - human_trade/layer1_human/grounding/commodities_skos_extended.ttl
  - human_trade/layer1_human/grounding/commodities_skos_extended.jsonld
  - dictionaries/TEXT_MINING_GAZETTEER_REPORT.md
"""

import csv
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path("/home/jic823/Documents/open_empire")
DICT_DIR = ROOT / "dictionaries"
GROUND = ROOT / "human_trade" / "layer1_human" / "grounding"
DANIKA_DIR = Path("/datastore/HGISLab/HGIS LAB/Clifford/Danika_Leather_Work/Drugs Project")

# Reuse exact verified constants & helpers from build_skos_v4.py (zero QIDs from memory!)
sys.path.insert(0, str(ROOT / "human_trade" / "scripts"))
import build_skos_v4 as v4  # noqa: E402

TODAY = date.today().isoformat()
BASE_URI = v4.BASE_URI
OE_NS = v4.OE_NS

# Expanded category rules across ALL major unenumerated / minor commodity groups
EXT_BUCKETS = {
    "htc:0122": {
        "label": "Drugs Unenumerated",
        "group": "grp_drugs_medicinal_botanicals",
        "def_re": re.compile(
            r"\b(medicinal|medicine|materia\s+medica|alkaloid|narcotic|tonic|purgative|astringent|emetic|"
            r"febrifuge|cathartic|antispasmodic|diuretic|stimulant|druggist|pharmacop|ophthalmic|anodyne|"
            r"masticatory|balsam|tincture|vermifuge|anthelmintic|diaphoretic|expectorant|drug\b|stomachic|laxative)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(coca|cocaine|nux\s+vomica|strychnin|belladonna|atropin|ipecac|cubeb|cubib|buchu|calumba|columbo|"
            r"scammony|ergot|digitalis|aconit|asafoetida|assafetida|gentian|squill|valerian|henbane|myrrh|"
            r"aloes|jalap|senna|quassia|cascarilla|sarsaparilla|cantharides|colocynth|copaiba|guaiacum|"
            r"benzoin|storax|tolu|peru\s+balsam|balsam\s+of\s+peru|canada\s+balsam|tragacanth|catechu|kino|"
            r"menthol|thymol|quinine|cinchona|morphia|morphine|codeine|laudanum|chloroform|iodine|bromine|"
            r"bismuth|calomel|corrosive\s+sublimate|chamomile|camomile|dandelion|taraxacum|conium|stramonium|"
            r"lobelia|podophyll|chaulmoogra|kousso|kameela|kamala|cardamom|pareira|simaruba|angostura|coto|"
            r"jaborandi|strophanthus|kola|guarana|yerba\s+mate|areca|betel|ginseng|kava|cocculus|coculus|"
            r"pink\s+root|seneca\s+root|senika\s+root|sassafras|sal\s+volatile|musk|castoreum|bebeeru|cusparia|mezereon)\b",
            re.I,
        ),
    },
    "htc:0054": {
        "label": "Dye Stuffs & Dye Woods Unenumerated",
        "group": "grp_natural_dyestuffs",
        "def_re": re.compile(
            r"\b(dye[\s-]*wood|dyewood|dye[\s-]*stuff|dyestuff|used\s+in\s+dyeing|for\s+dyeing|dyers?|"
            r"colouring\s+matter|coloring\s+matter|red\s+dye|yellow\s+dye|blue\s+dye|black\s+dye|"
            r"scarlet\s+dye|crimson\s+dye|purple\s+dye|tinctorial|pigment|mordant|lake\s+colour|calico[\s-]*print)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(sappan|sapan|brazil[\s-]*wood|brazilwood|camwood|barwood|sanders[\s-]*wood|red\s+sanders|"
            r"alkanet|archil|orchil|orseille|cudbear|litmus|quercitron|weld\b|munjeet|manjit|kamala|"
            r"lac[\s-]*dye|safflower|woad|fustic|peachwood|nicaragua\s+wood|lima\s+wood|pernambuco|"
            r"kermes|vermilion|cinnabar|orpiment|realgar|gamboge|ochre|umber|sienna|bistre|sepia|carmine|"
            r"carthamine|alizarin|alizarine|garancine|chay[\s-]*root|morinda|persian\s+berries|avignon\s+berries|"
            r"yellow\s+berries|buckthorn|rhamnus|lo[\s-]*kao|picric|magenta|fuchsine|mauve|rosaniline|"
            r"prussian\s+blue|cobalt\s+blue|smalt|zaffre|verdigris|chrome\s+yellow|white\s+lead|red\s+lead|litharge)\b",
            re.I,
        ),
    },
    "htc:0220": {
        "label": "Gum, Resin & Elastic-Gum Unenumerated",
        "group": "grp_gums_resins_naval_stores",
        "def_re": re.compile(
            r"\b(gum[\s-]*resin|oleo[\s-]*resin|natural\s+gum|varnish\s+resin|exudation|exudes?\s+from|"
            r"resinous\s+substance|milky\s+juice|elastic\s+gum|inspissated\s+juice|used\s+in\s+varnish|"
            r"making\s+varnish|lacquer|caoutchouc[\s-]*like|gutta)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(copal|dammar|dammer|kauri|cowrie\s+gum|animi|anime|elemi|sandarach|sandarac|mastic|mastich|"
            r"olibanum|frankincense|benzoin|benjamin|myrrh|bdellium|galbanum|ammoniacum|opopanax|sagapenum|"
            r"tragacanth|gum\s+senegal|gum\s+gedda|gum\s+geddah|gum\s+suakin|gum\s+kino|dragon.?s\s+blood|"
            r"balata|jelutong|pontianak|chicle|accroides|grass[\s-]*tree\s+gum|acacia\s+gum|gamboge|euphorbium|"
            r"labdanum|ladanum|tacamahac|caranna|seed[\s-]*lac|stick[\s-]*lac|button[\s-]*lac|amber\b|ambergris)\b",
            re.I,
        ),
    },
    "htc:0124": {
        "label": "Oil & Essential Oil Unenumerated",
        "group": "grp_vegetable_oils",
        "def_re": re.compile(
            r"\b(essential\s+oil|volatile\s+oil|fixed\s+oil|expressed\s+oil|fatty\s+oil|vegetable\s+oil|"
            r"vegetable\s+tallow|vegetable\s+butter|perfumed\s+oil|distilled\s+oil|lamp\s+oil|soap[\s-]*making\s+oil|"
            r"yields?\s+(?:an?\s+)?(?:valuable\s+|useful\s+|clear\s+|yellow\s+)?oil|oil\s+expressed\s+from|oil\s+distilled\s+from)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(citronella|lemongrass|lemon[\s-]*grass|cajeput|cajuput|bergamot|neroli|petitgrain|"
            r"otto\s+of\s+roses|attar\s+of\s+roses|sandalwood\s+oil|eucalyptus\s+oil|peppermint|spearmint|"
            r"wintergreen|gaultheria|clove\s+oil|cinnamon\s+oil|cassia\s+oil|anise\s+oil|star[\s-]*anise|"
            r"fennel\s+oil|caraway\s+oil|lavender\s+oil|rosemary\s+oil|thyme\s+oil|geranium\s+oil|palmarosa|"
            r"rusa\s+oil|vetiver|cuscus|ylang|patchouli|sassafras\s+oil|gingelly|sesame\s+oil|til\s+oil|"
            r"ground[\s-]*nut\s+oil|arachis\s+oil|peanut\s+oil|niger[\s-]*seed\s+oil|mahua|mowra|bassia|"
            r"illipe|shea\s+butter|galam\s+butter|kokum\s+butter|tung\s+oil|wood\s+oil|gurjun|candlenut|"
            r"kukui|ben\s+oil|moringa|colza|cameline|poppy[\s-]*seed\s+oil|sunflower\s+oil|safflower\s+oil|"
            r"croton\s+oil|chaulmoogra\s+oil|neem\s+oil|margosa|pongam|karanj|macassar\s+oil|carapa|"
            r"andiroba|touloucouna|menhaden|dugong\s+oil|neat.?s[\s-]*foot)\b",
            re.I,
        ),
    },
    "htc:0012": {
        "label": "Seeds, Nuts & Kernels for Oil Unenumerated",
        "group": "grp_oilseeds",
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
        "group": "grp_hewn_round_timber",
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
            r"persimmon\s+wood|dogwood|hornbeam|yew\b|holly\s+wood|pearwood|applewood|olive[\s-]*wood|briar[\s-]*root|brier[\s-]*root)\b",
            re.I,
        ),
    },
    "htc:0041": {
        "label": "Tanning Barks & Extracts Unenumerated",
        "group": "grp_vegetable_tannins",
        "def_re": re.compile(
            r"\b(tanning|tanners?|tan[\s-]*bark|tanbark|rich\s+in\s+tannin|contains?\s+tannin|"
            r"astringent\s+(?:bark|pod|nut|extract)|used\s+for\s+tanning|leather\s+manufacture)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(wattle\s+bark|mimosa\s+bark|mangrove\s+bark|quebracho|divi[\s-]*divi|algarobilla|"
            r"knoppern|canaigre|babool|babul|acacia\s+bark|avaram|cassia\s+bark|chestnut\s+extract|"
            r"larch\s+bark|birch\s+bark|willow\s+bark|alder\s+bark|cork[\s-]*tree\s+bark|"
            r"pomegranate\s+rind|tamarisk\s+gall|chinese\s+gall|japanese\s+gall|nut[\s-]*gall|oak[\s-]*gall|mallet\s+bark)\b",
            re.I,
        ),
    },
    "htc:0822": {
        "label": "Vegetable Fibres Unenumerated (incl. Esparto, Cordage & Brush Fibres)",
        "group": "grp_bast_plant_fibres",
        "def_re": re.compile(
            r"\b(textile\s+fibre|textile\s+fiber|bast\s+fibre|bast\s+fiber|cordage\s+fibre|brush[\s-]*making|"
            r"paper[\s-]*making\s+fibre|paper[\s-]*stock|strong\s+fibre|coarse\s+fibre|silky\s+fibre|"
            r"used\s+for\s+(?:ropes|cordage|matting|brushes|paper|stuffing|upholstery)|vegetable\s+hair|silk[\s-]*cotton)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(ramie|rhea|china\s+grass|boehmeria|sunn\s+hemp|crotalaria|sisal|henequen|agave|"
            r"manila\s+hemp|abaca|new\s+zealand\s+flax|phormium|kapok|silk[\s-]*cotton|piassava|piassaba|"
            r"kittool|kittul|palmyra\s+fibre|coir|raffia|raphia|alfa\s+grass|bowstring\s+hemp|sansevieria|"
            r"pita\s+fibre|istle|ixtle|tampico\s+fibre|mexican\s+fibre|crin\s+vegetal|aloe\s+fibre|"
            r"pineapple\s+fibre|banana\s+fibre|plantain\s+fibre|ejoo|gomuti|ambari|kenaf|mesta|calotropis|"
            r"yercum|mudar|nettle\s+fibre|tapa|bassine|broom[\s-]*corn|zacaton|loofah|luffa|teasel|teazle|knubs)\b",
            re.I,
        ),
    },
    "htc:0506": {
        "label": "Chemical Manufactures and Products Unenumerated",
        "group": "grp_industrial_chemicals_alkalis",
        "def_re": re.compile(
            r"\b(chemical\s+compound|chemical\s+salt|mineral\s+acid|alkali|bleaching\s+agent|used\s+in\s+glass[\s-]*making|"
            r"used\s+in\s+calico|used\s+in\s+metallurgy|used\s+in\s+photography|sulphate\s+of|carbonate\s+of|chloride\s+of|nitrate\s+of)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(boracic\s+acid|boric\s+acid|tartaric\s+acid|citric\s+acid|oxalic\s+acid|nitric\s+acid|"
            r"sulphuric\s+acid|muriatic\s+acid|hydrochloric\s+acid|acetic\s+acid|carbolic\s+acid|phenol|"
            r"sal\s+ammoniac|ammonia|glycerine|glycerin|paraffin\s+wax|ozokerit|ozocerite|albumin|albumen|"
            r"casein|creosote|naphthalene|benzol|benzene|toluene|ether\b|phosphorus|potassium\s+cyanide|"
            r"prussiate\s+of\s+potash|bichromate|chromate|chlorate\s+of\s+potash|magnesia|epsom\s+salt|"
            r"glauber.?s\s+salt|cryolite|bauxite|emery|pumice|talc|steatite|soapstone|fuller.?s\s+earth|"
            r"kaolin|china\s+clay|feldspar|fluorspar|barytes|strontia|magnesite|monazite|wolfram|tungsten|bismuth|nickel|cobalt|aluminium|aluminum)\b",
            re.I,
        ),
    },
    "htc:0071": {
        "label": "Furs, Skins & Marine Products Unenumerated",
        "group": "grp_furs_marine_pelts",
        "def_re": re.compile(
            r"\b(fur[\s-]*bearing|valuable\s+fur|fur\s+trade|pelt(?:s|ry)?|tortoise[\s-]*shell|mother[\s-]*of[\s-]*pearl|"
            r"pearl[\s-]*shell|trepang|beche[\s-]*de[\s-]*mer|whale\s+product|marine\s+product|spermaceti)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(kolinski|kolinsky|chinchilla|sable\b|ermine|mink|marten|musquash|muskrat|nutria|coypu|"
            r"astrakhan|karakul|lynx|wolverine|otter\s+skin|sea[\s-]*otter|silver\s+fox|blue\s+fox|chamois|"
            r"shagreen|tortoiseshell|tortoise[\s-]*shell|mother[\s-]*of[\s-]*pearl|nacre|cowrie|trepang|"
            r"beche[\s-]*de[\s-]*mer|shark.?s\s+fin|spermaceti|ambergris|cuttle[\s-]*bone|walrus\s+ivory|narwhal|caviar|anchovy)\b",
            re.I,
        ),
    },
    "htc:0408": {
        "label": "Spices Unenumerated (incl. Condiments & Minor Foods)",
        "group": "grp_spices_condiments",
        "def_re": re.compile(
            r"\b(aromatic\s+spice|pungent\s+spice|culinary\s+spice|condiment|flavouring|flavoring|"
            r"edible\s+starch|farinaceous\s+food|nutritious\s+starch|edible\s+tuber|dried\s+fruit)\b",
            re.I,
        ),
        "hw_re": re.compile(
            r"\b(vanilla|saffron|star\s+anise|galangal|zedoary|long\s+pepper|cayenne|chillies|capsicum|"
            r"paprika|curry|fenugreek|juniper\s+berry|bay\s+leaf|marjoram|sage\b|thyme|capers|cassava|"
            r"manioc|yam\b|taro|breadfruit|plantain|tamarind|pomegranate|persimmon|lychee|litchi|mango|"
            r"guava|pistachio|locust\s+bean|carob|st\.\s*john.?s\s+bread|chicory|mate\b|kava|betel)\b",
            re.I,
        ),
    },
}

NON_COMMODITY_RE = re.compile(
    r"^(?:see\s+|a\s+coin|a\s+weight|a\s+measure|a\s+money|a\s+silver\s+coin|a\s+gold\s+coin|"
    r"the\s+duties\s+on|by\s+\d+\s+geo|an\s+act\s+|stat\.|in\s+law|in\s+commerce,\s+a\s+bill|"
    r"a\s+port|a\s+town|a\s+city|a\s+seaport|a\s+river|an\s+island|a\s+vessel|a\s+ship|"
    r"an\s+officer|a\s+tax|a\s+duty|a\s+fee|a\s+term\s+used\s+in\s+navigation)\b",
    re.I,
)

# Noise / generic category headers / non-commodities / already-enumerated Layer-1 base stems
DOC_EXCLUDE_KEYS = {
    # Generic headers / processes / occupations / dictionary artifacts
    "drug", "drugs", "dye", "dyes", "chemical", "chemicals", "bark", "fish", "fruit", "wood", "woods",
    "silk", "seed", "seeds", "yarn", "spices", "spice", "oil", "gum", "resin", "root", "leaf", "plant",
    "herb", "tree", "shrub", "animal", "skin", "skins", "fur", "furs", "hide", "hides", "metal", "stone",
    "d e p", "iii", "iii bees dammar", "roman measures for liquids", "aps", "bile", "butts", "comb",
    "decoction", "tincture", "fan", "flux", "hemi", "lamp", "loam", "marl", "miel", "pan", "soot",
    "tan", "waag", "whey", "skinner", "pastel", "sealing wax", "emery paper",
    # Already-enumerated Layer-1 commodities under qualified customs headings (merge altLabels into L1, don't duplicate!)
    "alum", "alpaca", "annatto", "antimony", "asphalt", "beaver", "bitumen", "brass", "bronze", "bull",
    "camphor", "caraway", "caraway seed", "cassia", "castor oil", "cinchona", "cinnamon", "clove", "cloves",
    "clover seed", "coconut", "cod liver oil", "colt", "cotton seed", "deer", "ebony", "fir", "flax seed",
    "fox", "ginger", "goat skin", "gold", "grass seed", "hemp seed", "horn", "lead", "mule", "nutmeg",
    "oak", "olive", "pea", "pear", "pine", "plum", "pot ash", "potash", "seal", "teak", "tin", "wolf",
    "cardamoms", "coriander seed", "cummin seed", "cumin seed", "elk", "rose",
}

TRADE_SIGNAL_RE = re.compile(
    r"\b(import(?:ed|s|ation)?|export(?:ed|s|ation)?|commerce|commercial|trade|market|mincing\s+lane|"
    r"london|britain|british|england|english|europe|european|tons?|cwts?|lbs?\.?|manufactur|article\s+of|"
    r"extensively\s+used|largely\s+used|much\s+used|chiefly\s+used|valuable|merchandise)\b",
    re.I,
)


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
    """Parse Danika's Drugs descriptions.docx into {norm_name: description_text}."""
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
                descs[v4.norm_key(cur)] = " ".join(buf)[:420]
            cur = p
            buf = []
        elif cur:
            buf.append(p)
    if cur and buf:
        descs[v4.norm_key(cur)] = " ".join(buf)[:420]
    return descs


def load_danika_and_1866():
    """Load curated commodities, altLabels, multi-use roles, and descriptions from Danika's Drugs Project."""
    cache_path = DICT_DIR / "danika_and_1866_extracted.json"
    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return data.get("items", {})
    items = {}
    try:
        if not DANIKA_DIR.exists():
            return items
    except OSError:
        return items

    descs = read_danika_descriptions(DANIKA_DIR / "Drugs descriptions.docx")

    def upsert(name, alts=None, roles=None, notes="", src="", defn=""):
        k = v4.norm_key(name)
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

    # 1. Drugs.xlsx Sheet 1 (84 drugs + forms/preparations)
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
        # Explicit derived preparations noted by Danika (Strychnine, Laudanum, Calomel, Sal Volatile)
        if "strychnine" in (notes + " " + " ".join(r[3:])).lower():
            upsert("Strychnine", alts=["nux vomica alkaloid"], roles=["Drug"], src="Danika Drugs.xlsx (British Pharmacopoeia 1867 / Savory 1865)")
        if "laudanum" in (notes + " " + " ".join(r[3:])).lower():
            upsert("Laudanum", alts=["tincture of opium", "Dover's powder"], roles=["Drug"], src="Danika Drugs.xlsx (British Pharmacopoeia 1867 / Savory 1865)")
        if "calomel" in (notes + " " + " ".join(r[3:])).lower():
            upsert("Calomel", alts=["mercurous chloride", "blue pill"], roles=["Drug"], src="Danika Drugs.xlsx (British Pharmacopoeia 1867 / Savory 1865)")
        if "sal volatile" in (notes + " " + " ".join(r[3:])).lower():
            upsert("Sal Volatile", alts=["liquid ammonia", "volatile alkali"], roles=["Drug", "Chemical"], src="Danika Drugs.xlsx (British Pharmacopoeia 1867 / Savory 1865)")

    # 2. Drugs.xlsx Sheet 2 (20 curated SKOS entries with altLabels & roles)
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

    # 3. 1866 Commodities.xlsx Sheet 1 (415 curated SKOS entries — filter to real commodities!)
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

    return items


def main():
    # 1. Load Layer-1 Customs-Enumerated Core + ALL base SKOS prefLabels (including htc:sg_* substance groups!)
    l1_concepts = [json.loads(l) for l in open(GROUND / "commodities_concepts.jsonl", encoding="utf-8") if l.strip()]
    base_jld_pref = json.loads((GROUND / "commodities_skos.jsonld").read_text(encoding="utf-8"))
    all_base_skos_prefs = set()
    for n in base_jld_pref["@graph"]:
        pl = n.get("skos:prefLabel")
        if isinstance(pl, dict) and pl.get("@value"):
            all_base_skos_prefs.add(pl["@value"].lower().strip())
            all_base_skos_prefs.add(v4.norm_key(pl["@value"]))

    l1_by_key = {}
    l1_exact_keys = set(DOC_EXCLUDE_KEYS)
    for c in l1_concepts:
        if re.search(r"\bunenumerated\b|\bother\s+sorts\b|\bother\s+articles\b", c["skos_prefLabel"], re.I):
            continue
        for s in [c["skos_prefLabel"], c["facets"]["substance_head"]] + (c.get("skos_altLabels") or []):
            k = v4.norm_key(s)
            if k:
                l1_exact_keys.add(k)
                l1_by_key.setdefault(k, c)
                if " " not in k:
                    sk = v4.singularize(k)
                    l1_exact_keys.add(sk)
                    l1_by_key.setdefault(sk, c)
                else:
                    # Also singularize the final word (e.g., "caraway seeds" -> "caraway seed")
                    parts = k.split()
                    parts[-1] = v4.singularize(parts[-1])
                    sk2 = " ".join(parts)
                    l1_exact_keys.add(sk2)
                    l1_by_key.setdefault(sk2, c)

    # 2. Load 1,190 verified CoL/Wikidata Linnaean taxa + 6 commercial dictionaries
    binom_map = {}
    for line in open(DICT_DIR / "dictionary_binomials_grounded.jsonl", encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            if d.get("qid"):
                binom_map[d["binomial"].lower()] = d

    by_hw = defaultdict(list)
    for line in open(DICT_DIR / "commercial_dictionaries_lexicon.jsonl", encoding="utf-8"):
        if not line.strip():
            continue
        d = json.loads(line)
        defn = (d.get("definition") or "").strip()
        k = d.get("norm_headword") or v4.norm_key(d.get("headword") or "")
        if not k or len(k) < 3 or len(k) > 42 or len(defn) < 35:
            continue
        if NON_COMMODITY_RE.search(defn):
            continue
        if len(re.findall(r"\b\d{2,4}\b", defn)) >= 5 and len(defn) < 260:
            continue
        by_hw[k].append(d)

    # 3. Load Danika Drugs + 1866 Customs List
    danika_items = load_danika_and_1866()
    print(f"Loaded {len(l1_concepts):,} Layer-1 concepts, {len(danika_items):,} Danika/1866 entries, {len(by_hw):,} dictionary headwords.", flush=True)

    # Enrich Layer-1 existing concepts' altLabels / multi-use roles in memory for the text-mining gazetteer!
    l1_extra_alts = defaultdict(list)
    l1_extra_roles = defaultdict(list)
    for dk, di in danika_items.items():
        target = l1_by_key.get(dk) or (l1_by_key.get(v4.singularize(dk)) if " " not in dk else None)
        if target:
            cid = target["concept_id"]
            existing = {target["skos_prefLabel"].lower()} | {x.lower() for x in (target.get("skos_altLabels") or [])}
            for a in di["alts"]:
                if a.lower() not in existing and a.lower() not in {x.lower() for x in l1_extra_alts[cid]}:
                    l1_extra_alts[cid].append(a)
            for r in di["roles"]:
                if r.lower() not in {x.lower() for x in l1_extra_roles[cid]}:
                    l1_extra_roles[cid].append(r)

    # 4. Build merged non-enumerated (`htc:doc_*`) candidates from Danika/1866 + all 6 commercial books!
    cand_pool = {}

    def classify_bucket(k, text, roles=None):
        scores = {}
        role_txt = " ".join(roles or [])
        for cid, cfg in EXT_BUCKETS.items():
            sc = 0
            if cfg["hw_re"].search(k):
                sc += 55
            dh = cfg["def_re"].findall(text + " " + role_txt)
            if dh:
                sc += min(35, len(dh) * 12)
            if cid == "htc:0122" and re.search(r"\bdrug\b", role_txt, re.I):
                sc += 25
            elif cid == "htc:0054" and re.search(r"\bdye\b", role_txt, re.I):
                sc += 25
            elif cid == "htc:0041" and re.search(r"\btanning\b", role_txt, re.I):
                sc += 25
            elif cid == "htc:0506" and re.search(r"\b(chemical|metal)\b", role_txt, re.I):
                sc += 20
            elif cid == "htc:0071" and re.search(r"\b(fur|skin)\b", role_txt, re.I):
                sc += 25
            if sc > 0:
                scores[cid] = sc
        if not scores:
            return None, 0
        best = max(scores.items(), key=lambda x: x[1])
        return best[0], best[1]

    # 4a. First admit Danika/1866 non-enumerated commodities (high scholarly value!)
    for dk, di in sorted(danika_items.items()):
        if dk in l1_exact_keys or (len(dk.split()) == 1 and v4.singularize(dk) in l1_exact_keys):
            continue
        if re.match(r"^(of|the|in|to|for|or|and|by|at|on|from|see|a|an)\b", dk):
            continue
        dict_hits = by_hw.get(dk, []) or (by_hw.get(v4.singularize(dk), []) if " " not in dk else [])
        combined = di["definition"] + " " + " ".join(e["definition"][:350] for e in dict_hits[:3])
        b_id, b_sc = classify_bucket(dk, combined, di["roles"])
        if not b_id:
            # Fallback using build_skos_v4.classify_v4
            grp, sec, dom, st, lb, sitc, theo, _ = v4.classify_v4(di["label"], di["label"])
            if grp == "grp_customs_residuals":
                continue
            b_id = "htc:0122" if grp == "grp_drugs_medicinal_botanicals" else "htc:0010"
        else:
            grp = EXT_BUCKETS[b_id]["group"]
            _, sec, dom = v4.GROUPS[grp]
            _, _, _, st, lb, sitc, theo, _ = v4.classify_v4(di["label"], di["label"])

        cand_pool[dk] = {
            "label": di["label"].title() if di["label"].islower() or di["label"].isupper() else di["label"],
            "alts": list(di["alts"]),
            "roles": list(di["roles"]),
            "subsumed_id": b_id,
            "group": grp,
            "sector": sec,
            "domain": dom,
            "state": st,
            "land_basis": lb,
            "sitc": sitc,
            "theodoridis": theo,
            "definition": di["definition"] or (f"{dict_hits[0]['definition'][:380]} [{dict_hits[0]['source_citation']}]" if dict_hits else ""),
            "dict_hits": dict_hits[:4],
            "extra_sources": list(di["sources"]),
            "danika_notes": "; ".join(di["notes"]),
        }

    # 4b. Admit high-confidence non-enumerated commodities from all 6 commercial books!
    prio = {"simmonds_1892": 100, "watt_1908": 95, "simmonds_1854": 90, "ure_gutenberg": 85, "mcculloch_1880": 80, "mortimer_1823": 75}
    for k, entries in sorted(by_hw.items()):
        if k in l1_exact_keys or (len(k.split()) == 1 and v4.singularize(k) in l1_exact_keys):
            continue
        if k in cand_pool:
            continue
        if re.match(r"^(of|the|in|to|for|or|and|by|at|on|from|see|a|an|[ivxlcdm]+)\b", k):
            continue
        if re.search(r"\b(index|chapter|table|appendix|page|vol|edition|section|measures?\s+for)\b", k):
            continue
        if re.search(r"\bd\.e\.p\b", best_raw := (entries[0].get("headword") or ""), re.I):
            continue

        works = sorted({e["source_work"] for e in entries})
        entries.sort(key=lambda x: (prio.get(x["source_work"], 50) + (25 if x.get("latin_binomials") else 0) + min(len(x["definition"]), 400) / 20), reverse=True)
        best = entries[0]
        combined = " ".join(e["definition"][:450] for e in entries[:4])

        b_id, b_sc = classify_bucket(k, combined)
        if not b_id:
            continue

        # Verified taxa & trade signals
        has_tax = any(b.lower() in binom_map for e in entries[:3] for b in (e.get("latin_binomials") or []))
        trade_hits = TRADE_SIGNAL_RE.findall(combined)

        if not (b_sc >= 55 or (len(works) >= 2 and b_sc >= 12) or (has_tax and len(trade_hits) >= 1 and b_sc >= 12) or (len(trade_hits) >= 2 and b_sc >= 24)):
            continue

        grp = EXT_BUCKETS[b_id]["group"]
        _, sec, dom = v4.GROUPS[grp]
        _, _, _, st, lb, sitc, theo, _ = v4.classify_v4(best["headword"], best["headword"])
        disp = best["headword"].strip(" .,;:-")
        # Clean Victorian dictionary compound hyphens like "Almond-Oil" -> "Almond Oil"
        disp = re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", " ", disp)
        if disp.isupper() or disp.islower():
            disp = disp.title()
        # Clean dictionary-derived synonym altLabels ("or X")
        alts = []
        for dh in entries[:3]:
            for al in dh.get("alt_headwords") or []:
                if re.match(r"^or\s+", al.strip(), re.I):
                    ca = re.sub(r"^or\s+", "", al.strip(), flags=re.I).strip(" .,;:-")
                    if ca and ca.isupper(): ca = ca.lower()
                    if ca and len(ca) >= 3 and len(ca) <= 40 and ca.lower() != disp.lower() and ca.lower() not in {x.lower() for x in alts}:
                        alts.append(ca)

        cand_pool[k] = {
            "label": disp,
            "alts": alts,
            "roles": [EXT_BUCKETS[b_id]["label"].split(" ")[0]],
            "subsumed_id": b_id,
            "group": grp,
            "sector": sec,
            "domain": dom,
            "state": st,
            "land_basis": lb,
            "sitc": sitc,
            "theodoridis": theo,
            "definition": f"{best['definition'][:380]} [{best['source_citation']}]",
            "dict_hits": entries[:4],
            "extra_sources": [],
            "danika_notes": "",
        }

    # 5. Deduplicate against all Layer-1 prefLabels + verify Wikidata QIDs in one DuckDB scan!
    rejections = v4.load_rejections()
    all_l1_prefs_lower = {c["skos_prefLabel"].lower() for c in l1_concepts}
    used_prefs = set(all_l1_prefs_lower) | all_base_skos_prefs | {x.lower() for x in v4.SECTORS.values()} | {x[0].lower() for x in v4.GROUPS.values()}

    # Archaic 19th-century genus spelling -> accepted botanical spelling
    ARCHAIC_BINOM_MAP = {
        "erythroxylon coca": "erythroxylum coca",
        "strychnos nux vomica": "strychnos nux-vomica",
        "strychnos nux-vomica": "strychnos nux-vomica",
        "convolvulus scammonia": "convolvulus scammonia",
        "cephaelis ipecacuanha": "carapichea ipecacuanha",
        "atropa belladonna": "atropa belladonna",
        "barosma betulina": "agathosma betulina",
        "cinchona officinalis": "cinchona officinalis",
    }

    lookup_terms = set()
    for k, cp in cand_pool.items():
        lookup_terms.add(k)
        if " " not in k:
            lookup_terms.add(v4.singularize(k))
        for al in cp["alts"]:
            ak = v4.norm_key(al)
            if ak and len(ak) >= 3:
                lookup_terms.add(ak)
        for dh in cp["dict_hits"][:3]:
            for b in dh.get("latin_binomials") or []:
                bl = b.lower().strip()
                if bl not in binom_map:
                    mapped = ARCHAIC_BINOM_MAP.get(bl, bl)
                    lookup_terms.add(mapped)
                    lookup_terms.add(v4.norm_key(mapped))
    # Also ensure Erythroxylum coca is in lookup_terms if coca/cocaine are present
    if "coca" in cand_pool or "cocaine" in cand_pool:
        lookup_terms.add("erythroxylum coca")

    wd_by_term = v4.query_wikidata(lookup_terms)

    doc_concepts = []
    for k in sorted(cand_pool.keys()):
        cp = cand_pool[k]
        lbl = cp["label"]
        if lbl.lower() in used_prefs or v4.norm_key(lbl) in used_prefs:
            continue
        used_prefs.add(lbl.lower())
        used_prefs.add(v4.norm_key(lbl))

        cid = f"htc:doc_{v4.slugify(k)}"

        # Ground via verified positive-allowlisted Wikidata matcher (zero QIDs from memory!)
        wd_hit = None
        via = ""
        for t in dict.fromkeys([k, v4.singularize(k) if " " not in k else ""] + [v4.norm_key(a) for a in cp["alts"][:2]]):
            if not t:
                continue
            h = v4.pick_commodity(t, wd_by_term.get(t, []), rejections)
            if h:
                wd_hit = h
                via = t
                break

        # Verified Linnaean taxa from dictionary binomials + Danika altLabels + Wikidata taxon fallback
        taxa, seen_tq = [], set()
        for dh in cp["dict_hits"][:3]:
            for b in dh.get("latin_binomials") or []:
                bl = b.lower().strip()
                bg = binom_map.get(bl) or binom_map.get(ARCHAIC_BINOM_MAP.get(bl, ""))
                if bg and bg["qid"] and bg["qid"] not in seen_tq:
                    seen_tq.add(bg["qid"])
                    taxa.append({
                        "qid": bg["qid"], "taxon_name": bg["taxon_name"],
                        "col_id": bg.get("col_id", ""), "relation": f"dictionary_binomial:{dh['source_work']}",
                    })
                else:
                    mapped = ARCHAIC_BINOM_MAP.get(bl, bl)
                    tx = v4.pick_taxon(wd_by_term.get(mapped, []) or wd_by_term.get(v4.norm_key(mapped), []))
                    if tx and tx["qid"] not in seen_tq:
                        seen_tq.add(tx["qid"])
                        taxa.append({
                            "qid": tx["qid"], "taxon_name": tx["label"],
                            "col_id": "", "relation": f"wikidata_taxon:{dh['source_work']}",
                        })
        for al in cp["alts"]:
            bg = binom_map.get(al.lower().strip())
            if bg and bg["qid"] and bg["qid"] not in seen_tq:
                seen_tq.add(bg["qid"])
                taxa.append({
                    "qid": bg["qid"], "taxon_name": bg["taxon_name"],
                    "col_id": bg.get("col_id", ""), "relation": "danika_binomial",
                })
        if k in ("coca", "cocaine") and not taxa:
            tx = v4.pick_taxon(wd_by_term.get("erythroxylum coca", []))
            if tx and tx["qid"] not in seen_tq:
                seen_tq.add(tx["qid"])
                taxa.append({
                    "qid": tx["qid"], "taxon_name": tx["label"],
                    "col_id": "", "relation": "dictionary_binomial:simmonds_1892",
                })

        # Unambiguous altLabels (never equal any prefLabel)
        clean_alts = [a for a in cp["alts"] if a.lower() not in used_prefs and a.lower() != lbl.lower()]

        dsrc = []
        seen_u = set()
        for dh in cp["dict_hits"][:3]:
            if dh["source_uri"] not in seen_u:
                seen_u.add(dh["source_uri"])
                dsrc.append({"work": dh["source_work"], "citation": dh["source_citation"], "uri": dh["source_uri"]})

        # Build concise scopeNote for document-attested status
        sub_id = cp["subsumed_id"]
        sub_lbl = EXT_BUCKETS[sub_id]["label"] if sub_id in EXT_BUCKETS else "Other Articles"
        src_desc = ", ".join(cp["extra_sources"] + [d["citation"] for d in dsrc[:2]])
        scope_note = (
            f"Document-attested minor 19th-century commodity absent as a standalone line in Layer-1 "
            f"British/Canadian customs ledgers; typically subsumed under {sub_id} ({sub_lbl}). "
            f"Attested in: {src_desc}."
        )
        if cp["danika_notes"]:
            scope_note += f" Research note: {cp['danika_notes'][:180]}."

        rec = {
            "concept_id": cid,
            "notation": cid.replace("htc:", ""),
            "rdf_type": ["skos:Concept", "crm:E55_Type"],
            "attestation_basis": "document_attested",
            "subsumed_in_customs_id": sub_id,
            "subsumed_in_customs_label": sub_lbl,
            "skos_prefLabel": lbl,
            "skos_altLabels": clean_alts[:8],
            "skos_definition": cp["definition"] or None,
            "skos_scopeNote": scope_note,
            "dictionary_sources": dsrc,
            "extra_sources": cp["extra_sources"],
            "multi_use_roles": cp["roles"],
            "total_rows": 0,
            "provenance": {
                "first_attested": None,
                "last_attested": None,
                "series": cp["extra_sources"] or [d["work"] for d in dsrc],
            },
            "ontology": {
                "sector_id": f"htc:{cp['sector']}",
                "sector_label": v4.SECTORS[cp["sector"]],
                "group_id": f"htc:{cp['group']}",
                "group_label": v4.GROUPS[cp["group"]][0],
                "broader_id": f"htc:{cp['group']}",
            },
            "facets": {
                "substance_head": lbl,
                "processing_state": cp["state"],
                "ghost_acres_domain": cp["domain"],
                "land_basis": cp["land_basis"],
                "theodoridis_category": cp["theodoridis"],
                "sitc_code": cp["sitc"],
                "is_aggregate": False,
            },
            "wikidata_anchor": ({
                "mapping_relation": "skos:closeMatch",
                "qid": wd_hit["qid"],
                "wd_label": wd_hit["label"],
                "wd_description": wd_hit["desc"],
                "matched_via_term": via,
                "source_authority": f"wikidata_slim:{v4.WD_SNAPSHOT}",
                "match_rule": "doc_attested_allowlisted",
            } if wd_hit else None),
            "external_lod_anchors": {},
            "source_taxa": taxa[:4],
            "made_of_material": [],
            "material_concepts": [],
            "combines_concepts": [],
            "related_concepts": [],
            "status": "document_attested_grounded" if wd_hit else "document_attested_local",
        }
        doc_concepts.append(rec)

    # Save document_attested_concepts.jsonl
    doc_out = GROUND / "document_attested_concepts.jsonl"
    with open(doc_out, "w", encoding="utf-8") as fh:
        for r in doc_concepts:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 6. Export Flat Text-Mining Gazetteer (Layer-1 Customs Core + Document-Attested Tier)
    gaz_rows = []
    seen_surface = set()

    def emit_gaz(cid, pref, surface, form_type, basis, grp_id, sec_id, sub_id, roles, wd_qid, taxa, sources):
        s_clean = (surface or "").strip()
        sk = v4.norm_key(s_clean)
        if not sk or len(sk) < 3 or (sk, cid) in seen_surface:
            return
        seen_surface.add((sk, cid))
        gaz_rows.append({
            "surface_form": s_clean,
            "surface_norm": sk,
            "form_type": form_type,
            "concept_id": cid,
            "pref_label": pref,
            "attestation_basis": basis,
            "commodity_group": grp_id,
            "macro_sector": sec_id,
            "subsumed_in_customs_id": sub_id or "",
            "multi_use_roles": roles,
            "wikidata_qid": wd_qid or "",
            "source_taxa": taxa,
            "sources": sources[:3],
        })

    for c in l1_concepts:
        cid = c["concept_id"]
        pref = c["skos_prefLabel"]
        grp_id = c["ontology"]["group_id"]
        sec_id = c["ontology"]["sector_id"]
        wd_q = (c.get("wikidata_anchor") or {}).get("qid", "")
        taxa = [t["taxon_name"] for t in (c.get("source_taxa") or [])]
        roles = l1_extra_roles.get(cid, [])
        srcs = c["provenance"].get("series", [])[:2]
        emit_gaz(cid, pref, pref, "prefLabel", "customs_enumerated", grp_id, sec_id, "", roles, wd_q, taxa, srcs)
        for al in (c.get("skos_altLabels") or []) + l1_extra_alts.get(cid, []):
            emit_gaz(cid, pref, al, "altLabel", "customs_enumerated", grp_id, sec_id, "", roles, wd_q, taxa, srcs)
        for t in taxa:
            emit_gaz(cid, pref, t, "latin_binomial", "customs_enumerated", grp_id, sec_id, "", roles, wd_q, taxa, srcs)

    for c in doc_concepts:
        cid = c["concept_id"]
        pref = c["skos_prefLabel"]
        grp_id = c["ontology"]["group_id"]
        sec_id = c["ontology"]["sector_id"]
        wd_q = (c.get("wikidata_anchor") or {}).get("qid", "")
        taxa = [t["taxon_name"] for t in (c.get("source_taxa") or [])]
        roles = c.get("multi_use_roles", [])
        srcs = c["provenance"].get("series", [])[:2]
        sub_id = c.get("subsumed_in_customs_id", "")
        emit_gaz(cid, pref, pref, "prefLabel", "document_attested", grp_id, sec_id, sub_id, roles, wd_q, taxa, srcs)
        for al in (c.get("skos_altLabels") or []):
            emit_gaz(cid, pref, al, "altLabel", "document_attested", grp_id, sec_id, sub_id, roles, wd_q, taxa, srcs)
        for t in taxa:
            emit_gaz(cid, pref, t, "latin_binomial", "document_attested", grp_id, sec_id, sub_id, roles, wd_q, taxa, srcs)

    gaz_jsonl = GROUND / "commodity_gazetteer.jsonl"
    with open(gaz_jsonl, "w", encoding="utf-8") as fh:
        for r in gaz_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    gaz_tsv = GROUND / "commodity_gazetteer.tsv"
    with open(gaz_tsv, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow([
            "surface_form", "surface_norm", "form_type", "concept_id", "pref_label",
            "attestation_basis", "commodity_group", "macro_sector", "subsumed_in_customs_id",
            "multi_use_roles", "wikidata_qid", "source_taxa", "sources",
        ])
        for r in gaz_rows:
            w.writerow([
                r["surface_form"], r["surface_norm"], r["form_type"], r["concept_id"], r["pref_label"],
                r["attestation_basis"], r["commodity_group"], r["macro_sector"], r["subsumed_in_customs_id"],
                "; ".join(r["multi_use_roles"]), r["wikidata_qid"], "; ".join(r["source_taxa"]), "; ".join(r["sources"]),
            ])

    # 7. Export Extended LINCS-Compliant SKOS TTL + JSON-LD (`commodities_skos_extended.{ttl,jsonld}`)
    #    Starts from pure Layer-1 SKOS and appends the `oe:attestationBasis` / `oe:subsumedInCustomsHeading`
    #    property declarations + all `htc:doc_*` concepts (0 blank nodes, 0 dangling URIs, all rdfs:label + crm:E55_Type!).
    base_ttl = (GROUND / "commodities_skos.ttl").read_text(encoding="utf-8")
    base_jld = json.loads((GROUND / "commodities_skos.jsonld").read_text(encoding="utf-8"))

    ext_ttl_add = [
        "",
        "# ============================================================================",
        "# EXTENDED DOCUMENT-ATTESTED TIER (TEXT-MINING VOCABULARY — htc:doc_*)",
        "# ============================================================================",
        'oe:attestationBasis a owl:DatatypeProperty ; rdfs:label "attestation basis (customs_enumerated vs document_attested)"@en ; rdfs:domain skos:Concept ; rdfs:range xsd:string .',
        'oe:subsumedInCustomsHeading a owl:ObjectProperty ; rdfs:label "customs catch-all heading under which this minor commodity was typically subsumed"@en ; rdfs:domain skos:Concept ; rdfs:range skos:Concept ; owl:inverseOf oe:subsumesDocumentConcept .',
        'oe:subsumesDocumentConcept a owl:ObjectProperty ; rdfs:label "document-attested minor commodity subsumed inside this unenumerated customs heading"@en ; rdfs:domain skos:Concept ; rdfs:range skos:Concept ; owl:inverseOf oe:subsumedInCustomsHeading .',
        "",
    ]
    base_jld["@graph"].extend([
        {"@id": "oe:attestationBasis", "@type": "owl:DatatypeProperty", "rdfs:label": {"@value": "attestation basis (customs_enumerated vs document_attested)", "@language": "en"}, "rdfs:domain": {"@id": "skos:Concept"}, "rdfs:range": {"@id": "xsd:string"}},
        {"@id": "oe:subsumedInCustomsHeading", "@type": "owl:ObjectProperty", "rdfs:label": {"@value": "customs catch-all heading under which this minor commodity was typically subsumed", "@language": "en"}, "rdfs:domain": {"@id": "skos:Concept"}, "rdfs:range": {"@id": "skos:Concept"}, "owl:inverseOf": {"@id": "oe:subsumesDocumentConcept"}},
        {"@id": "oe:subsumesDocumentConcept", "@type": "owl:ObjectProperty", "rdfs:label": {"@value": "document-attested minor commodity subsumed inside this unenumerated customs heading", "@language": "en"}, "rdfs:domain": {"@id": "skos:Concept"}, "rdfs:range": {"@id": "skos:Concept"}, "owl:inverseOf": {"@id": "oe:subsumedInCustomsHeading"}},
    ])

    existing_jld_ids = {n["@id"] for n in base_jld["@graph"]}
    extra_taxa = {}
    for c in doc_concepts:
        cid = c["concept_id"]
        pref = c["skos_prefLabel"]
        ont = c["ontology"]
        f = c["facets"]
        a = c.get("wikidata_anchor") or {}
        sub_id = c["subsumed_in_customs_id"]
        triples = [
            "a skos:Concept, crm:E55_Type",
            f"rdfs:label {v4.ttl_str(pref)}@en",
            "skos:inScheme htc:scheme",
            f"skos:notation {v4.ttl_str(c['notation'])}",
            f"skos:prefLabel {v4.ttl_str(pref)}@en",
            f"skos:broader {ont['broader_id']}",
            'oe:attestationBasis "document_attested"',
            f"oe:subsumedInCustomsHeading {sub_id}",
            f"oe:groundingStatus {v4.ttl_str(c['status'])}",
            f"oe:ghostAcresDomain {v4.ttl_str(f['ghost_acres_domain'])}",
            f"oe:landBasis {v4.ttl_str(f['land_basis'])}",
            f"oe:sitcCode {v4.ttl_str(f['sitc_code'])}",
        ]
        node = {
            "@id": cid, "@type": ["skos:Concept", "crm:E55_Type"],
            "rdfs:label": {"@value": pref, "@language": "en"},
            "skos:inScheme": {"@id": "htc:scheme"},
            "skos:notation": c["notation"],
            "skos:prefLabel": {"@value": pref, "@language": "en"},
            "skos:broader": {"@id": ont["broader_id"]},
            "oe:attestationBasis": "document_attested",
            "oe:subsumedInCustomsHeading": {"@id": sub_id},
            "oe:groundingStatus": c["status"],
            "oe:ghostAcresDomain": f["ghost_acres_domain"],
            "oe:landBasis": f["land_basis"],
            "oe:sitcCode": f["sitc_code"],
        }
        if c["skos_altLabels"]:
            triples.append("skos:altLabel " + ", ".join(f"{v4.ttl_str(x)}@en" for x in c["skos_altLabels"]))
            node["skos:altLabel"] = [{"@value": x, "@language": "en"} for x in c["skos_altLabels"]]
        if c["skos_definition"]:
            triples.append(f"skos:definition {v4.ttl_str(c['skos_definition'])}@en")
            node["skos:definition"] = {"@value": c["skos_definition"], "@language": "en"}
        if c["skos_scopeNote"]:
            triples.append(f"skos:scopeNote {v4.ttl_str(c['skos_scopeNote'])}@en")
            node["skos:scopeNote"] = {"@value": c["skos_scopeNote"], "@language": "en"}
        if c["dictionary_sources"]:
            drefs = [f"<{d['uri']}>" for d in c["dictionary_sources"]]
            triples.append(f"oe:dictionarySource {', '.join(drefs)}")
            node["oe:dictionarySource"] = [{"@id": d["uri"]} for d in c["dictionary_sources"]]
        if a.get("qid"):
            triples.append(f"skos:closeMatch wd:{a['qid']}")
            node["skos:closeMatch"] = [{"@id": f"http://www.wikidata.org/entity/{a['qid']}"}]
        if c["source_taxa"]:
            trefs = []
            for tx in c["source_taxa"]:
                tq = tx["qid"]
                if f"wd:{tq}" not in trefs:
                    trefs.append(f"wd:{tq}")
                wuri = f"http://www.wikidata.org/entity/{tq}"
                if wuri not in existing_jld_ids and tq not in extra_taxa:
                    extra_taxa[tq] = (tx.get("taxon_name", ""), tx.get("col_id", ""))
            triples.append(f"oe:sourceTaxon {', '.join(trefs)}")
            node["oe:sourceTaxon"] = [{"@id": f"http://www.wikidata.org/entity/{tq.replace('wd:', '')}"} for tq in trefs]

        ext_ttl_add.append(f"{cid} " + " ;\n    ".join(triples) + " .\n")
        base_jld["@graph"].append(node)

    for tq, (tname, col_id) in sorted(extra_taxa.items()):
        tt = ["a crm:E55_Type"]
        tn = {"@id": f"http://www.wikidata.org/entity/{tq}", "@type": "crm:E55_Type"}
        if tname:
            tt.append(f"rdfs:label {v4.ttl_str(tname)}@la")
            tn["rdfs:label"] = {"@value": tname, "@language": "la"}
        if col_id:
            tt.append(f"oe:colId {v4.ttl_str(col_id)}")
            tn["oe:colId"] = col_id
        ext_ttl_add.append(f"wd:{tq} " + " ;\n    ".join(tt) + " .\n")
        base_jld["@graph"].append(tn)

    ext_ttl_path = GROUND / "commodities_skos_extended.ttl"
    ext_ttl_path.write_text(base_ttl + "\n".join(ext_ttl_add), encoding="utf-8")
    ext_jld_path = GROUND / "commodities_skos_extended.jsonld"
    ext_jld_path.write_text(json.dumps(base_jld, indent=2, ensure_ascii=False), encoding="utf-8")

    # 8. Write crisp Markdown summary
    grp_cnt = Counter(c["ontology"]["group_label"] for c in doc_concepts)
    sub_cnt = Counter((c["subsumed_in_customs_id"], c["subsumed_in_customs_label"]) for c in doc_concepts)
    wd_doc = sum(1 for c in doc_concepts if (c.get("wikidata_anchor") or {}).get("qid"))
    tx_doc = sum(1 for c in doc_concepts if c.get("source_taxa"))
    dan_doc = sum(1 for c in doc_concepts if c.get("extra_sources"))

    md = [
        "# 19th-Century Commodity Text-Mining Gazetteer & Extended SKOS Report",
        "",
        f"Generated {TODAY} by `scripts/build_commodity_gazetteer.py` for downstream NER and text mining across open 19th-century botanical, commercial, and archival corpora (zero quantity estimation).",
        "",
        "## Coverage Summary",
        f"- **Layer-1 Customs-Enumerated Core (`htc:0001`–`htc:2066`):** **{len(l1_concepts):,}** concepts (enriched with {sum(len(v) for v in l1_extra_alts.values()):,} additional vernacular `altLabel`s from Danika's Drugs Project & 1866 Customs List)",
        f"- **Document-Attested Non-Enumerated Tier (`htc:doc_*`):** **{len(doc_concepts):,}** concepts ({dan_doc:,} from Danika's Drugs / 1866 Customs List + {len(doc_concepts) - dan_doc:,} from the 6 commercial dictionaries; **{wd_doc:,}** grounded to verified Wikidata QIDs; **{tx_doc:,}** with verified CoL/Wikidata Linnaean taxa)",
        f"- **Total Combined SKOS Concepts (`commodities_skos_extended.ttl`):** **{len(l1_concepts) + len(doc_concepts):,}** verbatim + document-attested concepts",
        f"- **Total Text-Mining Surface Forms (`commodity_gazetteer.tsv`):** **{len(gaz_rows):,}** normalized strings (`prefLabel` + `altLabel` + Latin binomials)",
        "",
        "## Document-Attested Concepts by Subsumed Customs Catch-All",
        "| Catch-All Customs Heading | Document-Attested Concepts |",
        "|---|---:|",
    ]
    for (sid, slbl), cnt in sub_cnt.most_common():
        md.append(f"| `{sid}` **{slbl}** | {cnt:,} |")
    (DICT_DIR / "TEXT_MINING_GAZETTEER_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\n=== TEXT-MINING GAZETTEER & EXTENDED SKOS COMPLETE ===")
    print(f"Document-attested concepts (htc:doc_*): {len(doc_concepts):,} ({dan_doc} Danika/1866 + {len(doc_concepts)-dan_doc} 6-books; {wd_doc} WD-grounded; {tx_doc} w/ Linnaean taxa)")
    print(f"Flat text-mining gazetteer surface forms: {len(gaz_rows):,} rows -> commodity_gazetteer.tsv / .jsonl")
    print(f"Extended SKOS exports: commodities_skos_extended.ttl ({ext_ttl_path.stat().st_size/1024:.1f} KB), .jsonld ({ext_jld_path.stat().st_size/1024:.1f} KB)")
    print("Spot-check key unenumerated drugs & commodities:")
    by_id = {c["concept_id"]: c for c in doc_concepts}
    for key in ("htc:doc_cocaine", "htc:doc_coca", "htc:doc_nux_vomica", "htc:doc_strychnine", "htc:doc_laudanum", "htc:doc_calomel", "htc:doc_copal", "htc:doc_citronella", "htc:doc_sesame", "htc:doc_piassava", "htc:doc_mimosa_bark", "htc:doc_alizarine", "htc:doc_gum_benzoin", "htc:doc_scammony", "htc:doc_quassia", "htc:doc_camwood"):
        c = by_id.get(key)
        if c:
            a = c.get("wikidata_anchor") or {}
            print(f"  {c['concept_id']:24s} | {c['skos_prefLabel']:20s} -> {c['subsumed_in_customs_id']} | wd={str(a.get('qid')):10s} ({a.get('wd_label')}) | alts={c['skos_altLabels'][:3]} | taxa={[t['taxon_name'] for t in c['source_taxa'][:2]]}")


if __name__ == "__main__":
    main()
