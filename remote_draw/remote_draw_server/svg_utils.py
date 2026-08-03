from __future__ import annotations

from xml.dom import minidom
import xml.etree.ElementTree as ET


XML_DECL = '<?xml version="1.0" encoding="UTF-8"?>'


def pretty_xml(xml_str: str) -> str:
    xml_str = (xml_str or "").strip()
    if not xml_str:
        return ""

    try:
        dom = minidom.parseString(xml_str.encode("utf-8"))
        pretty = dom.toprettyxml(indent="  ", newl="\n")

        pretty = "\n".join(line for line in pretty.splitlines() if line.strip())

        lines = pretty.splitlines()
        if lines and lines[0].startswith("<?xml"):
            lines = lines[1:]
        pretty_body = "\n".join(lines).strip()

        return XML_DECL + "\n" + pretty_body

    except Exception:
        if xml_str.startswith("<?xml"):
            lines = xml_str.splitlines()
            while lines and lines[0].startswith("<?xml"):
                lines.pop(0)
            return XML_DECL + "\n" + "\n".join(lines).strip()
        return XML_DECL + "\n" + xml_str


def wrap_svg_like_pyqt(raw_svg_or_children: str, width: int, height: int) -> str:
    raw = (raw_svg_or_children or "").strip()
    if not raw:
        children_xml = ""
    elif raw.lower().startswith("<svg"):
        start = raw.find(">")
        end = raw.lower().rfind("</svg>")
        if start != -1 and end != -1 and end > start:
            children_xml = raw[start + 1 : end].strip()
        else:
            children_xml = raw
    else:
        children_xml = raw

    svg = f"""
<svg width="338.67mm" height="190.5mm" baseProfile="tiny" version="1.2" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
 <title>Vektor-Editor Export from Remote Projection</title>
 <desc>SVG export from Remote Projection</desc>
 <g fill-rule="evenodd" font-family="Segoe UI" font-size="12" font-weight="400" stroke-linecap="square" stroke-linejoin="bevel">
  <g>
   <rect width="{width}" height="{height}"/>
  </g>
{children_xml}
 </g>
</svg>
""".strip()

    return svg