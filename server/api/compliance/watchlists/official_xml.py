from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from api.compliance.watchlists.normalize import build_search_document, join_name_parts


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _direct(parent: ET.Element, *names: str) -> str:
    wanted = {name.casefold() for name in names}
    for child in list(parent):
        if _local(child.tag).casefold() in wanted:
            return (child.text or "").strip()
    return ""


def _elements(root: ET.Element, name: str) -> list[ET.Element]:
    return [el for el in root.iter() if _local(el.tag) == name]


def _record(
    *,
    record_type: str,
    reference: str,
    primary_name: str,
    names: list[str],
    listed_on: str = "",
    data_id: str = "",
    dates_of_birth: list[str] | None = None,
    document_numbers: list[str] | None = None,
    nationalities: list[str] | None = None,
    search_parts: list[str | None] | None = None,
    raw: dict | None = None,
) -> dict[str, Any]:
    clean_names = [name for name in names if name]
    return {
        "record_type": record_type,
        "reference_number": reference[:64],
        "data_id": (data_id or reference)[:32],
        "primary_name": primary_name[:512],
        "listed_on": listed_on[:32],
        "names": clean_names,
        "dates_of_birth": dates_of_birth or [],
        "document_numbers": document_numbers or [],
        "nationalities": nationalities or [],
        "search_document": build_search_document(
            [reference, primary_name, *clean_names, *(search_parts or [])]
        ),
        "raw": raw or {},
    }


def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in records:
        ref = row["reference_number"]
        if not ref or ref in seen:
            continue
        seen.add(ref)
        out.append(row)
    if not out:
        raise ValueError("Official list file has no records")
    return out


def _attr(el: ET.Element, name: str) -> str:
    for key, value in el.attrib.items():
        if _local(key).casefold() == name.casefold():
            return value.strip()
    return ""


def parse_ofac_enhanced(xml_bytes: bytes) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)
    date_generated = ""
    for node in _elements(root, "dataAsOf"):
        date_generated = (node.text or "").strip()
        if date_generated:
            break
    records: list[dict[str, Any]] = []
    for entity in _elements(root, "entity"):
        reference = entity.attrib.get("id", "").strip()
        if not reference:
            continue
        kind = ""
        listed_on = ""
        names: list[str] = []
        primary = ""
        programs: list[str] = []
        for child in list(entity):
            tag = _local(child.tag)
            if tag == "generalInfo":
                for info in child.iter():
                    if _local(info.tag) == "entityType":
                        kind = (info.text or "").strip()
                        break
            elif tag == "sanctionsPrograms":
                for program in child.iter():
                    if _local(program.tag) == "sanctionsProgram" and program.text:
                        programs.append(program.text.strip())
            elif tag == "sanctionsLists":
                for item in child.iter():
                    if _local(item.tag) == "sanctionsList":
                        listed_on = listed_on or _attr(item, "datePublished")
            elif tag == "names":
                for name_el in list(child):
                    if _local(name_el.tag) != "name":
                        continue
                    is_primary = _direct(name_el, "isPrimary").casefold() == "true"
                    full = ""
                    first = ""
                    last = ""
                    for part in name_el.iter():
                        part_tag = _local(part.tag)
                        text = (part.text or "").strip()
                        if not text:
                            continue
                        if part_tag == "formattedFullName" and not full:
                            full = text
                        elif part_tag == "formattedFirstName" and not first:
                            first = text
                        elif part_tag == "formattedLastName" and not last:
                            last = text
                    label = full or join_name_parts(first, last)
                    if not label:
                        continue
                    names.append(label)
                    if is_primary and not primary:
                        primary = label
        if not primary and names:
            primary = names[0]
        record_type = "individual" if "individual" in kind.casefold() else "entity"
        records.append(
            _record(
                record_type=record_type,
                reference=reference,
                primary_name=primary,
                names=names,
                listed_on=listed_on,
                data_id=reference,
                search_parts=[kind, *programs],
                raw={"entityType": kind, "programs": programs},
            )
        )
    return {"date_generated": date_generated, "records": _dedupe(records)}


def _uk_name(name_el: ET.Element) -> str:
    parts = [
        _direct(name_el, f"Name{index}")
        for index in range(1, 7)
    ]
    return join_name_parts(*parts)


def parse_uk_sanctions(xml_bytes: bytes) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)
    date_generated = _direct(root, "DateGenerated")
    records: list[dict[str, Any]] = []
    for node in _elements(root, "Designation"):
        reference = _direct(node, "UniqueID")
        if not reference:
            continue
        kind = _direct(node, "IndividualEntityShip")
        listed_on = _direct(node, "DateDesignated")
        regime = _direct(node, "RegimeName")
        names: list[str] = []
        primary = ""
        for name_el in _elements(node, "Name"):
            label = _uk_name(name_el)
            if not label:
                continue
            names.append(label)
            if "primary" in _direct(name_el, "NameType").casefold() and not primary:
                primary = label
        if not primary and names:
            primary = names[0]
        record_type = "individual" if kind.casefold() == "individual" else "entity"
        records.append(
            _record(
                record_type=record_type,
                reference=reference,
                primary_name=primary,
                names=names,
                listed_on=listed_on,
                search_parts=[kind, regime],
                raw={"regime": regime, "kind": kind},
            )
        )
    return {"date_generated": date_generated, "records": _dedupe(records)}


def parse_eu_fsf(xml_bytes: bytes) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)
    date_generated = _attr(root, "generationDate")
    records: list[dict[str, Any]] = []
    for node in _elements(root, "sanctionEntity"):
        reference = _attr(node, "logicalId")
        if not reference:
            continue
        listed_on = _attr(node, "designationDate")
        kind = ""
        names: list[str] = []
        primary = ""
        countries: list[str] = []
        births: list[str] = []
        for child in list(node):
            tag = _local(child.tag)
            if tag == "subjectType":
                kind = _attr(child, "code")
            elif tag == "nameAlias":
                label = _attr(child, "wholeName")
                if not label:
                    continue
                names.append(label)
                if _attr(child, "strong").casefold() == "true" and not primary:
                    primary = label
            elif tag == "citizenship":
                country = _attr(child, "countryDescription")
                if country:
                    countries.append(country)
            elif tag == "birthdate":
                year = _attr(child, "year") or (child.text or "").strip()
                if year:
                    births.append(year)
        if not primary and names:
            primary = names[0]
        record_type = "individual" if kind.casefold() == "person" else "entity"
        records.append(
            _record(
                record_type=record_type,
                reference=reference,
                primary_name=primary,
                names=names,
                listed_on=listed_on,
                dates_of_birth=births,
                nationalities=countries,
                search_parts=[kind, *births, *countries],
                raw={"subjectType": kind},
            )
        )
    return {"date_generated": date_generated, "records": _dedupe(records)}


def _canada_fields(record: ET.Element) -> dict[str, str]:
    fields: dict[str, str] = {}
    for child in list(record):
        key = _local(child.tag).casefold().replace("_", "")
        fields[key] = (child.text or "").strip()
    return fields


def parse_canada_sema(xml_bytes: bytes) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)
    records: list[dict[str, Any]] = []
    for node in _elements(root, "record"):
        fields = _canada_fields(node)
        item = fields.get("item", "")
        schedule = fields.get("schedule", "")
        reference = "-".join(part for part in (schedule, item) if part)
        if not reference:
            continue
        given = fields.get("givenname", "")
        last = fields.get("lastname", "")
        entity = fields.get("entity", "")
        person = join_name_parts(given, last)
        primary = person or entity
        aliases = [part.strip() for part in fields.get("aliases", "").split(";") if part.strip()]
        names = [primary, *aliases] if primary else aliases
        record_type = "individual" if person else "entity"
        records.append(
            _record(
                record_type=record_type,
                reference=reference,
                primary_name=primary,
                names=names,
                listed_on=fields.get("dateoflisting", ""),
                dates_of_birth=[fields["dateofbirth"]] if fields.get("dateofbirth") else [],
                nationalities=[fields["country"]] if fields.get("country") else [],
                search_parts=[fields.get("country", ""), *aliases],
                raw=fields,
            )
        )
    return {"date_generated": "", "records": _dedupe(records)}
