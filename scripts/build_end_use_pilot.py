#!/usr/bin/env python3
"""
3-Industry Primary-Source End-Use Pilot Builder:
  1. Soap Manufacture (`oe:ind_soap_manufacture`)
  2. Calico Cloth & Calico Printing (`oe:ind_calico_printing`)
  3. Chocolate & Confectionery (`oe:ind_chocolate_confectionery`)

Extracts commodity -> industrial end-use links directly from the FULL TEXT of our
6 OCR'd / Project Gutenberg 19th-century commercial & manufacturing books:
  - Andrew Ure, Dictionary of Arts, Manufactures, and Mines (PG #44562, 6.57M chars)
  - P. L. Simmonds, Commercial Products of the Vegetable Kingdom (1854, PG #15191)
  - P. L. Simmonds, Commercial Dictionary of Trade Products (1892, IA b21780535, Chandra-2 OCR)
  - George Watt, Commercial Products of India (1908, IA b31361584, Chandra-2 OCR)
  - J. R. McCulloch, Dictionary of Commerce (1880, IA dictionaryprac00mccu, Chandra-2 OCR)
  - Thomas Mortimer, General Commercial Dictionary (1823, IA generalcommercia00mort, Chandra-2 OCR)

Zero quantity estimation & zero unsourced links: every link is backed by at least
one verbatim primary-source quote with clickable Internet Archive / Project Gutenberg URI.

Outputs:
  - human_trade/layer1_human/grounding/end_use_pilot_links.tsv
  - human_trade/layer1_human/grounding/end_use_pilot_links.jsonl
  - human_trade/layer1_human/grounding/end_use_pilot_skos.ttl
  - human_trade/layer1_human/grounding/end_use_pilot_skos.jsonld
  - dictionaries/END_USE_PILOT_REPORT.md
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
BASE_URI = "https://openempire.hgis.usask.ca/vocab/commodities/"
OE_NS = "https://openempire.hgis.usask.ca/ontology/"

PAGE_MARK_RE = re.compile(r"^(\d+)-{35,}\s*$", re.M)

# 3 Pilot Industries
INDUSTRIES = {
    "oe:ind_soap_manufacture": {
        "label": "Soap Manufacture",
        "short": "Soap Manufacture",
        "description": (
            "19th-century hard, soft, yellow, mottled, curd, Castile, and toilet soap manufacture — "
            "combining animal tallow and tropical/vegetable oils with caustic alkalis (barilla, kelp, soda ash, potash, lime), "
            "rosin, common salt for salting out, and essential oils for scenting."
        ),
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
        "essay_heading_re": re.compile(r"(?:^|\n)\s*(?:\*\*)?SOAP(?:\s*,\s*MANUFACTURE\s+OF)?(?:\*\*)?[\.,]", re.M),
    },
    "oe:ind_calico_printing": {
        "label": "Calico Cloth & Calico Printing",
        "short": "Calico Cloth & Printing",
        "description": (
            "19th-century cotton weaving, bleaching, dyeing, and calico printing — combining raw cotton "
            "with bleaching powder and alkalis, natural and coal-tar dyestuffs (madder, indigo, logwood, cochineal, "
            "quercitron, fustic, sumach, alizarine), metallic mordants (alum, copperas, tin/lead/iron salts), "
            "and thickeners/sizing agents (gum senegal, gum arabic, starch, flour, albumen)."
        ),
        "trigger_re": re.compile(
            r"\b(calico[\s-]*print\w*|printing\s+calico\w*|printed\s+calico\w*|cotton[\s-]*print\w*|"
            r"calico\s+cloth|calicoes|sizing\s+(?:cotton|warps?|cloth|calico)|bleaching\s+(?:cotton|calico)|"
            r"dyeing\s+(?:cotton|calico)|turkey[\s-]*red|madder[\s-]*style|steam[\s-]*colou?rs?|"
            r"discharge\s+style|resist\s+paste|cotton\s+manufactur\w*|cotton[\s-]*dyers?)\b",
            re.I,
        ),
        "neg_re": None,
        "essay_heading_re": re.compile(r"(?:^|\n)\s*(?:\*\*)?CALICO[\s-]*PRINTING(?:\*\*)?[\.,]", re.M),
    },
    "oe:ind_chocolate_confectionery": {
        "label": "Chocolate & Confectionery",
        "short": "Chocolate & Confectionery",
        "description": (
            "19th-century chocolate bars, drinking chocolate, cocoa preparations, and sugar confectionery — "
            "combining roasted cacao beans and cocoa butter with cane sugar, aromatic spices "
            "(vanilla, cinnamon, cassia, cloves, cardamom, nutmeg), farinaceous thickeners/admixtures "
            "(arrowroot, sago, starch, flour), gums, almonds, and condensed milk."
        ),
        "trigger_re": re.compile(
            r"\b(making\s+chocolate|manufactur\w*\s+of\s+chocolate|used\s+(?:in|for)\s+(?:making\s+)?chocolate|"
            r"flavour\w*\s+chocolate|flavor\w*\s+chocolate|chocolate[\s-]*mak\w*|chocolate[\s-]*paste|"
            r"chocolate\s+(?:bars?|cakes?|is\s+made|prepared|mixed|manufactured)|butter\s+of\s+cacao|cocoa[\s-]*butter|"
            r"confectioner(?:y|s)?|sweetmeats?|lozenges?|bon[\s-]*bons?|sugar[\s-]*plums?)\b",
            re.I,
        ),
        "neg_re": re.compile(r"\b(topical\s+chocolate|chocolate\s+(?:colour|color|brown|dye|shade)|acetate\s+of\s+alumina|calico[\s-]*print|mordant)\b", re.I),
        "essay_heading_re": re.compile(r"(?:^|\n)\s*(?:\*\*)?CHOCOLATE(?:\*\*)?[\.,]", re.M),
    },
}

# Context guard: sentence must describe material/process/use, NOT purely customs tariffs or shipping tables
USE_SIGNAL_RE = re.compile(
    r"\b(used|employ\w*|made|making|manufactur\w*|prepar\w*|mix\w*|boil\w*|add\w*|combin\w*|"
    r"flavour\w*|flavor\w*|scent\w*|perfum\w*|dye\w*|print\w*|bleach\w*|thicken\w*|siz\w*|"
    r"mordant\w*|saponif\w*|yield\w*|afford\w*|produc\w*|contain\w*|consist\w*|ingredient\w*|"
    r"chief\w*|largely|extensively|much|valuable|adapt\w*|suit\w*|substitut\w*|adulterat\w*|"
    r"paste|liquor|bath|vat|solution|oil|fat|alkali|lye|ley|curd|cake|bar|sweet|colour|color|"
    r"red|blue|yellow|black|purple|crimson|scarlet|green|brown|white|orange)\b",
    re.I,
)
TARIFF_NOISE_RE = re.compile(
    r"(?:£\s*\d|s\.\s*\d+d\.|\d+\s+Geo\.\s*\d|\d+\s+Vict\.|duty\s+of\s+\d|imported\s+in\s+18\d\d.*\d{3,}|"
    r"table\s+of\s+imports|total\s+value\s+£|duty[\s-]*free\s+goods|from\s+[A-Z][a-z]+\s+they\s+draw|"
    r"exports?\s+consist\s+of|imports?\s+consist\s+of|^See\s+[A-Z])",
    re.I,
)

# Role labels for UI & RDF
ROLE_LABELS = {
    "primary_feedstock": "Primary Feedstock / Base Material",
    "alkali_or_reagent": "Alkali, Acid & Chemical Reagent",
    "dye_or_colorant": "Dyestuff, Dyewood & Pigment",
    "mordant_or_fixer": "Mordant, Tannin & Colour Fixer",
    "thickener_or_sizing": "Thickener, Gum & Warp Sizing",
    "bleaching_agent": "Bleaching Agent",
    "flavouring_or_scent": "Flavouring, Spice & Perfume",
    "filler_or_admixture": "Binder, Dairy & Farinaceous Admixture",
}

# High-precision canonical commodity surface patterns mapped to normalized lookup keys in our SKOS vocab.
# Every pattern is matched against our verified Layer-1 (2,066) + Document-Attested (601) concepts dynamically!
# Tuple: (canonical_label_query, regex_pattern, allowed_industries_or_None, industry_role_overrides)
CANONICAL_PATTERNS = [
    # --- Fats, Oils, Waxes & Rosin ---
    ("Tallow", r"\b(?:tallow|russian\s+tallow|mutton\s+tallow|beef\s+tallow|vegetable\s+tallow)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Palm Oil", r"\bpalm[\s-]*oil\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Cocoa-nut Oil", r"\b(?:coco[\s-]*nut|cocoa[\s-]*nut)[\s-]*oil\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Olive Oil", r"\b(?:olive[\s-]*oil|gallipoli\s+oil|sweet\s+oil)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_calico_printing": "alkali_or_reagent"}),
    ("Lard", r"\b(?:hog'?s?\s+lard|lard)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Rosin", r"\b(?:rosin|colophony|yellow\s+resin|pine\s+resin)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_calico_printing": "thickener_or_sizing"}),
    ("Oil Seed", r"\b(?:linseed[\s-]*oil|hemp[\s-]*seed[\s-]*oil|rape[\s-]*seed[\s-]*oil|colza[\s-]*oil|cotton[\s-]*seed[\s-]*oil)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Oil Castor", r"\bcastor[\s-]*oil\b", None, {"oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_calico_printing": "alkali_or_reagent"}),
    ("Shea Butter", r"\b(?:shea[\s-]*butter|galam[\s-]*butter|bassia\s+oil|mahua\s+oil|mowra\s+oil|illipe)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Sesame", r"\b(?:sesame[\s-]*oil|gingelly[\s-]*oil|til[\s-]*oil|teel[\s-]*oil|benne[\s-]*oil)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Ground nut", r"\b(?:ground[\s-]*nut[\s-]*oil|earth[\s-]*nut[\s-]*oil|arachis[\s-]*oil)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Neem Oil", r"\b(?:neem[\s-]*oil|margosa[\s-]*oil)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Poppy Seed Oil", r"\bpoppy[\s-]*seed[\s-]*oil\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Almond Oil", r"\balmond[\s-]*oil\b", None, {"oe:ind_soap_manufacture": "primary_feedstock", "oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Train or Blubber (Whale Oils)", r"\b(?:whale[\s-]*oil|train[\s-]*oil|fish[\s-]*oil|seal[\s-]*oil|cod[\s-]*oil)\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Spermaceti", r"\bspermaceti\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Glycerine", r"\bglycerin[e]?\b", None, {"oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "thickener_or_sizing"}),
    ("Stearine", r"\bstearin[e]?\b", None, {"oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Beeswax", r"\b(?:bees[\s-]*wax|white\s+wax)\b", None, {"oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_soap_manufacture": "primary_feedstock"}),

    # --- Alkalis, Salts, Acids & Bleaching Reagents ---
    ("Alkali", r"\b(?:soda[\s-]*ash|caustic\s+soda|carbonate\s+of\s+soda|subcarbonate\s+of\s+soda|crystals\s+of\s+soda|black[\s-]*ash|alkali|soda\s+ley|soda\s+lye|natron)\b", None, {"oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "bleaching_agent"}),
    ("Barilla", r"\bbarilla\b", None, {"oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "bleaching_agent"}),
    ("Kelp", r"\bkelp\b", None, {"oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "bleaching_agent"}),
    ("Pearl and Pot Ashes", r"\b(?:potash|pot[\s-]*ash|pearl[\s-]*ash|wood[\s-]*ash(?:es)?|caustic\s+potash|carbonate\s+of\s+potash)\b", None, {"oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "bleaching_agent"}),
    ("Salt", r"\b(?:common\s+salt|sea[\s-]*salt|rock[\s-]*salt|muriate\s+of\s+soda|bay[\s-]*salt|cat[\s-]*salt)\b", None, {"oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "alkali_or_reagent"}),
    ("Manufactures Lime", r"\b(?:quick[\s-]*lime|caustic\s+lime|slaked\s+lime|milk\s+of\s+lime|lime[\s-]*water)\b", None, {"oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "bleaching_agent"}),
    ("Bleaching Materials", r"\b(?:bleaching[\s-]*powder|chloride\s+of\s+lime|chlorine|hypochlorite|eau\s+de\s+javelle)\b", None, {"oe:ind_calico_printing": "bleaching_agent", "oe:ind_soap_manufacture": "bleaching_agent"}),
    ("Sulphuric Acid", r"\b(?:sulphuric\s+acid|oil\s+of\s+vitriol|vitriol)\b", None, {"oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_soap_manufacture": "alkali_or_reagent"}),
    ("Muriatic Acid", r"\b(?:muriatic\s+acid|hydrochloric\s+acid|spirit\s+of\s+salt)\b", None, {"oe:ind_calico_printing": "alkali_or_reagent"}),
    ("Nitric acid", r"\b(?:nitric\s+acid|aqua[\s-]*fortis)\b", None, {"oe:ind_calico_printing": "alkali_or_reagent"}),
    ("Tartaric Acid", r"\b(?:tartaric\s+acid|cream\s+of\s+tartar|argol|tartar)\b", None, {"oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_chocolate_confectionery": "alkali_or_reagent"}),
    ("Citric Acid", r"\b(?:citric\s+acid|lemon[\s-]*juice|lime[\s-]*juice)\b", None, {"oe:ind_calico_printing": "alkali_or_reagent", "oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Oxalic Acid", r"\boxalic\s+acid\b", None, {"oe:ind_calico_printing": "alkali_or_reagent"}),
    ("Chemical Manufactures Acetic Acid", r"\b(?:acetic\s+acid|pyroligneous\s+acid|vinegar)\b", None, {"oe:ind_calico_printing": "alkali_or_reagent"}),
    ("Bichromate", r"\b(?:bichromate\s+of\s+potash|chromate\s+of\s+potash|chrome\s+yellow|chromate\s+of\s+lead)\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Prussiate of Potash", r"\b(?:prussiate\s+of\s+potash|prussian\s+blue|ferrocyanide)\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Manganese Ore", r"\b(?:manganese|oxide\s+of\s+manganese|manganese\s+brown)\b", None, {"oe:ind_calico_printing": "bleaching_agent"}),
    ("Arsenic", r"\b(?:arsenic|arseniate\s+of\s+soda|orpiment|realgar)\b", None, {"oe:ind_calico_printing": "alkali_or_reagent"}),
    ("Borax", r"\bborax\b", None, {"oe:ind_soap_manufacture": "alkali_or_reagent", "oe:ind_calico_printing": "alkali_or_reagent"}),
    ("Sal Ammoniac", r"\b(?:sal[\s-]*ammoniac|muriate\s+of\s+ammonia)\b", None, {"oe:ind_calico_printing": "alkali_or_reagent"}),

    # --- Cotton & Calico Dyestuffs, Mordants, Thickeners ---
    ("Cotton Raw", r"\b(?:raw\s+cotton|cotton\s+wool|cotton\s+cloth|cotton\s+yarn|cotton\s+fabric|calico\s+cloth|cotton\s+piece[\s-]*goods)\b", {"oe:ind_calico_printing"}, {"oe:ind_calico_printing": "primary_feedstock"}),
    ("Madder", r"\b(?:madder|madder[\s-]*root|rubia\s+tinctorum)\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Garancine", r"\bgarancin[e]?\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Alizarine", r"\balizarin[e]?\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Indigo", r"\bindigo\b", None, {"oe:ind_calico_printing": "dye_or_colorant", "oe:ind_soap_manufacture": "dye_or_colorant"}),
    ("Dye Woods Logwood", r"\blog[\s-]*wood\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Cochineal", r"\bcochineal\b", None, {"oe:ind_calico_printing": "dye_or_colorant", "oe:ind_chocolate_confectionery": "dye_or_colorant"}),
    ("Quercitron", r"\bquercitron\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Dye Woods Fustic", r"\bfustic\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Brazil wood", r"\b(?:brazil[\s-]*wood|peach[\s-]*wood|lima[\s-]*wood|sappan[\s-]*wood|sapan[\s-]*wood)\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Camwood", r"\b(?:cam[\s-]*wood|bar[\s-]*wood)\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Safflower", r"\bsafflower\b", None, {"oe:ind_calico_printing": "dye_or_colorant", "oe:ind_chocolate_confectionery": "dye_or_colorant"}),
    ("Annatto Flag", r"\b(?:annatto|anatto|arnatto|arnotto|roucou)\b", None, {"oe:ind_calico_printing": "dye_or_colorant", "oe:ind_soap_manufacture": "dye_or_colorant", "oe:ind_chocolate_confectionery": "dye_or_colorant"}),
    ("Turmeric", r"\bturmeric\b", None, {"oe:ind_calico_printing": "dye_or_colorant", "oe:ind_soap_manufacture": "dye_or_colorant"}),
    ("Lac Dye", r"\blac[\s-]*dye\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Weld", r"\bweld\b", {"oe:ind_calico_printing"}, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Berries Yellow", r"\b(?:persian\s+berries|avignon\s+berries|yellow\s+berries|french\s+berries)\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Munjut", r"\b(?:munjeet|manjit|munjut)\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Ultramarine", r"\bultramarine\b", None, {"oe:ind_calico_printing": "dye_or_colorant", "oe:ind_soap_manufacture": "dye_or_colorant"}),
    ("Coal Tar Dyes", r"\b(?:aniline\s+dye|aniline\s+colou?r|coal[\s-]*tar\s+dye|magenta|mauve|fuchsine)\b", None, {"oe:ind_calico_printing": "dye_or_colorant"}),
    ("Alum", r"\b(?:alum|acetate\s+of\s+alumina|red\s+liquor|aluminous\s+mordant)\b", None, {"oe:ind_calico_printing": "mordant_or_fixer"}),
    ("Copperas", r"\b(?:copperas|sulphate\s+of\s+iron|iron\s+liquor|acetate\s+of\s+iron|pyrolignite\s+of\s+iron|nitrate\s+of\s+iron|green\s+vitriol)\b", None, {"oe:ind_calico_printing": "mordant_or_fixer", "oe:ind_soap_manufacture": "dye_or_colorant"}),
    ("Blue Vitriol", r"\b(?:blue\s+vitriol|sulphate\s+of\s+copper|acetate\s+of\s+copper|verdigris|nitrate\s+of\s+copper)\b", None, {"oe:ind_calico_printing": "mordant_or_fixer"}),
    ("Lead Pig and Sheet", r"\b(?:sugar\s+of\s+lead|acetate\s+of\s+lead|nitrate\s+of\s+lead)\b", None, {"oe:ind_calico_printing": "mordant_or_fixer"}),
    ("Tin", r"\b(?:muriate\s+of\s+tin|chloride\s+of\s+tin|stannate\s+of\s+soda|salts?\s+of\s+tin|tin\s+liquor|tin\s+mordant)\b", None, {"oe:ind_calico_printing": "mordant_or_fixer"}),
    ("Shumach", r"\b(?:sumach|sumac|shumach)\b", None, {"oe:ind_calico_printing": "mordant_or_fixer"}),
    ("Galls", r"\b(?:gall[\s-]*nuts?|nut[\s-]*galls?|aleppo\s+galls?|galls\b)\b", None, {"oe:ind_calico_printing": "mordant_or_fixer"}),
    ("Cutch", r"\b(?:catechu|cutch|terra\s+japonica|gambier)\b", None, {"oe:ind_calico_printing": "mordant_or_fixer"}),
    ("Myrabolans", r"\bmyr[ao]b[ao]lans?\b", None, {"oe:ind_calico_printing": "mordant_or_fixer"}),
    ("Gum Senegal", r"\bgum[\s-]*senegal\b", None, {"oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Gum Arabic", r"\bgum[\s-]*arabic\b", None, {"oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Gum Tragacanth", r"\b(?:gum[\s-]*tragacanth|tragacanth)\b", None, {"oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Starch", r"\b(?:starch|british\s+gum|dextrin[e]?|calcined\s+starch|torrefied\s+starch|potato[\s-]*starch|wheat[\s-]*starch)\b", None, {"oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Wheat Meal and Flour", r"\b(?:wheat[\s-]*flour|flour\s+paste|wheaten\s+flour|flour)\b", None, {"oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Albumin", r"\b(?:albumen|albumin|blood[\s-]*albumen|egg[\s-]*albumen)\b", None, {"oe:ind_calico_printing": "thickener_or_sizing", "oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Bran", r"\bbran\b", {"oe:ind_calico_printing"}, {"oe:ind_calico_printing": "bleaching_agent"}),

    # --- Chocolate & Confectionery Feedstocks, Spices, Aromatics, Fillers ---
    ("Cocoa", r"\b(?:cocoa|cacao|cacao[\s-]*beans?|cocoa[\s-]*beans?|cocoa[\s-]*nibs?|butter\s+of\s+cacao|cocoa[\s-]*butter)\b", {"oe:ind_chocolate_confectionery", "oe:ind_soap_manufacture"}, {"oe:ind_chocolate_confectionery": "primary_feedstock", "oe:ind_soap_manufacture": "primary_feedstock"}),
    ("Sugar Unrefined", r"\b(?:sugar|cane[\s-]*sugar|refined\s+sugar|loaf[\s-]*sugar|white\s+sugar|brown\s+sugar|raw\s+sugar)\b", {"oe:ind_chocolate_confectionery", "oe:ind_soap_manufacture"}, {"oe:ind_chocolate_confectionery": "primary_feedstock", "oe:ind_soap_manufacture": "alkali_or_reagent"}),
    ("Molasses", r"\b(?:molasses|treacle)\b", {"oe:ind_chocolate_confectionery"}, {"oe:ind_chocolate_confectionery": "primary_feedstock"}),
    ("Honey", r"\bhoney\b", {"oe:ind_chocolate_confectionery", "oe:ind_soap_manufacture"}, {"oe:ind_chocolate_confectionery": "primary_feedstock", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Vanilla", r"\bvanilla\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Spices Cinnamon", r"\bcinnamon\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Spices Cassia Lignea", r"\b(?:cassia|cassia[\s-]*buds?|cassia[\s-]*lignea|cassia[\s-]*oil)\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Spices Cloves", r"\b(?:cloves?|oil\s+of\s+cloves?)\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Spices Nutmegs", r"\b(?:nutmegs?|mace\b)\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Cardamom", r"\bcardamoms?\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Pimento", r"\b(?:pimento|allspice)\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Ginger Raw", r"\bginger\b", {"oe:ind_chocolate_confectionery"}, {"oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Almonds", r"\b(?:almonds?|sweet\s+almonds?|bitter\s+almonds?)\b", None, {"oe:ind_chocolate_confectionery": "filler_or_admixture", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Arrowroot", r"\barrow[\s-]*root\b", {"oe:ind_chocolate_confectionery"}, {"oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Sago", r"\bsago\b", {"oe:ind_chocolate_confectionery", "oe:ind_calico_printing"}, {"oe:ind_chocolate_confectionery": "filler_or_admixture", "oe:ind_calico_printing": "thickener_or_sizing"}),
    ("Tapioca", r"\btapioca\b", {"oe:ind_chocolate_confectionery"}, {"oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Rice", r"\b(?:rice[\s-]*flour|ground\s+rice|rice[\s-]*starch)\b", None, {"oe:ind_chocolate_confectionery": "filler_or_admixture", "oe:ind_calico_printing": "thickener_or_sizing"}),
    ("Milk Condensed", r"\b(?:condensed\s+milk|cow'?s?\s+milk|milk)\b", {"oe:ind_chocolate_confectionery"}, {"oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Liquorice", r"\b(?:liquorice|licorice)\b", {"oe:ind_chocolate_confectionery"}, {"oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Caraway", r"\b(?:caraway|oil\s+of\s+caraway)\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Aniseed", r"\b(?:aniseed|anise|oil\s+of\s+anise)\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Coriander", r"\bcoriander\b", {"oe:ind_chocolate_confectionery"}, {"oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Peppermint", r"\b(?:peppermint|oil\s+of\s+peppermint)\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Lemons and Oranges", r"\b(?:orange[\s-]*peel|lemon[\s-]*peel|candied\s+peel|oil\s+of\s+lemons?|oil\s+of\s+orange)\b", None, {"oe:ind_chocolate_confectionery": "flavouring_or_scent", "oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Pistachio", r"\bpistachio\b", {"oe:ind_chocolate_confectionery"}, {"oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Isinglass", r"\b(?:isinglass|gelatine|gelatin)\b", {"oe:ind_chocolate_confectionery"}, {"oe:ind_chocolate_confectionery": "filler_or_admixture"}),
    ("Saffron", r"\bsaffron\b", {"oe:ind_chocolate_confectionery", "oe:ind_calico_printing"}, {"oe:ind_chocolate_confectionery": "dye_or_colorant", "oe:ind_calico_printing": "dye_or_colorant"}),

    # --- Essential Oils & Perfumes for Soap Scenting ---
    ("Citronella", r"\bcitronella\b", {"oe:ind_soap_manufacture"}, {"oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Bergamot", r"\bbergamot\b", None, {"oe:ind_soap_manufacture": "flavouring_or_scent", "oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Lavender Oil", r"\b(?:lavender[\s-]*oil|oil\s+of\s+lavender|spike\s+lavender)\b", {"oe:ind_soap_manufacture"}, {"oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Rosemary", r"\b(?:rosemary|oil\s+of\s+rosemary)\b", {"oe:ind_soap_manufacture"}, {"oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Thyme", r"\b(?:oil\s+of\s+thyme|thyme\s+oil)\b", {"oe:ind_soap_manufacture"}, {"oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Musk", r"\bmusk\b", {"oe:ind_soap_manufacture", "oe:ind_chocolate_confectionery"}, {"oe:ind_soap_manufacture": "flavouring_or_scent", "oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Ambergris", r"\bambergris\b", {"oe:ind_soap_manufacture", "oe:ind_chocolate_confectionery"}, {"oe:ind_soap_manufacture": "flavouring_or_scent", "oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Benzoin", r"\b(?:benzoin|gum[\s-]*benjamin)\b", {"oe:ind_soap_manufacture"}, {"oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Sandal wood", r"\b(?:sandal[\s-]*wood[\s-]*oil|oil\s+of\s+sandal[\s-]*wood)\b", {"oe:ind_soap_manufacture"}, {"oe:ind_soap_manufacture": "flavouring_or_scent"}),
    ("Otto of Roses", r"\b(?:otto\s+of\s+roses?|attar\s+of\s+roses?|rose[\s-]*water|oil\s+of\s+roses?)\b", None, {"oe:ind_soap_manufacture": "flavouring_or_scent", "oe:ind_chocolate_confectionery": "flavouring_or_scent"}),
    ("Vermilion", r"\b(?:vermilion|cinnabar)\b", {"oe:ind_soap_manufacture", "oe:ind_calico_printing"}, {"oe:ind_soap_manufacture": "dye_or_colorant", "oe:ind_calico_printing": "dye_or_colorant"}),
    ("Ochre", r"\b(?:red\s+ochre|yellow\s+ochre|ochre)\b", {"oe:ind_soap_manufacture", "oe:ind_calico_printing"}, {"oe:ind_soap_manufacture": "dye_or_colorant", "oe:ind_calico_printing": "dye_or_colorant"}),
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
    """Map every CANONICAL_PATTERNS query to a verified existing Layer-1 or Document-Attested concept ID."""
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
            # Substring fallback preferring Layer-1 with highest rows and shortest exact-ish title
            cands = [c for c in all_c if qn in norm_key(c["skos_prefLabel"])]
        if not cands:
            return None
        # Prefer Layer-1 (non-doc) with highest rows; avoid "Unenumerated" or "Manufactures" unless queried
        def score(c):
            is_l1 = 1 if not c["concept_id"].startswith("htc:doc_") else 0
            exact = 1 if norm_key(c["skos_prefLabel"]) == qn else 0
            unenum = -1 if "unenumerated" in c["skos_prefLabel"].lower() else 0
            return (exact * 100 + is_l1 * 20 + unenum * 50, c.get("total_rows", 0), -len(c["skos_prefLabel"]))
        return max(cands, key=score)

    resolved = []
    missing = []
    for query, pat, allowed_inds, role_map in CANONICAL_PATTERNS:
        c = pick_best(query)
        if not c:
            missing.append(query)
            continue
        resolved.append({
            "query": query,
            "concept": c,
            "rx": re.compile(pat, re.I),
            "allowed_inds": allowed_inds,
            "role_map": role_map,
        })
    if missing:
        print(f"Note: {len(missing)} patterns did not match an existing htc: concept (skipped): {missing}")
    return resolved


def iter_all_corpus_pages():
    """Yield (work_id, citation_prefix, page_num, uri, clean_text) across all 6 full-text books."""
    # 1. Project Gutenberg full texts (chunked into pseudo-pages of ~4,500 chars for fast sentence indexing)
    gut_specs = [
        ("ure_gutenberg", "Ure (1853), Dictionary of Arts, Manufactures, and Mines", "https://www.gutenberg.org/ebooks/44562", GUT_ROOT / "pg44562_ure_dictionary_arts_manufactures.txt"),
        ("simmonds_1854", "Simmonds (1854), Commercial Products of the Vegetable Kingdom", "https://www.gutenberg.org/ebooks/15191", GUT_ROOT / "pg15191_simmonds_1854_vegetable_kingdom.txt"),
    ]
    for wid, cit, uri, path in gut_specs:
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        # Strip Gutenberg boilerplate header/footer
        m_start = re.search(r"\*\*\*\s*START OF (?:THIS|THE) PROJECT GUTENBERG", raw)
        m_end = re.search(r"\*\*\*\s*END OF (?:THIS|THE) PROJECT GUTENBERG", raw)
        body = raw[m_start.end():m_end.start()] if (m_start and m_end) else raw
        chunk_sz = 5000
        for i in range(0, len(body), chunk_sz):
            yield (wid, cit, (i // chunk_sz) + 1, uri, body[i:i + chunk_sz + 300])

    # 2. All 4 Chandra-2 OCR'd books in dictionaries_all (exact PDF page numbers & clickable IA page URIs!)
    ia_specs = {
        "b21780535": ("simmonds_1892", "Simmonds (1892), Commercial Dictionary of Trade Products"),
        "b31361584": ("watt_1908", "Watt (1908), Commercial Products of India"),
        "dictionaryprac00mccu": ("mcculloch_1880", "McCulloch (1880), Dictionary of Commerce"),
        "generalcommercia00mort": ("mortimer_1823", "Mortimer (1823), General Commercial Dictionary"),
    }
    for ia_id, (wid, cit) in ia_specs.items():
        bundles = sorted(OCR_ROOT.glob(f"{ia_id}_p*/{ia_id}/{ia_id}.md"))
        for md_path in bundles:
            m_b = re.search(r"_p(\d+)", md_path.parent.parent.name)
            base_page = int(m_b.group(1)) if m_b else 1
            txt = md_path.read_text(encoding="utf-8", errors="ignore")
            parts = PAGE_MARK_RE.split(txt)
            # parts = [pre, pnum1, body1, pnum2, body2, ...]
            if len(parts) < 3:
                yield (wid, f"{cit}, p. {base_page}", base_page, f"https://archive.org/details/{ia_id}/page/n{base_page}/mode/1up", txt)
            else:
                for idx in range(1, len(parts), 2):
                    rel_p = int(parts[idx])
                    pdf_p = base_page + rel_p - 1 if rel_p <= 30 else rel_p
                    body = parts[idx + 1]
                    uri = f"https://archive.org/details/{ia_id}/page/n{pdf_p}/mode/1up"
                    yield (wid, f"{cit}, p. {pdf_p}", pdf_p, uri, body)


def clean_sentence(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[*_#]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_sentences(text: str):
    # Join hyphenated linebreaks & normalize whitespace before sentence splitting
    text = re.sub(r"-\s*\n\s*", "", text)
    # Break cleanly before ALL-CAPS dictionary headwords so adjacent entries never bleed into one sentence
    text = re.sub(r"(?<=[\.\?!])\s+(?=[A-Z]{4,}(?:[\s\-][A-Z]{2,})?[,\.\(])", "\n<ENTRY>\n", text)
    text = re.sub(r"[ \t\r]+", " ", text)
    # Protect common 19th-c. abbreviations before splitting
    prot = re.sub(r"\b(Mr|Dr|St|vs|No|pp|cf|oz|lb|lbs|cwt|vol|ed|fig|sec|stat|Geo|Vict|Fr|Germ|Lat|etc)\.", r"\1<DOT>", text)
    out = []
    for block in prot.split("<ENTRY>"):
        for s in re.split(r"(?<=[\.\?!])\s+(?=[A-Z])", block.strip()):
            s = s.replace("<DOT>", ".").strip()
            if s:
                out.append(s)
    return out


def main():
    resolved = resolve_canonical_concepts()
    print(f"Resolved {len(resolved)} canonical commodity matchers against verified htc: vocabulary.", flush=True)

    # Track evidence per (industry_id, concept_id)
    # Value: {"concept": c, "role": role, "works": set(), "quotes": [], "mentions": 0}
    evidence = defaultdict(lambda: {"concept": None, "role": "", "works": set(), "quotes": [], "mentions": 0})
    pages_scanned = 0
    essay_pages = Counter()

    # Track whether we are inside a multi-page dedicated essay in a given work
    active_essay = {}  # work_id -> (industry_id, remaining_pages)

    for wid, cit, pnum, uri, raw_text in iter_all_corpus_pages():
        pages_scanned += 1

        # Detect start of dedicated industry essays (SOAP / CALICO-PRINTING / CHOCOLATE) in Ure, McCulloch, Mortimer
        cur_essay_ind = None
        if wid in ("ure_gutenberg", "mcculloch_1880", "mortimer_1823", "simmonds_1854"):
            for ind_id, cfg in INDUSTRIES.items():
                if cfg["essay_heading_re"].search(raw_text):
                    active_essay[wid] = (ind_id, 4 if wid == "ure_gutenberg" else 2)
                    break
            if wid in active_essay:
                ind_id, rem = active_essay[wid]
                cur_essay_ind = ind_id
                essay_pages[(wid, ind_id)] += 1
                if rem <= 1:
                    del active_essay[wid]
                else:
                    active_essay[wid] = (ind_id, rem - 1)

        # Quick pre-filter: skip page if NO industry trigger and NOT inside an active essay
        page_inds = set()
        if cur_essay_ind:
            page_inds.add(cur_essay_ind)
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

            # Determine which industry(ies) this specific sentence attests
            sent_inds = set()
            for ind_id in page_inds:
                cfg = INDUSTRIES[ind_id]
                if cfg["trigger_re"].search(sent) and not (cfg["neg_re"] and cfg["neg_re"].search(sent)):
                    sent_inds.add(ind_id)
            if cur_essay_ind and not sent_inds:
                cfg = INDUSTRIES[cur_essay_ind]
                # Inside a dedicated SOAP / CALICO-PRINTING / CHOCOLATE essay, require strong ingredient/recipe context
                if not (cfg["neg_re"] and cfg["neg_re"].search(sent)) and re.search(r"\b(ingredient|added|mixed|boiled|solution|mordant|thickened|dyed|printed|saponif|alkali|oil|fat|tallow|paste|cacao|chocolate|sugar|spice|flavour|scent|bleach|colour|color)\b", sent, re.I):
                    sent_inds.add(cur_essay_ind)
            if not sent_inds:
                continue

            for item in resolved:
                if not item["rx"].search(sent):
                    continue
                c = item["concept"]
                cid = c["concept_id"]
                for ind_id in sent_inds:
                    if item["allowed_inds"] is not None and ind_id not in item["allowed_inds"]:
                        continue
                    role = item["role_map"].get(ind_id)
                    if not role:
                        # Fallback role from commodity group only if allowed
                        continue
                    rec = evidence[(ind_id, cid)]
                    rec["concept"] = c
                    rec["role"] = role
                    rec["works"].add(wid)
                    rec["mentions"] += 1
                    # Keep up to 4 diverse, concise verbatim quotes (prefer distinct books + explicit trigger match!)
                    has_direct = bool(INDUSTRIES[ind_id]["trigger_re"].search(sent))
                    q_score = (100 if has_direct else 40) + (20 if wid == "ure_gutenberg" else 15 if wid in ("simmonds_1854", "simmonds_1892") else 10) - abs(len(sent) - 180) / 20.0
                    existing_works = {q["work"] for q in rec["quotes"]}
                    if len(rec["quotes"]) < 4 or (wid not in existing_works):
                        rec["quotes"].append({
                            "work": wid,
                            "citation": cit,
                            "uri": uri,
                            "quote": sent[:360] + ("..." if len(sent) > 360 else ""),
                            "score": round(q_score, 1),
                            "mode": "direct_sentence" if has_direct else "essay_context",
                        })
                        # Keep top 3 diverse quotes (at most 1 per work when >3)
                        rec["quotes"].sort(key=lambda x: -x["score"])
                        dedup_q, seen_w = [], set()
                        for q in rec["quotes"]:
                            if q["work"] not in seen_w:
                                dedup_q.append(q)
                                seen_w.add(q["work"])
                            if len(dedup_q) >= 3:
                                break
                        rec["quotes"] = dedup_q

    print(f"Scanned {pages_scanned:,} full-text pages across all 6 books.", flush=True)

    # Mode C: Dictionary Headword + Definition Pairing (`commercial_dictionaries_lexicon.jsonl`, 27,325 entries)
    # Catches high-precision entries where the commodity is the headword and the definition uses "It is used in soap-making..."
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
            matched_inds = []
            for ind_id, cfg in INDUSTRIES.items():
                if cfg["trigger_re"].search(defn) and not (cfg["neg_re"] and cfg["neg_re"].search(defn)):
                    matched_inds.append(ind_id)
            if not matched_inds:
                continue
            for item in resolved:
                if not item["rx"].search(hw):
                    continue
                c = item["concept"]
                cid = c["concept_id"]
                for ind_id in matched_inds:
                    if item["allowed_inds"] is not None and ind_id not in item["allowed_inds"]:
                        continue
                    role = item["role_map"].get(ind_id)
                    if not role:
                        continue
                    rec = evidence[(ind_id, cid)]
                    rec["concept"] = c
                    rec["role"] = role
                    wid = e["source_work"]
                    rec["works"].add(wid)
                    rec["mentions"] += 1
                    quote_txt = f"{hw}: {defn}"
                    rec["quotes"].append({
                        "work": wid,
                        "citation": e["source_citation"],
                        "uri": e["source_uri"],
                        "quote": quote_txt[:360] + ("..." if len(quote_txt) > 360 else ""),
                        "score": 135.0,
                        "mode": "direct_sentence",
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

    # Assemble sorted links list (require >= 1 direct quote OR >= 2 mentions)
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

    # 1. Export flat TSV + JSONL
    out_jsonl = GROUND / "end_use_pilot_links.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as fh:
        for r in links:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    out_tsv = GROUND / "end_use_pilot_links.tsv"
    with open(out_tsv, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow([
            "industry_id", "industry_label", "commodity_id", "commodity_label",
            "attestation_basis", "layer1_rows", "commodity_group",
            "production_role", "production_role_label", "wikidata_qid",
            "book_count", "mention_count", "books", "primary_citation", "primary_uri", "primary_quote",
        ])
        for r in links:
            q0 = r["evidence_quotes"][0]
            w.writerow([
                r["industry_id"], r["industry_label"], r["commodity_id"], r["commodity_label"],
                r["attestation_basis"], r["layer1_rows"], r["commodity_group"],
                r["production_role"], r["production_role_label"], r["wikidata_qid"],
                r["book_count"], r["mention_count"], "; ".join(r["books"]),
                q0["citation"], q0["uri"], q0["quote"],
            ])

    # 2. Export LINCS-Compliant SKOS / CIDOC-CRM Overlay (`end_use_pilot_skos.{ttl,jsonld}`)
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
        "# OPEN EMPIRE — 3-INDUSTRY END-USE OVERLAY PILOT (LINCS / SKOS / CIDOC-CRM)",
        "# ============================================================================",
        "oe:industry_scheme a skos:ConceptScheme ;",
        '    rdfs:label "Open Empire 19th-Century Manufacturing End-Use Scheme (Pilot)"@en ;',
        '    dcterms:title "Open Empire 19th-Century Manufacturing End-Use Scheme (Pilot)"@en ;',
        f'    dcterms:created "{TODAY}"^^xsd:date ;',
        '    skos:hasTopConcept oe:ind_soap_manufacture, oe:ind_calico_printing, oe:ind_chocolate_confectionery .',
        "",
        'oe:usedInIndustry a owl:ObjectProperty ; rdfs:label "commodity used as input in manufacturing industry"@en ; rdfs:domain skos:Concept ; rdfs:range skos:Concept ; owl:inverseOf oe:usesCommodityInput .',
        'oe:usesCommodityInput a owl:ObjectProperty ; rdfs:label "manufacturing industry employs commodity input"@en ; rdfs:domain skos:Concept ; rdfs:range skos:Concept ; owl:inverseOf oe:usedInIndustry .',
        "",
    ]

    jld_graph = [
        {
            "@id": "oe:industry_scheme",
            "@type": "skos:ConceptScheme",
            "rdfs:label": {"@value": "Open Empire 19th-Century Manufacturing End-Use Scheme (Pilot)", "@language": "en"},
            "dcterms:title": {"@value": "Open Empire 19th-Century Manufacturing End-Use Scheme (Pilot)", "@language": "en"},
            "dcterms:created": {"@value": TODAY, "@type": "xsd:date"},
            "skos:hasTopConcept": [{"@id": k} for k in INDUSTRIES.keys()],
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

    (GROUND / "end_use_pilot_skos.ttl").write_text("\n".join(ttl_lines), encoding="utf-8")
    jld_doc = {
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
    }
    (GROUND / "end_use_pilot_skos.jsonld").write_text(json.dumps(jld_doc, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. Write Scholarly Markdown Report
    md = [
        "# 19th-Century Industrial End-Use Pilot Report (Soap, Calico Printing, Chocolate)",
        "",
        f"Generated {TODAY} by `scripts/build_end_use_pilot.py` across **{pages_scanned:,} full-text pages** from 6 19th-century commercial & manufacturing dictionaries (Ure 1853, Simmonds 1854, Simmonds 1892, McCulloch 1880, Mortimer 1823, Watt 1908). Every link is grounded in at least one verbatim primary-source quote.",
        "",
        "## Summary",
        "| Industry | Attested Commodities | Layer-1 Customs | Document-Attested (`htc:doc_*`) | Total Attested Sentences |",
        "|---|---:|---:|---:|---:|",
    ]
    for ind_id, cfg in INDUSTRIES.items():
        lst = by_ind[ind_id]
        l1_n = sum(1 for r in lst if r["attestation_basis"] == "customs_enumerated")
        doc_n = sum(1 for r in lst if r["attestation_basis"] == "document_attested")
        m_n = sum(r["mention_count"] for r in lst)
        md.append(f"| **{cfg['label']}** (`{ind_id}`) | **{len(lst)}** | {l1_n} | {doc_n} | {m_n:,} |")

    for ind_id, cfg in INDUSTRIES.items():
        md.append(f"\n## {cfg['label']} (`{ind_id}`)")
        md.append(cfg["description"])
        by_role = defaultdict(list)
        for r in by_ind[ind_id]:
            by_role[r["production_role"]].append(r)
        for role_key, role_lbl in ROLE_LABELS.items():
            rlst = by_role.get(role_key, [])
            if not rlst:
                continue
            md.append(f"\n### {role_lbl} ({len(rlst)})")
            md.append("| Commodity | Tier | Books | Mentions | Primary-Source Quote |")
            md.append("|---|---|---:|---:|---|")
            for r in rlst:
                q0 = r["evidence_quotes"][0]
                tier = "Layer-1" if r["attestation_basis"] == "customs_enumerated" else "Doc-Attested"
                qtxt = q0["quote"].replace("|", "\\|")[:220]
                md.append(f"| `{r['commodity_id']}` **{r['commodity_label']}** | {tier} | {r['book_count']} | {r['mention_count']} | \"{qtxt}\" — [{q0['citation']}]({q0['uri']}) |")

    (DICT_DIR / "END_USE_PILOT_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\n=== 3-INDUSTRY END-USE PILOT COMPLETE ===")
    for ind_id, cfg in INDUSTRIES.items():
        lst = by_ind[ind_id]
        l1_n = sum(1 for r in lst if r["attestation_basis"] == "customs_enumerated")
        doc_n = sum(1 for r in lst if r["attestation_basis"] == "document_attested")
        print(f"\n{cfg['label']}: {len(lst)} commodities ({l1_n} Layer-1 + {doc_n} Doc-Attested)")
        for role_key, role_lbl in ROLE_LABELS.items():
            rlst = [r for r in lst if r["production_role"] == role_key]
            if rlst:
                names = ", ".join(f"{r['commodity_label']} ({r['book_count']}b/{r['mention_count']}m)" for r in rlst[:10])
                print(f"  [{role_lbl}]: {names}")


if __name__ == "__main__":
    main()
