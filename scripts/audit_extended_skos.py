#!/usr/bin/env python3
"""Audit document_attested_concepts.jsonl and LINCS compliance on commodities_skos_extended.{ttl,jsonld}."""
import json
import re
from collections import Counter
from pathlib import Path

G = Path(__file__).resolve().parents[1] / "human_trade" / "layer1_human" / "grounding"
docs = [json.loads(l) for l in open(G / "document_attested_concepts.jsonl", encoding="utf-8") if l.strip()]
print(f"Total doc_concepts: {len(docs)}")
print("By subsumed_in_customs_id:")
for k, v in Counter((d["subsumed_in_customs_id"], d["subsumed_in_customs_label"]) for d in docs).most_common():
    print(f"  {k[0]} ({k[1]}): {v}")

print("\n--- Check ALL WD anchors for potential homonyms ---")
bad_pat = re.compile(
    r"genus|species|family|city|town|person|river|color|colour|music|game|myth|plant|tree|herb|shrub|"
    r"unit|software|album|film|character|county|parish|island|mountain|constellation|company|brand|vessel|ship|currency|coin|weight|measure",
    re.I,
)
for d in docs:
    a = d.get("wikidata_anchor")
    if a:
        cid = d["concept_id"]
        lbl = d["skos_prefLabel"]
        qid = a["qid"]
        wdl = a["wd_label"]
        wdd = a["wd_description"]
        if lbl.lower() != wdl.lower() or bad_pat.search(wdd or ""):
            print(f"  CHECK {cid:26s} | {lbl:24s} -> {qid:10s} ({wdl}): {wdd}")

print("\n--- Check short / long / punctuation / suspicious labels ---")
for d in docs:
    cid = d["concept_id"]
    lbl = d["skos_prefLabel"]
    sub = d["subsumed_in_customs_id"]
    src = d["extra_sources"][:1] or [x["work"] for x in d["dictionary_sources"][:1]]
    if len(lbl) <= 4 or len(lbl.split()) >= 4 or re.search(r"[^a-zA-Z\s\-'\(\)]", lbl):
        print(f"  LABEL {cid:26s} | {lbl:36s} | sub={sub} | src={src}")

print("\n--- Check Danika/1866 non-enumerated sample (first 60) ---")
dan = [d for d in docs if d.get("extra_sources")]
print(f"Total Danika/1866 doc_concepts: {len(dan)}")
print(", ".join(d["skos_prefLabel"] for d in dan[:80]))

print("\n--- LINCS & SKOS Validation on commodities_skos_extended.jsonld & .ttl ---")
jld = json.loads((G / "commodities_skos_extended.jsonld").read_text(encoding="utf-8"))
graph = jld["@graph"]
all_ids = {n["@id"] for n in graph}
missing_type = [n["@id"] for n in graph if not n.get("@type")]
missing_label = [n["@id"] for n in graph if not n.get("rdfs:label")]
untagged_label = []
for n in graph:
    rl = n.get("rdfs:label")
    if isinstance(rl, dict) and not rl.get("@language"):
        untagged_label.append(n["@id"])
    elif isinstance(rl, str):
        untagged_label.append(n["@id"])

dangling = set()
def walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "@id" and isinstance(v, str) and (v.startswith("htc:") or v.startswith("oe:")):
                if v not in all_ids:
                    dangling.add(v)
            else:
                walk(v)
    elif isinstance(obj, list):
        for x in obj:
            walk(x)
for n in graph:
    for k, v in n.items():
        if k != "@id":
            walk(v)

ttl = (G / "commodities_skos_extended.ttl").read_text(encoding="utf-8")
ttl_no_str = re.sub(r'"(?:\\.|[^"\\])*"', '""', ttl)
bnode_hits = re.findall(r'\[|\]|_:[A-Za-z0-9_]+', ttl_no_str)

prefs = Counter()
for n in graph:
    pl = n.get("skos:prefLabel")
    if isinstance(pl, dict):
        # S14 is per concept scheme: htc: and the htc1866: bridge scheme may legitimately share a label
        sch = n.get("skos:inScheme")
        sch = sch.get("@id") if isinstance(sch, dict) else str(sch)
        prefs[(sch, pl["@value"].lower())] += 1
s14_dups = {k: v for k, v in prefs.items() if v > 1}

# S13 prefLabel == altLabel on same concept
s13_hits = []
for n in graph:
    pl = n.get("skos:prefLabel")
    if isinstance(pl, dict):
        pv = pl["@value"].lower()
        als = n.get("skos:altLabel") or []
        if isinstance(als, dict):
            als = [als]
        for al in als:
            av = (al["@value"] if isinstance(al, dict) else str(al)).lower()
            if av == pv:
                s13_hits.append((n["@id"], pv))

print(f"Nodes in extended JSON-LD: {len(graph)}")
print(f"  Cat 3 missing rdf:type:        {len(missing_type)} {missing_type[:5]}")
print(f"  Cat 3 missing rdfs:label:      {len(missing_label)} {missing_label[:5]}")
print(f"  Cat 3 untagged rdfs:label:     {len(untagged_label)} {untagged_label[:5]}")
print(f"  Cat 10 dangling local URIs:    {len(dangling)} {sorted(dangling)[:10]}")
print(f"  Cat 11 blank nodes in TTL:     {len(bnode_hits)}")
print(f"  SKOS S13 pref==alt clashes:    {len(s13_hits)} {s13_hits[:5]}")
print(f"  Repeated prefLabels within a scheme (editorial policy; not SKOS S14, which is per resource): {len(s14_dups)} {list(s14_dups.items())[:5]}")
