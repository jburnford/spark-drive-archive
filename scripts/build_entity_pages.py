#!/usr/bin/env python3
"""Build the GitHub Pages records from the released graphs (no private inputs or network)."""
import csv
import gzip
import json
import sys
from collections import defaultdict
from html import escape
from pathlib import Path

from rdflib import DCTERMS, OWL, Graph, Literal, RDF, RDFS, SKOS, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "human_trade" / "scripts"))
from public_rdf import MAPPING_SET, NAMESPACES, SITE, record_path, turtle_text

DOCS = ROOT / "docs"
GROUND = ROOT / "human_trade" / "layer1_human" / "grounding"
CROSSWALK = "identifier-crosswalk.tsv"
STEMS = ("commodities_skos_extended", "end_use_network_skos")
DATA = "https://raw.githubusercontent.com/jburnford/spark-drive-archive/main/human_trade/layer1_human/grounding/"


def read_graph():
    graph = Graph()
    for stem in STEMS:
        graph.parse(GROUND / f"{stem}.ttl", format="turtle")
    mapping_file = "commodities_mappings.sssom.tsv"
    with (GROUND / mapping_file).open(encoding="utf-8") as f:
        meta = dict(line[1:].strip().split(": ", 1) for line in f
                    if line.startswith(("#mapping_set_id: ", "#license: ")))
    subject = URIRef(meta["mapping_set_id"])
    if str(subject) != MAPPING_SET:
        raise ValueError("Unexpected SSSOM mapping set identifier")
    graph.add((subject, RDFS.label, Literal("Commodity mappings", lang="en")))
    graph.add((subject, DCTERMS.license, URIRef(meta["license"])))
    graph.add((subject, RDFS.seeAlso, URIRef(DATA + mapping_file)))
    return graph


def json_value(term):
    if isinstance(term, URIRef):
        return {"@id": str(term)}
    value = {"@value": str(term)}
    if term.language:
        value["@language"] = term.language
    elif term.datatype:
        value["@type"] = str(term.datatype)
    return value


def link(uri, text, root):
    url = str(uri)
    if url.startswith(SITE):
        url = root + url[len(SITE):]
    if not url.startswith(("../", "http://", "https://")):
        return escape(str(text))
    return f'<a href="{escape(url, quote=True)}">{escape(str(text))}</a>'


def title(graph, uri):
    for prop in (SKOS.prefLabel, RDFS.label):
        label = graph.value(uri, prop)
        if label:
            return str(label)
    return graph.namespace_manager.normalizeUri(uri).strip("<>")


def render(graph, subject, labels, local_id):
    uri = str(subject)
    root = "../" * record_path(uri).count("/")
    fragment = uri.split("#")[-1]
    label = labels[subject]
    node = {"@id": uri}
    fields = defaultdict(list)
    for prop, obj in sorted(graph.predicate_objects(subject)):
        if prop == RDF.type:
            node.setdefault("@type", []).append(str(obj))
        else:
            node.setdefault(str(prop), []).append(json_value(obj))
        fields[prop].append(obj)

    def display(obj):
        if isinstance(obj, URIRef):
            return link(obj, labels.get(obj) or title(graph, obj), root)
        return escape(str(obj))

    def field(name, values):
        return f"<dt>{name}</dt><dd>" + "<br>".join(display(v) for v in values) + "</dd>"

    definitions = fields.pop(SKOS.definition, [])
    fields.pop(RDFS.label, None)
    fields.pop(SKOS.prefLabel, None)
    details = []
    for prop, values in fields.items():
        details.append(field(link(prop, labels.get(prop) or title(graph, prop), root), values))
    for prop, heading in [(SKOS.broader, "Narrower concepts"),
                          (URIRef(NAMESPACES["oe"] + "assertsCommodity/#resource"), "End-use evidence"),
                          (URIRef(NAMESPACES["oe"] + "readingOf/#resource"), "Historical readings")]:
        incoming = sorted(graph.subjects(prop, subject), key=lambda s: (labels[s], s))
        if incoming:
            details.append(field(heading, incoming))
    # Escape markup delimiters in RDF literals before embedding JSON in a raw-text HTML element.
    embedded = json.dumps(node, ensure_ascii=False, indent=2).replace("<", r"\u003c")
    definition_html = "".join(f"<p>{escape(str(v))}</p>" for v in definitions)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(label)} · Open Empire</title><link rel="stylesheet" href="{root}records.css">
<link rel="canonical" href="{escape(uri.split('#')[0])}">
<link rel="alternate" type="text/turtle" href="entity.ttl">
<script type="application/ld+json">{embedded}</script></head>
<body><header><nav><a href="{root}">Open Empire vocabulary</a></nav></header>
<main id="{fragment}"><p class="notation">{escape(local_id)}</p><h1>{escape(label)}</h1>
{definition_html}<dl>{''.join(details)}</dl>
<footer><a href="{escape(uri)}">Permanent identifier</a> · <a href="entity.ttl">Download this record (Turtle)</a> · <a href="{root}{CROSSWALK}">Identifier crosswalk</a></footer>
</main></body></html>
"""


PREFIXES = {"skos": str(SKOS), "rdfs": str(RDFS), "owl": str(OWL), "dcterms": str(DCTERMS)}


def write_downloads(graph):
    bulk = DOCS / "data" / "open-empire.ttl.gz"
    bulk.parent.mkdir(exist_ok=True)
    bulk.write_bytes(gzip.compress(turtle_text(graph, PREFIXES).encode("utf-8"), mtime=0))
    void = f'''@base <{SITE}> .
@prefix void: <http://rdfs.org/ns/void#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .

<void.ttl#dataset> a void:Dataset ;
    dcterms:title "Open Empire historical trade vocabulary and industry network"@en ;
    foaf:homepage <{SITE}> ;
    void:dataDump <data/open-empire.ttl.gz> ;
    void:triples {len(graph)} ;
    void:exampleResource <id/00/0056/#concept> ;
    void:vocabulary <{SKOS}> .
'''
    (DOCS / "void.ttl").write_text(void, encoding="utf-8")


def main():
    graph = read_graph()
    labels = {s: title(graph, s) for s in set(graph.subjects())}
    pages = {}
    for subject in sorted(labels):
        if not str(subject).startswith(SITE):
            continue
        route = record_path(str(subject))
        if route.casefold() in pages:
            raise ValueError(f"Two records would share {route}")
        pages[route.casefold()] = subject

    with (DOCS / CROSSWALK).open(encoding="utf-8") as f:
        registry = list(csv.DictReader(f, delimiter="\t"))
    targets = {r["canonical_uri"] for r in registry}
    if missing := targets - {str(uri) for uri in pages.values()}:
        raise ValueError(f"Crosswalk targets missing from the release: {sorted(missing)[:5]}")
    for subject in pages.values():
        route = record_path(str(subject))
        prefix = next(k for k, v in NAMESPACES.items() if str(subject).startswith(v))
        local_id = f"{prefix}:{route.rstrip('/').rsplit('/', 1)[-1]}"
        path = DOCS / route / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        page = render(graph, subject, labels, local_id)
        if not path.exists() or path.read_text(encoding="utf-8") != page:
            path.write_text(page, encoding="utf-8")
        turtle = turtle_text(graph.triples((subject, None, None)), PREFIXES)
        path.with_name("entity.ttl").write_text(turtle, encoding="utf-8")
    write_downloads(graph)
    print(f"Built {len(pages):,} entity pages")


if __name__ == "__main__":
    main()
