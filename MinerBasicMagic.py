import os
import time
import logging
from pathlib import Path
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.model.pp_structure_v2 import CustomPaddleModel

def minermagic(pdf_file: str, out_dir: str, full_dump: bool=True):
    # Create custom OCR model with specific parameters
    """ocr_model = CustomPaddleModel(
        ocr=True,
        show_log=True,
        lang="en",
        det_db_box_thresh=0.4,
        use_dilation=True,
        det_db_unclip_ratio=2.0
    )"""

    # 1) Input PDF + name prefix
    #pdf_file_name = pdf_file
    #timers = time.perf_counter()
    name_root      = Path(pdf_file).stem

    # 2) Where to dump images & JSON
    image_out_dir = os.path.join(out_dir, "figures and tables")
    json_dir  = out_dir
    os.makedirs(image_out_dir, exist_ok=True)
    #print(image_out_dir)

    # Writers
    image_writer = FileBasedDataWriter(image_out_dir)
    json_writer  = FileBasedDataWriter(json_dir)

    # 3) Read PDF bytes
    reader    = FileBasedDataReader("")
    pdf_bytes = reader.read(pdf_file)

    # 4) Build dataset + infer
    ds        = PymuDocDataset(pdf_bytes, lang="en")
    use_ocr   = ds.classify() == SupportedPdfParseMethod.OCR
    infer_res = ds.apply(doc_analyze, ocr=use_ocr, show_log=True)

    # 5) Run the pipeline in the correct mode (this will save all cropped images)
    pipe_res  = infer_res.pipe_ocr_mode(image_writer) if use_ocr \
                else infer_res.pipe_txt_mode(image_writer)

    #elapsed = time.perf_counter() - timers
    #print(f"Total processing time: {elapsed:.2f} seconds")
    # 6) Dump _only_ the content list JSON (with image references)
    if full_dump:
        pipe_res.dump_content_list(
            json_writer,
            f"{name_root}_content_list.json",
            os.path.basename(image_out_dir)
        )
        return None
    else:
        return pipe_res.get_content_list(os.path.basename(image_out_dir))


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
