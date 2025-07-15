import re
from sympy.parsing.latex import parse_latex
from sympy import simplify, Eq
from pylatexenc.latex2text import LatexNodes2Text
from cleanTex import normalize_malformed_latex


def clean_latex_ocr(ocr_text):
    # Pattern to match LaTeX commands starting with backslash
    pattern = re.compile(r'(\\\\[a-zA-Z]+\*?\s*\{[^}]*\})')

    parts = pattern.split(ocr_text)
    cleaned_parts = []

    for part in parts:
        if pattern.match(part):
            # This is a LaTeX command, clean its argument
            # Separate command and argument
            cmd_match = re.match(r'(\\[a-zA-Z]+\*?)\s*\{([^}]*)\}', part)
            if cmd_match:
                command = cmd_match.group(1)
                argument = cmd_match.group(2).replace(" ", "")
                cleaned_parts.append(f"{command}{{{argument}}}")
            else:
                # If no argument (edge case), leave as-is
                cleaned_parts.append(part)
        else:
            # Clean normal text: remove spaces between characters
            cleaned_parts.append(part.replace(" ", ""))

    return ''.join(cleaned_parts)


def simple_latex_cleaner(ocr_text):
    """
    Simplifies OCR LaTeX output based on the user's instructions:
    - Replace \\ with \
    - Replace $$ with $
    - Remove \n and \t
    - Collapse multiple spaces into a single space
    - Strip leading/trailing spaces
    """
    # Replace \\ with \
    cleaned = ocr_text.replace('\\\\', '\\')

    # Replace $$ with $
    cleaned = cleaned.replace('$$', '$')

    # Remove \n and \t
    #cleaned = cleaned.replace('\n', 'l')

    # Collapse multiple spaces into single space
    #cleaned = re.sub(r'\\n', '', cleaned)
    cleaned = re.sub(r'\s+', '', cleaned)

    # Strip leading and trailing spaces
    #cleaned = cleaned.strip()

    return cleaned

if __name__ == '__main__':
    # Example usage:
    converter = LatexNodes2Text(
        math_mode='text',
        keep_braced_groups=False
    )
    bew = r'$$( 1 + \lambda V _ {  { D S } } )$$'
    ocr_example = r"$$\n\begin{array} { r } { I _ { \mathrm { D S } } = ( \displaystyle \frac { W } { L } ) I _ { P } ^ { \prime } [ \frac { 3 V _ { \mathrm { D S } } } { V _ { \mathrm { p o } } } - 2 [ \{ \frac { ( V _ { \mathrm { D S } } - V _ { \mathrm { G S } } + V _ { \mathrm { b i } } ) } { V _ { \mathrm { p o } } } \\} ^ { 3 / 2 }   }  {   - \{ \frac { ( - V _ { \mathrm { G S } } + V _ { \mathrm { b i } } ) } { V _ { \mathrm { p o } } } \} ^ { 3 / 2 } ] ( 1 + \lambda V _ { \mathrm { D S } } ) } \end{array}\n$$"
    example = r"I_{\rm DS} = \!\!\left({W \over L}\right)\!I_{P}^{\prime}\Bigg[{3V_{\rm DS} \over V_{\rm po}} - 2\!\left[\left\{{(V_{\rm DS} - V_{\rm GS} + V_{\rm bi}) \over V_{\rm po}}\right\}^{3/2}\right.\hfill\cr\hfill - \left.\left\{{(-V_{\rm GS} + V_{\rm bi}) \over V_{\rm po}}\right\}^{3/2} \right]\Bigg](1 + \lambda V_{\rm DS})\quad\hbox{(1)}}"
    cleaned_formula = converter.latex_to_text(ocr_example)
    cleaned_formula = re.sub(r'\s+', '', cleaned_formula)
    cleaned_example = converter.latex_to_text(normalize_malformed_latex(example))
    print(cleaned_formula)
    print(cleaned_example)
    #expr1 = parse_latex(cleaned_formula)
    #print(cleaned_formula)
    #example = r"$ \begin{array} { r } { I _ { \mathrm { D S } } = ( \displaystyle \frac { W } { L } ) I _ { P } ^ { \prime } [ \frac { 3 V _ { \mathrm { D S } } } { V _ { \mathrm { p o } } } - 2 [ \{ \frac { ( V _ { \mathrm { D S } } - V _ { \mathrm { G S } } + V _ { \mathrm { b i } } ) } { V _ { \mathrm { p o } } } \} ^ { 3 / 2 }   } \\ {   - \{ \frac { ( - V _ { \mathrm { G S } } + V _ { \mathrm { b i } } ) } { V _ { \mathrm { p o } } } \} ^ { 3 / 2 } ] ( 1 + \lambda V _ { \mathrm { D S } } ) }$"


