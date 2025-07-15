import json
import math
import glob
import os

# Weighted distance function (column-aware)
def weighted_bbox_distance(bbox1, bbox2, wx=50, wy=1):
    x1 = (bbox1[0] + bbox1[2]) / 2
    y1 = (bbox1[1] + bbox1[3]) / 2
    x2 = (bbox2[0] + bbox2[2]) / 2
    y2 = (bbox2[1] + bbox2[3]) / 2
    return math.sqrt(wx * (x1 - x2)**2 + wy * (y1 - y2)**2)

# Function to process a single file and extract image-caption and table-caption pairs
def process_dict(middle_dict: list[dict]):
    results = {
        'images': [],
        'tables': []
    }

    for page in middle_dict['pdf_info']:
        blocks = page.get('preproc_blocks', [])

        images = []
        image_captions = []
        tables = []
        table_captions = []

        for block in blocks:
            if block['type'] == 'image':
                for b in block['blocks']:
                    if b['type'] == 'image_body':
                        image_path = b['lines'][0]['spans'][0]['image_path']
                        images.append({'bbox': b['bbox'], 'image_path': image_path})
                    elif b['type'] == 'image_caption':
                        caption_text = ' '.join(span['content'] for line in b['lines'] for span in line['spans'])
                        image_captions.append({'bbox': b['bbox'], 'caption': caption_text})
            elif block['type'] == 'image_caption':
                caption_text = ' '.join(span['content'] for line in block['lines'] for span in line['spans'])
                image_captions.append({'bbox': block['bbox'], 'caption': caption_text})
            elif block['type'] == 'table':
                tables.append({'bbox': block['bbox'], 'table': block})
            elif block['type'] == 'table_caption':
                caption_text = ' '.join(span['content'] for line in block['lines'] for span in line['spans'])
                table_captions.append({'bbox': block['bbox'], 'caption': caption_text})

        for caption in image_captions:
            if not caption['caption'].startswith('Fig'):
                continue
            min_dist = math.inf
            closest_image = None
            for image in images:
                dist = weighted_bbox_distance(caption['bbox'], image['bbox'], wx=5, wy=1)
                if dist < min_dist and image['bbox'][0] < caption['bbox'][0]:
                    min_dist = dist
                    closest_image = image
            if closest_image:
                results['images'].append({
                    'image_path': closest_image['image_path'],
                    'caption': caption['caption']
                })

        for caption in table_captions:
            min_dist = math.inf
            closest_table = None
            for table in tables:
                dist = weighted_bbox_distance(caption['bbox'], table['bbox'], wx=3, wy=1)
                if dist < min_dist:
                    min_dist = dist
                    closest_table = table
            if closest_table:
                results['tables'].append({
                    'table_bbox': closest_table['bbox'],
                    'caption': caption['caption']
                })

    return results

model_file = '/home/ge25yud/Documents/Sigma-per_with_finite_middle.json'
with open(model_file, 'r') as j:
    middle_dict = json.load(j)
from pprint import pprint
pprint(process_dict(middle_dict))