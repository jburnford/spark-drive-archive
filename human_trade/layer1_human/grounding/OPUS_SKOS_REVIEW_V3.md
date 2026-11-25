# v3 Re-Verification Verdict — Layer-1 Commodity SKOS

*Reviewer: `skos-reviewer` · 2026-11-24 · Follow-up to [OPUS_SKOS_REVIEW.md](OPUS_SKOS_REVIEW.md)*

**Inputs re-checked:** `commodities_skos.ttl` / `.jsonld`, `commodities_concepts.jsonl`, `commodities_mappings.sssom.tsv`, `htc_id_registry.tsv`, `commodity_rejections.tsv`, `ground_commodities_v3.py`.
**Method:** I parsed both serializations with rdflib 7.6.0 and ran SKOS integrity queries. I read **all 1,309 grounded concepts** line by line (scratch `v3/g3.tsv`), ran a regex scan of every anchor description for homonym signals, checked facet consistency, and diffed the SSSOM table against the TTL.

## Verdict
**Big improvement. Conditional pass for structure; Layer B still needs one short correction pass before publication.**
- Wrong-entity anchors are down from ~90 concepts / ~5,300 rows (v2) to **~30 concepts / ~2,300 rows**: 2.3% of grounded concepts and 1.9% of grounded rows.
- But these ~30 are **new regressions**. One is the #5 heading by frequency (`htc:0005` *Horses*).
- There is also a new facet regression: **pig iron and lead are now classed as live animals**.

## 1. Confirmed fixed ✅
| v2 finding | v3 evidence |
|---|---|
| AGROVOC `c_c_` | 0 `c_c_` IRIs. `agrovoc:c_1162` etc. are correct. |
| Positional IDs | `htc_id_registry.tsv` has 2,066 entries. **0 label/ID mismatches** against all 1,174 v2-grounded concepts, and JSONL IDs equal the registry. `skos:notation` is emitted. |
| `exactMatch` collapse | 0 Wikidata targets with more than one `exactMatch` subject. 0 exact/broad, exact/related, close/broad or broad/related clashes. |
| Composed LOD relations | Relations follow the composition rule (exact→close, broad→broad, related→related). Staves are now `relatedMatch` barrel with no inherited AAT. |
| v2 homonyms | Plumbago→graphite `Q5309`, Tar→`Q186209`, Cordage→rope `Q31029`, Clocks→`Q376`, Watches→`Q178794`, Toys→`Q11422`, Castor→castoreum `Q162724`, Matches→`Q37507`, Cement→`Q45190`, Clay→`Q42302`, Veneers→`Q477683`, Bugles/Beads→`Q1053956`, Type→`Q426853`, Bones→`Q265868` |
| v2 wrong substances | Coconut oils→`Q216235`; fish/seal/whale oils→`Q1786125`/`Q104904040`/`Q1053334`; oil-seed cakes→press cake `Q513720`; Cotton Seeds→`Q17104079`; cottonseed oil→`Q811663`; Wool Cotton→cotton; Timber Walnut→wood + `sourceTaxon` *Juglans*; sheep pelts→sheepskin; soda bicarbonate/caustic/sulphate→`Q179731`/`Q102769`/`Q211737`; Salt→table salt `Q11254`; ores→ore items (`Q191552`, `Q4410773`, `Q12135758`…) |
| Structure | 0 orphans; `hasTopConcept` (13 domains + 43 `htc1866:` tops); 2,130 `skos:broader`; no cycles. `oe:` RDFS/OWL declarations present. `prov:hadPrimarySource` uses series IRIs. Scheme metadata complete. |
| Facets | `other` cut to 6,321 rows (4.1%). Manufactures moved to `manufactured_goods`. `oe:landBasis`, `fisheries_marine`, `fodder_feed` and `isAggregate` (20 headings) added. SITC is now real Rev. 4 divisions. |
| SSSOM | 3,443 rows. **Every SSSOM row is present in the TTL.** The TTL has 93 extra internal `broadMatch` links to `htc1866:`, which is acceptable. |

## 2. Remaining / new problems

### P0 — must fix (all mechanical)
**A. New homonym anchors: 30 concepts, ~2,307 rows**

| htc | Heading | rows | Anchor (stored description) |
|---|---|---:|---|
| 0005, 0595, 1018 | Horses; …over one year old; …one year old or less | 1,370 | `Q10889209` *horse* :: **xiangqi piece** (`0005` is an `exactMatch`) |
| 0156, 0195, 0280, 1085, 1203, 1524, 2006 | Horns and Hoofs; Horns Tips…; Horns Unenumerated; Horns Deer/Buffalo/Ox/Buck | 579 | `Q163759` *horn* :: **valved brass instrument**, plus inherited AAT `300042319`, `300205592` (v2 had horn-material `Q29838373`) |
| 0420 | Sponge | 88 | `Q7578994` :: bread making process |
| 0543 | Pitch | 66 | `Q118819` :: perceptual property in music (+AAT `300236361`) |
| 1168, 1198 | Cattle and (other) Animal Foods… | 37 | `Q830` **cattle (live)**, plus inherited AGROVOC `c_1391` and STW `14142-3` |
| 0868 | Paper Making Materials Pulp of Wood | 33 | `Q1470757` *pulp* :: flesh of a fruit |
| 0941 | Pickets | 29 | `Q1388729` :: soldiers placed forward of a position |
| 0980 | Mace | 26 | `Q272990` :: blunt weapon (+AAT `300037214`). **v2 had the spice `Q1882876`.** |
| 1019 | Junk | 25 | `Q205011` :: SE-Asian vessel (+AAT). In customs, junk is old rope/oakum. |
| 1235 | Ships with the Tackle Apparel and Furniture… | 16 | `Q11460` **clothing** (matched on "apparel") |
| 1605, 1860 | Cannon and Mortars … with Carriages | 12 | `Q235356` horse-drawn carriage |
| 1887, 1923, 2061 | Copper … cement copper … | 8 | `Q45190` hydraulic cement |
| 1642 | Down | 7 | `Q15332388` :: relative direction |
| 1767 | Wedges | 5 | `Q15087361` :: bertsolari verse fillers |
| 1908 | Blue | 3 | `Q1088` :: primary colour (+AAT) |
| 2014 | Bass | 1 | `Q27911` :: singing voice |
| 2028 | Bear | 1 | `Q618804` :: gay-culture term |
| 2029 | Billets | 1 | `Q1308509` :: soldiers' living quarters |

**Root cause (code).** `pick_commodity_candidate` ([ground_commodities_v3.py L731–758](file:///home/jic823/Documents/open_empire/human_trade/scripts/ground_commodities_v3.py#L731-L758)) has **only negative filters**: the forbidden P31 set, a lowercase check, a description blacklist and the rejection list. It ranks what survives by sitelinks. The v2 *positive* description/type gate was removed. Two side effects follow:
1. Each rejection or taxon block hands the match to the **next homonym**. Sponge went from cleaning tool to bread process; Blue from soft drink to colour; Bear and Bass, whose taxa are now blocked, went to a slang term and a voice type; Horse (taxon blocked) went to a xiangqi piece.
2. Material senses lose to higher-sitelink artefact senses (horn material → brass horn).

**Fix:** require a positive P31/P279 allowlist (material, food, product, commodity, chemical substance, animal product, plant product, raw material) or a positive description gate. For animal headings with no non-taxon item, leave them unmatched with `oe:sourceTaxon` only. Add a CI regression list of the QIDs above.

**B. Facet regression: pig iron and lead classed as live animals (7 concepts, 653 rows).** `0107` *Pig and Scrap Iron*, `0267` *Lead Pig and Sheet*, `0342` *Iron Pig*, `0700` *Lead Pig*, `0933`, `1331`, `1676` all carry `processing_state=live`, `ghost_acres_domain=food_animal`, `land_basis=terrestrial_pasture`, `theodoridis=animals_and_animal_products` and `sitcCode=SITC4_00_Live_Animals`. This puts 653 metal rows into the pasture ghost-acres total. The `pig` token needs a negative look-behind for *iron/lead/scrap*. The substance tier even mints `htc:sub_food_iron_pig` under `dom_food_animal`.

**C. New SKOS S14 violation: 51 duplicate prefLabels in `htc:scheme`.** Layer-A′ substance concepts reuse the verbatim heading as their label, e.g. `htc:sub_food_peas` vs `htc:0006` "Peas"; `sub_food_wine`/`0269`; `sub_food_beef`/`0031`; `sub_food_iron_pig`/`0342`. Either give the A′ concepts distinct labels (e.g. "Peas (substance group)"@en) or put them in their own `skos:ConceptScheme`.

### P1 — important
1. **Granularity loss on top grains.** 14 headings (5,629 rows) now `broadMatch` only `Q12117` *cereal*: *Oats* 1,681, *Barley* 1,156, *Barley and Rye* 956 (two identical components), *Indian Corn* 513, *Maize* 496, *Rye* 336, buckwheat… `htc:0006` *Peas* (1,255 rows) is now ungrounded. Find non-taxon grain/pulse items (e.g. the maize-seed item `Q25618328` already used in v2) rather than falling back to "cereal". `htc:0002` *Butter* is `broadMatch` butter purely because of `dairy_processed`. That state is intrinsic to butter, so `exactMatch` is right.
2. **Remaining sense errors (P1/P2).** `0620` *Ashes* → combustion ash `Q152079` (v2 had potash; in Canadian series it means pot/pearl ash); `0913` *Percussion Caps* → toy-weapon caps; `0459` *Pictures* → painting (the practice); `1212` *Perfumery* → the art; `1955` *Coral* → class Anthozoa (a taxon in `*Match`, despite the "zero taxa" claim); `1408` *Pyrites* → "outdated classification"; `1548` *Railway Carriages* → horse-drawn carriage; `1672`/`1674`/`1815` electric wires and cables → rope; `1059`/`1746` machinery belting → machine; `1854` *Pictures … not on paper* → paper; `0395`/`1417` *Sugar Boxes / Sugar Box Shooks* → sugar (they are timber shooks); `0261` *Handspikes* → metal lever; `0647` *Timber Anchor Stocks* → anchor (part/whole); 12 feather headings → `Q81025` (anatomical structure).
3. **Domain glitches (~1,500 rows).** Bones → `fisheries_marine` (`0162`, `0517`; the trigger is the word "whale" in the exclusion clause). Garden/caraway seeds, kidney beans, chick peas and cheese → `fats_oils_soap` (`0246`, `0899`, `1385`, `1927`, `1415`, `1668`). Wine in wood, spruce beer, iron/steel rails, iron hoops and sugar-box shooks → `timber_forestry` (`0978`, `1354`, `1380`, `1030`, `1679`, `1741`, `0905`, `1417`). Mineral waters → minerals (`0904`, `1574`). Cream of Tartar → `food_animal` (`0750`). Horns/hoofs/ivory → `drugs_botanicals_chemicals`.
4. **The substance tier is thin.** There are 64 groups, mostly with 2 members (~170 of 2,066 concepts). The large families are not grouped: iron 46, wine 39, *skins furs pelts* 39, silk manufactures 31, hides 26. Tobacco is split across food and manufactured. A′ concepts carry no Layer-B mapping, so the "one reviewed mapping per substance" benefit is not yet realised.
5. **Provenance hygiene.** `oe:series_null_and_other_errors` ("NULL and other errors") is emitted as a `prov:Entity` primary source for 63 concepts. Drop it or replace it with a "source unresolved" flag.

### P2
- The JSON-LD lacks the 57 ontology-declaration triples (`rdfs:label/domain/range` for `oe:` properties). Instance data is otherwise identical to the TTL (42,612 vs 42,669 triples, 0 JSON-LD-only triples).
- Check that the non-numeric AGROVOC id `agrovoc:c_edddeb10` resolves.
- `fodder_feed` maps to Theodoridis `raw_materials`. Consider whether bran and oil cake belong with grain or animal products for comparability.

## 3. Bottom line
All 9 v2 P0s are fixed **as specified**. The fix for P0 #3/#4 (type filtering) traded the old false positives for a new, smaller set because there is no positive type gate. Before publication:
- **A** — add a positive allowlist and re-run.
- **B** — fix the `pig` regex.
- **C** — relabel or re-scheme the A′ concepts.

All three are mechanical. After them and P1.1 (grain granularity), Layer B is publishable.
