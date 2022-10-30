inp2json
========

This is a small Python script that takes an INP file and generates JSON output out of it.

This should make the data easier to read/process further for various purpuses, like a custom input viewer. This can come in handy in situations where such a thing is not available out of the box or does not have the desirable features.

I have tested this with shmupmame 4.2 and current (Wolf)MAME versions. Basically, it should work with anything that records version 3.0 or 3.5 INP files.

All games supported by MAME are supported by inp2json in principle: as more games become supported by MAME, to make inp2json support them as well, the input port reference file must be re-generated ([see here](#generating-the-input-port-reference-file)).

You need Python 3.6 or later, there are no other dependencies.

Basic usage
----------

```inp2json.py -i PATH_TO_INP_FILE```

The JSON is then written to `PATH_TO_INP_FILE.json`.

`inp2json.py` must be able to read the input port reference file (`mame_inputport_ref.gz`).

Synopsis
--------
```
usage: inp2json.new.py [-h] -i INPUT_FILE_PATH [-p [CHECK_PORTS ...]] [-m INPUTPORT_REF_PATH] [-d] [-l]

Convert a MAME input file (INP) to JSON text.

options:
  -h, --help            show this help message and exit
  -i INPUT_FILE_PATH, --input-file-path INPUT_FILE_PATH
                        Path to the MAME INP file that should be converted.
  -p [CHECK_PORTS ...], --check-ports [CHECK_PORTS ...]
                        Whitespace-separated list of port numbers to check. Use the -l/--list-ports option to view possible choices for
                        given INP file. (default: check all available ports)
  -m INPUTPORT_REF_PATH, --inputport-ref-path INPUTPORT_REF_PATH
                        Path to a file containing input port reference data, as generated by the filter_convert_mamexml.py helper. (default:
                        mame_inputport_ref.gz).
  -d, --write-decompressed
                        If specified, the decompressed INP file is written to the filesystem.
  -l, --list-ports      If specified, show available input ports for the game given via the INP file (-i/--input-file-path argument),
                        instead of converting the file.
```

Limitations
-----------

- Only recognizes digital inputs

Generating the input port reference file
----------------------------------------

1. Clone [https://github.com/6t8k/mame](https://github.com/6t8k/mame) and checkout the `infoxml_augment_inputfield_output` branch:

        $ git clone -b infoxml_augment_inputfield_output --single-branch https://github.com/6t8k/mame

2. [Build MAME](https://docs.mamedev.org/initialsetup/compilingmame.html)

3. Generate MAME info XML document:

        $ ./mame -listxml > ./mameinfo.xml

4. Generate input port reference file (requires Python 3.10 or later as I toyed with some newer features here):

        $ python filter_convert_mamexml.py -s mameinfo.xml | gzip --best > mame_inputport_ref.gz

To follow new MAME releases, the branch can simply be rebased onto a more recent release tag. I'll propose the source code changes upstream in hopes that this as well as steps 1 and 2 become obsolete.
