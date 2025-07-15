import re, unicodedata
from ParseMagicJSONfuncs import save_json, load_json
from pylatexenc.latex2text import LatexNodes2Text
# Substrings to match (case-insensitive)
phrases = [
    "Manuscript received",
    "ieee copyright",
    "digital object identifier",
    "This material is based on research sponsored",
    "the associate editor",
    "Authorized licensed use"
]




def clean_inline_formel(txt: str):
    converter = LatexNodes2Text(
        math_mode='verbatim',
        keep_braced_groups=False
    )

    def clean_latex_formula(match):
        latex_expr = match.group(1)
        # Remove spaces after opening brace and before closing brace
        latex_expr= re.sub(r'\{\s+', '{', latex_expr)
        latex_expr= re.sub(r'\s+\}', '}', latex_expr)

        # match spaces after backslash (LaTeX command)
        latex_expr= re.sub(r'\\\s+', r'', latex_expr)
        latex_expr = re.sub(r'\s+\\', r'\\', latex_expr)

        # match spaces NOT after operators or LaTeX commands
        latex_expr= re.sub(r'(?<![\\\+\-\*/=])\s+(?![\\\+\-\*/=])', '', latex_expr)
        #latex_expr = re.sub(r'\\s+', '', latex_expr)

        return latex_expr

    def replacer(match):
        latex_expr = match.group(1)
        return f"${converter.latex_to_text(latex_expr)}$"

    def normalize_spaces(text):
        return ''.join(' ' if unicodedata.category(c) == 'Zs' else c for c in text)

    txt = re.sub(r'\$(.*?)\$', replacer, txt)
    txt = re.sub(r'\$(.*?)\$', clean_latex_formula, txt)
    txt = normalize_spaces(txt)
    return txt

# Filter function
def is_bad_entry(entry):
    # Compile regex for faster matching
    phrase_pattern = re.compile("|".join(re.escape(p) for p in phrases), re.IGNORECASE)
    isbn_pattern = re.compile(r'ISBN\s+\d{1,5}-\d{1,7}-\d{1,7}-\d{1,7}-\d{1}')
    copyright_pattern = re.compile(r'©\s*\d{4}\s*IEEE', re.IGNORECASE)
    year_ieee_pattern = re.compile(r'\b\d{4}\b\s*IEEE', re.IGNORECASE)

    text = entry.get('text', '')
    return (
        phrase_pattern.search(text) or
        isbn_pattern.search(text) or
        copyright_pattern.search(text) or
        year_ieee_pattern.search(text)
    )
def combine_dicts(prev: dict, nexter: dict):
    prev_text = prev['text']
    next_text = nexter['text']
    if not prev_text.endswith('.'):
        nu_entry = {
            'type': 'text',
            'text': prev_text + ' '+ next_text,
            'page_idx': prev['page_idx']
        }
        #print(nu_entry)
        return nu_entry
    return None

def clean_bad_entry(data: list[dict]) -> list[dict]:
    filtered_data = []
    nu_idx = 0
    for idx, entry in enumerate(data):
        if not is_bad_entry(entry):
            if entry.get('type') == 'text':
                if '\n' in entry.get('text'):
                    entry['text'] = entry['text'].replace('\n', '')
                    entry['text'] =  re.sub(r'\s+', r' ', entry['text'])
                entry['text'] = clean_inline_formel(entry['text'])


            filtered_data.append(entry)
            nu_idx += 1
        else:
            prev_entry = next(item for item in reversed(filtered_data[:nu_idx+1]) if item.get('type') == 'text' and not item.get('text_level'))
            #print(prev_entry['text'].replace('\n', ''))
            next_entry = next(item for item in (data[idx+1:]) if item.get('type') == 'text' and not item.get('text_level'))
            #print(next_entry)
            nu_entry = combine_dicts(prev_entry, next_entry)
            if nu_entry:
                #print(nu_entry)
                id = filtered_data.index(prev_entry)
                #filtered_data.remove(prev_entry)
                filtered_data[id]['text'] = nu_entry['text']
                data.remove(next_entry)
    filtered_data = [entry for entry in data if not is_bad_entry(entry)]
    return filtered_data
# Filter the list

if __name__=="__main__":
    RAW_PATH   = '/home/ge25yud/Documents/A 5.8 GHz Implicit Class-F VCO in 180-nm CMOS Technology_content_list.json'
    raw_data = load_json(RAW_PATH)
    filtered_data = clean_bad_entry(raw_data)


    # Output result
    for item in filtered_data:
        print(item)
