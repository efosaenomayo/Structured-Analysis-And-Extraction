import json
import re, pprint
from typing import List, Dict, Tuple, Any


# ─────────────────────────────
#  I/O helpers
# ─────────────────────────────
def load_json(fp: str) -> List[Dict]:
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj: Any, fp: str) -> None:
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


# ─────────────────────────────
#  Header utilities
# ─────────────────────────────
def extract_all_headers(data: List[Dict]) -> List[Dict]:
    """Return every item whose text_level == 1 and type contains 'text'."""
    return [
        {"idx": i, "text": it["text"].strip()}
        for i, it in enumerate(data)
        if it.get("text_level") == 1 and "text" in it.get("type", "")
    ]


def find_introduction_idx(headers: List[Dict]) -> int:
    for i, h in enumerate(headers):
        if "INTRODUCTION" in h["text"].upper():
            return i
    raise ValueError("INTRODUCTION header not found")


def get_prefix(text: str) -> str:
    """Return the leading token before the first space (e.g. 'I.', 'A.' → 'I', 'A')."""
    m = re.match(r"^(\S+)[.)]?\s+", text)
    return m.group(1) if m else ""


# ★ UPDATED — far stricter Roman-numeral check
_ROMAN_1_50 = (
    "I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|"
    "XIX|XX|XXI|XXII|XXIII|XXIV|XXV|XXVI|XXVII|XXVIII|XXIX|XXX|XL|L"
)
_ROMAN_RE = re.compile(rf"^({_ROMAN_1_50})$")

DEPTH_NAME = {
    0: "section",
    1: "subsection",
    2: "subsubsection",
    3: "paragraph",
    4: "subparagraph",
}

def depth_to_label(depth: int) -> str:
    """Return a human name for tree depth; ≥5 collapses to 'level<N>'."""
    return DEPTH_NAME.get(depth, f"level{depth}")


def get_prefix_format(prefix: str) -> str:
    p = prefix.rstrip(".)").upper()
    if _ROMAN_RE.fullmatch(p):                 # I … L   (1–50)
        return "roman"
    if p.isdigit():                            # 1, 2, 3 …
        return "arabic"
    if re.fullmatch(r"[A-Z]", p):              # A, B, C …
        return "alpha"
    if re.fullmatch(r"\d+(\.\d+)+", p):        # 1.1, 2.3.4 …
        return "numeric"
    return "none"


def classify_level(fmt: str, text_upper: str) -> str:
    if fmt in ("roman", "arabic"):
        return "section"
    if fmt in ("alpha", "numeric"):
        return "subsection"
    return "section"


# ─────────────────────────────
#  Region helpers
# ─────────────────────────────
def determine_regions(
    headers: List[Dict],
    start: int,
    end: int,
    upper_bound: int,         # exclusive
) -> List[Tuple[int, int]]:
    """Return (region_start, region_end) for each headers[start..end]."""
    positions = [h["idx"] for h in headers[start : end + 1]]
    regions: List[Tuple[int, int]] = []
    for i, pos in enumerate(positions):
        region_start = pos
        region_end = positions[i + 1] - 1 if i + 1 < len(positions) else upper_bound - 1
        regions.append((region_start, region_end))
    return regions


def extract_subheaders(
    data: List[Dict], start: int, end: int
) -> List[Dict]:
    """Gather every header (text_level 1) *inside* data[start … end]."""
    subs: List[Dict] = []
    for idx in range(start, min(end, len(data) - 1) + 1):
        it = data[idx]
        if it.get("text_level") == 1 and "text" in it.get("type", ""):
            txt = it["text"].strip()
            if "REFERENCES" in txt.upper():
                break
            subs.append({"idx": idx, "text": txt})
    return subs


# ─────────────────────────────
#  Recursive parser  ★ UPDATED
# ─────────────────────────────
def recursive_region_parser(
    data: List[Dict],
    headers: List[Dict],
    start: int,
    end: int,
    upper_bound: int,         # exclusive limit for this level
    depth: int = 0
) -> List[Dict]:
    sections: List[Dict] = []
    regions = determine_regions(headers, start, end, upper_bound)

    for i, (r_start, r_end) in enumerate(regions):
        hdr = headers[start + i]
        prefix = get_prefix(hdr["text"])
        fmt = get_prefix_format(prefix)
        level = depth_to_label(depth)#classify_level(fmt, hdr["text"].upper())

        # immediate children inside this region
        child_headers = extract_subheaders(data, r_start + 1, r_end)
        subsections = (
            recursive_region_parser(
                data, child_headers, 0, len(child_headers) - 1,
                r_end + 1, depth + 1
            )
            if child_headers
            else []
        )

        sections.append(
            {
                "idx": r_start,
                "prefix": prefix,
                "title": hdr["text"],
                "format": fmt,
                "level": level,
                "region": (r_start, r_end),
                "subsections": subsections,
            }
        )

    return sections


# ─────────────────────────────
#  Top-level parse  ★ UPDATED
# ─────────────────────────────
def hierarchical_parse(data: List[Dict]) -> Dict[str, Any]:
    hdrs = extract_all_headers(data)
    intro_i = find_introduction_idx(hdrs)
    into_fmt = get_prefix_format(get_prefix(hdrs[intro_i]["text"]))

    body_end = next(                       # stop at “REFERENCES” or EOF
        (h["idx"] for h in hdrs if "REFERENCES" in h["text"].upper()),
        len(data),
    )

    # keep *only* headers that are real sections
    section_hdrs: List[Dict] = []
    for h in hdrs[intro_i:]:
        if h["idx"] >= body_end:
            break
        fmt = get_prefix_format(get_prefix(h["text"]))
        if fmt == into_fmt: #classify_level(fmt, h["text"].upper()) == "section":
            section_hdrs.append(h)

    section_format = into_fmt #get_prefix_format(get_prefix(section_hdrs[0]["text"]))

    hierarchy = recursive_region_parser(
        data, section_hdrs, 0, len(section_hdrs) - 1, body_end
    )

    return {"section_format": section_format, "hierarchy": hierarchy, "body_end": body_end}
if __name__ == '__main__':

    filepath = '/home/ge25yud/Documents/Mine_Outs/6H-SiC JFETs for 450 °C Differential Sensing Applications/auto/6H-SiC JFETs for 450 °C Differential Sensing Applications_content_list.json'
    datas = load_json(filepath)
    parsed = hierarchical_parse(datas)



    pprint.pprint(parsed)
