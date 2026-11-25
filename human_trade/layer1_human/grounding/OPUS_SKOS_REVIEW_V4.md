# v4 Final Verification — Layer-1 Commodity SKOS

*Reviewer: `skos-reviewer` · 2026-11-24 · Follows [OPUS_SKOS_REVIEW.md](OPUS_SKOS_REVIEW.md) and [OPUS_SKOS_REVIEW_V3.md](OPUS_SKOS_REVIEW_V3.md)*

**Method:**
- Parsed TTL and JSON-LD with rdflib 7.6.0.
- Ran the SKOS integrity suite: S13, S14, orphans, cycles, multi-parent, S27, `related` symmetry, mapping clashes, `exactMatch` uniqueness, and IRI patterns.
- Diffed every Wikidata anchor against v3. 303 anchors changed and I read all of them.
- Scanned all 1,218 anchor descriptions for homonym signals.
- Sampled 45 + 8 `skos:definition`s and read all 69 `skos:related` pairs and all 96 `altLabel`s.

## Verdict
**PASS on structure and RDF. Layer B is near-publishable: three small mechanical P0s remain.** The 4-tier hierarchy is valid SKOS. Structure is now the strongest part of the vocabulary.

## 1. Verified ✅
| Check | Result |
|---|---|
| Parse / equivalence | TTL **44,567** triples = JSON-LD **44,567**. **0 triples differ**; the ontology declarations now appear in both. |
| Persistent IDs | `htc_id_registry.tsv` is **byte-identical** to v3. |
| Hierarchy | 2,321 concepts (9 `sec_`, 44 `grp_`, 159 `sub_`, 2,066 `htc:`, plus `htc1866:`). 52 `hasTopConcept`/`topConceptOf`. **0 orphans, 0 cycles, 0 multi-parent.** Verbatim depth is 3 (1,055 concepts under a `sub_`) or 2 (1,011 directly under a `grp_`). |
| SKOS integrity | **S14: 0 duplicate prefLabels** (also case-insensitive, per scheme). **S13: 0.** S27: `related` is disjoint from `broaderTransitive` (0). `related` is fully symmetric. |
| Mappings | 0 `exactMatch` targets with more than one subject. 0 exact/broad, exact/related, close/broad, broad/related or broad/narrow clashes. All mapping triples come from SSSOM. |
| IRIs | 0 `c_c_`. **All AGROVOC IDs numeric.** STW, AAT and Wikidata IRIs all match canonical patterns. No malformed IRIs. |
| Provenance | `NULL and other errors` removed. `oe:dictionarySource` gives 821 resolvable archive.org / gutenberg IRIs. |
| v3 P0 fixes | Horses → `broadMatch` livestock `Q103459`. Horns → `Q82025`. Pitch → `Q840692`. Mace → spice `Q1882876`. Down → down feather. Wedges → tool. Bass → fish. Pickets/Billets → wood. Junk → oakum. Cement copper → copper. Cannon → gun carriage `Q1163915`. Electrical wires → electrical cable. Sponge, Bear, Blue and Coral are left unmatched rather than mis-matched. Pig iron/lead → `minerals_metals_energy` / `smelted_semi` / SITC 67–68. Butter → `exactMatch`. |

## 2. Remaining issues

### P0 — mechanical, fix before publishing
1. **`htc:0511` *Mares* (71 rows) → `skos:exactMatch` `Q3290341` "large circular plain on the Moon and Mars".** This is the last clear homonym. v3 had the correct horse sense `Q1104034`. Add it to `AUDIT_REJECTIONS`, or let the equine branch fall through to livestock like *Horses*.
2. **About 16 of the 69 `skos:related` pairs are nonsense**, and they are asserted symmetrically:
   - *Tallow and Stearine* ↔ eight *Spirits…* headings (`0077`, `0110`, `0612`, `0697`, `0767`, `1221`…)
   - *Maize* ↔ *Mace* (`0049` and `1373` ↔ `0980`)
   - *Starch* ↔ *Brimstone*; *Starch* ↔ *Chesnuts*
   - *Opium* ↔ *Fruit*; *Ultramarine* ↔ *Axes*; *Blue* ↔ *Benjamin*; *Oil Unenumerated* ↔ *Oil Cake*

   The pattern looks like dictionary "see also" or fuzzy-match spill-over. Keep only pairs justified by co-membership, `combinesConcept`, or a curated list.
3. **`htc:1165` *Scientific Instruments other than Electrical* → electrical cable.** The heading literally excludes that sense. More broadly, *Electrical Goods and Apparatus* (`1556`, `1566`), *Electrical Ware Door Fittings* (`1693`) and *Machinery … Electrical* (`1516`) are all mapped to "electrical cable". That is too specific; use `broadMatch` to an electrical-equipment class, or leave them unmatched.

### P1
1. **Wrong-sense `skos:definition`s.** About 6–7 of the 45 sampled (~15%) define a homonym, which projects to ~70 of 466:
   - `0080` *Vegetables* = vegetable-ivory (Phytelephas) entry
   - `0503` *Gin* = "Chinese name for the eatty; the machine by which … ore are raised from the pit"
   - `0127` *Tongues* = "the clapper of a bell…"
   - `1288` *Paper Unenumerated* = "American term for a note or draft"
   - `1768` *Bark* = "BARQUE, a square sterned ship"
   - `1339` *Paint* = cosmetic face-paint (Schminke/Fard)
   - `0337` *Castings* = the founding process
   - `0124` *Oil Unenumerated* = "See OIL-CAKE"
   - Cross-reference stubs such as `0983` "See LAC" and `1644` "see MAPLE HONEY"; `0612` is customs-duty text, not a definition.

   **Fix:** emit the quotation as `oe:dictionaryEntry` (headword + quote + source) and promote it to `skos:definition` only after a sense check, e.g. anchor-label or headword agreement. Drop "See X" stubs.
2. **Recall regression from the positive gate.** 162 v3 anchors were dropped (9,575 rows). About 150 of them (~9,200 rows) were *correct*:
   - dye / madder / indigo / cochineal: ~2,460 rows (`0054`, `0062`, `0088`, `0096`, `0118`, `0242`, `0302`…)
   - the whole sugar family: 11 headings, ~1,090 rows (`0360` *Sugar* `Q11002`, `0103`, `0284`, `0770`…)
   - footwear 772, machinery 606, hops 477, yarn 475, natural gums 401, galls 400, masts 273
   - guano, baleen, tin ore, arrowroot, sago, tapioca, geldings, calves, stallions, pearls, mica, mustard, rifles

   Grounded coverage fell from 1,309 to 1,218 concepts (121,052 → 115,505 rows), and `other` rose to 7,443 rows (4.9%). **Fix:** whitelist the reviewed v3 anchors (every v3 anchor not flagged in my V3 report) as curated pairs so they bypass the description gate.
3. **Residual facet glitches (~400 rows):**
   - Garden/caraway seeds, kidney beans, tares/lentils and chick peas sit in `grp_oilseeds` / SITC 22 (`0246`, `0899`, `0658`, `1385`, `1927`, `1839`, `1907`).
   - *Cheese except Margarine Cheese* and *Margarine Cheese* sit under "Animal Fats, Tallow…" / SITC 41 (`1415`, `1668`).
   - *Cream of Tartar* is in Dairy & Eggs / SITC 02 (`0750`; it is a tartrate).
   - *Iron Hoops* and *Steel Ingots Blooms **Billets*** are in timber (`0905`, `1517`).
   - Mineral waters are in industrial minerals (`0904`, `1574`).
   - *Soap Transparent…* is in grocery (`1074`).
4. **Input mapped to product (v2 regression):** `0868` *Paper Making Materials Pulp of Wood* → paper.

### P2
- **Ambiguous labels.** 13 `altLabel`s equal another concept's `prefLabel` (e.g. "India rubber" on `0015` vs `0142` *India Rubber*; "hogs" on `0037` vs `0384`; "maize" on `0047` vs `0049`). `0047` *Indian Corn* has altLabel "corn", which in British customs usage means grain generally. `0696` *Gutta Percha* has "elastic gum", but gutta-percha is the non-elastic latex. Some altLabels are Wikidata item labels rather than period synonyms ("egg as food").
- **Inconsistent substance-group label style:** "Textile (substance group)" vs "Wood — Hewn, Round & Cabinet Timber (group)".
- `0006` *Peas* → `Q12034432` "legume :: fruit type" is the botanical fruit-type sense; a pulse/food item would be better.

## 3. Bottom line
Fix the three mechanical P0s:
- reject `Q3290341` for *Mares*;
- prune the ~16 bogus `skos:related` pairs;
- correct the "electrical" over-mapping.

After that the vocabulary is **publishable as SKOS/LOD**. The two P1 follow-ups (re-admit the ~150 vetted v3 anchors, and gate the dictionary definitions) would bring coverage back above v3 levels and keep precision.
