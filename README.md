# Open Empire (`spark-drive-archive`): Historical Trade Ontology, Open Corpora & Entity Spine

**Live Interactive Ontology & Visual Tree:** https://jimclifford.ca/spark-drive-archive/

Reproducible code, open public-domain commercial dictionary lexicons, and extracted Layer-1 historical trade data & ontologies for *London's Ghost Acres* and comparative British World environmental history (University of Saskatchewan HGIS Lab).

## Rights & Sharing Policy (Strict 3-Tier Boundary)
1. **Included in this repository (Open Code, Open Documents, & Extracted Data):**
   - **All pipeline code:** Internet Archive / BHL discovery, download, Narval Chandra-2 OCR batching, dictionary parsing, Layer-1 trade consolidation, place/polity grounding, and SKOS v4 ontology generation (`scripts/`, `human_trade/scripts/`).
   - **Tier-1 Open Public Sources:** Audited manifests for public-domain Internet Archive / BHL / Project Gutenberg holdings (`manifests/`) and derived structured lexicons from 6 19th-century commercial dictionaries (`dictionaries/`).
   - **Extracted Archival Data (Layer 1 — `human_transcribed`):** Consolidated extracted observations (`human_trade/layer1_human/human_trade_observations.tsv.gz`), unique printed name tables, place/polity grounding (`places_grounding.jsonl`, `place_year_polities.tsv`), and the 4-tier SKOS v4 commodity vocabulary (`commodities_skos.{ttl,jsonld}`, `commodities_mappings.sssom.tsv`, `commodities_concepts.jsonl`, interactive `open_empire_layer1_skos_v4.html`).
2. **Strictly Excluded (Local / Private Only — enforced via `.gitignore`):**
   - Raw archival reading-room photography and scans (`/mnt/data/jic823/archival_corpus/`, TNA `CUST 4/5/26` PDFs).
   - Raw archival transcription spreadsheets and unpermissioned raw archival source files (`human_trade/raw_sources/`).
   - Licensed/vendor digitized corpora (e.g., Adam Matthew `CO 879`, paywalled JSTOR, `historyofceylontea.com`).
   - Large binary PDFs and raw OCR page dumps (`/mnt/data/jic823/open_empire_corpus/`).
3. **Layer Separation:** Layer-1 (`human_transcribed`) extracted trade records are kept strictly distinct from future Layer-2 (`llm_extracted`) archival OCR extractions.

## Repository Layout
- `SOURCES.md` — Provenance, license/rights tier, and publishability rules for every collection (including the 6 Wave 1b commercial dictionaries).
- `manifests/` — Audited Internet Archive / BHL item catalogs (`wave1_economic_botany.tsv`, `wave1b_commercial_dictionaries*.tsv`, `wave2_colonial_bluebooks.tsv`, `wave3_regional_ghost_acres.tsv`, and discovery snapshots).
- `scripts/` — Discovery, curation, download, Narval Slurm OCR bundling, dictionary parser (`parse_commercial_dictionaries.py`), and binomial grounding (`ground_dictionary_binomials.py`).
- `dictionaries/` — Parsed structured lexicon (`commercial_dictionaries_lexicon.jsonl`, 27,325 entries across 6 19th-century commercial dictionaries) and verified Linnaean taxon grounding (`dictionary_binomials_grounded.jsonl`, 1,190 Wikidata/Catalogue of Life taxa).
- `human_trade/`
  - `scripts/` — Layer-1 consolidation (`build_human_layer1.py`), places/polities grounding (`ground_places_v2.py`), SKOS v4 builder (`build_skos_v4.py`), and interactive HTML inspector builder (`build_skos_html_inspector.py`).
  - `layer1_human/` — Consolidated extracted Layer-1 observations (`human_trade_observations.tsv.gz`, 153,579 rows cleanly partitioned by `row_kind`), `CONSOLIDATION_REPORT.md`, `names/*.tsv`, and `grounding/` (persistent `htc_id_registry.tsv`, `commodities_skos.{ttl,jsonld}`, `commodities_mappings.sssom.tsv`, `places_grounding.jsonl`, `place_year_polities.tsv`, `GROUNDING_REPORT.md`, Opus review reports, and standalone `open_empire_layer1_skos_v4.html`).

## Current Milestones (2026-11-24)
- **6 19th-Century Commercial Dictionaries Parsed & Grounded:** Simmonds (1892), Mortimer (1823), McCulloch (1880), Watt (1908) via Narval Chandra-2 OCR (`198/198` bundles PASS) + Simmonds (1854) & Ure (1853) from Project Gutenberg → **27,325 entries**, **1,190 verified Linnaean taxa**.
- **Layer-1 Places & Polities Grounding v2:** **93.9%** of 270,080 mentions grounded to verified Wikidata QIDs (**98.5%** resolved with explicit aggregates) + **1,067** year-aware Empire Evolution `IN_POLITY` pairs.
- **Layer-1 Commodity SKOS v4 Ontology:** 4-tier hierarchy (**9 Macro-Sectors → 44 Commodity Groups → 163 S14-safe Substance Groups → 2,066 persistent `htc:` concepts**), **77.4%** of 152,625 commodity rows grounded to verified non-taxon Wikidata anchors + composed Getty AAT/STW/AGROVOC URIs (**79.2%** w/ explicit customs residuals), **447** 19th-century `skos:definition` entries with clickable IA/Gutenberg provenance, **67** unambiguous `skos:altLabel` sets, **54** vetted bidirectional `skos:related` links, **11** merged `oe:combinesConcept` headings, and **208** verified Linnaean `oe:sourceTaxon` links (all Opus v4 P0s resolved).
