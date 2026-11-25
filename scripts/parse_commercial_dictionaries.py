#!/usr/bin/env python3
"""
Parse all 6 completed 19th-century commercial dictionaries (4 Narval Chandra-2 OCR + 2 Project Gutenberg)
into a unified, provenance-tracked structured lexicon:
  /home/jic823/Documents/open_empire/dictionaries/commercial_dictionaries_lexicon.jsonl

Sources:
  1. Simmonds (1892), The Commercial Dictionary of Trade Products [IA: b21780535, Chandra-2 OCR]
  2. Mortimer (1823), A General Commercial Dictionary [IA: generalcommercia00mort, Chandra-2 OCR]
  3. McCulloch (1880), A Dictionary of Commerce [IA: dictionaryprac00mccu, Chandra-2 OCR]
  4. Watt (1908), The Commercial Products of India [IA: b31361584, Chandra-2 OCR]
  5. Ure, A Dictionary of Arts, Manufactures, and Mines [Project Gutenberg #44562]
  6. Simmonds (1854), The Commercial Products of the Vegetable Kingdom [Project Gutenberg #15191]

Each extracted record includes:
  headword, alt_headwords, norm_headword, source_work, source_citation, source_uri,
  pdf_page, definition, latin_binomials, see_also
"""

import json
import re
from collections import Counter
from pathlib import Path

OCR_ROOT = Path("/mnt/data/jic823/open_empire_corpus/ocr_chandra/dictionaries_all")
GUT_ROOT = Path("/mnt/data/jic823/open_empire_corpus/raw/gutenberg")
OUT_DIR = Path("/home/jic823/Documents/open_empire/dictionaries")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSONL = OUT_DIR / "commercial_dictionaries_lexicon.jsonl"

PAGE_MARK_RE = re.compile(r"^(\d+)-{40,}\s*$", re.M)
# Italicized Latin binomials: *Genus species* or *Genus Species* (19th-c. capitalized specific epithets like *Isonandra Gutta*)
BINOM_RE = re.compile(r"[*_]([A-Z][a-z]{2,22}\s+[A-Za-z][a-z]{2,24})[*_]")
BINOM_URE_RE = re.compile(r"_([a-zA-Z][a-z]{2,22}\s+[a-zA-Z][a-z]{2,24})_")
SEE_RE = re.compile(r"\bSee\s+(?:also\s+)?(?:\*\*|[*_])?([A-Z][A-Za-z0-9\s,'&-]{1,45}?)(?:\*\*|[*_])?(?:[.;,]|$)")

NON_TAXON_FIRST_WORDS = {
    "The", "This", "That", "See", "Also", "From", "With", "Into", "Upon", "Over",
    "Under", "Some", "Many", "Most", "Such", "Each", "Both", "Much", "More", "Very",
    "When", "Where", "Which", "While", "After", "Before", "About", "Above", "Below",
    "Between", "During", "Without", "Within", "Through", "Against", "Among", "Great",
    "Small", "Large", "Black", "White", "Red", "Blue", "Green", "Yellow", "Brown",
    "Sweet", "Bitter", "Wild", "True", "False", "Common", "East", "West", "North",
    "South", "New", "Old", "British", "French", "German", "Spanish", "Italian",
    "Dutch", "Russian", "Indian", "Chinese", "Turkish", "Arabic", "Malay", "Latin",
    "Greek", "English", "American", "African", "Australian", "Canadian", "Scottish",
    "Irish", "London", "Paris", "India", "China", "Bengal", "Bombay", "Madras",
    "Ceylon", "Java", "Sumatra", "Brazil", "Peru", "Mexico", "Egypt", "Persia",
    "Turkey", "Spain", "France", "Germany", "Italy", "Russia", "Sweden", "Norway",
    "Stat", "Act", "Vol", "Part", "Book", "Page", "Table", "Journal", "Report",
    "Ferment", "Dict", "Ann", "Chem", "Pharm", "Ind", "Soc", "Arts", "Trade",
    "Commercial", "General", "Royal", "Imperial", "Botanical", "Economic", "Value",
    "Price", "Duty", "Weight", "Measure", "Account", "History", "System", "Treatise",
    "Natural", "Artificial", "Vegetable", "Animal", "Mineral", "Oil", "Gum", "Wood",
    "Bark", "Root", "Seed", "Fruit", "Leaf", "Leaves", "Flower", "Flowers", "Juice",
    "Resin", "Wax", "Fat", "Salt", "Acid", "Spirit", "Wine", "Tea", "Coffee", "Sugar",
}


def norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


CATCHWORD_RE = re.compile(r"\s*\\?\*?\s*\[[^\]\[]{1,25}\]?\.?\s*$")
# A new ALL-CAPS headword that begins after a finished sentence inside the same paragraph (OCR merged two
# entries, or the next entry's opening did not match the headword patterns). Never a "See X" cross-reference.
INLINE_HEADWORD_RE = re.compile(
    r"(?<=[.\]])\s+(?:\*\*)?([A-Z][A-Z'\-]{3,}(?:[ ,]+(?:or\s+)?[A-Z][A-Z'\-]{1,}){0,4})(?:\*\*)?(?=\s*\((?:[A-Z][a-z]|GER|Fr|_)|,\s+[_*]*(?:or\s+)?[A-Za-z(]|\s+\*[a-z]+\*,|\.\s+[A-Z][a-z])")
NOT_HEADWORDS = {"PORT", "GERM", "LINN", "ROXB", "RUSS", "SPAN", "ITAL", "DUTCH", "SWED", "WILLD", "WALL", "LESCH", "LABILL"}


def cut_at_inline_headword(body: str) -> str:
    """Stop an entry body where the next dictionary entry begins inside the same text run."""
    for m in INLINE_HEADWORD_RE.finditer(body, 20):
        if re.sub(r"[^A-Z]", "", m.group(1)) in NOT_HEADWORDS:
            continue
        prev_sentence = re.split(r"\.\s", body[:m.start()])[-1]
        if re.search(r"\b[Ss]ee\b[^.]*$", prev_sentence) and not body[:m.start()].rstrip(" *_").endswith((".", "]")):
            continue
        return body[:m.start()].rstrip()
    return body


def clean_def(s: str, max_len: int = 700) -> str:
    """Whitespace/markup clean-up, strip the printer's trailing catchword ("[jar.]"), and shorten at the LAST
    sentence boundary inside max_len (the old version kept only the first sentence, or cut mid-word)."""
    s = re.sub(r"\s+", " ", (s or "")).strip()
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.split(r"\s\+-{3,}|\s\|\s", s)[0].strip()  # ASCII tables are not definition text
    s = CATCHWORD_RE.sub("", s).strip()
    s = re.sub(r"\s*\\?\*\s*$", "", s).strip()
    if len(s) <= max_len:
        return s
    gloss_end = 0
    if s.startswith("("):  # Mortimer/McCulloch language gloss "(GER. ... LAT. ...,)": sentence stops inside it are not ends
        g = re.match(r"\((?:[^()]|\([^()]*\))*\)", s)
        gloss_end = g.end() if g else 0
    cut = s[:gloss_end + max_len]
    ends = [m.end() for m in re.finditer(r"[.;]\s", cut) if m.end() > gloss_end + 80
            and not re.search(r"\b(?:[A-Z][a-z]?|[A-Z]{2,5}|vol|viz|etc|Fr|Ger|Lat|Linn|Roxb|No|pp?|St|Dr|Mr|cwt|lbs?|oz|gal)\.\s$", cut[:m.end()])]
    if ends:
        return cut[:ends[-1]].strip()
    return cut.rsplit(" ", 1)[0] + " …"


def extract_binomials(text: str, allow_lower_genus: bool = False) -> list:
    pat = BINOM_URE_RE if allow_lower_genus else BINOM_RE
    out = []
    seen = set()
    for m in pat.finditer(text):
        cand = m.group(1).strip()
        parts = cand.split()
        if len(parts) != 2:
            continue
        g, sp = parts[0].capitalize(), parts[1].lower()
        if g in NON_TAXON_FIRST_WORDS or len(sp) < 3:
            continue
        if sp in ("and", "the", "for", "with", "from", "that", "this", "are", "was", "were", "has", "have", "not", "but", "into", "also", "used", "called", "known", "made", "found", "name", "wood", "bark", "oil", "gum", "tree", "plant", "seed", "root", "leaf"):
            continue
        b = f"{g} {sp}"
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out


def extract_see_also(text: str) -> list:
    out = []
    seen = set()
    for m in SEE_RE.finditer(text):
        ref = m.group(1).strip(" .,;:*_")
        if len(ref) >= 2 and norm_key(ref) not in seen and not ref.lower().startswith(("p ", "pp ", "page ", "vol ", "table ", "fig ")):
            seen.add(norm_key(ref))
            out.append(ref)
    return out


def iter_ocr_pages(ia_id: str):
    """Yield (pdf_page_1based, page_text) across all sorted 25-page Chandra pieces for ia_id."""
    pieces = sorted(OCR_ROOT.glob(f"{ia_id}_p*"))
    for pdir in pieces:
        m = re.search(r"_p(\d+)$", pdir.name)
        if not m:
            continue
        start_page = int(m.group(1))
        mds = list(pdir.rglob("*.md"))
        if not mds:
            continue
        raw = mds[0].read_text(encoding="utf-8", errors="replace")
        # Split on Chandra pagination markers `1------------------------------------------------`
        chunks = PAGE_MARK_RE.split(raw)
        # chunks = [page0_text, '1', page1_text, '2', page2_text, ...]
        yield start_page, chunks[0]
        for i in range(1, len(chunks), 2):
            offset = int(chunks[i])
            txt = chunks[i + 1] if i + 1 < len(chunks) else ""
            yield start_page + offset, txt


def split_alt_headwords(raw_hw: str):
    """Split 'CAMOMILE, CHAMOMILE' or 'CAOUTCHOUC, GUM-ELASTIC, OR INDIAN-RUBBER'."""
    s = re.sub(r"\*\*|[*_]", "", raw_hw).strip(" .,;:-")
    # Remove trailing language tags like (French), (Italian)
    s = re.sub(r"\s*\([^)]{1,35}\)\s*$", "", s).strip()
    parts = re.split(r",\s*(?:or\s+)?|\s+OR\s+|\s+or\s+|;\s*", s)
    clean = []
    for p in parts:
        p = p.strip(" .,;:-'\"")
        if 2 <= len(p) <= 55 and not p.isdigit():
            clean.append(p)
    if not clean:
        return "", []
    return clean[0], clean[1:]


def parse_simmonds_1892():
    """Simmonds 1892 (b21780535): crisp **HEADWORD**, definition paragraphs."""
    entries = []
    hw_re = re.compile(r"^\*\*([A-Z][A-Z0-9\s,'&./()-]{1,75}?)\*\*((?:,\s*(?:or\s+)?\*\*[A-Z][A-Z0-9\s,'&./()-]{1,50}?\*\*)*)\s*(?:\([^)]+\))?\s*[,;:.—-]?\s*(.*)$")
    # An entry that starts mid-paragraph (OCR merged two entries): "... ACID**. **VIVRES** (French), provisions"
    inline_split = re.compile(r"(?<=[.\]])\s+(?=\*\*[A-Z][A-Z0-9\s,'&./()-]{1,75}?\*\*\s*(?:\([^)]+\))?\s*,\s+[a-z(])")
    raw = []
    for page_no, ptxt in iter_ocr_pages("b21780535"):
        if page_no < 10:
            continue  # front matter
        paras = [p.strip() for p in re.split(r"\n\s*\n", ptxt) if p.strip()]
        for para in paras:
            for flat in inline_split.split(re.sub(r"\s+", " ", para)):
                m = hw_re.match(flat.strip())
                if not m:
                    continue
                body = m.group(3).strip()
                if len(body) < 8:
                    continue
                raw.append((page_no, m.group(1).strip(" .,;:-"), m.group(2) or "", body))

    # Pass 2: "**TOBACCO, MOUNTAIN**" inside ONE bold run is an inverted sub-entry (mountain tobacco), not a
    # synonym of TOBACCO, whenever the dictionary also has a plain entry for the base word. Synonyms are
    # printed as separate bold runs ("**CAMOMILE**, **CHAMOMILE**") or joined by "or".
    from difflib import SequenceMatcher
    plain = {norm_key(h) for _, h, more, _ in raw if "," not in h}
    comma_bases = Counter(norm_key(h.partition(",")[0]) for _, h, more, _ in raw if "," in h and not more)
    stems = {norm_key(h.split("-")[0]) for _, h, more, _ in raw if "-" in h and "," not in h}
    for page_no, hw1, more, body in raw:
        inverted = None
        if "," in hw1 and not more and not re.search(r"\bor\b", hw1, re.I):
            base, _, qual = hw1.partition(",")
            base, qual = base.strip(), qual.strip(" .,;:-")
            nb = norm_key(base)
            known_base = nb in plain or comma_bases[nb] >= 2 or nb in stems
            variant = SequenceMatcher(None, nb, norm_key(qual)).ratio() >= 0.5  # GAGE, GAUGE / THRAVE, THREAVE
            if qual and "," not in qual and known_base and len(qual.split()) <= 3 and not variant:
                inverted = (base, qual)
        if inverted:
            base, qual = inverted
            connective = qual.upper().split()[-1] in ("OF", "FOR", "AND", "DE", "IN")
            primary = f"{base} {qual}" if connective else f"{qual} {base}"
            alts = [hw1]
            if connective:  # "VITRIOL, OIL OF" -> "OIL OF VITRIOL"
                primary = f"{qual} {base}"
        else:
            primary, alts = split_alt_headwords(hw1 + more)
        if not primary:
            continue
        if True:
            entries.append({
                "headword": primary,
                "alt_headwords": alts,
                "norm_headword": norm_key(primary),
                "source_work": "simmonds_1892",
                "source_citation": f"P. L. Simmonds, The Commercial Dictionary of Trade Products (1892), scan p. {page_no}",
                "source_uri": f"https://archive.org/details/b21780535/page/n{page_no}",
                "pdf_page": page_no,
                "inverted_subentry": bool(inverted),
                "definition": clean_def(body),
                "latin_binomials": extract_binomials(body),
                "see_also": extract_see_also(body),
            })
    return entries


def parse_allcaps_ocr_dict(ia_id: str, work_key: str, citation_prefix: str, min_page: int = 12):
    """Parse Mortimer (1823), McCulloch (1880), and Watt (1908) essay-style dictionaries."""
    entries = []
    # Match bold or ALL-CAPS headword at start of paragraph
    pat_bold = re.compile(r"^(?:#+\s*)?\*\*([A-Z][A-Z0-9\s,'&./-]{1,65}?)\*\*\s*[.,;:—-]+\s*(.+)$")
    pat_caps = re.compile(r"^([A-Z][A-Z\s,'&-]{2,55}?)(?:,\s+(?:or\s+)?([A-Z][A-Z\s'-]{2,40}?))?\s*[.,;—-]+\s+([A-Z(].+)$")
    # "ABANDONMENT (Fr. délaissement). In Commerce ..." - headword followed directly by its language gloss
    pat_paren = re.compile(r"^([A-Z][A-Z\s,'&-]{2,55}?)\s+(\((?:[A-Z][a-z]{1,3}|GER|DU|FR|IT|SP|LAT)\.?\s.+)$")
    # Watt opens every entry with authorities and references up to the plant family (COMBRETACEÆ.) - not a definition
    watt_preamble = re.compile(r"^.{0,900}?\b[A-Z]{3,}(?:ACEÆ|ACEAE|IFERÆ|OSÆ|INEÆ|IDEÆ|ATÆ|EÆ|Æ)\.\s+(?:D\.\s?E\.\s?P\.[^.]*\.(?:[^.]{0,25}\.)?\s+)?")

    cur = None
    cur_body_parts = []

    def flush():
        nonlocal cur, cur_body_parts
        if not cur:
            return
        full_body = cut_at_inline_headword(" ".join(cur_body_parts))
        if work_key == "watt_1908":
            full_body = watt_preamble.sub("", full_body, count=1)
            full_body = re.sub(r"^\**D\.\s?E\.\s?P\.\**,?\s*(?:[ivxlc]+\.,?\s*)?[\d\-–, ]*\.?\s*", "", full_body)
            # leading bibliography: "Author, *Title*, 1881, 59-119; ..." segments carry a year or volume/page numerals
            while True:
                seg = re.match(r"^[^;]{0,220}?;\s+", full_body)
                if seg and re.search(r"\b1[6-9]\d\d\b|\b[ivxlc]+\.,\s*\d", seg.group(0)):
                    full_body = full_body[seg.end():]
                else:
                    break
            full_body = re.sub(r"\s*#+\s*[A-Z][A-Z ]{3,}(?:[A-Z][a-z]+ ?){0,4}", " ", full_body)  # running heads
        cur["definition"] = clean_def(full_body)
        cur["latin_binomials"] = extract_binomials(full_body[:5000])
        cur["see_also"] = extract_see_also(full_body[:4000])
        entries.append(cur)
        cur = None
        cur_body_parts = []

    for page_no, ptxt in iter_ocr_pages(ia_id):
        if page_no < min_page:
            continue
        paras = [p.strip() for p in re.split(r"\n\s*\n", ptxt) if p.strip()]
        for para in paras:
            flat = re.sub(r"\s+", " ", para)
            # Skip short running headers / page numbers
            if len(flat) < 25 or flat.startswith("<table"):
                continue
            m = pat_bold.match(flat) or pat_caps.match(flat) or pat_paren.match(flat)
            if m:
                if len(m.groups()) == 2:
                    hw_raw, body = m.group(1), m.group(2)
                else:
                    hw_raw = m.group(1) + ((", " + m.group(2)) if m.group(2) else "")
                    body = m.group(3)
                # Reject obvious non-headword section subheads like "TRADE IN INDIAN TEA" or "TABLE OF"
                hw_clean = hw_raw.strip(" .,;:-*")
                if len(hw_clean.split()) <= 5 and not re.match(r"^(TABLE|ACCOUNT|STATEMENT|RETURN|VALUE|QUANTITY|EXPORTS|IMPORTS|PRICES|DUTY|DUTIES|AREA|TRADE|USES|PRODUCTION|CULTIVATION|MANUFACTURE|HISTORY|HABITAT|PROPERTIES|NOTE|APPENDIX)\b", hw_clean):
                    primary, alts = split_alt_headwords(hw_clean)
                    if primary and len(primary) >= 3:
                        flush()
                        cur = {
                            "headword": primary,
                            "alt_headwords": alts,
                            "norm_headword": norm_key(primary),
                            "source_work": work_key,
                            "source_citation": f"{citation_prefix}, scan p. {page_no}",
                            "source_uri": f"https://archive.org/details/{ia_id}/page/n{page_no}",
                            "pdf_page": page_no,
                        }
                        cur_body_parts = [body]
                        continue
            if cur and len(" ".join(cur_body_parts)) < 3500:
                cur_body_parts.append(flat)
    flush()
    return entries


def parse_ure_gutenberg():
    """Parse Project Gutenberg #44562 Andrew Ure Dictionary of Arts, Manufactures, and Mines."""
    p = GUT_ROOT / "pg44562_ure_dictionary_arts_manufactures.txt"
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8", errors="replace")
    start = txt.find("*** START OF")
    end = txt.find("*** END OF")
    body = txt[start:end] if start > 0 and end > start else txt
    paras = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"\n\s*\n", body) if x.strip()]

    pat = re.compile(r"^([A-Z][A-Z0-9\s,'&-]{2,95}?)(?:,\s*\([^)]+\)\s*|\s*)[.,;]?\s+([a-z(].+)$")
    entries = []
    cur = None
    cur_parts = []

    def flush():
        nonlocal cur, cur_parts
        if not cur:
            return
        fb = cut_at_inline_headword(" ".join(cur_parts))
        cur["definition"] = clean_def(fb)
        cur["latin_binomials"] = extract_binomials(fb[:4000], allow_lower_genus=True)
        cur["see_also"] = extract_see_also(fb[:3000])
        entries.append(cur)
        cur = None
        cur_parts = []

    for para in paras:
        if len(para) < 30:
            continue
        m = pat.match(para)
        if m:
            hw_raw, rest = m.group(1).strip(), m.group(2).strip()
            # Must have at least 1 uppercase word >= 3 chars and <= 7 words total
            if 1 <= len(hw_raw.split()) <= 7 and not hw_raw.startswith(("PAGE ", "FIG ", "TABLE ", "NOTE ", "END OF")):
                primary, alts = split_alt_headwords(hw_raw)
                if primary and len(primary) >= 3:
                    flush()
                    cur = {
                        "headword": primary,
                        "alt_headwords": alts,
                        "norm_headword": norm_key(primary),
                        "source_work": "ure_gutenberg",
                        "source_citation": "Andrew Ure, A Dictionary of Arts, Manufactures, and Mines (Project Gutenberg #44562)",
                        "source_uri": "https://www.gutenberg.org/ebooks/44562",
                        "pdf_page": None,
                    }
                    cur_parts = [rest]
                    continue
        if cur and len(" ".join(cur_parts)) < 3500:
            cur_parts.append(para)
    flush()
    return entries


def parse_simmonds_1854_gutenberg():
    """Parse Project Gutenberg #15191 P. L. Simmonds Commercial Products of the Vegetable Kingdom."""
    p = GUT_ROOT / "pg15191_simmonds_1854_vegetable_kingdom.txt"
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8", errors="replace")
    start = txt.find("*** START OF")
    end = txt.find("*** END OF")
    body = txt[start:end] if start > 0 and end > start else txt
    # The book opens with a subscriber list, works consulted and an analytical table of contents whose
    # summaries are not definitions: the text proper starts at the SECOND "SECTION I."
    starts = [m.start() for m in re.finditer(r"^SECTION I\.", body, re.M)]
    if len(starts) >= 2:
        body = body[starts[1]:]
    paras = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"\n\s*\n", body) if x.strip()]

    entries = []
    runin = re.compile(r"^([A-Z][A-Z\s,'&-]{2,60}?)\.--([A-Z].{60,})$")
    for p1 in paras:
        m = runin.match(p1)
        if m:
            primary, alts = split_alt_headwords(m.group(1))
            if primary and len(primary.split()) <= 6:
                entries.append({
                    "headword": primary, "alt_headwords": alts, "norm_headword": norm_key(primary),
                    "source_work": "simmonds_1854",
                    "source_citation": "P. L. Simmonds, The Commercial Products of the Vegetable Kingdom (1854, Project Gutenberg #15191)",
                    "source_uri": "https://www.gutenberg.org/ebooks/15191", "pdf_page": None,
                    "definition": clean_def(m.group(2)),
                    "latin_binomials": extract_binomials(m.group(2)[:4000], allow_lower_genus=True),
                    "see_also": extract_see_also(m.group(2)[:2000]),
                })
    # Section headings are ALL CAPS on their own short paragraph followed by prose
    i = 0
    while i < len(paras) - 1:
        p1 = paras[i]
        if 3 <= len(p1) <= 65 and p1 == p1.upper() and re.match(r"^[A-Z][A-Z\s,'&-]+[A-Z.]$", p1) and not p1.startswith(("SECTION ", "CHAPTER ", "PART ", "INDEX", "CONTENTS", "PREFACE", "TABLE ")):
            nxt = " ".join(paras[i + 1 : i + 5])
            if len(nxt) >= 80:
                primary, alts = split_alt_headwords(p1)
                if primary and len(primary.split()) <= 6:
                    entries.append({
                        "headword": primary,
                        "alt_headwords": alts,
                        "norm_headword": norm_key(primary),
                        "source_work": "simmonds_1854",
                        "source_citation": "P. L. Simmonds, The Commercial Products of the Vegetable Kingdom (1854, Project Gutenberg #15191)",
                        "source_uri": "https://www.gutenberg.org/ebooks/15191",
                        "pdf_page": None,
                        "definition": clean_def(nxt),
                        "latin_binomials": extract_binomials(nxt[:4000], allow_lower_genus=True),
                        "see_also": extract_see_also(nxt[:2000]),
                    })
        i += 1
    return entries


def main():
    all_entries = []
    counts = Counter()

    for name, fn in [
        ("simmonds_1892", parse_simmonds_1892),
        ("mortimer_1823", lambda: parse_allcaps_ocr_dict("generalcommercia00mort", "mortimer_1823", "Thomas Mortimer (rev. Dickinson), A General Commercial Dictionary (1823)")),
        ("mcculloch_1880", lambda: parse_allcaps_ocr_dict("dictionaryprac00mccu", "mcculloch_1880", "J. R. McCulloch, Dictionary of Commerce and Commercial Navigation (1880)")),
        ("watt_1908", lambda: parse_allcaps_ocr_dict("b31361584", "watt_1908", "Sir George Watt, The Commercial Products of India (1908)")),
        ("ure_gutenberg", parse_ure_gutenberg),
        ("simmonds_1854", parse_simmonds_1854_gutenberg),
    ]:
        ents = fn()
        counts[name] = len(ents)
        all_entries.extend(ents)
        with_binom = sum(1 for e in ents if e["latin_binomials"])
        with_see = sum(1 for e in ents if e["see_also"])
        print(f"  {name:16s}: {len(ents):6,d} entries | {with_binom:5,d} w/ Latin binomials | {with_see:5,d} w/ See cross-refs", flush=True)

    with open(OUT_JSONL, "w", encoding="utf-8") as fh:
        for e in all_entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    uniq_hw = len({e["norm_headword"] for e in all_entries})
    uniq_binoms = len({b for e in all_entries for b in e["latin_binomials"]})
    print(f"\nTOTAL: {len(all_entries):,} dictionary entries ({uniq_hw:,} unique normalized headwords, {uniq_binoms:,} unique Latin binomials) -> {OUT_JSONL}")

    # Spot-check CAOUTCHOUC, GUTTA PERCHA, TALLOW, VALONIA, CUTCH, SHUMACH, PLUMBAGO
    print("\n=== SPOT-CHECK KEY COMMODITIES IN EXTRACTED LEXICON ===")
    by_hw = {}
    for e in all_entries:
        by_hw.setdefault(e["norm_headword"], []).append(e)
    for k in ["caoutchouc", "gutta percha", "india rubber", "tallow", "stearine", "valonia", "cutch", "terra japonica", "sumach", "plumbago", "castor", "manna"]:
        hits = by_hw.get(k, [])
        print(f"  [{k}] -> {len(hits)} dict entries:")
        for h in hits[:3]:
            print(f"     ({h['source_work']}) alts={h['alt_headwords'][:4]} binoms={h['latin_binomials'][:4]} see={h['see_also'][:3]} | {h['definition'][:100]}")


if __name__ == "__main__":
    main()
