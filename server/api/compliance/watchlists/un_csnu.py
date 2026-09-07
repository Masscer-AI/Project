from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from api.compliance.watchlists.normalize import build_search_document, join_name_parts

LIST_SLUG = "onu_csnu"
DEFAULT_SOURCE_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"


def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _text(node: ET.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _first_text(parent: ET.Element, tag: str) -> str:
    child = parent.find(tag)
    if child is None:
        for el in parent:
            if _local_tag(el.tag) == tag:
                return _text(el)
        return ""
    return _text(child)


def _all_by_tag(parent: ET.Element, tag: str) -> list[ET.Element]:
    return [el for el in parent if _local_tag(el.tag) == tag]


def element_to_plain(el: ET.Element) -> Any:
    children = list(el)
    if not children:
        return _text(el)
    data: dict[str, Any] = {}
    attribs = {k.split("}", 1)[-1]: v for k, v in el.attrib.items()}
    if attribs:
        data["_attrs"] = attribs
    for child in children:
        tag = _local_tag(child.tag)
        value = element_to_plain(child)
        if tag in data:
            existing = data[tag]
            if not isinstance(existing, list):
                data[tag] = [existing]
            data[tag].append(value)
        else:
            data[tag] = value
    return data


def _flatten_strings(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            if item == value.get("_attrs"):
                continue
            out.extend(_flatten_strings(item))
        return out
    return [str(value)]


def _direct_values(raw: dict, *keys: str) -> list[str]:
    out: list[str] = []
    for key in keys:
        out.extend(_flatten_strings(raw.get(key)))
    return out


def _scalar(raw: dict, key: str) -> str:
    vals = _flatten_strings(raw.get(key))
    return vals[0] if vals else ""


def _name_from_parts(raw: dict) -> str:
    return join_name_parts(
        _scalar(raw, "FIRST_NAME"),
        _scalar(raw, "SECOND_NAME"),
        _scalar(raw, "THIRD_NAME"),
        _scalar(raw, "FOURTH_NAME"),
    )


def _aliases(raw: dict, alias_key: str, name_key: str) -> list[str]:
    block = raw.get(alias_key)
    names: list[str] = []
    for item in block if isinstance(block, list) else ([block] if block else []):
        if isinstance(item, dict):
            names.extend(_flatten_strings(item.get(name_key)))
        else:
            names.extend(_flatten_strings(item))
    return [n for n in names if n]


def _dobs(raw: dict) -> list[str]:
    block = raw.get("INDIVIDUAL_DATE_OF_BIRTH")
    items = block if isinstance(block, list) else ([block] if block else [])
    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        date = _flatten_strings(item.get("DATE"))
        year = _flatten_strings(item.get("YEAR"))
        from_year = _flatten_strings(item.get("FROM_YEAR"))
        to_year = _flatten_strings(item.get("TO_YEAR"))
        if date:
            out.extend(date)
        elif year:
            out.extend(year)
        elif from_year or to_year:
            out.append("-".join(filter(None, [*from_year, *to_year])))
    return out


def _documents(raw: dict) -> list[str]:
    block = raw.get("INDIVIDUAL_DOCUMENT")
    items = block if isinstance(block, list) else ([block] if block else [])
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            out.extend(_flatten_strings(item.get("NUMBER")))
        else:
            out.extend(_flatten_strings(item))
    return [n for n in out if n]


def _nationalities(raw: dict) -> list[str]:
    block = raw.get("NATIONALITY")
    items = block if isinstance(block, list) else ([block] if block else [])
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            out.extend(_flatten_strings(item.get("VALUE")))
        else:
            out.extend(_flatten_strings(item))
    return [n for n in out if n]


def _record_from_element(el: ET.Element, record_type: str) -> dict[str, Any]:
    raw = element_to_plain(el)
    if not isinstance(raw, dict):
        raw = {"value": raw}
    data_id = _first_text(el, "DATAID")
    reference = _first_text(el, "REFERENCE_NUMBER") or (f"DATAID:{data_id}" if data_id else "")
    primary = _name_from_parts(raw)
    alias_key = "INDIVIDUAL_ALIAS" if record_type == "individual" else "ENTITY_ALIAS"
    names = [primary, *_aliases(raw, alias_key, "ALIAS_NAME")]
    names = [n for n in names if n]
    dobs = _dobs(raw) if record_type == "individual" else []
    docs = _documents(raw) if record_type == "individual" else []
    nats = _nationalities(raw)
    comments = _direct_values(raw, "COMMENTS1", "DESIGNATION", "UN_LIST_TYPE", "LIST_TYPE")
    search_document = build_search_document(
        [
            reference,
            data_id,
            *names,
            *dobs,
            *docs,
            *nats,
            *comments,
            *_flatten_strings(raw.get("INDIVIDUAL_PLACE_OF_BIRTH")),
            *_flatten_strings(raw.get("ENTITY_ADDRESS") if record_type == "entity" else raw.get("INDIVIDUAL_ADDRESS")),
        ]
    )
    return {
        "record_type": record_type,
        "reference_number": reference,
        "data_id": data_id,
        "primary_name": primary[:512],
        "listed_on": _first_text(el, "LISTED_ON"),
        "names": names,
        "dates_of_birth": dobs,
        "document_numbers": docs,
        "nationalities": nats,
        "search_document": search_document,
        "raw": raw,
    }


def parse_un_consolidated(xml_bytes: bytes) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)
    date_generated = ""
    for key, value in root.attrib.items():
        if _local_tag(key) == "dateGenerated":
            date_generated = value
            break

    individuals_parent = None
    entities_parent = None
    if _local_tag(root.tag) == "INDIVIDUALS":
        individuals_parent = root
    elif _local_tag(root.tag) == "ENTITIES":
        entities_parent = root
    else:
        for child in root:
            tag = _local_tag(child.tag)
            if tag == "INDIVIDUALS":
                individuals_parent = child
            elif tag == "ENTITIES":
                entities_parent = child

    records: list[dict[str, Any]] = []
    if individuals_parent is not None:
        for node in _all_by_tag(individuals_parent, "INDIVIDUAL"):
            rec = _record_from_element(node, "individual")
            if rec["reference_number"]:
                records.append(rec)
    if entities_parent is not None:
        for node in _all_by_tag(entities_parent, "ENTITY"):
            rec = _record_from_element(node, "entity")
            if rec["reference_number"]:
                records.append(rec)

    return {"date_generated": date_generated, "records": records}
