import json
import re
from typing import List, Dict, Any, Tuple
from ParseMagicJSONfuncs import save_json, load_json, hierarchical_parse
from ParseMagicJSON import parse_json_struct
from cleanMagicOut import clean_bad_entry


# ──────────────────────────
# regex for cites + latex
# ──────────────────────────
CITE_RE  = re.compile(r"\[(\d+)\]")
LATEX_RE = re.compile(r"\$([^$]+)\$")


# ──────────────────────────
# 1)  Flatten nested hierarchy ➜ “sections”
#     and build a mapping   sec_id  →  (region_start, region_end)
# ──────────────────────────
def flatten_sections(
    hierarchy: List[Dict],
    data: List[Dict]
) -> Tuple[List[Dict], Dict[str, Tuple[int, int]]]:
    """
    Walk depth-first and assign sec_id’s like 1, 2, … / 1.1, 1.2 …
    Returns
        • flat list  [{'sec_id': '1', 'title': 'I. INTRODUCTION'}, …]
        • mapping    sec_id → (region_start, region_end) in data
    """
    flat: List[Dict] = []
    region_map: Dict[str, Tuple[int, int]] = {}

    stack: List[int] = []          # keeps section numbers per level

    def visit(node: Dict, level: int):
        # grow / trim stack to current depth
        if len(stack) < level + 1:
            stack.append(0)
        stack[level] += 1
        while len(stack) > level + 1:
            stack.pop()

        # build sec_id like 2.3.1 …
        sec_id = ".".join(map(str, stack))
        flat.append({"sec_id": sec_id, "title": node["title"]})
        region_map[sec_id] = node["region"]

        for child in node["subsections"]:
            visit(child, level + 1)

    for top in hierarchy:
        visit(top, 0)

    return flat, region_map


# ──────────────────────────
# 2)  Collect paragraphs  (order preserved)
# ──────────────────────────
def collect_paragraphs(
    data: List[Dict],
    sections_region: Dict[str, Tuple[int, int]]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Returns
      • flat list of paragraph dicts
      • flat list of equation dicts (equations extracted from paragraphs)
    """
    para_list: List[Dict] = []
    eq_list:   List[Dict] = []

    for sec_id, (r_start, r_end) in sections_region.items():
        p_count = 1
        eq_cnt = 0
        for idx in range(r_start + 1, r_end + 1):
            it = data[idx]
            if it.get("text_level") == 1:      # defensive: stop at next header
                break

            typ = it.get("type", "")

            if typ.startswith("text"):
                txt = it.get("text", "").strip()
                if not txt:
                    continue
                para_id = f"{sec_id}_p{p_count}"
                para_list.append(
                    {"para_id": para_id, "sec_id": sec_id, "text": txt}
                )
                last_para_id = para_id
                p_count += 1

            elif typ.startswith("equation") and last_para_id:
                latex = it.get("text", "").strip()
                if latex:
                    eq_id = f"{last_para_id}_eq{eq_cnt}"
                    eq_list.append(
                        {"eq_id": eq_id, "para_id": last_para_id, "raw_latex": latex}
                    )
                    eq_cnt += 1

    # keep original reading order
    para_list.sort(key=lambda d: (
        list(map(int, d["sec_id"].split("."))),   # sec 1 < 1.1 < 1.2 < 2 …
        int(d["para_id"].split("_p")[-1])
    ))
    eq_list.sort(key=lambda e: e["eq_id"])

    return para_list, eq_list


# ──────────────────────────
# 3)  Figures & tables  (simple counters)
# ──────────────────────────
def collect_figs_tables(data: List[Dict], end: int) -> Tuple[List[Dict], List[Dict]]:
    figs, tabs = [], []
    fig_c, tab_c = 0, 0
    for i, it in enumerate(data):
        t = it.get("type")
        if i >= end: break
        if t == "image":
            fig_c += 1
            figs.append(
                {
                    "fig_id":  f"fig{fig_c}",
                    "caption": (it.get("img_caption") or [""])[0]
                }
            )
        elif t == "table":
            tab_c += 1
            tabs.append(
                {
                    "tab_id":  f"tab{tab_c}",
                    "caption": (it.get("table_caption") or [""])[0]
                }
            )
    return figs, tabs


# ──────────────────────────
# 4)  Master builder
# ──────────────────────────
def build_flat_schema(
    data: List[Dict],
    hierarchy: List[Dict],
    body_end: int
) -> Dict[str, Any]:

    sections, sec_region = flatten_sections(hierarchy, data)
    paragraphs, equations = collect_paragraphs(data, sec_region)
    figures, tables      = collect_figs_tables(data, body_end)

    return {
        "sections":   sections,
        "paragraphs": paragraphs,
        "equations":  equations,
        "figures":    figures,
        "tables":     tables,
    }


# ──────────────────────────
# 5)  Example driver
# ──────────────────────────
if __name__ == "__main__":
    # (1) raw content + (2) nested hierarchy from parser #1
    RAW_PATH   = '/home/ge25yud/Documents/Mine_Outs/6H-SiC JFETs for 450 °C Differential Sensing Applications/auto/6H-SiC JFETs for 450 °C Differential Sensing Applications_content_list.json'
    HIER_PATH  = "hierarchy_output.json"   # assume you dumped parser#1 result
    OUT_PATH   = "flat_schema.json"

    raw_data   = load_json(RAW_PATH)
    filtered_data = clean_bad_entry(raw_data)
    hierarchy  = hierarchical_parse(filtered_data)["hierarchy"]
    body_end = hierarchical_parse(filtered_data)["body_end"]

    flat = build_flat_schema(filtered_data, hierarchy, body_end)
    save_json(flat, OUT_PATH)

    print(f"✅  flat schema written to {OUT_PATH}")
