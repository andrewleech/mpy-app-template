# mpy-app-template

A [Copier](https://copier.readthedocs.io/) template for MicroPython application projects.

Generates a project with a frozen application, a container-based build, unit tests on the
unix port, type stubs, pre-commit, and CI for GitHub or GitLab.

## Usage

```bash
uv tool install copier
mkdir my_project && cd my_project
copier copy --trust --vcs-ref main git@github.com:andrewleech/mpy-app-template.git .
```

Answer the questions and the project is generated, submodules fetched, the board definition
copied and an initial commit made.

To re-apply the template after it changes:

```bash
copier update --trust --vcs-ref main
```

## What you get

```
my_project
├── .devcontainer.json          VS Code dev container, using the build image
├── .github/workflows/ci.yml    or .gitlab-ci.yml, or both
├── Makefile                    build, test and lint entry points
├── src/firmware/application    frozen application: six modules
├── src/firmware/test           unit tests, run on the unix port
├── src/libs                    library submodules
├── src/micropython             MicroPython (submodule)
├── src/system                  board definition and build output
├── src/unix                    unix port build and hardware simulation
└── tools/initial_setup.py      project setup, re-runnable via `make setup`
```

The application is deliberately small: `boot.py` prepares the filesystem, `main.py` starts
things, `device.py` owns the event loop and task list, `hardware.py` constructs everything
that touches a peripheral, `device_config.py` holds settings and `version.py` reports the
build. It blinks an LED and runs aiorepl, and pulls in no libraries beyond micropython-lib.

## Build containers

Build images are not hardcoded. `tools/initial_setup.py` imports
[mpbuild](https://github.com/mattytrentini/mpbuild) and asks it which container builds the
chosen board, then records the answer in `src/system/build_containers.mk` and writes it into
`.devcontainer.json` and the CI configuration.

Asking mpbuild rather than reading its port table matters: rp2 resolves to a different image
tag, and esp32's ESP-IDF version is derived from the lockfile in the checked-out MicroPython
tree, so it follows the submodule rather than a constant.

Those four copies are kept in step by `make setup`, not by a shared variable. Re-run it after
moving the MicroPython submodule.

## Ports

The `target_port` choices are generated from mpbuild's container table by
`tools/sync_ports.py`, so the list is whatever mpbuild can actually build rather than a
hand-maintained copy. CI fails if the two drift. Regenerate with:

```bash
python3 tools/sync_ports.py          # rewrite the generated block
python3 tools/sync_ports.py --check  # what CI runs
```

Boards are not offered as choices: copier answers every question before MicroPython is
cloned, and there are a few hundred boards across the ports. `template_board` is validated
after the clone instead, and a wrong name lists that port's real boards.

rp2 and esp32 configure boards in cmake and the rest in make, which the generated build
system handles on both sides: the board marker file, the project settings include
(`mpconfigproj.mk` or `mpconfigproj.cmake`) and the default make goal all differ.

Version numbers reach both kinds of build the same way: they are resolved on the host and
passed in through `MICROPY_GIT_TAG`/`MICROPY_GIT_HASH`, which MicroPython's own
`makeversionhdr.py` prefers over its internal lookups.

## Testing the template

```bash
./test_template.sh --all          # generate and build every variant
./test_template.sh stm32-mboot    # just one
./test_template.sh --cleanup      # remove leftover test directories
```

Variants live in `test/*.copier-answers.yml`; adding a file there adds a variant to both the
script and the CI matrix. `.github/workflows/test-template.yml` runs the same variants on
every push.
