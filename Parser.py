
from __future__ import annotations
import argparse
import sys, os, time, json, logging
import multiprocessing as mp
# Set multiprocessing start method to 'spawn' for CUDA compatibility
mp.set_start_method('spawn', force=True)


from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Union, List, Dict
from tqdm import tqdm
import torch

from grobidParse import grobid_process
from MagicJSONschema import build_flat_schema
from ParseMagicJSONfuncs import hierarchical_parse
from cleanMagicOut import clean_bad_entry
from PyDFfuncs import get_pdf_arnum

def _init_worker(log_level: str):
    """
    This function will run in each worker process exactly once,
    before any calls to `_process_pdf()` occur.
    """
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)-s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

#NoGroBiD: Dict[str, str] = {}

def _process_pdf(args: tuple[Path, Path, int],
                 grobid_url: str = "http://localhost:8070"
                 ) -> Union[None, tuple[Path, bool]]:
    # Unpack tuple
    pdf_path, output_root, gpu_id = args
    # Assign GPU for this process
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    logging.info("[%s] Using GPU %d", pdf_path.name, gpu_id)
    IEEE_Fold = Path(os.getenv('IEEE_REPO'))
    arnum = get_pdf_arnum(str(pdf_path), pdf_path.name)

    from MinerBasicMagic import minermagic

    """Run minermagic on one PDF, writing into its own subfolder under output_root."""
    #stem = pdf_path.stem
    #pdf_out = output_root / stem
    #pdf_out.mkdir(parents=True, exist_ok=True)
    #timing = time.perf_counter()
    try:

        json_out = output_root / f"{arnum}.json"
        pred_dir = IEEE_Fold / 'predictions'
        pred_dir.mkdir(exist_ok=True, parents=True)
        miner_out = minermagic(str(pdf_path), str(output_root), False)
        filtered_data = miner_out #clean_bad_entry(miner_out)
        json_out.write_text(json.dumps(filtered_data, ensure_ascii=False, indent=2), encoding="utf-8")
        hierarchy = hierarchical_parse(filtered_data)["hierarchy"]
        body_end = hierarchical_parse(filtered_data)["body_end"]
        body_dict = build_flat_schema(filtered_data, hierarchy, body_end)
        full_json_out = pred_dir/f"{arnum}.json"
        try:
            content, refs_dict = grobid_process(pdf_path, grobid_url, output_root, False)
            content = content | body_dict
            #for key, item in body_dict.items():
             #   content[key] = item
            content["bibliographical references"] = refs_dict
            full_json_out.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")

            logging.debug("Processed: %s", pdf_path.name)
        except Exception as e:
            logging.error("Failure processing %s through GroBiD. Only outputting Miner JSON.", e)

            full_json_out.write_text(json.dumps(body_dict, ensure_ascii=False, indent=2), encoding="utf-8")
            logging.debug("Partially processed: %s", pdf_path.name)
            return pdf_path, True
    except Exception as e:
        logging.error("Failed to process %s: %s", pdf_path.name, e)
        return pdf_path, False
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
    with ProcessPoolExecutor(max_workers=workers,
                             mp_context=ctx,
                            initializer=_init_worker,
                            initargs=(log_level,)
                             ) as executor:
        futures = [executor.submit(_process_pdf, task) for task in tasks]
        for _ in tqdm(as_completed(futures), total=len(futures), desc="Processing PDFs", unit="pdf"):
            pass

    # Summarize failures
    failed = [f.result() for f in futures if f.result()]
    FailedDict = {k[0].name: str(k[0]) for k in failed if not k[1]}
    NoGroBiD = {k[0].name: str(k[0]) for k in failed if k[1]}
    if failed:
        logging.error("%d PDF(s) failed:", len(failed))
        if FailedDict:
            logging.error("%d failed the MinerU parsing pipeline:", len(FailedDict))
            for p in FailedDict.values():
                logging.error(" - %s", p)
        if NoGroBiD:
            logging.error("%d failed to parse through GroBiD:", len(NoGroBiD))
    else:
        logging.info("All %d PDFs processed successfully.", len(pdf_paths))


    Failedjson = output_root/"FailedMines.json"
    Failedjson.write_text(json.dumps(FailedDict, ensure_ascii=False, indent=2), encoding="utf-8")
    NoGrobjson = output_root/"NoGroBid.json"
    NoGrobjson.write_text(json.dumps(NoGroBiD, ensure_ascii=False, indent=2), encoding="utf-8")


    # Print overall elapsed time
    total_elapsed = time.perf_counter() - overall_start
    logging.info("Total processing time: %.2f seconds", total_elapsed)


def main(argv=None):
    default_src = os.getenv("DiffAmp")
    parser = argparse.ArgumentParser(description="Parallel MinerU PDF batch runner")
    parser.add_argument(
        "inputs", nargs="*", default=default_src,
        help="Directory of PDFs or list of PDF file paths"
    )
    parser.add_argument(
        "-o", "--output", help="Output root folder (default: <input_dir>/output or ./output)",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true",
        help="Recurse into subdirectories when input is a dir"
    )
    parser.add_argument(
        "-w", "--workers", type=int, default=4,
        help="Number of parallel worker processes"
    )
    parser.add_argument(
        "-ll", "--log-level", default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)-s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,  # Or sys.stderr
    )

    run_parallel(
        inputs=args.inputs if len(args.inputs) > 1 else args.inputs[0],
        output=args.output,
        workers=args.workers,
        recursive=args.recursive,
        log_level=args.log_level,
    )

if __name__ == "__main__":
    main()
