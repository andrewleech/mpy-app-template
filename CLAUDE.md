# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working on this repository.

## What this is

A Copier template producing MicroPython application projects. `copier.yaml` holds the
questions, `template/` the generated tree, `test/` the answer files used by both
`test_template.sh` and CI.

Jinja delimiters are remapped in `_envops`: `[[ variable ]]` and `[% block %]`, so that
`{{ }}` in generated shell and CI files is left alone.

## Editing the template

Changes are only meaningful once generated. After editing:

```bash
./test_template.sh stm32-mboot   # generate and build one variant
./test_template.sh --all         # every variant, slow
```

`mpy_app_template/boards.py` reads the port list from mpbuild's container table and the board
list from one GitHub tree request against the MicroPython repository, filtered the way mpbuild
filters it. `mpy_app_template/cli.py` calls that at startup and passes the result to copier as
the `port_boards` answer; `target_port` and `template_board` take their `choices` from it.

Driving copier directly leaves `port_boards` empty, and the validator on `target_port` says
which command to use. Prefer that over a Jinja extension: copier imports extensions from its
own environment, so a missing one fails with an import error carrying no useful advice.

`test_template.sh` and CI run `uvx --no-cache --from . mpy-new-project`. uv reuses a wheel it
built from a local path without noticing the source changed, so without the flag edits appear
to do nothing. Neither a new commit nor a dirty working tree is enough to make it rebuild,
and neither `--refresh` nor `--reinstall` helps. Installing from git is unaffected.

Two traps in path names:

- A conditional **directory** name must not carry the `.tmpl` suffix.
  `[% if x %]d[% endif %].tmpl` renders to a literal `.tmpl` directory when the
  condition is false. Conditional files are fine, because copier strips the
  suffix and skips the empty name.
- Copier evaluates a question's `default` even when its `when` is false, so a default that
  builds on a skipped answer has to collapse to empty itself. `project_board_name` does this
  for the unix port.

## tools/initial_setup.py

Runs as the copier task and again from `make setup`. It re-execs itself under
`uv run --with mpbuild --with pyyaml` when those imports are missing, so it works from
copier's interpreter and from a bare checkout.

The order in `main()` is load bearing:

1. `git submodule add` clones MicroPython.
2. The board definition is copied out of it.
3. mpbuild is asked for the build containers, which for esp32 reads that tree's IDF lockfile.
4. `make submodules` fetches the port dependencies, which needs the board directory to exist
   and, on the cmake ports, runs inside the build container.

## Ports

`rp2` and `esp32` are cmake based, every other port is make based. That difference shows up
in `src/system/Makefile.tmpl` (board marker file, whether `mkenv.mk` is included, the default
goal, the `submodules` target), in `_update_mpconfig_board` (which file to extend and with
what syntax) and in `mpconfigproj.mk` versus `mpconfigproj.cmake`.

Anything added to the build system needs checking against both sides. `test_template.sh rp2`
is the cheapest way to catch a make-only assumption; esp32 needs a multi-gigabyte image pull.

## mpy-cross and BUILD

The generated Makefile exports `MICROPY_MPYCROSS`. This is not an optimisation. Without it
the cmake ports add their own mpy-cross sub-make, and because `BUILD` is passed to the port
make on the command line, make exports it into that sub-make. mpy-cross then writes its
genhdr into the port's build directory. mpy-cross is a full-featured build, so its module
scan registers modules the port does not compile, and the firmware fails to link against
them. `MICROPY_PY_TSTRINGS`/`mp_module_string` is how this shows up on esp32.

Upstream clears `USER_C_MODULES` and `FROZEN_MANIFEST` in that sub-make
(`py/mkrules.cmake`) but not `BUILD`.

## Version numbers

Resolved on the host by the generated Makefile and exported as
`MICROPY_GIT_TAG`/`MICROPY_GIT_HASH`. MicroPython's `makeversionhdr.py` prefers those over
its own lookups, which is what makes one mechanism work for both build systems and keeps
version tooling out of the build container.

An empty `MICROPY_GIT_TAG` is treated by that script as a failure rather than a reason to
fall back, so it must never be exported or forwarded into a container empty. The Makefile
guards this in two places: the `ifneq` around the export, and `DOCKER_VERSION_ENV`.
