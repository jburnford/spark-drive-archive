#!/usr/bin/env python3
"""Write MANIFEST.json: one record tying the published files to a vocabulary version, the curated tables
and the authority snapshot they were built from. Run last, after every builder.

Hashes are SHA-256 of file content (gzip files are hashed uncompressed, so a rebuild with a new gzip
timestamp does not change the manifest). `scripts/verify.py` checks the published files against it.
"""
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "human_trade" / "scripts"))
import build_skos_v4 as v4  # noqa: E402

GROUND = ROOT / "human_trade" / "layer1_human" / "grounding"
PUBLISHED = (
    sorted(p for p in GROUND.iterdir() if p.is_file() and p.suffix in (".ttl", ".jsonld", ".jsonl", ".tsv", ".json", ".html"))
    + sorted((ROOT / "dictionaries").glob("*.jsonl")) + sorted((ROOT / "dictionaries").glob("*.tsv"))
    + [ROOT / "human_trade" / "layer1_human" / "human_trade_observations.tsv.gz", ROOT / "docs" / "index.html"]
    + sorted((ROOT / "human_trade" / "layer1_human" / "names").glob("*.tsv"))
)


def digest(path: Path) -> str:
    data = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def rows(path: Path) -> int:
    return sum(1 for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")) - 1


def main():
    curated = sorted(GROUND.glob("curated_*.tsv"))
    manifest = {
        "vocabulary": "Open Empire historical trade commodities",
        "vocabulary_version": v4.VOCAB_VERSION,
        "namespace": v4.BASE_URI,
        "ontology_namespace": v4.OE_NS,
        "wikidata_snapshot": v4.WD_SNAPSHOT,
        "curated_tables": {p.name: rows(p) for p in curated},
        "superseded": ["archive/end_use_pilot/ (3-industry pilot; do not load alongside end_use_network_*)"],
        "files": {str(p.relative_to(ROOT)): {"sha256": digest(p), "bytes": p.stat().st_size} for p in PUBLISHED if p.exists()},
    }
    out = ROOT / "MANIFEST.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(manifest['files'])} files, vocabulary version {v4.VOCAB_VERSION})")


if __name__ == "__main__":
    main()
