# 19th-Century Industrial End-Use Network Report (18 Major Manufacturing Industries)

Generated 2026-11-25 by `scripts/build_end_use_network.py` across **6,455 full-text pages** from 6 19th-century commercial & manufacturing books (Ure 1853, Simmonds 1854 & 1892, McCulloch 1880, Mortimer 1823, Watt 1908). Every link is attested by at least one verbatim primary-source quote.

**Totals:** **18** industries · **370** commodity→industry links · **198** distinct commodities (`146` Layer-1 customs + `52` Document-Attested) · **2,616** primary-source sentences.

## Overview Table
| Industry | Sector | Inputs | Layer-1 | Doc-Attested | Sentences | Top Multi-Book Inputs |
|---|---|---:|---:|---:|---:|---|
| **Soap Manufacture** (`oe:ind_soap_manufacture`) | Oils, Soap & Lighting | **24** | 20 | 4 | 181 | Pearl and Pot Ashes, Olive Oil, Palm Oil, Tallow, Alkali, Kelp |
| **Calico Cloth & Calico Printing** (`oe:ind_calico_printing`) | Textiles & Dyeing | **55** | 43 | 12 | 460 | Madder, Pearl and Pot Ashes, Cotton Raw, Alum Roach, Copperas, Bleaching Materials |
| **Woollen, Silk & Worsted Dyeing** (`oe:ind_woollen_silk_dyeing`) | Textiles & Dyeing | **26** | 22 | 4 | 146 | Wool, Indigo, Alum Roach, Cochineal, Orchal, Silk Raw |
| **Chocolate & Confectionery** (`oe:ind_chocolate_confectionery`) | Food, Drink & Groceries | **17** | 14 | 3 | 51 | Vanilla, Cocoa, Sugar Unrefined Total, Spices Cassia Lignea, Wheat Meal and Flour, Milk Condensed |
| **Leather Tanning, Tawing & Currying** (`oe:ind_leather_tanning`) | Hides, Leather & Animal Trades | **21** | 19 | 2 | 121 | Oak Bark, Shumach, Cutch, Galls, Valonia, Alum Roach |
| **Candle Manufacture** (`oe:ind_candle_manufacture`) | Oils, Soap & Lighting | **6** | 5 | 1 | 44 | Tallow, Stearine, Spermaceti, Lard, Paraffin, Bees Wax |
| **Paper Making & Cardboard** (`oe:ind_paper_making`) | Forestry, Paper & Print | **12** | 12 | 0 | 26 | Esparto and other Vegetable Fibres for making Paper, Starch, Glue Size and Gelatine, Alkali, Bleaching Materials, Flax |
| **Varnish, Paint & Lacquer** (`oe:ind_varnish_paint_lacquer`) | Chemicals, Resins & Coatings | **31** | 20 | 11 | 241 | Gum Copal, Spirits Unenumerated not Sweetened, Turpentine Oil, Pitch, Gum Lac, Seed, Shell, Stick, and Dye, Oil Seed |
| **Glassmaking, Pottery & Porcelain** (`oe:ind_glass_ceramics`) | Minerals, Metals & Heavy Industry | **18** | 17 | 1 | 212 | Flint Glass, Pearl and Pot Ashes, Lead Pig and Sheet, Kaolin, Cobalt Ore, Clay unmanufactured |
| **India-Rubber, Gutta-Percha & Waterproofing** (`oe:ind_rubber_waterproofing`) | Chemicals, Resins & Coatings | **5** | 5 | 0 | 42 | Caoutchouc, Naphtha, Gutta Percha, Tar, Oil Seed |
| **Brewing, Malting & Distilling** (`oe:ind_brewing_distilling`) | Food, Drink & Groceries | **12** | 10 | 2 | 291 | Hops, Barley, Malt, Sugar Unrefined Total, Molasses, Aniseed |
| **Sugar Refining** (`oe:ind_sugar_refining`) | Food, Drink & Groceries | **6** | 5 | 1 | 165 | Sugar Unrefined Total, Bones (except Whalefins), Charcoal, Molasses, Manufactures Lime, Albumin |
| **Shipbuilding, Rope, Cordage & Sailcloth** (`oe:ind_cordage_shipbuilding`) | Forestry, Paper & Print | **13** | 11 | 2 | 36 | Hemp Rough or Undressed, Tar, Tallow, Turpentine Oil, Pitch, Rosin |
| **Gunpowder, Explosives & Lucifer Matches** (`oe:ind_gunpowder_matches`) | Chemicals, Resins & Coatings | **9** | 5 | 4 | 127 | Charcoal, Saltpetre, Brimstone, Pearl and Pot Ashes, Chlorate Of Potash, Glue Size and Gelatine |
| **Perfumery, Pomades & Essential Oils** (`oe:ind_perfumery_cosmetics`) | Oils, Soap & Lighting | **19** | 12 | 7 | 35 | Spices Cloves, Spirits Unenumerated not Sweetened, Gum Benzoin, Safflower, Spices Cassia Lignea, Vanilla |
| **Pharmaceuticals & Druggists' Preparations** (`oe:ind_pharmaceuticals`) | Chemicals, Resins & Coatings | **52** | 36 | 16 | 123 | Opium, Sugar Unrefined Total, Turpentine Oil, Morphia, Lignum Quassia, Spirits Unenumerated not Sweetened |
| **Metallurgy, Smelting, Brass & Tinplate** (`oe:ind_metallurgy_tinplate`) | Minerals, Metals & Heavy Industry | **25** | 21 | 4 | 238 | Borax, Sulphuric Acid, Charcoal, Zinc Ore, Bismuth, Copper Ore |
| **Hat-Making, Brushes, Upholstery & Turnery** (`oe:ind_hats_brushes_upholstery`) | Hides, Leather & Animal Trades | **19** | 16 | 3 | 77 | Skins Furs Pelts Beaver, Ivory (Elephant Sea Cow Sea Horse or Sea Moose Teeth), Skins Furs Pelts Rabbit, Glue Size and Gelatine, Canes Rattans not Ground, Bristles |

## Most Multi-Use Commodities (Cross-Industry Hubs)
| Commodity | Tier | # Industries | Industries |
|---|---|---:|---|
| `htc:0562` **Rosin** | Layer-1 | **7** | Calico Cloth & Calico Printing, Shipbuilding, Rope, Cordage & Sailcloth, Metallurgy, Smelting, Brass & Tinplate, Paper Making & Cardboard, Pharmaceuticals & Druggists' Preparations, Soap Manufacture, Varnish, Paint & Lacquer |
| `htc:0136` **Pearl and Pot Ashes** | Layer-1 | **6** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Gunpowder, Explosives & Lucifer Matches, Paper Making & Cardboard, Soap Manufacture, Woollen, Silk & Worsted Dyeing |
| `htc:2002` **Copperas** | Layer-1 | **5** | Calico Cloth & Calico Printing, Hat-Making, Brushes, Upholstery & Turnery, Leather Tanning, Tawing & Currying, Soap Manufacture, Woollen, Silk & Worsted Dyeing |
| `htc:0348` **Manufactures Lime** | Layer-1 | **5** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Leather Tanning, Tawing & Currying, Metallurgy, Smelting, Brass & Tinplate, Sugar Refining |
| `htc:0172` **Olive Oil** | Layer-1 | **5** | Calico Cloth & Calico Printing, Perfumery, Pomades & Essential Oils, Pharmaceuticals & Druggists' Preparations, Soap Manufacture, Woollen, Silk & Worsted Dyeing |
| `htc:0975` **Sulphuric Acid** | Layer-1 | **5** | Calico Cloth & Calico Printing, Hat-Making, Brushes, Upholstery & Turnery, Leather Tanning, Tawing & Currying, Metallurgy, Smelting, Brass & Tinplate, Woollen, Silk & Worsted Dyeing |
| `htc:0022` **Tallow** | Layer-1 | **5** | Candle Manufacture, Shipbuilding, Rope, Cordage & Sailcloth, Leather Tanning, Tawing & Currying, Metallurgy, Smelting, Brass & Tinplate, Soap Manufacture |
| `htc:0557` **Alkali** | Layer-1 | **4** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Paper Making & Cardboard, Soap Manufacture |
| `htc:1932` **Alum Roach** | Layer-1 | **4** | Calico Cloth & Calico Printing, Leather Tanning, Tawing & Currying, Paper Making & Cardboard, Woollen, Silk & Worsted Dyeing |
| `htc:0118` **Cochineal** | Layer-1 | **4** | Calico Cloth & Calico Printing, Chocolate & Confectionery, Varnish, Paint & Lacquer, Woollen, Silk & Worsted Dyeing |
| `htc:0677` **Gum Lac, Seed, Shell, Stick, and Dye** | Layer-1 | **4** | Calico Cloth & Calico Printing, Hat-Making, Brushes, Upholstery & Turnery, Varnish, Paint & Lacquer, Woollen, Silk & Worsted Dyeing |
| `htc:0025` **Lard** | Layer-1 | **4** | Candle Manufacture, Perfumery, Pomades & Essential Oils, Pharmaceuticals & Druggists' Preparations, Soap Manufacture |
| `htc:0267` **Lead Pig and Sheet** | Layer-1 | **4** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Metallurgy, Smelting, Brass & Tinplate, Varnish, Paint & Lacquer |
| `htc:doc_nitric_acid` **Nitric acid** | Doc-Attested | **4** | Calico Cloth & Calico Printing, Gunpowder, Explosives & Lucifer Matches, Metallurgy, Smelting, Brass & Tinplate, Woollen, Silk & Worsted Dyeing |
| `htc:0257` **Salt** | Layer-1 | **4** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Leather Tanning, Tawing & Currying, Soap Manufacture |
| `htc:0573` **Spices Cloves** | Layer-1 | **4** | Chocolate & Confectionery, Perfumery, Pomades & Essential Oils, Pharmaceuticals & Druggists' Preparations, Soap Manufacture |
| `htc:0077` **Spirits Unenumerated not Sweetened** | Layer-1 | **4** | Hat-Making, Brushes, Upholstery & Turnery, Perfumery, Pomades & Essential Oils, Pharmaceuticals & Druggists' Preparations, Varnish, Paint & Lacquer |
| `htc:0103` **Sugar Unrefined Total** | Layer-1 | **4** | Brewing, Malting & Distilling, Chocolate & Confectionery, Pharmaceuticals & Druggists' Preparations, Sugar Refining |
| `htc:0364` **Tin in Blocks Ingots Bars or Slabs** | Layer-1 | **4** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Metallurgy, Smelting, Brass & Tinplate, Woollen, Silk & Worsted Dyeing |
| `htc:1115` **Borax** | Layer-1 | **3** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Metallurgy, Smelting, Brass & Tinplate |
| `htc:1248` **Charcoal** | Layer-1 | **3** | Gunpowder, Explosives & Lucifer Matches, Metallurgy, Smelting, Brass & Tinplate, Sugar Refining |
| `htc:doc_citric_acid` **Citric Acid** | Doc-Attested | **3** | Calico Cloth & Calico Printing, Pharmaceuticals & Druggists' Preparations, Woollen, Silk & Worsted Dyeing |
| `htc:0096` **Dye Woods Logwood** | Layer-1 | **3** | Calico Cloth & Calico Printing, Hat-Making, Brushes, Upholstery & Turnery, Woollen, Silk & Worsted Dyeing |
| `htc:0072` **Galls** | Layer-1 | **3** | Calico Cloth & Calico Printing, Leather Tanning, Tawing & Currying, Woollen, Silk & Worsted Dyeing |
| `htc:1015` **Glue Size and Gelatine** | Layer-1 | **3** | Gunpowder, Explosives & Lucifer Matches, Hat-Making, Brushes, Upholstery & Turnery, Paper Making & Cardboard |
