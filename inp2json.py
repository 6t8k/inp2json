#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert a MAME input file (INP) to JSON text."""

import argparse
import gzip
import io
import json
import struct
import sys
import zlib
from datetime import datetime

INPUTPORT_REF_PATH_DEF = "mame_inputport_ref.gz"

HEADER_BYTES = 64
SKIP_BYTES = 16 * 0
OFFS_BASETIME = 0x08
OFFS_MAJVERSION = 0x10
OFFS_MINVERSION = 0x11
OFFS_SYSNAME = 0x14
OFFS_APPDESC = 0x20

BASETIME_BYTES = 0x08
SYSNAME_BYTES = 0x0C
APPDESC_BYTES = 0x20

FRAME_STRUCT_FMT = "<LQL"  # seconds, attoseconds, curspeed
DIGITAL_STRUCT_FMT = "<LL"  # defvalue, digital
ANALOG_STRUCT_FMT = "<LLL?"  # accum, previous, sensitivity, reverse
FRAME_STRUCT_SIZE = struct.calcsize(FRAME_STRUCT_FMT)
DIGITAL_STRUCT_SIZE = struct.calcsize(DIGITAL_STRUCT_FMT)
ANALOG_STRUCT_SIZE = struct.calcsize(ANALOG_STRUCT_FMT)


class UnsupportedGameError(Exception):
    """This exception is raised when inp2json has determined that it does not support a given game."""


class InvalidInpHeaderError(Exception):
    """This exception is raised when an INP file header could not be parsed or was detected as invalid."""


def parse_args():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument(
        "-i",
        "--input-file-path",
        type=str,
        required=True,
        help="Path to the MAME INP file that should be converted.",
    )
    parser.add_argument(
        "-p",
        "--check-ports",
        action="extend",
        nargs="*",
        type=int,
        help="Whitespace-separated list of port numbers to check. Use the -l/--list-ports "
        "option to view possible choices for given INP file. (default: check all available ports)",
    )
    parser.add_argument(
        "-m",
        "--inputport-ref-path",
        type=str,
        default=INPUTPORT_REF_PATH_DEF,
        help="Path to a file containing input port reference data, as generated by the "
        f"filter_convert_mamexml.py helper. (default: {INPUTPORT_REF_PATH_DEF}).",
    )
    parser.add_argument(
        "-d",
        "--write-decompressed",
        action="store_true",
        default=False,
        help="If specified, the decompressed INP file is written to the filesystem.",
    )
    parser.add_argument(
        "-l",
        "--list-ports",
        action="store_true",
        default=False,
        help="If specified, show available input ports for the game given via the INP file "
        "(-i/--input-file-path argument), instead of converting the file.",
    )
    return parser.parse_args()


def parse_header(input_file_path):
    """
    Try to load an INP file from a file system path and partially parse it.

    Return None on failure, else return sysname, header bytes, compressed
    payload bytes, major MAME version and minor MAME version.
    """
    try:
        with open(input_file_path, "rb") as f:
            header_bytes = f.read(HEADER_BYTES)
            if (
                not header_bytes
                or len(header_bytes) < HEADER_BYTES
                or not header_bytes[:8] == b"MAMEINP\0"
            ):
                raise InvalidInpHeaderError("Not a MAME INP file")

            basetime = int.from_bytes(
                header_bytes[OFFS_BASETIME : OFFS_BASETIME + BASETIME_BYTES], "little"
            )
            print(
                "INP file basetime: {} UTC".format(
                    datetime.utcfromtimestamp(basetime).strftime("%Y-%m-%d %H:%M:%S")
                )
            )

            ver_maj = int(header_bytes[OFFS_MAJVERSION])
            ver_min = int(header_bytes[OFFS_MINVERSION])
            if ver_maj != 3 or ver_min not in (0, 5):
                raise InvalidInpHeaderError(f"Invalid version: {ver_maj}.{ver_min}")

            sysname = (
                header_bytes[OFFS_SYSNAME : OFFS_SYSNAME + SYSNAME_BYTES]
                .decode("ascii")
                .strip("\0")
            )
            print(f"INP file sysname: {sysname}")

            appdesc = (
                header_bytes[OFFS_APPDESC : OFFS_APPDESC + APPDESC_BYTES]
                .decode("ascii")
                .strip("\0")
            )
            print(f"INP file appdesc: {appdesc}")

            compressed_payload_bytes = f.read()
            return sysname, header_bytes, compressed_payload_bytes, ver_maj, ver_min
    except (OSError, UnicodeDecodeError, InvalidInpHeaderError) as e:
        print(f"Could not open and parse INP file at '{input_file_path}': {e}")

    return None


def get_iptprt_ref(iptprt_ref_path, sysname):
    """
    Try to load an input port reference file from a file system path.

    The helper `filter_convert_mamexml.py` can be used to generate an input
    port reference file in the expected format.

    Return input reference data for sysname, as well as the MAME build version
    and mameconfig version, if input reference data matching sysname is found.
    Raise UnsupportedGameError if no input reference data matching sysname is
    found. Return None on failure to deal with the given path or file.
    """
    sysname_bytes = sysname.encode("ascii")
    mame_build = None
    mame_config = None
    try:
        with gzip.open(iptprt_ref_path, "rb") as f:
            maybe_mame_info = json.loads(next(f))
            if (
                "mame_build" in maybe_mame_info
                and "mame_config" in maybe_mame_info
                and len(maybe_mame_info) == 2
            ):
                mame_build = maybe_mame_info["mame_build"]
                mame_config = maybe_mame_info["mame_config"]
            else:
                f.seek(0)

            for line in f:
                sysdata = line.split(b"\x00", 1)
                if len(sysdata) != 2:
                    return None
                if sysdata[0] == sysname_bytes:
                    return json.loads(sysdata[1]), mame_build, mame_config
    except OSError as e:
        print(f"Could not open input port reference file: {e}")
    except UnicodeDecodeError:
        print("Failed to unicode decode line")
    except (json.JSONDecodeError, StopIteration):
        print(f"Failed to parse input port reference data at '{iptprt_ref_path}'")
    else:
        raise UnsupportedGameError(
            f"Could not find sysname/machine {sysname} in input port reference data at '{iptprt_ref_path}'"
        )

    return None


def read_next_frame_metadata(data):
    """
    Try to read the next frame metadata.

    This function is designed to be called as part of a
    read_next_frame_metadata->read_next_frame_digital_inputs
    ->read_next_frame_analog_inputs loop in order to iterate over a
    (non-compressed) INP file payload.

    In case not enough data can be read, return None, else return seconds,
    attoseconds and current speed.
    """
    next_data = data.read(FRAME_STRUCT_SIZE)
    if not next_data:
        # Expected end of an INP file payload. If we can't read enough bytes at
        # at any other point, it looks like the payload is truncated/malformed.
        return None

    try:
        return struct.unpack(FRAME_STRUCT_FMT, next_data)
    except struct.error as e:
        print(f"Error when reading next frame metadata: {e}", file=sys.stderr)

    return None


def read_next_frame_digital_inputs(data, ports_count):
    """
    Try to read the next default and active digital input states.

    This function is designed to be called as part of a
    read_next_frame_metadata->read_next_frame_digital_inputs
    ->read_next_frame_analog_inputs loop in order to iterate over a
    (non-compressed) INP file payload.

    In case not enough data can be read, return None. Else, return two mappings
    between port index and bit fields (as ints); one representing default input
    state, the other representing active input state.
    """
    ports_def = {}
    ports_digital = {}

    for i in range(ports_count):
        next_data = data.read(DIGITAL_STRUCT_SIZE)
        try:
            defvalue, digital = struct.unpack(DIGITAL_STRUCT_FMT, next_data)
        except struct.error as e:
            print(f"Error when reading next digital input data: {e}", file=sys.stderr)
            return None

        ports_def[i] = defvalue
        ports_digital[i] = digital

    return ports_def, ports_digital


def read_next_frame_analog_inputs(data, ports_count):
    """
    Try to read the next analog input state.

    This function is designed to be called as part of a
    read_next_frame_metadata->read_next_frame_digital_inputs
    ->read_next_frame_analog_inputs loop in order to iterate over a
    (non-compressed) INP file payload.

    In case not enough data can be read, return None. Else, return True.

    Processing of analog fields is currently not implemented, hence analog
    input state is not returned. This function still has to be called in order
    to be able to correctly traverse INP files that contain analog input
    fields.
    """
    for _ in range(ports_count):
        next_data = data.read(ANALOG_STRUCT_SIZE)
        try:
            struct.unpack(ANALOG_STRUCT_FMT, next_data)
        except struct.error as e:
            print(f"Error when reading next analog input data: {e}", file=sys.stderr)
            return None

    return True  # placeholder


# pylint: disable=unused-argument
def check_digital_inputs(ports_ref, button_inputs_def, button_inputs_digital, port_idx):
    """
    Produce a list of pressed buttons that is both human- and machine-readable.

    Combine reference bit masks of one input port with a bit field
    representing digital input state in order to produce a list of pressed
    buttons.
    """
    pressed_buttons = []
    # We made sure in main() that ports to check are within ports_ref:
    key = list(ports_ref)[port_idx]
    fields = ports_ref[key]
    for mask, aux in fields.items():
        mask = int(mask, base=10)  # sic
        # Concerning ACTIVE_HIGH vs. ACTIVE_LOW fields, we do not need to
        # xor button_inputs_def as MAME already writes normalized values.
        if button_inputs_digital[port_idx] & mask == mask:
            pressed_buttons.append(aux.get("type"))

    if pressed_buttons:
        print(f"{key} {','.join(pressed_buttons)}")
    return pressed_buttons


def iter_inp_payload(ports_ref, inp_data, ports_to_check=None):
    """
    Convert an INP file payload into one list of pressed buttons per frame.

    Return a chronologically sorted list containing one dict per input frame,
    each containing timing data as well as a list of inputs that are active
    during the particular frame.

    The `ports_to_check` argument can be used to ignore specific input ports.
    It takes a list of 0-based port indexes (MAME orders the ports
    alphabetically by name). If it is None, all available ports are taken into
    account.
    """
    output = []
    frame_no = 0
    ports_count = len(ports_ref)

    analog_fields_count = 0
    for p in ports_ref.values():
        analog_fields_count += sum(1 for x in p.values() if x["analog"])

    if ports_to_check is None:
        ports_to_check = range(ports_count)

    while True:
        frame_no += 1

        metadata = read_next_frame_metadata(inp_data)
        if metadata is None:
            break
        seconds, attoseconds, curspeed = metadata

        print(f"Frame #{frame_no} {seconds} {attoseconds} {curspeed}")

        digital_inputs = read_next_frame_digital_inputs(inp_data, ports_count)
        if digital_inputs is None:
            break

        button_inputs_def, button_inputs_digital = digital_inputs

        analog_inputs = read_next_frame_analog_inputs(inp_data, analog_fields_count)
        if analog_inputs is None:
            break

        next_frame_output = {
            "f": frame_no,
            "s": seconds,
            "as": attoseconds,
            "cs": curspeed,
            "p": {},
        }

        for port_idx in ports_to_check:
            next_frame_output["p"][port_idx] = check_digital_inputs(
                ports_ref, button_inputs_def, button_inputs_digital, port_idx
            )

        output.append(next_frame_output)

    print("END OF REPLAY")
    return output


def print_ports(iptprt_ref):
    """Pretty-print information about available input ports to stdout."""
    idx = 0
    for port_name, fields in iptprt_ref.items():
        print(f"{idx} {port_name}")
        for mask, field in fields.items():
            ft = field["type"]
            sn = f" ({field['specific_name']})" if field["specific_name"] else ""
            pl = field["player"] + 1
            ac = (
                "low"
                if field["defvalue"] & int(mask, base=10) == int(mask, base=10)
                else "high"
            )
            an = "analog" if field["analog"] else "nonanalog"
            print(f"\t{ft}{sn}, player {pl}, active {ac}, {an}")
        idx += 1


def main(_args):
    print("Parsing INP file ...")
    parsed_inp_file = parse_header(_args.input_file_path)
    if not parsed_inp_file:
        print("Fatal: no INP file", file=sys.stderr)
        return 1

    sysname, header_bytes, compressed_payload_bytes = parsed_inp_file[:3]

    print(f"Looking up input port reference data for game '{sysname}' ...")
    try:
        iptprt_ref = get_iptprt_ref(_args.inputport_ref_path, sysname)
    except UnsupportedGameError as e:
        print(f"Fatal: game '{sysname}' is not supported: {e}", file=sys.stderr)
        return 1

    if not iptprt_ref:
        print(
            f"Fatal: could not load input port reference file '{_args.inputport_ref_path}'",
            file=sys.stderr,
        )
        return 1

    iptprt_ref, mame_build, mame_config = iptprt_ref
    print(f"Input port reference: {mame_build=} {mame_config=}")

    if _args.list_ports:
        print_ports(iptprt_ref)
        return 0

    if (
        _args.check_ports is not None
    ):  # None is default; checks all available ports. Will be a list otherwise.
        ports_count = len(iptprt_ref)
        for check_port in _args.check_ports:
            if not 0 <= check_port <= ports_count - 1:
                print(
                    f"Requested port {check_port} is unavailable for game '{sysname}'",
                    file=sys.stderr,
                )
                return 1

    inp_data = io.BytesIO(zlib.decompress(compressed_payload_bytes))
    inp_data.seek(SKIP_BYTES)

    if _args.write_decompressed:
        out_path = f"{_args.input_file_path}.decompressed"
        try:
            with open(out_path, "wb") as f:
                f.write(header_bytes)
                f.write(inp_data.read())
                inp_data.seek(0)
        except OSError as e:
            print(f"Fatal: could not write file '{out_path}': {e}", file=sys.stderr)
            return 1

    print("Iterating over INP file payload ...")
    output = iter_inp_payload(iptprt_ref, inp_data, _args.check_ports)

    print("Writing JSON...")
    out_path = f"{_args.input_file_path}.json"
    try:
        with open(out_path, "w", encoding="utf8") as f:
            f.write(json.dumps(output))
    except OSError as e:
        print(f"Fatal: could not write file '{out_path}': {e}", file=sys.stderr)
        return 1

    print("DONE")

    return 0


if __name__ == "__main__":
    args = parse_args()
    sys.exit(main(args))
