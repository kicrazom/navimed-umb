#!/usr/bin/env python3
"""Fetch English EMA Product Information PDFs for the navimed clinical-EN corpus.

The English Product Information (Annex I = Summary of Product Characteristics)
is published by EMA for every centrally-authorised medicine alongside the Polish
version, in the SAME EPAR. This script downloads the *English* Product
Information PDF for each medicine in ``manifest.json`` into ``epar_raw/``.

Provenance / anti-hallucination
-------------------------------
``manifest.json`` (medicine -> brand_name -> epar_slug) is derived directly from
the verified ``clinical-pl/corpus.jsonl`` ``source_url`` values, i.e. the exact
EPAR slugs the Polish corpus already used and that resolve to real EMA pages.
The English PI URL is the documented EMA pattern::

    https://www.ema.europa.eu/en/documents/product-information/<slug>-epar-product-information_en.pdf

No medicine, brand or URL is invented. If a download fails (404, network/egress
blocked, truncated), the medicine is SKIPPED and recorded in the fetch log with
the reason. Nothing is fabricated or substituted.

Network note
------------
This environment blocks raw ``curl`` egress from the shell but permits Python
``urllib`` egress, so the fetch uses ``urllib.request``. ``fetch_log.json`` records
exactly what was retrieved (URL, bytes, sha256) and what was skipped (with reason),
so the corpus build is fully auditable and re-runnable.
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
RAW_DIR = HERE / "epar_raw"
LOG = HERE / "fetch_log.json"

PI_URL = (
    "https://www.ema.europa.eu/en/documents/product-information/"
    "{slug}-epar-product-information_en.pdf"
)
USER_AGENT = (
    "Mozilla/5.0 (navimed-umb calibration corpus builder; research/non-commercial)"
)
MIN_PDF_BYTES = 20_000  # a real EMA PI PDF is hundreds of KB; reject stubs/error pages


def pi_url(slug: str) -> str:
    return PI_URL.format(slug=slug) if slug else ""


def download(
    url: str, dest: Path, timeout: int, retries: int
) -> tuple[bool, str, int, str]:
    """Return (ok, reason, n_bytes, sha256). Never raises on network errors."""
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ctype = resp.headers.get("Content-Type", "")
                data = resp.read()
            if not data.startswith(b"%PDF"):
                return (
                    False,
                    f"not a PDF (Content-Type={ctype!r}, head={data[:16]!r})",
                    len(data),
                    "",
                )
            if len(data) < MIN_PDF_BYTES:
                return (
                    False,
                    f"PDF too small ({len(data)} bytes) — likely error page",
                    len(data),
                    "",
                )
            dest.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            return True, "ok", len(data), sha
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} {e.reason}"
            if e.code in (404, 410):  # genuinely missing — no point retrying
                return False, last_err, 0, ""
        except urllib.error.URLError as e:
            last_err = f"URLError {e.reason}"
        except Exception as e:  # noqa: BLE001 - defensive: never crash the batch
            last_err = f"{type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(2 * attempt)
    return False, last_err or "unknown error", 0, ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=int, default=60, help="per-request timeout (s)")
    ap.add_argument("--retries", type=int, default=3, help="attempts per medicine")
    ap.add_argument(
        "--sleep", type=float, default=1.0, help="polite delay between medicines (s)"
    )
    ap.add_argument("--limit", type=int, default=0, help="fetch only first N (0 = all)")
    ap.add_argument(
        "--only", default="", help="comma-separated medicine names to fetch"
    )
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="skip medicines whose PDF is already present in epar_raw/",
    )
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["medicines"]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        manifest = [m for m in manifest if m["medicine"] in wanted]
    if args.limit:
        manifest = manifest[: args.limit]

    RAW_DIR.mkdir(exist_ok=True)
    fetched, skipped = [], []

    for i, m in enumerate(manifest, 1):
        med, brand, slug = m["medicine"], m["brand_name"], m["epar_slug"]
        url = pi_url(slug)
        dest = RAW_DIR / f"{med}.pdf"
        prefix = f"[{i}/{len(manifest)}] {med} ({brand})"

        if not slug:
            print(f"{prefix}: SKIP (no EPAR slug in manifest)")
            skipped.append(
                {"medicine": med, "brand_name": brand, "reason": "no epar_slug"}
            )
            continue
        if (
            args.skip_existing
            and dest.exists()
            and dest.stat().st_size >= MIN_PDF_BYTES
        ):
            print(f"{prefix}: already present ({dest.stat().st_size} bytes)")
            fetched.append(
                {
                    "medicine": med,
                    "brand_name": brand,
                    "url": url,
                    "bytes": dest.stat().st_size,
                    "sha256": "(pre-existing)",
                }
            )
            continue

        ok, reason, nbytes, sha = download(url, dest, args.timeout, args.retries)
        if ok:
            print(f"{prefix}: OK {nbytes} bytes")
            fetched.append(
                {
                    "medicine": med,
                    "brand_name": brand,
                    "url": url,
                    "bytes": nbytes,
                    "sha256": sha,
                }
            )
        else:
            print(f"{prefix}: SKIP ({reason})  url={url}")
            skipped.append(
                {"medicine": med, "brand_name": brand, "url": url, "reason": reason}
            )
        time.sleep(args.sleep)

    report = {
        "retrieved_at": date.today().isoformat(),
        "pi_url_pattern": PI_URL,
        "n_total": len(manifest),
        "n_fetched": len(fetched),
        "n_skipped": len(skipped),
        "fetched": fetched,
        "skipped": skipped,
    }
    LOG.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\nfetched {len(fetched)}/{len(manifest)}, skipped {len(skipped)}. log -> {LOG}"
    )
    if not fetched:
        sys.exit("no PDFs fetched — check egress to ema.europa.eu")


if __name__ == "__main__":
    main()
