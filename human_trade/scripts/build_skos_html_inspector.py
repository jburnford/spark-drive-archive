#!/usr/bin/env python3
"""
Build a standalone, self-contained interactive HTML SKOS Vocabulary Inspector
for Layer-1 (`human_transcribed`) archival commodities (v4 — 4-tier ontology +
6 19th-century commercial dictionaries) + Places summary.

Zero external JS/CSS dependencies — opens offline in any browser or from Google Drive.
"""

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "human_trade"
REPO_ROOT = Path(__file__).resolve().parents[2]
GROUND = BASE / "layer1_human" / "grounding"
OUT_HTML = GROUND / "open_empire_layer1_skos_v4.html"
DOCS_HTML = REPO_ROOT / "docs" / "index.html"


def main():
    concepts = [json.loads(l) for l in open(GROUND / "commodities_concepts.jsonl", encoding="utf-8") if l.strip()]
    doc_path = GROUND / "document_attested_concepts.jsonl"
    doc_concepts = [json.loads(l) for l in open(doc_path, encoding="utf-8") if l.strip()] if doc_path.exists() else []
    gaz_path = GROUND / "commodity_gazetteer.tsv"
    gaz_cnt = (sum(1 for _ in open(gaz_path, encoding="utf-8")) - 1) if gaz_path.exists() else 0
    end_use_path = GROUND / "end_use_network_links.jsonl"
    if not end_use_path.exists():
        end_use_path = GROUND / "end_use_pilot_links.jsonl"
    end_use_links = [json.loads(l) for l in open(end_use_path, encoding="utf-8") if l.strip()] if end_use_path.exists() else []
    ind_meta_path = GROUND / "end_use_industries.json"
    ind_meta = json.loads(ind_meta_path.read_text(encoding="utf-8")) if ind_meta_path.exists() else {}
    places = [json.loads(l) for l in open(GROUND / "places_grounding.jsonl", encoding="utf-8") if l.strip()]
    polity_cnt = sum(1 for _ in open(GROUND / "place_year_polities.tsv", encoding="utf-8")) - 1

    compact = []
    sec_stats = defaultdict(lambda: {"rows": 0, "cnt": 0, "doc_cnt": 0, "label": ""})
    grp_stats = defaultdict(lambda: {"rows": 0, "cnt": 0, "doc_cnt": 0, "label": "", "sector": ""})
    land_stats = Counter()
    rel_stats = Counter()
    rel_rows = Counter()
    state_stats = Counter()

    ag_cnt = stw_cnt = aat_cnt = tax_cnt = mat_cnt = 0
    def_cnt = alt_cnt = relc_cnt = comb_cnt = 0
    sub_ids = set()

    for c in concepts:
        f = c["facets"]
        ont = c["ontology"]
        a = c.get("wikidata_anchor") or {}
        ext = c.get("external_lod_anchors") or {}
        prov = c.get("provenance") or {}
        br = c.get("skos_1866_bridge") or {}
        rows = c["total_rows"]

        sec_id, sec_lbl = ont["sector_id"], ont["sector_label"]
        grp_id, grp_lbl = ont["group_id"], ont["group_label"]
        sec_stats[sec_id]["rows"] += rows
        sec_stats[sec_id]["cnt"] += 1
        sec_stats[sec_id]["label"] = sec_lbl
        grp_stats[grp_id]["rows"] += rows
        grp_stats[grp_id]["cnt"] += 1
        grp_stats[grp_id]["label"] = grp_lbl
        grp_stats[grp_id]["sector"] = sec_id

        land_stats[f["land_basis"]] += rows
        state_stats[f["processing_state"]] += 1

        rel = a.get("mapping_relation") or ("residual" if c["status"] == "customs_residual_category" else "ungrounded")
        rel_stats[rel] += 1
        rel_rows[rel] += rows

        if ext.get("agrovoc_ids"): ag_cnt += 1
        if ext.get("stw_ids"): stw_cnt += 1
        if ext.get("getty_aat_ids"): aat_cnt += 1
        if c.get("source_taxa"): tax_cnt += 1
        if c.get("made_of_material"): mat_cnt += 1
        if c.get("skos_definition"): def_cnt += 1
        if c.get("skos_altLabels"): alt_cnt += 1
        if c.get("related_concepts"): relc_cnt += 1
        if c.get("combines_concepts"): comb_cnt += 1
        br_id = ont.get("broader_id", grp_id)
        if br_id != grp_id:
            sub_ids.add(br_id)

        comps = []
        if a.get("component_substances"):
            comps = [[x["qid"], x["wd_label"]] for x in a["component_substances"]]
        elif a.get("qid"):
            comps = [[a["qid"], a.get("wd_label", "")]]

        compact.append({
            "id": c["concept_id"],
            "basis": "customs",
            "sub": "",
            "subl": "",
            "roles": [],
            "l": c["skos_prefLabel"],
            "alts": c.get("skos_altLabels") or [],
            "def": c.get("skos_definition") or "",
            "sn": c.get("skos_scopeNote") or "",
            "dsrc": [[d["citation"], d["uri"]] for d in (c.get("dictionary_sources") or [])],
            "r": rows,
            "sec": sec_id,
            "secl": sec_lbl,
            "grp": grp_id,
            "grpl": grp_lbl,
            "br": ont.get("broader_id", grp_id),
            "h": f["substance_head"],
            "s": f["processing_state"],
            "d": f["ghost_acres_domain"],
            "lb": f["land_basis"],
            "th": f["theodoridis_category"],
            "si": f["sitc_code"],
            "agg": bool(f["is_aggregate"]),
            "rel": rel,
            "wd": comps,
            "wdesc": a.get("wd_description", ""),
            "rule": a.get("match_rule", ""),
            "via": a.get("matched_via_term", ""),
            "ag": ext.get("agrovoc_ids", []),
            "agrel": ext.get("agrovoc_relation", ""),
            "stw": ext.get("stw_ids", []),
            "stwrel": ext.get("stw_relation", ""),
            "aat": ext.get("getty_aat_ids", []),
            "aatrel": ext.get("getty_aat_relation", ""),
            "tx": [[t["qid"], t.get("taxon_name", ""), t.get("col_id", ""), t.get("relation", "")] for t in (c.get("source_taxa") or [])],
            "mat": [[m["qid"], m.get("label", "")] for m in (c.get("made_of_material") or [])],
            "matc": c.get("material_concepts") or [],
            "relc": c.get("related_concepts") or [],
            "comb": c.get("combines_concepts") or [],
            "y0": prov.get("first_attested"),
            "y1": prov.get("last_attested"),
            "ser": prov.get("series", []) + [f"{x} (inferred: series not printed)" for x in prov.get("inferred_series", [])],
            "b1866": br.get("broaderConcept", ""),
        })

    # Append Document-Attested Text-Mining Tier (`htc:doc_*`) — zero quantity rows, linked via oe:subsumedInCustomsHeading
    doc_wd_cnt = doc_tx_cnt = 0
    for c in doc_concepts:
        f = c["facets"]
        ont = c["ontology"]
        a = c.get("wikidata_anchor") or {}
        prov = c.get("provenance") or {}
        sec_id, sec_lbl = ont["sector_id"], ont["sector_label"]
        grp_id, grp_lbl = ont["group_id"], ont["group_label"]
        sec_stats[sec_id]["doc_cnt"] += 1
        if not sec_stats[sec_id]["label"]:
            sec_stats[sec_id]["label"] = sec_lbl
        grp_stats[grp_id]["doc_cnt"] += 1
        if not grp_stats[grp_id]["label"]:
            grp_stats[grp_id]["label"] = grp_lbl
            grp_stats[grp_id]["sector"] = sec_id
        rel = a.get("mapping_relation") or "doc_local"
        if a.get("qid"):
            doc_wd_cnt += 1
        if c.get("source_taxa"):
            doc_tx_cnt += 1
        comps = [[a["qid"], a.get("wd_label", "")]] if a.get("qid") else []
        compact.append({
            "id": c["concept_id"],
            "basis": "doc",
            "sub": c.get("subsumed_in_customs_id", ""),
            "subl": c.get("subsumed_in_customs_label", ""),
            "roles": c.get("multi_use_roles") or [],
            "l": c["skos_prefLabel"],
            "alts": c.get("skos_altLabels") or [],
            "def": c.get("skos_definition") or "",
            "sn": c.get("skos_scopeNote") or "",
            "dsrc": [[d["citation"], d["uri"]] for d in (c.get("dictionary_sources") or [])],
            "r": 0,
            "sec": sec_id,
            "secl": sec_lbl,
            "grp": grp_id,
            "grpl": grp_lbl,
            "br": ont.get("broader_id", grp_id),
            "h": f["substance_head"],
            "s": f["processing_state"],
            "d": f["ghost_acres_domain"],
            "lb": f["land_basis"],
            "th": f["theodoridis_category"],
            "si": f["sitc_code"],
            "agg": False,
            "rel": rel,
            "wd": comps,
            "wdesc": a.get("wd_description", ""),
            "rule": a.get("match_rule", ""),
            "via": a.get("matched_via_term", ""),
            "ag": [], "agrel": "", "stw": [], "stwrel": "", "aat": [], "aatrel": "",
            "tx": [[t["qid"], t.get("taxon_name", ""), t.get("col_id", ""), t.get("relation", "")] for t in (c.get("source_taxa") or [])],
            "mat": [], "matc": [], "relc": [], "comb": [],
            "y0": None, "y1": None,
            "ser": prov.get("series", []) + [f"{x} (inferred: series not printed)" for x in prov.get("inferred_series", [])],
            "b1866": "",
        })

    # Compact places summary
    p_stats = Counter()
    p_men = Counter()
    compact_places = []
    for p in places:
        st = p["status"]
        if st == "matched" and p.get("match_method") in ("canada_kg_port", "wikidata_slim_canadian_port"):
            k = "canadian_port"
        elif st == "matched":
            k = "global_place"
        elif st == "matched_compound":
            k = "compound"
        elif st == "aggregate_category":
            k = "aggregate"
        else:
            k = "unmatched"
        p_stats[k] += 1
        p_men[k] += p["total_rows"]
        compact_places.append({
            "n": p["name_as_printed"],
            "r": p["total_rows"],
            "k": k,
            "q": p.get("qid", "") or ("+".join(x["qid"] for x in p.get("component_places", []))),
            "lbl": p.get("wd_label", "") or (" & ".join(x["label"] for x in p.get("component_places", []))),
            "rel": p.get("match_relation", ""),
            "src": p.get("source_authority", ""),
            "ys": p.get("year_span", []),
        })

    tot_rows = sum(c["total_rows"] for c in concepts)
    g_cnt = sum(rel_stats[x] for x in ("skos:exactMatch", "skos:closeMatch", "skos:broadMatch", "skos:relatedMatch"))
    g_rows = sum(rel_rows[x] for x in ("skos:exactMatch", "skos:closeMatch", "skos:broadMatch", "skos:relatedMatch"))
    tot_p_men = sum(p_men.values())
    p_qid_men = p_men["global_place"] + p_men["canadian_port"] + p_men["compound"]

    meta_payload = {
        "generated": date.today().isoformat(),
        "total_concepts": len(concepts),
        "doc_concepts": len(doc_concepts),
        "doc_wd_cnt": doc_wd_cnt,
        "doc_tx_cnt": doc_tx_cnt,
        "gazetteer_forms": gaz_cnt,
        "total_subgroups": len(sub_ids),
        "total_comm_rows": tot_rows,
        "total_obs": 153579,
        "grounded_concepts": g_cnt,
        "grounded_rows": g_rows,
        "residual_concepts": rel_stats["residual"],
        "residual_rows": rel_rows["residual"],
        "ag_cnt": ag_cnt,
        "stw_cnt": stw_cnt,
        "aat_cnt": aat_cnt,
        "tax_cnt": tax_cnt,
        "mat_cnt": mat_cnt,
        "def_cnt": def_cnt,
        "alt_cnt": alt_cnt,
        "relc_cnt": relc_cnt,
        "comb_cnt": comb_cnt,
        "sec_stats": {k: v for k, v in sorted(sec_stats.items(), key=lambda x: -x[1]["rows"])},
        "grp_stats": {k: v for k, v in sorted(grp_stats.items(), key=lambda x: -x[1]["rows"])},
        "land_stats": dict(land_stats.most_common()),
        "rel_stats": dict(rel_stats),
        "rel_rows": dict(rel_rows),
        "state_stats": dict(state_stats.most_common()),
        "place_stats": dict(p_stats),
        "place_mentions": dict(p_men),
        "place_total_mentions": tot_p_men,
        "place_qid_mentions": p_qid_men,
        "polity_pairs": polity_cnt,
    }

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Open Empire — Layer-1 Archival Commodity SKOS Vocabulary Inspector</title>
<style>
:root {{
  --bg: #f8f6f1;
  --surface: #ffffff;
  --ink: #1e242b;
  --muted: #5c6672;
  --border: #dfd9cc;
  --accent: #1d4e6b;
  --accent-soft: #e7f0f5;
  --exact: #146c43; --exact-bg: #dff3e8;
  --close: #0d5c75; --close-bg: #dff0f5;
  --broad: #7a4f01; --broad-bg: #fcf0d4;
  --rel: #5b3286; --rel-bg: #efe6fa;
  --res: #5c6672; --res-bg: #eceae4;
  --un: #9b2226; --un-bg: #fce4e4;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.45;
}}
header {{
  background: #17374b; color: #f8f6f1; padding: 24px 32px; border-bottom: 4px solid #b58d3d;
}}
header h1 {{
  margin: 0 0 6px 0; font-family: Georgia, "Times New Roman", serif; font-size: 1.65rem; font-weight: 700;
}}
header p {{ margin: 0; color: #cedae3; font-size: 0.92rem; max-width: 1120px; }}
.container {{ max-width: 1500px; margin: 0 auto; padding: 20px 28px 48px; }}
.kpis {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 20px;
}}
.kpi {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px;
}}
.kpi .val {{ font-size: 1.4rem; font-weight: 700; color: var(--accent); }}
.kpi .lbl {{ font-size: 0.77rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 2px; }}
.kpi .sub {{ font-size: 0.79rem; color: var(--muted); margin-top: 4px; }}
.tabs {{
  display: flex; gap: 6px; border-bottom: 2px solid var(--border); margin-bottom: 18px; flex-wrap: wrap;
}}
.tab {{
  padding: 9px 18px; border: none; background: transparent; cursor: pointer; font-weight: 600;
  color: var(--muted); font-size: 0.92rem; border-bottom: 3px solid transparent; margin-bottom: -2px;
}}
.tab.active {{ color: var(--accent); border-bottom-color: var(--accent); background: rgba(29,78,107,0.06); }}
.panel {{ display: none; }}
.panel.active {{ display: block; }}
.charts-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 16px; margin-bottom: 20px;
}}
.card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px 18px;
}}
.card h3 {{ margin: 0 0 12px 0; font-size: 0.95rem; font-family: Georgia, serif; color: var(--ink); }}
.bar-row {{
  display: grid; grid-template-columns: 200px 1fr 95px; gap: 8px; align-items: center;
  margin-bottom: 6px; font-size: 0.81rem; cursor: pointer; padding: 2px 4px; border-radius: 4px;
}}
.bar-row:hover {{ background: var(--accent-soft); }}
.bar-track {{ background: #eeeae0; height: 12px; border-radius: 6px; overflow: hidden; }}
.bar-fill {{ background: var(--accent); height: 100%; border-radius: 6px; }}
.bar-val {{ text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); }}
.controls {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 16px; margin-bottom: 14px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}}
.controls input[type=text], .controls select {{
  padding: 7px 10px; border: 1px solid #c9c2b2; border-radius: 6px; font-size: 0.85rem; background: #fff; max-width: 260px;
}}
.controls input[type=text] {{ flex: 1 1 280px; max-width: none; }}
.controls button {{
  padding: 7px 12px; border: 1px solid var(--border); border-radius: 6px; background: #f2efe7;
  cursor: pointer; font-size: 0.84rem; font-weight: 600; color: var(--ink);
}}
.controls button:hover {{ background: #e6e0d2; }}
.meta-line {{ font-size: 0.84rem; color: var(--muted); margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }}
table {{
  width: 100%; border-collapse: collapse; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; overflow: hidden; font-size: 0.83rem;
}}
th {{
  background: #f0ece2; text-align: left; padding: 9px 10px; font-weight: 600; color: #2b343d;
  border-bottom: 2px solid var(--border); position: sticky; top: 0;
}}
td {{ padding: 8px 10px; border-bottom: 1px solid #eeeae0; vertical-align: top; }}
tr.data-row:hover {{ background: #faf8f3; cursor: pointer; }}
.mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.78rem; }}
.badge {{
  display: inline-block; padding: 2px 7px; border-radius: 12px; font-size: 0.73rem;
  font-weight: 600; white-space: nowrap;
}}
.b-exact {{ background: var(--exact-bg); color: var(--exact); }}
.b-close {{ background: var(--close-bg); color: var(--close); }}
.b-broad {{ background: var(--broad-bg); color: var(--broad); }}
.b-rel {{ background: var(--rel-bg); color: var(--rel); }}
.b-res {{ background: var(--res-bg); color: var(--res); }}
.b-un {{ background: var(--un-bg); color: var(--un); }}
.b-tag {{ background: #eef1f4; color: #364554; font-weight: 500; margin: 1px 2px 1px 0; }}
.b-alt {{ background: #e8f3ee; color: #1a5c40; font-weight: 500; margin: 1px 3px 1px 0; }}
.b-link {{ background: #efe8fa; color: #4c267a; cursor: pointer; border: 1px solid #d7c7ee; margin: 2px 4px 2px 0; }}
.b-link:hover {{ background: #e1d4f7; }}
.b-comb {{ background: #fff0db; color: #874700; cursor: pointer; border: 1px solid #f0cfa0; margin: 2px 4px 2px 0; }}
.b-comb:hover {{ background: #fce2be; }}
.b-agg {{ background: #fff3cd; color: #856404; }}
.b-doc {{ background: #e0f5f1; color: #0c6356; border: 1px solid #a8dfd4; font-weight: 600; }}
.b-sub {{ background: #e9f2fa; color: #194d75; border: 1px solid #bdd7ee; cursor: pointer; margin: 2px 3px 2px 0; }}
.b-sub:hover {{ background: #d6e7f7; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.detail-row td {{ background: #fcfbf7; padding: 14px 18px; border-bottom: 2px solid var(--border); }}
.detail-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 12px; font-size: 0.83rem; }}
.detail-box {{ background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; }}
.detail-box h4 {{ margin: 0 0 6px 0; font-size: 0.77rem; text-transform: uppercase; color: var(--muted); letter-spacing: 0.03em; }}
.def-quote {{
  background: #f7f4ec; border-left: 3px solid #b58d3d; padding: 8px 12px; margin-bottom: 10px;
  font-family: Georgia, serif; font-size: 0.87rem; color: #2b2720; border-radius: 0 6px 6px 0;
}}
pre.ttl {{
  background: #1e242b; color: #e9eef3; padding: 10px 12px; border-radius: 6px;
  font-size: 0.76rem; overflow-x: auto; margin: 10px 0 0 0;
}}
.pager {{ display: flex; gap: 6px; align-items: center; margin-top: 12px; justify-content: center; }}
.pager button {{ padding: 5px 12px; border: 1px solid var(--border); background: #fff; border-radius: 5px; cursor: pointer; }}
.pager button:disabled {{ opacity: 0.45; cursor: default; }}
details.tree-sec {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 14px; margin-bottom: 10px;
}}
details.tree-sec > summary {{ cursor: pointer; font-weight: 700; font-size: 0.98rem; color: var(--accent); }}
details.tree-grp {{ margin: 8px 0 6px 16px; border-left: 3px solid #c9b996; padding-left: 12px; }}
details.tree-grp > summary {{ cursor: pointer; font-weight: 600; font-size: 0.89rem; color: #2a3b47; }}
details.tree-sub {{ margin: 5px 0 5px 16px; border-left: 2px solid var(--border); padding-left: 10px; }}
details.tree-sub > summary {{ cursor: pointer; font-weight: 600; font-size: 0.83rem; color: var(--muted); }}
.leaf-list {{ margin: 5px 0 8px 10px; font-size: 0.81rem; display: flex; flex-wrap: wrap; gap: 6px; }}
.leaf-chip {{ background: #f4f1e8; border: 1px solid var(--border); border-radius: 5px; padding: 2px 7px; cursor: pointer; }}
.leaf-chip:hover {{ background: var(--accent-soft); border-color: var(--accent); }}
/* Visual SVG Tree */
.vtree-layout {{
  display: grid; grid-template-columns: 1fr 350px; gap: 14px; align-items: start;
}}
@media (max-width: 1080px) {{
  .vtree-layout {{ grid-template-columns: 1fr; }}
}}
.vtree-stage {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  height: 740px; position: relative; overflow: hidden; cursor: grab; user-select: none;
}}
.vtree-stage.dragging {{ cursor: grabbing; }}
.vtree-stage svg {{ width: 100%; height: 100%; display: block; }}
.vtree-side {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 16px; max-height: 740px; overflow-y: auto; font-size: 0.83rem;
}}
.vtree-side h3 {{ margin: 0 0 6px 0; font-family: Georgia, serif; font-size: 1.02rem; color: var(--accent); }}
.vtree-legend {{
  position: absolute; bottom: 10px; left: 12px; background: rgba(255,255,255,0.92);
  border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px;
  font-size: 0.74rem; color: var(--muted); pointer-events: none; display: flex; gap: 10px; flex-wrap: wrap;
}}
.vtree-node {{ cursor: pointer; }}
.vtree-node text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; fill: #1e242b; }}
.vtree-node:hover text {{ fill: #1d4e6b; font-weight: 700; }}
.vtree-link {{ fill: none; stroke: #c9c1b0; stroke-width: 1.3; }}
.vtree-link.hi {{ stroke: #b58d3d; stroke-width: 2.6; }}
.vtree-rel-arc {{ fill: none; stroke: #6f42c1; stroke-width: 1.5; stroke-dasharray: 4 3; opacity: 0.75; }}
.vtree-comb-arc {{ fill: none; stroke: #c96a00; stroke-width: 1.8; opacity: 0.85; }}
</style>
</head>
<body>
<header>
  <h1>Open Empire — 19th-Century Archival Trade SKOS Vocabulary &amp; Text-Mining Gazetteer</h1>
  <p>4-tier historical commodity SKOS vocabulary (9 Macro-Sectors → 44 Commodity Groups → {len(sub_ids)} S14-safe Substance Groups → <strong>2,066 Layer-1 customs-enumerated</strong> + <strong>{len(doc_concepts):,} document-attested text-mining</strong> <code>htc:</code> concepts, <strong>{gaz_cnt:,}</strong> gazetteer surface forms; dual-typed as <code>skos:Concept</code> &amp; <code>crm:E55_Type</code> for LINCS / CIDOC CRM compatibility), enriched from 6 19th-century commercial dictionaries, Danika's Drugs Project (<em>British Pharmacopoeia</em> 1867 / Savory 1865 / 1866 Customs List), Wikidata, AGROVOC, STW, Getty AAT, and Catalogue of Life. Generated {date.today().isoformat()}.</p>
</header>

<div class="container">
  <div class="kpis" id="kpis"></div>

  <div class="tabs">
    <button class="tab active" id="btn-concepts" onclick="switchTab('concepts', this)">Commodities Browser ({len(concepts) + len(doc_concepts):,})</button>
    <button class="tab" id="btn-vtree" onclick="switchTab('vtree', this)">Visual Tree (Interactive SVG)</button>
    <button class="tab" id="btn-hierarchy" onclick="switchTab('hierarchy', this)">Outline Hierarchy Tree</button>
    <button class="tab" id="btn-industries" onclick="switchTab('industries', this)">Industries / End-Use Network ({len(ind_meta)})</button>
    <button class="tab" id="btn-places" onclick="switchTab('places', this)">Places &amp; Polities (499)</button>
  </div>

  <!-- TAB 1: COMMODITIES -->
  <div id="tab-concepts" class="panel active">
    <div class="charts-grid">
      <div class="card"><h3>Tier-1 Macro-Sectors (click to filter)</h3><div id="chart-sec"></div></div>
      <div class="card"><h3>Ecological Land Basis (<code>oe:landBasis</code>)</h3><div id="chart-land"></div></div>
      <div class="card"><h3>Layer-B Mapping Relations &amp; External LOD</h3><div id="chart-rel"></div></div>
    </div>

    <div class="controls">
      <input type="text" id="q" placeholder="Search htc ID, heading, altLabel (e.g. 'cocaine', 'copal', 'rubber', 'nux vomica'), definition, taxon, QID..." oninput="resetAndRender()">
      <select id="f-basis" onchange="resetAndRender()">
        <option value="">All Tiers ({len(concepts) + len(doc_concepts):,})</option>
        <option value="customs">Customs-Enumerated Core ({len(concepts):,})</option>
        <option value="doc">Document-Attested Text-Mining ({len(doc_concepts):,})</option>
      </select>
      <select id="f-sec" onchange="resetAndRender()"><option value="">All 9 Macro-Sectors</option></select>
      <select id="f-grp" onchange="resetAndRender()"><option value="">All 44 Commodity Groups</option></select>
      <select id="f-land" onchange="resetAndRender()"><option value="">All Land Bases</option></select>
      <select id="f-rel" onchange="resetAndRender()">
        <option value="">All Mapping Tiers</option>
        <option value="skos:exactMatch">skos:exactMatch</option>
        <option value="skos:closeMatch">skos:closeMatch</option>
        <option value="skos:broadMatch">skos:broadMatch</option>
        <option value="skos:relatedMatch">skos:relatedMatch</option>
        <option value="residual">Customs Residual</option>
        <option value="ungrounded">Ungrounded (Queue)</option>
      </select>
      <select id="f-state" onchange="resetAndRender()"><option value="">All Processing States</option></select>
      <select id="f-extra" onchange="resetAndRender()">
        <option value="">Enrichment Filters</option>
        <option value="def">Has 19th-c. Definition</option>
        <option value="alt">Has skos:altLabel</option>
        <option value="relc">Has skos:related</option>
        <option value="comb">Merged oe:combinesConcept</option>
        <option value="taxa">Has Source Taxon</option>
        <option value="mat">Has Made-Of Material</option>
        <option value="agrovoc">Has AGROVOC</option>
        <option value="stw">Has STW Economics</option>
        <option value="aat">Has Getty AAT</option>
        <option value="agg">Aggregate Total Headings</option>
      </select>
      <button onclick="clearFilters()">Reset</button>
    </div>

    <div class="meta-line">
      <span id="count-info"></span>
      <span>Click any row to inspect 19th-century dictionary definition, synonyms, <code>skos:related</code>, <code>oe:combinesConcept</code>, provenance, and Turtle snippet.</span>
    </div>

    <table>
      <thead>
        <tr>
          <th style="width:74px">ID</th>
          <th>Printed Customs Heading (<code>skos:prefLabel</code> &amp; <code>altLabel</code>)</th>
          <th style="width:66px;text-align:right">Rows</th>
          <th style="width:205px">Commodity Group / Land Basis</th>
          <th style="width:120px">State / SITC</th>
          <th style="width:225px">Wikidata Anchor (Layer B)</th>
          <th style="width:210px">External LOD &amp; Taxa / Relations</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="pager" id="pager"></div>
  </div>

  <!-- TAB 1B: VISUAL TREE (INTERACTIVE SVG) -->
  <div id="tab-vtree" class="panel">
    <div class="controls">
      <input type="text" id="vt-q" placeholder="Find &amp; highlight in tree (e.g. 'cocaine', 'copal', 'rubber', 'tea', 'tallow')..." oninput="vtreeSearch(this.value)">
      <button onclick="vtreeSetDepth(1)">Sectors (9)</button>
      <button onclick="vtreeSetDepth(2)">Groups (44)</button>
      <button onclick="vtreeSetDepth(3)">+ Sub-groups</button>
      <label style="font-size:0.83rem;display:flex;align-items:center;gap:4px;cursor:pointer">
        <input type="checkbox" id="vt-doc" checked onchange="rebuildVTree()"> Include Document-Attested ({len(doc_concepts):,})
      </label>
      <select id="vt-color" onchange="renderVTree()">
        <option value="sector">Color by Macro-Sector</option>
        <option value="mapping">Color by Mapping Tier</option>
      </select>
      <label style="font-size:0.83rem;display:flex;align-items:center;gap:4px;cursor:pointer">
        <input type="checkbox" id="vt-arcs" checked onchange="renderVTree()"> Show <code>related</code> / <code>combines</code> arcs
      </label>
      <button onclick="vtreeZoom(1.25)">Zoom +</button>
      <button onclick="vtreeZoom(0.8)">Zoom &minus;</button>
      <button onclick="vtreeFit()">Fit View</button>
    </div>
    <div class="vtree-layout">
      <div class="vtree-stage" id="vt-stage">
        <svg id="vt-svg" xmlns="http://www.w3.org/2000/svg">
          <g id="vt-viewport"></g>
        </svg>
        <div class="vtree-legend" id="vt-legend">
          <span><strong>Click circle/label:</strong> expand or collapse branch &amp; inspect</span>
          <span><strong>Drag:</strong> pan · <strong>Scroll:</strong> zoom</span>
          <span style="color:#6f42c1">--- <code>skos:related</code></span>
          <span style="color:#c96a00">&mdash; <code>oe:combinesConcept</code></span>
        </div>
      </div>
      <div class="vtree-side" id="vt-side">
        <h3>Tree Node Inspector</h3>
        <p style="color:var(--muted)">Click any Macro-Sector, Commodity Group, Substance Group, or leaf heading in the visual tree to inspect its definition, synonyms, botanical taxa, and cross-links.</p>
        <p style="color:var(--muted)">Tip: try typing <strong>rubber</strong>, <strong>tea</strong>, or <strong>tallow</strong> in the search box above to auto-expand matching branches and see <code>skos:related</code> / <code>oe:combinesConcept</code> arcs light up.</p>
      </div>
    </div>
  </div>

  <!-- TAB 2: HIERARCHY -->
  <div id="tab-hierarchy" class="panel">
    <div class="card" style="margin-bottom:14px;">
      <strong>4-Tier SKOS Hierarchy Structure:</strong> <code>htc:scheme</code> → <strong>9 Macro-Sectors</strong> (<code>skos:hasTopConcept</code>) → <strong>44 Mid-Level Commodity Groups</strong> (e.g., <em>Stimulant Beverages &amp; Infusions</em> uniting Tea, Coffee &amp; Cocoa; <em>Latexes &amp; Elastic Gums</em> uniting Caoutchouc, India Rubber &amp; Gutta Percha) → <strong>{len(sub_ids)} S14-safe Substance Groups</strong> → <strong>2,066 Verbatim Customs Headings</strong> (0 orphan concepts). Click any leaf chip to inspect it.
    </div>
    <div id="tree-root"></div>
  </div>

  <!-- TAB 2B: INDUSTRIES / END-USE NETWORK -->
  <div id="tab-industries" class="panel">
    <div class="card" style="margin-bottom:14px;">
      <strong>18-Industry Primary-Source End-Use Network (<code>oe:usedInIndustry</code> / <code>oe:usesCommodityInput</code>):</strong>
      Every commodity link below is mined from the <strong>full text of 6 19th-century commercial &amp; manufacturing books</strong> (6,455 pages across Ure 1840, Simmonds 1854 &amp; 1892, McCulloch 1880, Mortimer 1823, and Watt 1908) — uniting <strong>Layer-1 customs-enumerated commodities</strong> with <strong>Document-Attested minor inputs (<code>htc:doc_*</code>)</strong> without altering the 4-tier material taxonomy. Select any industry pill below or search across all 18 industries.
    </div>
    <div class="controls" style="margin-bottom:10px">
      <input type="text" id="ind-q" placeholder="Filter inputs or search across all 18 industries (e.g. 'palm oil', 'cochineal', 'shellac', 'quicksilver')..." oninput="renderIndustries()">
      <button onclick="document.getElementById('ind-q').value='';renderIndustries()">Clear Search</button>
    </div>
    <div class="controls" id="ind-buttons" style="gap:6px"></div>
    <div id="ind-content"></div>
  </div>

  <!-- TAB 3: PLACES -->
  <div id="tab-places" class="panel">
    <div class="kpis" id="place-kpis"></div>
    <div class="controls">
      <input type="text" id="pq" placeholder="Search printed place, Canadian port, QID, label..." oninput="renderPlaces()">
      <select id="f-pk" onchange="renderPlaces()">
        <option value="">All Categories</option>
        <option value="global_place">Global Places &amp; Polities</option>
        <option value="canadian_port">Canadian Customs Ports</option>
        <option value="compound">Multi-Place Compounds</option>
        <option value="aggregate">Non-Geo Aggregates</option>
        <option value="unmatched">Unmatched Queue</option>
      </select>
    </div>
    <table>
      <thead>
        <tr>
          <th>Printed Place Name</th>
          <th style="width:80px;text-align:right">Mentions</th>
          <th style="width:130px">Category</th>
          <th style="width:140px">Wikidata QID(s)</th>
          <th>Resolved Label</th>
          <th style="width:120px">Years</th>
          <th style="width:200px">Authority</th>
        </tr>
      </thead>
      <tbody id="ptbody"></tbody>
    </table>
  </div>
</div>

<script>
const META = {json.dumps(meta_payload, ensure_ascii=False)};
const CONCEPTS = {json.dumps(compact, ensure_ascii=False)};
const PLACES = {json.dumps(compact_places, ensure_ascii=False)};
const END_USES = {json.dumps(end_use_links, ensure_ascii=False)};
const IND_META = {json.dumps(ind_meta, ensure_ascii=False)};
const END_USES_BY_CID = {{}};
for (const eu of END_USES) {{ (END_USES_BY_CID[eu.commodity_id] = END_USES_BY_CID[eu.commodity_id] || []).push(eu); }}
const BY_ID = Object.fromEntries(CONCEPTS.map(c => [c.id, c]));

const PAGE_SIZE = 75;
let curPage = 1;
let filtered = CONCEPTS;
let expandedId = null;

function esc(s) {{
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}
function fmt(n) {{ return Number(n || 0).toLocaleString(); }}
function pct(n, d) {{ return d ? ((n / d) * 100).toFixed(1) + '%' : '0%'; }}

function relBadge(rel) {{
  const map = {{
    'skos:exactMatch': ['exactMatch', 'b-exact'],
    'skos:closeMatch': ['closeMatch', 'b-close'],
    'skos:broadMatch': ['broadMatch', 'b-broad'],
    'skos:relatedMatch': ['relatedMatch', 'b-rel'],
    'residual': ['residual', 'b-res'],
    'ungrounded': ['ungrounded', 'b-un'],
    'doc_local': ['doc-attested', 'b-doc'],
  }};
  const [lbl, cls] = map[rel] || [rel, 'b-tag'];
  return `<span class="badge ${{cls}}">${{lbl}}</span>`;
}}

function jumpToConcept(id) {{
  switchTab('concepts', document.getElementById('btn-concepts'));
  clearFilters();
  document.getElementById('q').value = id;
  resetAndRender();
  expandedId = id;
  renderTable();
  window.scrollTo(0, 240);
}}

function initDashboard() {{
  const kpis = [
    [fmt(META.total_concepts) + ' + ' + fmt(META.doc_concepts), 'Customs + Text-Mining Tier', fmt(META.gazetteer_forms) + ' normalized gazetteer forms'],
    [pct(META.grounded_rows, META.total_comm_rows), 'Layer-1 Wikidata Grounded', fmt(META.grounded_concepts) + ' customs (' + pct(META.grounded_rows + META.residual_rows, META.total_comm_rows) + ' w/ residuals)'],
    [fmt(META.doc_concepts), 'Document-Attested (htc:doc_*)', fmt(META.doc_wd_cnt) + ' WD-grounded · ' + fmt(META.doc_tx_cnt) + ' w/ Linnaean taxa'],
    [fmt(META.def_cnt) + ' / ' + fmt(META.alt_cnt), '19th-c. Defs / altLabels', '6 commercial books + Danika Drugs / 1866'],
    [fmt(META.tax_cnt + META.doc_tx_cnt) + ' / ' + fmt(META.mat_cnt), 'Taxa / Material Links', 'Verified Linnaean oe:sourceTaxon'],
    [pct(META.place_qid_mentions, META.place_total_mentions), 'Places Grounded', pct(META.place_qid_mentions + (META.place_mentions.aggregate||0), META.place_total_mentions) + ' resolved w/ aggregates'],
  ];
  document.getElementById('kpis').innerHTML = kpis.map(([v,l,s]) =>
    `<div class="kpi"><div class="val">${{v}}</div><div class="lbl">${{l}}</div><div class="sub">${{s}}</div></div>`
  ).join('');

  const fSec = document.getElementById('f-sec');
  Object.entries(META.sec_stats).forEach(([k, v]) => {{
    fSec.innerHTML += `<option value="${{k}}">${{esc(v.label)}} (${{v.cnt}})</option>`;
  }});
  const fGrp = document.getElementById('f-grp');
  Object.entries(META.grp_stats).forEach(([k, v]) => {{
    fGrp.innerHTML += `<option value="${{k}}">${{esc(v.label)}} (${{v.cnt}})</option>`;
  }});
  const fLand = document.getElementById('f-land');
  Object.keys(META.land_stats).forEach(k => {{
    fLand.innerHTML += `<option value="${{k}}">${{k}}</option>`;
  }});
  const fState = document.getElementById('f-state');
  Object.entries(META.state_stats).forEach(([k, v]) => {{
    fState.innerHTML += `<option value="${{k}}">${{k}} (${{v}})</option>`;
  }});

  const maxS = Math.max(...Object.values(META.sec_stats).map(x => x.rows));
  document.getElementById('chart-sec').innerHTML = Object.entries(META.sec_stats).map(([k, v]) => `
    <div class="bar-row" onclick="quickFilter('f-sec','${{k}}')">
      <div>${{esc(v.label)}}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${{(v.rows/maxS*100).toFixed(1)}}%"></div></div>
      <div class="bar-val">${{fmt(v.rows)}} (${{pct(v.rows, META.total_comm_rows)}})</div>
    </div>`).join('');

  const maxL = Math.max(...Object.values(META.land_stats));
  document.getElementById('chart-land').innerHTML = Object.entries(META.land_stats).map(([k, v]) => `
    <div class="bar-row" onclick="quickFilter('f-land','${{k}}')">
      <div><code>${{k}}</code></div>
      <div class="bar-track"><div class="bar-fill" style="width:${{(v/maxL*100).toFixed(1)}}%;background:#3b6e52"></div></div>
      <div class="bar-val">${{fmt(v)}} (${{pct(v, META.total_comm_rows)}})</div>
    </div>`).join('');

  const relOrder = ['skos:exactMatch','skos:closeMatch','skos:broadMatch','skos:relatedMatch','residual','ungrounded'];
  const maxR = Math.max(...relOrder.map(k => META.rel_rows[k] || 0));
  document.getElementById('chart-rel').innerHTML = relOrder.map(k => {{
    const r = META.rel_rows[k] || 0, c = META.rel_stats[k] || 0;
    return `<div class="bar-row" onclick="quickFilter('f-rel','${{k}}')">
      <div>${{relBadge(k)}} <span class="mono">(${{c}})</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:${{(r/maxR*100).toFixed(1)}}%;background:#7a4f01"></div></div>
      <div class="bar-val">${{fmt(r)}} (${{pct(r, META.total_comm_rows)}})</div>
    </div>`;
  }}).join('');
}}

function quickFilter(elId, val) {{
  const el = document.getElementById(elId);
  el.value = (el.value === val) ? '' : val;
  resetAndRender();
}}

function clearFilters() {{
  ['q','f-basis','f-sec','f-grp','f-land','f-rel','f-state','f-extra'].forEach(id => document.getElementById(id).value = '');
  resetAndRender();
}}

function resetAndRender() {{
  curPage = 1;
  expandedId = null;
  const q = document.getElementById('q').value.trim().toLowerCase();
  const basis = document.getElementById('f-basis').value;
  const sec = document.getElementById('f-sec').value;
  const grp = document.getElementById('f-grp').value;
  const land = document.getElementById('f-land').value;
  const rel = document.getElementById('f-rel').value;
  const st = document.getElementById('f-state').value;
  const ex = document.getElementById('f-extra').value;

  filtered = CONCEPTS.filter(c => {{
    if (basis && c.basis !== basis) return false;
    if (sec && c.sec !== sec) return false;
    if (grp && c.grp !== grp) return false;
    if (land && c.lb !== land) return false;
    if (rel && c.rel !== rel) return false;
    if (st && c.s !== st) return false;
    if (ex === 'def' && !c.def) return false;
    if (ex === 'alt' && !c.alts.length) return false;
    if (ex === 'relc' && !c.relc.length) return false;
    if (ex === 'comb' && !c.comb.length) return false;
    if (ex === 'taxa' && !c.tx.length) return false;
    if (ex === 'mat' && !c.mat.length) return false;
    if (ex === 'agrovoc' && !c.ag.length) return false;
    if (ex === 'stw' && !c.stw.length) return false;
    if (ex === 'aat' && !c.aat.length) return false;
    if (ex === 'agg' && !c.agg) return false;
    if (q) {{
      const hay = (c.id + ' ' + c.l + ' ' + c.alts.join(' ') + ' ' + c.h + ' ' + c.grpl + ' ' + c.secl + ' ' + c.si + ' ' +
        c.sub + ' ' + c.subl + ' ' + (c.roles||[]).join(' ') + ' ' +
        c.def + ' ' + c.wd.map(x => x.join(' ')).join(' ') + ' ' +
        c.tx.map(x => x.join(' ')).join(' ')).toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});
  renderTable();
}}

function buildTtlSnippet(c) {{
  let lines = [
    `${{c.id}} a skos:Concept, crm:E55_Type ;`,
    `    rdfs:label "${{c.l.replace(/"/g, '\\"')}}"@en ;`,
    `    skos:inScheme htc:scheme ;`,
    `    skos:prefLabel "${{c.l.replace(/"/g, '\\"')}}"@en ;`,
  ];
  if (c.alts.length) lines.push(`    skos:altLabel ${{c.alts.map(a => '"' + a.replace(/"/g, '\\"') + '"@en').join(', ')}} ;`);
  lines.push(`    skos:broader ${{c.br}} ;`);
  if (c.basis === 'doc') {{
    lines.push(`    oe:attestationBasis "document_attested" ;`);
    if (c.sub) lines.push(`    oe:subsumedInCustomsHeading ${{c.sub}} ;`);
  }}
  if (c.relc.length) lines.push(`    skos:related ${{c.relc.join(', ')}} ;`);
  if (c.comb.length) lines.push(`    oe:combinesConcept ${{c.comb.join(', ')}} ;`);
  if (c.matc.length) lines.push(`    oe:materialConcept ${{c.matc.join(', ')}} ;`);
  if (c.def) lines.push(`    skos:definition "${{c.def.slice(0, 220).replace(/"/g, '\\"')}}${{c.def.length > 220 ? '...' : ''}}"@en ;`);
  if (c.sn) lines.push(`    skos:scopeNote "${{c.sn.replace(/"/g, '\\"')}}"@en ;`);
  if (c.dsrc.length) lines.push(`    oe:dictionarySource ${{c.dsrc.map(x => '<' + x[1] + '>').join(', ')}} ;`);
  lines.push(`    oe:macroSector ${{c.sec}} ;`);
  lines.push(`    oe:commodityGroup ${{c.grp}} ;`);
  lines.push(`    oe:substanceHead "${{c.h.replace(/"/g, '\\"')}}" ;`);
  lines.push(`    oe:processingState "${{c.s}}" ;`);
  lines.push(`    oe:landBasis "${{c.lb}}" ;`);
  lines.push(`    oe:sitcCode "${{c.si}}" ;`);
  if (c.wd.length) lines.push(`    ${{c.rel}} ${{c.wd.map(x => 'wd:' + x[0]).join(', ')}} ;`);
  if (c.ag.length) lines.push(`    ${{c.agrel}} ${{c.ag.map(x => 'agrovoc:' + x).join(', ')}} ;`);
  if (c.stw.length) lines.push(`    ${{c.stwrel}} ${{c.stw.map(x => 'stw:' + x).join(', ')}} ;`);
  if (c.aat.length) lines.push(`    ${{c.aatrel}} ${{c.aat.map(x => 'aat:' + x).join(', ')}} ;`);
  if (c.tx.length) lines.push(`    oe:sourceTaxon ${{c.tx.map(x => 'wd:' + x[0]).join(', ')}} ;`);
  if (c.mat.length) lines.push(`    oe:madeOfMaterial ${{c.mat.map(x => 'wd:' + x[0]).join(', ')}} ;`);
  lines[lines.length - 1] = lines[lines.length - 1].replace(/ ;$/, ' .');
  return lines.join('\\n');
}}

function renderTable() {{
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  if (curPage > totalPages) curPage = totalPages;
  const slice = filtered.slice((curPage - 1) * PAGE_SIZE, curPage * PAGE_SIZE);
  const sumRows = filtered.reduce((a, c) => a + c.r, 0);
  document.getElementById('count-info').innerHTML =
    `Showing <strong>${{fmt(filtered.length)}}</strong> concepts (<strong>${{fmt(sumRows)}}</strong> rows, ${{pct(sumRows, META.total_comm_rows)}}) — Page ${{curPage}} of ${{totalPages}}`;

  const htmlRows = [];
  for (const c of slice) {{
    const wdHtml = c.wd.length
      ? `${{relBadge(c.rel)}} ` + c.wd.map(([q, l]) =>
          `<a class="mono" target="_blank" href="https://www.wikidata.org/wiki/${{q}}">${{q}}</a> ${{esc(l)}}`
        ).join(' + ')
      : relBadge(c.rel);

    const lodParts = [];
    if (c.ag.length) lodParts.push(c.ag.map(x => `<a class="badge b-tag" target="_blank" href="http://aims.fao.org/aos/agrovoc/${{x}}">AGROVOC:${{x}}</a>`).join(''));
    if (c.stw.length) lodParts.push(c.stw.map(x => `<a class="badge b-tag" target="_blank" href="http://zbw.eu/stw/descriptor/${{x}}">STW:${{x}}</a>`).join(''));
    if (c.aat.length) lodParts.push(c.aat.map(x => `<a class="badge b-tag" target="_blank" href="http://vocab.getty.edu/aat/${{x}}">AAT:${{x}}</a>`).join(''));
    if (c.tx.length) lodParts.push('<div style="margin-top:3px">' + c.tx.slice(0,3).map(([q, n]) => `<a target="_blank" href="https://www.wikidata.org/wiki/${{q}}"><em>${{esc(n || q)}}</em></a>`).join(', ') + '</div>');
    if (c.comb.length) lodParts.push('<div style="margin-top:2px">' + c.comb.map(id => `<span class="badge b-comb" onclick="event.stopPropagation();jumpToConcept('${{id}}')">combines ${{id}}</span>`).join('') + '</div>');
    if (c.sub) lodParts.push(`<div style="margin-top:2px"><span class="badge b-sub" onclick="event.stopPropagation();jumpToConcept('${{c.sub}}')">subsumed in ${{c.sub}}</span></div>`);
    if (c.relc.length) lodParts.push('<div style="margin-top:2px;font-size:0.74rem;color:#4c267a">related: ' + c.relc.slice(0,3).map(id => `<a href="#" onclick="event.stopPropagation();jumpToConcept('${{id}}');return false;">${{esc((BY_ID[id]||{{}}).l || id)}}</a>`).join(', ') + (c.relc.length > 3 ? ` +${{c.relc.length - 3}}` : '') + '</div>');

    const altHtml = c.alts.length
      ? '<div style="margin-top:3px">' + c.alts.map(a => `<span class="badge b-alt">${{esc(a)}}</span>`).join('') + '</div>'
      : '';

    htmlRows.push(`
      <tr class="data-row" onclick="toggleDetail('${{c.id}}')">
        <td class="mono">${{c.id}}</td>
        <td>
          <strong>${{esc(c.l)}}</strong>
          ${{c.basis === 'doc' ? ' <span class="badge b-doc" title="Document-attested minor 19th-c. commodity for text mining">Doc-Attested</span>' : ''}}
          ${{c.agg ? ' <span class="badge b-agg">Aggregate</span>' : ''}}
          ${{c.def ? ' <span class="badge b-tag" title="Has 19th-century dictionary definition">19c def</span>' : ''}}
          ${{altHtml}}
          <div style="font-size:0.75rem;color:#5c6672">${{c.basis === 'doc' ? ('roles: ' + esc((c.roles||[]).join(', ') || 'minor commodity')) : ('head: ' + esc(c.h))}}</div>
        </td>
        <td style="text-align:right;font-variant-numeric:tabular-nums">${{c.basis === 'doc' ? '<span style="color:#0c6356;font-size:0.74rem">doc</span>' : fmt(c.r)}}</td>
        <td>
          <div style="font-weight:600;font-size:0.8rem">${{esc(c.grpl)}}</div>
          <div style="font-size:0.74rem;color:#5c6672">${{esc(c.secl)}}</div>
          <span class="badge b-tag">${{c.lb}}</span>
        </td>
        <td><span class="badge b-tag">${{c.s}}</span><div class="mono" style="margin-top:2px;color:#5c6672">${{c.si.replace('SITC4_','SITC ')}}</div></td>
        <td>${{wdHtml}}${{c.wdesc ? `<div style="font-size:0.74rem;color:#5c6672;margin-top:2px">${{esc(c.wdesc.slice(0,95))}}</div>` : ''}}</td>
        <td>${{lodParts.join(' ')}}</td>
      </tr>
    `);

    if (expandedId === c.id) {{
      const defBlock = c.def
        ? `<div class="def-quote"><strong>19th-Century Commercial Definition:</strong> ${{esc(c.def)}}</div>`
        : '';
      const snBlock = c.sn
        ? `<div class="def-quote" style="border-left-color:#1d4e6b;background:#eef5f9"><strong>Historical Scope Note (<code>skos:scopeNote</code>):</strong> ${{esc(c.sn)}}</div>`
        : '';
      const dsrcHtml = c.dsrc.length
        ? c.dsrc.map(([cit, uri]) => `<div><a target="_blank" href="${{esc(uri)}}">${{esc(cit)}} ↗</a></div>`).join('')
        : 'none matched';
      const relChips = c.relc.length
        ? c.relc.map(id => `<span class="badge b-link" onclick="jumpToConcept('${{id}}')">${{id}} ${{esc((BY_ID[id]||{{}}).l || '')}}</span>`).join('')
        : 'none';
      const combChips = c.comb.length
        ? c.comb.map(id => `<span class="badge b-comb" onclick="jumpToConcept('${{id}}')">${{id}} ${{esc((BY_ID[id]||{{}}).l || '')}}</span>`).join('')
        : 'none';
      const matcChips = c.matc.length
        ? c.matc.map(id => `<span class="badge b-comb" onclick="jumpToConcept('${{id}}')">${{id}} ${{esc((BY_ID[id]||{{}}).l || '')}}</span>`).join('')
        : 'none';
      const indChips = (END_USES_BY_CID[c.id] || []).length
        ? (END_USES_BY_CID[c.id] || []).map(eu => `<span class="badge b-doc" style="cursor:pointer;margin-right:4px" onclick="switchTab('industries',document.getElementById('btn-industries'));selectIndustry('${{eu.industry_id}}')">${{esc(eu.industry_label)}} (${{eu.production_role.replace(/_/g,' ')}})</span>`).join('')
        : '';

      htmlRows.push(`
        <tr class="detail-row"><td colspan="7">
          ${{snBlock}}
          ${{defBlock}}
          <div class="detail-grid">
            <div class="detail-box">
              <h4>4-Tier Ontology &amp; Semantic Links</h4>
              <div><strong>Sector:</strong> ${{esc(c.secl)}} (<code>${{c.sec}}</code>)</div>
              <div><strong>Group:</strong> ${{esc(c.grpl)}} (<code>${{c.grp}}</code>)</div>
              <div><strong>Direct Broader:</strong> <code>${{c.br}}</code></div>
              ${{c.sub ? `<div style="margin-top:4px"><strong>Subsumed in Customs Catch-All:</strong> <span class="badge b-sub" onclick="jumpToConcept('${{c.sub}}')">${{c.sub}} ${{esc(c.subl)}}</span></div>` : ''}}
              <div style="margin-top:4px"><strong>Base Material (<code>oe:materialConcept</code>):</strong> ${{matcChips}}</div>
              <div style="margin-top:4px"><strong>Combines (<code>oe:combinesConcept</code>):</strong> ${{combChips}}</div>
              <div style="margin-top:4px"><strong>Related (<code>skos:related</code>):</strong> ${{relChips}}</div>
              ${{indChips ? `<div style="margin-top:6px"><strong>Industrial End-Uses (<code>oe:usedInIndustry</code>):</strong> ${{indChips}}</div>` : ''}}
            </div>
            <div class="detail-box">
              <h4>Archival Provenance &amp; Dictionary Sources</h4>
              <div><strong>Years:</strong> ${{c.y0 || '?'}}–${{c.y1 || '?'}}</div>
              <div><strong>Series:</strong> ${{esc(c.ser.join('; ') || 'n/a')}}</div>
              <div><strong>Theodoridis Bucket:</strong> <code>${{c.th}}</code></div>
              ${{c.b1866 ? `<div><strong>1866 SKOS Broader:</strong> <code>htc1866:${{esc(c.b1866)}}</code></div>` : ''}}
              <div style="margin-top:4px"><strong>Dictionary Sources:</strong> ${{dsrcHtml}}</div>
            </div>
            <div class="detail-box">
              <h4>Mapping Audit &amp; Taxa / Materials</h4>
              <div><strong>Rule:</strong> <code>${{esc(c.rule || 'none')}}</code> ${{c.via ? `(via "${{esc(c.via)}}")` : ''}}</div>
              <div><strong>Source Taxa:</strong> ${{c.tx.length ? c.tx.map(([q,n,col,r]) => `<em>${{esc(n)}}</em> (<a target="_blank" href="https://www.wikidata.org/wiki/${{q}}">${{q}}</a>${{col ? ', CoL:'+col : ''}})`).join('; ') : 'none'}}</div>
              <div><strong>Made Of Material:</strong> ${{c.mat.length ? c.mat.map(([q,l]) => `${{esc(l)}} (${{q}})`).join(', ') : 'none'}}</div>
            </div>
          </div>
          <pre class="ttl">${{esc(buildTtlSnippet(c))}}</pre>
        </td></tr>
      `);
    }}
  }}
  document.getElementById('tbody').innerHTML = htmlRows.join('');
  document.getElementById('pager').innerHTML = `
    <button ${{curPage<=1?'disabled':''}} onclick="goPage(1)">« First</button>
    <button ${{curPage<=1?'disabled':''}} onclick="goPage(${{curPage-1}})">‹ Prev</button>
    <span>Page ${{curPage}} / ${{totalPages}}</span>
    <button ${{curPage>=totalPages?'disabled':''}} onclick="goPage(${{curPage+1}})">Next ›</button>
    <button ${{curPage>=totalPages?'disabled':''}} onclick="goPage(${{totalPages}})">Last »</button>
  `;
}}

function toggleDetail(id) {{ expandedId = (expandedId === id ? null : id); renderTable(); }}
function goPage(p) {{ curPage = p; expandedId = null; renderTable(); window.scrollTo(0, 240); }}

let treeBuilt = false;
function buildTree() {{
  if (treeBuilt) return;
  treeBuilt = true;
  const bySecGrp = {{}};
  for (const c of CONCEPTS) {{
    bySecGrp[c.sec] = bySecGrp[c.sec] || {{}};
    (bySecGrp[c.sec][c.grp] = bySecGrp[c.sec][c.grp] || []).push(c);
  }}
  const parts = [];
  for (const [secId, sstat] of Object.entries(META.sec_stats)) {{
    const grpMap = bySecGrp[secId] || {{}};
    const grpEntries = Object.entries(grpMap).sort((a,b) =>
      b[1].reduce((s,x)=>s+x.r,0) - a[1].reduce((s,x)=>s+x.r,0)
    );
    let grpHtml = '';
    for (const [grpId, list] of grpEntries) {{
      const gRows = list.reduce((s,x)=>s+x.r,0);
      const byBr = {{}};
      for (const c of list) {{
        const k = c.br === grpId ? '__direct__' : c.br;
        (byBr[k] = byBr[k] || []).push(c);
      }}
      let subHtml = '';
      const subEntries = Object.entries(byBr).filter(([k]) => k !== '__direct__')
        .sort((a,b) => b[1].reduce((s,x)=>s+x.r,0) - a[1].reduce((s,x)=>s+x.r,0));
      for (const [subId, mems] of subEntries) {{
        const mRows = mems.reduce((s,x)=>s+x.r,0);
        const subLbl = mems[0].h + ' (substance group)';
        subHtml += `<details class="tree-sub"><summary>${{esc(subLbl)}} <span class="mono">(${{mems.length}} headings · ${{fmt(mRows)}} rows)</span></summary><div class="leaf-list">` +
          mems.map(x => `<span class="leaf-chip" onclick="jumpToConcept('${{x.id}}')"><span class="mono">${{x.id}}</span> ${{esc(x.l)}} (${{fmt(x.r)}}) ${{relBadge(x.rel)}}</span>`).join('') +
          `</div></details>`;
      }}
      const directs = byBr['__direct__'] || [];
      if (directs.length) {{
        subHtml += `<details class="tree-sub"><summary>Direct headings <span class="mono">(${{directs.length}} headings)</span></summary><div class="leaf-list">` +
          directs.slice(0, 140).map(x => `<span class="leaf-chip" onclick="jumpToConcept('${{x.id}}')"><span class="mono">${{x.id}}</span> ${{esc(x.l)}} (${{fmt(x.r)}}) ${{relBadge(x.rel)}}</span>`).join('') +
          (directs.length > 140 ? `<span class="leaf-chip">… +${{directs.length - 140}} more (use Browser tab)</span>` : '') +
          `</div></details>`;
      }}
      grpHtml += `<details class="tree-grp"><summary>${{esc(META.grp_stats[grpId].label)}} <span class="mono">(${{list.length}} concepts · ${{fmt(gRows)}} rows)</span></summary>${{subHtml}}</details>`;
    }}
    parts.push(`<details class="tree-sec"><summary>${{esc(sstat.label)}} <span class="mono">(${{sstat.cnt}} concepts · ${{fmt(sstat.rows)}} rows · ${{grpEntries.length}} groups)</span></summary>${{grpHtml}}</details>`);
  }}
  document.getElementById('tree-root').innerHTML = parts.join('');
}}

let placesBuilt = false;
function renderPlaces() {{
  if (!placesBuilt) {{
    placesBuilt = true;
    const pk = [
      [fmt(PLACES.length), 'Unique Printed Places', fmt(META.place_total_mentions) + ' total mentions'],
      [pct(META.place_qid_mentions, META.place_total_mentions), 'Grounded to QID(s)', fmt(META.place_qid_mentions) + ' mentions'],
      [fmt(META.place_stats.canadian_port || 0), 'Canadian Customs Ports', fmt(META.place_mentions.canadian_port || 0) + ' mentions (Canada KG + WD)'],
      [fmt(META.polity_pairs), 'Empire IN_POLITY Pairs', 'Year-aware lineage links'],
    ];
    document.getElementById('place-kpis').innerHTML = pk.map(([v,l,s]) =>
      `<div class="kpi"><div class="val">${{v}}</div><div class="lbl">${{l}}</div><div class="sub">${{s}}</div></div>`
    ).join('');
  }}
  const q = document.getElementById('pq').value.trim().toLowerCase();
  const fk = document.getElementById('f-pk').value;
  const rows = PLACES.filter(p => {{
    if (fk && p.k !== fk) return false;
    if (q && !(p.n + ' ' + p.q + ' ' + p.lbl + ' ' + p.src).toLowerCase().includes(q)) return false;
    return true;
  }});
  document.getElementById('ptbody').innerHTML = rows.map(p => {{
    const qHtml = p.q ? p.q.split('+').map(q => `<a class="mono" target="_blank" href="https://www.wikidata.org/wiki/${{q}}">${{q}}</a>`).join(' + ') : '—';
    return `<tr>
      <td><strong>${{esc(p.n)}}</strong></td>
      <td style="text-align:right;font-variant-numeric:tabular-nums">${{fmt(p.r)}}</td>
      <td><span class="badge b-tag">${{p.k}}</span></td>
      <td>${{qHtml}}</td>
      <td>${{esc(p.lbl || '—')}}</td>
      <td class="mono">${{p.ys && p.ys.length ? p.ys[0] + '–' + p.ys[1] : '—'}}</td>
      <td class="mono" style="color:#5c6672">${{esc(p.src || '—')}}</td>
    </tr>`;
  }}).join('');
}}

// =========================================================================
// INTERACTIVE PURE-SVG VISUAL TREE (ZERO EXTERNAL DEPENDENCIES)
// =========================================================================
const SEC_COLORS = {{
  'htc:sec_food_and_drink': '#1d4e6b',
  'htc:sec_minerals_metals_manufactures': '#5c6672',
  'htc:sec_forestry_timber': '#2f6b48',
  'htc:sec_hides_skins_tanning': '#8c4a27',
  'htc:sec_fibres_textiles': '#6f42c1',
  'htc:sec_botanicals_dyes_chemicals': '#b5651d',
  'htc:sec_livestock_fodder': '#a34832',
  'htc:sec_oils_fats_waxes': '#a87d1a',
  'htc:sec_unclassified_residuals': '#7a828a',
}};
const REL_COLORS = {{
  'skos:exactMatch': '#146c43',
  'skos:closeMatch': '#0d5c75',
  'skos:broadMatch': '#b57614',
  'skos:relatedMatch': '#6f42c1',
  'residual': '#7a828a',
  'ungrounded': '#b02a37',
  'doc_local': '#0c6356',
}};

let vtRoot = null;
let vtNodeMap = {{}};
let vtBuilt = false;
let vtPanZoomInit = false;
let vtSelectedId = null;
let vtMatchIds = new Set();
let vtPathIds = new Set();
let vtTx = 28, vtTy = 24, vtScale = 0.85;
let vtBounds = {{ w: 1000, h: 700 }};

function rebuildVTree() {{
  vtBuilt = false;
  vtNodeMap = {{}};
  vtMatchIds.clear();
  vtPathIds.clear();
  buildVTreeData();
  const q = document.getElementById('vt-q').value;
  if (q && q.trim()) vtreeSearch(q);
}}

function buildVTreeData() {{
  if (vtBuilt) return;
  vtBuilt = true;
  const incDoc = document.getElementById('vt-doc') ? document.getElementById('vt-doc').checked : true;

  const bySecGrp = {{}};
  for (const c of CONCEPTS) {{
    if (!incDoc && c.basis === 'doc') continue;
    bySecGrp[c.sec] = bySecGrp[c.sec] || {{}};
    (bySecGrp[c.sec][c.grp] = bySecGrp[c.sec][c.grp] || []).push(c);
  }}

  const root = {{
    id: 'htc:scheme', label: 'htc:scheme (Archival Trade SKOS)', kind: 'root',
    rows: META.total_comm_rows, count: META.total_concepts + (incDoc ? META.doc_concepts : 0), sector: '',
    expanded: true, children: [], parent: null
  }};
  vtNodeMap[root.id] = root;

  for (const [secId, sstat] of Object.entries(META.sec_stats)) {{
    const secNode = {{
      id: secId, label: sstat.label, kind: 'sector',
      rows: sstat.rows, count: sstat.cnt + (incDoc ? (sstat.doc_cnt || 0) : 0), sector: secId,
      expanded: true, children: [], parent: root
    }};
    vtNodeMap[secId] = secNode;
    root.children.push(secNode);

    const grpMap = bySecGrp[secId] || {{}};
    const grpEntries = Object.entries(grpMap).sort((a,b) =>
      b[1].reduce((s,x)=>s+x.r,0) - a[1].reduce((s,x)=>s+x.r,0)
    );
    for (const [grpId, list] of grpEntries) {{
      const gRows = list.reduce((s,x)=>s+x.r,0);
      const grpNode = {{
        id: grpId, label: META.grp_stats[grpId].label, kind: 'group',
        rows: gRows, count: list.length, sector: secId,
        expanded: false, children: [], parent: secNode
      }};
      vtNodeMap[grpId] = grpNode;
      secNode.children.push(grpNode);

      const byBr = {{}};
      for (const c of list) {{
        const k = c.br === grpId ? '__direct__' : c.br;
        (byBr[k] = byBr[k] || []).push(c);
      }}
      const subEntries = Object.entries(byBr).filter(([k]) => k !== '__direct__')
        .sort((a,b) => b[1].reduce((s,x)=>s+x.r,0) - a[1].reduce((s,x)=>s+x.r,0));
      for (const [subId, mems] of subEntries) {{
        const mRows = mems.reduce((s,x)=>s+x.r,0);
        const subNode = {{
          id: subId, label: mems[0].h + ' (' + mems.length + ')', kind: 'subgroup',
          rows: mRows, count: mems.length, sector: secId,
          expanded: false, children: [], parent: grpNode
        }};
        vtNodeMap[subId] = subNode;
        grpNode.children.push(subNode);
        for (const c of mems.sort((a,b) => b.r - a.r)) {{
          const leaf = {{
            id: c.id, label: c.l, kind: 'concept',
            rows: c.r, count: 1, sector: secId, concept: c,
            expanded: false, children: [], parent: subNode
          }};
          vtNodeMap[c.id] = leaf;
          subNode.children.push(leaf);
        }}
      }}
      const directs = (byBr['__direct__'] || []).sort((a,b) => b.r - a.r);
      for (const c of directs) {{
        const leaf = {{
          id: c.id, label: c.l, kind: 'concept',
          rows: c.r, count: 1, sector: secId, concept: c,
          expanded: false, children: [], parent: grpNode
        }};
        vtNodeMap[c.id] = leaf;
        grpNode.children.push(leaf);
      }}
    }}
  }}
  vtRoot = root;
  if (!vtPanZoomInit) {{ initVTreePanZoom(); vtPanZoomInit = true; }}
  renderVTree();
  vtreeFit();
}}

function initVTreePanZoom() {{
  const stage = document.getElementById('vt-stage');
  let dragging = false, sx = 0, sy = 0, ox = 0, oy = 0;
  stage.addEventListener('mousedown', e => {{
    if (e.target.closest('.vtree-node')) return;
    dragging = true; sx = e.clientX; sy = e.clientY; ox = vtTx; oy = vtTy;
    stage.classList.add('dragging');
  }});
  window.addEventListener('mousemove', e => {{
    if (!dragging) return;
    vtTx = ox + (e.clientX - sx);
    vtTy = oy + (e.clientY - sy);
    applyVTreeTransform();
  }});
  window.addEventListener('mouseup', () => {{
    dragging = false; stage.classList.remove('dragging');
  }});
  stage.addEventListener('wheel', e => {{
    e.preventDefault();
    const rect = stage.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    const ns = Math.max(0.15, Math.min(3.0, vtScale * factor));
    vtTx = mx - (mx - vtTx) * (ns / vtScale);
    vtTy = my - (my - vtTy) * (ns / vtScale);
    vtScale = ns;
    applyVTreeTransform();
  }}, {{ passive: false }});
}}

function applyVTreeTransform() {{
  const vp = document.getElementById('vt-viewport');
  if (vp) vp.setAttribute('transform', `translate(${{vtTx.toFixed(1)}},${{vtTy.toFixed(1)}}) scale(${{vtScale.toFixed(3)}})`);
}}

function vtreeZoom(factor) {{
  const stage = document.getElementById('vt-stage');
  const cx = stage.clientWidth / 2, cy = stage.clientHeight / 2;
  const ns = Math.max(0.15, Math.min(3.0, vtScale * factor));
  vtTx = cx - (cx - vtTx) * (ns / vtScale);
  vtTy = cy - (cy - vtTy) * (ns / vtScale);
  vtScale = ns;
  applyVTreeTransform();
}}

function vtreeFit() {{
  const stage = document.getElementById('vt-stage');
  const sw = stage.clientWidth || 960, sh = stage.clientHeight || 720;
  const pad = 36;
  const scaleX = (sw - pad * 2) / Math.max(300, vtBounds.w);
  const scaleY = (sh - pad * 2) / Math.max(200, vtBounds.h);
  vtScale = Math.max(0.18, Math.min(1.15, Math.min(scaleX, scaleY)));
  vtTx = pad;
  vtTy = Math.max(pad, (sh - vtBounds.h * vtScale) / 2);
  applyVTreeTransform();
}}

function vtreeSetDepth(maxDepth) {{
  vtMatchIds.clear(); vtPathIds.clear();
  document.getElementById('vt-q').value = '';
  function walk(n, d) {{
    n.expanded = d < maxDepth;
    for (const ch of n.children) walk(ch, d + 1);
  }}
  walk(vtRoot, 0);
  renderVTree();
  vtreeFit();
}}

function vtreeSearch(raw) {{
  const q = (raw || '').trim().toLowerCase();
  vtMatchIds.clear();
  vtPathIds.clear();
  if (!q) {{
    vtreeSetDepth(2);
    return;
  }}
  function collapseAll(n) {{ n.expanded = false; for (const ch of n.children) collapseAll(ch); }}
  collapseAll(vtRoot);
  vtRoot.expanded = true;

  let hits = 0;
  for (const c of CONCEPTS) {{
    const hay = (c.id + ' ' + c.l + ' ' + c.alts.join(' ') + ' ' + c.h + ' ' + c.grpl).toLowerCase();
    if (hay.includes(q)) {{
      vtMatchIds.add(c.id);
      hits++;
      if (hits <= 60) {{
        let cur = vtNodeMap[c.id];
        while (cur) {{
          vtPathIds.add(cur.id);
          if (cur.parent) cur.parent.expanded = true;
          cur = cur.parent;
        }}
      }}
    }}
  }}
  renderVTree();
  vtreeFit();
}}

function focusVTreeConcept(id) {{
  let cur = vtNodeMap[id];
  if (!cur) return;
  vtMatchIds.clear(); vtPathIds.clear();
  vtMatchIds.add(id);
  while (cur) {{
    vtPathIds.add(cur.id);
    if (cur.parent) cur.parent.expanded = true;
    cur = cur.parent;
  }}
  vtSelectedId = id;
  renderVTree();
  renderVTreeInspector(vtNodeMap[id]);
  // Center on the selected node
  const stage = document.getElementById('vt-stage');
  const n = vtNodeMap[id];
  if (n && n._x !== undefined) {{
    vtScale = Math.max(vtScale, 0.78);
    vtTx = (stage.clientWidth || 900) * 0.48 - n._x * vtScale;
    vtTy = (stage.clientHeight || 700) * 0.50 - n._y * vtScale;
    applyVTreeTransform();
  }}
}}

function vtreeNodeColor(n) {{
  const mode = document.getElementById('vt-color').value;
  if (vtMatchIds.has(n.id)) return '#d99b1e';
  if (mode === 'mapping' && n.concept) return REL_COLORS[n.concept.rel] || '#5c6672';
  if (n.kind === 'root') return '#17374b';
  return SEC_COLORS[n.sector] || '#1d4e6b';
}}

function renderVTree() {{
  if (!vtRoot) return;
  const COL_X = [20, 270, 560, 880, 1140];
  const ROW_H = 22;
  let nextY = 18;
  const visible = [];
  const visById = {{}};
  const links = [];

  function layout(node, depth) {{
    node._depth = depth;
    node._x = COL_X[Math.min(depth, COL_X.length - 1)];
    const kids = (node.expanded && node.children.length) ? node.children : [];
    if (!kids.length) {{
      node._y = nextY;
      nextY += ROW_H;
    }} else {{
      const ys = [];
      for (const ch of kids) {{
        layout(ch, depth + 1);
        ys.push(ch._y);
        links.push([node, ch]);
      }}
      node._y = (ys[0] + ys[ys.length - 1]) / 2;
    }}
    visible.push(node);
    visById[node.id] = node;
  }}
  layout(vtRoot, 0);

  let maxX = 0;
  for (const n of visible) maxX = Math.max(maxX, n._x + 300);
  vtBounds = {{ w: maxX + 40, h: nextY + 30 }};

  const svgParts = [];

  // 1. Hierarchical Bezier edges
  for (const [p, c] of links) {{
    const mx = (p._x + c._x) / 2;
    const isHi = vtPathIds.has(p.id) && vtPathIds.has(c.id);
    svgParts.push(`<path class="vtree-link${{isHi ? ' hi' : ''}}" d="M${{p._x}},${{p._y}} C${{mx}},${{p._y}} ${{mx}},${{c._y}} ${{c._x}},${{c._y}}" />`);
  }}

  // 2. Optional cross-links for visible skos:related & oe:combinesConcept pairs
  if (document.getElementById('vt-arcs').checked) {{
    const drawn = new Set();
    for (const n of visible) {{
      if (!n.concept) continue;
      for (const tid of (n.concept.comb || [])) {{
        const tn = visById[tid];
        if (!tn) continue;
        const dx = Math.max(55, Math.abs(n._y - tn._y) * 0.32);
        const ax = Math.max(n._x, tn._x) + 190 + dx;
        svgParts.push(`<path class="vtree-comb-arc" d="M${{n._x+8}},${{n._y}} Q${{ax}},${{(n._y+tn._y)/2}} ${{tn._x+8}},${{tn._y}}" />`);
      }}
      for (const tid of (n.concept.relc || [])) {{
        const tn = visById[tid];
        if (!tn) continue;
        const pairKey = [n.id, tid].sort().join('|');
        if (drawn.has(pairKey)) continue;
        drawn.add(pairKey);
        const dx = Math.max(45, Math.abs(n._y - tn._y) * 0.28);
        const ax = Math.max(n._x, tn._x) + 160 + dx;
        svgParts.push(`<path class="vtree-rel-arc" d="M${{n._x+8}},${{n._y}} Q${{ax}},${{(n._y+tn._y)/2}} ${{tn._x+8}},${{tn._y}}" />`);
      }}
    }}
  }}

  // 3. Nodes & labels
  for (const n of visible) {{
    const hasKids = n.children.length > 0;
    const r = n.kind === 'root' ? 8 : (n.kind === 'sector' ? 7 : (n.kind === 'group' ? 5.5 : (n.kind === 'subgroup' ? 4.5 : Math.max(3.5, Math.min(6, Math.log10(n.rows + 1) * 1.9)))));
    const col = vtreeNodeColor(n);
    const fill = (hasKids && !n.expanded) ? col : '#ffffff';
    const strokeW = (n.id === vtSelectedId || vtMatchIds.has(n.id)) ? 3 : 2;
    const lblText = n.label.length > 44 ? n.label.slice(0, 42) + '…' : n.label;
    const countTag = hasKids ? ` (${{n.count}})` : (n.concept && n.concept.basis === 'doc' ? ' · [doc]' : ` · ${{fmt(n.rows)}}`);
    const fontW = (n.kind === 'root' || n.kind === 'sector' || vtMatchIds.has(n.id) || n.id === vtSelectedId) ? '700' : (n.kind === 'group' ? '600' : '400');
    const fontS = n.kind === 'root' ? '12.5' : (n.kind === 'sector' ? '12' : (n.kind === 'group' ? '11.2' : '10.6'));
    const dashAttr = (n.concept && n.concept.basis === 'doc') ? ' stroke-dasharray="2.5 1.5"' : '';

    svgParts.push(`
      <g class="vtree-node" transform="translate(${{n._x}},${{n._y}})" onclick="onVTreeClick('${{esc(n.id)}}')">
        <circle r="${{r.toFixed(1)}}" fill="${{fill}}" stroke="${{col}}" stroke-width="${{strokeW}}"${{dashAttr}} />
        ${{hasKids ? `<text x="0" y="3" text-anchor="middle" font-size="8.5" font-weight="700" fill="${{n.expanded ? col : '#fff'}}">${{n.expanded ? '−' : '+'}}</text>` : ''}}
        <text x="${{(r + 6).toFixed(1)}}" y="3.8" font-size="${{fontS}}" font-weight="${{fontW}}">${{esc(lblText)}}<tspan fill="#6c757d" font-weight="400" font-size="9.8">${{esc(countTag)}}</tspan></text>
      </g>
    `);
  }}

  document.getElementById('vt-viewport').innerHTML = svgParts.join('');
  applyVTreeTransform();
}}

function onVTreeClick(id) {{
  const n = vtNodeMap[id];
  if (!n) return;
  vtSelectedId = id;
  if (n.children.length) {{
    n.expanded = !n.expanded;
    renderVTree();
  }} else {{
    renderVTree();
  }}
  renderVTreeInspector(n);
}}

function renderVTreeInspector(n) {{
  const box = document.getElementById('vt-side');
  if (!n) return;
  if (n.kind !== 'concept') {{
    const topKids = n.children.slice(0, 12).map(ch =>
      `<div style="margin:3px 0"><a href="#" onclick="onVTreeClick('${{esc(ch.id)}}');return false;">${{esc(ch.label)}}</a> <span class="mono" style="color:var(--muted)">(${{fmt(ch.rows)}} rows)</span></div>`
    ).join('');
    box.innerHTML = `
      <span class="badge b-tag">${{n.kind.toUpperCase()}}</span>
      <h3 style="margin-top:6px">${{esc(n.label)}}</h3>
      <div class="mono" style="color:var(--muted);margin-bottom:8px">${{esc(n.id)}}</div>
      <div><strong>Concepts:</strong> ${{fmt(n.count)}} · <strong>Layer-1 Rows:</strong> ${{fmt(n.rows)}} (${{pct(n.rows, META.total_comm_rows)}})</div>
      ${{n.children.length ? `<div style="margin-top:10px"><strong>Direct Children (${{n.children.length}}):</strong>${{topKids}}${{n.children.length > 12 ? `<div style="color:var(--muted);margin-top:4px">… +${{n.children.length - 12}} more</div>` : ''}}</div>` : ''}}
      ${{n.kind === 'sector' || n.kind === 'group' ? `<div style="margin-top:12px"><button onclick="switchTab('concepts',document.getElementById('btn-concepts'));clearFilters();document.getElementById('${{n.kind==='sector'?'f-sec':'f-grp'}}').value='${{n.id}}';resetAndRender();" style="padding:6px 10px;border:1px solid var(--border);border-radius:5px;background:#f2efe7;cursor:pointer;font-weight:600">Filter in Table Browser →</button></div>` : ''}}
    `;
    return;
  }}
  const c = n.concept;
  const alts = c.alts.length ? '<div style="margin:6px 0">' + c.alts.map(a => `<span class="badge b-alt">${{esc(a)}}</span>`).join('') + '</div>' : '';
  const def = c.def ? `<div class="def-quote" style="margin:8px 0">${{esc(c.def)}}</div>` : '';
  const sn = c.sn ? `<div class="def-quote" style="margin:8px 0;border-left-color:#1d4e6b;background:#eef5f9"><strong>Scope Note:</strong> ${{esc(c.sn)}}</div>` : '';
  const dsrc = c.dsrc.length ? '<div style="margin:4px 0"><strong>Sources:</strong> ' + c.dsrc.map(([cit,u]) => `<a target="_blank" href="${{esc(u)}}">${{esc(cit)}} ↗</a>`).join(' · ') + '</div>' : '';
  const wd = c.wd.length ? `${{relBadge(c.rel)}} ` + c.wd.map(([q,l]) => `<a class="mono" target="_blank" href="https://www.wikidata.org/wiki/${{q}}">${{q}}</a> ${{esc(l)}}`).join(' + ') : relBadge(c.rel);
  const taxa = c.tx.length ? '<div style="margin:5px 0"><strong>Taxa:</strong> ' + c.tx.map(([q,nm]) => `<a target="_blank" href="https://www.wikidata.org/wiki/${{q}}"><em>${{esc(nm||q)}}</em></a>`).join(', ') + '</div>' : '';
  const comb = c.comb.length ? '<div style="margin:6px 0"><strong>Combines:</strong> ' + c.comb.map(id => `<span class="badge b-comb" onclick="focusVTreeConcept('${{id}}')">${{id}} ${{esc((BY_ID[id]||{{}}).l||'')}}</span>`).join('') + '</div>' : '';
  const matc = c.matc.length ? '<div style="margin:6px 0"><strong>Base Material:</strong> ' + c.matc.map(id => `<span class="badge b-comb" onclick="focusVTreeConcept('${{id}}')">${{id}} ${{esc((BY_ID[id]||{{}}).l||'')}}</span>`).join('') + '</div>' : '';
  const relc = c.relc.length ? '<div style="margin:6px 0"><strong>Related:</strong> ' + c.relc.map(id => `<span class="badge b-link" onclick="focusVTreeConcept('${{id}}')">${{id}} ${{esc((BY_ID[id]||{{}}).l||'')}}</span>`).join('') + '</div>' : '';

  box.innerHTML = `
    <span class="mono" style="color:var(--muted)">${{c.id}}</span> · ${{c.basis === 'doc' ? '<span class="badge b-doc">Document-Attested</span>' : (fmt(c.r) + ' rows (' + (c.y0||'?') + '–' + (c.y1||'?') + ')')}}
    <h3 style="margin-top:4px">${{esc(c.l)}}</h3>
    ${{c.sub ? `<div style="margin:4px 0"><span class="badge b-sub" onclick="focusVTreeConcept('${{c.sub}}')">subsumed in ${{c.sub}} (${{esc(c.subl)}})</span></div>` : ''}}
    ${{alts}}
    <div style="margin:5px 0;font-size:0.79rem;color:var(--muted)">${{esc(c.secl)}} → <strong>${{esc(c.grpl)}}</strong></div>
    <div style="margin:6px 0">${{wd}}</div>
    <div style="margin:5px 0"><span class="badge b-tag">${{c.s}}</span> <span class="badge b-tag">${{c.lb}}</span> <span class="badge b-tag">${{c.si.replace('SITC4_','SITC ')}}</span></div>
    ${{sn}}
    ${{def}}
    ${{dsrc}}
    ${{taxa}}
    ${{matc}}
    ${{comb}}
    ${{relc}}
    <div style="margin-top:12px">
      <button onclick="jumpToConcept('${{c.id}}')" style="padding:6px 10px;border:1px solid var(--border);border-radius:5px;background:#f2efe7;cursor:pointer;font-weight:600">Open Full Record &amp; Turtle →</button>
    </div>
  `;
}}

let activeIndId = 'oe:ind_calico_printing';
let indBuilt = false;
const ROLE_ORDER = [
  ['primary_feedstock', 'Primary Feedstock / Base Material', '#146c43'],
  ['alkali_or_reagent', 'Alkali, Acid & Chemical Reagent', '#1d4e6b'],
  ['dye_or_colorant', 'Dyestuff, Dyewood & Pigment', '#8c2d19'],
  ['mordant_or_fixer', 'Mordant & Colour Fixer', '#6f42c1'],
  ['tanning_or_curing', 'Tanning, Tawing & Currying Agent', '#8c4a27'],
  ['thickener_or_sizing', 'Thickener, Gum, Resin & Sizing', '#7a4f01'],
  ['bleaching_agent', 'Bleaching & Clarifying Agent', '#0d5c75'],
  ['flavouring_or_scent', 'Flavouring, Spice & Perfume', '#9c4221'],
  ['solvent_or_fuel', 'Solvent, Flux, Fuel & Lubricant', '#495057'],
  ['filler_or_admixture', 'Binder, Dairy, Fibre & Admixture', '#4a5568'],
];

function buildIndustryButtons() {{
  const box = document.getElementById('ind-buttons');
  if (!box) return;
  const counts = {{}};
  for (const r of END_USES) counts[r.industry_id] = (counts[r.industry_id] || 0) + 1;
  box.innerHTML = Object.entries(IND_META).map(([id, m]) => {{
    const active = (id === activeIndId);
    const st = active ? 'background:#1d4e6b;color:#fff;border-color:#1d4e6b' : '';
    return `<button onclick="selectIndustry('${{id}}')" id="indbtn-${{id}}" style="${{st}}">${{esc(m.label)}} <span style="opacity:0.75">(${{counts[id]||0}})</span></button>`;
  }}).join('');
}}

function selectIndustry(indId) {{
  activeIndId = indId;
  const qEl = document.getElementById('ind-q');
  if (qEl) qEl.value = '';
  buildIndustryButtons();
  renderIndustries();
}}

function renderIndustries() {{
  if (!indBuilt) {{
    indBuilt = true;
    buildIndustryButtons();
  }}
  const q = ((document.getElementById('ind-q') || {{}}).value || '').trim().toLowerCase();

  // If user typed a search query, search across ALL 18 industries!
  if (q) {{
    const hits = END_USES.filter(r =>
      (r.commodity_label + ' ' + r.commodity_id + ' ' + r.industry_label + ' ' + r.production_role_label + ' ' +
       (r.evidence_quotes || []).map(x => x.quote).join(' ')).toLowerCase().includes(q)
    );
    let html = `<div class="card" style="margin-bottom:14px;border-left:4px solid #b58d3d">
      <h3 style="margin:0">Cross-Industry Search: “${{esc(q)}}” — ${{hits.length}} attested links across ${{new Set(hits.map(x=>x.industry_id)).size}} industries</h3>
    </div>`;
    if (!hits.length) {{
      document.getElementById('ind-content').innerHTML = html + '<div class="card">No matching commodity-industry links found.</div>';
      return;
    }}
    html += `<div class="card"><table><thead><tr>
      <th style="width:210px">Industry</th>
      <th style="width:210px">Commodity &amp; Role</th>
      <th style="width:95px">Attestation</th>
      <th>Primary-Source Quotes</th>
    </tr></thead><tbody>`;
    for (const r of hits) {{
      const quotesHtml = (r.evidence_quotes || []).slice(0, 2).map(qt => `
        <div class="def-quote" style="margin:0 0 5px 0;padding:5px 9px;font-size:0.8rem">
          “${{esc(qt.quote)}}” <a target="_blank" href="${{esc(qt.uri)}}">[${{esc(qt.citation)}} ↗]</a>
        </div>`).join('');
      html += `<tr>
        <td><a href="#" onclick="selectIndustry('${{r.industry_id}}');return false;" style="font-weight:700">${{esc(r.industry_label)}}</a></td>
        <td>
          <a href="#" onclick="jumpToConcept('${{r.commodity_id}}');return false;" style="font-weight:700">${{esc(r.commodity_label)}}</a>
          <div style="margin-top:2px"><span class="badge b-tag">${{esc(r.production_role_label)}}</span></div>
        </td>
        <td><span class="badge b-exact">${{r.book_count}}b / ${{r.mention_count}}m</span></td>
        <td>${{quotesHtml}}</td>
      </tr>`;
    }}
    html += '</tbody></table></div>';
    document.getElementById('ind-content').innerHTML = html;
    return;
  }}

  const rows = END_USES.filter(x => x.industry_id === activeIndId);
  const meta = IND_META[activeIndId] || {{ label: activeIndId, desc: '' }};
  const l1n = rows.filter(x => x.attestation_basis === 'customs_enumerated').length;
  const docn = rows.length - l1n;
  const totM = rows.reduce((s, x) => s + (x.mention_count || 0), 0);

  let html = `
    <div class="card" style="margin-bottom:14px;border-left:4px solid #1d4e6b">
      <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px">
        <h3 style="margin:0;font-size:1.15rem">${{esc(meta.label)}} <span class="mono" style="font-weight:400;color:var(--muted)">(${{activeIndId}})</span></h3>
        <div>
          <span class="badge b-exact">${{rows.length}} Attested Inputs</span>
          <span class="badge b-close">${{l1n}} Layer-1 Customs</span>
          <span class="badge b-doc">${{docn}} Doc-Attested</span>
          <span class="badge b-tag">${{fmt(totM)}} Primary-Source Sentences</span>
        </div>
      </div>
      <p style="margin:8px 0 0 0;color:var(--muted);font-size:0.86rem">${{esc(meta.desc)}}</p>
    </div>
  `;

  for (const [rkey, rlbl, rcol] of ROLE_ORDER) {{
    const rlist = rows.filter(x => x.production_role === rkey);
    if (!rlist.length) continue;
    html += `<div class="card" style="margin-bottom:14px;">
      <h3 style="border-bottom:2px solid ${{rcol}};padding-bottom:6px;margin-bottom:10px;color:${{rcol}}">${{esc(rlbl)}} (${{rlist.length}})</h3>
      <table>
        <thead>
          <tr>
            <th style="width:230px">Commodity</th>
            <th style="width:105px">Tier / Rows</th>
            <th style="width:95px">Attestation</th>
            <th>Primary-Source Evidence Quotes (Ure 1840, Simmonds 1854/1892, McCulloch 1880, Mortimer 1823, Watt 1908)</th>
          </tr>
        </thead>
        <tbody>`;
    for (const r of rlist) {{
      const tierBadge = r.attestation_basis === 'document_attested'
        ? '<span class="badge b-doc">Doc-Attested</span>'
        : `<span class="badge b-close">Layer-1</span><div class="mono" style="color:var(--muted);margin-top:2px">${{fmt(r.layer1_rows)}} rows</div>`;
      const quotesHtml = (r.evidence_quotes || []).map(q => `
        <div class="def-quote" style="margin:0 0 6px 0;padding:6px 10px;font-size:0.81rem">
          “${{esc(q.quote)}}”
          <div style="font-family:-apple-system,sans-serif;font-size:0.74rem;margin-top:3px">
            — <a target="_blank" href="${{esc(q.uri)}}">${{esc(q.citation)}} ↗</a>
          </div>
        </div>
      `).join('');
      html += `
        <tr>
          <td>
            <a href="#" onclick="jumpToConcept('${{r.commodity_id}}');return false;" style="font-weight:700">${{esc(r.commodity_label)}}</a>
            <div class="mono" style="color:var(--muted)">${{r.commodity_id}}${{r.wikidata_qid ? ` · <a target="_blank" href="https://www.wikidata.org/wiki/${{r.wikidata_qid}}">${{r.wikidata_qid}}</a>` : ''}}</div>
            <div style="font-size:0.74rem;color:var(--muted)">${{esc(r.commodity_group)}}</div>
          </td>
          <td>${{tierBadge}}</td>
          <td>
            <span class="badge b-exact">${{r.book_count}} book${{r.book_count>1?'s':''}}</span>
            <div class="mono" style="color:var(--muted);margin-top:2px">${{r.mention_count}} sent.</div>
          </td>
          <td>${{quotesHtml}}</td>
        </tr>`;
    }}
    html += `</tbody></table></div>`;
  }}
  document.getElementById('ind-content').innerHTML = html;
}}

function switchTab(name, btn) {{
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'vtree') buildVTreeData();
  if (name === 'hierarchy') buildTree();
  if (name === 'industries') renderIndustries();
  if (name === 'places') renderPlaces();
}}

initDashboard();
renderTable();
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html_doc, encoding="utf-8")
    DOCS_HTML.parent.mkdir(parents=True, exist_ok=True)
    DOCS_HTML.write_text(html_doc, encoding="utf-8")
    (DOCS_HTML.parent / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Wrote {OUT_HTML} ({OUT_HTML.stat().st_size/1024:.1f} KB) and {DOCS_HTML}")


if __name__ == "__main__":
    main()
