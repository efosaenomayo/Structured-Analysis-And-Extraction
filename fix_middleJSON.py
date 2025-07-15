import json
import statistics
from pathlib import Path
from shapely.geometry import box
from rtree import index

# —————————————————————————————————————————————
# 1. Load both JSON files
# —————————————————————————————————————————————

pdf_dict_path    = Path("pdf_dict.json")
middle_json_path = Path("6H-SiC JFETs for 450 °C Differential Sensing Applications_middle.json")

pdf_lines = json.loads(pdf_dict_path.read_text())["Lines"]
middle    = json.loads(middle_json_path.read_text())

# We assume middle["pdf_info"][0]["preproc_blocks"] exists
blocks = middle["pdf_info"][0]["preproc_blocks"]

# —————————————————————————————————————————————
# 2. Build an R-tree index over blocks
# —————————————————————————————————————————————

# We'll keep a list: block_boxes[i] = ( (xmin, ymin, xmax, ymax), i )
block_boxes = []
for i, blk in enumerate(blocks):
    bb = tuple(blk["bbox"])  # [x0, y0, x1, y1]
    block_boxes.append((bb, i))

# Build R-tree
block_idx = index.Index()
for i, (bb, _) in enumerate(block_boxes):
    block_idx.insert(i, bb)

# Helper to compute IoU between two bboxes
def iou(a, b):
    A = box(*a)
    B = box(*b)
    inter = A.intersection(B).area
    if inter == 0:
        return 0.0
    return inter / (A.area + B.area - inter)

# —————————————————————————————————————————————
# 3. For each PyMuPDF line, reconcile with existing blocks/lines
# —————————————————————————————————————————————

for pdf_line in pdf_lines:
    pbbox = tuple(pdf_line["bbox"])
    ptext = pdf_line["text"]

    # 3A) Find candidate blocks whose bbox overlaps pbbox
    candidate_block_ids = list(block_idx.intersection(pbbox))
    # Keep only those with IoU ≥ 0.5
    cand_blocks = []
    for bid in candidate_block_ids:
        bbb, blk_idx = block_boxes[bid]
        score = iou(pbbox, bbb)
        if score >= 0.5:
            cand_blocks.append((blk_idx, score))
    if not cand_blocks:
        # No existing block overlaps this line → SKIP (do NOT create a new block)
        continue
    print(cand_blocks)

    # 3B) Choose the block with highest IoU
    cand_blocks.sort(key=lambda x: x[1], reverse=True)
    chosen_blk_idx = cand_blocks[0][0]
    blk = blocks[chosen_blk_idx]

    # 3C) Within this block, look for overlapping “lines”
    mid_lines = blk.get("lines", [])

    # Build a small list of (mid_line_bbox, line_index_in_block)
    mid_line_boxes = [(tuple(ln["bbox"]), idx) for idx, ln in enumerate(mid_lines)]

    # For each mid‐line, compute IoU with pdf_line
    overlapping_line_ids = []
    for ml_bbox, ml_idx in mid_line_boxes:
        if iou(pbbox, ml_bbox) >= 0.5:
            overlapping_line_ids.append(ml_idx)

    if len(overlapping_line_ids) == 1:
        # 3C1) Exactly one existing line matches → overwrite its text & bbox
        ln_idx = overlapping_line_ids[0]
        target = mid_lines[ln_idx]
        target["bbox"] = list(pbbox)
        # Replace all spans with a single span containing ptext
        target["spans"] = [{
            "bbox": list(pbbox),
            "content": ptext,
            "type": "text",
            "score": 1.0
        }]

    elif len(overlapping_line_ids) > 1:
        # 3C2) Multiple middle‐lines likely all pieces of one true line → MERGE
        # Pick the first as “master,” merge others into it
        master_idx = overlapping_line_ids[0]
        master = mid_lines[master_idx]

        # Compute new merged bbox = union of all involved mid‐line bboxes, but
        # we want exactly the pdf_line’s bbox, so just set to pbbox
        master["bbox"] = list(pbbox)

        # Overwrite spans
        master["spans"] = [{
            "bbox": list(pbbox),
            "content": ptext,
            "type": "text",
            "score": 1.0
        }]

        # Remove all other duplicates from block
        # (remove in descending order so indexes remain valid)
        for dup_idx in sorted(overlapping_line_ids[1:], reverse=True):
            mid_lines.pop(dup_idx)

    else:
        # 3C3) No matching mid‐line → we must INSERT a new line into the existing block
        # Create a new “line” object that matches the same schema
        new_line = {
            "bbox": list(pbbox),
            "spans": [{
                "bbox": list(pbbox),
                "content": ptext,
                "type": "text",
                "score": 1.0
            }],
            # Optionally assign an “index” field. If you need the new line
            # to fit into an existing index ordering you can do something like:
            # "index": (max(existing_indexes)+1)
        }

        # Insert it so that blk["lines"] remains sorted by y0 ascending.
        # Compute y0 for each existing line and for the new line, then insert.
        new_y0 = pbbox[1]
        insert_pos = 0
        for idx_existing, ln in enumerate(mid_lines):
            existing_y0 = ln["bbox"][1]
            if existing_y0 > new_y0:
                break
            insert_pos += 1
        mid_lines.insert(insert_pos, new_line)

        # Done. (No change to blocks list itself.)

# —————————————————————————————————————————————
# 4. Save the “fixed” middle.json
# —————————————————————————————————————————————

fixed_path = Path("6H-SiC JFETs for 450 °C Differential Sensing Applications_middle_FIXED.json")
fixed_path.write_text(json.dumps(middle, indent=2))

print(f"Saved updated file to {fixed_path!r}")
