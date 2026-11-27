"""Offline checks for the static Linked Data distribution."""
import csv
import gzip
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin

from rdflib import DCTERMS, Graph, Namespace, RDF, RDFS, URIRef

from build_manifest import DOCS, entity_files_digest


class RecordHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.jsonld = []
        self.in_jsonld = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if "href" in attrs:
            self.links.append(attrs)
        if tag == "script":
            self.in_jsonld = attrs.get("type") == "application/ld+json"

    def handle_data(self, data):
        if self.in_jsonld:
            self.jsonld.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_jsonld = False


def verify_pages(manifest, extended, network, check):
    info = manifest["entity_pages"]
    site = info["base"]
    mapping = URIRef(manifest["namespace"] + "mappings/#resource")
    void = Namespace("http://rdfs.org/ns/void#")
    description = Graph().parse(DOCS / "void.ttl", format="turtle")
    dataset = URIRef(site + "void.ttl#dataset")
    download = "data/open-empire.ttl.gz"
    bulk = Graph().parse(data=gzip.decompress((DOCS / download).read_bytes()), format="turtle")
    check("VoID describes the full download", (dataset, RDF.type, void.Dataset) in description
          and (dataset, void.dataDump, URIRef(site + download)) in description
          and int(description.value(dataset, void.triples)) == len(bulk))
    expected = set(extended) | set(network)
    metadata = set(bulk.triples((mapping, None, None)))
    check(f"bulk graph contains the released graphs and mapping set ({len(bulk):,} triples)",
          set(bulk) == expected | metadata and {p for _, p, _ in metadata} == {RDFS.label, DCTERMS.license, RDFS.seeAlso})
    subjects = {str(s) for s in bulk.subjects() if str(s).startswith(site)}
    with (DOCS / "identifier-crosswalk.tsv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    check("previous IRIs and short keys map unambiguously to published records",
          bool(rows) and all(len({r[key] for r in rows}) == len(rows) for key in ("local_id", "previous_uri", "canonical_uri"))
          and all(r["canonical_uri"] in subjects for r in rows))

    routes = {urldefrag(uri)[0][len(site):] for uri in subjects}
    html_routes = {p.parent.relative_to(DOCS).as_posix() + "/" for p in DOCS.glob("*/**/index.html")}
    ttl_routes = {p.parent.relative_to(DOCS).as_posix() + "/" for p in DOCS.rglob("entity.ttl")}
    check(f"{len(subjects):,} paired HTML and Turtle records match the manifest",
          len(subjects) == len(routes) == info["count"] and html_routes == ttl_routes == routes
          and entity_files_digest() == info["sha256"])
    home = RecordHTML()
    home.feed((DOCS / "index.html").read_text(encoding="utf-8"))
    check("Pages root serves static files and advertises the dataset downloads",
          (DOCS / ".nojekyll").is_file() and
          {site + path for path in (download, "identifier-crosswalk.tsv", "void.ttl")}
          <= {urljoin(site, a["href"]) for a in home.links})

    failures = []
    files = {site + p.relative_to(DOCS).as_posix() for p in DOCS.rglob("*") if p.is_file()}
    for uri in sorted(subjects):
        document, fragment = urldefrag(uri)
        page = DOCS / document[len(site):] / "index.html"
        try:
            html = RecordHTML()
            html.feed(page.read_text(encoding="utf-8"))
            if fragment not in html.ids or not any(a.get("rel") == "canonical" and a["href"] == document for a in html.links):
                raise ValueError("missing identifier or canonical document")
            if not any(a.get("rel") == "alternate" and a.get("type") == "text/turtle" and a["href"] == "entity.ttl" for a in html.links):
                raise ValueError("missing alternate Turtle link")
            for a in html.links:
                target, anchor = urldefrag(urljoin(document, a["href"]))
                if target.startswith(site) and target not in files:
                    if target + "index.html" not in files or (anchor and target + "#" + anchor not in subjects):
                        raise ValueError(f"unresolved link {a['href']}")
            embedded = Graph().parse(data="".join(html.jsonld), format="json-ld")
            alternate = Graph().parse(page.with_name("entity.ttl"), format="turtle")
            if set(embedded) != set(alternate) or set(embedded) != set(bulk.triples((URIRef(uri), None, None))):
                raise ValueError("graph differs")
        except (ValueError, OSError, SyntaxError) as exc:
            failures.append((uri, str(exc)))
    check("every HTML record resolves its local links and embeds the same RDF as its Turtle and bulk records",
          not failures, failures[:3])
