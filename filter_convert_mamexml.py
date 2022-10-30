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
from enum import IntEnum, auto, unique

LOGLEVEL_DEF = "INFO"
logger = logging.getLogger(__name__)


@unique
class IoportType(IntEnum):
    """These are from src/emu/ioport.h."""

    # pseudo-port types
    IPT_INVALID = 0
    IPT_UNUSED = auto()
    IPT_END = auto()
    IPT_UNKNOWN = auto()
    IPT_PORT = auto()
    IPT_DIPSWITCH = auto()
    IPT_CONFIG = auto()

    # start buttons
    IPT_START1 = auto()
    IPT_START2 = auto()
    IPT_START3 = auto()
    IPT_START4 = auto()
    IPT_START5 = auto()
    IPT_START6 = auto()
    IPT_START7 = auto()
    IPT_START8 = auto()
    IPT_START9 = auto()
    IPT_START10 = auto()

    # coin slots
    IPT_COIN1 = auto()
    IPT_COIN2 = auto()
    IPT_COIN3 = auto()
    IPT_COIN4 = auto()
    IPT_COIN5 = auto()
    IPT_COIN6 = auto()
    IPT_COIN7 = auto()
    IPT_COIN8 = auto()
    IPT_COIN9 = auto()
    IPT_COIN10 = auto()
    IPT_COIN11 = auto()
    IPT_COIN12 = auto()
    IPT_BILL1 = auto()

    # service coin
    IPT_SERVICE1 = auto()
    IPT_SERVICE2 = auto()
    IPT_SERVICE3 = auto()
    IPT_SERVICE4 = auto()

    # tilt inputs
    IPT_TILT1 = auto()
    IPT_TILT2 = auto()
    IPT_TILT3 = auto()
    IPT_TILT4 = auto()

    # misc other digital inputs
    IPT_POWER_ON = auto()
    IPT_POWER_OFF = auto()
    IPT_SERVICE = auto()
    IPT_TILT = auto()
    IPT_INTERLOCK = auto()
    IPT_MEMORY_RESET = auto()
    IPT_VOLUME_UP = auto()
    IPT_VOLUME_DOWN = auto()
    IPT_START = auto()  # use the numbered start button(s) for coin-ops
    IPT_SELECT = auto()
    IPT_KEYPAD = auto()
    IPT_KEYBOARD = auto()

    # digital joystick inputs
    IPT_DIGITAL_JOYSTICK_FIRST = auto()

    # use IPT_JOYSTICK for panels where the player has one single joystick
    IPT_JOYSTICK_UP = auto()
    IPT_JOYSTICK_DOWN = auto()
    IPT_JOYSTICK_LEFT = auto()
    IPT_JOYSTICK_RIGHT = auto()

    # use IPT_JOYSTICKLEFT and IPT_JOYSTICKRIGHT for dual joystick panels
    IPT_JOYSTICKRIGHT_UP = auto()
    IPT_JOYSTICKRIGHT_DOWN = auto()
    IPT_JOYSTICKRIGHT_LEFT = auto()
    IPT_JOYSTICKRIGHT_RIGHT = auto()
    IPT_JOYSTICKLEFT_UP = auto()
    IPT_JOYSTICKLEFT_DOWN = auto()
    IPT_JOYSTICKLEFT_LEFT = auto()
    IPT_JOYSTICKLEFT_RIGHT = auto()

    IPT_DIGITAL_JOYSTICK_LAST = auto()

    # action buttons
    IPT_BUTTON1 = auto()
    IPT_BUTTON2 = auto()
    IPT_BUTTON3 = auto()
    IPT_BUTTON4 = auto()
    IPT_BUTTON5 = auto()
    IPT_BUTTON6 = auto()
    IPT_BUTTON7 = auto()
    IPT_BUTTON8 = auto()
    IPT_BUTTON9 = auto()
    IPT_BUTTON10 = auto()
    IPT_BUTTON11 = auto()
    IPT_BUTTON12 = auto()
    IPT_BUTTON13 = auto()
    IPT_BUTTON14 = auto()
    IPT_BUTTON15 = auto()
    IPT_BUTTON16 = auto()

    # mahjong inputs
    IPT_MAHJONG_FIRST = auto()

    IPT_MAHJONG_A = auto()
    IPT_MAHJONG_B = auto()
    IPT_MAHJONG_C = auto()
    IPT_MAHJONG_D = auto()
    IPT_MAHJONG_E = auto()
    IPT_MAHJONG_F = auto()
    IPT_MAHJONG_G = auto()
    IPT_MAHJONG_H = auto()
    IPT_MAHJONG_I = auto()
    IPT_MAHJONG_J = auto()
    IPT_MAHJONG_K = auto()
    IPT_MAHJONG_L = auto()
    IPT_MAHJONG_M = auto()
    IPT_MAHJONG_N = auto()
    IPT_MAHJONG_O = auto()
    IPT_MAHJONG_P = auto()
    IPT_MAHJONG_Q = auto()
    IPT_MAHJONG_KAN = auto()
    IPT_MAHJONG_PON = auto()
    IPT_MAHJONG_CHI = auto()
    IPT_MAHJONG_REACH = auto()
    IPT_MAHJONG_RON = auto()
    IPT_MAHJONG_FLIP_FLOP = auto()
    IPT_MAHJONG_BET = auto()
    IPT_MAHJONG_SCORE = auto()
    IPT_MAHJONG_DOUBLE_UP = auto()
    IPT_MAHJONG_BIG = auto()
    IPT_MAHJONG_SMALL = auto()
    IPT_MAHJONG_LAST_CHANCE = auto()

    IPT_MAHJONG_LAST = auto()

    # hanafuda inputs
    IPT_HANAFUDA_FIRST = auto()

    IPT_HANAFUDA_A = auto()
    IPT_HANAFUDA_B = auto()
    IPT_HANAFUDA_C = auto()
    IPT_HANAFUDA_D = auto()
    IPT_HANAFUDA_E = auto()
    IPT_HANAFUDA_F = auto()
    IPT_HANAFUDA_G = auto()
    IPT_HANAFUDA_H = auto()
    IPT_HANAFUDA_YES = auto()
    IPT_HANAFUDA_NO = auto()

    IPT_HANAFUDA_LAST = auto()

    # gambling inputs
    IPT_GAMBLING_FIRST = auto()

    IPT_GAMBLE_KEYIN = auto()  # attendant
    IPT_GAMBLE_KEYOUT = auto()  # attendant
    IPT_GAMBLE_SERVICE = auto()  # attendant
    IPT_GAMBLE_BOOK = auto()  # attendant
    IPT_GAMBLE_DOOR = auto()  # attendant
    #  IPT_GAMBLE_DOOR2 = auto()   # many gambling games have several doors.
    #  IPT_GAMBLE_DOOR3 = auto()
    #  IPT_GAMBLE_DOOR4 = auto()
    #  IPT_GAMBLE_DOOR5 = auto()

    IPT_GAMBLE_PAYOUT = auto()  # player
    IPT_GAMBLE_BET = auto()  # player
    IPT_GAMBLE_DEAL = auto()  # player
    IPT_GAMBLE_STAND = auto()  # player
    IPT_GAMBLE_TAKE = auto()  # player
    IPT_GAMBLE_D_UP = auto()  # player
    IPT_GAMBLE_HALF = auto()  # player
    IPT_GAMBLE_HIGH = auto()  # player
    IPT_GAMBLE_LOW = auto()  # player

    # poker-specific inputs
    IPT_POKER_HOLD1 = auto()
    IPT_POKER_HOLD2 = auto()
    IPT_POKER_HOLD3 = auto()
    IPT_POKER_HOLD4 = auto()
    IPT_POKER_HOLD5 = auto()
    IPT_POKER_CANCEL = auto()

    # slot-specific inputs
    IPT_SLOT_STOP1 = auto()
    IPT_SLOT_STOP2 = auto()
    IPT_SLOT_STOP3 = auto()
    IPT_SLOT_STOP4 = auto()
    IPT_SLOT_STOP_ALL = auto()

    IPT_GAMBLING_LAST = auto()

    # analog inputs
    IPT_ANALOG_FIRST = auto()

    IPT_ANALOG_ABSOLUTE_FIRST = auto()

    IPT_AD_STICK_X = auto()  # absolute # autocenter
    IPT_AD_STICK_Y = auto()  # absolute # autocenter
    IPT_AD_STICK_Z = auto()  # absolute # autocenter
    IPT_PADDLE = auto()  # absolute # autocenter
    IPT_PADDLE_V = auto()  # absolute # autocenter
    IPT_PEDAL = auto()  # absolute # autocenter
    IPT_PEDAL2 = auto()  # absolute # autocenter
    IPT_PEDAL3 = auto()  # absolute # autocenter
    IPT_LIGHTGUN_X = auto()  # absolute
    IPT_LIGHTGUN_Y = auto()  # absolute
    IPT_POSITIONAL = auto()  # absolute # autocenter if not wraps
    IPT_POSITIONAL_V = auto()  # absolute # autocenter if not wraps

    IPT_ANALOG_ABSOLUTE_LAST = auto()

    IPT_DIAL = auto()  # relative
    IPT_DIAL_V = auto()  # relative
    IPT_TRACKBALL_X = auto()  # relative
    IPT_TRACKBALL_Y = auto()  # relative
    IPT_MOUSE_X = auto()  # relative
    IPT_MOUSE_Y = auto()  # relative

    IPT_ANALOG_LAST = auto()

    # analog adjuster support
    IPT_ADJUSTER = auto()

    # the following are special codes for user interface handling - not to be used by drivers!
    IPT_UI_FIRST = auto()

    IPT_UI_CONFIGURE = auto()
    IPT_UI_ON_SCREEN_DISPLAY = auto()
    IPT_UI_DEBUG_BREAK = auto()
    IPT_UI_PAUSE = auto()
    IPT_UI_PAUSE_SINGLE = auto()
    IPT_UI_REWIND_SINGLE = auto()
    IPT_UI_RESET_MACHINE = auto()
    IPT_UI_SOFT_RESET = auto()
    IPT_UI_SHOW_GFX = auto()
    IPT_UI_FRAMESKIP_DEC = auto()
    IPT_UI_FRAMESKIP_INC = auto()
    IPT_UI_THROTTLE = auto()
    IPT_UI_FAST_FORWARD = auto()
    IPT_UI_SHOW_FPS = auto()
    IPT_UI_SNAPSHOT = auto()
    IPT_UI_RECORD_MNG = auto()
    IPT_UI_RECORD_AVI = auto()
    IPT_UI_TOGGLE_CHEAT = auto()
    IPT_UI_UP = auto()
    IPT_UI_DOWN = auto()
    IPT_UI_LEFT = auto()
    IPT_UI_RIGHT = auto()
    IPT_UI_HOME = auto()
    IPT_UI_END = auto()
    IPT_UI_PAGE_UP = auto()
    IPT_UI_PAGE_DOWN = auto()
    IPT_UI_FOCUS_NEXT = auto()
    IPT_UI_FOCUS_PREV = auto()
    IPT_UI_SELECT = auto()
    IPT_UI_CANCEL = auto()
    IPT_UI_DISPLAY_COMMENT = auto()
    IPT_UI_CLEAR = auto()
    IPT_UI_ZOOM_IN = auto()
    IPT_UI_ZOOM_OUT = auto()
    IPT_UI_ZOOM_DEFAULT = auto()
    IPT_UI_PREV_GROUP = auto()
    IPT_UI_NEXT_GROUP = auto()
    IPT_UI_ROTATE = auto()
    IPT_UI_SHOW_PROFILER = auto()
    IPT_UI_TOGGLE_UI = auto()
    IPT_UI_RELEASE_POINTER = auto()
    IPT_UI_PASTE = auto()
    IPT_UI_SAVE_STATE = auto()
    IPT_UI_LOAD_STATE = auto()
    IPT_UI_TAPE_START = auto()
    IPT_UI_TAPE_STOP = auto()
    IPT_UI_DATS = auto()
    IPT_UI_FAVORITES = auto()
    IPT_UI_EXPORT = auto()
    IPT_UI_AUDIT = auto()

    # additional OSD-specified UI port types (up to 16)
    IPT_OSD_1 = auto()
    IPT_OSD_2 = auto()
    IPT_OSD_3 = auto()
    IPT_OSD_4 = auto()
    IPT_OSD_5 = auto()
    IPT_OSD_6 = auto()
    IPT_OSD_7 = auto()
    IPT_OSD_8 = auto()
    IPT_OSD_9 = auto()
    IPT_OSD_10 = auto()
    IPT_OSD_11 = auto()
    IPT_OSD_12 = auto()
    IPT_OSD_13 = auto()
    IPT_OSD_14 = auto()
    IPT_OSD_15 = auto()
    IPT_OSD_16 = auto()

    IPT_UI_LAST = auto()

    IPT_OTHER = auto()  # not mapped to standard defaults

    IPT_SPECIAL = auto()  # uninterpreted characters
    IPT_CUSTOM = auto()  # handled by custom code
    IPT_OUTPUT = auto()

    IPT_COUNT = auto()


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
) -> tuple[
    str, str, dict[str, dict[str, dict[int, dict[str, bool | str | int | None]]]]
]:
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
    machines: dict[str, dict[str, dict[int, dict[str, bool | str | int | None]]]] = {}

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
                machines[machine_name][inputport_tag] = {}
            else:
                logger.warning("No input port tag, skipping")
        elif machine_name and inputport_tag and elem.tag in ("nonanalog", "analog"):
            # Currently, analog fields are unsupported by inp2json, but if we
            # encounter one here, we pass it on nevertheless. This way, INP
            # files of games that have analog fields can still be traversed
            # correctly (and any digital fields can still be processed).
            if inputfield_mask := int(elem.get("mask", 0)):
                if machines[machine_name][inputport_tag].get(inputfield_mask):
                    logger.warning(
                        "Field %s %s %s already seen, overiding existing entry",
                        machine_name,
                        inputport_tag,
                        inputfield_mask,
                    )
                try:
                    ioport_type = int(elem.get("type", ""))
                    defvalue = int(elem.get("defvalue", ""))
                    player = int(elem.get("player", ""))
                except ValueError:
                    logger.exception(
                        "Field %s %s %s - missing or abnormal attribute values, skipping",
                        machine_name,
                        inputport_tag,
                        inputfield_mask,
                    )
                else:
                    machines[machine_name][inputport_tag][inputfield_mask] = {
                        "analog": elem.tag == "analog",
                        "type": IoportType(ioport_type).name,
                        "defvalue": defvalue,
                        "specific_name": elem.get(
                            "specific_name"
                        ),  # May be empty on the part of MAME
                        "player": player,
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
