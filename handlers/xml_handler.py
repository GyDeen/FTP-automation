"""
XML file handler.
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from handlers.base import BaseHandler


class XMLHandler(BaseHandler):
    extensions = {".xml", ".xsl", ".xsd"}

    def validate(self, path: "str | Path") -> bool:
        try:
            ET.parse(path)
            return True
        except Exception:
            return False

    def read(self, path: "str | Path") -> ET.Element:
        """Return an xml.etree.ElementTree.Element."""
        tree = ET.parse(path)
        return tree.getroot()

    def write(self, path: "str | Path", data: Any) -> None:
        """Data may be an ET.Element or a serialized XML string."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, ET.Element):
            tree = ET.ElementTree(data)
            tree.write(path, encoding="utf-8", xml_declaration=True)
        elif isinstance(data, str):
            root = ET.fromstring(data)
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        else:
            raise TypeError(f"Unsupported data type for XMLHandler: {type(data)}")
