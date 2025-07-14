import os
import shutil
import time
import fitz  # PyMuPDF
import pdfplumber
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from SectionTitleLayout import INTRO_GENERAL_REGEX, determine_prefix_style

# Logging Configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Global Paths
IEEEFold = "/home/saefoxxyo/Work/IEEE"
DocFolds = os.environ["DiffAmp"]
roman_outpath = os.path.join(DocFolds, "Romans")
digit_outpath = os.path.join(DocFolds, "Digits")

# Ensure directories exist before processing
os.makedirs(roman_outpath, exist_ok=True)
os.makedirs(digit_outpath, exist_ok=True)


def preprocess_pdfs(pdf_file):
    """Processes a PDF file: Extracts prefix and moves it accordingly."""
    pdf_path = os.path.join(DocFolds, pdf_file)

    try:
        with pdfplumber.open(pdf_path) as doc:  # Ensure file closes after processing
            page = doc.pages[0]  # Load the first page
            mid_x = page.width / 2
            #text = page.extract_text()
            #words =  page.extract_words()
            #words_sorted = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
            # Crop left half

            left_crop = page.crop((0, 0, mid_x, page.height))
            left_words = left_crop.extract_words(extra_attrs=["fontname", "size"])
            words_sorted = sorted(left_words, key=lambda w: (round(w["bottom"]), w["x0"]))

        prefix_style = "none"  # Default if no match is found
        lines = []
        current_line_y = None
        line_words = []




        # We’ll combine words into “lines” based on their y-coordinates.
        # pdfplumber’s default x_tolerance / y_tolerance can help, but we’ll do a simple grouping here.
        # Sort words top-to-bottom, then left-to-right

        # Find the introduction line
        #for block in blocks:
            #for line in block.get("lines", []):
        for w in words_sorted:
            y_rounded = round(w["bottom"])
            #print(y_rounded)
            # If we’re on a new y-coordinate, start a new line
            if current_line_y is None or abs(current_line_y - y_rounded) > 3:
                # If we have accumulated words on one line, push them into lines
                if line_words:
                    line_text = " ".join(word["text"] for word in line_words)
                    """if "INTRODUCTION" in w['text'].upper():
                        print("Current Doc: "+ pdf_file+ "\nCurrent text: " + line_text+ "\nNext text: "+w['text']
                        + '\ncurrent line pos.: '+str(current_line_y) + '\nnext line pos.: '+str(y_rounded))"""
                    match = INTRO_GENERAL_REGEX.match(line_text)
                    if match:
                        #print(line_text)
                        prefix = match.group("prefix") or ""  # Example: "I." or "1."
                        prefix_style = determine_prefix_style(prefix)
                        break

                # Reset for the new line
                line_words = [w]
                current_line_y = y_rounded
            else:
                # print(w)
                line_words.append(w)
                if "INTRODUCTION" in w['text'].upper():
                    print("Current Doc: " + pdf_file + "\nCurrent text: " + line_text + "\nNext text: " + w['text']
                          + '\ncurrent line pos.: ' + str(current_line_y) + '\nnext line pos.: ' + str(y_rounded))



        # Determine destination
        if prefix_style == "digit":
            destination = digit_outpath
        elif prefix_style == "roman":
            destination = roman_outpath
        else:
            logging.info(f"Skipping {pdf_file}: No valid prefix found.")
            return f"Skipped {pdf_file}"

        # Handle potential filename conflicts by renaming
        dest_file = os.path.join(destination, pdf_file)
        if os.path.exists(dest_file):
            logging.info(f"{dest_file} already exists. Renaming to avoid conflicts.")
            base, ext = os.path.splitext(dest_file)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            dest_file = f"{base}_{counter}{ext}"

        # Move the file
        shutil.move(pdf_path, dest_file)
        logging.info(f"Moved {pdf_file} to {dest_file}")

        return f"Processed {pdf_file}"  # Return a message for logging

    except Exception as e:
        logging.error(f"Error processing {pdf_file}: {e}")
        return f"Error processing {pdf_file}"


def main():
    """Main function to process PDFs in parallel."""
    pdf_files = [doc for doc in sorted(os.listdir(DocFolds)) if doc.endswith(".pdf")]

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(preprocess_pdfs, pdf_file): pdf_file for pdf_file in pdf_files}

        for future in as_completed(futures):
            pdf_file = futures[future]  # Retrieve the corresponding filename
            try:
                result = future.result()  # Retrieve the processing result
                logging.info(result)  # Log success message
            except Exception as e:
                logging.error(f"Failed to process {pdf_file}: {e}")  # Log specific file error


if __name__ == "__main__":
    start_time = time.time()
    main()
        # 1) Open PDF
    logging.info(f"Total time taken: {time.time() - start_time:.2f} seconds.")
