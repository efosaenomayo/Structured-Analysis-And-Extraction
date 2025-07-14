import json
import re
import pprint
from typing import List, Dict, Tuple, Any
from ParseMagicJSONfuncs import hierarchical_parse, get_prefix, load_json, save_json
from pylatexenc.latex2text import LatexNodes2Text
from OCR_Formel_cleanup import simple_latex_cleaner

def parse_formulae(text: str) -> List[Dict[str, str]]:
    """
    Return [{'cleaned text': 'C_ p', 'raw latex': '$C_{\\rm p}$'}, …]
    'cleaned text' is a very coarse strip of LaTeX commands – good enough for now.
    """
    _LATEX_RE = re.compile(r"\$([^$]+)\$")  # captures inner part of $…$
    out: List[Dict[str, str]] = []
    for m in _LATEX_RE.finditer(text):
        raw = f"${m.group(1)}$"
        cleaned = re.sub(r"\\[a-zA-Z]+|[{}]", "", m.group(1)).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.replace("__", "_")
        if cleaned:
            out.append({"cleaned text": cleaned, "raw latex": raw})
    return out


def collect_region_content(
    data: List[Dict], region_start: int, region_end: int
) -> List[Dict[str, Any]]:
    """
    Walk through data[region_start+1 .. region_end]. For each "text" item,
    return {"text": <string>}. Skip empty strings. Do NOT include image/table here.
    """
    content: List[Dict[str, Any]] = []
    for idx in range(region_start + 1, region_end + 1):
        item = data[idx]
        if item.get('text_level') == 1:
            break
        item_type = item.get("type", "")
        if item_type.startswith("text"):
            para = item.get("text", "").strip()
            if not para:
                continue

        formulae = parse_formulae(para)
        content_dict = {"text": para}
        if formulae:
            content_dict["formulae"] = formulae
        content.append(content_dict)
    return content


def build_body_text(
    data: List[Dict], parsed_hierarchy: List[Dict]
) -> Dict[str, Any]:
    """
    Build the "body text" structure, nesting subsections under keys of the form:
      "<parent_prefix> - <sub_title>"

    For each top-level section:
      key = section["title"]  # e.g. "I. INTRODUCTION"
      value = {
        "heading": section["title"],
        "text": [ { "text": ... }, ... ],
        "subsections": { ... nested ... }
      }

    For each subsection under a section:
      sub_key = f"{parent_prefix} - {sub['title']}"
      value = {
        "heading": sub["title"],
        "text": [ { "text": ... }, ... ],
        "subsections": {}  # (no deeper nesting in this paper)
      }
    """
    body_text: Dict[str, Any] = {}

    for sec in parsed_hierarchy:
        sec_title = sec["title"]  # e.g. "I. INTRODUCTION"
        parent_prefix = get_prefix(sec_title)  # e.g. "I"
        region_start, region_end = sec["region"]

        # Collect paragraphs within this section
        paragraphs = collect_region_content(data, region_start, region_end)

        # Build nested subsections
        subsecs_dict: Dict[str, Any] = {}
        for sub in sec["subsections"]:
            sub_title = sub["title"]  # e.g. "A. Noise Considerations"
            sub_key = f"{parent_prefix} - {sub_title}"
            sub_region_start, sub_region_end = sub["region"]
            sub_paragraphs = collect_region_content(data, sub_region_start, sub_region_end)

            # In this document, there are no deeper levels, so we set an empty dict for further nesting
            subsecs_dict[sub_key] = {
                "heading": sub_title,
                "text": sub_paragraphs,
                "subsections": {},
            }

        body_text[sec_title] = {
            "heading": sec_title,
            "text": paragraphs,
            "subsections": subsecs_dict,
        }

    return {"body text": body_text}


def extract_figures_and_tables(data: List[Dict]) -> Dict[str, Any]:
    """
    From the content_list JSON, collect all images and tables into a single dict.
    Keys:
      - "fig1", "fig2", ... for images (in order of appearance)
      - "table1", "table2", ... for tables
    Each figure entry has:
      {
        "caption": <first img_caption string>,
        "fig_num": <int>,
        "figure": <img_path>
      }
    Each table entry has:
      {
        "caption": <first table_caption string>,
        "table_num": <int>,
        "table": <table_body HTML>
      }
    """
    fig_tab_dict: Dict[str, Any] = {}
    fig_counter = 0
    table_counter = 0

    for item in data:
        itype = item.get("type")
        if itype == "image":
            img_caps = item.get("img_caption", [])
            caption = img_caps[0] if img_caps else ""
            fig_counter += 1
            key = f"fig{fig_counter}"
            fig_tab_dict[key] = {
                "caption": caption,
                "fig_num": fig_counter,
                "figure": item.get("img_path", "")
            }
        elif itype == "table":
            tbl_caps = item.get("table_caption", [])
            caption = tbl_caps[0] if tbl_caps else ""
            table_counter += 1
            key = f"table{table_counter}"
            fig_tab_dict[key] = {
                "caption": caption,
                "table_num": table_counter,
                "table": item.get("table_body", "")
            }

    return {"figures and tables": fig_tab_dict}

def parse_json_struct(data: List[Dict]) -> List[Dict]:
    parsed = hierarchical_parse(data)
    hierarchy = parsed["hierarchy"]
    # Parse the hierarchy of sections/subsections
    parsed = hierarchical_parse(raw_data)
    hierarchy = parsed["hierarchy"]

    # Build the nested "body text" dictionary (with properly nested subsections)
    body_text_struct = build_body_text(raw_data, hierarchy)

    # Extract all figures and tables into a separate dict
    figs_and_tabs = extract_figures_and_tables(raw_data)

    # 5. Combine into final output
    final_output = {
        "body text": body_text_struct["body text"],
        "figures and tables": figs_and_tabs["figures and tables"]
    }

    return final_output


if __name__ == "__main__":
    # Adjust these paths as needed:
    filepath = '/home/ge25yud/Documents/Mine_Outs/6H-SiC JFETs for 450 °C Differential Sensing Applications/auto/6H-SiC JFETs for 450 °C Differential Sensing Applications_content_list.json'
    datas = load_json(filepath)
    output_structured_path = "6H-SiC JFETs for 450 °C Differential Sensing Applications_transformed.json"

    # Load the raw content_list JSON (list of items)
    raw_data = load_json(filepath)
    final_output = parse_json_struct(datas)


    save_json(final_output, output_structured_path)