inp2json
========

This is a small Python script that takes an INP file and generates JSON output out of it.

This should make the data easier to read/process further for various purpuses, like a custom input viewer. This can come in handy in situations where such a thing is not available out of the box or does not have the desirable features.

I have tested this with shmupmame 4.2 and current (Wolf)MAME versions. Basically, it should work with anything that records version 3.0 or 3.5 INP files.

You need Python 3, there are no other dependencies.

Basic usage
----------

```inp2json.py --input-file PATH_TO_INP_FILE --check-ports 0,1```

The JSON is then written to `PATH_TO_INP_FILE.json`.

If you see nonsensical or no button presses at all, you might have to play a bit with the `--check-ports` and/or `--ports-count` arguments.

Limitations
-----------

- Only recognizes digital inputs
- Currently, the only games supported are Nemesis/Gradius, Donkey Kong and Robotron 2084. Games can easily be added by looking up the necessary data in the MAME drivers and incorporating it in line with the existing Nemesis/Gradius data, i.e. [nemesis.cpp](https://github.com/mamedev/mame/blob/c6543e2c9c7afd96a6c16c3bbc16b507f9c93df0/src/mame/drivers/nemesis.cpp#L808).
