# Layer-1 Human-Transcribed Trade Entity Grounding Report (v4 — 4-Tier Ontology + 6 Commercial Dictionaries)

All QIDs strictly read from verified local authorities (`ceylon/spine`, `empire-evolution`, `Canada-History-Knowledge-Graph`, local Wikidata `2026-11-09` slim Parquet dump, and Catalogue of Life) plus live Wikidata `wbgetentities` external-identifier enrichment — **zero QIDs from memory**. Built by `human_trade/scripts/build_skos_v4.py`, fixing all Opus v2/v3 P0–P2 issues and enriching the ontology from 6 19th-century commercial dictionaries (Simmonds 1892, Mortimer 1823, McCulloch 1880, Watt 1908, Simmonds 1854, Ure 1853).

- **Layer-1 Observation Reconciliation:** `153,579` total records − (`514` `qa_check_row` + `168` `blank` + `272` `missing_commodity`) = **`152,625` commodity-bearing rows** across **`2,066` persistent `htc:` concepts** (`htc_id_registry.tsv`).
- **CI Checks Passed:** `0` malformed `c_c_` IRIs, `0` SKOS S14 duplicate `prefLabel` clashes, `0` `exactMatch` state collapses, `0` rejected QIDs, `0` metal-pig animal misclassifications, `0` orphan concepts.

## 1. Places & Polities (499 Unique Printed Names, 270,080 Mentions)
| Category | Unique Places | Mentions | Share |
| --- | ---: | ---: | ---: |
| Global places & polities (Base World + Wikidata 2026-11-09) | 244 | 217,400 | 80.5% |
| Canadian customs ports (Canada KG + Wikidata 2026-11-09) | 86 | 33,547 | 12.4% |
| Multi-place customs compounds (`multi_place_aggregate`) | 11 | 2,754 | 1.0% |
| **Subtotal grounded to verified QID(s)** | **341** | **253,701** | **93.9%** |
| Explicit non-geographic / fishery aggregates | 14 | 12,261 | 4.5% |
| **Total resolved** | **355** | **265,962** | **98.5%** |
| Remaining unmatched (`places_review_queue.tsv`) | 144 | 4,118 | 1.5% |

- **Year-aware Empire Evolution `IN_POLITY` links:** **1,067** `(place, year)` pairs in `place_year_polities.tsv`.

## 2. 4-Tier Archival Commodity SKOS v4 Ontology (`2,066` Persistent `htc:` Concepts)
- **Hierarchy:** `htc:scheme` → **9 Macro-Sectors** (`skos:hasTopConcept`) → **44 Mid-Level Commodity Groups** → **181 S14-safe Substance Groups** (`htc:sub_*`) → **2,066 Verbatim Customs Concepts** (residuals cut to **3.08%** / 4,697 rows).
- **6-Dictionary Historical Enrichment & Multi-Sector Audit (Opus 5.5 Verdict: ✅ PUBLISHABLE — `OPUS_SKOS_REVIEW_V5.md`):**
  - **`skos:definition` + clickable `oe:dictionarySource`:** **447** concepts (sense-filtered, zero `"See X"` stubs or homonym mismatches)
  - **`skos:altLabel` (unambiguous common & archaic synonyms):** **69** concepts
  - **Bidirectional `skos:related` (vetted curated, compound & cross-stage pairs — 0 S27 overlaps):** **273** concepts
  - **Merged customs headings (`oe:combinesConcept`):** **11** concepts | **Cross-stage base-material links (`oe:materialConcept`):** active across metals, fibres, leather, and wood
  - **Wikidata Grounding:** **1,421** concepts / **131,256** rows (**86.0%**, or **87.8%** with explicit customs residuals; **0 homonyms** across all 1,421 anchors)
  - **Verified Linnaean `oe:sourceTaxon`:** **233** concepts | **SSSOM mappings:** **3,707** rows (`commodities_mappings.sssom.tsv`)

| Mapping Relation (Layer B — Positive-Allowlisted Non-Taxon Commodity Anchors) | Concepts | Layer-1 Rows | Row Share |
| --- | ---: | ---: | ---: |
| `skos:exactMatch` | 158 | 29,101 | 19.1% |
| `skos:closeMatch` | 9 | 1,632 | 1.1% |
| `skos:broadMatch` | 1,027 | 77,233 | 50.6% |
| `skos:relatedMatch` | 24 | 7,539 | 4.9% |
| **Total grounded to verified Wikidata QID(s)** | **1,218** | **115,505** | **75.7%** |
| Explicit customs residuals (`customs_residual_category`) | 7 | 2,804 | 1.8% |
| **Total grounded + explicit residuals** | **1,225** | **118,309** | **77.5%** |

### Multi-Anchor External LOD & Structural Properties
- **Getty AAT (`P1014`):** **935** concepts (72,106 rows, 47.2%)
- **STW Thesaurus for Economics (`P3911`):** **698** concepts (59,840 rows, 39.2%)
- **FAO AGROVOC (`P8061`, fixed `agrovoc:c_*` IRIs):** **299** concepts (31,442 rows, 20.6%)
- **Verified Linnaean Source Taxa (`oe:sourceTaxon` — zero taxa in `*Match`):** **202** concepts (36,442 rows, 23.9%)
- **Base Material Links (`oe:madeOfMaterial` for manufactures & ores):** **205** concepts (10,306 rows, 6.8%)
- **SSSOM Reversible Mappings Table:** **3,267** rows in `commodities_mappings.sssom.tsv`

### Layer-1 Rows by Tier-1 Macro-Sector
- `htc:sec_food_and_drink` (Food, Drink & Stimulants): **50,065** rows (32.8%, 461 concepts)
- `htc:sec_minerals_metals_manufactures` (Minerals, Fuels, Metals & Industrial Manufactures): **20,217** rows (13.2%, 463 concepts)
- `htc:sec_forestry_timber` (Timber, Lumber & Forest Products): **19,305** rows (12.6%, 177 concepts)
- `htc:sec_hides_skins_tanning` (Hides, Skins, Furs, Leather & Tanning Materials): **17,085** rows (11.2%, 150 concepts)
- `htc:sec_fibres_textiles` (Textile Fibres, Yarns, Fabrics & Apparel): **11,370** rows (7.4%, 255 concepts)
- `htc:sec_botanicals_dyes_chemicals` (Latexes, Resins, Dyes, Drugs & Chemicals): **10,966** rows (7.2%, 157 concepts)
- `htc:sec_livestock_fodder` (Livestock, Draft Animals & Animal Feed): **8,146** rows (5.3%, 58 concepts)
- `htc:sec_oils_fats_waxes` (Oils, Fats, Oilseeds, Waxes & Soap): **8,028** rows (5.3%, 91 concepts)
- `htc:sec_unclassified_residuals` (Unenumerated & Residual Customs Categories): **7,443** rows (4.9%, 254 concepts)

### Layer-1 Rows by Ecological `oe:landBasis`
- `terrestrial_crop`: **49,125** rows (32.2%)
- `terrestrial_pasture`: **37,186** rows (24.4%)
- `terrestrial_forest`: **23,969** rows (15.7%)
- `industrial_manufactured`: **18,039** rows (11.8%)
- `mineral`: **9,838** rows (6.4%)
- `unclassified`: **7,443** rows (4.9%)
- `marine`: **7,025** rows (4.6%)

### Layer-1 Rows by Theodoridis (2018) 5-Bucket Rollup
- `raw_materials`: **69,650** rows (45.6%)
- `manufactured_articles`: **23,193** rows (15.2%)
- `animals_and_animal_products`: **19,252** rows (12.6%)
- `other_food_drink_spices`: **17,035** rows (11.2%)
- `grain_and_flour`: **16,060** rows (10.5%)
- `unclassified`: **7,435** rows (4.9%)
