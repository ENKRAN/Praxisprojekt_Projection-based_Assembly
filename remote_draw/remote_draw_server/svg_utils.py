from xml.dom import minidom
import xml.etree.ElementTree as ET

def pretty_xml(xml_str: str) -> str:
    xml_str = (xml_str or "").strip()
    if not xml_str:
        return ""
    try:
        dom = minidom.parseString(xml_str.encode("utf-8"))
        pretty = dom.toprettyxml(indent="  ", newl="\n")
        pretty = "\n".join(line for line in pretty.splitlines() if line.strip())
        if not pretty.startswith("<?xml"):
            pretty = '<?xml version="1.0" encoding="UTF-8"?>\n' + pretty
        return pretty
    except Exception:
        if not xml_str.startswith("<?xml"):
            return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        return xml_str

def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag

def extract_last_element_svg(full_svg: str) -> str:
    full_svg = (full_svg or "").strip()
    if not full_svg:
        return ""

    try:
        root = ET.fromstring(full_svg)
        if _strip_ns(root.tag).lower() != "svg":
            return ""

        children = list(root)
        if not children:
            return ""

        last = children[-1]

        attrib = dict(root.attrib)
        if "xmlns" not in attrib:
            attrib["xmlns"] = "http://www.w3.org/2000/svg"

        new_root = ET.Element("svg", attrib=attrib)
        last_xml = ET.tostring(last, encoding="unicode", method="xml")
        new_root.append(ET.fromstring(last_xml))
        return ET.tostring(new_root, encoding="unicode", method="xml")
    except Exception:
        return ""

def extract_last_vector_element_xml(full_svg: str) -> str:
    full_svg = (full_svg or "").strip()
    if not full_svg:
        return ""

    try:
        root = ET.fromstring(full_svg)
        if _strip_ns(root.tag).lower() != "svg":
            return ""

        children = list(root)
        if not children:
            return ""

        last = children[-1]
        return ET.tostring(last, encoding="unicode", method="xml")
    except Exception:
        return ""
