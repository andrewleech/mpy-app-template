# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## Project

MicroPython firmware generated from mpy-app-template. `.copier-answers.yml`
records the answers it was generated with.

## Commands

```bash
make submodules   # fetch MicroPython and libraries
make system       # build firmware with the application frozen in
make libs-only    # build with libraries only, no application
make tests        # unit tests on the unix port
make checks       # pre-commit: ruff, mypy, yamllint
make setup        # re-run project setup after a MicroPython bump
```

## Build environment

Builds run in containers chosen by mpbuild for this port, recorded in
`src/system/build_containers.mk` and mirrored into `.devcontainer.json` and the
CI configuration by `tools/initial_setup.py`. Those four copies are kept in step
by `make setup`, not by a shared variable; a MicroPython bump can leave them
stale until it is re-run.

The Makefile sets `RUN_IN_DOCKER=0` when `/.dockerenv` exists or `CI` is set, so
the same targets work on the host, inside the devcontainer and in CI.

Firmware and unix builds use different containers. Static analysis and anything
needing `uv` run on the host: the toolchain images carry no Python tooling.

## Architecture

- `src/firmware/application/` is six modules. `hardware.py` is the only place a
  peripheral is constructed, which is what lets the unix port substitute
  `src/unix/simulation`. Keep it that way when adding hardware.
- `src/manifest.py` is the manifest root, pulling in `libs/` and, unless
  `EXCLUDE_APP=1`, `firmware/`. The board manifest includes it with
  `platform_baremetal=True`; `src/unix/manifest.py` with `False`, which is what
  gates freezing the tests and unittest.
- Version generation goes through `tools/makeversionhdr.py`, which prefers
  `MICROPY_GIT_TAG`/`MICROPY_GIT_HASH` from the environment. An empty value is
  treated as failure rather than a fallback, so never export them empty.

## MicroPython specifics

- Frozen modules throughout, for memory efficiency.
- Type stubs come from `make typings` into `tools/typings`, used as a custom
  typeshed. `src/unix/simulation` is kept off the type paths so `machine`
  resolves to the port stubs.
- Reference `CLAUDE_micropython.md` for MicroPython core guidance. Changes to
  `src/micropython` belong upstream, not vendored here.
