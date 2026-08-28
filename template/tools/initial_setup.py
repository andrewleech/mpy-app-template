#!/usr/bin/env python3
"""
Post-generation setup for a project created from mpy-app-template.

Registers the git submodules, copies the board definition out of MicroPython,
asks mpbuild which container builds this port, and installs type stubs.

Re-runnable: `make setup` calls it again after a MicroPython bump so the
recorded build containers track the checked-out tree. mpbuild derives the
esp32 IDF version from ports/esp32/lockfiles, so the answer is only correct
once the submodule is at the intended commit.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Placeholders the template ships; replaced in-place on first run, and replaced
# again from the recorded value on later runs.
BUILD_CONTAINER_TOKEN = "@BUILD_CONTAINER@"
UNIX_CONTAINER_TOKEN = "@UNIX_BUILD_CONTAINER@"

CONTAINERS_MK = PROJECT_DIR / "src" / "system" / "build_containers.mk"

# Files carrying a literal image name. The Makefile reads CONTAINERS_MK instead;
# devcontainer.json and both CI configs cannot include a makefile.
CONTAINER_CONSUMERS = (
    PROJECT_DIR / ".devcontainer.json",
    PROJECT_DIR / ".github" / "workflows" / "ci.yml",
    PROJECT_DIR / ".gitlab-ci.yml",
)

SUBMODULES = (
    ("src/micropython", "https://github.com/micropython/micropython.git"),
    ("src/libs/micropython-lib", "https://github.com/micropython/micropython-lib.git"),
    (
        "src/libs/micropython_unittest_junit",
        "https://gitlab.com/alelec/micropython_unittest_junit.git",
    ),
)

_BOOTSTRAP_ENV = "MPY_TEMPLATE_SETUP_BOOTSTRAPPED"


class Colours:
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    RED = "\033[91m"
    END = "\033[0m"


def info(*args):
    print(Colours.GREEN, end="")
    print(*args, end="")
    print(Colours.END)


def note(*args):
    print(Colours.BLUE, end="")
    print(*args, end="")
    print(Colours.END)


def warn(*args):
    print(Colours.RED, end="")
    print(*args, end="")
    print(Colours.END)


def run(*cmd, check=True, capture=False, cwd=None):
    return subprocess.run(
        [str(c) for c in cmd],
        check=check,
        cwd=cwd or PROJECT_DIR,
        capture_output=capture,
        text=True,
    )


# --------------------------------------------------------------------------
# bootstrap


def ensure_dependencies():
    """Re-exec under uv when the packages this script imports are missing.

    Copier runs tasks with its own interpreter, which has neither mpbuild nor
    PyYAML. Rather than requiring the caller to arrange an environment, run
    ourselves again inside an ephemeral one.
    """
    try:
        import mpbuild  # noqa: F401
        import yaml  # noqa: F401

        return
    except ImportError:
        pass

    if os.environ.get(_BOOTSTRAP_ENV):
        warn("Dependencies still missing after bootstrap; continuing degraded.")
        return

    uv = shutil.which("uv")
    if not uv:
        warn("uv not found: install it to resolve build containers from mpbuild.")
        warn("  https://docs.astral.sh/uv/getting-started/installation/")
        return

    note("Re-running under uv to obtain mpbuild")
    os.environ[_BOOTSTRAP_ENV] = "1"
    os.execvp(
        uv,
        [uv, "run", "--quiet", "--no-project", "--with", "mpbuild", "--with", "pyyaml",
         "python", str(Path(__file__).resolve()), *sys.argv[1:]],
    )


# --------------------------------------------------------------------------
# build containers


def resolve_build_containers(answers):
    """Ask mpbuild which containers build this project.

    Returns (target_image, unix_image). Falls back to mpbuild's static port
    table, and then to an empty string, so a missing mpbuild degrades to a
    warning rather than a failed generation.
    """
    port = answers["target_port"]
    board = answers.get("template_board")

    try:
        from mpbuild import board_database
        from mpbuild.build import BUILD_CONTAINERS, get_build_container
    except ImportError:
        warn("mpbuild unavailable; build container not resolved.")
        warn("Set BUILD_CONTAINER in src/system/build_containers.mk by hand.")
        return "", ""

    unix_image = BUILD_CONTAINERS.get("unix", "")
    if port == "unix":
        return unix_image, unix_image

    target_image = ""
    mpy_dir = PROJECT_DIR / "src" / "micropython"
    if board and (mpy_dir / "ports").is_dir():
        try:
            database = board_database(mpy_dir)
            target_image = get_build_container(database.boards[board])
        except Exception as err:  # noqa: BLE001 - any failure falls back
            note(f"mpbuild board lookup failed ({err}); using the port table.")

    if not target_image:
        target_image = BUILD_CONTAINERS.get(port, "")
    if not target_image:
        warn(f"mpbuild has no container for the {port} port.")

    return target_image, unix_image


def _recorded_containers():
    """Values written by a previous run, so re-runs can replace them."""
    if not CONTAINERS_MK.exists():
        return BUILD_CONTAINER_TOKEN, UNIX_CONTAINER_TOKEN
    text = CONTAINERS_MK.read_text()
    target = re.search(r"^BUILD_CONTAINER\s*=\s*(\S*)", text, re.M)
    unix = re.search(r"^UNIX_BUILD_CONTAINER\s*=\s*(\S*)", text, re.M)
    return (
        (target.group(1) if target and target.group(1) else BUILD_CONTAINER_TOKEN),
        (unix.group(1) if unix and unix.group(1) else UNIX_CONTAINER_TOKEN),
    )


def record_build_containers(target_image, unix_image):
    if not target_image and not unix_image:
        return

    previous_target, previous_unix = _recorded_containers()

    CONTAINERS_MK.parent.mkdir(parents=True, exist_ok=True)
    CONTAINERS_MK.write_text(
        "# Resolved from mpbuild by tools/initial_setup.py. Re-run `make setup`\n"
        "# after changing the MicroPython submodule; the esp32 image in\n"
        "# particular is derived from that tree's IDF lockfile.\n"
        f"BUILD_CONTAINER = {target_image}\n"
        f"UNIX_BUILD_CONTAINER = {unix_image}\n"
    )
    info(f"Build container: {target_image}")
    if unix_image != target_image:
        info(f"Unix build container: {unix_image}")

    for path in CONTAINER_CONSUMERS:
        if not path.exists():
            continue
        text = original = path.read_text()
        if target_image:
            text = text.replace(previous_target, target_image)
        if unix_image:
            text = text.replace(previous_unix, unix_image)
        if text != original:
            path.write_text(text)
            note(f"  updated {path.relative_to(PROJECT_DIR)}")


# --------------------------------------------------------------------------
# submodules


def add_submodules(answers):
    info("Registering git submodules")
    for dest, url in SUBMODULES:
        dest_path = PROJECT_DIR / dest
        if (PROJECT_DIR / ".gitmodules").exists():
            existing = run(
                "git", "config", "--file", ".gitmodules",
                "--get", f"submodule.{dest}.url",
                check=False, capture=True,
            )
            if existing.returncode == 0:
                continue

        # A fresh clone can leave an empty placeholder directory behind.
        if dest_path.is_dir() and not any(dest_path.iterdir()):
            dest_path.rmdir()

        note(f"  {dest} <- {url}")
        run("git", "submodule", "add", "-f", "--depth", "1", url, dest)


def init_submodules():
    info("Checking out submodules")
    run("make", "submodules")


# --------------------------------------------------------------------------
# board definition


def _copy_board_files(src: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)

    for name in sorted(os.listdir(src)):
        if name == "manifest.py":
            # The board's own manifest becomes manifest_base.py; the project
            # manifest.py shipped by the template includes it alongside the
            # application manifest.
            shutil.copyfile(src / name, dest / "manifest_base.py")
            manifest = dest / "manifest.py"
            if manifest.exists() and 'include("manifest_base.py")' not in manifest.read_text():
                with manifest.open("a", encoding="utf-8") as f:
                    f.write('\ninclude("manifest_base.py")\n')
            continue

        if (dest / name).exists():
            continue

        if (src / name).is_file():
            shutil.copy(src / name, dest)
        elif (src / name).is_dir():
            _copy_board_files(src / name, dest / name)


def _update_mpconfig_board(dest: Path):
    """Point the board at the project's build settings.

    rp2 and esp32 configure boards in cmake, every other port in make, so the
    file to extend and the include syntax both differ.
    """
    for name, marker, line in (
        ("mpconfigboard.mk", "mpconfigproj.mk",
         "include $(BOARD_DIR)/../mpconfigproj.mk\n"),
        ("mpconfigboard.cmake", "mpconfigproj.cmake",
         "include(${MICROPY_BOARD_DIR}/../mpconfigproj.cmake)\n"),
    ):
        path = dest / name
        if not path.exists():
            continue
        content = path.read_text()
        if marker not in content:
            path.write_text(content + "\n# Include local project build settings.\n" + line)


def _update_mpconfig_header(dest: Path, answers):
    """Name the board after the project.

    USB identifiers are deliberately left alone: MicroPython's per-port
    defaults are appropriate, and overriding them means claiming vendor and
    product IDs the project does not own.
    """
    path = dest / "mpconfigboard.h"
    if not path.exists():
        return
    content = path.read_text()
    prefix = answers["project_name"].upper()
    if not re.search(rf'#define MICROPY_HW_BOARD_NAME.*"{prefix}-', content):
        content = re.sub(
            r'(#define MICROPY_HW_BOARD_NAME\s+")(.*?")',
            rf"\1{prefix}-\2",
            content,
            count=1,
        )
        path.write_text(content)


def _available_boards(port):
    """Board names this port offers, via mpbuild's board database.

    Boards cannot be offered as copier choices: the questions are answered
    before MicroPython is cloned, and there are a few hundred of them across
    the ports. Validating afterwards gives the same authority and a usable
    error.
    """
    try:
        from mpbuild import board_database

        database = board_database(PROJECT_DIR / "src" / "micropython")
        return sorted(
            name for name, board in database.boards.items()
            if board.port.name == port
        )
    except Exception:  # noqa: BLE001 - fall back to listing the directory
        boards = PROJECT_DIR / "src" / "micropython" / "ports" / port / "boards"
        if not boards.is_dir():
            return []
        return sorted(p.name for p in boards.iterdir() if p.is_dir())


def add_board_files(answers):
    port = answers["target_port"]
    if port == "unix":
        return

    board = answers.get("template_board")
    if not board:
        warn(f"No board selected for the {port} port.")
        raise SystemExit(1)

    dest = PROJECT_DIR / "src" / "system" / answers["project_board_name"]
    src = PROJECT_DIR / "src" / "micropython" / "ports" / port / "boards" / board

    if not src.is_dir():
        warn(f'No board "{board}" in the {port} port.')
        available = _available_boards(port)
        if available:
            note(f"Available boards for {port}:")
            for name in available:
                note(f"  {name}")
            note("Set template_board in .copier-answers.yml and re-run `make setup`.")
        else:
            warn(f"The {port} port has no board definitions in this MicroPython checkout.")
        raise SystemExit(1)

    if not (dest / "mpconfigboard.h").exists():
        info(f'Copying board definition "{board}" from the {port} port')
        _copy_board_files(src, dest)

    _update_mpconfig_board(dest)
    _update_mpconfig_header(dest, answers)


# --------------------------------------------------------------------------
# type stubs


def install_typings(answers):
    """Install MicroPython stubs for the target port.

    Not every port has a published stubs package (nrf has none), so a failure
    here is reported and skipped rather than fatal.
    """
    port = answers["target_port"]
    package = f"micropython-{port}-stubs"
    dest = PROJECT_DIR / "tools" / "typings"

    info(f"Installing {package}")
    result = run("uv", "pip", "install", "--quiet", package, "--target", dest,
                 check=False, capture=True)
    if result.returncode != 0:
        warn(f"Could not install {package}; type checking will not see the port API.")
        if result.stderr:
            note(result.stderr.strip().splitlines()[-1])
        return

    # mypy requires a VERSIONS file at both levels of a custom typeshed.
    (dest / "stdlib" / "os").mkdir(parents=True, exist_ok=True)
    (dest / "stdlib" / "os" / "path.pyi").write_text(
        "from posixpath import __all__ as __all__\n"
    )
    (dest / "stdlib" / "VERSIONS").write_text("os: 3.0-\nsys: 3.0-\nio: 3.0-\n")
    (dest / "VERSIONS").write_text("# Stub versions for MicroPython stubs\n")


# --------------------------------------------------------------------------
# licence


def write_license(answers):
    chosen = answers.get("license", "none")
    available = PROJECT_DIR / "tools" / "licenses"
    if not available.is_dir():
        return

    if chosen != "none":
        text = (available / f"{chosen}.txt").read_text()
        text = text.replace("<YEAR>", str(answers.get("_year", "")) or _this_year())
        text = text.replace("<AUTHOR>", answers.get("author", "") or answers["project_name"])
        (PROJECT_DIR / "LICENSE").write_text(text)
        info(f"Licence: {chosen}")

    shutil.rmtree(available)


def _this_year():
    from datetime import date

    return str(date.today().year)


# --------------------------------------------------------------------------


def init_repository(answers):
    if (PROJECT_DIR / ".git").exists():
        return False
    info("Initialising git repository")
    run("git", "init", "-b", "main")
    if answers.get("project_url"):
        run("git", "remote", "add", "origin", answers["project_url"])
    return True


def run_pre_commit():
    info("Running pre-commit to normalise generated formatting")
    run("git", "add", ".")
    result = run("uvx", "pre-commit", "run", "--all-files", check=False)
    if result.returncode == 127:
        warn("pre-commit unavailable; skipping the formatting pass.")
        return
    run("git", "add", ".")
    run("uvx", "pre-commit", "install", check=False)


def _identity_args(answers):
    """Supply a committer identity when git has none configured.

    A fresh machine or a CI runner has no user.name/user.email, and git exits
    128 rather than committing. Fall back to the answers rather than failing
    generation; the developer can amend afterwards.
    """
    configured = run("git", "config", "user.email", check=False, capture=True)
    if configured.returncode == 0 and configured.stdout.strip():
        return []

    name = answers.get("author") or answers["project_name"]
    note(f'git has no committer identity configured; using "{name}" for the initial commit.')
    return ["-c", f"user.name={name}", "-c", "user.email=noreply@example.invalid"]


def create_initial_commit(answers):
    if run("git", "log", "-1", check=False, capture=True).returncode == 0:
        info("Repository already has history; review and commit the changes.")
        return

    info("Creating the initial commit")
    run("git", "add", ".")
    message = f"Create {answers['project_name']} from mpy-app-template"
    run("git", *_identity_args(answers), "commit", "-m", message, "--no-verify")
    run("git", "tag", "v0.0.1")
    print(run("git", "log", "-1", "--oneline", capture=True).stdout, end="")


def main():
    ensure_dependencies()

    import yaml

    with open(PROJECT_DIR / ".copier-answers.yml", encoding="utf-8") as f:
        answers = yaml.safe_load(f)

    init_repository(answers)

    # Order matters. `git submodule add` clones MicroPython, which both the
    # board copy and the mpbuild container lookup read. `make submodules`
    # then needs the board directory to exist and, on the cmake-based ports,
    # runs inside the build container, so it has to come last.
    add_submodules(answers)
    add_board_files(answers)

    target_image, unix_image = resolve_build_containers(answers)
    record_build_containers(target_image, unix_image)

    init_submodules()

    install_typings(answers)
    write_license(answers)

    run_pre_commit()
    create_initial_commit(answers)

    info("Setup complete")


if __name__ == "__main__":
    main()
