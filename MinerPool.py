"""minermagic.py – MinerU parallel batch runner (images + content_list JSON only)
===========================================================================
* Std‑lib **logging** → console
* **Multiprocessing** pool – **N workers in total** (default: CPUs if no GPU,
  otherwise `#GPUs × workers_per_gpu`).  Workers are pinned to GPUs in a
  round‑robin scheme so you can run **multiple workers per GPU**.
* `tqdm` progress bar updates as PDFs finish
* VRAM safeguard:  `--batch-pages N` or per‑worker heuristic
* Output folder defaults to `<SRC>/output`

Outputs per PDF
---------------
```
<OUTPUT>/<pdf‑stem>/images/…
<OUTPUT>/<pdf‑stem>_content_list.json
```

Example usage
-------------
```bash
# 2 workers on each of 3 GPUs  → 6 procs total
python minermagic.py pdfs -p 6 --workers-per-gpu 2 --batch-pages 20
```
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from typing import List, Tuple

from tqdm import tqdm

# MinerU imports happen **inside the worker**

# ---------------------------------------------------------------------------
# GPU helper ----------------------------------------------------------------
# ---------------------------------------------------------------------------

from itertools import cycle
_gpu_cycle = None  # will hold an endless cycle of gpu ids

def _available_gpu_ids():
    """Return a list of *visible* CUDA device indices (can be empty)."""
    try:
        import torch  # type: ignore
        return list(range(torch.cuda.device_count()))
    except Exception:
        # fall back to `nvidia-smi -L` if torch isn't compiled with CUDA
        try:
            out = subprocess.check_output(["nvidia-smi", "-L"], text=True, stderr=subprocess.DEVNULL)
            return [i for i, ln in enumerate(out.splitlines()) if ln.startswith("GPU ")]
        except Exception:
            return []


# ---------------------------------------------------------------------------

def _get_gpu_count() -> int:
    try:
        import torch  # type: ignore
        return torch.cuda.device_count()
    except Exception:
        try:
            out = subprocess.check_output(["nvidia-smi", "-L"], text=True)
            return len([ln for ln in out.splitlines() if ln.startswith("GPU ")])
        except Exception:
            return 0


def _get_free_vram_gb() -> float:
    try:
        import torch  # type: ignore
        if not torch.cuda.is_available():
            return 0.0
        torch.cuda.empty_cache()
        free, _ = torch.cuda.mem_get_info(0)
        return free / 1024 ** 3
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Worker init / worker func ---------------------------------------------------
# ---------------------------------------------------------------------------

def _worker_init(gpu_id: int | None, batch_pages: int | None):
    if gpu_id is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    if batch_pages:
        os.environ["MINERU_MIN_BATCH_INFERENCE_SIZE"] = str(batch_pages)
    else:
        free = _get_free_vram_gb()
        if free:
            os.environ.setdefault("MINERU_MIN_BATCH_INFERENCE_SIZE", str(max(40, int(free * 100))))


def _process_pdf(task: Tuple[Path, Path, str, int | None]):
    pdf_path, output_root, lang, gpu_id = task
    # ensure env in case spawn start method duplicates init
    if gpu_id is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    from magic_pdf.data.data_reader_writer import FileBasedDataReader, FileBasedDataWriter
    from magic_pdf.data.dataset import PymuDocDataset
    from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
    from magic_pdf.config.enums import SupportedPdfParseMethod

    out_dir = output_root / pdf_path.stem
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    reader = FileBasedDataReader("")
    pdf_bytes = reader.read(str(pdf_path))

    ds = PymuDocDataset(pdf_bytes, lang=lang)
    use_ocr = ds.classify() == SupportedPdfParseMethod.OCR
    infer = ds.apply(doc_analyze, ocr=use_ocr, show_log=False)

    image_w = FileBasedDataWriter(str(img_dir))
    json_w = FileBasedDataWriter(str(out_dir))
    pipe = infer.pipe_ocr_mode(image_w) if use_ocr else infer.pipe_txt_mode(image_w)
    pipe.dump_content_list(json_w, f"{pdf_path.stem}_content_list.json", "images")
    return True


# ---------------------------------------------------------------------------
# Batch runner ----------------------------------------------------------------
# ---------------------------------------------------------------------------

def run_batch(
    src: str | Path,
    output: str | Path | None = None,
    *,
    recursive: bool = False,
    procs: int | None = None,
    workers_per_gpu: int = 1,
    lang: str = "en",
    log_level: str = "INFO",
    batch_pages: int | None = None,
):
    logging.basicConfig(level=log_level.upper(), format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)

    src_path = Path(src).expanduser().resolve()
    if not src_path.exists():
        raise SystemExit(f"Input not found: {src_path}")

    pdfs = [src_path] if src_path.is_file() else sorted(src_path.rglob("*.pdf") if recursive else src_path.glob("*.pdf"))
    if not pdfs:
        raise SystemExit("No PDF files found.")
    logging.info("%d PDF(s) detected", len(pdfs))

    output_root = Path(output or ((src_path.parent if src_path.is_file() else src_path) / "output")).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    gpu_cnt = _get_gpu_count()
    if procs is None:
        procs = (gpu_cnt * workers_per_gpu) if gpu_cnt else (os.cpu_count() or 1)
    logging.info("GPUs: %d  |  Workers to spawn: %d (workers/GPU=%d)", gpu_cnt, procs, workers_per_gpu if gpu_cnt else 0)

    # Build task list with round‑robin GPU assignment (None if CPU‑only)
    tasks: List[Tuple[Path, Path, str, int | None]] = []
    for idx, pdf in enumerate(pdfs):
        gpu_id = (idx % gpu_cnt) if gpu_cnt else None
        tasks.append((pdf, output_root, lang, gpu_id))

    start = time.perf_counter()
    with Pool(processes=procs, initializer=_worker_init, initargs=(None, batch_pages)) as pool, tqdm(total=len(tasks), desc="Parsing", unit="pdf") as bar:
        for ok in pool.imap_unordered(_process_pdf, tasks):
            bar.update()
            if not ok:
                logging.warning("A task failed")

    elapsed = time.perf_counter() - start
    logging.info("Finished %d PDF(s) in %.1f s (%.2f s/pdf)", len(tasks), elapsed, elapsed / len(tasks))


# ---------------------------------------------------------------------------
# CLI -----------------------------------------------------------------------
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None):
    ap = argparse.ArgumentParser(description="Parallel MinerU batch parser (multi workers/GPU)")
    ap.add_argument("src", help="PDF file or folder")
    ap.add_argument("-o", "--output", help="Output root (default: <src>/output)")
    ap.add_argument("--recursive", "-R", action="store_true", help="Recurse into sub‑dirs")
    ap.add_argument("-p", "--procs", type=int, help="Total worker processes (overrides workers/GPU logic)")
    ap.add_argument("--workers-per-gpu", type=int, default=1, help="Desired workers per visible GPU (ignored if -p used)")
    ap.add_argument("--lang", default="en", help="OCR language hint")
    ap.add_argument("--batch-pages", type=int, help="Set MINERU_MIN_BATCH_INFERENCE_SIZE explicitly")
    ap.add_argument("--log-level", default="INFO", help="Logging level")
    args = ap.parse_args(argv)

    run_batch(
        args.src,
        output=args.output,
        recursive=args.recursive,
        procs=args.procs,
        workers_per_gpu=args.workers_per_gpu,
        lang=args.lang,
        log_level=args.log_level,
        batch_pages=args.batch_pages,
    )

if __name__ == "__main__":
    DocFolds = os.getenv("DiffAmp")
    if len(sys.argv) == 1:
        default_src = DocFolds if DocFolds else "."
        main([default_src])
    else:
        main()
