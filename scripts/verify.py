#!/usr/bin/env python3
"""Verify the PUBLISHED files only (no restricted sources, no Wikidata snapshot, no network).

    pip install rdflib && python scripts/verify.py

Checks: files match MANIFEST.json; Turtle and JSON-LD agree; the extended vocabulary contains the core; every
end-use commodity joins to its concept by IRI; tier filters recover both tiers; hierarchy is a clean tree;
no attestation date outside the corpus period; every end-use assertion carries evidence. Exit code 1 on failure.
"""
import gzip
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, SKOS, URIRef

ROOT = Path(__file__).resolve().parents[1]
GROUND = ROOT / "human_trade" / "layer1_human" / "grounding"
FAIL = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' — ' + str(detail)) if detail else ''}")
    if not ok:
        FAIL.append(name)


def main():
    man = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    H = Namespace(man["namespace"])
    scheme = H["scheme/#resource"]

    def oe(name):
        return URIRef(man["ontology_namespace"] + name + "/#resource")

    print(f"Vocabulary version {man['vocabulary_version']} (Wikidata snapshot {man['wikidata_snapshot']})")

    bad = []
    for rel, meta in man["files"].items():
        p = ROOT / rel
        if not p.exists():
            bad.append(f"missing {rel}")
            continue
        data = gzip.open(p, "rb").read() if p.suffix == ".gz" else p.read_bytes()
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            bad.append(f"changed {rel}")
    check(f"{len(man['files'])} published files match the manifest", not bad, bad[:5])

    g = {}
    for stem in ("commodities_skos", "commodities_skos_extended", "end_use_network_skos"):
        t = Graph().parse(GROUND / f"{stem}.ttl", format="turtle")
        j = Graph().parse(GROUND / f"{stem}.jsonld", format="json-ld")
        check(f"{stem}: Turtle = JSON-LD ({len(t):,} triples)", len(t - j) == 0 and len(j - t) == 0)
        g[stem] = t
    core, ext, net = g["commodities_skos"], g["commodities_skos_extended"], g["end_use_network_skos"]
    check("extended vocabulary contains every core triple", len(core - ext) == 0, len(core - ext))

    members = set(ext.subjects(SKOS.inScheme, scheme))
    inputs = set(net.subjects(oe("usedInIndustry"), None))
    check(f"all {len(inputs)} end-use commodities join to a vocabulary concept by IRI", bool(inputs) and inputs <= members, len(inputs - members))
    fwd = set(net.subject_objects(oe("usedInIndustry")))
    inv = {(o, s) for s, o in net.subject_objects(oe("usesCommodityInput"))}
    check("every end-use link has its inverse", fwd == inv)
    asserts = set(net.subjects(RDF.type, oe("EndUseAssertion")))
    pairs = {(next(net.objects(a, oe("assertsCommodity"))), next(net.objects(a, oe("assertsIndustry")))) for a in asserts}
    check(f"every end-use link has an evidence record ({len(asserts)})", bool(asserts) and pairs == fwd)
    check("every evidence record cites at least one passage", all(any(net.objects(a, oe("hasEvidence"))) for a in asserts))

    registry = sum(1 for _ in open(GROUND / "htc_id_registry.tsv", encoding="utf-8")) - 1
    docs = sum(1 for l in open(GROUND / "document_attested_concepts.jsonl", encoding="utf-8") if l.strip())
    n_cust = len(set(ext.subjects(oe("attestationBasis"), Literal("customs_enumerated"))))
    n_doc = len(set(ext.subjects(oe("attestationBasis"), Literal("document_attested"))))
    check(f"tier filter: customs_enumerated = registry ({registry})", n_cust == registry, n_cust)
    check(f"tier filter: document_attested = document table ({docs})", n_doc == docs, n_doc)

    concepts = {s for s in ext.subjects(SKOS.inScheme, scheme) if (s, RDF.type, SKOS.Concept) in ext}
    broader = defaultdict(set)
    for s, o in ext.subject_objects(SKOS.broader):
        broader[s].add(o)
    tops = set(ext.objects(scheme, SKOS.hasTopConcept))
    check("no concept has more than one parent", not [c for c in concepts if len(broader[c]) > 1])
    check("no orphan concepts", not [c for c in concepts if c not in broader and c not in tops])

    def cyclic(c):
        seen, cur = set(), c
        while cur in broader and broader[cur]:
            cur = next(iter(broader[cur]))
            if cur in seen or cur == c:
                return True
            seen.add(cur)
        return False
    check("no cycles in skos:broader", not any(cyclic(c) for c in concepts))
    subjects = set(ext.subjects())
    dangling = {o for _, _, o in ext if isinstance(o, URIRef) and str(o).startswith(str(H)) and o not in subjects}
    check("no dangling local IRIs", not dangling, sorted(dangling)[:3])
    rel = set(ext.subject_objects(SKOS.related))
    check("skos:related is symmetric", all((b, a) in rel for a, b in rel))
    exact = defaultdict(set)
    for s, o in ext.subject_objects(SKOS.exactMatch):
        exact[o].add(s)
    check("no external item is the exactMatch of two concepts", not [o for o, v in exact.items() if len(v) > 1])

    years = [int(o) for p in (oe("firstAttested"), oe("lastAttested")) for o in ext.objects(None, p)]
    check(f"attestation years within 1600–1950 ({min(years)}–{max(years)})", all(1600 <= y <= 1950 for y in years))
    readings = set(ext.subjects(RDF.type, oe("ScopedReading")))
    check(f"every scoped reading points at a registered heading ({len(readings)})",
          all(any(o in concepts for o in ext.objects(r, oe("readingOf"))) for r in readings))

    from verify_entity_pages import verify_pages
    verify_pages(man, ext, net, check)

    print(f"\n{'ALL CHECKS PASSED' if not FAIL else str(len(FAIL)) + ' CHECK(S) FAILED: ' + '; '.join(FAIL)}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
