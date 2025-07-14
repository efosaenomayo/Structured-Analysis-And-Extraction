from __future__ import annotations
import argparse
import logging
import sys, os, time, json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Union, List
from tqdm import tqdm
import torch

# Import your single‑file function with new signature
from MinerParallel import run_parallel

if __name__ == '__main__':
    DocFolds = Path(os.environ.get('DiffAmp'))
    resFolds = DocFolds/"results"
    typical_json = resFolds/"typical.json"
    if typical_json.exists():
        with open(typical_json, 'r') as typ:
            research_art_dicts = json.load(typ)

        typical_research_pdfs = [pdf_dict.get('pdf_path') for pdf_dict in research_art_dicts]
        output_fold = str(DocFolds/"EvalOuts")
        run_parallel(typical_research_pdfs, output_fold)
