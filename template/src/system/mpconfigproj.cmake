# Included from mpconfigboard.cmake. The cmake-based ports (rp2, esp32)
# take the frozen manifest from a cmake variable rather than a make one.
set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest.py)
