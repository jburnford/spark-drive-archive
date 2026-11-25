# Sources and Publishability (`open_empire`)

This repository tracks **Tier 1 (Open Public Sources)** metadata, manifests, scripts, and derived lexicons, plus **extracted structured data & ontologies** derived from Layer-1 human-transcribed trade tables.

**Strict Rights Exclusions (never committed to GitHub):**
- Reading-room archival photography and raw OCR (stored locally in `/mnt/data/jic823/archival_corpus` and `/mnt/data/jic823/tna_cust_ledgers`) are **never** pushed to GitHub.
- Raw archival spreadsheets and unpermissioned raw archival dumps (`human_trade/raw_sources/`) are ignored via `.gitignore`.
- Licensed/vendor digitized corpora (e.g., Adam Matthew `CO 879` Confidential Print Africa, paywalled JSTOR Global Plants, `historyofceylontea.com`) are **never** scraped or stored here.

## Registered Open Collections (Tier 1 — Public Domain)

| Wave | Series / Collection | Repository | Rights / Publishability | Manifest / Output |
| :--- | :--- | :--- | :--- | :--- |
| **Wave 1b** | P. L. Simmonds, *The Commercial Dictionary of Trade Products* (1892, `b21780535`) | Internet Archive / Wellcome | Public domain; Chandra-2 OCR & derived lexicon open | `manifests/wave1b_dictionaries_batch1_canonical.tsv` → `dictionaries/` |
| **Wave 1b** | T. Mortimer, *A General Commercial Dictionary* (1823, `generalcommercia00mort`) | Internet Archive | Public domain; Chandra-2 OCR & derived lexicon open | `manifests/wave1b_dictionaries_batch2_narval.tsv` → `dictionaries/` |
| **Wave 1b** | J. R. McCulloch, *A Dictionary, Practical, Theoretical, and Historical, of Commerce* (1880, `dictionaryprac00mccu`) | Internet Archive | Public domain; Chandra-2 OCR & derived lexicon open | `manifests/wave1b_dictionaries_batch2_narval.tsv` → `dictionaries/` |
| **Wave 1b** | G. Watt, *The Commercial Products of India* (1908, `b31361584`) | Internet Archive / Wellcome | Public domain; Chandra-2 OCR & derived lexicon open | `manifests/wave1b_dictionaries_batch2_narval.tsv` → `dictionaries/` |
| **Wave 1b** | P. L. Simmonds, *The Commercial Products of the Vegetable Kingdom* (1854, PG #15191) | Project Gutenberg / IA mirror | Public domain; proofread text & derived lexicon open | `dictionaries/commercial_dictionaries_lexicon.jsonl` |
| **Wave 1b** | A. Ure, *A Dictionary of Arts, Manufactures, and Mines* (1853, PG #44562) | Project Gutenberg / IA mirror | Public domain; proofread text & derived lexicon open | `dictionaries/commercial_dictionaries_lexicon.jsonl` |
| **Wave 1** | *Bulletin of Miscellaneous Information* (Royal Gardens, Kew) | Internet Archive / BHL | Public domain; OCR & derived data may be published | `manifests/wave1_economic_botany.tsv` |
| **Wave 1** | *Bulletin of the Imperial Institute* | Internet Archive | Public domain (pre-1928 runs); OCR & derived data may be published | `manifests/wave1_economic_botany.tsv` |
| **Wave 1** | *Agricultural Bulletin of the Straits and Federated Malay States* / *Gardens' Bulletin* | Internet Archive / BHL | Public domain (pre-1928 runs); OCR & derived data may be published | `manifests/wave1_economic_botany.tsv` |
| **Wave 1** | *A Dictionary of the Economic Products of India* (George Watt) & *The Agricultural Ledger* | Internet Archive / DLI | Public domain; OCR & derived data may be published | `manifests/wave1_economic_botany.tsv` |
| **Wave 1** | *Journal of the Society of Arts* (Royal Society of Arts) | Internet Archive | Public domain (pre-1928 runs); OCR & derived data may be published | `manifests/wave1_economic_botany.tsv` |
| **Wave 2** | Colonial Blue Books beyond Ceylon (`collection:colonial-office-gb-publications` + open IA scans) | Internet Archive | Public domain / Crown open scans; OCR & parsed tables may be published | `manifests/wave2_colonial_bluebooks.tsv` |
| **Wave 3** | Regional "Ghost Acres of Ghost Acres" (Burma/India, West Africa, Australasia, SAOA) | Internet Archive / BHL / SAOA | Public domain / Open Access; verify per-item license before publishing raw OCR | `manifests/wave3_regional_ghost_acres.tsv` |

## Extracted Archival Data (Tier 2 — Extracted Structured Tables & Ontologies Only)
- **Layer 1 (`human_trade/layer1_human/`):** Structured extracted observations, unique printed commodity/place/unit headings, place/polity grounding, and SKOS v4 commodity vocabulary derived from historical British (`KEW_CUST 4/5`, HCPP *Annual Statement of Trade*) and Canadian (*Sessional Papers*) customs trade ledgers. Raw archival photographs, PDFs, and raw working spreadsheets are excluded from this repository.
