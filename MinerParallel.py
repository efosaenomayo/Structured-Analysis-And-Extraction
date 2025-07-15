"""minermagic_parallel.py – Parallel MinerU runner (images + content_list JSON only)
===========================================================================
Scales a single‑PDF mineru (`minermagic`) across multiple PDFs in parallel.

Defaults:
- Input: either a directory path string or a list of PDF file paths.
- Output: if input is a directory → `<input_dir>/output/`; otherwise → `./output/`.

Per‑PDF outputs go to:
```
<OUTPUT>/<pdf‑stem>/images/
<OUTPUT>/<pdf‑stem>_content_list.json
```

Usage:
```bash
# Directory, non‑recursive:
python minermagic_parallel.py /path/to/pdfs

# Directory, recursive, 8 workers:
python minermagic_parallel.py /path/to/pdfs --recursive -j 8

# List of files, custom output:
python minermagic_parallel.py file1.pdf file2.pdf -o results -j 4
```
"""
from __future__ import annotations
import argparse
import logging
import sys, os, time
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Union, List
from tqdm import tqdm
import torch



def _process_pdf(args: tuple[Path, Path, int]) -> Union[None, Path]:
    # Import your single‑file function with new signature
    from MinerBasicMagic import minermagic

    # Unpack tuple
    pdf_path, output_root, gpu_id = args
    # Assign GPU for this process
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    logging.debug("[%s] Using GPU %d", pdf_path.name, gpu_id)

    """Run minermagic on one PDF, writing into its own subfolder under output_root."""
    #stem = pdf_path.stem
    #pdf_out = output_root / stem
    #pdf_out.mkdir(parents=True, exist_ok=True)
    try:
        minermagic(str(pdf_path), str(output_root))
        logging.debug("Processed: %s", pdf_path.name)
    except Exception as e:
        logging.error("Failed to process %s: %s", pdf_path.name, e)
        return pdf_path
    return None


def run_parallel(
    inputs: Union[str, List[str]],
    output: Union[str, None] = None,
    workers: int = 4,
    recursive: bool = False,
    log_level: str = "INFO",
):
    """
    Batch process PDFs in parallel via MinerU.

    Args:
        inputs: directory path or list of PDF file paths.
        output: root output folder (defaults adaptively).
        workers: number of parallel processes.
        recursive: whether to recurse into subdirectories if inputs is dir.
        log_level: logging level.
    """
    # Start overall timer
    overall_start = time.perf_counter()

    # Set multiprocessing start method to 'spawn' for CUDA compatibility
    mp.set_start_method('spawn', force=True)

    # Setup logging
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    # Normalize inputs paths
    if isinstance(inputs, str) and Path(inputs).is_dir():
        # Single directory input
        dir_path = Path(inputs)
        pdf_paths = (
            list(dir_path.rglob("*.pdf")) if recursive else list(dir_path.glob("*.pdf"))
        )
        output_root = Path(inputs) / "output" if not output else None
    else:
        # Single file or list of PDF paths
        paths = inputs if isinstance(inputs, list) else [inputs]
        pdf_paths = [Path(p) for p in paths if Path(p).is_file() and Path(p).suffix.lower() == ".pdf"]
        output_root = Path("output") if not output else None

    if not pdf_paths:
        logging.error("No PDF files found in inputs: %s", inputs)
        return

    # Determine default output
    if output and not output_root:
        output_root = Path(output)

    output_root.mkdir(parents=True, exist_ok=True)
    logging.info("Writing outputs to: %s", output_root)

    # Detect GPUs
    gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
    if gpu_count == 0:
        logging.warning("No CUDA GPUs detected; all work will run on CPU")
        gpu_ids = [""] * len(pdf_paths)
    else:
        gpu_ids = [i % gpu_count for i in range(len(pdf_paths))]
        logging.info("Distributing %d PDFs across %d GPUs", len(pdf_paths), gpu_count)

    # Build task list with GPU assignment
    tasks = [(pdf, output_root / pdf.stem, gpu_ids[idx]) for idx, pdf in enumerate(pdf_paths)]

    # Launch parallel processing with 'spawn' context
    ctx = mp.get_context('spawn')
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
        futures = [executor.submit(_process_pdf, task) for task in tasks]
        for _ in tqdm(as_completed(futures), total=len(futures), desc="Processing PDFs", unit="pdf"):
            pass

    # Summarize failures
    failed = [f.result() for f in futures if f.result()]
    if failed:
        logging.error("%d PDF(s) failed:", len(failed))
        for p in failed:
            logging.error(" - %s", p)
    else:
        logging.info("All %d PDFs processed successfully.", len(pdf_paths))

    # Print overall elapsed time
    total_elapsed = time.perf_counter() - overall_start
    logging.info("Total processing time: %.2f seconds", total_elapsed)


def main(argv=None):
    default_src = os.getenv("DiffAmp")
    default_src = os.path.join(default_src, 'Digits')
    parser = argparse.ArgumentParser(description="Parallel MinerU PDF batch runner")
    parser.add_argument(
        "inputs", nargs="*", default=default_src,
        help="Directory of PDFs or list of PDF file paths"
    )
    parser.add_argument(
        "-o", "--output", help="Output root folder (default: <input_dir>/output or ./output)",
    )
    parser.add_argument(
        "--recursive", action="store_true",
        help="Recurse into subdirectories when input is a dir"
    )
    parser.add_argument(
        "-j", "--workers", type=int, default=8,
        help="Number of parallel worker processes"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    args = parser.parse_args(argv)

    run_parallel(
        inputs=args.inputs if len(args.inputs) > 1 else args.inputs[0],
        output=args.output,
        workers=args.workers,
        recursive=args.recursive,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
