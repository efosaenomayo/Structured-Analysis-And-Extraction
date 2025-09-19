import json, os, sys
from pathlib import Path
import logging
from typing import Union, List
import itertools

# ADD THIS: Configure logging for the main process here
logging.basicConfig(
    level=logging.INFO,  # Use the parsed log level
    format="%(asctime)s %(levelname)-s %(message)s",
    datefmt="%H:%M:%S"
)

from grobidstart import process_grobids, process_results

if __name__ == "__main__":
    DocFolds = Path(os.getenv('DiffAmp'))
    json_typs = DocFolds/'results/typical.json'
    out_dir = DocFolds/'GrobOuts'
    out_dir.mkdir(parents=True, exist_ok=True)
    #failed_list = getFailed(out_dir, False)
    """if failed_list:
        pdf_paths = failed_list
    elif json_typs.is_file():"""
    with json_typs.open() as f:
        #pdf_paths = [Path(k['pdf_path']) for k in json.load(f)]
        pdf_paths = list(itertools.islice((Path(k['pdf_path']) for k in json.load(f)), 10))
    logging.info(f"Starting parallel parsing on {len(pdf_paths)} PDFs.")

    workers = os.cpu_count() - 1
    grob_args = pdf_paths, out_dir, workers
    process_results(process_grobids(grob_args), out_dir)
