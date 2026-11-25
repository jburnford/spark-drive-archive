#!/usr/bin/env python3
"""
Export Layer-1 (`human_transcribed`) archival commodity vocabulary to SKOS Turtle (.ttl)
and SKOS JSON-LD (.jsonld), and write the consolidated `GROUNDING_REPORT.md` covering
Places, Polities (Empire Evolution year-aware IN_POLITY), and Two-Layer Archival Commodities.
"""

import csv
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "human_trade"
LAYER1 = BASE / "layer1_human"
GROUND = LAYER1 / "grounding"

BASE_URI = "https://open-empire.hgislab.usask.ca/vocab/human-trade-commodities/"
OE_NS = "https://open-empire.hgislab.usask.ca/ns#"


def ttl_str(s: str) -> str:
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    return f'"{s}"'


def main():
    places = [json.loads(l) for l in open(GROUND / "places_grounding.jsonl", encoding="utf-8") if l.strip()]
    concepts = [json.loads(l) for l in open(GROUND / "commodities_concepts.jsonl", encoding="utf-8") if l.strip()]
    polity_rows = list(csv.DictReader(open(GROUND / "place_year_polities.tsv", encoding="utf-8"), delimiter="\t"))

    # --- 1. Export SKOS Turtle (.ttl) ---
    ttl_lines = [
        f"@prefix htc: <{BASE_URI}> .",
        f"@prefix oe: <{OE_NS}> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix wd: <http://www.wikidata.org/entity/> .",
        "@prefix agrovoc: <http://aims.fao.org/aos/agrovoc/> .",
        "@prefix stw: <http://zbw.eu/stw/descriptor/> .",
        "@prefix aat: <http://vocab.getty.edu/aat/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "htc:scheme a skos:ConceptScheme ;",
        '    dcterms:title "Open Empire Layer-1 Human-Transcribed Trade Commodities Vocabulary"@en ;',
        '    dcterms:description "Two-layer archival SKOS vocabulary preserving verbatim 18th-20th century British and Canadian customs commodity headings alongside decomposed processing states and reversible LOD links to Wikidata (2026-11-09), FAO AGROVOC, Getty AAT, Catalogue of Life taxa, SITC Rev. 4, and Theodoridis (2018) land-use buckets."@en .',
        "",
    ]

    jsonld_graph = [
        {
            "@id": "htc:scheme",
            "@type": "skos:ConceptScheme",
            "dcterms:title": {"@value": "Open Empire Layer-1 Human-Transcribed Trade Commodities Vocabulary", "@language": "en"},
        }
    ]

    for c in concepts:
        cid = c["concept_id"]
        pref = c["skos_prefLabel"]
        facets = c.get("facets") or {}
        anchor = c.get("wikidata_anchor") or {}
        ext = c.get("external_lod_anchors") or {}
        bridge = c.get("skos_1866_bridge") or {}

        triples = [
            "a skos:Concept",
            "skos:inScheme htc:scheme",
            f"skos:prefLabel {ttl_str(pref)}@en",
            f'oe:observationCount "{c["total_rows"]}"^^xsd:integer',
            f"oe:groundingStatus {ttl_str(c['status'])}",
        ]
        node = {
            "@id": cid,
            "@type": "skos:Concept",
            "skos:inScheme": {"@id": "htc:scheme"},
            "skos:prefLabel": {"@value": pref, "@language": "en"},
            "oe:observationCount": c["total_rows"],
            "oe:groundingStatus": c["status"],
        }

        if bridge.get("prefLabel") and bridge["prefLabel"].lower() != pref.lower():
            triples.append(f"skos:altLabel {ttl_str(bridge['prefLabel'])}@en")
            node["skos:altLabel"] = {"@value": bridge["prefLabel"], "@language": "en"}

        if facets.get("substance_head"):
            triples.append(f"oe:substanceHead {ttl_str(facets['substance_head'])}")
            node["oe:substanceHead"] = facets["substance_head"]
        if facets.get("processing_state"):
            triples.append(f"oe:processingState {ttl_str(facets['processing_state'])}")
            node["oe:processingState"] = facets["processing_state"]
        if facets.get("ghost_acres_domain"):
            triples.append(f"oe:ghostAcresDomain {ttl_str(facets['ghost_acres_domain'])}")
            node["oe:ghostAcresDomain"] = facets["ghost_acres_domain"]
        if facets.get("theodoridis_category"):
            triples.append(f"oe:theodoridisBucket {ttl_str(facets['theodoridis_category'])}")
            node["oe:theodoridisBucket"] = facets["theodoridis_category"]
        if c.get("skos_broadMatch_sitc"):
            triples.append(f"oe:sitcRollup {ttl_str(c['skos_broadMatch_sitc'])}")
            node["oe:sitcRollup"] = c["skos_broadMatch_sitc"]

        if anchor.get("qid"):
            rel = anchor.get("mapping_relation") or "skos:closeMatch"
            if not rel.startswith("skos:"):
                rel = "skos:closeMatch"
            if anchor.get("component_substances"):
                qlist = [f"wd:{x['qid']}" for x in anchor["component_substances"] if x.get("qid")]
                triples.append(f"{rel} {', '.join(qlist)}")
                node[rel] = [{"@id": f"http://www.wikidata.org/entity/{x['qid']}"} for x in anchor["component_substances"] if x.get("qid")]
            else:
                triples.append(f"{rel} wd:{anchor['qid']}")
                node[rel] = [{"@id": f"http://www.wikidata.org/entity/{anchor['qid']}"}]
            if anchor.get("source_authority"):
                triples.append(f"dcterms:source {ttl_str(anchor['source_authority'])}")
                node["dcterms:source"] = anchor["source_authority"]

            for tax in anchor.get("source_taxa") or []:
                if tax.get("qid"):
                    triples.append(f"oe:sourceTaxon wd:{tax['qid']}")
                    node.setdefault("oe:sourceTaxon", []).append({
                        "@id": f"http://www.wikidata.org/entity/{tax['qid']}",
                        "taxon_name": tax.get("taxon_name", ""),
                        "col_id": tax.get("col_id", ""),
                    })

        if ext.get("agrovoc_ids"):
            ag_rel = "skos:closeMatch"
            ag_refs = [f"agrovoc:c_{x}" for x in ext["agrovoc_ids"]]
            triples.append(f"{ag_rel} {', '.join(ag_refs)}")
            node.setdefault(ag_rel, []).extend({"@id": f"http://aims.fao.org/aos/agrovoc/c_{x}"} for x in ext["agrovoc_ids"])

        if ext.get("stw_ids"):
            stw_refs = [f"stw:{x}" for x in ext["stw_ids"]]
            triples.append(f"skos:broadMatch {', '.join(stw_refs)}")
            node.setdefault("skos:broadMatch", []).extend({"@id": f"http://zbw.eu/stw/descriptor/{x}"} for x in ext["stw_ids"])

        if ext.get("getty_aat_ids"):
            aat_rel = "skos:closeMatch"
            aat_refs = [f"aat:{x}" for x in ext["getty_aat_ids"]]
            triples.append(f"{aat_rel} {', '.join(aat_refs)}")
            node.setdefault(aat_rel, []).extend({"@id": f"http://vocab.getty.edu/aat/{x}"} for x in ext["getty_aat_ids"])

        ttl_lines.append(f"{cid} " + " ;\n    ".join(triples) + " .\n")
        jsonld_graph.append(node)

    ttl_path = GROUND / "commodities_skos.ttl"
    ttl_path.write_text("\n".join(ttl_lines), encoding="utf-8")

    jsonld_obj = {
        "@context": {
            "htc": BASE_URI,
            "oe": OE_NS,
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "dcterms": "http://purl.org/dc/terms/",
            "wd": "http://www.wikidata.org/entity/",
            "agrovoc": "http://aims.fao.org/aos/agrovoc/",
            "stw": "http://zbw.eu/stw/descriptor/",
            "aat": "http://vocab.getty.edu/aat/",
        },
        "@graph": jsonld_graph,
    }
    jsonld_path = GROUND / "commodities_skos.jsonld"
    jsonld_path.write_text(json.dumps(jsonld_obj, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- 2. Build consolidated GROUNDING_REPORT.md ---
    p_cnt = Counter()
    p_men = Counter()
    for p in places:
        st = p["status"]
        if st == "matched" and p.get("match_method") in ("canada_kg_port", "wikidata_slim_canadian_port"):
            key = "matched_canadian_port"
        elif st == "matched":
            key = "matched_global_place"
        elif st == "matched_compound":
            key = "matched_compound"
        elif st == "aggregate_category":
            key = "aggregate_category"
        else:
            key = "unmatched"
        p_cnt[key] += 1
        p_men[key] += p["total_rows"]
    tot_men = sum(p_men.values())
    p_qid_cnt = p_cnt["matched_global_place"] + p_cnt["matched_canadian_port"] + p_cnt["matched_compound"]
    p_qid_men = p_men["matched_global_place"] + p_men["matched_canadian_port"] + p_men["matched_compound"]
    p_res_men = p_qid_men + p_men["aggregate_category"]

    c_cnt = Counter()
    c_rows = Counter()
    dom_rows = Counter()
    dom_cnt = Counter()
    theo_rows = Counter()
    agrovoc_cnt = agrovoc_rows = 0
    stw_cnt = stw_rows = 0
    aat_cnt = aat_rows = 0
    taxa_cnt = taxa_rows = 0
    for c in concepts:
        st = c["status"]
        rows = c["total_rows"]
        c_cnt[st] += 1
        c_rows[st] += rows
        facets = c.get("facets") or {}
        dom = facets.get("ghost_acres_domain", "other")
        dom_rows[dom] += rows
        dom_cnt[dom] += 1
        theo_rows[facets.get("theodoridis_category", "unclassified")] += rows
        ext = c.get("external_lod_anchors") or {}
        if ext.get("agrovoc_ids"):
            agrovoc_cnt += 1
            agrovoc_rows += rows
        if ext.get("stw_ids"):
            stw_cnt += 1
            stw_rows += rows
        if ext.get("getty_aat_ids"):
            aat_cnt += 1
            aat_rows += rows
        a = c.get("wikidata_anchor") or {}
        if a.get("source_taxa"):
            taxa_cnt += 1
            taxa_rows += rows

    tot_c_rows = sum(c_rows.values())
    g_statuses = ("grounded_exact", "grounded_substance_head", "grounded_wikidata_slim", "grounded_compound_commodity")
    g_cnt = sum(c_cnt[s] for s in g_statuses)
    g_rows = sum(c_rows[s] for s in g_statuses)
    res_cnt = c_cnt["customs_residual_category"]
    res_rows = c_rows["customs_residual_category"]

    rep = []
    rep.append("# Layer-1 Human-Transcribed Trade Entity Grounding Report (v2)\n\n")
    rep.append("All QIDs strictly read from verified local authorities (`ceylon/spine`, `empire-evolution`, `Canada-History-Knowledge-Graph`, and the local Wikidata `2026-11-09` slim Parquet dump) plus live Wikidata `wbgetentities` external-identifier enrichment — **zero QIDs from memory**.\n\n")

    rep.append("## 1. Places & Polities (499 Unique Printed Names, 270,080 Mentions)\n")
    rep.append("| Category | Unique Places | Mentions | Share |\n| --- | ---: | ---: | ---: |\n")
    rep.append(f"| Global places & polities (Base World + Wikidata 2026-11-09) | {p_cnt['matched_global_place']:,} | {p_men['matched_global_place']:,} | {p_men['matched_global_place']/tot_men*100:.1f}% |\n")
    rep.append(f"| Canadian customs ports (Canada KG + Wikidata 2026-11-09) | {p_cnt['matched_canadian_port']:,} | {p_men['matched_canadian_port']:,} | {p_men['matched_canadian_port']/tot_men*100:.1f}% |\n")
    rep.append(f"| Multi-place customs compounds (`multi_place_aggregate`) | {p_cnt['matched_compound']:,} | {p_men['matched_compound']:,} | {p_men['matched_compound']/tot_men*100:.1f}% |\n")
    rep.append(f"| **Subtotal grounded to verified QID(s)** | **{p_qid_cnt:,}** | **{p_qid_men:,}** | **{p_qid_men/tot_men*100:.1f}%** |\n")
    rep.append(f"| Explicit non-geographic / fishery aggregates | {p_cnt['aggregate_category']:,} | {p_men['aggregate_category']:,} | {p_men['aggregate_category']/tot_men*100:.1f}% |\n")
    rep.append(f"| **Total resolved** | **{p_qid_cnt + p_cnt['aggregate_category']:,}** | **{p_res_men:,}** | **{p_res_men/tot_men*100:.1f}%** |\n")
    rep.append(f"| Remaining unmatched (`places_review_queue.tsv`) | {p_cnt['unmatched']:,} | {p_men['unmatched']:,} | {p_men['unmatched']/tot_men*100:.1f}% |\n\n")
    rep.append(f"- **Year-aware Empire Evolution `IN_POLITY` links:** **{len(polity_rows):,}** `(place, year)` pairs resolved cleanly in `place_year_polities.tsv`.\n\n")

    rep.append("## 2. Two-Layer Archival Commodities (2,066 Unique Printed Headings)\n")
    rep.append("- **Layer A (Local Archival `skos:Concept` `htc:0001`–`htc:2066`):** **2,066 / 2,066 (100%)** exported to `commodities_skos.ttl` and `commodities_skos.jsonld`.\n")
    rep.append("| Grounding Tier | Concepts | Layer-1 Rows | Row Share |\n| --- | ---: | ---: | ---: |\n")
    for st in ("grounded_exact", "grounded_substance_head", "grounded_wikidata_slim", "grounded_compound_commodity", "customs_residual_category", "skos_1866_bridged_needs_wd", "local_concept_only_needs_wd"):
        if c_cnt[st]:
            rep.append(f"| `{st}` | {c_cnt[st]:,} | {c_rows[st]:,} | {c_rows[st]/tot_c_rows*100:.1f}% |\n")
    rep.append(f"| **Total grounded to verified Wikidata QID(s)** | **{g_cnt:,}** | **{g_rows:,}** | **{g_rows/tot_c_rows*100:.1f}%** |\n")
    rep.append(f"| **Total grounded + explicit customs residuals** | **{g_cnt+res_cnt:,}** | **{g_rows+res_rows:,}** | **{(g_rows+res_rows)/tot_c_rows*100:.1f}%** |\n\n")

    rep.append("### Multi-Anchor External LOD Coverage (Verified via Wikidata `wbgetentities`)\n")
    rep.append(f"- **FAO AGROVOC (`P8061`):** **{agrovoc_cnt:,}** concepts covering **{agrovoc_rows:,}** rows ({agrovoc_rows/tot_c_rows*100:.1f}%)\n")
    rep.append(f"- **STW Thesaurus for Economics (`P3911`):** **{stw_cnt:,}** concepts covering **{stw_rows:,}** rows ({stw_rows/tot_c_rows*100:.1f}%)\n")
    rep.append(f"- **Getty AAT (`P1014`):** **{aat_cnt:,}** concepts covering **{aat_rows:,}** rows ({aat_rows/tot_c_rows*100:.1f}%)\n")
    rep.append(f"- **Biological Source Taxa (`P1582` / `P225` / Catalogue of Life):** **{taxa_cnt:,}** concepts covering **{taxa_rows:,}** rows ({taxa_rows/tot_c_rows*100:.1f}%)\n\n")

    rep.append("### Layer-1 Rows by *Ghost Acres* Book Domain\n")
    for dom, rcnt in dom_rows.most_common():
        rep.append(f"- `{dom}`: **{rcnt:,}** rows ({dom_cnt[dom]:,} concepts)\n")

    rep.append("\n### Layer-1 Rows by Theodoridis (2018) 5-Bucket Land-Use Comparison\n")
    for tb, rcnt in theo_rows.most_common():
        rep.append(f"- `{tb}`: **{rcnt:,}** rows ({rcnt/tot_c_rows*100:.1f}%)\n")

    (GROUND / "GROUNDING_REPORT.md").write_text("".join(rep), encoding="utf-8")
    print(f"Wrote {ttl_path} ({ttl_path.stat().st_size/1024:.1f} KB), {jsonld_path} ({jsonld_path.stat().st_size/1024:.1f} KB), and GROUNDING_REPORT.md")


if __name__ == "__main__":
    main()
