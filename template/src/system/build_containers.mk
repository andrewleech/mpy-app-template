# Build containers, resolved from mpbuild by tools/initial_setup.py.
# Re-run `make setup` after changing the MicroPython submodule: the esp32 image
# in particular is derived from that tree's IDF lockfile.
BUILD_CONTAINER = @BUILD_CONTAINER@
UNIX_BUILD_CONTAINER = @UNIX_BUILD_CONTAINER@
