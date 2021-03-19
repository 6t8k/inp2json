#!/bin/python3

import argparse
from datetime import datetime
import io
import json
import sys
import zlib

parser = argparse.ArgumentParser(
    description="Convert a MAME input file (INP) to JSON text.")
parser.add_argument("-i", "--input-file", type=str,
                    help="The INP file to analyze.")
parser.add_argument("-p", "--check-ports", type=str, default="0,1",
                    help="Comma-separated list of port numbers to check.")
parser.add_argument("-n", "--ports-count", type=int, default=8,
                    help="Count of input ports that were recorded in the INP file (default=8).")
parser.add_argument("-d", "--write-decompressed", action="store_true", default=False,
                    help="If specified, the decompressed INP file is written to the filesystem.")
args = parser.parse_args()


ENDIANNESS = "little"
HEADER_BYTES = 64
SKIP_BYTES = 16 * 0
OFFS_BASETIME = 0x08
OFFS_MAJVERSION = 0x10
OFFS_MINVERSION = 0x11
OFFS_SYSNAME = 0x14
OFFS_APPDESC = 0x20

BASETIME_BYTES = 0x08
SYSNAME_BYTES = 0x0c
APPDESC_BYTES = 0x20

SECONDS_BYTES = 4
ATTOSECONDS_BYTES = 8
CURSPEED_BYTES = 4
DEFVALUE_BYTES = 4
DIGITAL_BYTES = 4

"""
apparently, the following holds true (in most cases):
shmupmame 4.2: number of ports: 8, input ports: 0/1
newer MAME versions: number of ports: 6, input ports: 2/3

we're lazy, and instead of a distinction based on the MAME version,
simply copy the button masks here for now:
"""
BUTTONS = {
    "nemesis": {
        0: {
            0x01: "COIN1",
            0x02: "COIN2",
            0x04: "SERVICE1",
            0x08: "START1",
            0x10: "START2",
        },
        1: {
            0x01: "LEFT",
            0x02: "RIGHT",
            0x04: "UP",
            0x08: "DOWN",
            0x10: "BTN1",
            0x20: "BTN2",
            0x40: "BTN3",
        },
        2: {
            0x01: "COIN1",
            0x02: "COIN2",
            0x04: "SERVICE1",
            0x08: "START1",
            0x10: "START2",
        },
        3: {
            0x01: "LEFT",
            0x02: "RIGHT",
            0x04: "UP",
            0x08: "DOWN",
            0x10: "BTN1",
            0x20: "BTN2",
            0x40: "BTN3",
        },
    },
    "dkong": {
        1: {
            0x01: "RIGHT",
            0x02: "LEFT",
            0x04: "UP",
            0x08: "DOWN",
            0x10: "BTN1",
        },
        2: {
            0x01: "RIGHT",
            0x02: "LEFT",
            0x04: "UP",
            0x08: "DOWN",
            0x10: "BTN1",
        },
        3: {
            0x01: "SERVICE",
            0x02: "UNKNOWN",
            0x04: "START1",
            0x08: "START2",
            0x10: "UNKNOWN",
            0x20: "UNKNOWN",
            0x40: "CUSTOM",
            0x80: "COIN1",
        },
    },
}

BUTTONS_ALIAS = [("gradius", "nemesis"), ]
for alias, parent in BUTTONS_ALIAS:
    BUTTONS[alias] = BUTTONS[parent]


def parse_header_and_decompress(args):
    inp_data = None
    ports_to_check = [int(x) for x in args.check_ports.split(",")]

    with open(args.input_file, "rb") as f:

        header_bytes = f.read(HEADER_BYTES)
        if not header_bytes or not header_bytes[:7] == b"MAMEINP":
            print("Invalid file", file=sys.stderr)
            sys.exit(1)

        basetime = int.from_bytes(
            header_bytes[OFFS_BASETIME:OFFS_BASETIME+BASETIME_BYTES], "little")
        print("Basetime: {} UTC".format(datetime.utcfromtimestamp(
            basetime).strftime('%Y-%m-%d %H:%M:%S')))

        ver_maj = int(header_bytes[OFFS_MAJVERSION])
        ver_min = int(header_bytes[OFFS_MINVERSION])
        if ver_maj != 3 or ver_min not in (0, 5):
            print("Invalid version: {}.{}".format(
                ver_maj, ver_min), file=sys.stderr)
            sys.exit(1)

        sysname = header_bytes[OFFS_SYSNAME:OFFS_SYSNAME +
                               SYSNAME_BYTES].decode("ascii").strip("\0")
        if sysname not in BUTTONS:
            print("Unsupported game: '{}'".format(sysname), file=sys.stderr)
            sys.exit(1)

        for port in ports_to_check:
            if port >= args.ports_count or port not in BUTTONS[sysname]:
                print("Requested port {} is unavailable for game '{}'".format(
                    port, sysname), file=sys.stderr)
                sys.exit(1)

        inp_data = io.BytesIO(zlib.decompress(f.read()))
        inp_data.seek(SKIP_BYTES)

    if args.write_decompressed:
        with open("{}.decompressed".format(args.input_file), "wb") as f:
            f.write(header_bytes)
            f.write(inp_data.read())
            inp_data.seek(0)

    return ver_maj, ver_min, sysname, ports_to_check, inp_data


def read_next_frame_metadata(data):
    seconds_bytes = data.read(SECONDS_BYTES)
    attoseconds_bytes = data.read(ATTOSECONDS_BYTES)
    curspeed_bytes = data.read(CURSPEED_BYTES)

    if not (curspeed_bytes and attoseconds_bytes and seconds_bytes):
        return False

    seconds = int.from_bytes(seconds_bytes, ENDIANNESS)
    attoseconds = int.from_bytes(attoseconds_bytes, ENDIANNESS)
    curspeed = int.from_bytes(curspeed_bytes, ENDIANNESS)

    return seconds, attoseconds, curspeed


def read_next_frame_inputs(data):
    ports_def = dict()
    ports_digital = dict()

    for i in range(args.ports_count):

        next_val = data.read(DEFVALUE_BYTES)
        if not next_val:
            return False

        ports_def[i] = int.from_bytes(next_val, ENDIANNESS)

        next_val = data.read(DIGITAL_BYTES)
        if not next_val:
            return False

        ports_digital[i] = int.from_bytes(next_val, ENDIANNESS)

    return ports_def, ports_digital


def check_button_inputs(button_inputs_def, button_inputs_digital, game, port_num):
    pressed_buttons = []
    for mask, name in BUTTONS[game][port_num].items():
        if button_inputs_digital[port_num] & mask == mask:
            pressed_buttons.append(name)

    if pressed_buttons:
        print(",".join(pressed_buttons))
    return pressed_buttons


def main(args):
    output = list()
    _, _, sysname, ports_to_check, data = parse_header_and_decompress(args)
    frame_no = 0

    while True:
        frame_no += 1

        metadata = read_next_frame_metadata(data)
        if metadata is False:
            break
        seconds, attoseconds, curspeed = metadata

        print("Frame #{} {} {} {}".format(
            frame_no, seconds, attoseconds, curspeed))

        button_inputs = read_next_frame_inputs(data)
        if button_inputs is False:
            break

        button_inputs_def, button_inputs_digital = button_inputs

        next_frame_output = {
            "f": frame_no,
            "s": seconds,
            "as": attoseconds,
            "cs": curspeed,
            "p": {},
        }

        for port_num in ports_to_check:
            next_frame_output["p"][port_num] = check_button_inputs(button_inputs_def,
                                                                   button_inputs_digital,
                                                                   sysname,
                                                                   port_num)

        output.append(next_frame_output)

    print("END OF REPLAY")

    print("Writing JSON...")
    with open("{}.json".format(args.input_file), "w") as f:
        f.write(json.dumps(output))
    print("DONE")


if __name__ == "__main__":
    main(args)
