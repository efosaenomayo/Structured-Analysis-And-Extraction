import ocrmypdf, os, time
from pathlib import Path

def pre_ocr(pdf_path: Path, out_dir: Path | None = None, workers: int = 8) -> Path:
    if not out_dir:
        out_dir = pdf_path.parent

    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir/(pdf_path.stem + "_ocr.pdf")
    try:
        ocrmypdf.ocr(
            pdf_path,
            out_pdf,
            deskew=True,
            rotate_pages=True,
            progress_bar=True,
            force_ocr=True,
            jobs=workers
        )
    except Exception as exc:
        # Decide: raise, log, or return original path?
        raise RuntimeError(f"OCR failed for {pdf_path}: {exc}") from exc

    return out_pdf

def _byte_ocr(pdf_path: Path) -> bytes:
    """
    Return a *searchable* PDF as bytes, deleting the temp copy afterwards.
    """

    tmp_dir = pdf_path.parent/"OCRs"
    tmp_dir.mkdir(exist_ok=True)

    # 1 ─ OCR into tmp_dir to guarantee we never touch the source folder
    Ocr_pdf = pre_ocr(pdf_path, out_dir=tmp_dir)

    # 2 ─ read bytes; raise if the file somehow vanished
    pdf_bytes = Ocr_pdf.read_bytes()

    # 3 ─ remove the temp file; swallow 'file missing' only here
    Ocr_pdf.unlink(missing_ok=True)
    return pdf_bytes

if __name__ == "__main__":
    overall_start = time.perf_counter()
    DocFolds = Path(os.environ.get('DiffAmp'))
    pdf_path = DocFolds / 'A 5.8 GHz Implicit Class-F VCO in 180-nm CMOS Technology.pdf'
    out_path = DocFolds / pdf_path.stem
    pre_ocr(pdf_path, out_path)

    total_elapsed = time.perf_counter() - overall_start
    print("Total processing time: %.2f seconds", total_elapsed)