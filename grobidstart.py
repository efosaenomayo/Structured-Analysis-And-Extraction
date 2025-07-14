import argparse, json, logging, pathlib, os
from datetime import datetime
from tqdm import tqdm
from pathlib import Path
from typing import Union, List
from concurrent.futures import ProcessPoolExecutor, as_completed
from grobidParse import grobid_process

def process_grobids(args: tuple[Union[Path, List[Path]], Path, int], grobid_url: str = "http://localhost:8070"):
    inputs, output, workers =  args

    # Normalize inputs paths
    if inputs.is_dir():
        # Single directory input
        pdf_paths = list(inputs.glob("*.pdf"))

        output_root = Path(inputs) / "output" if not output else output
    else:
        # Single file or list of PDF paths
        paths = inputs if isinstance(inputs, list) else [inputs]
        pdf_paths = [Path(p) for p in paths if Path(p).is_file() and Path(p).suffix.lower() == ".pdf"]
        output_root = Path("output") if not output else None
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(grobid_process, pdf, grobid_url, output): pdf for pdf in inputs}

if __name__ == "__main__":
