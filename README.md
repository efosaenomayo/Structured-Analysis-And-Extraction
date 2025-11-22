# Structured Analysis and Extraction

## Overview
Structured Analysis and Extraction is a collection of Python scripts that transform PDFs into structured JSON along with cropped figure and table images. The toolkit wraps the **magic-pdf (MinerU)** pipeline for layout-aware parsing and can optionally enrich results with metadata from a running **GROBID** server. Typical outcomes include:

- Layout-aware JSON capturing pages, paragraphs, tables, figures, formulas, and captions.
- Cropped PNGs for detected figures and tables.
- (Optional) Bibliographic header and reference data merged from GROBID.

## Table of Contents
1. [Dependencies and Environment](#dependencies-and-environment)
2. [Installation](#installation)
3. [How to Run](#how-to-run)
   - [MinerU-only parsing](#mineru-only-parsing)
   - [Full pipeline (MinerU + GROBID)](#full-pipeline-mineru--grobid)
4. [Outputs](#outputs)
5. [Configuration and Options](#configuration-and-options)
6. [Customization and Upgrades](#customization-and-upgrades)
7. [Acknowledgements](#acknowledgements)

## Dependencies and Environment
- **Python**: 3.10+ recommended.
- **GPU**: CUDA-capable GPU recommended for speed; CPU works but is slower. Ensure NVIDIA drivers match your PyTorch build.
- **System libraries**: Packages required by `magic-pdf` (e.g., `libgl1`, `libglib2.0-0` on Debian/Ubuntu) and any fonts needed by your PDFs.
- **Python libraries**:
  - `magic-pdf` (MinerU) ≥ 0.8
  - `torch`, `torchvision`, `torchaudio` built for your CUDA toolkit (or CPU wheels)
  - `requests` (used for GROBID HTTP calls)
- **Optional services**: Reachable GROBID server when metadata enrichment is desired.

## Installation
Install Python dependencies in a virtual environment of your choice. Update the PyTorch wheel URL to match your CUDA version (or remove `--extra-index-url` for CPU-only):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install "magic-pdf>=0.8" torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121
pip install requests
```

Verify MinerU is available:

```bash
python -c "import magic_pdf; print(magic_pdf.__version__)"
```

## How to Run
### MinerU-only parsing
Run MinerU directly to parse one PDF and emit outputs under an `output/` directory next to the input:

```bash
python MinerBasicMagic.py /path/to/paper.pdf
```

Parse a directory recursively with multiple workers and write results elsewhere:

```bash
python MinerBasicMagic.py /path/to/pdfs --recursive -j 8 -o /path/to/results
```

### Full pipeline (MinerU + GROBID)
Set the key environment variables and run the orchestrator to parse PDFs, flatten MinerU output, and merge GROBID metadata when available:

```bash
export IEEE_REPO=/data/predictions            # required: where per-paper outputs are written
export DiffAmp=/data/papers                  # optional: default input search path
python Parser.py
```

`Parser.py` parallelizes MinerU runs, flattens hierarchical JSON, merges GROBID header/reference metadata, and writes per-paper folders under `${IEEE_REPO}`. If GROBID is unreachable, MinerU-only JSON is still produced.

You can override defaults and steer the run with the following CLI arguments (all defined in `Parser.py`):

| Argument | Default | Purpose |
| --- | --- | --- |
| `inputs` | `${DiffAmp}` env var | Directory of PDFs to search, or one-or-more explicit PDF paths. When a directory is provided, `--recursive` controls whether nested folders are scanned. |
| `-o, --output` | `<input_dir>/output` or `./output` | Root folder for MinerU and merged JSON outputs when you do not rely on `${IEEE_REPO}`. |
| `-r, --recursive` | `False` | Recurse into subdirectories when `inputs` is a directory. |
| `-w, --workers` | `4` | Number of parallel worker processes driving MinerU and GROBID. |
| `-ll, --log-level` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

Example: parse two explicit PDFs with verbose logs into a custom output folder:

```bash
python Parser.py /data/papers/a.pdf /data/papers/b.pdf --output /data/run-1 --workers 8 --log-level DEBUG
```

## Outputs
- **MinerU artifacts**: For each PDF, an `output/` folder containing cropped figure/table images and `<pdf>_content_list.json` describing layout content.
- **Full pipeline results**: Under `${IEEE_REPO}`, each paper receives a folder with flattened JSON suitable for downstream tasks plus any merged GROBID header and reference data. Error summaries are emitted as JSON for failed documents.

## Configuration and Options
- **Input root (`DiffAmp`)**: Optional environment variable pointing `Parser.py` to a default PDF directory when explicit paths are not provided.
- **Output root (`IEEE_REPO`)**: Required for `Parser.py`; controls where per-paper prediction folders are written.
- **Batch sizing (`MINERU_MIN_BATCH_INFERENCE_SIZE`)**: MinerU auto-tunes based on detected GPU VRAM; override to balance throughput vs. memory usage.
- **Language hints (`--lang`)**: Pass to MinerU runners for non-English PDFs to improve extraction quality.
- **Worker counts (`-j`)**: Control parallelism for MinerU runners; reduce if you hit GPU memory limits.
- **GROBID endpoints**: Ensure the server URL and ports are reachable; configure authentication per your deployment.

## Customization and Upgrades
- **Schema tuning**: `MagicJSONschema.py` reshapes MinerU output into a flatter schema. Adjust section handling, figure/table references, or paragraph ordering here to fit downstream needs.
- **Batch drivers**: `MinerBasicMagic.py`, `MinerFigsCaption.py`, and related helpers expose different defaults for MinerU runs—inspect their CLI arguments for alternate batching or output behaviors.
- **Post-processing utilities**: Scripts such as `ParseMagicJSON.py`, `ParseReferences.py`, and `cleanMagicOut.py` offer cleanup, reference parsing, and inspection helpers that can be chained after MinerU runs.
- **Upgrading MinerU/PyTorch**: When updating `magic-pdf`, review release notes for model or schema changes. Align PyTorch wheels with your CUDA toolkit and revalidate any custom schema code (`MagicJSONschema.py`) after upgrades.

## Acknowledgements
This project builds on the efforts of:

- **MinerU / magic-pdf team** — creators of the open-source MinerU pipeline that powers the layout-aware parsing used here. Explore their models, dataset curation work, and issues on GitHub: https://github.com/opendatalab/MinerU.
- **GROBID team** — maintainers of the GROBID service for robust bibliographic parsing and citation extraction. See their code, releases, and documentation on GitHub: https://github.com/kermitt2/grobid.
