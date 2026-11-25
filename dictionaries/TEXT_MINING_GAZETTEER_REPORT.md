# 19th-Century Commodity Text-Mining Gazetteer & Extended SKOS Report

Generated 2026-11-25 by `scripts/build_commodity_gazetteer.py` for downstream NER and text mining across open 19th-century botanical, commercial, and archival corpora (zero quantity estimation).

## Coverage Summary
- **Layer-1 Customs-Enumerated Core (`htc:0001`–`htc:2066`):** **2,066** concepts (enriched with 123 additional vernacular `altLabel`s from Danika's Drugs Project & 1866 Customs List)
- **Document-Attested Non-Enumerated Tier (`htc:doc_*`):** **601** concepts (123 from Danika's Drugs / 1866 Customs List + 478 from the 6 commercial dictionaries; **139** grounded to verified Wikidata QIDs; **208** with verified CoL/Wikidata Linnaean taxa)
- **Total Combined SKOS Concepts (`commodities_skos_extended.ttl`):** **2,667** verbatim + document-attested concepts
- **Total Text-Mining Surface Forms (`commodity_gazetteer.tsv`):** **3,504** normalized strings (`prefLabel` + `altLabel` + Latin binomials)

## Document-Attested Concepts by Subsumed Customs Catch-All
| Catch-All Customs Heading | Document-Attested Concepts |
|---|---:|
| `htc:0122` **Drugs Unenumerated** | 129 |
| `htc:0054` **Dye Stuffs & Dye Woods Unenumerated** | 74 |
| `htc:0506` **Chemical Manufactures and Products Unenumerated** | 64 |
| `htc:0408` **Spices Unenumerated (incl. Condiments & Minor Foods)** | 55 |
| `htc:0124` **Oil & Essential Oil Unenumerated** | 50 |
| `htc:0071` **Furs, Skins & Marine Products Unenumerated** | 45 |
| `htc:0012` **Seeds, Nuts & Kernels for Oil Unenumerated** | 43 |
| `htc:0220` **Gum, Resin & Elastic-Gum Unenumerated** | 38 |
| `htc:0070` **Wood & Cabinet Timber Unenumerated** | 36 |
| `htc:0822` **Vegetable Fibres Unenumerated (incl. Esparto, Cordage & Brush Fibres)** | 30 |
| `htc:0010` **Other Articles** | 27 |
| `htc:0041` **Tanning Barks & Extracts Unenumerated** | 10 |
