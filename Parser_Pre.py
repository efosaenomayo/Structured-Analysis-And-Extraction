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

from Parser import run_parallel

def getFailed(output_dir: Path, get_mines: bool = True, get_nogrobids: bool= False) -> Union[None, List[Path]]:
    MineFails = output_dir / "FailedMines.json"
    noGrobids = output_dir / "NoGroBid.json"
    if not get_mines:
        return None
    if not output_dir.is_dir():
        logging.error(f"{str(output_dir)} does not exist or is not directory.")
        return None
    if not MineFails.exists():
        logging.error(f"No existing JSON file logging MinerU failures.")
        return None
    with MineFails.open() as Mf:
        pdf_paths = [k for k in json.load(Mf).values()]

    if get_nogrobids:
        if not noGrobids.exists():
            logging.warning(f"No existing JSON file logging GroBid failures.")
        else:
            with noGrobids.open() as nG:
                pdf_paths.extend(k for k in json.load(nG).values())
                return pdf_paths
    return pdf_paths
    #pdfs_paths = [v.values for]




if __name__ == "__main__":
    DocFolds = Path(os.getenv('DiffAmp'))
    json_typs = DocFolds/'results/typical.json'
    out_dir = DocFolds/'GrobMineOuts'
    out_dir.mkdir(parents=True, exist_ok=True)
    failed_list = getFailed(out_dir, False)
    if failed_list:
        pdf_paths = failed_list
    elif json_typs.is_file():
        with json_typs.open() as f:
            pdf_paths = [k['pdf_path'] for k in json.load(f)]
            #pdf_paths = list(itertools.islice((k['pdf_path'] for k in json.load(f)), 10))
    logging.info(f"Starting parallel parsing on {len(pdf_paths)} PDFs.")
    run_parallel(pdf_paths, str(out_dir), workers=1)
