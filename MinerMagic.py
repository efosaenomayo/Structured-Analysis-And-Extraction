"""minermagic.py – MinerU native‑batch runner (images + content_list JSON only)
==========================================================================
* Console‑only logging via the **logging** std‑lib (no Loguru)
* `tqdm` progress bars for dataset‑build and parsing
* **No retry loop** – each PDF is attempted once; failures are reported
* VRAM‑aware env‐var to keep MinerU from OOMing
* Overall wall‑clock timer printed at the end

Outputs per PDF
---------------
```
<OUTPUT>/<pdf‑stem>/images/...       # cropped figures / tables
<OUTPUT>/<pdf‑stem>_content_list.json
```

Usage examples
--------------
```bash
# single PDF
python minermagic.py paper.pdf -o results
# folder (non‑recursive)
python minermagic.py /data/pdfs -j 4 -o results
# recursive, 8 workers
python minermagic.py /data/pdfs --recursive -j 8 -o results
```
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List

from tqdm import tqdm

from magic_pdf.data.batch_build_dataset import batch_build_dataset
from magic_pdf.tools.common import batch_do_parse

# ---------------------------------------------------------------------------
# GPU memory helper ----------------------------------------------------------
# ---------------------------------------------------------------------------

def _get_free_vram_gb() -> float:
    """Return free GPU memory (GB) of the first CUDA device, or 0.0 if unknown."""
    try:
        import torch  # type: ignore
        if not torch.cuda.is_available():
            return 0.0
        torch.cuda.empty_cache()
        free_bytes, _ = torch.cuda.mem_get_info(0)
        return free_bytes / 1024 ** 3
    except Exception:
        # fallback to nvidia‑smi
        try:
            out = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.free",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return float(out.strip().split("\n")[0]) / 1024  # MB → GB
        except Exception:
            return 0.0


def _auto_set_batch_env(min_pages: int = 40):
    """Set MINERU_MIN_BATCH_INFERENCE_SIZE based on free VRAM if not already set."""
    if "MINERU_MIN_BATCH_INFERENCE_SIZE" in os.environ:
        return  # user explicitly set it
    free_gb = _get_free_vram_gb()
    if free_gb == 0:
        logging.info("Could not detect GPU VRAM – using MinerU defaults")
        return
    pages = max(min_pages, int(free_gb * 100))
    os.environ["MINERU_MIN_BATCH_INFERENCE_SIZE"] = str(pages)
    logging.info("Auto batch size set to %s pages (free VRAM ≈ %.1fGB)", pages, free_gb)

# ---------------------------------------------------------------------------
# Main ----------------------------------------------------------------------
# ---------------------------------------------------------------------------
def run_batch(src: str | Path,
              output: str | Path | None = None,
              *,
              recursive: bool = False,
              workers: int = 4,
              lang: str = "en",
              log_level: str = "INFO") -> None:
    """Parse a single PDF or a folder of PDFs with MinerU.

    If *output* is None, an `output` folder is created **beside the input**.
    """

    # --- logging setup --------------------------------------------------
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    _auto_set_batch_env()

    src_path = Path(src).expanduser().resolve()
    if not src_path.exists():
        logging.error("Input not found: %s", src_path)
        raise SystemExit(1)

    # discover PDFs ------------------------------------------------------
    pdf_paths = (
        [src_path]
        if src_path.is_file()
        else sorted(src_path.rglob("*.pdf") if recursive else src_path.glob("*.pdf"))
    )
    if not pdf_paths:
        logging.error("No PDF found under %s", src_path)
        raise SystemExit(1)
    logging.info("Found %d PDF(s) to process", len(pdf_paths))

    # output directory ---------------------------------------------------
    if output is None:
        output_root = (src_path.parent if src_path.is_file() else src_path) / "output"
    else:
        output_root = Path(output).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    logging.info("Outputs will be saved to %s", output_root)

    # dataset build ------------------------------------------------------
    logging.info("Building datasets with %d worker(s)…", workers)
    t0 = time.perf_counter()
    datasets_raw = batch_build_dataset([str(p) for p in pdf_paths], workers, lang)
    build_elapsed = time.perf_counter() - t0

    datasets: list = []
    doc_names: list[str] = []
    for path, ds in zip(pdf_paths, datasets_raw):
        if ds is None:
            logging.warning("Dataset build failed for %s", path)
        else:
            datasets.append(ds)
            doc_names.append(path.stem)

    if not datasets:
        logging.error("All dataset builds failed – nothing to parse.")
        raise SystemExit(1)

    logging.info("Dataset build finished in %.1fs (%d successful, %d failed)",
                 build_elapsed, len(datasets), len(pdf_paths) - len(datasets))

    # parsing ------------------------------------------------------------
    logging.info("Starting MinerU parse on %d dataset(s)…", len(datasets))
    t1 = time.perf_counter()

    pbar = tqdm(total=len(datasets), desc="Parsing PDFs", unit="pdf")
    try:
        batch_do_parse(
            str(output_root),
            doc_names,
            datasets,
            "auto",
            f_draw_span_bbox=False,
            f_draw_layout_bbox=False,
            f_draw_model_bbox=False,
            f_draw_line_sort_bbox=False,
            f_draw_char_bbox=False,
            f_dump_md=False,
            f_dump_middle_json=False,
            f_dump_model_json=False,
            f_dump_orig_pdf=False,
            f_dump_content_list=True,
            lang=lang,
        )
        pbar.update(len(datasets))
    except Exception as e:
        logging.exception("MinerU batch parsing raised an exception: %s", e)
        raise
    finally:
        pbar.close()

    parse_elapsed = time.perf_counter() - t1
    total_elapsed = build_elapsed + parse_elapsed

    logging.info(
        "Parse finished in %.1f s (dataset build %.1f s, parsing %.1f s)",
        total_elapsed,
        build_elapsed,
        parse_elapsed,
    )
def main(argv: List[str] | None = None):
    DocFolds = os.getenv("DiffAmp")
    default_src = os.path.join(DocFolds, "Digits") if DocFolds else "."

    parser = argparse.ArgumentParser(description="Batch‑parse PDFs with MinerU.")
    parser.add_argument("src", nargs="?", default=default_src, help="PDF file or folder")
    parser.add_argument("-o", "--output", help="Output root folder (default: <src>/output)")
    parser.add_argument("--recursive", action="store_true", help="Recurse into sub‑dirs")
    parser.add_argument("-j", "--workers", type=int, default=4, help="Workers for dataset build")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO…)")
    parser.add_argument("--lang", default="en", help="OCR language hint")
    args = parser.parse_args(argv)

    run_batch(
            args.src,
            output=args.output,
            recursive=args.recursive,
            workers=args.workers,
            lang=args.lang,
            log_level=args.log_level,
        )


if __name__ == "__main__":
    main()
