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
from public_rdf import NAMESPACES, SITE, VOCAB_VERSION, WD_SNAPSHOT

DOCS = ROOT / "docs"
GROUND = ROOT / "human_trade" / "layer1_human" / "grounding"
PUBLISHED = (
    sorted(p for p in GROUND.iterdir() if p.is_file() and "_v3." not in p.name and p.suffix in (".ttl", ".jsonld", ".jsonl", ".tsv", ".json", ".html"))
    + sorted((ROOT / "dictionaries").glob("*.jsonl")) + sorted((ROOT / "dictionaries").glob("*.tsv"))
    + [ROOT / "human_trade" / "layer1_human" / "human_trade_observations.tsv.gz", ROOT / "docs" / "index.html",
       ROOT / "docs" / "data" / "open-empire.ttl.gz", ROOT / "docs" / "void.ttl",
       DOCS / ".nojekyll", DOCS / "records.css", ROOT / "docs" / "identifier-crosswalk.tsv"]
    + sorted((ROOT / "human_trade" / "layer1_human" / "names").glob("*.tsv"))
)


def digest(path: Path) -> str:
    data = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def entity_files_digest():
    result = hashlib.sha256()
    pages = sorted((*DOCS.glob("*/**/index.html"), *DOCS.rglob("entity.ttl")))
    for path in pages:
        result.update(f"{path.relative_to(DOCS).as_posix()}\t{digest(path)}\n".encode())
    return result.hexdigest()


def rows(path: Path) -> int:
    return sum(1 for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")) - 1


def main():
    curated = sorted(GROUND.glob("curated_*.tsv"))
    manifest = {
        "vocabulary": "Open Empire historical trade commodities",
        "vocabulary_version": VOCAB_VERSION,
        "namespace": NAMESPACES["htc"],
        "ontology_namespace": NAMESPACES["oe"],
        "wikidata_snapshot": WD_SNAPSHOT,
        "curated_tables": {p.name: rows(p) for p in curated},
        "entity_pages": {
            "base": SITE,
            "sha256": entity_files_digest(),
            "count": sum(1 for p in (ROOT / "docs").glob("*/**/index.html")),
            "crosswalk": "docs/identifier-crosswalk.tsv",
        },
        "superseded": ["archive/end_use_pilot/ (3-industry pilot; do not load alongside end_use_network_*)"],
        "files": {str(p.relative_to(ROOT)): {"sha256": digest(p), "bytes": p.stat().st_size} for p in PUBLISHED if p.exists()},
    }
    out = ROOT / "MANIFEST.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(manifest['files'])} files, vocabulary version {VOCAB_VERSION})")


if __name__ == "__main__":
    main()
