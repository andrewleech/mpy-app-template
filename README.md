# mpy-app-template

A [Copier](https://copier.readthedocs.io/) template for MicroPython application projects.

You answer a handful of questions, and get a project with a frozen application, builds that
run in the right toolchain container, unit tests on the unix port, type stubs wired into mypy
and Pylance, pre-commit, and CI for GitHub or GitLab.

## Creating a project

```bash
uvx --from git+https://github.com/andrewleech/mpy-app-template mpy-new my_project
```

Answering the questions is the whole setup. `tools/initial_setup.py` then registers the
submodules, copies the board definition out of MicroPython, works out which containers build
this port, installs the type stubs and makes the first commit.

`mpy-new` wraps `copier copy`. It reads the port and board lists first and hands them to
copier as answers, which is how the questions can offer a list that matches MicroPython right
now. Running `copier` directly skips that step, and the first question says so.

To pick up template changes later:

```bash
cd my_project
uvx --from git+https://github.com/andrewleech/mpy-app-template mpy-new --update .
```

## Choosing a port and board

The port question offers what mpbuild can build in a container, and the board question then
narrows to the boards that port has. Pick `rp2` and you scroll a list of 38 Pico-family
boards; pick `stm32` and you get 76. Type a few characters to filter.

Both lists are read when `mpy-new` starts, so they match MicroPython as it stands rather than
whenever the template was last touched. Ports come from mpbuild, boards from the MicroPython
repository using the rule mpbuild itself uses to find them (a directory under
`ports/<port>/boards/` holding a `board.json`). One request covers every port.

Set `MPY_BOARDS_REF` to read the boards from a ref other than master.

## Build containers

Build images come from mpbuild, resolved once during setup and recorded in
`src/system/build_containers.mk`, `.devcontainer.json` and the CI configuration.

Asking mpbuild for the answer (rather than reading its port table) is what gets rp2 its
`:bookworm` image tag, and what gets esp32 an ESP-IDF version read from the lockfile in your
MicroPython submodule. Move that submodule and `make setup` brings all four copies back into
step.

```bash
make submodules     # fetch MicroPython and the libraries
make system         # firmware with the application frozen in
make libs-only      # firmware with just the libraries, no application
make mboot          # bootloader (stm32, when enabled)
make deploy-dfu     # flash over DFU
```

Firmware lands in `src/system/build-<BOARD>/`.

## Testing

```bash
make tests       # unit tests on the unix port
make checks      # ruff, mypy, yamllint through pre-commit
make repl-unix   # REPL on the unix port with simulated hardware
make run-unix    # run the application on the unix port
```

`src/unix/simulation` holds stand-ins for the hardware modules the application imports, sized
to what the application actually touches. Grow it alongside `hardware.py`, and keep anything
that depends on real peripheral behaviour in an on-target test.

## The generated application

Six modules, and no libraries beyond micropython-lib:

| Module | Role |
|---|---|
| `boot.py` | filesystem setup, runs first |
| `main.py` | logging, starts the application |
| `device.py` | event loop and the task list |
| `hardware.py` | everything that touches a peripheral |
| `device_config.py` | settings and their defaults |
| `version.py` | reports the build |

It blinks an LED and runs aiorepl. `hardware.py` being the single place a peripheral is
constructed is what lets the unix port swap in `src/unix/simulation`, so keep new hardware
there as the application grows.

USB identifiers stay at the port defaults, so a device enumerates as MicroPython does out of
the box and mboot as a standard ST DFU device.

## Versions

[git-versioner](https://pypi.org/project/git-versioner/) or `git describe`, your pick at
generation time. Either way the version is worked out on the host and handed to the build
through `MICROPY_GIT_TAG` / `MICROPY_GIT_HASH`, which is what lets one mechanism cover the
make-based ports and the cmake ones (rp2, esp32) alike, and keeps the version tooling out of
the container.

```python
import version
print(version.firmware_version)
```

## Working on the template

```bash
./test_template.sh --all          # generate and build every variant
./test_template.sh stm32-mboot    # just one
./test_template.sh --cleanup      # tidy up leftover test directories
```

Variants live in `test/*.copier-answers.yml`, and dropping a new file in there adds it to
both the script and the CI matrix in `.github/workflows/test-template.yml`.
