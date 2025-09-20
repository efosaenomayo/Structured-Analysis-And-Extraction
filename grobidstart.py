import argparse, json, logging, os
from tqdm import tqdm
from pathlib import Path
from typing import Union, List
from concurrent.futures import ProcessPoolExecutor, as_completed
from grobidParse import grobid_process

def process_grobids(args: tuple[List[Path], Path, int], grobid_url: str = "http://localhost:8070",
    full_dump: bool = True,
    all_dump: bool = False) -> List[Path]:
    inputs, output_dir, workers =  args

    failed_results = []

    # Normalize inputs paths
    # Single file or list of PDF paths
    pdf_paths = inputs if isinstance(inputs, list) else [inputs]
    #pdf_paths = [Path(p) for p in paths if Path(p).is_file() and Path(p).suffix.lower() == ".pdf"]

    with ProcessPoolExecutor(max_workers=workers) as pool:
        # Set up the future tasks
        futures = {pool.submit(grobid_process, pdf, grobid_url, output_dir, full_dump, all_dump): pdf for pdf in pdf_paths}

        # Process futures as they complete
        pbar = tqdm(as_completed(futures), total=len(pdf_paths), desc="Processing PDFs")
        for fut in pbar:
            pdf_path = futures[fut]
            pbar.set_postfix_str(pdf_path.name, refresh=True)
            try:
                result = fut.result()
                if not result:
                    failed_results.append(pdf_path)
            except Exception as e:
                logging.error("❌  Error processing future for %s: %s", pdf_path.name, e)

    return failed_results

def process_results(failed_grobes: List[Path], output_root: Path):
    NoGrobjson = output_root / "GroBid_Fails.json"
    NoGrobes = []
    for pdf in failed_grobes:
        NoGrobes.append({
            'title': pdf.name,
            'PDF path': str(pdf)
        })
    NoGrobjson.write_text(json.dumps(NoGrobes, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch process scholarly PDFs using a GROBID server.")
    parser.add_argument("inputs", nargs="+", help="One or more input PDF files or directories containing PDFs.")
    parser.add_argument("-o", "--output", default="Grob_Outs",
                        help="Output directory to save JSON results. (Default: 'output')")
    parser.add_argument("-w", "--workers", type=int, default=os.cpu_count(),
                        help="Number of concurrent worker processes. (Default: 4)")
    parser.add_argument("--url", default="http://localhost:8070",
                        help="URL of the running GROBID service. (Default: http://localhost:8070)")
    parser.add_argument("--no-save", action="store_true", help="Do not save individual JSON files for each PDF.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress info-level logging messages.")
    #parser.add_argument("--save-summary", help="If specified, save a consolidated JSON array of all results to this file.")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=log_level, datefmt="%Y-%m-%d %H:%M:%S")

    # Discover all PDF files from the provided input paths
    input_paths = [Path(p) for p in args.inputs]
    pdf_files = []
    output_root = input_paths[0].parent
    for p in input_paths:
        if p.is_dir():
            pdf_files.extend(sorted(p.glob("*.pdf")))
            output_root = p
        elif p.is_file() and p.suffix.lower() == ".pdf":
            pdf_files.append(p)
            if output_root != p.parent:
                output_root = None

    if not pdf_files:
        logging.warning("No PDF files were found in the specified input paths. Exiting.")
        exit()

    output_path = Path(args.output) if not output_root else output_root/args.output
    logging.info(f"Found {len(pdf_files)} PDF(s) to process. Using {args.workers} worker(s).")

    grob_args = input_paths, output_path, args.workers
    # Run the batch processing
    #failed_grobes = process_grobids(grob_args)
    process_results(process_grobids(grob_args), output_path)
