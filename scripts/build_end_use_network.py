#!/usr/bin/env python3
"""
18-Industry Primary-Source End-Use Network Builder (`oe:industry_scheme`).

Models where 19th-century traded commodities went in British & Imperial manufacturing —
built strictly from primary-source evidence across ALL 6,455 full-text pages of our
6 OCR'd / Project Gutenberg 19th-century commercial & manufacturing books:
  - Andrew Ure, Dictionary of Arts, Manufactures, and Mines (PG #44562, 6.57M chars)
  - P. L. Simmonds, Commercial Products of the Vegetable Kingdom (1854, PG #15191)
  - P. L. Simmonds, Commercial Dictionary of Trade Products (1892, IA b21780535, Chandra-2 OCR)
  - George Watt, Commercial Products of India (1908, IA b31361584, Chandra-2 OCR)
  - J. R. McCulloch, Dictionary of Commerce (1880, IA dictionaryprac00mccu, Chandra-2 OCR)
  - Thomas Mortimer, General Commercial Dictionary (1823, IA generalcommercia00mort, Chandra-2 OCR)

Zero quantity estimation & zero unsourced links: every commodity -> industry edge
carries at least one verbatim 19th-century quote with clickable IA / Gutenberg URI.

Outputs:
  - human_trade/layer1_human/grounding/end_use_network_links.tsv
  - human_trade/layer1_human/grounding/end_use_network_links.jsonl
  - human_trade/layer1_human/grounding/end_use_network_skos.ttl
  - human_trade/layer1_human/grounding/end_use_network_skos.jsonld
  - dictionaries/END_USE_NETWORK_REPORT.md
"""

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path("/home/jic823/Documents/open_empire")
GROUND = ROOT / "human_trade" / "layer1_human" / "grounding"
DICT_DIR = ROOT / "dictionaries"
OCR_ROOT = Path("/mnt/data/jic823/open_empire_corpus/ocr_chandra/dictionaries_all")
GUT_ROOT = Path("/mnt/data/jic823/open_empire_corpus/raw/gutenberg")

TODAY = date.today().isoformat()
# MUST be the namespaces of the commodity vocabulary (build_skos_v4.BASE_URI / OE_NS): with any other value
# the industry graph and the commodity graph share compact ids but never join by IRI.
BASE_URI = "https://open-empire.hgislab.usask.ca/vocab/human-trade-commodities/"
OE_NS = "https://open-empire.hgislab.usask.ca/ns#"

PAGE_MARK_RE = re.compile(r"^(\d+)-{35,}\s*$", re.M)

ROLE_LABELS = {
    "primary_feedstock": "Primary Feedstock / Base Material",
    "alkali_or_reagent": "Alkali, Acid & Chemical Reagent",
    "dye_or_colorant": "Dyestuff, Dyewood & Pigment",
    "mordant_or_fixer": "Mordant & Colour Fixer",
    "tanning_or_curing": "Tanning, Tawing & Currying Agent",
    "thickener_or_sizing": "Thickener, Gum, Resin & Sizing",
    "bleaching_agent": "Bleaching & Clarifying Agent",
    "flavouring_or_scent": "Flavouring, Spice & Perfume",
    "solvent_or_fuel": "Solvent, Flux, Fuel & Lubricant",
    "filler_or_admixture": "Binder, Dairy, Fibre & Admixture",
    "preservative_or_coating": "Preservative, Coating & Caulking",
    "refractory_material": "Refractory, Crucible & Mould Material",
}

# ============================================================================
# 18 MAJOR 19TH-CENTURY BRITISH & IMPERIAL MANUFACTURING INDUSTRIES
# ============================================================================
INDUSTRIES = {
    "oe:ind_soap_manufacture": {
        "label": "Soap Manufacture",
        "sector": "Oils, Soap & Lighting",
        "description": "Hard, soft, yellow, mottled, curd, Castile, and toilet soap manufacture — combining animal tallow and tropical/vegetable oils with caustic alkalis (barilla, kelp, soda ash, potash, lime), rosin, salt for salting out, and essential oils for scenting.",
        "trigger_re": re.compile(
            r"\b(soap[\s-]*mak\w*|soap[\s-]*boil(?:er|ers|ing)|making\s+(?:hard\s+|soft\s+|yellow\s+|white\s+)?soap|"
            r"manufactur\w*\s+of\s+(?:hard\s+|soft\s+|yellow\s+|white\s+|toilet\s+)?soap|"
            r"used\s+(?:in|for)\s+(?:making\s+)?soap|employed\s+in\s+(?:making\s+)?soap|"
            r"fitted\s+for\s+(?:the\s+)?(?:manufacture\s+of\s+)?soap|useful\s+in\s+making\s+soap|"
            r"saponif\w*|hard\s+soap|soft\s+soap|yellow\s+soap|mottled\s+soap|curd\s+soap|"
            r"toilet\s+soap|castile\s+soap|marseilles?\s+soap|scent\w*\s+soap|perfum\w*\s+soap|"
            r"soap[\s-]*works|soap[\s-]*pan)\b",
            re.I,
        ),
        "neg_re": re.compile(r"\b(mordant\w*|madder\s+bath|cleared\s+with\s+a?\s*soap|calico[\s-]*print|oxymuriate\s+of\s+lime)\b", re.I),
        "ure_essays": [(r"\nSOAP\s*\(", r"\nSODA[\.,\s]")],
    },
    "oe:ind_calico_printing": {
        "label": "Calico Cloth & Calico Printing",
        "sector": "Textiles & Dyeing",
        "description": "Cotton weaving, bleaching, dyeing, and calico printing — combining raw cotton with bleaching powder and alkalis, botanical/insect/mineral/coal-tar dyestuffs, metallic mordants, and gum/starch thickeners.",
        "trigger_re": re.compile(
            r"\b(calico[\s-]*print\w*|printing\s+calico\w*|printed\s+calico\w*|cotton[\s-]*print\w*|"
            r"calico\s+cloth|calicoes|sizing\s+(?:cotton|warps?|cloth|calico)|bleaching\s+(?:cotton|calico)|"
            r"dyeing\s+(?:of\s+)?(?:\w+\s+)?(?:cotton|calico|chintz|muslin|fustian)|(?:cotton|calico)[\s-]*dyeing|"
            r"(?:dyed|steeped)\s+(?:in\s+)?(?:cotton|calico)|cotton\s+steeped\s+in\s+lac\s+dye|"
            r"dye(?:s|ing)?\s+(?:wool,?\s+silk,?\s+and\s+)?cotton|soiling\s+the\s+white\s+ground|"
            r"turkey[\s-]*red|madder[\s-]*style|steam[\s-]*colou?rs?|topical\s+(?:dye|colou?r)|"
            r"discharge\s+style|resist\s+paste|cotton\s+manufactur\w*|cotton[\s-]*dyers?|printed\s+cotton\w*)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [(r"\nCALICO-PRINTING\s*\(", r"\nCALOMEL[\.,\s]")],
    },
    "oe:ind_woollen_silk_dyeing": {
        "label": "Woollen, Silk & Worsted Dyeing",
        "sector": "Textiles & Dyeing",
        "description": "Woollen, worsted, and silk scouring, fulling, and dyeing — employing raw wool and silk with scarlet/crimson insect dyes (cochineal, lac dye, kermes), lichen dyes (orchal, archil, cudbear), indigo/woad vats, alum/tartar/tin mordants, olive oil, and fuller's earth.",
        "trigger_re": re.compile(
            r"\b(dyeing\s+(?:of\s+)?(?:wool\w*|silk\w*|scarlet\s+cloth|broadcloth|worsted)|"
            r"(?:wool\w*|silk)\s+(?:dyeing|dyers?)|(?:scouring|fulling|dressing)\s+(?:wool\w*|cloth)|"
            r"woollen\s+manufactur\w*|silk\s+manufactur\w*|silk[\s-]*dyers?|wool[\s-]*dyers?|"
            r"scarlet\s+dye\s+(?:for|on)\s+wool|dyeing\s+scarlet\s+cloth|indigo\s+vat|woad\s+vat)\b",
            re.I,
        ),
        "neg_re": re.compile(r"\bcalico[\s-]*print\b", re.I),
        "ure_essays": [(r"\nDYEING[\.,\s]\s*\(", r"\nEARTHS[\.,\s]")],
    },
    "oe:ind_chocolate_confectionery": {
        "label": "Chocolate & Confectionery",
        "sector": "Food, Drink & Groceries",
        "description": "Chocolate bars, drinking chocolate, cocoa butter, and sugar confectionery — combining roasted cacao beans with cane sugar, aromatic spices (vanilla, cinnamon, cloves, cassia), gums, almonds, starches, and milk.",
        "trigger_re": re.compile(
            r"\b(making\s+chocolate|manufactur\w*\s+of\s+chocolate|used\s+(?:in|for)\s+(?:making\s+)?chocolate|"
            r"flavour\w*\s+chocolate|flavor\w*\s+chocolate|chocolate[\s-]*mak\w*|chocolate[\s-]*paste|"
            r"chocolate\s+(?:bars?|cakes?|is\s+made|prepared|mixed|manufactured)|butter\s+of\s+cacao|cocoa[\s-]*butter|"
            r"confectioner(?:y|s)?|sweetmeats?|lozenges?|bon[\s-]*bons?|sugar[\s-]*plums?)\b",
            re.I,
        ),
        "neg_re": re.compile(r"\b(topical\s+chocolate|chocolate\s+(?:colour|color|brown|dye|shade)|acetate\s+of\s+alumina|calico[\s-]*print|mordant)\b", re.I),
        "ure_essays": [(r"\nCHOCOLATE\.", r"\nCHROMATES[\.,\s]")],
    },
    "oe:ind_leather_tanning": {
        "label": "Leather Tanning, Tawing & Currying",
        "sector": "Hides, Leather & Animal Trades",
        "description": "Tanning, tawing, and currying raw ox/calf/sheep/goat hides into sole, harness, morocco, Russia, and chamois leather — using oak, hemlock, and mimosa barks, valonia, sumach, cutch, myrabolans, divi-divi, lime, alum, salt, tallow, and fish/train oils.",
        "trigger_re": re.compile(
            r"\b(tanning|tanners?|tannery|tanneries|tan[\s-]*bark|tan[\s-]*pit|tan[\s-]*liquor|ooze\b|"
            r"currying|curriers?|tawing|tawed\s+leather|morocco\s+leather|russia\s+leather|chamois\s+leather|"
            r"leather[\s-]*dress\w*|manufactur\w*\s+of\s+leather|making\s+leather|used\s+for\s+tanning|"
            r"used\s+in\s+tanning|employed\s+in\s+tanning|unhairing\s+hides)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [(r"\nLEATHER[\.,\s]\s*\(", r"\nLEMONS[\.,\s]")],
    },
    "oe:ind_candle_manufacture": {
        "label": "Candle Manufacture",
        "sector": "Oils, Soap & Lighting",
        "description": "Dipped, mould, composite, stearine, wax, spermaceti, and paraffin candle manufacture — combining tallow, palm/coconut stearine, beeswax, spermaceti, and paraffin with cotton wicks and sulphuric acid/borax treatments.",
        "trigger_re": re.compile(
            r"\b(candle[\s-]*mak\w*|making\s+candles?|manufactur\w*\s+of\s+candles?|used\s+(?:in|for)\s+(?:making\s+)?candles?|"
            r"employed\s+in\s+(?:making\s+)?candles?|tallow\s+candles?|wax\s+candles?|spermaceti\s+candles?|"
            r"composite\s+candles?|stearine\s+candles?|stearic\s+candles?|palm[\s-]*oil\s+candles?|"
            r"paraffin\s+candles?|mould\s+candles?|dipped\s+candles?|candle[\s-]*wicks?|tallow[\s-]*chandler\w*)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [(r"\nCANDLE[\.,\s]\s*\(", r"\nCAOUTCHOUC[\.,\s]")],
    },
    "oe:ind_paper_making": {
        "label": "Paper Making & Cardboard",
        "sector": "Forestry, Paper & Print",
        "description": "Paper, pasteboard, and millboard manufacture — pulping linen/cotton rags, esparto grass, wood pulp, straw, hemp, and jute, bleached with chloride of lime, sized with rosin/alum/gelatine/starch, and loaded or tinted with kaolin, smalt, and ultramarine.",
        "trigger_re": re.compile(
            r"\b(paper[\s-]*mak\w*|making\s+paper|manufactur\w*\s+of\s+paper|paper[\s-]*mill\w*|"
            r"paper[\s-]*stock|paper[\s-]*pulp|sizing\s+paper|used\s+(?:in|for)\s+(?:making\s+)?paper|"
            r"paste[\s-]*board|mill[\s-]*board|wrapping[\s-]*paper|writing[\s-]*paper|printing[\s-]*paper)\b",
            re.I,
        ),
        "neg_re": re.compile(r"\b(paper[\s-]*hangings|sand[\s-]*paper|emery[\s-]*paper|paper[\s-]*money|bank[\s-]*note)\b", re.I),
        "ure_essays": [(r"\nPAPER[\.,\s]\s*\(", r"\nPAPIER[\.,\s]")],
    },
    "oe:ind_varnish_paint_lacquer": {
        "label": "Varnish, Paint & Lacquer",
        "sector": "Chemicals, Resins & Coatings",
        "description": "Spirit and oil varnishes, japans, lacquers, French polish, and house/marine paints — dissolving tropical resins (copal, dammar, shellac, mastic, sandarac, amber, elemi, rosin) in linseed oil, turpentine, and spirits, pigmented with white lead, vermilion, ochre, umber, ultramarine, and chrome yellow.",
        "trigger_re": re.compile(
            r"\b(varnish(?:es|ing|[\s-]*mak\w*)?|making\s+varnish|manufactur\w*\s+of\s+varnish|"
            r"lacquer(?:s|ing)?|japanning|french\s+polish|oil[\s-]*paint\w*|house[\s-]*paint\w*|"
            r"drying[\s-]*oil|painters?'?\s+colou?rs?|used\s+(?:by\s+painters|in\s+painting|in\s+varnish)|"
            r"spirit[\s-]*varnish|copal\s+varnish|oil[\s-]*varnish|asphaltum\s+varnish)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [(r"\nVARNISH[\.,\s]\s*\(", r"\nVERDIGRIS[\.,\s]")],
    },
    "oe:ind_glass_ceramics": {
        "label": "Glassmaking, Pottery & Porcelain",
        "sector": "Minerals, Metals & Heavy Industry",
        "description": "Crown, plate, bottle, and flint glassmaking plus earthenware and bone-china porcelain — fusing sand/flint and kaolin/china clay with soda ash, barilla, kelp, potash, lime, red lead/litharge, manganese, borax, cobalt/smalt, and calcined bone ash.",
        "trigger_re": re.compile(
            r"\b(glass[\s-]*mak\w*|making\s+glass|manufactur\w*\s+of\s+glass|glass[\s-]*house|glass[\s-]*works|"
            r"flint[\s-]*glass|crown[\s-]*glass|plate[\s-]*glass|bottle[\s-]*glass|stained\s+glass|"
            r"pottery|porcelain|china[\s-]*ware|earthen[\s-]*ware|stone[\s-]*ware|glaz(?:e|ing)\s+(?:pottery|porcelain|earthenware)|"
            r"enamel(?:ling|s)?\s+(?:glass|pottery|porcelain))\b",
            re.I,
        ),
        "neg_re": re.compile(r"\b(looking[\s-]*glass|hour[\s-]*glass|magnifying[\s-]*glass|wine[\s-]*glass)\b", re.I),
        "ure_essays": [
            (r"\nGLASS\s*\(", r"\nGLAUBER[\.,\s]"),
            (r"\nPOTTERY,\s*PORCELAIN", r"\nPRINTING\s+INK"),
        ],
    },
    "oe:ind_rubber_waterproofing": {
        "label": "India-Rubber, Gutta-Percha & Waterproofing",
        "sector": "Chemicals, Resins & Coatings",
        "description": "Vulcanized india-rubber goods, mackintosh waterproof fabrics, elastic webbing, and gutta-percha submarine telegraph cable insulation — combining caoutchouc and gutta-percha with sulphur, coal-tar naphtha, turpentine, white lead, zinc, and woven cotton/linen.",
        "trigger_re": re.compile(
            r"\b(vulcaniz\w*|vulcanis\w*|water[\s-]*proof(?:ing|ed)?\s+(?:cloth|fabric|garment|coat|textile|articles?)|"
            r"mackintosh\w*|india[\s-]*rubber\s+(?:manufactur\w*|goods|shoes|boots|cloth|web|tubes?|hose|belts?)|"
            r"caoutchouc\s+(?:manufactur\w*|dissolv\w*|solution|varnish|waterproof|shoes|tubes?)|"
            r"gutta[\s-]*percha|submarine\s+telegraph|telegraph\s+cable|insulat\w*\s+(?:wire|cable))\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [(r"\nCAOUTCHOUC,\s*GUM-ELASTIC", r"\nCAPERS[\.,\s]")],
    },
    "oe:ind_brewing_distilling": {
        "label": "Brewing, Malting & Distilling",
        "sector": "Food, Drink & Groceries",
        "description": "Ale, porter, stout, beer brewing, and spirits/gin/whisky/rum distilling — mashing malted barley, grains, sugar, and molasses, bittering with hops (and substitutes like quassia), fining with isinglass, and rectifying gin/cordials with juniper berries, coriander, and spices.",
        "trigger_re": re.compile(
            r"\b(brewing|brewers?|brewery|breweries|malting|maltsters?|mash[\s-]*tun|wort\b|"
            r"porter\s+and\s+stout|ale\s+and\s+beer|making\s+(?:beer|ale|porter|gin|whisky|rum|brandy)|"
            r"distill(?:ing|ers?|ery|eries|ation\s+of\s+spirits)|fining\s+(?:beer|ale|wine|malt)|"
            r"flavour\w*\s+gin|gin[\s-]*distill\w*|rectif(?:ying|iers?)\s+spirits)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [
            (r"\nBEER[\.,\s]\s*\(", r"\nBILE[\.,\s]"),
            (r"\nDISTILLATION,\s*\(", r"\nDUCTILITY[\.,\s]"),
        ],
    },
    "oe:ind_sugar_refining": {
        "label": "Sugar Refining",
        "sector": "Food, Drink & Groceries",
        "description": "Refining raw colonial muscovado and beet sugars into loaf and granulated white sugar — clarifying and decolorizing raw cane sugar with lime, bullock's blood/albumen, animal charcoal (bone black), and clay.",
        "trigger_re": re.compile(
            r"\b(sugar[\s-]*refin\w*|refining\s+(?:of\s+)?sugar|sugar[\s-]*bak\w*|sugar[\s-]*boil\w*|"
            r"sugar[\s-]*house|clarif(?:ying|ication\s+of)\s+sugar|decoloriz\w*\s+(?:sugar|syrup)|"
            r"loaf[\s-]*sugar|muscovado|vacuum[\s-]*pan|animal\s+charcoal.*sugar|sugar.*animal\s+charcoal|"
            r"bone[\s-]*black.*sugar|sugar.*bone[\s-]*black)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [(r"\nSUGAR\s*\(", r"\nSULPHUR[\.,\s]")],
    },
    "oe:ind_cordage_shipbuilding": {
        "label": "Shipbuilding, Rope, Cordage & Sailcloth",
        "sector": "Forestry, Paper & Print",
        "description": "Wooden ship construction, spars, sails, caulking, and marine cordage — combining oak, teak, greenheart, pine/fir masts, and copper sheathing with hemp, manila/abaca, coir, sisal, flax, oakum, tar, pitch, turpentine, and rosin.",
        "trigger_re": re.compile(
            r"\b(ship[\s-]*build\w*|naval\s+architecture|naval\s+stores|rope[\s-]*mak\w*|making\s+(?:ropes?|cordage|cables?)|"
            r"manufactur\w*\s+of\s+(?:cordage|ropes?|sail[\s-]*cloth)|sail[\s-]*cloth|canvas\s+for\s+sails|"
            r"caulking\s+(?:ships?|vessels?|seams)|sheathing\s+(?:ships?|vessels?)|ships?'?\s+(?:masts|spars|rigging|timbers|bottoms)|"
            r"marine\s+cordage|standing\s+rigging)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [(r"\nROPE-MAKING\.", r"\nROSE[\.,\s]")],
    },
    "oe:ind_gunpowder_matches": {
        "label": "Gunpowder, Explosives & Lucifer Matches",
        "sector": "Chemicals, Resins & Coatings",
        "description": "Black gunpowder, blasting powder, guncotton, and lucifer/congreve friction matches — compounding saltpetre (potassium/sodium nitrate), brimstone (sulphur), and willow/alder charcoal, plus phosphorus, chlorate of potash, pine splints, paraffin, and glue for matches.",
        "trigger_re": re.compile(
            r"\b(gun[\s-]*powder|powder[\s-]*mill\w*|blasting[\s-]*powder|making\s+gunpowder|manufactur\w*\s+of\s+gunpowder|"
            r"lucifer\s+match\w*|friction\s+match\w*|congreve\s+match\w*|match[\s-]*mak\w*|making\s+matches|"
            r"gun[\s-]*cotton|nitro[\s-]*glycerin\w*|pyrotechn\w*|fire[\s-]*works)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [(r"\nGUNPOWDER\.", r"\nGYPSUM[\.,\s]")],
    },
    "oe:ind_perfumery_cosmetics": {
        "label": "Perfumery, Pomades & Essential Oils",
        "sector": "Oils, Soap & Lighting",
        "description": "Eau de Cologne, scented spirits, pomades, incense, and cosmetics — infusing alcohol, lard, and olive/almond oils with essential oils (bergamot, otto of roses, lavender, citronella, sandalwood), animal fixatives (musk, ambergris, castor), and fragrant resins/spices (benzoin, myrrh, olibanum, vanilla, cloves).",
        "trigger_re": re.compile(
            r"\b(perfumer(?:y|s)?|making\s+perfumes?|used\s+(?:in|by)\s+perfumer\w*|eau\s+de\s+cologne|"
            r"pomade\w*|pommade\w*|cosmetic\w*|scent(?:ed|ing)\s+(?:waters?|oils?|powders?|pomades?)|"
            r"incense|pastilles|pot[\s-]*pourri|lavender[\s-]*water|rose[\s-]*water|toilet\s+waters?)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [],
    },
    "oe:ind_pharmaceuticals": {
        "label": "Pharmaceuticals & Druggists' Preparations",
        "sector": "Chemicals, Resins & Coatings",
        "description": "19th-century apothecary, pharmacopoeia, and fine-chemical drug manufacture (e.g., Howard & Sons, Allen & Hanburys) — extracting alkaloids and preparing tinctures, pills, plasters, and ointments from cinchona/quinine, opium/morphia/laudanum, coca/cocaine, nux vomica/strychnine, quicksilver/calomel, ipecacuanha, jalap, senna, rhubarb, aloes, camphor, castor/cod-liver oils, and iodine.",
        "trigger_re": re.compile(
            r"\b(pharmacop\w*|druggist\w*|apothecar\w*|materia\s+medica|pharmaceutical|officinal|"
            r"medicinal\s+(?:use|virtue|propert\w*|preparat\w*|extract|purposes?)|used\s+in\s+medicine|"
            r"employed\s+in\s+medicine|tincture\s+of|ointment\w*|medical\s+practice|alkaloid\w*|"
            r"febrifuge|cathartic|purgative|anodyne|emetic|narcotic|vermicide|anthelmintic)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [],
    },
    "oe:ind_metallurgy_tinplate": {
        "label": "Metallurgy, Smelting, Brass & Tinplate",
        "sector": "Minerals, Metals & Heavy Industry",
        "description": "Iron, copper, lead, tin, and zinc smelting, brass founding, type-metal, and tinplate manufacture — combining metallic ores and unwrought metals with coal, coke, charcoal, limestone, borax, plumbago crucibles, sulphuric/muriatic pickling acids, sal ammoniac, and palm oil/tallow tinplate baths.",
        "trigger_re": re.compile(
            r"\b(smelting|blast[\s-]*furnace|reverberatory\s+furnace|tin[\s-]*plate|tinned\s+iron|galvaniz\w*|"
            r"brass[\s-]*found\w*|making\s+brass|manufactur\w*\s+of\s+(?:brass|steel|iron|tin[\s-]*plate|bronze|pewter)|"
            r"type[\s-]*metal|bell[\s-]*metal|gun[\s-]*metal|solder(?:ing)?|crucibles?|metallurg\w*|"
            r"flux\s+(?:for|in)\s+(?:smelting|metals?|iron|copper)|amalgamation\s+of\s+(?:gold|silver))\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [
            (r"\nTIN-PLATE\.", r"\nTITANIUM[\.,\s]"),
            (r"\nBRASS[\.,\s]\s*\(", r"\nBREAD[\.,\s]"),
        ],
    },
    "oe:ind_hats_brushes_upholstery": {
        "label": "Hat-Making, Brushes, Upholstery & Turnery",
        "sector": "Hides, Leather & Animal Trades",
        "description": "Felt and silk hat-making, brushmaking, upholstery stuffing, and ornamental turnery — working beaver, rabbit/coney, and nutria pelts with shellac stiffening, nitrate of mercury carroting, and logwood/copperas black dye; hog bristles, horsehair, piassava, coir, and kapok; and ivory, whalebone, tortoise-shell, mother-of-pearl, cork, and rattan.",
        "trigger_re": re.compile(
            r"\b(hat[\s-]*mak\w*|hatters?|manufactur\w*\s+of\s+hats?|felt\s+hats?|silk\s+hats?|beaver\s+hats?|"
            r"brush[\s-]*mak\w*|making\s+brushes?|brooms?\s+and\s+brushes?|upholster\w*|stuffing\s+(?:mattresses?|cushions?|chairs?)|"
            r"turnery|turners?|inlaying|buttons?\s+and\s+combs?|combs?\s+and\s+knife[\s-]*handles?|umbrella\s+ribs?|corsets?\s+and\s+stays?)\b",
            re.I,
        ),
        "neg_re": None,
        "ure_essays": [(r"\nHAT\s+MANUFACTURE\.", r"\nHEAT[\.,\s]")],
    },
}

USE_SIGNAL_RE = re.compile(
    r"\b(used|employ\w*|made|making|manufactur\w*|prepar\w*|mix\w*|boil\w*|add\w*|combin\w*|"
    r"flavour\w*|flavor\w*|scent\w*|perfum\w*|dye\w*|print\w*|bleach\w*|thicken\w*|siz\w*|"
    r"mordant\w*|saponif\w*|tan(?:ning|ned|ners?)?|currying|smelt\w*|melt\w*|fus\w*|glaz\w*|"
    r"vulcan\w*|dissolv\w*|distill\w*|brew\w*|ferment\w*|refin\w*|clarif\w*|caulk\w*|stiffen\w*|"
    r"yield\w*|afford\w*|produc\w*|contain\w*|consist\w*|ingredient\w*|chief\w*|largely|"
    r"extensively|much|valuable|adapt\w*|suit\w*|substitut\w*|adulterat\w*|paste|liquor|bath|"
    r"vat|solution|oil|fat|tallow|alkali|lye|ley|curd|cake|bar|colour|color|medic\w*|tincture|pill|extract)\b",
    re.I,
)
TARIFF_NOISE_RE = re.compile(
    r"(?:£\s*\d|s\.\s*\d+d\.|\d+\s+Geo\.\s*\d|\d+\s+Vict\.|duty\s+of\s+\d|imported\s+in\s+18\d\d.*\d{3,}|"
    r"table\s+of\s+imports|total\s+value\s+£|duty[\s-]*free\s+goods|from\s+[A-Z][a-z]+\s+they\s+draw|"
    r"exports?\s+consist\s+of|imports?\s+consist\s+of|^See\s+[A-Z])",
    re.I,
)

# ============================================================================
# CANONICAL COMMODITY MATCHERS (~195 HIGH-PRECISION LAYER-1 + DOC-ATTESTED TERMS)
# Format: (exact_or_best_htc_label, regex_pattern, {industry_id: production_role})
# ============================================================================
CANONICAL_PATTERNS = [
    # --- Fats, Oils, Waxes & Rosin ---
    ("Tallow", r"\b(?:tallow|russian\s+tallow|mutton\s+tallow|beef\s+tallow|vegetable\s+tallow)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_candle_manufacture": "primary_feedstock",
        "oe:ind_leather_tanning": "tanning_or_curing", "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
        "oe:ind_cordage_shipbuilding": "solvent_or_fuel", "oe:ind_perfumery_cosmetics": "primary_feedstock",
    }),
    ("Palm Oil", r"\bpalm[\s-]*oil\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_candle_manufacture": "primary_feedstock",
        "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
    }),
    ("Cocoa-nut Oil", r"\b(?:coco[\s-]*nut|cocoa[\s-]*nut)[\s-]*oil\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_candle_manufacture": "primary_feedstock",
        "oe:ind_perfumery_cosmetics": "primary_feedstock",
    }),
    ("Olive Oil", r"\b(?:olive[\s-]*oil|gallipoli\s+oil|sweet\s+oil)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_calico_printing": "alkali_or_reagent",
        "oe:ind_woollen_silk_dyeing": "solvent_or_fuel", "oe:ind_perfumery_cosmetics": "primary_feedstock",
        "oe:ind_pharmaceuticals": "filler_or_admixture", "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Lard", r"\b(?:hog'?s?\s+lard|lard)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_candle_manufacture": "primary_feedstock",
        "oe:ind_perfumery_cosmetics": "primary_feedstock", "oe:ind_pharmaceuticals": "filler_or_admixture",
    }),
    ("Rosin", r"\b(?:rosin|colophony|yellow\s+resin|pine\s+resin)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_calico_printing": "thickener_or_sizing",
        "oe:ind_paper_making": "thickener_or_sizing", "oe:ind_varnish_paint_lacquer": "primary_feedstock",
        "oe:ind_cordage_shipbuilding": "thickener_or_sizing", "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
        "oe:ind_pharmaceuticals": "filler_or_admixture",
    }),
    ("Oil Seed", r"\b(?:linseed[\s-]*oil|hemp[\s-]*seed[\s-]*oil|rape[\s-]*seed[\s-]*oil|colza[\s-]*oil|cotton[\s-]*seed[\s-]*oil)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_varnish_paint_lacquer": "solvent_or_fuel",
        "oe:ind_rubber_waterproofing": "solvent_or_fuel", "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Oil Castor", r"\bcastor[\s-]*oil\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_calico_printing": "alkali_or_reagent",
        "oe:ind_pharmaceuticals": "primary_feedstock", "oe:ind_perfumery_cosmetics": "primary_feedstock",
    }),
    ("Oil Fish Cod Liver", r"\bcod[\s-]*liver[\s-]*oil\b", {
        "oe:ind_pharmaceuticals": "primary_feedstock", "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Shea Butter", r"\b(?:shea[\s-]*butter|galam[\s-]*butter|bassia\s+oil|mahua\s+oil|mowra\s+oil|illipe)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_candle_manufacture": "primary_feedstock",
    }),
    ("Sesame", r"\b(?:sesame[\s-]*oil|gingelly[\s-]*oil|til[\s-]*oil|teel[\s-]*oil|benne[\s-]*oil)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_perfumery_cosmetics": "primary_feedstock",
    }),
    ("Ground nut", r"\b(?:ground[\s-]*nut[\s-]*oil|earth[\s-]*nut[\s-]*oil|arachis[\s-]*oil)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock",
    }),
    ("Neem Oil", r"\b(?:neem[\s-]*oil|margosa[\s-]*oil)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Poppy Seed Oil", r"\bpoppy[\s-]*seed[\s-]*oil\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_varnish_paint_lacquer": "solvent_or_fuel",
    }),
    ("Almond Oil", r"\balmond[\s-]*oil\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_perfumery_cosmetics": "primary_feedstock",
        "oe:ind_pharmaceuticals": "filler_or_admixture",
    }),
    ("Train or Blubber (Whale Oils)", r"\b(?:whale[\s-]*oil|train[\s-]*oil|fish[\s-]*oil|seal[\s-]*oil|cod[\s-]*oil)\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Spermaceti", r"\bspermaceti\b", {
        "oe:ind_candle_manufacture": "primary_feedstock", "oe:ind_perfumery_cosmetics": "primary_feedstock",
        "oe:ind_pharmaceuticals": "filler_or_admixture",
    }),
    ("Stearine", r"\bstearin[e]?\b", {
        "oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_candle_manufacture": "primary_feedstock",
    }),
    ("Bees Wax", r"\b(?:bees[\s-]*wax|white\s+wax|yellow\s+wax)\b", {
        "oe:ind_candle_manufacture": "primary_feedstock", "oe:ind_varnish_paint_lacquer": "thickener_or_sizing",
        "oe:ind_perfumery_cosmetics": "primary_feedstock", "oe:ind_pharmaceuticals": "filler_or_admixture",
        "oe:ind_calico_printing": "thickener_or_sizing",
    }),
    ("Paraffin", r"\b(?:paraffin|ozokerit\w*)\b", {
        "oe:ind_candle_manufacture": "primary_feedstock", "oe:ind_gunpowder_matches": "solvent_or_fuel",
    }),
    ("Glycerine", r"\bglycerin[e]?\b", {
        "oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_gunpowder_matches": "primary_feedstock",
        "oe:ind_pharmaceuticals": "filler_or_admixture", "oe:ind_perfumery_cosmetics": "filler_or_admixture",
    }),

    # --- Alkalis, Salts, Acids & Industrial Chemicals ---
    ("Alkali", r"\b(?:soda[\s-]*ash|caustic\s+soda|carbonate\s+of\s+soda|subcarbonate\s+of\s+soda|crystals\s+of\s+soda|black[\s-]*ash|soda\s+ley|soda\s+lye|natron)\b", {
        "oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "bleaching_agent",
        "oe:ind_glass_ceramics": "alkali_or_reagent", "oe:ind_paper_making": "bleaching_agent",
        "oe:ind_woollen_silk_dyeing": "bleaching_agent",
    }),
    ("Barilla", r"\bbarilla\b", {
        "oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_glass_ceramics": "alkali_or_reagent",
        "oe:ind_calico_printing": "bleaching_agent",
    }),
    ("Kelp", r"\bkelp\b", {
        "oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_glass_ceramics": "alkali_or_reagent",
        "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Pearl and Pot Ashes", r"\b(?:potash|pot[\s-]*ash|pearl[\s-]*ash|wood[\s-]*ash(?:es)?|caustic\s+potash|carbonate\s+of\s+potash)\b", {
        "oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "bleaching_agent",
        "oe:ind_glass_ceramics": "alkali_or_reagent", "oe:ind_woollen_silk_dyeing": "alkali_or_reagent",
        "oe:ind_paper_making": "bleaching_agent", "oe:ind_gunpowder_matches": "alkali_or_reagent",
    }),
    ("Salt", r"\b(?:common\s+salt|sea[\s-]*salt|rock[\s-]*salt|muriate\s+of\s+soda|bay[\s-]*salt|cat[\s-]*salt)\b", {
        "oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_leather_tanning": "tanning_or_curing",
        "oe:ind_glass_ceramics": "alkali_or_reagent", "oe:ind_calico_printing": "alkali_or_reagent",
    }),
    ("Manufactures Lime", r"\b(?:quick[\s-]*lime|caustic\s+lime|slaked\s+lime|milk\s+of\s+lime|lime[\s-]*water|limestone)\b", {
        "oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "bleaching_agent",
        "oe:ind_leather_tanning": "tanning_or_curing", "oe:ind_glass_ceramics": "alkali_or_reagent",
        "oe:ind_sugar_refining": "bleaching_agent", "oe:ind_paper_making": "bleaching_agent",
        "oe:ind_metallurgy_tinplate": "solvent_or_fuel", "oe:ind_candle_manufacture": "alkali_or_reagent",
    }),
    ("Bleaching Materials", r"\b(?:bleaching[\s-]*powder|chloride\s+of\s+lime|chlorine|hypochlorite|eau\s+de\s+javelle)\b", {
        "oe:ind_calico_printing": "bleaching_agent", "oe:ind_paper_making": "bleaching_agent",
    }),
    ("Sulphuric Acid", r"\b(?:sulphuric\s+acid|oil\s+of\s+vitriol|vitriol)\b", {
        "oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_woollen_silk_dyeing": "alkali_or_reagent",
        "oe:ind_candle_manufacture": "alkali_or_reagent", "oe:ind_metallurgy_tinplate": "alkali_or_reagent",
        "oe:ind_leather_tanning": "tanning_or_curing", "oe:ind_paper_making": "bleaching_agent",
        "oe:ind_hats_brushes_upholstery": "alkali_or_reagent",
    }),
    ("Muriatic Acid", r"\b(?:muriatic\s+acid|hydrochloric\s+acid|spirit\s+of\s+salt)\b", {
        "oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_metallurgy_tinplate": "alkali_or_reagent",
        "oe:ind_woollen_silk_dyeing": "alkali_or_reagent",
    }),
    ("Nitric acid", r"\b(?:nitric\s+acid|aqua[\s-]*fortis)\b", {
        "oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_woollen_silk_dyeing": "alkali_or_reagent",
        "oe:ind_hats_brushes_upholstery": "alkali_or_reagent", "oe:ind_metallurgy_tinplate": "alkali_or_reagent",
        "oe:ind_gunpowder_matches": "alkali_or_reagent",
    }),
    ("Tartaric Acid", r"\b(?:tartaric\s+acid|cream\s+of\s+tartar|argol|tartar)\b", {
        "oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_woollen_silk_dyeing": "mordant_or_fixer",
        "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Citric Acid", r"\b(?:citric\s+acid|lemon[\s-]*juice|lime[\s-]*juice)\b", {
        "oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_woollen_silk_dyeing": "alkali_or_reagent",
        "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Oxalic Acid", r"\boxalic\s+acid\b", {
        "oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_leather_tanning": "bleaching_agent",
    }),
    ("Chemical Manufactures Acetic Acid", r"\b(?:acetic\s+acid|pyroligneous\s+acid|vinegar)\b", {
        "oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_woollen_silk_dyeing": "alkali_or_reagent",
    }),
    ("Borax", r"\bborax\b", {
        "oe:ind_glass_ceramics": "alkali_or_reagent", "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
        "oe:ind_candle_manufacture": "alkali_or_reagent", "oe:ind_soap_manufacture": "alkali_or_reagent",
        "oe:ind_calico_printing": "alkali_or_reagent",
    }),
    ("Sal Ammoniac", r"\b(?:sal[\s-]*ammoniac|muriate\s+of\s+ammonia)\b", {
        "oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
        "oe:ind_woollen_silk_dyeing": "alkali_or_reagent",
    }),
    ("Arsenic", r"\b(?:arsenic|arseniate\s+of\s+soda|white\s+arsenic)\b", {
        "oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_glass_ceramics": "bleaching_agent",
        "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Manganese Ore", r"\b(?:manganese|oxide\s+of\s+manganese|manganese\s+brown)\b", {
        "oe:ind_calico_printing": "bleaching_agent", "oe:ind_glass_ceramics": "bleaching_agent",
        "oe:ind_paper_making": "bleaching_agent", "oe:ind_gunpowder_matches": "alkali_or_reagent",
        "oe:ind_metallurgy_tinplate": "alkali_or_reagent",
    }),
    ("Saltpetre", r"\b(?:saltpetre|saltpeter|nitre|nitrate\s+of\s+potash)\b", {
        "oe:ind_gunpowder_matches": "primary_feedstock", "oe:ind_glass_ceramics": "bleaching_agent",
        "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
    }),
    ("Nitre Cubic", r"\b(?:cubic\s+nitre|nitrate\s+of\s+soda|chili\s+saltpetre)\b", {
        "oe:ind_gunpowder_matches": "primary_feedstock", "oe:ind_glass_ceramics": "alkali_or_reagent",
    }),
    ("Brimstone", r"\b(?:brimstone|sulphur|flowers\s+of\s+sulphur)\b", {
        "oe:ind_gunpowder_matches": "primary_feedstock", "oe:ind_rubber_waterproofing": "alkali_or_reagent",
        "oe:ind_woollen_silk_dyeing": "bleaching_agent", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Phosphorus", r"\bphosphorus\b", {
        "oe:ind_gunpowder_matches": "primary_feedstock",
    }),
    ("Chlorate Of Potash", r"\bchlorate\s+of\s+potash\b", {
        "oe:ind_gunpowder_matches": "primary_feedstock", "oe:ind_calico_printing": "alkali_or_reagent",
    }),
    ("Iodine", r"\biodine\b", {
        "oe:ind_pharmaceuticals": "primary_feedstock",
    }),

    # --- Fibres, Textiles, Skins, Hides & Paper Stocks ---
    ("Cotton Raw", r"\b(?:raw\s+cotton|cotton\s+wool|cotton\s+cloth|cotton\s+yarn|cotton\s+fabric|calico\s+cloth|cotton\s+piece[\s-]*goods|cotton\s+wick)\b", {
        "oe:ind_calico_printing": "primary_feedstock", "oe:ind_candle_manufacture": "filler_or_admixture",
        "oe:ind_gunpowder_matches": "primary_feedstock", "oe:ind_rubber_waterproofing": "filler_or_admixture",
    }),
    ("Wool", r"\b(?:sheep'?s?\s+wool|raw\s+wool|woollen\s+cloth|woollen\s+yarn|worsted|carded\s+wool|fleece\s+wool|lambs?'?\s+wool)\b", {
        "oe:ind_woollen_silk_dyeing": "primary_feedstock", "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Silk Raw", r"\b(?:raw\s+silk|silk\s+thread|silk\s+plush|silk\s+fabric|silk\s+stuffs?|thrown\s+silk)\b", {
        "oe:ind_woollen_silk_dyeing": "primary_feedstock", "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Fullers' Earth", r"\bfuller'?s?[\s-]*earth\b", {
        "oe:ind_woollen_silk_dyeing": "bleaching_agent",
    }),
    ("Hides Raw Dry", r"\b(?:ox[\s-]*hides?|cow[\s-]*hides?|buffalo[\s-]*hides?|calf[\s-]*skins?|raw\s+hides?|salted\s+hides?|green\s+hides?|horse[\s-]*hides?)\b", {
        "oe:ind_leather_tanning": "primary_feedstock",
    }),
    ("Skins Furs Pelts Goat undressed", r"\b(?:goat[\s-]*skins?|kid[\s-]*skins?)\b", {
        "oe:ind_leather_tanning": "primary_feedstock",
    }),
    ("Skins Furs Pelts Sheep Undressed", r"\b(?:sheep[\s-]*skins?|lamb[\s-]*skins?)\b", {
        "oe:ind_leather_tanning": "primary_feedstock",
    }),
    ("Skins Furs Pelts Beaver", r"\b(?:beaver\s+fur|beaver\s+skins?|beaver\s+wool|beaver\s+hair|beaver\s+hats?|beaver)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Skins Furs Pelts Rabbit", r"\b(?:rabbit[\s-]*fur|rabbit[\s-]*skins?|coney[\s-]*wool|coney[\s-]*fur|hare'?s?[\s-]*fur|hare[\s-]*skins?|rabbits?|hares?)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Skins Furs Pelts Nutria", r"\b(?:nutria\s+fur|nutria\s+skins?|coypu|musquash\s+fur)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Rags", r"\b(?:linen\s+rags?|cotton\s+rags?|woollen\s+rags?|old\s+rags?|paper\s+rags?)\b", {
        "oe:ind_paper_making": "primary_feedstock",
    }),
    ("Esparto and other Vegetable Fibres for making Paper", r"\b(?:esparto|alfa\s+grass)\b", {
        "oe:ind_paper_making": "primary_feedstock", "oe:ind_cordage_shipbuilding": "primary_feedstock",
    }),
    ("Wood Manufactures Wood Pulp", r"\b(?:wood[\s-]*pulp|mechanical\s+pulp|chemical\s+wood\s+pulp)\b", {
        "oe:ind_paper_making": "primary_feedstock",
    }),
    ("Straw", r"\b(?:straw[\s-]*pulp|wheat[\s-]*straw|oat[\s-]*straw|rye[\s-]*straw)\b", {
        "oe:ind_paper_making": "primary_feedstock", "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Hemp Rough or Undressed", r"\b(?:hemp|russian\s+hemp|sunn\s+hemp|italian\s+hemp)\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock", "oe:ind_paper_making": "primary_feedstock",
    }),
    ("Manila Hemp", r"\b(?:manila\s+hemp|manilla\s+hemp|abaca)\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock", "oe:ind_paper_making": "primary_feedstock",
    }),
    ("Sisal Hemp", r"\b(?:sisal\s+hemp|henequen)\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock",
    }),
    ("Flax", r"\b(?:flax|flax\s+fibre|tow\b)\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock", "oe:ind_paper_making": "primary_feedstock",
    }),
    ("Jute", r"\bjute\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock", "oe:ind_paper_making": "primary_feedstock",
    }),
    ("Coir", r"\bcoir\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock", "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Junk and Oakum", r"\b(?:oakum|old\s+junk)\b", {
        "oe:ind_cordage_shipbuilding": "filler_or_admixture", "oe:ind_paper_making": "primary_feedstock",
    }),
    ("Bristles", r"\b(?:hog'?s?\s+bristles?|bristles)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Horse Hair", r"\b(?:horse[\s-]*hair|curled\s+hair)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Piassava Fibre and other Fibres for Brush Making", r"\b(?:piassava|piassaba|kittool|kittul|bass\s+fibre)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Kapok", r"\b(?:kapok|silk[\s-]*cotton)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Ivory (Elephant Sea Cow Sea Horse or Sea Moose Teeth)", r"\b(?:ivory|elephant'?s?\s+teeth|vegetable\s+ivory|corozo)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Whale Fins", r"\b(?:whale[\s-]*bone|baleen|whale[\s-]*fins?)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Tortoise or Turtle Shell Unmanufactured", r"\b(?:tortoise[\s-]*shell|turtle[\s-]*shell)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Mother of Pearl Shells", r"\b(?:mother[\s-]*of[\s-]*pearl|pearl[\s-]*shell)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Cork Unmanufactured", r"\bcork\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Canes Rattans not Ground", r"\b(?:rattans?|canes?)\b", {
        "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),

    # --- Dyes, Pigments, Mordants & Tanning Materials ---
    ("Madder", r"\b(?:madder|madder[\s-]*root|rubia\s+tinctorum)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Madder Garancine", r"\bgarancin[e]?\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
    }),
    ("Madder Munjeet", r"\b(?:munjeet|manjit|munjut)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
    }),
    ("Dye Stuffs Alizarine and Alizarine Dyes", r"\balizarin[e]?\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
    }),
    ("Indigo", r"\bindigo\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_paper_making": "dye_or_colorant", "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Woad", r"\bwoad\b", {
        "oe:ind_woollen_silk_dyeing": "dye_or_colorant", "oe:ind_calico_printing": "dye_or_colorant",
    }),
    ("Dye Woods Logwood", r"\blog[\s-]*wood\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_hats_brushes_upholstery": "dye_or_colorant", "oe:ind_leather_tanning": "dye_or_colorant",
    }),
    ("Cochineal", r"\bcochineal\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_chocolate_confectionery": "dye_or_colorant", "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Gum Lac, Seed, Shell, Stick, and Dye", r"\b(?:lac[\s-]*dye|lac[\s-]*lake|shell[\s-]*lac|shellac|stick[\s-]*lac|seed[\s-]*lac)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_varnish_paint_lacquer": "primary_feedstock", "oe:ind_hats_brushes_upholstery": "thickener_or_sizing",
    }),
    ("Kermes", r"\bkermes\b", {
        "oe:ind_woollen_silk_dyeing": "dye_or_colorant", "oe:ind_calico_printing": "dye_or_colorant",
    }),
    ("Bark Quercitron", r"\bquercitron\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
    }),
    ("Wood and Timber Dye Woods Fustic", r"\bfustic\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
    }),
    ("Wood and Timber Dye Woods Brazil Wood", r"\b(?:brazil[\s-]*wood|peach[\s-]*wood|lima[\s-]*wood|sappan[\s-]*wood|sapan[\s-]*wood|pernambuco\s+wood)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
    }),
    ("Safflower", r"\bsafflower\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_perfumery_cosmetics": "dye_or_colorant",
    }),
    ("Orchal", r"\b(?:orchal|archil|orchil|orseille|cudbear)\b", {
        "oe:ind_woollen_silk_dyeing": "dye_or_colorant", "oe:ind_calico_printing": "dye_or_colorant",
    }),
    ("Annatto Flag", r"\b(?:annatto|anatto|arnatto|arnotto|roucou)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_chocolate_confectionery": "dye_or_colorant", "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Turmeric", r"\bturmeric\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Weld", r"\bweld\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
    }),
    ("Berries Yellow", r"\b(?:persian\s+berries|avignon\s+berries|yellow\s+berries|french\s+berries)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
    }),
    ("Aniline", r"\b(?:aniline|coal[\s-]*tar\s+dye|magenta|mauve|fuchsine|rosaniline)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
    }),
    ("Bichromate", r"\b(?:bichromate\s+of\s+potash|chromate\s+of\s+potash|chrome\s+yellow|chromate\s+of\s+lead|chrome\s+orange)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Prussian Blue", r"\b(?:prussiate\s+of\s+potash|prussian\s+blue|ferrocyanide|ferroprussiate)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_woollen_silk_dyeing": "dye_or_colorant",
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant", "oe:ind_paper_making": "dye_or_colorant",
    }),
    ("Ultramarine", r"\bultramarine\b", {
        "oe:ind_paper_making": "dye_or_colorant", "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
        "oe:ind_calico_printing": "dye_or_colorant",
    }),
    ("Smalts", r"\b(?:smalt|smalts|cobalt\s+blue|zaffre)\b", {
        "oe:ind_glass_ceramics": "dye_or_colorant", "oe:ind_paper_making": "dye_or_colorant",
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Verdigris", r"\bverdigris\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
        "oe:ind_hats_brushes_upholstery": "dye_or_colorant",
    }),
    ("Orpiment", r"\b(?:orpiment|realgar)\b", {
        "oe:ind_calico_printing": "dye_or_colorant", "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Painters Colours and Pigments White Lead", r"\bwhite[\s-]*lead\b", {
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant", "oe:ind_rubber_waterproofing": "filler_or_admixture",
        "oe:ind_glass_ceramics": "alkali_or_reagent",
    }),
    ("Vermilion", r"\b(?:vermilion|cinnabar)\b", {
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant", "oe:ind_rubber_waterproofing": "dye_or_colorant",
    }),
    ("Ochre", r"\b(?:red\s+ochre|yellow\s+ochre|ochre)\b", {
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant", "oe:ind_soap_manufacture": "dye_or_colorant",
    }),
    ("Umber", r"\bumber\b", {
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Gamboge", r"\bgamboge\b", {
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Alkanet", r"\balkanet\b", {
        "oe:ind_perfumery_cosmetics": "dye_or_colorant", "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Alum Roach", r"\b(?:alum|acetate\s+of\s+alumina|red\s+liquor|aluminous\s+mordant)\b", {
        "oe:ind_calico_printing": "mordant_or_fixer", "oe:ind_woollen_silk_dyeing": "mordant_or_fixer",
        "oe:ind_leather_tanning": "tanning_or_curing", "oe:ind_paper_making": "thickener_or_sizing",
    }),
    ("Copperas", r"\b(?:copperas|sulphate\s+of\s+iron|iron\s+liquor|acetate\s+of\s+iron|pyrolignite\s+of\s+iron|nitrate\s+of\s+iron|green\s+vitriol)\b", {
        "oe:ind_calico_printing": "mordant_or_fixer", "oe:ind_woollen_silk_dyeing": "mordant_or_fixer",
        "oe:ind_hats_brushes_upholstery": "mordant_or_fixer", "oe:ind_soap_manufacture": "dye_or_colorant",
        "oe:ind_leather_tanning": "dye_or_colorant",
    }),
    ("Blue Vitriol", r"\b(?:blue\s+vitriol|sulphate\s+of\s+copper|acetate\s+of\s+copper|nitrate\s+of\s+copper)\b", {
        "oe:ind_calico_printing": "mordant_or_fixer", "oe:ind_woollen_silk_dyeing": "mordant_or_fixer",
        "oe:ind_hats_brushes_upholstery": "mordant_or_fixer",
    }),
    ("Lead Pig and Sheet", r"\b(?:sugar\s+of\s+lead|acetate\s+of\s+lead|nitrate\s+of\s+lead|red[\s-]*lead|litharge|minium|oxide\s+of\s+lead)\b", {
        "oe:ind_calico_printing": "mordant_or_fixer", "oe:ind_glass_ceramics": "alkali_or_reagent",
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant", "oe:ind_rubber_waterproofing": "alkali_or_reagent",
        "oe:ind_metallurgy_tinplate": "primary_feedstock",
    }),
    ("Tin in Blocks Ingots Bars or Slabs", r"\b(?:muriate\s+of\s+tin|chloride\s+of\s+tin|stannate\s+of\s+soda|salts?\s+of\s+tin|tin\s+liquor|tin\s+mordant|block\s+tin|grain\s+tin|oxide\s+of\s+tin)\b", {
        "oe:ind_calico_printing": "mordant_or_fixer", "oe:ind_woollen_silk_dyeing": "mordant_or_fixer",
        "oe:ind_metallurgy_tinplate": "primary_feedstock", "oe:ind_glass_ceramics": "dye_or_colorant",
    }),
    # Tanning barks & extracts
    ("Oak Bark", r"\boak[\s-]*bark\b", {
        "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Bark For Tanners and Dyers Use", r"\b(?:tan[\s-]*bark|tanners?'?\s+bark|larch[\s-]*bark|birch[\s-]*bark|willow[\s-]*bark|mangrove[\s-]*bark|babul\s+bark)\b", {
        "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Bark Extract of Hemlock", r"\bhemlock[\s-]*bark\b", {
        "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Mimosa Bark", r"\b(?:mimosa[\s-]*bark|wattle[\s-]*bark|acacia[\s-]*bark)\b", {
        "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Valonia", r"\bvalonia\b", {
        "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Divi Divi", r"\bdivi[\s-]*divi\b", {
        "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Shumach", r"\b(?:sumach|sumac|shumach)\b", {
        "oe:ind_leather_tanning": "tanning_or_curing", "oe:ind_calico_printing": "mordant_or_fixer",
        "oe:ind_woollen_silk_dyeing": "mordant_or_fixer",
    }),
    ("Galls", r"\b(?:gall[\s-]*nuts?|nut[\s-]*galls?|aleppo\s+galls?|oak[\s-]*galls?|galls\b)\b", {
        "oe:ind_leather_tanning": "tanning_or_curing", "oe:ind_calico_printing": "mordant_or_fixer",
        "oe:ind_woollen_silk_dyeing": "mordant_or_fixer",
    }),
    ("Cutch", r"\b(?:catechu|cutch|terra\s+japonica|gambier)\b", {
        "oe:ind_leather_tanning": "tanning_or_curing", "oe:ind_calico_printing": "mordant_or_fixer",
        "oe:ind_woollen_silk_dyeing": "mordant_or_fixer",
    }),
    ("Myrabolans", r"\bmyr[ao]b[ao]lans?\b", {
        "oe:ind_leather_tanning": "tanning_or_curing", "oe:ind_calico_printing": "mordant_or_fixer",
    }),

    # --- Resins, Gums, Naval Stores, Rubber, Solvents & Thickeners ---
    ("Gum Senegal", r"\bgum[\s-]*senegal\b", {
        "oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture",
        "oe:ind_pharmaceuticals": "filler_or_admixture",
    }),
    ("Gum Arabic", r"\bgum[\s-]*arabic\b", {
        "oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture",
        "oe:ind_pharmaceuticals": "filler_or_admixture", "oe:ind_gunpowder_matches": "thickener_or_sizing",
        "oe:ind_woollen_silk_dyeing": "thickener_or_sizing",
    }),
    ("Gum Tragacanth", r"\b(?:gum[\s-]*tragacanth|tragacanth)\b", {
        "oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture",
        "oe:ind_pharmaceuticals": "filler_or_admixture",
    }),
    ("Gum Copal", r"\bcopal\b", {
        "oe:ind_varnish_paint_lacquer": "primary_feedstock",
    }),
    ("Gum Dammar", r"\b(?:dammar|dammer|kauri\s+gum)\b", {
        "oe:ind_varnish_paint_lacquer": "primary_feedstock",
    }),
    ("Gum Mastic", r"\b(?:mastic|mastich)\b", {
        "oe:ind_varnish_paint_lacquer": "primary_feedstock", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Sandarac", r"\bsandarac[h]?\b", {
        "oe:ind_varnish_paint_lacquer": "primary_feedstock",
    }),
    ("Elemi", r"\belemi\b", {
        "oe:ind_varnish_paint_lacquer": "primary_feedstock", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Amber", r"\bamber\b", {
        "oe:ind_varnish_paint_lacquer": "primary_feedstock", "oe:ind_hats_brushes_upholstery": "primary_feedstock",
    }),
    ("Turpentine Oil", r"\b(?:oil\s+of\s+turpentine|spirits?\s+of\s+turpentine|turpentine)\b", {
        "oe:ind_varnish_paint_lacquer": "solvent_or_fuel", "oe:ind_rubber_waterproofing": "solvent_or_fuel",
        "oe:ind_cordage_shipbuilding": "thickener_or_sizing", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Tar", r"\b(?:pine[\s-]*tar|stockholm\s+tar|archangel\s+tar|wood[\s-]*tar|coal[\s-]*tar|tarred\s+hemp|tar\b)\b", {
        "oe:ind_cordage_shipbuilding": "thickener_or_sizing", "oe:ind_varnish_paint_lacquer": "primary_feedstock",
        "oe:ind_rubber_waterproofing": "solvent_or_fuel",
    }),
    ("Pitch", r"\b(?:pitch|burgundy\s+pitch|mineral\s+pitch|asphaltum)\b", {
        "oe:ind_cordage_shipbuilding": "thickener_or_sizing", "oe:ind_varnish_paint_lacquer": "primary_feedstock",
        "oe:ind_pharmaceuticals": "filler_or_admixture",
    }),
    ("Caoutchouc", r"\b(?:caoutchouc|india[\s-]*rubber|indian[\s-]*rubber)\b", {
        "oe:ind_rubber_waterproofing": "primary_feedstock", "oe:ind_varnish_paint_lacquer": "primary_feedstock",
    }),
    ("Gutta Percha", r"\bgutta[\s-]*percha\b", {
        "oe:ind_rubber_waterproofing": "primary_feedstock",
    }),
    ("Naphtha", r"\b(?:coal[\s-]*tar\s+naphtha|naphtha|benzol|benzene)\b", {
        "oe:ind_rubber_waterproofing": "solvent_or_fuel", "oe:ind_varnish_paint_lacquer": "solvent_or_fuel",
    }),
    ("Starch", r"\b(?:starch|british\s+gum|dextrin[e]?|calcined\s+starch|torrefied\s+starch|potato[\s-]*starch|wheat[\s-]*starch)\b", {
        "oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_paper_making": "thickener_or_sizing",
        "oe:ind_chocolate_confectionery": "filler_or_admixture",
    }),
    ("Wheat Meal and Flour", r"\b(?:wheat[\s-]*flour|flour\s+paste|wheaten\s+flour|flour)\b", {
        "oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture",
        "oe:ind_leather_tanning": "tanning_or_curing",
    }),
    ("Albumin", r"\b(?:albumen|albumin|blood[\s-]*albumen|egg[\s-]*albumen|bullock'?s?\s+blood)\b", {
        "oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_sugar_refining": "bleaching_agent",
        "oe:ind_chocolate_confectionery": "filler_or_admixture",
    }),
    ("Glue Size and Gelatine", r"\b(?:glue|gelatine|gelatin|size\b)\b", {
        "oe:ind_paper_making": "thickener_or_sizing", "oe:ind_gunpowder_matches": "thickener_or_sizing",
        "oe:ind_hats_brushes_upholstery": "thickener_or_sizing",
    }),
    ("Isinglass", r"\bisinglass\b", {
        "oe:ind_brewing_distilling": "bleaching_agent", "oe:ind_chocolate_confectionery": "filler_or_admixture",
    }),
    ("Bran", r"\bbran\b", {
        "oe:ind_calico_printing": "bleaching_agent", "oe:ind_leather_tanning": "tanning_or_curing",
    }),

    # --- Minerals, Clays, Fuels, Metals & Timber ---
    ("Kaolin", r"\b(?:kaolin|china[\s-]*clay|cornish\s+clay|porcelain\s+clay)\b", {
        "oe:ind_glass_ceramics": "primary_feedstock", "oe:ind_paper_making": "filler_or_admixture",
    }),
    ("Clay unmanufactured", r"\b(?:pipe[\s-]*clay|potter'?s?\s+clay|fire[\s-]*clay|stourbridge\s+clay)\b", {
        "oe:ind_glass_ceramics": "primary_feedstock", "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
        "oe:ind_sugar_refining": "bleaching_agent",
    }),
    ("Flint Glass", r"\b(?:flint|calcined\s+flint|silica|quartz\s+sand|white\s+sand)\b", {
        "oe:ind_glass_ceramics": "primary_feedstock",
    }),
    ("Bones (except Whalefins)", r"\b(?:animal\s+charcoal|bone[\s-]*black|bone[\s-]*ash|calcined\s+bones?|ivory[\s-]*black)\b", {
        "oe:ind_sugar_refining": "bleaching_agent", "oe:ind_glass_ceramics": "primary_feedstock",
        "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
    }),
    ("Charcoal", r"\b(?:wood[\s-]*charcoal|alder\s+charcoal|willow\s+charcoal|dogwood\s+charcoal|charcoal)\b", {
        "oe:ind_gunpowder_matches": "primary_feedstock", "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
        "oe:ind_sugar_refining": "bleaching_agent",
    }),
    ("Coal", r"\b(?:pit[\s-]*coal|bituminous\s+coal|anthracite|mineral\s+coal|cannel\s+coal)\b", {
        "oe:ind_metallurgy_tinplate": "solvent_or_fuel", "oe:ind_glass_ceramics": "solvent_or_fuel",
    }),
    ("Coke", r"\bcoke\b", {
        "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
    }),
    ("Plumbago", r"\b(?:plumbago|graphite|black[\s-]*lead)\b", {
        "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
    }),
    ("Pig and Scrap Iron", r"\b(?:pig[\s-]*iron|iron[\s-]*ore|bar[\s-]*iron|sheet[\s-]*iron|wrought[\s-]*iron|cast[\s-]*iron)\b", {
        "oe:ind_metallurgy_tinplate": "primary_feedstock",
    }),
    ("Copper Ore", r"\b(?:copper[\s-]*ore|unwrought\s+copper|sheet\s+copper|cake\s+copper|rosette\s+copper|copper\s+sheathing)\b", {
        "oe:ind_metallurgy_tinplate": "primary_feedstock", "oe:ind_cordage_shipbuilding": "primary_feedstock",
    }),
    ("Zinc Ore", r"\b(?:zinc|spelter|calamine|zinc[\s-]*white|oxide\s+of\s+zinc)\b", {
        "oe:ind_metallurgy_tinplate": "primary_feedstock", "oe:ind_varnish_paint_lacquer": "dye_or_colorant",
        "oe:ind_rubber_waterproofing": "alkali_or_reagent",
    }),
    ("Antimony Ore", r"\b(?:antimony|regulus\s+of\s+antimony)\b", {
        "oe:ind_metallurgy_tinplate": "primary_feedstock", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Bismuth", r"\bbismuth\b", {
        "oe:ind_metallurgy_tinplate": "primary_feedstock", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Nickel Ore", r"\bnickel\b", {
        "oe:ind_metallurgy_tinplate": "primary_feedstock",
    }),
    ("Cobalt Ore", r"\b(?:cobalt|oxide\s+of\s+cobalt)\b", {
        "oe:ind_glass_ceramics": "dye_or_colorant", "oe:ind_metallurgy_tinplate": "primary_feedstock",
    }),
    ("Quicksilver", r"\b(?:quicksilver|mercury|nitrate\s+of\s+mercury|mercurial)\b", {
        "oe:ind_pharmaceuticals": "primary_feedstock", "oe:ind_hats_brushes_upholstery": "alkali_or_reagent",
        "oe:ind_metallurgy_tinplate": "solvent_or_fuel",
    }),
    ("Timber Oak", r"\b(?:oak\s+timber|english\s+oak|dantzic\s+oak|live\s+oak|african\s+oak)\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock",
    }),
    ("Wood and Timber Hewn Teak", r"\b(?:teak|teak[\s-]*wood|indian\s+oak)\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock",
    }),
    ("Greenheart", r"\bgreenheart\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock",
    }),
    ("Masts", r"\b(?:masts|spars|pine\s+timber|fir\s+timber|kauri\s+pine|yellow\s+pine|pitch\s+pine)\b", {
        "oe:ind_cordage_shipbuilding": "primary_feedstock", "oe:ind_gunpowder_matches": "filler_or_admixture",
    }),

    # --- Food, Brewing, Spirits, Spices & Perfumes ---
    ("Cocoa", r"\b(?:cocoa|cacao|cacao[\s-]*beans?|cocoa[\s-]*beans?|cocoa[\s-]*nibs?|butter\s+of\s+cacao|cocoa[\s-]*butter)\b", {
        "oe:ind_chocolate_confectionery": "primary_feedstock", "oe:ind_soap_manufacture": "primary_feedstock",
    }),
    ("Sugar Unrefined Total", r"\b(?:sugar|cane[\s-]*sugar|refined\s+sugar|loaf[\s-]*sugar|white\s+sugar|brown\s+sugar|raw\s+sugar|muscovado)\b", {
        "oe:ind_chocolate_confectionery": "primary_feedstock", "oe:ind_sugar_refining": "primary_feedstock",
        "oe:ind_brewing_distilling": "primary_feedstock", "oe:ind_pharmaceuticals": "filler_or_admixture",
    }),
    ("Molasses", r"\b(?:molasses|treacle)\b", {
        "oe:ind_brewing_distilling": "primary_feedstock", "oe:ind_sugar_refining": "primary_feedstock",
        "oe:ind_chocolate_confectionery": "primary_feedstock",
    }),
    ("Honey", r"\bhoney\b", {
        "oe:ind_chocolate_confectionery": "primary_feedstock", "oe:ind_pharmaceuticals": "filler_or_admixture",
        "oe:ind_brewing_distilling": "primary_feedstock",
    }),
    ("Barley", r"\bbarley\b", {
        "oe:ind_brewing_distilling": "primary_feedstock",
    }),
    ("Malt", r"\b(?:malt|malted\s+barley|pale\s+malt|roasted\s+malt)\b", {
        "oe:ind_brewing_distilling": "primary_feedstock",
    }),
    ("Hops", r"\bhops?\b", {
        "oe:ind_brewing_distilling": "flavouring_or_scent",
    }),
    ("Juniper Berries", r"\bjuniper[\s-]*berr(?:y|ies)\b", {
        "oe:ind_brewing_distilling": "flavouring_or_scent", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Lignum Quassia", r"\bquassia\b", {
        "oe:ind_brewing_distilling": "flavouring_or_scent", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Cocculus Indicus", r"\bcocculus\s+indicus\b", {
        "oe:ind_brewing_distilling": "flavouring_or_scent", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Spirits Unenumerated not Sweetened", r"\b(?:rectified\s+spirit|spirits?\s+of\s+wine|alcohol)\b", {
        "oe:ind_varnish_paint_lacquer": "solvent_or_fuel", "oe:ind_perfumery_cosmetics": "solvent_or_fuel",
        "oe:ind_pharmaceuticals": "solvent_or_fuel", "oe:ind_hats_brushes_upholstery": "solvent_or_fuel",
    }),
    ("Vanilla", r"\bvanilla\b", {
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),
    ("Spices Cinnamon", r"\bcinnamon\b", {
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent",
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent", "oe:ind_pharmaceuticals": "flavouring_or_scent",
    }),
    ("Spices Cassia Lignea", r"\b(?:cassia|cassia[\s-]*buds?|cassia[\s-]*lignea|cassia[\s-]*oil)\b", {
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent",
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),
    ("Spices Cloves", r"\b(?:cloves?|oil\s+of\s+cloves?)\b", {
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent",
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent", "oe:ind_pharmaceuticals": "flavouring_or_scent",
    }),
    ("Spices Nutmegs", r"\b(?:nutmegs?|mace\b)\b", {
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),
    ("Cardamom", r"\bcardamoms?\b", {
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_pharmaceuticals": "primary_feedstock",
        "oe:ind_brewing_distilling": "flavouring_or_scent",
    }),
    ("Ginger Raw", r"\bginger\b", {
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_brewing_distilling": "flavouring_or_scent",
        "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Almonds", r"\b(?:almonds?|sweet\s+almonds?|bitter\s+almonds?)\b", {
        "oe:ind_chocolate_confectionery": "filler_or_admixture", "oe:ind_soap_manufacture": "flavouring_or_scent",
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),
    ("Liquorice", r"\b(?:liquorice|licorice)\b", {
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_brewing_distilling": "flavouring_or_scent",
        "oe:ind_pharmaceuticals": "filler_or_admixture",
    }),
    ("Aniseed", r"\b(?:aniseed|anise|oil\s+of\s+anise)\b", {
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_brewing_distilling": "flavouring_or_scent",
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),
    ("Coriander", r"\bcoriander\b", {
        "oe:ind_brewing_distilling": "flavouring_or_scent", "oe:ind_chocolate_confectionery": "flavouring_or_scent",
    }),
    ("Milk Condensed", r"\b(?:condensed\s+milk|cow'?s?\s+milk|milk)\b", {
        "oe:ind_chocolate_confectionery": "filler_or_admixture",
    }),
    ("Citronella", r"\bcitronella\b", {
        "oe:ind_soap_manufacture": "flavouring_or_scent", "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),
    ("Bergamot", r"\bbergamot\b", {
        "oe:ind_soap_manufacture": "flavouring_or_scent", "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),
    ("Lavender Oil", r"\b(?:lavender[\s-]*oil|oil\s+of\s+lavender|spike\s+lavender)\b", {
        "oe:ind_soap_manufacture": "flavouring_or_scent", "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),
    ("Musk", r"\bmusk\b", {
        "oe:ind_soap_manufacture": "flavouring_or_scent", "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
        "oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Ambergris", r"\bambergris\b", {
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent", "oe:ind_chocolate_confectionery": "flavouring_or_scent",
    }),
    ("Sandal wood", r"\b(?:sandal[\s-]*wood[\s-]*oil|oil\s+of\s+sandal[\s-]*wood|sandal[\s-]*wood)\b", {
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent",
    }),
    ("Otto of Roses", r"\b(?:otto\s+of\s+roses?|attar\s+of\s+roses?|oil\s+of\s+roses?)\b", {
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent",
    }),
    ("Gum Benzoin", r"\b(?:benzoin|gum[\s-]*benjamin)\b", {
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent", "oe:ind_pharmaceuticals": "primary_feedstock",
        "oe:ind_varnish_paint_lacquer": "primary_feedstock",
    }),
    ("Olibanum", r"\b(?:olibanum|frankincense)\b", {
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Myrrh", r"\bmyrrh\b", {
        "oe:ind_pharmaceuticals": "primary_feedstock", "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),
    ("Storax", r"\bstorax\b", {
        "oe:ind_perfumery_cosmetics": "flavouring_or_scent", "oe:ind_pharmaceuticals": "primary_feedstock",
    }),
    ("Tolu", r"\b(?:balsam\s+of\s+tolu|tolu\s+balsam)\b", {
        "oe:ind_pharmaceuticals": "primary_feedstock", "oe:ind_perfumery_cosmetics": "flavouring_or_scent",
    }),

    # --- Major Drugs, Alkaloids & Botanicals (Pharmaceuticals) ---
    ("Opium", r"\bopium\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Morphia", r"\b(?:morphia|morphine)\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Laudanum", r"\blaudanum\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Bark Peruvian", r"\b(?:cinchona|peruvian\s+bark|jesuits?'?\s+bark)\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Quinine Sulphate of", r"\bquinine\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Coca", r"\bcoca\s+lea(?:f|ves)\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Cocaine", r"\bcocaine\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Nux Vomica", r"\bnux[\s-]*vomica\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Strychnine", r"\bstrychnin[e]?\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Calomel", r"\bcalomel\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Radix Ipecacoanhoe", r"\bipecacuanha\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Jalap", r"\bjalap\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Senna", r"\bsenna\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Rhubarb", r"\brhubarb\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Aloes", r"\baloes\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Sarsaparilla", r"\bsarsaparilla\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Balsam Copaiba", r"\b(?:copaiba|copaiva)\b", {"oe:ind_pharmaceuticals": "primary_feedstock", "oe:ind_varnish_paint_lacquer": "primary_feedstock"}),
    ("Camphor Refined", r"\bcamphor\b", {"oe:ind_pharmaceuticals": "primary_feedstock", "oe:ind_varnish_paint_lacquer": "solvent_or_fuel", "oe:ind_perfumery_cosmetics": "flavouring_or_scent"}),
    ("Atropa Belladonna", r"\bbelladonna\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Gentian", r"\bgentian\b", {"oe:ind_pharmaceuticals": "primary_feedstock", "oe:ind_brewing_distilling": "flavouring_or_scent"}),
    ("Asafoetida", r"\b(?:asafoetida|assafetida|assafoetida)\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Scammony", r"\bscammony\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
    ("Cascarilla", r"\bcascarilla\b", {"oe:ind_pharmaceuticals": "primary_feedstock"}),
]


def norm_key(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"['’`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ttl_str(s: str) -> str:
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    return f'"{s}"'


def resolve_canonical_concepts():
    l1 = [json.loads(l) for l in open(GROUND / "commodities_concepts.jsonl", encoding="utf-8") if l.strip()]
    doc = [json.loads(l) for l in open(GROUND / "document_attested_concepts.jsonl", encoding="utf-8") if l.strip()]
    all_c = l1 + doc
    by_exact = defaultdict(list)
    by_norm = defaultdict(list)
    for c in all_c:
        by_exact[c["skos_prefLabel"].lower()].append(c)
        by_norm[norm_key(c["skos_prefLabel"])].append(c)
        for al in c.get("skos_altLabels") or []:
            by_norm[norm_key(al)].append(c)

    def pick_best(query: str):
        ql = query.lower()
        qn = norm_key(query)
        cands = by_exact.get(ql) or by_norm.get(qn)
        if not cands:
            cands = [c for c in all_c if qn in norm_key(c["skos_prefLabel"])]
        if not cands:
            return None
        def score(c):
            is_l1 = 1 if not c["concept_id"].startswith("htc:doc_") else 0
            exact = 1 if norm_key(c["skos_prefLabel"]) == qn else 0
            unenum = -1 if "unenumerated" in c["skos_prefLabel"].lower() else 0
            return (exact * 100 + is_l1 * 20 + unenum * 50, c.get("total_rows", 0), -len(c["skos_prefLabel"]))
        return max(cands, key=score)

    resolved, missing = [], []
    for query, pat, role_map in CANONICAL_PATTERNS:
        c = pick_best(query)
        if not c:
            missing.append(query)
            continue
        resolved.append({
            "query": query,
            "concept": c,
            "rx": re.compile(pat, re.I),
            "role_map": role_map,
        })
    if missing:
        print(f"Note: {len(missing)} skipped (no htc: match): {missing}")
    return resolved


def clean_sentence(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[*_#]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_sentences(text: str):
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"(?<=[\.\?!])\s+(?=[A-Z]{4,}(?:[\s\-][A-Z]{2,})?[,\.\(])", "\n<ENTRY>\n", text)
    text = re.sub(r"[ \t\r]+", " ", text)
    prot = re.sub(r"\b(Mr|Dr|St|vs|No|pp|cf|oz|lb|lbs|cwt|vol|ed|fig|sec|stat|Geo|Vict|Fr|Germ|Lat|etc)\.", r"\1<DOT>", text)
    out = []
    for block in prot.split("<ENTRY>"):
        for s in re.split(r"(?<=[\.\?!])\s+(?=[A-Z])", block.strip()):
            s = s.replace("<DOT>", ".").strip()
            if s:
                out.append(s)
    return out


def iter_all_corpus_pages():
    """Yield (work_id, citation, uri, text, essay_industry_or_None) across all 6 full-text books."""
    # 1. Ure (1840) — compute exact character spans for every dedicated industry essay!
    ure_path = GUT_ROOT / "pg44562_ure_dictionary_arts_manufactures.txt"
    if ure_path.exists():
        raw = ure_path.read_text(encoding="utf-8", errors="ignore")
        m_s = re.search(r"\*\*\*\s*START OF (?:THIS|THE) PROJECT GUTENBERG", raw)
        m_e = re.search(r"\*\*\*\s*END OF (?:THIS|THE) PROJECT GUTENBERG", raw)
        body = raw[m_s.end():m_e.start()] if (m_s and m_e) else raw
        ure_spans = []
        for ind_id, cfg in INDUSTRIES.items():
            for sp, ep in cfg.get("ure_essays") or []:
                m1 = re.search(sp, body)
                if m1:
                    m2 = re.search(ep, body[m1.end():])
                    end_pos = (m1.end() + m2.start()) if m2 else min(len(body), m1.end() + 40000)
                    ure_spans.append((m1.start(), end_pos, ind_id))
        chunk_sz = 5000
        for i in range(0, len(body), chunk_sz):
            mid = i + chunk_sz // 2
            essay_ind = None
            for s0, e0, ind_id in ure_spans:
                if s0 <= mid <= e0:
                    essay_ind = ind_id
                    break
            yield ("ure_gutenberg", "Ure (1840), Dictionary of Arts, Manufactures, and Mines", "https://www.gutenberg.org/ebooks/44562", body[i:i + chunk_sz + 250], essay_ind)

    # 2. Simmonds (1854) Project Gutenberg
    s54_path = GUT_ROOT / "pg15191_simmonds_1854_vegetable_kingdom.txt"
    if s54_path.exists():
        raw = s54_path.read_text(encoding="utf-8", errors="ignore")
        m_s = re.search(r"\*\*\*\s*START OF (?:THIS|THE) PROJECT GUTENBERG", raw)
        m_e = re.search(r"\*\*\*\s*END OF (?:THIS|THE) PROJECT GUTENBERG", raw)
        body = raw[m_s.end():m_e.start()] if (m_s and m_e) else raw
        chunk_sz = 5000
        for i in range(0, len(body), chunk_sz):
            yield ("simmonds_1854", "Simmonds (1854), Commercial Products of the Vegetable Kingdom", "https://www.gutenberg.org/ebooks/15191", body[i:i + chunk_sz + 250], None)

    # 3. All 4 Chandra-2 OCR'd books in dictionaries_all (with exact PDF page URIs)
    ia_specs = {
        "b21780535": ("simmonds_1892", "Simmonds (1892), Commercial Dictionary of Trade Products"),
        "b31361584": ("watt_1908", "Watt (1908), Commercial Products of India"),
        "dictionaryprac00mccu": ("mcculloch_1880", "McCulloch (1880), Dictionary of Commerce"),
        "generalcommercia00mort": ("mortimer_1823", "Mortimer (1823), General Commercial Dictionary"),
    }
    for ia_id, (wid, cit) in ia_specs.items():
        for md_path in sorted(OCR_ROOT.glob(f"{ia_id}_p*/{ia_id}/{ia_id}.md")):
            m_b = re.search(r"_p(\d+)", md_path.parent.parent.name)
            base_page = int(m_b.group(1)) if m_b else 1
            txt = md_path.read_text(encoding="utf-8", errors="ignore")
            parts = PAGE_MARK_RE.split(txt)
            if len(parts) < 3:
                yield (wid, f"{cit}, scan p. {base_page}", f"https://archive.org/details/{ia_id}/page/n{base_page}/mode/1up", txt, None)
            else:
                if parts[0].strip():
                    yield (wid, f"{cit}, scan p. {base_page}", f"https://archive.org/details/{ia_id}/page/n{base_page}/mode/1up", parts[0], None)
                for idx in range(1, len(parts), 2):
                    rel_p = int(parts[idx])
                    pdf_p = base_page + rel_p if rel_p <= 30 else rel_p
                    yield (wid, f"{cit}, scan p. {pdf_p}", f"https://archive.org/details/{ia_id}/page/n{pdf_p}/mode/1up", parts[idx + 1], None)


LINK_DECISIONS_PATH = GROUND / "curated_end_use_link_decisions.tsv"


def apply_curated_link_decisions(links):
    """Apply hand-reviewed decisions to regex-mined links: `drop` (no quote supports the link), `repoint`
    (quotes are about a different heading -> target concept), plus optional removal of individual quotes
    (`drop_quotes`: "||"-separated substrings). Keyword co-occurrence is not evidence of use; these rows
    record where a human-style reading of the verbatim quotes contradicted the mined link."""
    if not LINK_DECISIONS_PATH.exists():
        return links
    concepts = {}
    for fn in ("commodities_concepts.jsonl", "document_attested_concepts.jsonl"):
        for line in open(GROUND / fn, encoding="utf-8"):
            if line.strip():
                c = json.loads(line)
                concepts[c["concept_id"]] = c
    dec = {}
    with open(LINK_DECISIONS_PATH, encoding="utf-8") as fh:
        for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
            if r["action"] not in ("drop", "repoint", "prune"):
                raise ValueError(f"curated_end_use_link_decisions.tsv: bad action {r['action']}")
            if not r["rationale"].strip():
                raise ValueError("curated_end_use_link_decisions.tsv: missing rationale")
            dec[(r["industry_id"], r["commodity_id"])] = r
    out, index, used = [], {}, set()
    for l in links:
        d = dec.get((l["industry_id"], l["commodity_id"]))
        if d:
            used.add((l["industry_id"], l["commodity_id"]))
            if d["action"] == "drop":
                continue
            subs = [x.strip() for x in (d.get("drop_quotes") or "").split("||") if x.strip()]
            if subs:
                l["evidence_quotes"] = [q for q in l["evidence_quotes"] if not any(x in q["quote"] for x in subs)]
                if not l["evidence_quotes"]:
                    continue
                l["books"] = sorted({q["work"] for q in l["evidence_quotes"]}); l["book_count"] = len(l["books"])
            if d["action"] == "repoint":
                c = concepts.get(d["target"])
                if not c:
                    raise ValueError(f"curated_end_use_link_decisions.tsv: target {d['target']} not found")
                a = c.get("wikidata_anchor") or {}
                l.update({"commodity_id": c["concept_id"], "commodity_label": c["skos_prefLabel"],
                          "attestation_basis": c.get("attestation_basis", "customs_enumerated"),
                          "layer1_rows": c.get("total_rows", 0), "commodity_group": c["ontology"]["group_label"],
                          "wikidata_qid": a.get("qid", "")})
            if d.get("new_role"):
                if d["new_role"] not in ROLE_LABELS:
                    raise ValueError(f"curated_end_use_link_decisions.tsv: unknown role {d['new_role']}")
                l["production_role"], l["production_role_label"] = d["new_role"], ROLE_LABELS[d["new_role"]]
            l["curation"] = {"action": d["action"], "rationale": d["rationale"]}
        key = (l["industry_id"], l["commodity_id"])
        if key in index:  # re-pointed onto an existing link: merge evidence
            tgt = index[key]
            seen = {q["quote"] for q in tgt["evidence_quotes"]}
            tgt["evidence_quotes"] += [q for q in l["evidence_quotes"] if q["quote"] not in seen]
            tgt["books"] = sorted(set(tgt["books"]) | set(l["books"])); tgt["book_count"] = len(tgt["books"])
            tgt["mention_count"] += l["mention_count"]
            continue
        index[key] = l
        out.append(l)
    stale = sorted(set(dec) - used)
    if stale:
        print(f"NOTE: {len(stale)} curated link decisions matched no mined link: {stale[:10]}", flush=True)
    return out


def main():
    resolved = resolve_canonical_concepts()
    # Pre-index matchers by industry for fast inner loop!
    by_ind_matchers = defaultdict(list)
    for item in resolved:
        for ind_id in item["role_map"].keys():
            by_ind_matchers[ind_id].append(item)
    print(f"Resolved {len(resolved)} canonical commodities across {len(INDUSTRIES)} industries.", flush=True)

    evidence = defaultdict(lambda: {"concept": None, "role": "", "works": set(), "quotes": [], "mentions": 0})
    pages_scanned = 0

    def add_quote(rec, wid, cit, uri, quote_txt, score, mode):
        rec["works"].add(wid)
        rec["mentions"] += 1
        existing_works = {q["work"] for q in rec["quotes"]}
        if len(rec["quotes"]) < 4 or wid not in existing_works:
            rec["quotes"].append({
                "work": wid, "citation": cit, "uri": uri,
                "quote": quote_txt[:360] + ("..." if len(quote_txt) > 360 else ""),
                "score": round(score, 1), "mode": mode,
            })
            rec["quotes"].sort(key=lambda x: -x["score"])
            dedup_q, seen_w = [], set()
            for q in rec["quotes"]:
                if q["work"] not in seen_w:
                    dedup_q.append(q)
                    seen_w.add(q["work"])
                if len(dedup_q) >= 3:
                    break
            rec["quotes"] = dedup_q

    # Mode A + B: Full-text scan across all 6 books + exact Ure essay spans
    for wid, cit, uri, raw_text, essay_ind in iter_all_corpus_pages():
        pages_scanned += 1
        page_inds = set()
        if essay_ind:
            page_inds.add(essay_ind)
        for ind_id, cfg in INDUSTRIES.items():
            if cfg["trigger_re"].search(raw_text):
                page_inds.add(ind_id)
        if not page_inds:
            continue

        for raw_sent in split_sentences(raw_text):
            sent = clean_sentence(raw_sent)
            if len(sent) < 40 or len(sent) > 520:
                continue
            if TARIFF_NOISE_RE.search(sent):
                continue
            if sent.count(",") >= 8 or len(re.findall(r"\b\d{3,}\b", sent)) >= 3:
                continue
            if not USE_SIGNAL_RE.search(sent):
                continue

            sent_inds = set()
            for ind_id in page_inds:
                cfg = INDUSTRIES[ind_id]
                if cfg["trigger_re"].search(sent) and not (cfg["neg_re"] and cfg["neg_re"].search(sent)):
                    sent_inds.add(ind_id)
            if essay_ind and not sent_inds:
                cfg = INDUSTRIES[essay_ind]
                if not (cfg["neg_re"] and cfg["neg_re"].search(sent)) and re.search(
                    r"\b(ingredient|added|mixed|boiled|melted|dissolved|fused|smelted|solution|mordant|thicken\w*|dyed|printed|saponif|tanning|alkali|oil|fat|tallow|paste|cacao|chocolate|sugar|spice|flavour|scent|bleach|colour|color|decoction|gallons?|pounds?|ounces?|bath|vat|gum|resin|bark|pulp|furnace|crucible)\b",
                    sent, re.I,
                ):
                    sent_inds.add(essay_ind)
            if not sent_inds:
                continue

            for ind_id in sent_inds:
                has_direct = bool(INDUSTRIES[ind_id]["trigger_re"].search(sent))
                q_score = (100 if has_direct else 45) + (20 if wid == "ure_gutenberg" else 15 if wid in ("simmonds_1854", "simmonds_1892") else 10) - abs(len(sent) - 180) / 20.0
                for item in by_ind_matchers[ind_id]:
                    if not item["rx"].search(sent):
                        continue
                    c = item["concept"]
                    rec = evidence[(ind_id, c["concept_id"])]
                    rec["concept"] = c
                    rec["role"] = item["role_map"][ind_id]
                    add_quote(rec, wid, cit, uri, sent, q_score, "direct_sentence" if has_direct else "essay_context")

    # Mode C: Dictionary Headword + Definition Pairing (`commercial_dictionaries_lexicon.jsonl`)
    lex_path = DICT_DIR / "commercial_dictionaries_lexicon.jsonl"
    if lex_path.exists():
        for line in open(lex_path, encoding="utf-8"):
            if not line.strip():
                continue
            e = json.loads(line)
            hw = (e.get("headword") or "").strip()
            defn = clean_sentence(e.get("definition") or "")
            if not hw or len(defn) < 25 or TARIFF_NOISE_RE.search(defn):
                continue
            matched_inds = [
                ind_id for ind_id, cfg in INDUSTRIES.items()
                if cfg["trigger_re"].search(defn) and not (cfg["neg_re"] and cfg["neg_re"].search(defn))
            ]
            if not matched_inds:
                continue
            for ind_id in matched_inds:
                for item in by_ind_matchers[ind_id]:
                    if not item["rx"].search(hw):
                        continue
                    c = item["concept"]
                    rec = evidence[(ind_id, c["concept_id"])]
                    rec["concept"] = c
                    rec["role"] = item["role_map"][ind_id]
                    add_quote(rec, e["source_work"], e["source_citation"], e["source_uri"], f"{hw}: {defn}", 135.0, "direct_sentence")

    print(f"Scanned {pages_scanned:,} full-text pages across all 6 books.", flush=True)

    # Assemble verified links (require >= 1 direct quote OR >= 2 essay_context mentions)
    links = []
    for (ind_id, cid), rec in sorted(evidence.items(), key=lambda x: (x[0][0], -len(x[1]["works"]), -x[1]["mentions"])):
        if not rec["quotes"]:
            continue
        has_any_direct = any(q["mode"] == "direct_sentence" for q in rec["quotes"])
        if not has_any_direct and rec["mentions"] < 2:
            continue
        c = rec["concept"]
        a = c.get("wikidata_anchor") or {}
        links.append({
            "industry_id": ind_id,
            "industry_label": INDUSTRIES[ind_id]["label"],
            "industry_sector": INDUSTRIES[ind_id]["sector"],
            "commodity_id": cid,
            "commodity_label": c["skos_prefLabel"],
            "attestation_basis": c.get("attestation_basis", "customs_enumerated"),
            "layer1_rows": c.get("total_rows", 0),
            "commodity_group": c["ontology"]["group_label"],
            "production_role": rec["role"],
            "production_role_label": ROLE_LABELS[rec["role"]],
            "wikidata_qid": a.get("qid", ""),
            "book_count": len(rec["works"]),
            "books": sorted(rec["works"]),
            "mention_count": rec["mentions"],
            "evidence_quotes": [
                {"work": q["work"], "citation": q["citation"], "uri": q["uri"], "quote": q["quote"], "mode": q["mode"]}
                for q in rec["quotes"]
            ],
        })

    links = apply_curated_link_decisions(links)

    # 1. Export flat TSV + JSONL
    (GROUND / "end_use_network_links.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in links) + "\n", encoding="utf-8"
    )
    with open(GROUND / "end_use_network_links.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow([
            "industry_id", "industry_label", "industry_sector", "commodity_id", "commodity_label",
            "attestation_basis", "layer1_rows", "commodity_group",
            "production_role", "production_role_label", "wikidata_qid",
            "book_count", "mention_count", "books", "primary_citation", "primary_uri", "primary_quote",
        ])
        for r in links:
            q0 = r["evidence_quotes"][0]
            w.writerow([
                r["industry_id"], r["industry_label"], r["industry_sector"], r["commodity_id"], r["commodity_label"],
                r["attestation_basis"], r["layer1_rows"], r["commodity_group"],
                r["production_role"], r["production_role_label"], r["wikidata_qid"],
                r["book_count"], r["mention_count"], "; ".join(r["books"]),
                q0["citation"], q0["uri"], q0["quote"],
            ])

    # 2. Export LINCS-Compliant SKOS / CIDOC-CRM Overlay (`end_use_network_skos.{ttl,jsonld}`)
    top_ids = list(INDUSTRIES.keys())
    ttl_lines = [
        f"@prefix htc: <{BASE_URI}> .",
        f"@prefix oe: <{OE_NS}> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "# ============================================================================",
        "# OPEN EMPIRE — 18-INDUSTRY END-USE OVERLAY NETWORK (LINCS / SKOS / CIDOC-CRM)",
        "# ============================================================================",
        "oe:industry_scheme a skos:ConceptScheme ;",
        '    rdfs:label "Open Empire 19th-Century Manufacturing End-Use Scheme"@en ;',
        '    dcterms:title "Open Empire 19th-Century Manufacturing End-Use Scheme"@en ;',
        f'    dcterms:created "{TODAY}"^^xsd:date ;',
        f"    skos:hasTopConcept {', '.join(top_ids)} .",
        "",
        'oe:usedInIndustry a owl:ObjectProperty ; rdfs:label "commodity used as input in manufacturing industry"@en ; rdfs:domain skos:Concept ; rdfs:range skos:Concept ; owl:inverseOf oe:usesCommodityInput .',
        'oe:usesCommodityInput a owl:ObjectProperty ; rdfs:label "manufacturing industry employs commodity input"@en ; rdfs:domain skos:Concept ; rdfs:range skos:Concept ; owl:inverseOf oe:usedInIndustry .',
        "",
    ]

    jld_graph = [
        {
            "@id": "oe:industry_scheme", "@type": "skos:ConceptScheme",
            "rdfs:label": {"@value": "Open Empire 19th-Century Manufacturing End-Use Scheme", "@language": "en"},
            "dcterms:title": {"@value": "Open Empire 19th-Century Manufacturing End-Use Scheme", "@language": "en"},
            "dcterms:created": {"@value": TODAY, "@type": "xsd:date"},
            "skos:hasTopConcept": [{"@id": k} for k in top_ids],
        },
        {
            "@id": "oe:usedInIndustry", "@type": "owl:ObjectProperty",
            "rdfs:label": {"@value": "commodity used as input in manufacturing industry", "@language": "en"},
            "rdfs:domain": {"@id": "skos:Concept"}, "rdfs:range": {"@id": "skos:Concept"},
            "owl:inverseOf": {"@id": "oe:usesCommodityInput"},
        },
        {
            "@id": "oe:usesCommodityInput", "@type": "owl:ObjectProperty",
            "rdfs:label": {"@value": "manufacturing industry employs commodity input", "@language": "en"},
            "rdfs:domain": {"@id": "skos:Concept"}, "rdfs:range": {"@id": "skos:Concept"},
            "owl:inverseOf": {"@id": "oe:usedInIndustry"},
        },
    ]

    by_ind = defaultdict(list)
    by_comm = defaultdict(list)
    for r in links:
        by_ind[r["industry_id"]].append(r)
        by_comm[r["commodity_id"]].append(r)

    for ind_id, cfg in INDUSTRIES.items():
        inputs = [r["commodity_id"] for r in by_ind[ind_id]]
        triples = [
            "a skos:Concept, crm:E55_Type",
            f"rdfs:label {ttl_str(cfg['label'])}@en",
            "skos:inScheme oe:industry_scheme",
            "skos:topConceptOf oe:industry_scheme",
            f"skos:prefLabel {ttl_str(cfg['label'])}@en",
            f"skos:definition {ttl_str(cfg['description'])}@en",
        ]
        node = {
            "@id": ind_id, "@type": ["skos:Concept", "crm:E55_Type"],
            "rdfs:label": {"@value": cfg["label"], "@language": "en"},
            "skos:inScheme": {"@id": "oe:industry_scheme"},
            "skos:topConceptOf": {"@id": "oe:industry_scheme"},
            "skos:prefLabel": {"@value": cfg["label"], "@language": "en"},
            "skos:definition": {"@value": cfg["description"], "@language": "en"},
        }
        if inputs:
            triples.append("oe:usesCommodityInput " + ", ".join(inputs))
            node["oe:usesCommodityInput"] = [{"@id": x} for x in inputs]
        ttl_lines.append(f"{ind_id} " + " ;\n    ".join(triples) + " .\n")
        jld_graph.append(node)

    for cid, clinks in sorted(by_comm.items()):
        inds = [r["industry_id"] for r in clinks]
        lbl = clinks[0]["commodity_label"]
        ttl_lines.append(
            f"{cid} a skos:Concept, crm:E55_Type ;\n"
            f"    rdfs:label {ttl_str(lbl)}@en ;\n"
            f"    oe:usedInIndustry {', '.join(inds)} .\n"
        )
        jld_graph.append({
            "@id": cid, "@type": ["skos:Concept", "crm:E55_Type"],
            "rdfs:label": {"@value": lbl, "@language": "en"},
            "oe:usedInIndustry": [{"@id": x} for x in inds],
        })

    (GROUND / "end_use_network_skos.ttl").write_text("\n".join(ttl_lines), encoding="utf-8")
    (GROUND / "end_use_network_skos.jsonld").write_text(json.dumps({
        "@context": {
            "htc": BASE_URI, "oe": OE_NS,
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "crm": "http://www.cidoc-crm.org/cidoc-crm/",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "owl": "http://www.w3.org/2002/07/owl#",
            "dcterms": "http://purl.org/dc/terms/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
        },
        "@graph": jld_graph,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. Export Industry Metadata JSON for the HTML explorer
    ind_meta_out = {
        ind_id: {
            "id": ind_id,
            "label": cfg["label"],
            "sector": cfg["sector"],
            "desc": cfg["description"],
        }
        for ind_id, cfg in INDUSTRIES.items()
    }
    (GROUND / "end_use_industries.json").write_text(json.dumps(ind_meta_out, indent=2, ensure_ascii=False), encoding="utf-8")

    # 4. Write Scholarly Markdown Report
    md = [
        "# 19th-Century Industrial End-Use Network Report (18 Major Manufacturing Industries)",
        "",
        f"Generated {TODAY} by `scripts/build_end_use_network.py` across **{pages_scanned:,} full-text pages** from 6 19th-century commercial & manufacturing books (Ure 1840, Simmonds 1854 & 1892, McCulloch 1880, Mortimer 1823, Watt 1908). Every quote is verbatim from the cited book; links were mined by keyword co-occurrence and then hand-reviewed (see `curated_end_use_link_decisions.tsv`) — co-occurrence alone is not proof of use.",
        "",
        f"**Totals:** **{len(INDUSTRIES)}** industries · **{len(links):,}** commodity→industry links · **{len(by_comm):,}** distinct commodities (`{sum(1 for c in by_comm if not c.startswith('htc:doc_'))}` Layer-1 customs + `{sum(1 for c in by_comm if c.startswith('htc:doc_'))}` Document-Attested) · **{sum(r['mention_count'] for r in links):,}** keyword-matched sentences (mentions; the links file shows up to 3 verbatim quotes per link).",
        "",
        "## Overview Table",
        "| Industry | Sector | Inputs | Layer-1 | Doc-Attested | Sentences | Top Multi-Book Inputs |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for ind_id, cfg in INDUSTRIES.items():
        lst = by_ind[ind_id]
        l1_n = sum(1 for r in lst if r["attestation_basis"] == "customs_enumerated")
        doc_n = len(lst) - l1_n
        m_n = sum(r["mention_count"] for r in lst)
        top6 = ", ".join(r["commodity_label"] for r in lst[:6])
        md.append(f"| **{cfg['label']}** (`{ind_id}`) | {cfg['sector']} | **{len(lst)}** | {l1_n} | {doc_n} | {m_n:,} | {top6} |")

    md.append("\n## Most Multi-Use Commodities (Cross-Industry Hubs)")
    md.append("| Commodity | Tier | # Industries | Industries |")
    md.append("|---|---|---:|---|")
    for cid, clinks in sorted(by_comm.items(), key=lambda x: (-len(x[1]), x[1][0]["commodity_label"]))[:25]:
        tier = "Layer-1" if not cid.startswith("htc:doc_") else "Doc-Attested"
        inames = ", ".join(r["industry_label"] for r in clinks)
        md.append(f"| `{cid}` **{clinks[0]['commodity_label']}** | {tier} | **{len(clinks)}** | {inames} |")

    (DICT_DIR / "END_USE_NETWORK_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"\n=== 18-INDUSTRY END-USE NETWORK COMPLETE ===")
    print(f"Total links: {len(links):,} across {len(by_comm):,} distinct commodities and {len(INDUSTRIES)} industries ({sum(r['mention_count'] for r in links):,} sentences)")
    for ind_id, cfg in INDUSTRIES.items():
        lst = by_ind[ind_id]
        l1_n = sum(1 for r in lst if r["attestation_basis"] == "customs_enumerated")
        top5 = ", ".join(f"{r['commodity_label']}({r['book_count']}b)" for r in lst[:6])
        print(f"  {cfg['label']:42s}: {len(lst):2d} ({l1_n:2d} L1 + {len(lst)-l1_n:2d} Doc) | {top5}")


if __name__ == "__main__":
    main()
