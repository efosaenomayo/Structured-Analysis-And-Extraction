import argparse, json, logging, pathlib, os
from datetime import datetime
from tqdm import tqdm
from grobidParseFuncs import _post_pdf, _tei_refs_to_ieee_json, _tei_header_to_ieee_json
from typing import Optional, Tuple, Dict, Any, List

def grobid_process(pdf_path: pathlib.Path,
                   grobid_url: str,
                   out_dir: pathlib.Path,
                   full_dump: bool = True,
                   all_dump: bool = False) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
    """Send one PDF to Grobid, save TEI + JSON in out_dir."""
    t0 = datetime.now()

    logging.info("🟡  %s – start", pdf_path.name)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) read bytes once
    try:
        pdf_bytes = pdf_path.read_bytes()
        logging.debug("Read %d bytes from %s", len(pdf_bytes), pdf_path)
    except Exception as exc:
        logging.error("❌  %s – cannot read PDF: %s", pdf_path.name, exc)
        return None

    # 2) header endpoint
    try:
        header_xml = _post_pdf(
            pdf_bytes,
            f"{grobid_url}/api/processHeaderDocument",
            consolidate="consolidateHeader",
        )
        if full_dump and all_dump:
            header_file = out_dir / f"{pdf_path.stem}.header.tei.xml"
            header_file.write_text(header_xml, encoding="utf-8")
            logging.debug("Saved header TEI → %s", header_file)
    except Exception as exc:
        logging.error("❌  %s – header extraction failed: %s", pdf_path.name, exc)

    # 3) references endpoint
    try:
        refs_xml = _post_pdf(
            pdf_bytes,
            f"{grobid_url}/api/processReferences",
            consolidate="includeRawCitations",
        )
        if full_dump and all_dump:
            refs_file = out_dir / f"{pdf_path.stem}.references.tei.xml"
            refs_file.write_text(refs_xml, encoding="utf-8")
            logging.debug("Saved references TEI → %s", refs_file)
    except Exception as exc:
        logging.error("❌  %s – reference extraction failed: %s", pdf_path.name, exc)

    # 4) TEI → JSON transformation
    try:
        doc = {"source_file": str(pdf_path.resolve())}
        dict_header = _tei_header_to_ieee_json(header_xml)
        refs_dict = _tei_refs_to_ieee_json(refs_xml)
        doc = {"source_file": str(pdf_path.resolve()), **dict_header, "bibliographical references": refs_dict}

        if full_dump:
            json_file = out_dir / f"{pdf_path.stem}.json"
            json_file.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            logging.info("✅  %s – JSON saved → %s  (%.2f s)",
                     pdf_path.name, json_file, (datetime.now() - t0).total_seconds())
        return dict_header, refs_dict
    except Exception as exc:
        logging.error("❌  %s – TEI→JSON conversion failed: %s", pdf_path.name, exc)
        return None


if __name__ == "__main__":
    grobid_url = "http://localhost:8070"
    DocFolds = pathlib.Path(os.environ.get('DiffAmp'))
    pdf_path = DocFolds/'6H-SiC JFETs for 450 °C Differential Sensing Applications.pdf'
    out_path = DocFolds/pdf_path.stem
    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s",
                        level=logging.DEBUG)
    logging.info("STARTING!!!!!")
    grobid_process(pdf_path, grobid_url, out_path)


