# Layer-1 Human-Transcribed Trade Consolidation Report

- **Canonical file:** `/home/jic823/Documents/open_empire/human_trade/layer1_human/human_trade_observations.tsv.gz`
- **Total Layer-1 records:** **153,579** (`tc_2021_full_database.csv`: 144,742; `British Imports Database 1910-1940.xlsx`: +8,837 unique, 75 exact overlaps skipped, 1,039,663 blank rows skipped)
- **Row kinds:** {'malformed_year': 42, 'origin_detail': 117028, 'export_total': 26784, 'import_total': 8892, 'incomplete': 151, 'blank': 168, 'qa_check_row': 514}
- **Unique printed places (origin + destination, excl. World/Total):** **499**
- **Unique printed commodities:** **2,066**
- **Unique printed unit pairs:** **336**

## Series Breakdown
- `(blank)`: **64,289**
- `HCPP_Annual Statement of Trade`: **55,798**
- `KEW_CUST 4`: **9,765**
- `HCPP_Annual Statement of Trade (1910-1940 ext)`: **8,837**
- `CSP_Canadian Trade and Navigation`: **6,820**
- `HCPP_Other`: **6,293**
- `KEW_CUST 5`: **1,342**
- `NULL and other errors`: **233**
- `Newfoundland_data`: **202**

## What Are the 64,289 Blank-Series Rows?
- Top destinations: [('All Countries', 25273), ('United States', 17754), ('Great Britain', 7800), ('British North America', 2936), ('Newfoundland', 2215), ('British West Indies', 1199), ('St. Pierre', 796), ('France', 630), ('Germany', 586), ('Other Foreign Countries', 492), ('Belgium', 345), ('Australia', 323)]
- Year span: `1763` to `Mille` (79 distinct year labels)

## Built-In `World`-Total Arithmetic Check (Origin Parts vs. Printed World Total)
- Checkable `(series, year, commodity, dest, unit)` groups (>=2 origin rows + 1 World total): **6,618**
  - Agree within 1%: **6,382** (96.4%)
  - Agree within 1–5%: **47** (0.7%)
  - Differ >5% (often partial country coverage or 'Other Countries' omitted): **189** (2.9%)
