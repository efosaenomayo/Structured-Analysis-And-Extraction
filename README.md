# Structured Analysis and Extraction

A collection of Python scripts for turning PDFs into structured JSON plus cropped figure/table images. The toolkit wraps the [magic-pdf (MinerU)](https://github.com/opendatalab/MinerU) library for layout-aware parsing and can optionally enrich outputs with metadata from a Grobid server.

## Table of Contents
1. [Introduction](#introduction)
2. [Dependencies and Environment](#dependencies-and-environment)
3. [Installation](#installation)
4. [Core Workflows](#core-workflows)
   - [MinerU-only parsing](#mineru-only-parsing)
   - [Full pipeline (MinerU + Grobid)](#full-pipeline-mineru--grobid)
5. [Outputs](#outputs)
6. [Configuration and Options](#configuration-and-options)
7. [Advanced Usage and Customization](#advanced-usage-and-customization)
8. [Troubleshooting](#troubleshooting)
9. [Acknowledgements](#acknowledgements)

## Introduction
The scripts in this repository orchestrate MinerU to extract layout-aware content from PDFs (text, figures, tables) and convert it into structured JSON. Optional Grobid integration adds bibliographic header and reference metadata. The outputs are designed to support downstream analysis tasks such as citation resolution or dataset creation.

## Dependencies and Environment
- **Python**: 3.10 or newer is recommended.
- **CUDA-capable GPU**: Strongly recommended for speed. CPU works but is slower. Ensure GPU drivers match the installed PyTorch build.
- **System libraries**: Packages required by `magic-pdf` (e.g., `libgl1`, `libglib2.0` on Ubuntu) and any system fonts your PDFs may rely on.
- **Python libraries**:
  - `magic-pdf` (MinerU) ≥ 0.8
  - `torch`, `torchvision`, `torchaudio` built for your CUDA toolkit (or CPU wheels if running on CPU)
  - `requests` (for Grobid HTTP calls)
- **Optional services**: Access to a running Grobid server if you want metadata enrichment.

## Installation
Install Python dependencies (adjust the PyTorch wheel URL to match your CUDA version or use CPU wheels):

```bash
pip install -U pip
pip install "magic-pdf>=0.8" torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121
pip install requests
```

Verify MinerU is available:

```bash
python -c "import magic_pdf; print(magic_pdf.__version__)"
```

## Core Workflows
### MinerU-only parsing
Parse a single PDF and write outputs next to the input under an `output/` folder:

```bash
python MinerMagic.py /path/to/paper.pdf
```

Parse a directory recursively with 8 workers and place results elsewhere:

```bash
python MinerMagic.py /path/to/pdfs --recursive -j 8 -o /path/to/results
```

### Full pipeline (MinerU + Grobid)
Set the environment variables and run the orchestrator to parse PDFs and merge Grobid metadata when available:

```bash
export IEEE_REPO=/data/predictions            # where final per-paper outputs go
export DiffAmp=/data/papers                  # default input search path (optional if you pass explicit paths)
python Parser.py
```

`Parser.py` parallelizes MinerU parsing, flattens the hierarchical output, merges Grobid header/reference metadata, and writes per-paper prediction folders under `${IEEE_REPO}`. If Grobid is unreachable, MinerU-only JSON is still produced.

## Outputs
- **MinerU artifacts**: For each PDF, an `output/` directory containing cropped images for figures and tables plus `<pdf>_content_list.json` describing layout content.
- **Full pipeline results**: Under `${IEEE_REPO}`, each paper gets its own folder with flattened JSON suitable for downstream tasks, along with any merged Grobid header and reference data. Error summaries are emitted as JSON reports for failed documents.

## Configuration and Options
- **Input root (`DiffAmp`)**: Optional environment variable that points `Parser.py` to a default PDF directory when explicit paths are not provided.
- **Output root (`IEEE_REPO`)**: Required for `Parser.py`; controls where per-paper prediction folders are written.
- **Batch sizing (`MINERU_MIN_BATCH_INFERENCE_SIZE`)**: MinerU auto-tunes based on detected GPU VRAM; override this environment variable to balance throughput vs. memory usage.
- **Language hints (`--lang`)**: Pass to MinerU runners for non-English PDFs to improve extraction quality.
- **Worker counts (`-j`)**: Control parallelism for MinerU runners; reduce if you encounter GPU memory pressure.
- **Grobid endpoints**: If using Grobid, ensure the server URL and ports are reachable from your environment; configure any required authentication per your deployment.

## Advanced Usage and Customization
- **Schema tuning**: `MagicJSONschema.py` reshapes MinerU output into a flatter schema. Adjust section handling, figure/table reference collection, or paragraph ordering here if your downstream consumers need different structures.
- **Batch drivers**: `MinerParallel.py` and `MinerBasicMagic.py` provide alternative MinerU runners with varying defaults; inspect their CLI arguments for different batching and output behaviors.
- **Post-processing utilities**: Scripts like `ParseMagicJSON.py`, `ParseReferences.py`, and `cleanMagicOut.py` offer ad-hoc cleanup, reference parsing, and inspection helpers that can be chained after MinerU runs.
- **Upgrades**: When upgrading MinerU (`magic-pdf`), review release notes for model or schema changes. Re-validate custom schema code (`MagicJSONschema.py`) after upgrades to ensure compatibility. Likewise, align PyTorch wheels with your CUDA toolkit when updating.

## Troubleshooting
- **Import or GPU errors**: Confirm `magic-pdf` is installed in the active environment and that PyTorch matches your CUDA driver version.
- **Out-of-memory or slow runs**: Lower `MINERU_MIN_BATCH_INFERENCE_SIZE`, reduce `-j`, or run on fewer PDFs to find stable settings for your GPU.
- **Grobid failures**: The pipeline will still emit MinerU-only JSON. Check Grobid server health, network connectivity, and retry if metadata is missing.

## Acknowledgements
This project builds on the efforts of the MinerU team (magic-pdf) for layout-aware PDF parsing and the Grobid team for bibliographic metadata extraction.
