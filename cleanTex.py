import re
from pylatexenc.latex2text import LatexNodes2Text

def convert_html_tags(text):
    # <sub> to _value and <sup> to ^value
    text = re.sub(r'<sub[^>]*>(.*?)</sub>', r'_\1', text)
    text = re.sub(r'<sup[^>]*>(.*?)</sup>', r'^\1', text)
    # Remove any remaining tags
    return re.sub(r'<[^>]+>', '', text)


def normalize_malformed_latex(text):
    text = text.replace(r'\over', '/')
    text = re.sub(r'\\(hbox|tag)\{\(\d+\)\}', '', text)
    text = text.replace(r'\$', '$')
    text = text.replace(r'\cr', '\n')  # line break in alignments
    text = text.replace(r'\ll', '<<')  # much less than
    text = text.replace(r'\eqalignno{', '')  # remove alignment wrappers
    text = text.replace(r'}&', ')')  # equation label ending
    text = text.replace(r'&', '')    # clean up alignment symbols
    text = re.sub(
        r'(?<!\\)(text|frac|sqrt|sum|int|lim|log|sin|cos|tan|hbox|mu|ohm|omega)',
        r'\\\1', text
    )
    return text

def convert_latex_math(text):
    # Convert \frac{a}{b} → (a) / (b)
    text = re.sub(r'\\frac\s*\{(.*?)\}\s*\{(.*?)\}', r'(\1) / (\2)', text)
    # Convert \sqrt{a} → sqrt(a)
    text = re.sub(r'\\sqrt\s*\{(.*?)\}', r'sqrt(\1)', text)
    # \text{g} → g
    text = re.sub(r'\\text\{([^}]*)\}', r'\1', text)

    # Handle superscripts and subscripts
    text = re.sub(r'\^\{(.*?)\}', r'^\1', text)
    text = re.sub(r'_\{(.*?)\}', r'_\1', text)
    text = re.sub(r'\^([^\s_])', r'^\1', text)
    text = re.sub(r'_([^\s^])', r'_\1', text)
    return text

def latex_to_text(latex_str):
    # Step 1: HTML <sub> and <sup> if present
    malaligned_match = r'\\$[^$]+\\$'
    latex_str = normalize_malformed_latex(latex_str)
    latex_str = convert_html_tags(latex_str)

    # Step 2: Use pylatexenc to convert most of the structure
    converter = LatexNodes2Text(
        math_mode='text',
        keep_braced_groups=True
    )
    text = converter.latex_to_text(latex_str)

    # Step 3: Manually fix math constructs not handled
    text = convert_latex_math(text)

    # Step 4: Final cleanup
    text = text.replace('{', '(').replace('}', ')')
    text = re.sub(r'\\[a-zA-Z]+', '', text)  # remove leftover commands
    text = re.sub(r'\s+', ' ', text).strip()

    return text
