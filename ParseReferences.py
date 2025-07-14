import json
from pathlib import Path
import re
import requests as req
from bs4 import BeautifulSoup as bSoup
from bs4.element import Tag
import logging
from ParseIEEEHead import process_math 

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def parse_references(arNum: str, sess: req.Session):
    ref_url = "https://ieeexplore-ieee-org.eaccess.tum.edu/rest/document/{arNum}/references"

    response = sess.get(ref_url)
    if response.ok:
        try: 
            data = response.json()
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse Reference JSON: {e}")
            return None
    else:
        return None
    # Extract reference entries
    references = data.get("references", [])

    # Parse relevant information
    parsed_references = []
    for ref in references:
        parsed_references.append(get_referenceDict(ref))
    
    return parsed_references

def clean_text(raw: str):
    # Step 1: Remove LaTeX/math expressions like \$...$
    
    cleaned = process_math(raw)
    cleaned = re.sub(r'\\\$.*?\\\$', '', raw)

    # Step 2: Collapse multiple spaces to single
    cleaned = re.sub(r'\s+', ' ', cleaned)

    # Step 3: Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    return cleaned


def extract_references(refsoup: Tag) -> dict:
    references = {}

    for ref in refsoup.select('div.reference-container'):
        number_tag = ref.select_one('div.number b')
        text_tag = ref.select_one('div.col > div')

        if number_tag and text_tag:
            ref_num = number_tag.get_text(strip=True).rstrip('.')
            ref_id = f"ref{ref_num}"
            ref_text = clean_text(text_tag.get_text(" ", strip=True))
            authors, title, source, year, volume, issue, pages = extract_details(ref_text, True)

            # Find the <em> tag for source (journal/conference name)
            source_tag = text_tag.select_one('em')
            source = source_tag.get_text(strip=True) if source_tag else None

            references[ref_id] ={
                "reference no.": ref_num,
                "title": title,
                "authors": authors,
                "source": source,
                "volume": volume,
                "issue no.": issue,
                "pages": pages,
                "publication year": year,
                "raw text": ref_text
            }

    return references
       

def get_referenceDict(ref: dict):
    refDict= {}
    ref_text = ref.get("text")
    
    authors, source, year, volume, issue, pages = extract_details(ref_text)
    id = ref.get("id")
    refDict[id] ={
        "id": ref.get("id"),
        "title": ref.get("title"),
        "authors": authors,
        "source": source,
        "volume": volume,
        "issue no.": issue,
        "pages": pages,
        "publication year": year
    }
    articNum = ref.get("articleNumber")
    if articNum:
        refDict["articleNumber"]  = articNum
        refDict["documentLink"]  = ref.get("links").get("documentLink")
    refDict[id]["raw text"] = ref_text
    return refDict

def extract_details(text: str, sel: bool=False):
    # Match authors: before the first quotation mark
    authors_match = re.match(r'^(.*?),\s*"', text)
    authors_text = authors_match.group(1) if authors_match else ""

    # Split authors by ', and' or ' and ' or just ',' (handling Oxford commas and variants)
    authors = re.split(r',\s+and\s+| and |, ', authors_text)

    # Match source/journal/conference: after the title in <em> tags
    source_match = re.search(r'<em>(.*?)</em>', text)
    source = source_match.group(1) if source_match else ""

    title_match = re.search(r'"([^"]+)"', text)
    title = title_match.group(1) if title_match else None

    # Match year: typically found near end, often a 4-digit year
    year_match = re.search(r'\b(19|20)\d{2}\b', text)
    year = year_match.group(0) if year_match else ""

    volume_match = re.search(r'vol\.\s*(\d+)', text, re.IGNORECASE)
    volume = volume_match.group(1) if volume_match else None

    iss_match = re.search(r'no\.\s*(\d+)', text, re.IGNORECASE)
    issue = iss_match.group(1) if iss_match else None

    pages_match = re.search(r'pp\.\s*(\d+)-(\d+)', text, re.IGNORECASE)
    page_match = re.search(r'pp\.\s*(\d+)', text, re.IGNORECASE)
    if pages_match:
        pages = f"{pages_match.group(1)}-{pages_match.group(2)}"
    elif page_match:
        pages = f"{page_match.group(1)}"
    else:
        pages = None
    if sel:
        return authors, title, source, year, volume, issue, pages
    return authors, source, year, volume, issue, pages


if __name__ == '__main__':

    from eaccess import eaccess_login

    LOGIN_URL = "https://eaccess.tum.edu/login?url=https://ieeexplore.ieee.org/Xplore/home.jsp"
    # Load the JSON file
    #file_path = Path("/home/saefoxxyo/Downloads/references.json")
    out_path = "/home/saefoxxyo/Downloads/parsed_references.json"
    """ with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f) """
    #ref_url = "https://ieeexplore-ieee-org.eaccess.tum.edu/rest/document/5701053/references"
    arnum = int("5701053")
    sess = eaccess_login(LOGIN_URL)
    parsed_Dicts = parse_references(arnum, sess)
    with open(out_path, "w") as out:
        json.dump(parsed_Dicts, out, indent=4)