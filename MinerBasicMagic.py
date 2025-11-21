import os
import time, json
from typing import Any, List
import logging
from pathlib import Path

from mineru.cli.common import read_fn, prepare_env
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.enum_class import MakeMode
from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json as pipeline_result_to_middle_json


def minermagic(pdf_file: str, out_dir: str, full_dump: bool = True) -> List[dict[str, Any]] | None:
    """
    Run MinerU (pipeline backend) on a single PDF.

    - If full_dump is True: write <stem>_content_list.json (and images)
      under out_dir/<stem>/<parse_method>/, and return None.
    - If full_dump is False: return the content_list as a Python list
      and still use MinerU's standard directory layout for images.
    """
    pdf_path = Path(pdf_file).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    pdf_name = pdf_path.stem
    out_root = Path(out_dir).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    # 1) Read PDF bytes (handles images→PDF conversion if needed)
    pdf_bytes = read_fn(pdf_path)

    # 2) Run pipeline backend for a single PDF
    pdf_bytes_list = [pdf_bytes]
    lang_list = ["en"]  # or [""] to let MinerU infer/guess
    parse_method = "auto"

    (infer_results, all_image_lists,
     all_pdf_docs,out_lang_list,
        ocr_enabled_list) = pipeline_doc_analyze(pdf_bytes_list,lang_list,
                                                 parse_method=parse_method,formula_enable=True,
                                                 table_enable=True,)

    # We only have one document: use index 0
    model_list = infer_results[0]
    images_list = all_image_lists[0]
    pdf_doc = all_pdf_docs[0]
    _lang = out_lang_list[0]
    _ocr_enable = ocr_enabled_list[0]

    # 3) Where to put images + JSON
    local_image_dir, local_md_dir = prepare_env(str(out_root), pdf_name, parse_method)
    image_writer = FileBasedDataWriter(local_image_dir)
    md_writer = FileBasedDataWriter(local_md_dir)

    # 4) Convert model output → middle_json (successor of PipeResult internals)
    middle_json = pipeline_result_to_middle_json(
        model_list,
        images_list,
        pdf_doc,
        image_writer,
        _lang,
        _ocr_enable,
        True,
    )
    pdf_info = middle_json["pdf_info"]

    # 5) Build content_list (successor of PipeResult.get_content_list)
    image_dir_name = os.path.basename(local_image_dir)
    content_list = pipeline_union_make(pdf_info, MakeMode.CONTENT_LIST, image_dir_name)

    # 6) Dump / return
    if full_dump:
        # Write content_list.json similar to old behavior (different path layout)
        md_writer.write_string(
            f"{pdf_name}_content_list.json",
            json.dumps(content_list, ensure_ascii=False, indent=4),
        )

        # Optionally also dump middle_json for debugging:
        md_writer.write_string(
            f"{pdf_name}_middle.json",
            json.dumps(middle_json, ensure_ascii=False, indent=4),
        )

        logging.info("MinerU pipeline finished for %s → %s", pdf_name, local_md_dir)
        return None
    else:
        # Parser.py expects a Python list, not a file.
        return content_list

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,  # Use the parsed log level
        format="%(asctime)s %(levelname)-s %(message)s",
        datefmt="%H:%M:%S"
    )

    DocFolds = os.environ.get('DiffAmp')
    pdf_path = os.path.join(DocFolds, '6H-SiC JFETs for 450 °C Differential Sensing Applications.pdf')
    timers = time.perf_counter()
    miner_contents = minermagic(pdf_path, f"{os.path.dirname(pdf_path)}/{Path(pdf_path).stem}", True)

    total_elapsed = time.perf_counter() - timers
    logging.info("Total processing time: %.2f seconds", total_elapsed)
    print(f"Total processing time: {total_elapsed:.2f} seconds")
