# grobidParseFuncs.py   (lxml version)
import requests, logging
from lxml import etree as ET

# ──────────────────────────────────────────────────────────────
# 0  Constants & tiny helpers
# ──────────────────────────────────────────────────────────────
TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}

def _post_pdf(pdf_bytes: bytes, endpoint: str, *, consolidate: str, timeout: int = 120) -> str:
    """Send a PDF to one Grobid endpoint, return raw TEI XML."""
    files = {"input": ("doc.pdf", pdf_bytes, "application/pdf")}
    data  = {consolidate: "1"}          # 1 = yes, normalise
    r = requests.post(endpoint, files=files, data=data, timeout=timeout)
    r.raise_for_status()
    return r.text


# ──────────────────────────────────────────────────────────────
# 1  Header → IEEE-style JSON
# ──────────────────────────────────────────────────────────────
def _tei_header_to_ieee_json(tei_xml: str) -> dict:
    root = ET.fromstring(tei_xml.encode())       # <TEI …>

    # ---------- basic scalars ----------
    title = root.xpath("string(.//tei:titleStmt/tei:title[@level='a'][@type='main'])",
                       namespaces=TEI_NS)
    doi   = root.xpath("string(.//tei:idno[@type='DOI'])", namespaces=TEI_NS)

    # publication date can sit in <publicationStmt> *or* <imprint>
    date  = root.xpath("string((.//tei:publicationStmt/tei:date "
                       "| .//tei:imprint/tei:date)[1])", namespaces=TEI_NS)
    pubyear = (root.xpath("string((.//tei:publicationStmt/tei:date "
                          "| .//tei:imprint/tei:date)[1]/@when)",
                          namespaces=TEI_NS) or date)[:4]

    publisher = root.xpath("string((.//tei:publicationStmt/tei:publisher "
                           "| .//tei:imprint/tei:publisher)[1])",
                           namespaces=TEI_NS)

    # ---------- authors ----------
    authors = []
    for a in root.xpath(".//tei:analytic/tei:author", namespaces=TEI_NS):
        forenames = a.xpath("tei:persName/tei:forename/text()", namespaces=TEI_NS)
        surname   = a.xpath("string(tei:persName/tei:surname)", namespaces=TEI_NS)
        name = " ".join(forenames + ([surname] if surname else [])).strip()
        if name:
            authors.append(name)
    authors_str = ", ".join(authors)

    # ---------- journal / conference block ----------
    monogr = root.xpath(".//tei:monogr", namespaces=TEI_NS)
    monogr = monogr[0] if monogr else None

    publication_title = (monogr.xpath("string(tei:title[@level='j' or @level='m'][1])",
                                      namespaces=TEI_NS)
                         if monogr is not None else "")

    conf_loc = (monogr.xpath("string(.//tei:meeting//tei:addrLine | "
                             ".//tei:meeting//tei:settlement)",
                             namespaces=TEI_NS)
                if monogr is not None else "")
    content_type = "Conferences" if conf_loc else "Journals"
    subtype      = "IEEE Conference" if conf_loc else "IEEE Journal"

    volume = monogr.xpath("string(.//tei:biblScope[@unit='volume'])",
                          namespaces=TEI_NS) if monogr is not None else ""
    start_page = monogr.xpath("string(.//tei:biblScope[@unit='page']/@from)",
                              namespaces=TEI_NS) if monogr is not None else ""
    end_page   = monogr.xpath("string(.//tei:biblScope[@unit='page']/@to)",
                              namespaces=TEI_NS) if monogr is not None else ""

    abstract = root.xpath("string(.//tei:abstract)", namespaces=TEI_NS)


    return {
        "authors": authors_str or None,
        "title": title or None,
        "doi": doi or None,
        "displayPublicationDate": date or None,
        "publisher": publisher or None,
        "contentTypeDisplay": content_type,
        "subType": subtype,
        "publicationTitle": publication_title or None,
        "confLoc": conf_loc or None,
        "volume": volume or None,
        "startPage": start_page or None,
        "endPage": end_page or None,
        "publicationDate": date or None,
        "publicationYear": pubyear or None,
        "abstract": abstract.strip() or None,
    }


# ──────────────────────────────────────────────────────────────
# 2  References → IEEE-style dict
# ──────────────────────────────────────────────────────────────
def _tei_refs_to_ieee_json(tei_xml: str) -> list[dict]:
    root = ET.fromstring(tei_xml.encode())
    out  = []

    for i, bib in enumerate(root.xpath(".//tei:listBibl/tei:biblStruct",
                                       namespaces=TEI_NS), 1):
        title = bib.xpath("string(./tei:analytic/tei:title[@level='a'][@type='main'] "
                          "| ./tei:analytic/tei:title[1])",
                          namespaces=TEI_NS)

        # author list (many refs have only one)
        authors = []
        for a in bib.xpath("./tei:analytic/tei:author", namespaces=TEI_NS):
            forenames = a.xpath("tei:persName/tei:forename/text()", namespaces=TEI_NS)
            surname   = a.xpath("string(tei:persName/tei:surname)", namespaces=TEI_NS)
            fullname  = " ".join(forenames + ([surname] if surname else [])).strip()
            if fullname:
                authors.append(fullname)

        source = bib.xpath("string(./tei:monogr/tei:title[1])", namespaces=TEI_NS)
        volume = bib.xpath("string(.//tei:biblScope[@unit='volume'])", namespaces=TEI_NS)
        issue  = bib.xpath("string(.//tei:biblScope[@unit='issue'])",  namespaces=TEI_NS)

        # pages:  prefer explicit @from/@to, otherwise text()
        pg_from = bib.xpath("string(.//tei:biblScope[@unit='page']/@from)",
                            namespaces=TEI_NS)
        pg_to   = bib.xpath("string(.//tei:biblScope[@unit='page']/@to)",
                            namespaces=TEI_NS)
        pages   = f"{pg_from}-{pg_to}" if pg_from and pg_to else ""

        year = (bib.xpath("string(.//tei:date/@when)", namespaces=TEI_NS) or
                bib.xpath("string(.//tei:date)", namespaces=TEI_NS))[:4]

        raw_text = bib.xpath(
            "string(./tei:note[@type='raw_reference'])", namespaces=TEI_NS
        ) or None

        conf_city = bib.xpath(
            "string(.//tei:meeting//tei:addrLine | .//tei:meeting//tei:settlement)",
            namespaces=TEI_NS,
        )

        out.append({
            "ref_id": f"ref{i}",
            "title": title or None,
            "authors": authors or None,
            "source": source or None,
            "volume": volume or None,
            "issue no.": issue or None,
            "pages": pages or None,
            "publication year": year or None,
            "raw text": raw_text or None,
        })

    return out
