# 19th-Century Commodity Text-Mining Gazetteer & Extended SKOS Report

Generated 2026-11-25 by `scripts/build_commodity_gazetteer.py` for downstream NER and text mining across open 19th-century botanical, commercial, and archival corpora (zero quantity estimation).

## Coverage Summary
- **Layer-1 Customs-Enumerated Core (`htc:0001`–`htc:2066`):** **2,066** concepts (enriched with 273 additional vernacular `altLabel`s from Danika's Drugs Project & 1866 Customs List)
- **Document-Attested Non-Enumerated Tier (`htc:doc_*`):** **380** concepts (43 from Danika's Drugs / 1866 Customs List + 337 from the 6 commercial dictionaries; **92** grounded to verified Wikidata QIDs; **148** with verified CoL/Wikidata Linnaean taxa)
- **Total Combined SKOS Concepts (`commodities_skos_extended.ttl`):** **2,446** verbatim + document-attested concepts
- **Total Text-Mining Surface Forms (`commodity_gazetteer.tsv`):** **3,343** normalized strings (`prefLabel` + `altLabel` + Latin binomials)

## Document-Attested Concepts by Subsumed Customs Catch-All
| Catch-All Customs Heading | Document-Attested Concepts |
|---|---:|
| `htc:0122` **Drugs Unenumerated** | 86 |
| `htc:0054` **Dye Stuffs Unenumerated** | 42 |
| `htc:0124` **Oil Unenumerated** | 36 |
| `htc:0070` **Wood Unenumerated** | 32 |
| `htc:0506` **Chemical Manufactures and Products Unenumerated** | 31 |
| `htc:0408` **Spices Unenumerated** | 25 |
| `htc:0220` **Gum Unenumerated** | 23 |
| `htc:0822` **Esparto and other Vegetable Fibres for making Paper** | 20 |
| `htc:0012` **Seeds Unenumerated Other Sorts** | 17 |
| `htc:0010` **Other Articles** | 9 |
| `htc:0071` **Furs Unenumerated Undressed** | 8 |
| `htc:0402` **Fruit Raw unenumerated** | 8 |
| `htc:1905` **Minerals Unenumerated** | 7 |
| `htc:0041` **Bark For Tanners and Dyers Use** | 6 |
| `htc:0382` **Ore Unenumerated** | 6 |
| `htc:0085` **Vegetables Unenumerated** | 6 |
| `htc:0351` **Fisheries Articles Unenumerated** | 4 |
| `htc:0352` **Nuts and Kernels Unenumerated** | 3 |
| `htc:0421` **Grains Unenumerated** | 3 |
| `htc:0653` **Precious Stones Unset** | 1 |
| `htc:0205` **Stone** | 1 |
| `htc:0427` **Zinc Ore** | 1 |
| `htc:0290` **Isinglass** | 1 |
| `htc:0106` **Leather** | 1 |
| `htc:1026` **Oil Seed Cake Unenumerated** | 1 |
| `htc:1343` **Alkali of other Sorts Unenumerated** | 1 |
| `htc:0316` **Clover and Grass Seeds** | 1 |
