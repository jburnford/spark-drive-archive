# v6 Review — Commodity Vocabulary, Document-Attested Tier and End-Use Network

*2026-11-25 · follows [V5](OPUS_SKOS_REVIEW_V5.md)*

## Why the earlier reviews missed this

V2–V5 checked SKOS integrity (cycles, orphans, S13/S14, duplicate `exactMatch`) and Wikidata homonyms.
Those all still pass. They did not read the hierarchy heading by heading, the definitions against their
headings, the document-attested tier, or the end-use quotes against the links they are meant to support.
This review did all four, in full (no sampling), and found that structural validity was hiding a large
number of content errors.

## Method

- Read all 2,066 Layer-1 headings in their sector → group → substance-group position, with facets and anchors.
- Read every populated definition (447), taxon set (233), altLabel set (69), related/material link set, scope note and 1866 bridge.
- Read all 601 document-attested concepts and checked all 795 of their citations against the lexicon.
- Read all 370 end-use links and all 684 quotes; checked every quote is verbatim.
- Ambiguous headings were settled from the Layer-1 observations (series, years, units, routes) and the
  dictionaries, not from the label alone.
- Confirmed the whole pipeline is deterministic (re-running it on the committed state gave zero diff)
  before changing anything, so every fix lives in a generator or a curated table, never in an output file.

## Evidence trail

Corrections are data, each with a written rationale, in four new tables read by the builders:

| File | Rows | Applied by |
|---|---:|---|
| `curated_overrides.tsv` | 285 | `build_skos_v4.py` — group / processing state / land basis / Wikidata anchor |
| `curated_field_fixes.tsv` | 184 | `build_skos_v4.py` — definitions, taxa, labels, 1866 bridges |
| `curated_doc_tier_decisions.tsv` | 277 | `build_commodity_gazetteer.py` — drop / same-as-Layer-1 / merge / refile |
| `curated_end_use_link_decisions.tsv` | 68 | `build_end_use_network.py` — drop / re-point / prune quotes |

- Every overridden Layer-1 concept carries a `skos:editorialNote` with the rationale **and** an automatically
  computed summary of its trade evidence (rows, years, series, units, top routes).
- Replacement definitions are verbatim lexicon entries or verbatim excerpts; nothing is paraphrased.
- Anchors are still resolved only through the local Wikidata snapshot. Seven correct taxa could not be added
  because the snapshot labels them in English (see open items).
- Each table has a label guard and fails loudly if a row stops matching, so stale rows cannot rot silently.

## What was wrong, and what changed

### Layer-1 hierarchy (the regex classifier)

The classifier is a first-match keyword cascade, so one word decided the group.

- **Keyword collisions:** *Petroleum Oil Spirit* and turpentine under beverages (“spirit”); burnt lime, plaster
  and calcium salts under fruit (“lime”); hop and telegraph poles under fruit (“hop”); *Carpets Turkey* under
  live poultry; elephant, sea-cow and sea-horse **teeth** (ivory) under live draft horses; enamelled iron
  hollow-ware under tanned leather; sawn marble under sawn lumber; *Gum Lac, Seed…* under oilseeds.
- **Negation ignored:** “Hides **not** Tanned, Tawed, Curried…” filed as tanned leather.
- **Residual bin:** 204 headings sat in “Unenumerated & Residual”, most of them named commodities
  (Marmalade, Ginseng, Chloroform, Claret, Chairs, Lintseed Oil…). 151 were placed; **residual rows fell
  from 3.08% to 1.92%** (53 headings left, all genuinely unspecific or undetermined).
- **Settled from the trade data:**
  - *Cocoa nuts* — 25 of 34 rows are counted by number from the West Indies and Guiana, i.e. coconuts; it had
    been anchored to the cocoa bean.
  - *Oil Seed* (1896, in tons) is seed oil, not oil seeds.
  - *Tongues* / *Meats viz Tongues* are provisions, not fish.
  - *Rabbits* arrive by the hundredweight (carcasses), not live.
- **Wrong anchors:** ships-to-be-broken-up → *clothing* (“apparel”); gambier → catechu; valonia → tanbark.

### Layer-1 definitions, taxa and links (automatic headword matching)

- **Wrong sense:** all ten tobacco headings were defined as *Arnica montana* (“mountain tobacco”) and carried
  that taxon; Stone was the 14-lb weight; Ink a Japanese measure; Charcoal was bone charcoal; Logs were
  Scottish stockings; Capers an oat-cake; Currants were *Ribes*, not dried Corinth grapes.
- **Not definitions:** duty prose on six Spirits headings, statistics on Meat, Hides, Raisins, Cutch;
  Watt bibliographies on Wool, Petroleum, Horns.
- **Run-ons:** definitions continuing into the next dictionary entry (Whiskey → WHITE LEAD, Axes → AXUNGIA).
- **Taxa:** vegetable-ivory palm on animal ivory and on Vegetables; fig tree on Feathers; khat on Tea;
  reptiles and fish on Eggs; a coffee species described in 2008.
- **Material links** (fixed in the generator): “not Iron or Steel” was tagged iron; “not with Rubber” tagged
  rubber; ores were “made of” the smelted metal; hubs were *Iron Bars*, *Copper Old* and *Leather Undressed*
  instead of *Iron*, *Copper*, *Leather*.
- A *Terra Japonica* scope note was attached to *Timber Deals and Deal ends*.

### Document-attested tier (601 → 380 concepts)

- **49 dropped:** not commodities — six ship’s mates filed under Spices (keyword “mate”), coins, tools,
  processes, ports, garbled OCR headwords.
- **115 already existed as Layer-1 customs lines**, contradicting the tier’s premise of “absent from the
  ledgers” (Logwood, Gum Copal, Ermine, Lynx, Gunpowder…). Their labels are kept as gazetteer surface forms
  of the Layer-1 heading.
- **57 merged** as spelling or synonym variants; **56 refiled** under the correct customs heading.
- `subsumed_in_customs_label` was an invented label; it now shows the real Layer-1 prefLabel
  (htc:0071 is “Furs Unenumerated Undressed”, not “Furs, Skins & Marine Products”).
- Definitions are cut at the next headword and at a sentence end instead of blindly at 380 characters.
- A binomial is accepted only if it occurs in the cited definition (taxon-bearing concepts 208 → 148).

### End-use network (370 → 322 links)

- Every quote is verbatim (684/684), but links were made by keyword co-occurrence. Reading them:
  about 1 link in 6 was not supported by its own quotes.
- **48 dropped:** negations (“makes no reference to the lard and tallow manufactures”), the commodity as
  *product* not input (flint glass, molasses), homonyms (“size” as dimension, “mauve” for aniline),
  sentences fused across headwords.
- **20 re-pointed** to the heading the quote is actually about (lead salts, not pig lead; argol, not
  tartaric acid; *Sugar*, not the statistical line *Sugar Unrefined Total*).
- **Page citations were one page low** on all 282 full-text quotes from the four Internet Archive books,
  and the first page of every 25-page OCR chunk was never scanned. Fixed (6,455 → 6,648 pages scanned).
- **Ure was cited as 1853.** The Gutenberg text (#44562) is the second edition, **1840**.

## Verification

| Check | Result |
|---|---|
| Pipeline run twice | byte-identical outputs |
| TTL vs JSON-LD (all four vocabularies) | 0 triple diff |
| Layer-1 scheme | 2,343 concepts, 0 orphans, 0 cycles, 0 multi-parent, 0 dangling, 0 duplicate `exactMatch`, `related` symmetric |
| Extended scheme | 2,723 concepts, same results; every `subsumedInCustomsHeading` target exists |
| End-use links | every commodity id resolves |
| Grounded | 1,420 concepts / 131,018 rows (85.8%) |

`audit_extended_skos.py` reports three “S14 duplicate prefLabels” (Bark, Fish, Fruit). They are in two
different schemes (`htc:` and `htc1866:`), so they are not S14 violations; the audit script does not
separate schemes.

## Open items (not fixed here)

**Needs a decision**
- **Land basis of wild furs.** Beaver, marten, fox and the other wild pelts take `terrestrial_pasture` from
  their group. For ghost-acre accounting that is wrong, but there is no “wild / hunted” value to move them to.
- **Coarse anchors on the largest grains.** Oats, Barley, Rye, Buckwheat and Peas are only `broadMatch`
  cereal / legume, and Horses and Swine `broadMatch` livestock, because the snapshot matcher cannot resolve
  their labels. Same cause for the seven taxa not added (elephants, walrus, hippopotamus, *Piper nigrum*,
  *Castor canadensis*, *Ursus americanus*).
- *Cocoa nuts* is period-dependent (scope note added); the nine pre-1841 rows by weight may be cacao.
- *Whiting* (one row, 1840) and *Bass* (one row, 1837) cannot be settled from one row each.

**Root causes still in place**
- **The lexicon parser** folds sub-entries into their parent headword (“TOBACCO, Mountain” → TOBACCO),
  truncates definitions at ~480 characters and lets entries run into the next headword. The curated tables
  correct the cases found; the parser is the source.
- **The end-use miner** still links on co-occurrence. About 60 further links are true but carry a wrong
  role or some irrelevant quotes, and 291 Ure / Simmonds 1854 quotes cite the ebook with no page.
- **Watt and Simmonds 1854** rarely yield usable definitions (bibliographic preambles; a table of contents).
  About 18 document-attested concepts labelled with a Latin binomial still have such text.
- The 13 residual document-attested concepts from the drugs list have no definition.
- Compound headings: four `oe:combinesConcept` sets list only one constituent.
- `end_use_pilot_*` is superseded by the network and was not reviewed.
- Places and polities grounding was outside this review.
