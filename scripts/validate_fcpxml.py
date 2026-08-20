#!/usr/bin/env python3
"""Perform structural checks on an FCPXML handoff without claiming FCP import parity."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fcpxml", type=Path)
    args = parser.parse_args()
    root = ET.parse(args.fcpxml).getroot()
    errors: list[str] = []
    warnings: list[str] = []
    if root.tag != "fcpxml":
        errors.append("root element is not fcpxml")
    ids = [n.get("id") for n in root.findall("./resources/*") if n.get("id")]
    if len(ids) != len(set(ids)):
        errors.append("duplicate resource ids")
    # `text-style ref=` points at a `text-style-def id=` declared locally inside the same
    # caption/title, NOT at a top-level resource. Same for `<text ref=>`. Collect those ids
    # separately or every caption export reads as a broken reference.
    local_ids = {n.get("id") for n in root.iter("text-style-def") if n.get("id")}
    dup_local = [n.get("id") for n in root.iter("text-style-def") if n.get("id")]
    if len(dup_local) != len(set(dup_local)):
        errors.append("duplicate text-style-def ids")
    refs = {n.get("ref") for n in root.iter() if n.get("ref")}
    unknown = sorted(refs - set(ids) - local_ids)
    if unknown:
        errors.append(f"unknown resource refs: {', '.join(unknown)}")
    for rep in root.findall(".//media-rep"):
        src = rep.get("src", "")
        parsed = urlparse(src)
        if parsed.scheme != "file":
            errors.append(f"non-local media URI: {src}")
        elif not Path(unquote(parsed.path)).exists():
            warnings.append(f"missing media: {unquote(parsed.path)}")
    if root.find(".//sequence/spine") is None:
        errors.append("missing sequence spine")
    version = root.get("version", "").replace(".", "_")
    dtd = Path(f"/Applications/Final Cut Pro.app/Contents/Frameworks/Interchange.framework/Versions/A/Resources/FCPXMLv{version}.dtd")
    dtd_status = "unavailable"
    if dtd.exists():
        # xmllint's --dtdvalid takes a URI, not a plain path. The default FCP install path
        # contains spaces ("Final Cut Pro.app"), which a raw path cannot express: xmllint then
        # reports "xmlSAX2ResolveEntity / Could not parse DTD" and every run looks like an XML
        # error when the XML is fine. Pass a percent-escaped file:// URI instead.
        checked = subprocess.run(
            ["xmllint", "--noout", "--dtdvalid", dtd.as_uri(), str(args.fcpxml)],
            capture_output=True,
            text=True,
            check=False,
        )
        dtd_status = "passed" if checked.returncode == 0 else "failed"
        if checked.returncode:
            errors.append("Final Cut Pro DTD validation failed: " + checked.stderr.strip())
    print(f"resources={len(ids)} refs={len(refs)} dtd={dtd_status} errors={len(errors)} warnings={len(warnings)}")
    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARNING: {message}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
