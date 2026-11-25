# 19th-Century Industrial End-Use Network Report (18 Major Manufacturing Industries)

Generated 2026-11-25 by `scripts/build_end_use_network.py` across **6,648 full-text pages** from 6 19th-century commercial & manufacturing books (Ure 1840, Simmonds 1854 & 1892, McCulloch 1880, Mortimer 1823, Watt 1908). Every quote is verbatim from the cited book; links were mined by keyword co-occurrence and then hand-reviewed (see `curated_end_use_link_decisions.tsv`) — co-occurrence alone is not proof of use.

**Totals:** **18** industries · **322** commodity→industry links · **199** distinct commodities (`151` Layer-1 customs + `48` Document-Attested) · **2,408** keyword-matched sentences (mentions; the links file shows up to 3 verbatim quotes per link).

## Overview Table
| Industry | Sector | Inputs | Layer-1 | Doc-Attested | Sentences | Top Multi-Book Inputs |
|---|---|---:|---:|---:|---:|---|
| **Soap Manufacture** (`oe:ind_soap_manufacture`) | Oils, Soap & Lighting | **23** | 20 | 3 | 180 | Pearl and Pot Ashes, Olive Oil, Palm Oil, Tallow, Alkali, Kelp |
| **Calico Cloth & Calico Printing** (`oe:ind_calico_printing`) | Textiles & Dyeing | **48** | 38 | 10 | 416 | Madder, Pearl and Pot Ashes, Cotton Raw, Alum Roach, Bleaching Materials, Sugar of Lead |
| **Woollen, Silk & Worsted Dyeing** (`oe:ind_woollen_silk_dyeing`) | Textiles & Dyeing | **24** | 22 | 2 | 139 | Wool, Indigo, Alum Roach, Cochineal, Orchal, Silk Raw |
| **Chocolate & Confectionery** (`oe:ind_chocolate_confectionery`) | Food, Drink & Groceries | **15** | 12 | 3 | 49 | Vanilla, Cocoa, Sugar, Cassia Buds, Fresh Milk, Starch |
| **Leather Tanning, Tawing & Currying** (`oe:ind_leather_tanning`) | Hides, Leather & Animal Trades | **19** | 18 | 1 | 104 | Shumach, Cutch, Galls, Valonia, Alum Roach, Divi Divi |
| **Candle Manufacture** (`oe:ind_candle_manufacture`) | Oils, Soap & Lighting | **5** | 5 | 0 | 43 | Tallow, Stearine, Train Blubber and Spermaceti (Whale Oils), Paraffin, Bees Wax |
| **Paper Making & Cardboard** (`oe:ind_paper_making`) | Forestry, Paper & Print | **10** | 10 | 0 | 22 | Esparto and other Vegetable Fibres for making Paper, Starch, Glue Size and Gelatine, Alkali, Bleaching Materials, Flax |
| **Varnish, Paint & Lacquer** (`oe:ind_varnish_paint_lacquer`) | Chemicals, Resins & Coatings | **28** | 19 | 9 | 235 | Gum Copal, Spirits, Turpentine Oil, Asphalt or Bitumen, Gum Lac, Seed, Shell, Stick, and Dye, Oil Seed |
| **Glassmaking, Pottery & Porcelain** (`oe:ind_glass_ceramics`) | Minerals, Metals & Heavy Industry | **15** | 13 | 2 | 148 | Pearl and Pot Ashes, Litharge, China Clay, Cobalt Ore, Clay unmanufactured, Borax |
| **India-Rubber, Gutta-Percha & Waterproofing** (`oe:ind_rubber_waterproofing`) | Chemicals, Resins & Coatings | **4** | 4 | 0 | 41 | Caoutchouc, Naphtha, Gutta Percha, Oil Seed |
| **Brewing, Malting & Distilling** (`oe:ind_brewing_distilling`) | Food, Drink & Groceries | **11** | 9 | 2 | 301 | Hops, Barley, Malt, Sugar, Molasses, Lignum Quassia |
| **Sugar Refining** (`oe:ind_sugar_refining`) | Food, Drink & Groceries | **5** | 4 | 1 | 156 | Sugar Unrefined Total, Bones (except Whalefins), Charcoal, Manufactures Lime, Albumen |
| **Shipbuilding, Rope, Cordage & Sailcloth** (`oe:ind_cordage_shipbuilding`) | Forestry, Paper & Print | **9** | 8 | 1 | 28 | Hemp Rough or Undressed, Tar, Tallow, Pitch, Wood and Timber Hewn Teak, Abaca |
| **Gunpowder, Explosives & Lucifer Matches** (`oe:ind_gunpowder_matches`) | Chemicals, Resins & Coatings | **7** | 4 | 3 | 115 | Charcoal, Saltpetre, Brimstone, Chlorate of Potash, Nitric acid, Glycerine Crude |
| **Perfumery, Pomades & Essential Oils** (`oe:ind_perfumery_cosmetics`) | Oils, Soap & Lighting | **16** | 9 | 7 | 32 | Spices Cloves, Spirits, Gum Benzoin, Lard, Safflower, Almonds |
| **Pharmaceuticals & Druggists' Preparations** (`oe:ind_pharmaceuticals`) | Chemicals, Resins & Coatings | **44** | 31 | 13 | 114 | Opium, Sugar, Turpentine Oil, Morphia, Lignum Quassia, Spirits |
| **Metallurgy, Smelting, Brass & Tinplate** (`oe:ind_metallurgy_tinplate`) | Minerals, Metals & Heavy Industry | **23** | 19 | 4 | 216 | Borax, Sulphuric Acid, Charcoal, Iron Ore Including Chrome, Zinc Crude in Cakes, Bismuth |
| **Hat-Making, Brushes, Upholstery & Turnery** (`oe:ind_hats_brushes_upholstery`) | Hides, Leather & Animal Trades | **16** | 14 | 2 | 69 | Skins Furs Pelts Beaver, Ivory (Elephant Sea Cow Sea Horse or Sea Moose Teeth), Skins Furs Pelts Rabbit, Canes Rattans not Ground, Bristles, Whale Fins |

## Most Multi-Use Commodities (Cross-Industry Hubs)
| Commodity | Tier | # Industries | Industries |
|---|---|---:|---|
| `htc:0562` **Rosin** | Layer-1 | **5** | Calico Cloth & Calico Printing, Metallurgy, Smelting, Brass & Tinplate, Paper Making & Cardboard, Soap Manufacture, Varnish, Paint & Lacquer |
| `htc:0975` **Sulphuric Acid** | Layer-1 | **5** | Calico Cloth & Calico Printing, Hat-Making, Brushes, Upholstery & Turnery, Leather Tanning, Tawing & Currying, Metallurgy, Smelting, Brass & Tinplate, Woollen, Silk & Worsted Dyeing |
| `htc:0557` **Alkali** | Layer-1 | **4** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Paper Making & Cardboard, Soap Manufacture |
| `htc:1932` **Alum Roach** | Layer-1 | **4** | Calico Cloth & Calico Printing, Leather Tanning, Tawing & Currying, Paper Making & Cardboard, Woollen, Silk & Worsted Dyeing |
| `htc:0118` **Cochineal** | Layer-1 | **4** | Calico Cloth & Calico Printing, Chocolate & Confectionery, Varnish, Paint & Lacquer, Woollen, Silk & Worsted Dyeing |
| `htc:2002` **Copperas** | Layer-1 | **4** | Hat-Making, Brushes, Upholstery & Turnery, Leather Tanning, Tawing & Currying, Soap Manufacture, Woollen, Silk & Worsted Dyeing |
| `htc:0677` **Gum Lac, Seed, Shell, Stick, and Dye** | Layer-1 | **4** | Calico Cloth & Calico Printing, Hat-Making, Brushes, Upholstery & Turnery, Varnish, Paint & Lacquer, Woollen, Silk & Worsted Dyeing |
| `htc:0172` **Olive Oil** | Layer-1 | **4** | Calico Cloth & Calico Printing, Pharmaceuticals & Druggists' Preparations, Soap Manufacture, Woollen, Silk & Worsted Dyeing |
| `htc:0136` **Pearl and Pot Ashes** | Layer-1 | **4** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Soap Manufacture, Woollen, Silk & Worsted Dyeing |
| `htc:0573` **Spices Cloves** | Layer-1 | **4** | Chocolate & Confectionery, Perfumery, Pomades & Essential Oils, Pharmaceuticals & Druggists' Preparations, Soap Manufacture |
| `htc:0022` **Tallow** | Layer-1 | **4** | Candle Manufacture, Shipbuilding, Rope, Cordage & Sailcloth, Leather Tanning, Tawing & Currying, Soap Manufacture |
| `htc:0364` **Tin in Blocks Ingots Bars or Slabs** | Layer-1 | **4** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Metallurgy, Smelting, Brass & Tinplate, Woollen, Silk & Worsted Dyeing |
| `htc:1115` **Borax** | Layer-1 | **3** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Metallurgy, Smelting, Brass & Tinplate |
| `htc:1248` **Charcoal** | Layer-1 | **3** | Gunpowder, Explosives & Lucifer Matches, Metallurgy, Smelting, Brass & Tinplate, Sugar Refining |
| `htc:0096` **Dye Woods Logwood** | Layer-1 | **3** | Calico Cloth & Calico Printing, Hat-Making, Brushes, Upholstery & Turnery, Woollen, Silk & Worsted Dyeing |
| `htc:0072` **Galls** | Layer-1 | **3** | Calico Cloth & Calico Printing, Leather Tanning, Tawing & Currying, Woollen, Silk & Worsted Dyeing |
| `htc:1599` **Gum Benzoin** | Layer-1 | **3** | Perfumery, Pomades & Essential Oils, Pharmaceuticals & Druggists' Preparations, Varnish, Paint & Lacquer |
| `htc:0025` **Lard** | Layer-1 | **3** | Perfumery, Pomades & Essential Oils, Pharmaceuticals & Druggists' Preparations, Soap Manufacture |
| `htc:0695` **Liquorice** | Layer-1 | **3** | Brewing, Malting & Distilling, Chocolate & Confectionery, Pharmaceuticals & Druggists' Preparations |
| `htc:0299` **Manganese Ore** | Layer-1 | **3** | Calico Cloth & Calico Printing, Glassmaking, Pottery & Porcelain, Metallurgy, Smelting, Brass & Tinplate |
| `htc:0348` **Manufactures Lime** | Layer-1 | **3** | Calico Cloth & Calico Printing, Metallurgy, Smelting, Brass & Tinplate, Sugar Refining |
| `htc:doc_musk` **Musk** | Doc-Attested | **3** | Chocolate & Confectionery, Perfumery, Pomades & Essential Oils, Soap Manufacture |
| `htc:doc_nitric_acid` **Nitric acid** | Doc-Attested | **3** | Calico Cloth & Calico Printing, Gunpowder, Explosives & Lucifer Matches, Metallurgy, Smelting, Brass & Tinplate |
| `htc:1504` **Oil Seed** | Layer-1 | **3** | India-Rubber, Gutta-Percha & Waterproofing, Soap Manufacture, Varnish, Paint & Lacquer |
| `htc:0339` **Safflower** | Layer-1 | **3** | Calico Cloth & Calico Printing, Perfumery, Pomades & Essential Oils, Woollen, Silk & Worsted Dyeing |
