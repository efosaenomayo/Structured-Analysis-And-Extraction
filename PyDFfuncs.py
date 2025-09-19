from pypdf import  PdfReader
import os
import pymupdf
import logging

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pdf_arnum(file_path: str, pdf_file: str):
    """Extract PDF metadata using PyPDF."""
    logging.debug(f"Processing: {pdf_file}")
    try:
        with open(file_path, "rb") as pdf:
            reader = PdfReader(pdf)
            pdf_metadata =  reader.metadata

        if not pdf_metadata:
            logging.warning(f"No metadata found for: {pdf_file}")
            return None

        arNum = pdf_metadata.get('/IEEE Article ID')
        if not arNum:
            logging.warning(f"No IEEE Article ID in metadata for: {pdf_file}")
            return None

        logging.debug(f"Found IEEE Article ID: {arNum}")
        return arNum
    except Exception as e:
        logging.error(f"Exception encountered opening PDF {pdf_file}: {e}")
        return None

if __name__=="__main__":
    IEEEFold = '/home/saefoxxyo/Work/IEEE'
    DocFolds = os.path.join(IEEEFold, 'ALLDOCS(DiffAmp)')
    pdf_path = os.path.join(DocFolds, '0.3V Bulk-Driven Current Conveyor.pdf')



    with open (pdf_path, "rb") as pdf:
        reader = PdfReader(pdf)
        print("\npypdf\n")
        #print(reader.metadata)
        metadat = reader.metadata

    doc = pymupdf.open(pdf_path)