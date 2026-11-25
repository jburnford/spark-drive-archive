# v5 Final Verification Note — Layer-1 Commodity SKOS

*Reviewer: `skos-reviewer` · 2026-11-25 · Follows [V4](OPUS_SKOS_REVIEW_V4.md)*

**Method:**
- Parsed TTL and JSON-LD with rdflib 7.6.0 and ran the full SKOS integrity suite.
- Diffed every anchor against v4: **260 anchors changed, and I read all of them.**
- Scanned all 1,421 anchor descriptions for homonym signals.
- Read all **257 `skos:related` pairs**.
- Re-checked the definitions I flagged in v4 and sampled 40 new ones.

## Verdict: ✅ PUBLISHABLE
No P0s remain. What is left is P1/P2 polish that can go in a point release.

| Check | Result |
|---|---|
| TTL vs JSON-LD | **45,938 = 45,938 triples, 0 diff** |
| IDs | `htc_id_registry.tsv` byte-identical to v3/v4 |
| Hierarchy | 2,343 concepts, 52 top concepts, **0 orphans, 0 cycles, 0 multi-parent**, all `inScheme` |
| S13 / S14 / S27 | **0 / 0 / 0**. `related` is symmetric, has no self-links, and never overlaps `broaderTransitive`. |
| Mappings | **0 duplicate `exactMatch` targets**. 0 clashes across exact/close/broad/related/narrow. 0 `*Match` links inside the scheme. |
| IRIs | 0 `c_c_`. AGROVOC all numeric. STW, AAT and Wikidata all canonical. No malformed IRIs. 0 NULL-series. All `oe:` properties declared (incl. `oe:materialConcept`). |
| v4 P0s | **Fixed.** *Mares* → livestock (`Q103459`). Bogus related pairs removed: Spirits↔Tallow, Maize↔Mace, Starch↔Brimstone, Axes↔Ultramarine and the rest. *Scientific Instruments other than Electrical* → scientific instrument `Q3099911`. Electrical goods no longer → cable. |
| Homonym scan | **0 homonyms** among the 1,421 anchors. Relaxing the colour and sailing-vessel rules surfaced only legitimate senses: dyes, mast `Q331744`, bowsprit, annatto, turmeric. |
| Coverage | 1,421 concepts / 131,256 rows (86.0%). The ~150 correct v3 anchors I listed are back: sugar family, dyes/madder/indigo, hops, galls, guano, footwear, machinery, yarn, gums, masts, arrowroot/sago/tapioca, baleen. Residuals are 4,697 rows (3.08%). |
| Definitions | Every wrong sense I flagged in v4 is fixed or removed (Vegetables, Gin, Tongues, Paper, Bark, Paint, Oil Unenumerated). Error rate in the new sample is ~1–2 of 40. |

## Residual (non-blocking)
**P1**
- `htc:1137` *Hemp Seeds* → `Q13414920` hemp **fiber** (seed vs fibre).
- `htc:1686` *Rapeseed Oil* → `broadMatch` seed (it is the oil; it also sits in `grp_oilseeds` / SITC 22 rather than 42).
- `htc:1674` *Electrical Goods … Telegraph and Telephone Cables* → rope `Q31029`.
- **Odd `related` hubs.** About 14 wood headings (wood manufactures, furniture, dye woods, anchor stocks, rag/wood pulp `0851`, `1544`, `1658`) are linked to **`0211` *Knees*** (curved ship timbers) as "the" wood concept. About 10 linen manufactures are linked to **`1979` *Linen Waste***. Point these `oe:materialConcept`/`related` links at `0070` *Wood Unenumerated* and a raw-linen/flax heading, or at the substance group.
- **Definition leftovers.** `0256` *Tobacco Manufactured Snuff* has the *Lobelia inflata* ("Indian tobacco") entry. `0337` *Castings* is defined as the founding process. `0612` *Spirits Unenumerated…* has customs-duty prose instead of a definition. `2014` *Bass* has a bast/rush definition but a fish anchor, so one of the two is wrong.

**P2**
- Mineral/aerated waters (`0904`, `1574`) sit under `grp_alcoholic_beverages`.
- Garden and caraway seeds (`0246`, `1385`) sit in `grp_oilseeds`.
- `0459` *Pictures* / `0381` *Embroidery* map to the practice-sense items (painting, embroidery as an art).

## Recommendation
Tag and publish v5 as the Layer-1 commodity vocabulary release. Fold the P1 items into v5.1 along with the CI regression list: the rejected QIDs from V2–V4, plus the S13/S14/S27/IRI checks above.
