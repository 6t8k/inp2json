#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helper that generates input port reference data for inp2json.py.

It takes a MAME info XML document (generated via MAME's `-listxml` cli option),
picks out input ports and associated fields for each machine, converts the
result to JSON and writes it to stdout.
"""

import argparse
import collections
import json
import logging
import sys
import xml
import xml.etree.ElementTree as ET
from typing import TypedDict


class InputFieldDto(TypedDict):
    analog: bool
    type: str
    defvalue: int
    specific_name: str | None
    player: int | None


class InputPortDto(TypedDict):
    fields: dict[int, InputFieldDto]
    legacy_order: int | None


LOGLEVEL_DEF = "INFO"
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument(
        "-s",
        "--source-path",
        type=str,
        required=True,
        help="Path to a MAME info XML file.",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        type=str,
        default=LOGLEVEL_DEF,
        help=f"Log level to set. (default: {LOGLEVEL_DEF})",
    )
    return parser.parse_args()


def load_and_parse_xmldoc(
    path: str,
) -> None | collections.abc.Generator[xml.etree.ElementTree.Element, None, None]:
    """
    Try to load and parse an XML document from a file system path.

    Return None on failure.
    Else, return an iterator that incrementally parses the XML
    document into elements. Elements are returned once their starting tags have
    been parsed, so any text contents and tail attributes are skipped.
    """
    try:
        tree_iter = ET.iterparse(path, ["start"])
    except OSError:
        logger.exception("Could not open XML document %s", path)
        return None
    except ET.ParseError:
        logger.exception("Could not parse XML document %s", path)
        return None

    return (elem for _, elem in tree_iter)


def pick_mame_metadata(
    elem_iter: collections.abc.Iterable[xml.etree.ElementTree.Element],
) -> tuple[str, str, dict[str, dict[str, InputPortDto]]]:
    """
    Single out pertinent information from a parsed MAME info XML document.

    Returns MAME build version, mameconfig version, and a dict containing
    every input field for each input port for each machine found.
    """
    # We could change this into a generator in order to improve resource
    # efficiency, but that would make the bookkeeping to see if we encounter
    # the same machine/ports/fields multiple times less pragmatic/partially
    # counteract the improved efficiency again.
    # Since this script is a helper that should only have to be run in order
    # to adopt updated MAME metadata from upstream, which should be needed
    # relatively rarely, we opt for bookkeeping and against a generator here.
    mame_build = ""
    mame_config = ""
    machine_name = None
    inputport_tag = None
    machines: dict[str, dict[str, InputPortDto]] = {}

    for elem in elem_iter:
        if elem.tag == "mame":
            mame_build = elem.get("build", "")
            mame_config = elem.get("mameconfig", "")
        elif elem.tag == "machine":
            machine_name = elem.get("name")
            if not machine_name:
                logger.warning("No machine name, skipping")
            elif elem.get("runnable") == "no":
                # Non-runnable machines are expected to be (constituent) devices,
                # as opposed to (full) game drivers. This is distinct from
                # emulation status/quality, which can be gleaned from the
                # 'driver' element instead.
                logger.warning("Machine %s not runnable, skipping", machine_name)
            else:
                if machines.get(machine_name):
                    logger.warning(
                        "Machine %s already seen, overiding existing entry",
                        machine_name,
                    )
                machines[machine_name] = {}
        elif machine_name and elem.tag == "port":
            if inputport_tag := elem.get("tag"):
                if machines[machine_name].get(inputport_tag):
                    logger.warning(
                        "Port %s %s already seen, overiding existing entry",
                        machine_name,
                        inputport_tag,
                    )
                machines[machine_name][inputport_tag] = {
                    "fields": {},
                    "legacy_order": int(elem.get("_alloc_order", ""))
                    if elem.get("_alloc_order") is not None
                    else None,
                }
            else:
                logger.warning("No input port tag, skipping")
        elif machine_name and inputport_tag and elem.tag in ("nonanalog", "analog"):
            # Currently, analog fields are unsupported by inp2json, but if we
            # encounter one here, we pass it on nevertheless. This way, INP
            # files of games that have analog fields can still be traversed
            # correctly (and any digital fields can still be processed).
            if inputfield_mask := int(elem.get("mask", 0)):
                if machines[machine_name][inputport_tag]["fields"].get(inputfield_mask):
                    logger.warning(
                        "Field %s %s %s already seen, overiding existing entry",
                        machine_name,
                        inputport_tag,
                        inputfield_mask,
                    )
                try:
                    inputfield_type = elem.get("type")
                    if inputfield_type is None:
                        raise KeyError
                    inputfield_defvalue = int(elem.get("defvalue", ""))
                    inputfield_player = (
                        int(elem.get("player", ""))
                        if elem.get("player") is not None
                        else None
                    )
                except (KeyError, ValueError):
                    logger.exception(
                        "Field %s %s %s - missing or abnormal attribute values, skipping",
                        machine_name,
                        inputport_tag,
                        inputfield_mask,
                    )
                else:
                    machines[machine_name][inputport_tag]["fields"][inputfield_mask] = {
                        "analog": elem.tag == "analog",
                        "type": inputfield_type,
                        "defvalue": inputfield_defvalue,
                        # the following attributes may be absent on the part of MAME:
                        "specific_name": elem.get("specific_name"),
                        "player": inputfield_player,
                    }
            else:
                logger.warning(
                    "Port %s %s - no/all-zero input field mask, skipping",
                    machine_name,
                    inputport_tag,
                )

        elem.clear()
        del elem

    return mame_build, mame_config, machines


def main(_args: argparse.Namespace) -> int:
    logger.info("Startig with args: %s", vars(_args))

    logger.info("Parsing XML document ...")
    tree_iter = load_and_parse_xmldoc(_args.source_path)
    if not tree_iter:
        logger.critical("Fatal: no XML document")
        sys.exit(1)

    logger.info("Filtering ...")
    mame_build, mame_config, machines = pick_mame_metadata(tree_iter)

    logger.info("Converting to JSON lines and writing to stdout ...")
    # Write JSON lines in order to avoid using hundreds of megabytes of memory
    # on the reading end while aiming to stay fast and pragmatic enough.
    print(json.dumps({"mame_build": mame_build, "mame_config": mame_config}))
    for machine_name, ports in machines.items():
        print(f"{machine_name}\x00{json.dumps(ports)}")

    logger.info("Done.")

    return 0


if __name__ == "__main__":
    args = parse_args()

    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        "[%(filename)s:%(lineno)s - %(funcName)-20s][%(levelname)-8s] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    numeric_loglevel = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_loglevel, int):
        raise ValueError(f"Invalid log level: {args.log_level}")
    logger.setLevel(numeric_loglevel)

    sys.exit(main(args))
