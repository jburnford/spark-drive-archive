#!/usr/bin/env python3
"""
Build small 2-3 hour Narval backfill bundles for Open Empire Chandra-2 OCR.

Reads PDFs under a local directory (or list of relative paths), verifies exact page
counts with `pdfinfo`, splits each PDF into 25-page pieces (0-based inclusive
`--page-range` matching `chandra_ceylon.py`), and packs pieces into small bundle
TSVs (default 150 pages per Slurm array task -> ~20-45 min compute, safe inside a
`--time=02:00:00` backfill window).

Bundle TSV format (no header, matching /project/def-jic823/ceylon_ocr/run_bundle.slurm):
    tag<TAB>rel_pdf<TAB>pages<TAB>zero_based_range
"""

import argparse
import re
import subprocess
from pathlib import Path


def get_pdf_pages(pdf_path: Path) -> int:
    out = subprocess.check_output(["pdfinfo", str(pdf_path)], text=True)
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    if not m:
        raise RuntimeError(f"Could not read page count for {pdf_path}")
    return int(m.group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-root", required=True, help="Local root corresponding to $BASE/pdfs on Narval")
    ap.add_argument("--out-dir", required=True, help="Directory to write <N>.tsv bundle files")
    ap.add_argument("--piece-pages", type=int, default=25, help="Pages per chandra piece (default 25)")
    ap.add_argument("--bundle-pages", type=int, default=150, help="Target max pages per Slurm array task (default 150)")
    ap.add_argument("--pdf", action="append", default=[], help="Specific relative PDF path(s) under --pdf-root")
    args = ap.parse_args()

    pdf_root = Path(args.pdf_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.pdf:
        pdfs = [pdf_root / p for p in args.pdf]
    else:
        pdfs = sorted(pdf_root.rglob("*.pdf"))

    if not pdfs:
        raise SystemExit("No PDFs found.")

    pieces = []
    manifest_rows = []
    for pdf in pdfs:
        rel = pdf.relative_to(pdf_root).as_posix()
        n_pages = get_pdf_pages(pdf)
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", pdf.stem)
        manifest_rows.append((stem, rel, n_pages))
        for start0 in range(0, n_pages, args.piece_pages):
            end0 = min(start0 + args.piece_pages - 1, n_pages - 1)
            cnt = end0 - start0 + 1
            tag = f"{stem}_p{start0 + 1:05d}"
            pieces.append((tag, rel, cnt, f"{start0}-{end0}"))

    # Pack pieces sequentially into small bundles
    bundles = []
    cur = []
    cur_pages = 0
    for p in pieces:
        if cur and cur_pages + p[2] > args.bundle_pages:
            bundles.append(cur)
            cur = []
            cur_pages = 0
        cur.append(p)
        cur_pages += p[2]
    if cur:
        bundles.append(cur)

    for idx, b in enumerate(bundles, 1):
        bpath = out_dir / f"{idx}.tsv"
        with open(bpath, "w", encoding="utf-8", newline="\n") as fh:
            for tag, rel, cnt, rng in b:
                fh.write(f"{tag}\t{rel}\t{cnt}\t{rng}\n")
        bp = sum(x[2] for x in b)
        print(f"Bundle {idx}: {bpath.name} — {len(b)} pieces, {bp} pages ({b[0][0]} .. {b[-1][0]})")

    total_pages = sum(x[2] for x in manifest_rows)
    print(f"Total: {len(manifest_rows)} PDF(s), {total_pages} pages, {len(pieces)} pieces, {len(bundles)} bundle(s)")


if __name__ == "__main__":
    main()
