#!/usr/bin/env python3
"""
Polite, resumable Internet Archive open-corpus fetcher for Open Empire.

Supports:
  --mode ocr   : metadata JSON + _djvu.txt (secondary cross-check reading only)
  --mode pdf   : metadata JSON + best single clean PDF (for Chandra OCR)
  --mode full  : metadata JSON + _djvu.txt + best single clean PDF

Stores immutable source files under:
  /mnt/data/jic823/open_empire_corpus/raw/<wave>/<series>/<identifier>/
Never downloads raw JP2 tarballs or lending-restricted items.
Logs every downloaded file with SHA-256 into:
  /mnt/data/jic823/open_empire_corpus/logs/download_ledger.tsv
"""

import argparse
import csv
import hashlib
import json
import random
import subprocess
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

CORPUS_ROOT = Path("/mnt/data/jic823/open_empire_corpus")
RAW_ROOT = CORPUS_ROOT / "raw"
LOG_ROOT = CORPUS_ROOT / "logs"
LEDGER_PATH = LOG_ROOT / "download_ledger.tsv"

USER_AGENT = "OpenEmpireResearchBot/0.2 (University of Saskatchewan HGIS Lab; jim.clifford@usask.ca)"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_json(url: str) -> dict:
    proc = subprocess.run(
        [
            "curl", "-fsSL", "--retry", "6", "--retry-all-errors", "--retry-delay", "3",
            "--max-time", "90", "-A", USER_AGENT, url,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def download_file(url: str, dest: Path) -> int:
    tmp = dest.with_suffix(dest.suffix + ".part")
    subprocess.run(
        [
            "curl", "-fsSL", "-C", "-", "--retry", "8", "--retry-all-errors", "--retry-delay", "4",
            "--connect-timeout", "30", "--speed-time", "45", "--speed-limit", "1024",
            "-A", USER_AGENT, "-o", str(tmp), url,
        ],
        check=True,
    )
    tmp.replace(dest)
    return dest.stat().st_size


def pick_files(meta: dict, mode: str):
    """Select clean open OCR text and/or best single PDF from IA metadata."""
    files = meta.get("files", [])
    if str(meta.get("metadata", {}).get("access-restricted-item", "")).lower() == "true":
        return [], "access_restricted"

    ocr_candidates = []
    pdf_candidates = []
    for f in files:
        name = f.get("name", "")
        fmt = (f.get("format") or "").lower()
        if f.get("private") == "true":
            continue
        if name.endswith("_djvu.txt") or fmt == "djvutxt":
            ocr_candidates.append((0, name, f))
        elif name.endswith("_hocr_searchtext.txt.gz"):
            ocr_candidates.append((1, name, f))

        if name.lower().endswith(".pdf"):
            if "encrypted" in fmt or "lcp" in name.lower():
                continue
            # Prefer clean original/standard PDF over _bw.pdf or _text.pdf unless only those exist
            if name.lower().endswith("_bw.pdf"):
                rank = 3
            elif name.lower().endswith("_text.pdf"):
                rank = 2
            elif fmt == "text pdf":
                rank = 0
            else:
                rank = 1
            size = int(f.get("size") or 0)
            pdf_candidates.append((rank, -size, name, f))

    chosen = []
    if mode in ("ocr", "full") and ocr_candidates:
        ocr_candidates.sort(key=lambda x: x[0])
        chosen.append(("ocr_text", ocr_candidates[0][1]))

    if mode in ("pdf", "full") and pdf_candidates:
        pdf_candidates.sort(key=lambda x: (x[0], x[1]))
        chosen.append(("pdf", pdf_candidates[0][2]))

    return chosen, "ok"


def process_item(row: dict, mode: str, delay_s: float):
    wave = row["wave"]
    series = row["series"]
    iid = row["identifier"]
    item_dir = RAW_ROOT / wave / series / iid
    item_dir.mkdir(parents=True, exist_ok=True)
    meta_path = item_dir / "ia_metadata.json"

    try:
        if meta_path.exists() and meta_path.stat().st_size > 100:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            if delay_s > 0:
                time.sleep(delay_s)
            meta = fetch_json(f"https://archive.org/metadata/{urllib.parse.quote(iid)}")
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        return iid, "meta_error", [], str(exc)

    chosen, status = pick_files(meta, mode)
    if status != "ok":
        return iid, status, [], ""

    records = []
    for role, fname in chosen:
        dest = item_dir / Path(fname).name
        if dest.exists() and dest.stat().st_size > 0:
            records.append((role, str(dest), dest.stat().st_size, "cached"))
            continue
        if delay_s > 0:
            time.sleep(delay_s)
        url = f"https://archive.org/download/{urllib.parse.quote(iid)}/{urllib.parse.quote(fname)}"
        try:
            nbytes = download_file(url, dest)
            digest = sha256_file(dest)
            records.append((role, str(dest), nbytes, digest))
        except Exception as exc:
            records.append((role, str(dest), 0, f"ERROR:{exc}"))
            return iid, "download_error", records, str(exc)

    return iid, "ok", records, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="Path to manifest TSV")
    ap.add_argument("--series", default="", help="Filter by series (optional)")
    ap.add_argument("--sub-group", default="", help="Filter by sub_group (optional)")
    ap.add_argument("--mode", choices=["ocr", "pdf", "full"], default="pdf", help="ocr, pdf, or full")
    ap.add_argument("--limit", type=int, default=0, help="Max items to process (0 = all)")
    ap.add_argument("--workers", type=int, default=2, help="Concurrent download workers (keep <= 3 for IA)")
    ap.add_argument("--delay", type=float, default=0.8, help="Polite per-request delay in seconds")
    args = ap.parse_args()

    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(args.manifest, encoding="utf-8"), delimiter="\t"))
    selected = []
    for r in rows:
        if r.get("status") == "already_in_ceylon":
            continue
        if args.series and r.get("series") != args.series:
            continue
        if args.sub_group and r.get("sub_group") != args.sub_group:
            continue
        selected.append(r)

    if args.limit > 0:
        selected = selected[: args.limit]

    print(f"Fetching {len(selected)} items (mode={args.mode}, workers={args.workers}, delay={args.delay}s) ...", flush=True)

    ledger_exists = LEDGER_PATH.exists()
    ledger_fh = open(LEDGER_PATH, "a", encoding="utf-8", newline="")
    writer = csv.writer(ledger_fh, delimiter="\t")
    if not ledger_exists:
        writer.writerow(["timestamp_utc", "wave", "series", "identifier", "role", "path", "bytes", "sha256_or_status"])

    ok = 0
    err = 0
    restricted = 0
    total_bytes = 0

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_item, r, args.mode, args.delay): r for r in selected}
        for i, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            iid, status, records, msg = fut.result()
            now = datetime.now(timezone.utc).isoformat()
            if status == "ok":
                ok += 1
                for role, path, nbytes, digest in records:
                    total_bytes += nbytes
                    if digest != "cached":
                        writer.writerow([now, r["wave"], r["series"], iid, role, path, nbytes, digest])
            elif status == "access_restricted":
                restricted += 1
            else:
                err += 1
                writer.writerow([now, r["wave"], r["series"], iid, status, "", 0, msg])
            if i % 10 == 0 or i == len(selected):
                ledger_fh.flush()
                print(
                    f"  [{i}/{len(selected)}] ok={ok}, restricted={restricted}, err={err}, bytes={total_bytes/(1024**2):.1f} MB",
                    flush=True,
                )

    ledger_fh.close()
    print(f"Done. ok={ok}, restricted={restricted}, err={err}, total={total_bytes/(1024**2):.1f} MB")


if __name__ == "__main__":
    main()
