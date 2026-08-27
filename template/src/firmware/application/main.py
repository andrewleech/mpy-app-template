"""
Run on power on or reset, after boot.py.

Kept minimal so the hardware is largely untouched at startup. Set
device_config.AUTORUN to False to reach the REPL without starting the
application, then call run() by hand.
"""

import logging

import device_config

logging.basicConfig(level=device_config.LOG_LEVEL)
log = logging.getLogger("main")


def run():
    import device

    device.run()


if device_config.AUTORUN:
    run()
