#!/usr/bin/env bash
# Rebuild every published artifact in dependency order, then write the manifest and verify the result.
# Needs: python with duckdb + rdflib, the raw sources under human_trade/raw_sources/, and the external data
# roots (override with OE_WD_SLIM_GLOB, OE_OCR_ROOT, OE_GUTENBERG_ROOT). Outputs are deterministic.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
"$PY" human_trade/scripts/build_human_layer1.py          # raw transcriptions -> observations
"$PY" human_trade/scripts/ground_places_v2.py            # places and polities
"$PY" scripts/parse_commercial_dictionaries.py           # six dictionaries -> lexicon
"$PY" scripts/ground_dictionary_binomials.py             # Linnaean names -> taxa
"$PY" human_trade/scripts/build_skos_v4.py               # customs vocabulary (+ curated tables)
"$PY" scripts/build_commodity_gazetteer.py               # document-attested tier, gazetteer, extended vocabulary
"$PY" scripts/unpack_unenumerated_from_books.py          # catalogue of unenumerated commodities
"$PY" scripts/build_end_use_network.py                   # end-use network and evidence records
"$PY" human_trade/scripts/build_skos_html_inspector.py   # HTML inspector and docs/index.html
"$PY" scripts/build_entity_pages.py
"$PY" scripts/build_manifest.py
"$PY" scripts/verify.py
