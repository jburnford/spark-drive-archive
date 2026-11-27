"""Publish the project's compact record IDs as dereferenceable GitHub Pages IRIs."""
import json
import re
from itertools import groupby

from rdflib import Graph, Literal, RDF, URIRef

VOCAB_VERSION = "7.0"
WD_SNAPSHOT = "2026-11-09"
SITE = "https://jimclifford.ca/spark-drive-archive/"
NAMESPACES = {"htc": SITE + "id/", "htc1866": SITE + "customs-1866/", "oe": SITE + "ontology/"}
MAPPING_SET = NAMESPACES["htc"] + "mappings/#resource"


def public_id(local_id, fragment):
    """Keep printed notations intact and shard the high-volume series before minting."""
    prefix, name = local_id.split(":", 1)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name) or fragment not in ("resource", "concept"):
        raise ValueError(f"Invalid entity identifier: {local_id}#{fragment}")
    shard = ""
    if prefix == "htc":
        if name[:2].isdigit():
            shard = name[:2] + "/"
        elif "_" in name:
            shard = name.split("_", 1)[0] + "/"
    elif prefix == "oe" and name.startswith("use_"):
        shard = name.split("__", 1)[0] + "/"
    return f"{prefix}:{shard}{name}/#{fragment}"


def short_id(identifier):
    prefix, path = identifier.split(":", 1)
    return prefix + ":" + path.partition("/#")[0].rsplit("/", 1)[-1]


def record_path(uri):
    """Return the Pages path, rejecting unsafe filenames and non-project IRIs."""
    for namespace in NAMESPACES.values():
        if uri.startswith(namespace):
            local, sep, fragment = uri[len(namespace):].partition("/#")
            if sep and fragment in {"concept", "resource"} and re.fullmatch(r"(?:[A-Za-z0-9_-]+/)?[A-Za-z0-9_-]+", local):
                return namespace[len(SITE):] + local + "/"
            raise ValueError(f"Invalid project identifier: {uri}")
    raise ValueError(f"Unknown project namespace: {uri}")


def public_document(document):
    """Expand local references in RDF positions only. The extended builder also reads published core nodes."""
    names = {}
    for node in document["@graph"]:
        identifier = node["@id"]
        if identifier.partition(":")[0] not in NAMESPACES:
            continue
        short = short_id(identifier)
        types = node["@type"]
        if isinstance(types, str):
            types = [types]
        fragment = "concept" if "skos:Concept" in types else "resource"
        names[short] = public_id(short, fragment)

    def identifier(value):
        if ":" not in value or value.partition(":")[0] not in NAMESPACES:
            return value
        return names[short_id(value)]

    def convert(value, key=None):
        if isinstance(value, list):
            return [convert(item, key) for item in value]
        if isinstance(value, dict):
            return {identifier(k): convert(v, k) for k, v in value.items()}
        if key in ("@type", "@id"):
            return identifier(value)
        return value

    context = {identifier(k): NAMESPACES.get(k, v) for k, v in document["@context"].items()}
    return {"@context": context, "@graph": convert(document["@graph"])}


def write_graph(jsonld_path, document):
    """Write both serializations from the same set of nodes in a deterministic order."""
    public = public_document(document)
    data = json.dumps(public, ensure_ascii=False, indent=2)
    graph = Graph().parse(data=data, format="json-ld")
    prefixes = {key: value for key, value in public["@context"].items() if isinstance(value, str)}
    ttl = turtle_text(graph, prefixes)
    jsonld_path.write_text(data + "\n", encoding="utf-8")
    jsonld_path.with_suffix(".ttl").write_text(ttl, encoding="utf-8")


def turtle_text(triples, prefixes):
    """Stable Turtle with relative local IRIs and an explicit, portable base."""
    standard = {url: key for key, url in prefixes.items() if key not in NAMESPACES}

    def turtle(term):
        if isinstance(term, Literal):
            return term.n3()
        if not isinstance(term, URIRef):
            raise ValueError(f"Expected a named resource, got {term!r}")
        uri = str(term)
        if uri.startswith(SITE):
            return f"<{uri[len(SITE):]}>"
        for ns, prefix in standard.items():
            if uri.startswith(ns) and re.fullmatch(r"[A-Za-z0-9_-]+", uri[len(ns):]):
                return f"{prefix}:{uri[len(ns):]}"
        return term.n3()

    lines = [f"@base <{SITE}> .", *(f"@prefix {k}: <{v}> ." for k, v in prefixes.items())]
    for subject, triples in groupby(sorted(triples), key=lambda triple: triple[0]):
        properties = []
        for predicate, values in groupby(triples, key=lambda triple: triple[1]):
            objects = ", ".join(turtle(obj) for _, _, obj in values)
            properties.append(f"{'a' if predicate == RDF.type else turtle(predicate)} {objects}")
        lines.append("\n" + turtle(subject) + " " + " ;\n    ".join(properties) + " .")
    return "\n".join(lines) + "\n"
