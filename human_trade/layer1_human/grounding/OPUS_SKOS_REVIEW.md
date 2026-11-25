# Independent Review — Layer-1 (`human_transcribed`) Commodity SKOS Vocabulary

*London's Ghost Acres* / Open Empire · Reviewer: `skos-reviewer` · 2026-11-24
Scope: `htc:0001`–`htc:2066` (2,066 printed headings, 152,625 Layer-1 rows as summed from `commodities_concepts.jsonl`).

---

## 0. Verdict (TL;DR)

| Layer | Verdict |
|---|---|
| **Layer A — verbatim archival concepts** | **Sound in principle.** 2,066 unique prefLabels, no SKOS S14 clashes, labels escaped correctly, and the Turtle parses cleanly. Two things are seriously wrong: the IDs are **positional (frequency-rank) and not persistent**, and the facet classifier makes **systematic order-of-rule errors**. |
| **Layer B — LOD mappings** | **Not ready to publish.** Every one of the 253 AGROVOC IRIs is broken (`c_c_…`). I found **~90 grounded concepts (~5,300 rows) mapped to the wrong entity or substance**: CLOCK gene, GNU `watch`, a rocket stage, a Swedish chewing gum, a moth, tobacco tar, a rope data structure, and so on. **~640 concepts (~31k rows)** use `closeMatch` where the correct relation is `broadMatch`, and `exactMatch` is used in ways that **collapse processing states**, which is exactly what the two-layer design promises not to do. External AGROVOC/AAT/STW links take their relation strength from Wikidata without checking whether the Wikidata link itself is broad or wrong. |
| **Facets / SITC / Theodoridis** | The SITC rollup and the Theodoridis bucket are **pure functions of `ghost_acres_domain`**, so every domain error spreads to both. About 75% of the 27,868 `other`/`unclassified` rows come from **gaps in the regex vocabulary** (plurals, missing customs terms, spelling variants), not from real ambiguity. |

Overall: **publish Layer A after the ID fix. Hold Layer B until the P0 list in §6 is done.** The rest of the architecture (opaque local concepts, faceted state, reversible mappings) is the right design and is worth keeping.

### Method
- I regenerated `commodities_skos.ttl`/`.jsonld` byte-for-byte from `commodities_concepts.jsonl`, using the exporter's own serialization code ([export_layer1_skos_and_report.py L26–163](file:///home/jic823/Documents/open_empire/human_trade/scripts/export_layer1_skos_and_report.py#L26-L163)). The production `.ttl`/`.jsonld` files were not present in the read-only grounding directory I could see. The regenerated copies live in scratch (`regen_commodities_skos.ttl`, `.jsonld`). I parsed both with **rdflib 7.6.0** (Turtle + JSON-LD) and ran SKOS integrity queries.
- **Empirical audit: I read all 1,174 grounded concepts (100%, not a sample).** That covers all four tiers (`grounded_exact` 143, `grounded_substance_head` 120, `grounded_wikidata_slim` 908, `grounded_compound_commodity` 3) across top, mid and long-tail frequency. I quantified the error classes with scripts.
- Every QID and label below was read from `commodities_concepts.jsonl` on disk. No QIDs come from memory. Where I suggest a replacement I name the *existing* in-vocabulary QID (e.g. `Q5309` graphite, `Q513720` press cake, `Q191552` iron ore, `Q89` apple), or else describe the target type without guessing a QID.

---

## 1. RDF / SKOS / JSON-LD Syntax and Modelling Validity

### 1.1 What is correct
- **Turtle parses**: 25,649 triples, 2,066 `skos:Concept`, one `skos:ConceptScheme`. `htc:0001`-style local names and `stw:14098-1` are legal Turtle 1.1 PN_LOCAL. `ttl_str()` escapes `\`, `"`, CR and LF, and no label contains control characters, quotes or backslashes.
- **JSON-LD parses**: 25,648 triples. It is isomorphic to the TTL apart from the issues in 1.2.
- **No `prefLabel` duplicates** (S14 holds), even case-insensitively. No `exactMatch`/`broadMatch` or `closeMatch`/`broadMatch` clash on the same pair (S46-style disjointness holds).
- STW IRIs (`http://zbw.eu/stw/descriptor/NNNNN-N`, 610/610 well-formed) and AAT IRIs (`http://vocab.getty.edu/aat/300NNNNNN`, 923/923 well-formed) are canonical.

### 1.2 Defects
| # | Defect | Evidence | Sev |
|---|---|---|---|
| R1 | **All AGROVOC IRIs double-prefixed** | `P8061` values already carry `c_` (e.g. `"agrovoc_ids": ["c_1162"]`), and the exporter prepends `c_` again: [export L128/L130](file:///home/jic823/Documents/open_empire/human_trade/scripts/export_layer1_skos_and_report.py#L126-L130). The same bug is in the JSONL `agrovoc_uris` ([ground_commodities_v2 L782](file:///home/jic823/Documents/open_empire/human_trade/scripts/ground_commodities_v2.py#L780-L783)). Result: `htc:0002 skos:closeMatch agrovoc:c_c_1162`. **253/253 broken.** | P0 |
| R2 | **IDs are positional, not persistent** | `cid = f"htc:{idx:04d}"` comes from the row order of `commodities.tsv` ([ground_layer1_entities L477–481](file:///home/jic823/Documents/open_empire/human_trade/scripts/ground_layer1_entities.py#L477-L481)). I verified that all 2,066 concepts are strictly ordered by descending `total_rows`. Any re-transcription or extra ledger changes the counts and **reshuffles every IRI**. That is fatal for a published LOD vocabulary. | P0 |
| R3 | No `skos:hasTopConcept` / `skos:topConceptOf` / `skos:broader` | `hasTopConcept=0`, `topConceptOf=0`, `broader=0`. qSKOS would flag all 2,066 as orphans ("missing top concepts", "unconnected concept"). | P1 |
| R4 | `exactMatch` transitivity collapses processing states | 19 Wikidata QIDs are the `exactMatch` target of 2+ htc concepts (43 concepts). Because SKOS `exactMatch` is transitive, these entail that the htc concepts are exact matches of each other. Examples: `htc:0430` *Brimstone* = `htc:1276` *Brimstone Unrefined* = `htc:1593` *Brimstone Refined* (all `wd:Q682`); `htc:0293` *Mackerel Pickled* = `htc:0802` *Mackerel Fresh* (`Q8064278`); `htc:0071` *Furs Unenumerated Undressed* = `htc:0144` *…Dressed* (`Q197204`); `htc:0021` *Wool* = `htc:0050` *Wool Sheep and Lambs*. Also, 52 `exactMatch` concepts carry a non-raw `processing_state`. | P0 |
| R5 | JSON-LD drops taxon names silently | `oe:sourceTaxon` objects contain `"taxon_name"`/`"col_id"` keys that are not in `@context` ([export L120–124](file:///home/jic823/Documents/open_empire/human_trade/scripts/export_layer1_skos_and_report.py#L117-L124)). JSON-LD processors drop undefined terms, so no taxon-name triples come out (confirmed: the JSON-LD graph has the same triple count as the TTL minus one). | P1 |
| R6 | Scheme `dcterms:description` only in TTL | Missing from the JSON-LD scheme node (export L50–56). The two serializations are therefore not equivalent. | P2 |
| R7 | `skos:altLabel` misused for broader 1866 terms | 170 altLabels come from `skos_1866_bridge.prefLabel` ([export L82–84](file:///home/jic823/Documents/open_empire/human_trade/scripts/export_layer1_skos_and_report.py#L82-L84)). Many are **broader concepts, not synonyms**: `"fish"@en` on `htc:0183` *Herring Pickled*, `0038`, `0152`, `0197`, `0202`, `0221`, `0324`; `"hide"@en` on 10 different hide states (`0020`, `0023`, `0026`, `0053`, `0060`, `0112`, `0200`…); `"teeth"` on `0224` *Ivory…*; `"skins"` on `0174` *Skins - Furs - Pelts Bear*; `"carmine"` on `0118` *Cochineal*. | P1 |
| R8 | `dcterms:source` describes the *mapping*, not the concept | `htc:0130 dcterms:source "ceylon_spine:taxon_wd.jsonl"` says the concept came from a grounding file. It should say the concept came from a customs ledger. The value is a plain literal, `prov:` is declared but never used, and there is no `prov:hadPrimarySource` to the printed series. | P1 |
| R9 | Undeclared `oe:` vocabulary; facets as untyped literals | `oe:processingState "raw_unprocessed"`, `oe:sitcRollup "SITC_04_Cereals"`, etc. have no RDFS/OWL declarations, no ranges, and no facet concept schemes. The JSON field is called `skos_broadMatch_sitc` but it is emitted as a literal, with no `skos:broadMatch` to any SITC resource. | P1 |
| R10 | Thin scheme metadata | No `dcterms:created/modified`, licence, creator/publisher, `owl:versionInfo`, or `skos:notation` on concepts. | P2 |
| R11 | Two normalized near-duplicate headings | `htc:0553` *Cordage Twine and Cable Yarn* / `htc:1065` *Cordage, Twine, and Cable Yarn*; `htc:1080` / `htc:1460` *Stone, ornamental, granite, marble, &c(.), unwrought*. Keep both, since they are verbatim, but link them to a common broader concept. | P2 |
| R12 | RDF/XML-unsafe local names | `htc:0001` cannot be a QName in RDF/XML. This is harmless for Turtle/JSON-LD, but use full IRIs if RDF/XML is ever produced. | P2 |

---

## 2. Empirical Audit of Grounded Mappings (all 1,174 inspected)

### 2.1 Root causes in the matcher (code)
1. **Label-only lookup with no type constraint.** `query_wikidata_commodities` matches `lower(label_en) IN terms`. It fetches `instance_of` ([L568](file:///home/jic823/Documents/open_empire/human_trade/scripts/ground_commodities_v2.py#L547-L571)) but `pick_best_wd_commodity` never uses it. Candidates are filtered only by description regexes, and the "good" regex accepts words like *drink, food, product, species, plant, tool, rope, medium for recording*, so homonyms get through. Ties go to sitelinks.
2. **`grounded_exact`/`grounded_substance_head` from `ceylon/spine` are never re-checked** ([L676](file:///home/jic823/Documents/open_empire/human_trade/scripts/ground_commodities_v2.py#L674-L677)). Errors such as *Plumbago*→plant genus therefore persist, even though the v2 `CUSTOMS_TERM_MAP` maps `plumbago`→`graphite`.
3. **The prefix rule runs before the curated 1866 label and demotes `broadMatch` to `closeMatch`** ([L501–511](file:///home/jic823/Documents/open_empire/human_trade/scripts/ground_commodities_v2.py#L501-L511)). Adding qualifiers makes a heading *narrower*, so the right relation to the generic target is `broadMatch`. The code does the opposite. One- or two-token prefixes (`fish`, `cotton`, `oil seed`, `iron`) also override the 1866 bridge: `htc:0367` *Cotton Seeds* has bridge "Cotton seed" but is mapped to cotton fibre, and `htc:0323` *Oil Seed Cakes* has bridge "Oil Seed Cake" but is mapped to vegetable oil.
4. **`substance_head` splits on `-`, `(`, `:` and ` for `** ([ground_layer1_entities L458](file:///home/jic823/Documents/open_empire/human_trade/scripts/ground_layer1_entities.py#L456-L461)). That breaks intra-word hyphens in 10 headings (495 rows): *Cocoa-nut Oil*→"Cocoa", *Coco-nut Oil*→"Coco", *Gold-bearing Quartz*→"Gold", *Chicory Raw or Kiln-Dried*→"Chicory or Kiln", *Metal Old … re-manufactured*→"Metal Old fit only to be re".

### 2.2 P0 — wrong entity (homonym false positives): 40 concepts, ~1,920 rows
| htc | Printed heading | rows | Rel | QID → label :: description (as stored) | Should be |
|---|---|---:|---|---|---|
| 0130 | Plumbago | 253 | exact (EX) | Q2039140 *Plumbago* :: genus of plants | graphite (`Q5309`, already used for `htc:1547`) |
| 0207 | Tar | 171 | exact | Q3338507 *tar* :: particulate matter produced by the burning of tobacco | wood/coal tar (naval-stores product) |
| 0241 | Clover Seeds | 155 | close | Q5135861 *Clover* :: manufacturer and marketer of dairy products… | clover seed (crop) |
| 0278, 0553, 0735, 0988, 1058, 1065, 1443, 1494, 1528, 1595, 1598 | Cordage … (11 headings) | 363 | close/exact | Q1156047 *rope* :: data structure representing a long string… | rope/cordage (textile) |
| 0344 | Toys | 111 | exact | Q6516633 *Toy* :: Swedish chewing gum | toy |
| 0369, 1714 | Clocks… | 108 | close | Q14908739 *CLOCK* :: protein-coding gene in Homo sapiens | clock (timepiece) |
| 0436 | Castor | 85 | close | Q48970 *Castor* :: family of solid-fuel rocket stages | castoreum or castor beans (check the series) |
| 0459 | Pictures | 80 | exact | Q96742522 *Pictures* :: 2019 board game | picture/print |
| 0686 | Watches | 49 | close | Q1934809 *watch* :: GNU command-line tool | watch (timepiece) |
| 0727 | Hoop | 44 | exact | Q2553153 *hoop* :: apparatus in rhythmic gymnastics | barrel hoop / hoop iron |
| 0804, 1680 | Matches… | 45 | exact/close | Q6786204 *Match* :: soft drink | match (fire-lighting) |
| 0922 | Curios | 30 | exact | Q5676387 *Curio* :: genus of plants | curio/curiosity |
| 0540, 1103 | Cement… | 88 | exact | Q189310 *cement* :: chemical precipitate between grains in a rock | building cement |
| 1348 | Leeches | 13 | exact | Q1640028 *leech* :: rope in the side of a sail | medicinal leech (animal) |
| 1451 | Clay unmanufactured | 11 | exact | Q1627382 *Clay* :: species of moth; **also emitted as `oe:sourceTaxon` "Mythimna ferrago"** | clay (material) |
| 1777 | Beads Unenumerated | 5 | close | Q4876048 *bead* :: woodworking decorative treatment | bead (ornament) |
| 1843 | Shot | 4 | exact | Q7502422 *shot* :: fabric… (+inherited AAT 300265783) | lead shot (ammunition) |
| 1908 | Blue | 3 | exact | Q15178353 *Blue* :: soft drink | laundry blue / pigment |
| 1915 | Veneers | 3 | exact | Q1686140 *veneer* :: thin ceramic or resin coating for the teeth | wood veneer |
| 2010 | Bugles | 1 | exact | Q4843841 *bugles* :: corn snack food from General Mills | bugle beads (glass) |
| 2024 | Type | 1 | exact | Q3707858 *type* :: anchoring point of a taxonomic name | printing type |
| 1831 | Manna | 4 | close | Q241156 *manna* :: edible substance described in the Bible | manna (ash exudate, drug) |
| 0517 | Bones except Whalebone for Manufacturing | 70 | close | Q881659 *bone* :: strip of rigid material used to stiffen corsets (i.e. the *excluded* whalebone sense; +AAT 300253790) | bone (animal material) |
| 0337 | Castings Unenumerated | 113 | close | Q496098 *casting* :: manufacturing process… | cast-metal articles |
| 0420 | Sponge | 88 | close | Q1210980 *sponge* :: cleaning tool made from soft and porous usually synthetic… | natural sponge (marine animal product) |
| 1576 | Cinders | 9 | close | Q16742056 *Cinder* :: type of igneous rock | coal cinders |
| 1267 | Lead Black | 15 | close | Q708 *lead* (element) | "black lead" = graphite |

### 2.3 P0 — wrong substance or wrong sense: ~50 concepts, ~3,400 rows
| htc | Printed heading | rows | Current anchor | Problem |
|---|---|---:|---|---|
| 0625 | Cocoa-nut Oil | 57 | > Q42385 *Theobroma cacao* (+AGROVOC c_7713, sourceTaxon cacao) | **coconut oil, not cacao.** Caused by the head-split bug. |
| 1470, 1565 | Coco-nut Oil Unrefined / Refined | 20 | > Q13187 *Cocos nucifera* | oil mapped to the palm species (also domain `other`) |
| 0157, 0286, 0449, 0547, 0786, 1655, 1800, 1861, 1918 | Fish Oil; …Cod; …Seal; …Unenumerated; …Whale; …Herring; …Refined Cod; …Porpoise; …Dog | 556 | ~ Q600396 *fish as food* | oil ≠ fish; seal, whale and porpoise are not fish. Meanwhile `htc:0250` *Train or Blubber (Whale Oils)* (150 rows) sits ungrounded. |
| 0323, 0447, 0741, 1026, 1033, 1091 | Oil Seed Cake(s) … | 317 | ~ Q4739805 *vegetable oil* (+AAT 300014258) | cake is the residue, the opposite of the oil. Use `Q513720` *press cake* (already used for `htc:0166`). |
| 0367 / 1743, 1813 | Cotton Seeds / Cotton Seed Oil (Un)Refined | 103 / 11 | ~ Q11457 *cotton* (fibre) | oilseed/oil mapped to the fibre; `0367` is also in domain `fibres_textiles` |
| 0308 | Wool Cotton | 124 | ~ Q42329 *wool* | the heading means cotton wool, i.e. raw cotton |
| 0133 | Timber Walnut | 250 | ~ Q208021 *walnut* :: edible seed | **edible nut vs timber** |
| 0092, 0441, 1005 | Sheep's Pelts; Sheep Skins; Sheep and Lamb Skins | 454 | ~ Q7368 *sheep* (live animal; +AGROVOC/STW/AAT for sheep) | **pelt vs live animal** |
| 0127 / 0513 / 2030 | Tongues; Tongues and Sounds; Cod Sounds | 257/70/1 | > / ~ Q1558649 *beef tongue*; ~ Q13194939 *cod* | In Canadian fishery series these are cod tongues and swim bladders (sounds). `broadMatch` to "beef tongue" is also the wrong direction (beef tongue is *narrower*). |
| 0109 | Shumach | 286 | ~ Q16131953 *sumac* :: spice; dried fruit of Rhus coriaria | customs sumach is a tanning material (leaves), not the spice |
| 0118 | Cochineal | 269 | = Q320617 *carmine* :: pigment | the insect dyestuff ≠ the derived lake pigment; at most `relatedMatch` |
| 1329, 1365, 1623 | Soda Bicarbonate / Caustic / Sulphate | 35 | ~ Q190227 *sodium carbonate* | three different compounds |
| 0257, 1220 | Salt; Salt Rock and White | 164 | =/~ Q12370 *salt* :: "mineral ionic substance composed of cations and anions" | stored description reads as the generic chemistry class; check for the sodium chloride / table salt item |
| 0458 | Furs or Skins of Fish | 81 | ~ fur | not fur; also domain `food_animal` |
| 0868, 1100, 1164, 1407, 1469, 1621, 1472 / 0550, 0711, 0814, 1361 | (Paper Making Materials) Pulp of Wood …; Paper Making Materials … | ~276 | ~ Q11472 *paper* | input material mapped to the end product |
| 0398, 1312 / 0884 / 0709 | Barley Meal (and Flour) / Rye meal / Maize or Indian Corn Meal | 184 | ~ Hordeum vulgare / Secale cereale / Q11575 maize (species of grass) | flour mapped to the plant species |
| 0187 | Wheat Other Descriptions including Shredded Wheat and Semolina | 186 | ~ Q15645384 wheat | processed products mapped to the grain |
| 0756, 1261 | Coal Tar Dyes Unenumerated; Coal Products not Dyes | 58 | ~ Q24489 coal | derivatives mapped to the fuel |

### 2.4 Systematic relation-type errors (each needs a rule fix)
| Class | Scale | Examples | Fix |
|---|---|---|---|
| **Container vs stave (part ≠ kind)** | 9 concepts, 1,570 rows | `0039` *Staves - Other*, `0059` *Standard Staves*, `0089`, `0217`, `1270`, `1344`, `1383`, `2042`, `2043` → `broadMatch`/`closeMatch` Q10289 *barrel*, plus inherited AAT `300206700`, `300194514` | A stave is a *component* of a barrel, not a narrower barrel. Use `relatedMatch`, or ground to a stave item. Remove the inherited AAT `closeMatch`. |
| **Taxon anchored as if it were the commodity** | 76 anchors, 10,560 rows (33 `exactMatch`) | `0003` Oats = Avena sativa; `0006` Peas = Pisum sativum; `0007` Barley; `0095` Rye; `0138` Cocoa = *Theobroma cacao* (tree); `0163` Apples = *Malus* (genus); `0474` Figs = *Ficus*; `0600` Walnuts = *Juglans*; `0492` Birch = *Betula*; `0029`/`0813`/`1966` oak = *Quercus*; `0400` Sarsaparilla = *Smilax regelii* (one species); `1584` Turkey = *Meleagris*; `2028` Bear = *Ursidae*; `1099` Rabbits = Leporidae | Put the taxon in `oe:sourceTaxon` only. Anchor `skos:*Match` to the commodity/food/material item. Never use `exactMatch` to a taxon. |
| **Same substance, inconsistent QIDs** | — | apples `Q104819` (*Malus*) vs `Q89`; maize `Q11575` vs `Q25618328`; salmon `Q188879` (*Atlantic* salmon, for Canadian series that include Pacific fish) vs `Q2796766`; birch `Q25243` vs `Q865564`; figs `Q59798` vs `Q2746643`; plumbago `Q2039140` vs `Q5309`; iron ore `Q677` (element: `0196`, `1675`) vs `Q191552` (`0534`); cocoa tree vs `Q208008` | Pick one canonical item per substance in a reviewed lookup table and apply it everywhere. |
| **Ores mapped to elements** | 9 concepts | `0196` Iron Ore Including Chrome, `1675`, `0258` Lead Ore, `0299` Manganese Ore, `0427`/`0886` Zinc Ore, `0457` Tin Ore, `0911` Antimony Ore → element | Ore items exist and are already used (`Q63219186` copper ore, `Q4417415` silver ore, `Q191552` iron ore, `Q12110813` cobalt ore). |
| **Manufactured articles anchored to raw material** | 167 concepts, 7,848 rows (155 `closeMatch`) | 31 *Silk Manufactures…* → silk fibre; 21 *Cotton Manufactures…* → cotton fibre; *Woollen Manufactures…* → wool fibre; 46 iron headings → **iron (element)** incl. `0238` *Iron Stoves*, `0879` *Iron Nails…*, `1174` *Iron Anchors…*; `0105`/`0115` *Leather Manufactures Boots…/Gloves* → leather; `0102`/`0108` *Wood Manufactures* → wood | Use `skos:relatedMatch` plus an explicit `oe:madeOfMaterial wd:…`. Reserve `closeMatch`/`broadMatch` for product-class targets. |
| **Prefix rule: `closeMatch` where `broadMatch` is meant** | 638 `grounded_wikidata_slim` concepts, 30,927 rows | 39 wine headings ~ wine; 39 *Skins Furs Pelts <species>* ~ fur (`Q197204`, whose stored description is the *biological hair coat*); `0231` *Seeds Rape* ~ generic seed; `0183` *Herring Pickled* ~ fish as food | Invert the rule: more tokens or a processing state means `broadMatch`. |
| **Compound headings collapsed to one component** | — | `0171` *Beans and Peas* ~ bean; `0385` *Lemons and Oranges* ~ lemon; `0206` *Cutch and Gambier* ~ catechu; `0030` *Tallow and Stearine* ~ tallow; `0240` *Masts and Spars* ~ mast; `0100` *Furs and skins* ~ fur. Only 3 headings use the compound tier. | Detect `X and Y` / `X, Y and Z` before single-term lookup. |

### 2.5 What is right (abbreviated)
Most high-frequency staple foods are correctly anchored: `0001` Wheat, `0002` Butter, `0009` Flour, `0011` Cheese, `0014` Eggs, `0015` Caoutchouc, `0017` Sheep (live), `0018` Pork, `0021` Wool, `0022` Tallow, `0024` Bacon, `0025` Lard, `0027` Horned Cattle, `0031` Beef, `0036` Bran, `0040` Potatoes, `0044` Firewood, `0056` Hops, `0068` Whiskey, `0076` Coffee, `0081` Tea, `0094` Soap, `0111` Coal, `0164` Rice, `0172` Olive Oil, `0181` Palm Oil, `0185` Gum Arabic, `0285` Opium, `0328` Saltpetre, `0342` Iron Pig, `0491` Silver Ore, `0534` Iron Ore Other Sorts, `0805` Vegetable Ivory, `1269` Buffalo Robes, `1547` Plumbago crude → graphite. The 4 customs residuals are handled correctly.

**Estimated precision.** About 90/1,174 (7.7%) grounded concepts point at the wrong entity or substance. About 850 more (~72%) have a relation strength that overstates the match. By rows, roughly 5,300 rows of the 116,586 "grounded" rows are outright wrong. The headline "76.4% grounded" should be reported alongside a relation-weighted figure.

---

## 3. Facet, SITC and Theodoridis (2018) Bucket Accuracy

### 3.1 Architecture
`classify_commodity_facets` ([ground_layer1_entities L415–461](file:///home/jic823/Documents/open_empire/human_trade/scripts/ground_layer1_entities.py#L415-L461)) is **first-match-wins regex** over the raw heading. I verified that `theodoridis_category` and `sitcRollup` are **1:1 functions of `ghost_acres_domain`** (11 domains ↔ 11 (bucket, SITC) pairs). The three facets are therefore not independent evidence, and every domain error is tripled.

### 3.2 `processing_state` (1,038/2,066 = 50% `unspecified`)
| Bug (rule order / regex) | Concepts / rows | Examples |
|---|---|---|
| `live` (matches *sheep, lambs, pigs, horses…*) fires before skins/wool/leather | 13 / 1,724 | `0034` *Skins Furs Pelts Sheep Undressed*, `0050` *Wool Sheep and Lambs*, `0092` *Sheep's Pelts*, `0287` *…Sheep Tanned Tawed or Dressed*, `1302` *Leather Undressed Sheep Skins*, and **`1887` *Copper, black or coarse, … copper in pigs* = `live`** |
| `dressed_tanned` (matches *dressed*) applied to timber and fibre | 9 / 806 | `0089` *Wood and Timber Staves - Sawn or Split, Planed or Dressed*, `0314` *…Fir…*, `0379` *…Oak…*; `0530` *Flax Dressed or Undressed* |
| `sawn_milled` (matches *split, ground, meal, flour*) conflates sawmilling and grain milling and catches split peas and ground minerals | 13 / 917 outside timber/grain | `0046` *Peas not fresh other than Split Peas* (518), `0272` *Ground Plaster*, `0811` *Chicory Roasted or Ground*, `1013` *Mica Ground* |
| raw rule (*cotton, wool, hides…*) fires before `manufactured` | 53 / 1,814 | `0159` *Cotton Manufactures* = `raw_unprocessed`; `0480` *…Piece Goods Printed*; `0494` *Cotton Yarn*; `0363` *Hides Varnished, Japanned or Enamelled* = raw; `0472` *Furs manufactured* = raw |
| `wet_salted`/`dried_cured` on wood pulp | 4 | `1407` *Pulp of Wood Mechanical Wet* = `wet_salted` |
| `refined_extract` for dairy, oil cake and oilseed | — | `0002` Butter, `0011` Cheese, `0166` Oil Cake, `1504` Oil Seed |

### 3.3 `ghost_acres_domain` / Theodoridis / SITC
| Bug | Concepts / rows | Examples |
|---|---|---|
| Animal terms (*sheep, cattle, horses*) are tested before hides/wool, so skins and wool become `food_animal` → `animals_and_animal_products` | 12 / 1,800 | as above, plus `0458` *Furs or Skins of Fish* |
| Fibre, metal and leather rules are tested before `manufactured_goods`, so manufactures become Theodoridis `raw_materials` | 76 / 2,150 textiles; 82 / 3,030 metals; 17 / 1,678 leather | `0265` *Linen Manufactures*, 31 silk manufactures, `0238` *Iron Stoves*, `0270` *Iron Manufactures Unenumerated*, `0105` *Leather Manufactures Boots and Shoes*. **`manufactured_articles` is under-counted by up to ~6.8k rows** (regex estimate; the metals figure includes some semi-manufactures such as pig/sheet lead). |
| Substring collisions | — | `1677` *Iron and Steel Bolts and Nuts* → `food_colonial_grocery` (*nuts*); `1227` *Soda Ash* → `timber_forestry` (*ash*); `1461` *Cocoa Butter* → `food_animal` (*butter*); `0473`/`1653` *Rags Woollen … Manure* → `drugs_botanicals_chemicals` (*manure*); `1528` *Cordage and Cables not of Iron* → minerals (*iron*) |
| `SITC_*` values are composite labels, not SITC Rev. 4 codes | all | `SITC_26_65_Textile_Fibres` merges raw fibres (26) with fabrics (65); `SITC_4_22` absorbs soap, candles, rosin and turpentine; **`SITC_9_Unclassified` reuses the real SITC section 9 label for classifier failures** |

### 3.4 Why `other`/`unclassified` holds 27,868 rows (641 concepts)
It is mostly **vocabulary gaps in `MACRO_RULES`**, not real ambiguity:
- **Word-boundary and plural misses**: `\bbiscuit\b` misses *Biscuits* (`0114`, 275); *Meats* (`0368`), *Grains* (`0421`), *Coals* (`0661`), *Seeds* (no seed term at all: `0012` 956 rows, `0231`, `0246`, `0304`); *Bark For Tanners* misses `bark for tanner\b` (`0041`, 540).
- **Missing customs terms**: lumber/logs/saw logs/deal ends/lathwood/knees/shooks/handspikes (`0119`, `0067`, `0210`, `0211`, `0298`, `0404`…); hay/straw (`0061` 455, `0167`); vegetables/pears/cranberries (`0080` 377, `0085`, `0086`); fishery products (codfish `0123` 261, lobsters `0101` 319, oysters, mackerel `0293`, halibut, venison); gin, hogs, mares, geldings, stallions; pearl ashes (`0136`, `0150`, the *key* Canadian forest-clearance product); arrowroot, sago, tapioca, buckwheat (`0463`); whalebone, isinglass, ivory.
- **Spelling variants**: *Shumach* (`0109`, 286), *Myrabolans* (`0180`, 191), *Orchal*.
- **Residuals hiding a domain**: `0019` *Other woods* (840 rows) is a timber residual.

**Simulation** (scratch): adding about 200 terms (plural-tolerant) moves **~20,850 of 27,868 rows (~75%)**: timber 5,210; grocery 3,109; fodder/seeds 2,758; fish/animal 2,590; minerals 1,998; manufactures 1,948; drugs 1,344; tannins 1,275; grain 617. What remains (~7,000 rows / 288 concepts) is mostly real residuals (`0010` *Other Articles* 1,120; *Goods Unenumerated…*; *Value of Articles Imported by Parcel Post*).

### 3.5 Scholarly notes for the ghost-acres argument
- **Marine vs terrestrial.** Fish, whale/seal/porpoise oil, sealskins, isinglass, sounds and whalebone sit in land-based buckets. Add an `oe:landBasis` facet (`terrestrial_crop`/`pasture`/`forest`/`marine`/`mineral`) so marine "ghost acres" are not counted as hectares.
- **Fodder** (hay, straw, oil cake, bran) is the hinge between imported feed and domestic livestock. It should be its own domain, not `other`.
- **Draft animals.** Horses (`0005`, 1,285 rows) are `food_animal`; consider separating draft from food animals.
- **Aggregate "Total" headings**: `0103` *Sugar Unrefined Total* (304), `0121` *Wine Total of all Kinds* (265), `0867`, `1125`. Flag them `oe:isAggregate true` so quantity sums don't double-count.
- Row sum in the JSONL is 152,625, while the brief says 153,579 (Δ 954). Reconcile with blank or unparseable headings.

---

## 4. External LOD URI and Mapping Hygiene
| # | Finding | Evidence | Sev |
|---|---|---|---|
| L1 | AGROVOC `c_c_` double prefix | 253/253 IRIs, in both `.ttl`/`.jsonld` and JSONL `agrovoc_uris` | P0 |
| L2 | Non-numeric AGROVOC id `c_0d5d04c4` | on 6 madder concepts (`0242`, `0302`, `0524`, `0634`, `0986`, `1458`) via `Q163641` *Rubia tinctorum*. Verify that it resolves. It is also a *taxon* concept attached to dyestuff headings. | P1 |
| L3 | **Relation strength not composed** | AAT/AGROVOC are always `closeMatch` ([export L127, L138](file:///home/jic823/Documents/open_empire/human_trade/scripts/export_layer1_skos_and_report.py#L126-L141)) even when the Wikidata link is `broadMatch` (127 concepts) or a too-strong `closeMatch` (635). Rule: the inherited relation should be no stronger than the weakest link (`exact∘X = X`, `broad∘exact = broad`, anything with `related` = `related`). | P0 |
| L4 | STW always `broadMatch` | including 65 concepts whose Wikidata anchor is `exactMatch` (e.g. `htc:0001` Wheat → `stw:14098-1`). This is conservative but under-asserts. Compose it the same way as L3. | P2 |
| L5 | **LOD inherited from wrong anchors** | `1843` Shot → AAT `300265783` (fabric); `0420` Sponge → AAT `300386524`, `300011854`; `0337` Castings → AAT `300053104`, `300054038` (process); staves → barrel AAT; `0092`/`0441` sheep pelts → AGROVOC `c_7030`, STW `14143-1`, AAT `300404156` (live sheep); `0625` → AGROVOC `c_7713` (cacao); oil-seed cake → AAT `300014258`; `0517` → AAT `300253790`. Fixing the anchors fixes these. | P0 |
| L6 | Compound headings | LOD and taxa come only from `component_substances[0]`. `htc:0013` *Barley and Rye* has `oe:sourceTaxon` barley only, and `htc:0104` gets STW only for beer. | P2 |
| L7 | "Biological source taxa: 467 concepts" overstated | 94 concepts (16,610 rows) have no source taxon other than the anchor itself (`is_taxon`). These include the moth (`1451`), *Curio* (`0922`) and *Plumbago* (`0130`) false positives. 130 entries have no `relation` key and many `col_id` are empty. | P1 |
| L8 | Docstring drift | The script header lists `P4112` for AGROVOC, but the code reads `P8061`. Fix the docstring. | P2 |

---

## 5. Internal Structure, Hierarchy and Provenance

1. **Mint an intermediate "substance concept" tier (Layer A′)** and connect it with `skos:broader`/`narrower`. 296 heading families with 2+ members cover 1,626 concepts. The biggest are *iron* (46), *skins furs pelts* (39), *wine* (39), *wood* (38), *timber* (36), *silk manufactures* (31), *paper* (27), *hides* (26), *fish* (21), *sugar* (21), *cotton manufactures* (21). Example: `htc:sub/hides` ⟵broader⟵ `0020` Hides Raw Dry, `0023`, `0026`, `0053`, `0112`, `0200`, `0306`…, each keeping its `processing_state`. Then put **one** reviewed Layer-B mapping on the substance concept and let the verbatim headings take `broadMatch`. That removes the 19 `exactMatch` collapses and most of the prefix-rule errors.
2. **Use the 1866 `SKOS_from_Custom_Records.xlsx` hierarchy properly.** 303 concepts (51,507 rows) carry a bridge. 54 distinct `broaderConcept` values (e.g. *Corn*, *Fruit*, *Seafood*, *Chemical*, *Animal part*, *Forest Product*, *Hydrocarbon*) give ready-made top concepts. The `state` and `sourceOf` columns (*tanned, dressed, wet, tawed, curried, varnished*; *Oil, Dye Stuff, Tanning*) can seed controlled facet vocabularies. Mint these as a separate `htc1866:` scheme. Link with `skos:broader` (or `broadMatch` across schemes), **not** `altLabel` (R7). Let the curated 1866 concept outrank the one-token prefix rule.
3. **Top concepts.** Declare the 11 domains, or the 1866 top concepts, as `skos:hasTopConcept`/`topConceptOf`.
4. **Facet schemes.** Mint `oe:processingState/raw_unprocessed`, etc. as `skos:Concept`s in their own schemes and use object properties. Separate `sawn` from `milled_ground`.
5. **Provenance.** Per concept: `prov:hadPrimarySource` → the customs series (British Annual Statements / Canadian Trade and Navigation Returns), `oe:firstAttested`/`oe:lastAttested` years, and `oe:series`. Per mapping: reify each Layer-B link (e.g. SSSOM-style rows, or RDF-star) with `mapping_justification`, `matched_via_term`, authority (`ceylon_spine` vs `wikidata_slim:2026-11-09`), confidence and reviewer. This makes the "reversible" claim operational.
6. **Persistent IDs.** Freeze an ID registry keyed on the verbatim heading (e.g. normalized-label hash → htc number). Never re-derive IDs from rank. Add `skos:notation "0001"`.

---

## 6. Prioritized Fix List

### P0 — must fix before publication (bugs, wrong facts, broken RDF)
1. **AGROVOC IRIs**: strip the existing `c_` (`agrovoc:{x}` if `x.startswith("c_")`) in both the exporter (L128/L130) and `ground_commodities_v2.py` L782. Re-check that `c_0d5d04c4` resolves. *(253 IRIs)*
2. **Persistent IDs**: replace positional `htc:{idx}` with a frozen registry, and publish a crosswalk from the current IDs.
3. **Remove or repair the ~90 wrong-entity and wrong-substance anchors** in §2.2–2.3 (headline cases: `0130` Plumbago, `0207` Tar, `0241` Clover Seeds, 11 Cordage, `0344` Toys, `0369` Clocks, `0436` Castor, `0459` Pictures, `0686` Watches, `0804` Matches, `0540` Cement, `1451` Clay→moth, `0625`/`1470`/`1565` coconut oil, 9 fish/marine oils, 6 oil-seed cakes, `0367` Cotton Seeds, `0133` Timber Walnut, `0092`/`0441`/`1005` sheep pelts, `0127`/`0513` tongues & sounds, `0109` Shumach, `0517` bones, `0420` Sponge, `1329`/`1365`/`1623` soda). Add the bad (term, QID) pairs to `name_rejections.jsonl`, and **re-validate the ceylon-derived EX/SH tiers** instead of skipping them (L676).
4. **Type-constrain the matcher**: use the `instance_of` it already fetches. Allow material/food/commodity/product classes, and reject genes, software, games, brands, soft drinks, taxa-as-anchor and geological processes. Swap the sitelinks tie-break for type plus a reviewed allowlist.
5. **Stop `exactMatch` collapsing processing states**: allow `exactMatch` only when the heading carries no state or qualifier and the target is the same kind (not a taxon). Otherwise use `broadMatch`. *(19 QIDs / 43 concepts collapsed; 52 state-bearing exactMatches)*
6. **Invert the prefix-rule demotion** (L509): extra tokens or a state mean `broadMatch`. Run the curated 1866 concept lookup *before* the 1–2-token prefix rule. *(638 concepts)*
7. **Compose external-LOD relations** with the Wikidata relation (L3), and drop LOD inherited from rejected anchors (L5).
8. **Fix staves→barrel** (part/whole) and **ores→elements** (use the existing ore items).
9. **Fix facet rule order**: (a) test skins/hides/wool/leather before `live` and the animal domain; (b) test `manufactures` before fibre/metal/leather raw rules; (c) make *dressed* context-dependent (timber vs leather vs fibre); (d) add word boundaries to avoid *nuts*/*ash*/*butter*/*manure*/*pigs* collisions; (e) stop splitting `substance_head` on intra-word hyphens. *(see §3 counts)*

### P1 — high-value modelling and coverage improvements
10. Expand `MACRO_RULES` with plural-tolerant terms, the missing customs vocabulary and spelling variants (§3.4). This removes ~75% of `other`. Add `fodder` and `marine` handling and an `oe:landBasis` facet. Flag `Total` headings as aggregates.
11. Decouple SITC from domain. Assign real SITC Rev. 4 section/division codes per concept as `skos:notation` or links to minted SITC concepts, and stop using SITC 9 for classifier failures. Derive the Theodoridis bucket from the corrected domain/state, not from the label.
12. Mint the substance tier and the 1866 scheme. Add `skos:broader`/`narrower` and `hasTopConcept`. Convert the 170 bridge altLabels to `broader` links.
13. Move taxa out of `skos:*Match` into `oe:sourceTaxon` only. Resolve the inconsistent QIDs for apple, maize, salmon, birch, fig, cocoa and plumbago through one reviewed canonical table.
14. Detect compound headings (`X and Y`) generally and emit per-component `relatedMatch` with per-component LOD and taxa.
15. Provenance: separate the mapping authority (`oe:mappingAuthority` or reified mapping) from the concept's `prov:hadPrimarySource` (the archival series). Publish an SSSOM mapping table alongside the SKOS.
16. Declare the `oe:` ontology (RDFS/OWL: domains, ranges, labels). Add `taxon_name`/`col_id` to the JSON-LD `@context`, or emit them as `rdfs:label` on the taxon node.
17. Ground the high-yield review-queue items: `0051` Machinery Manufactures (494), `0074` Hardware (391), `0075` Flaxseed and Linseed (384; the map already has `flax seed`), `0119` Saw Logs (268), `0123` Codfish… (261), `0136`/`0150` Pearl (and Pot) Ashes (472), `0137` Timber Elm (246; in the map but unmatched), `0250` Train or Blubber (150).

### P2 — polish
18. Add scheme metadata (licence, creator, `dcterms:created/modified`, `owl:versionInfo`) and the scheme description to the JSON-LD.
19. Add `skos:notation` to concepts. Link the near-duplicate headings (`0553`/`1065`, `1080`/`1460`) under a common broader concept.
20. Compose STW relations instead of fixed `broadMatch`. Fix the P4112/P8061 docstring drift. Reconcile the 152,625 vs 153,579 row totals.
21. Report grounding coverage as both "any link" and "relation-weighted/validated", and report taxa coverage without self-taxon cases.
22. Add a CI check: rdflib parse, qSKOS-style checks (orphans, S14, altLabel/prefLabel overlap, mapping clashes), an IRI pattern test for each external namespace, and a regression list of known false-positive QIDs.

---

### Appendix — Reproducibility
Scratch directory: `/home/jic823/.gemini/antigravity/brain/41056b04-ef96-4222-ad22-de3f9b4b83ae/scratch/`
- `regen_export.py` — the exporter's SKOS section, redirected to scratch → `regen_commodities_skos.ttl` (25,649 triples) and `regen_commodities_skos.jsonld` (25,648 triples)
- `grounded.tsv` — all 1,174 grounded concepts (id | rows | tier | heading | relation+QID+label::description | via-term | domain/state), sorted by rows
- No production files or scripts were modified. `/mnt/data/jic823/archival_corpus` was not touched.
