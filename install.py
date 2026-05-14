#!/usr/bin/env python3
"""
App Review Analyzer — portable installer.

Cross-platform: works on Windows, macOS, and Linux.

Usage:
    python install.py              # interactive (asks about optional deps)
    python install.py --yes        # accept all defaults (install playwright, skip anthropic)
    python install.py --no-venv    # install into the current environment (skip venv creation)
    python install.py --venv .env  # use a different venv directory

The interactive setup.sh / setup.ps1 wrappers just call into this script after
picking a usable Python interpreter — all real install logic lives here.

Dependency versions are parsed from requirements.txt (single source of truth).
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Force UTF-8 on our own stdout/stderr — protects against LC_ALL=C / minimal-container
# environments where Python's default IO encoding is ASCII and prints with non-ASCII
# chars (e.g. progress arrows, future review-text logging) would UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MIN_PY = (3, 10)

# ANSI color codes — disabled on Windows CMD where they don't render
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
USE_COLOR = sys.stdout.isatty() and not (IS_WINDOWS and not os.environ.get("WT_SESSION"))
GREEN = "\033[0;32m" if USE_COLOR else ""
YELLOW = "\033[1;33m" if USE_COLOR else ""
RED = "\033[0;31m" if USE_COLOR else ""
NC = "\033[0m" if USE_COLOR else ""


def info(msg: str) -> None:
    print(f"{GREEN}→{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}! {msg}{NC}")


def fail(msg: str) -> None:
    print(f"{RED}ERROR:{NC} {msg}", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────
# Dependency manifest — parsed from requirements.txt
# ──────────────────────────────────────────────────────────────────

def parse_requirements(req_file: Path) -> tuple[list[str], dict[str, str]]:
    """Parse requirements.txt → (core_specs, optional_by_name).

    Splits on the '# CORE' and '# OPTIONAL' section headers. Stripped of
    inline comments. Preserves version specs (e.g. 'pandas>=2.0.0').
    """
    if not req_file.exists():
        fail(f"requirements.txt not found at {req_file}")
        sys.exit(1)

    section: str | None = None
    core: list[str] = []
    optional: dict[str, str] = {}

    for raw in req_file.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            header = stripped.lstrip("#").strip().upper()
            if header.startswith("CORE"):
                section = "core"
            elif header.startswith("OPTIONAL"):
                section = "optional"
            continue
        # Strip inline comments and surrounding whitespace
        spec = raw.split("#", 1)[0].strip()
        if not spec:
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)", spec)
        if not m:
            warn(f"Ignoring unparseable requirements.txt line: {raw!r}")
            continue
        name = m.group(1).lower()
        if section == "core":
            core.append(spec)
        elif section == "optional":
            optional[name] = spec
        else:
            warn(f"Requirement '{spec}' before a '# CORE' or '# OPTIONAL' section header — skipping")

    if not core:
        fail("requirements.txt has no CORE section or it's empty")
        sys.exit(1)
    return core, optional


# ──────────────────────────────────────────────────────────────────
# Platform / Python sanity
# ──────────────────────────────────────────────────────────────────

def check_python_version() -> None:
    if sys.version_info < MIN_PY:
        fail(
            f"Python {MIN_PY[0]}.{MIN_PY[1]}+ required, but this is "
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} at {sys.executable}"
        )
        print("Install a newer Python from https://www.python.org/downloads/")
        sys.exit(1)


def check_architecture() -> None:
    """Refuse mismatched-arch Pythons that will fail to build native deps.

    Apple Silicon Mac running an x86_64 Python: pandas/numpy source builds fail
    because the toolchain links for x86_64 but loader requires arm64.

    Windows-on-ARM running an x86/AMD64 Python (emulated): same problem class.
    """
    py_arch = platform.machine().upper()

    if sys.platform == "darwin":
        sys_arch = platform.uname().machine.upper()
        if sys_arch == "ARM64" and py_arch not in ("ARM64", "AARCH64"):
            fail(
                f"This Mac is arm64 (Apple Silicon) but Python at {sys.executable} "
                f"is {py_arch}. Native deps like pandas will fail to build."
            )
            print("Install the universal2 / arm64 Python from python.org and re-run.")
            sys.exit(1)
    elif sys.platform == "win32":
        # Under emulation, PROCESSOR_ARCHITECTURE shows what the SHELL was launched as.
        # PROCESSOR_ARCHITEW6432 leaks the real host arch when running under WOW64.
        real_arch = (os.environ.get("PROCESSOR_ARCHITEW6432")
                     or os.environ.get("PROCESSOR_ARCHITECTURE", "")).upper()
        if real_arch == "ARM64" and py_arch not in ("ARM64", "AARCH64"):
            fail(
                f"Windows-on-ARM detected, but Python at {sys.executable} is {py_arch}. "
                f"Native deps will fail to build under emulation."
            )
            print("Install the ARM64 build of Python from https://www.python.org/downloads/")
            sys.exit(1)


def is_externally_managed(python_exe: Path | str) -> bool:
    """Check if this Python interpreter is PEP 668 externally-managed.

    Some distributions (Debian/Ubuntu 23.04+, recent macOS framework Python,
    Homebrew Python) ship an EXTERNALLY-MANAGED marker that blocks `pip install`
    into the system Python. We detect it so we can give a useful error rather
    than letting pip fail with a wall of text.
    """
    try:
        out = subprocess.check_output(
            [str(python_exe), "-c",
             "import sysconfig, sys; print(sysconfig.get_paths()['stdlib'])"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return (Path(out) / "EXTERNALLY-MANAGED").exists()
    except (subprocess.CalledProcessError, OSError):
        return False


# ──────────────────────────────────────────────────────────────────
# venv
# ──────────────────────────────────────────────────────────────────

def venv_python_path(venv_dir: Path) -> Path:
    if IS_WINDOWS:
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_is_healthy(venv_dir: Path) -> tuple[bool, str]:
    """Return (healthy?, reason). Healthy = python >= MIN_PY AND arch matches host."""
    py = venv_python_path(venv_dir)
    if not py.exists():
        return False, f"missing interpreter at {py}"
    try:
        probe = subprocess.check_output(
            [str(py), "-c",
             "import sys, platform; "
             "print(f'{sys.version_info.major}.{sys.version_info.minor}|{platform.machine()}')"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except (subprocess.CalledProcessError, OSError) as e:
        return False, f"could not probe interpreter ({e})"

    try:
        ver_str, venv_arch = probe.split("|", 1)
        major, minor = (int(x) for x in ver_str.split(".", 1))
    except ValueError:
        return False, f"unparseable probe output {probe!r}"

    if (major, minor) < MIN_PY:
        return False, f"Python {major}.{minor} < required {MIN_PY[0]}.{MIN_PY[1]}"

    host_arch = platform.machine().lower()
    if venv_arch.lower() != host_arch:
        return False, f"arch mismatch (venv={venv_arch}, host={host_arch})"

    return True, "ok"


def make_venv(venv_dir: Path, accept_all: bool) -> Path:
    """Create venv (or reuse healthy existing one), return path to python executable."""
    if venv_dir.exists():
        ok, reason = venv_is_healthy(venv_dir)
        if ok:
            info(f"Reusing healthy venv at {venv_dir}")
        else:
            warn(f"Existing venv at {venv_dir} is unhealthy: {reason}")
            if accept_all:
                info(f"--yes given → recreating venv")
                shutil.rmtree(venv_dir)
            else:
                reply = input(f"  Delete and recreate {venv_dir}? [Y/n] ").strip().lower()
                if reply in ("", "y", "yes"):
                    shutil.rmtree(venv_dir)
                else:
                    fail("Cannot proceed with an unhealthy venv. Re-run with a different --venv path or delete it manually.")
                    sys.exit(1)

    if not venv_dir.exists():
        info(f"Creating virtual environment at {venv_dir}")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

    py = venv_python_path(venv_dir)
    if not py.exists():
        fail(f"venv created but python not found at {py}")
        sys.exit(1)
    return py


# ──────────────────────────────────────────────────────────────────
# pip helpers (split for clarity — pip_install for packages, pip_upgrade for flags)
# ──────────────────────────────────────────────────────────────────

def _pip_cmd(python_exe: Path | str, *args: str, quiet: bool = True) -> list[str]:
    cmd = [str(python_exe), "-m", "pip", "install"]
    if quiet:
        cmd.append("--quiet")
    cmd.extend(args)
    return cmd


def pip_install(python_exe: Path | str, *packages: str, user: bool = False, quiet: bool = True) -> None:
    extra: list[str] = []
    if user:
        extra.append("--user")
    subprocess.check_call(_pip_cmd(python_exe, *extra, *packages, quiet=quiet))


def pip_upgrade(python_exe: Path | str, *packages: str, quiet: bool = True) -> None:
    subprocess.check_call(_pip_cmd(python_exe, "--upgrade", *packages, quiet=quiet))


# ──────────────────────────────────────────────────────────────────
# Misc helpers
# ──────────────────────────────────────────────────────────────────

def ask_yes_no(prompt: str, default_yes: bool, accept_all: bool) -> bool:
    if accept_all:
        return default_yes
    suffix = "[Y/n]" if default_yes else "[y/N]"
    while True:
        reply = input(f"  {prompt} {suffix} ").strip().lower()
        if not reply:
            return default_yes
        if reply in ("y", "yes"):
            return True
        if reply in ("n", "no"):
            return False


def smoke_test(python_exe: Path | str) -> None:
    info("Running smoke test...")
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [
        str(python_exe), "-c",
        "from scripts.theme_tagger import load_taxonomy, list_available_taxonomies\n"
        "tax = load_taxonomy('general')\n"
        "print(f'  Loaded \"{tax[\"label\"]}\": {len(tax[\"negative_themes\"])} negative + {len(tax[\"positive_themes\"])} positive themes')\n"
        "print(f'  Available taxonomies: {len(list_available_taxonomies())}')\n",
    ]
    subprocess.check_call(cmd, cwd=str(Path(__file__).parent), env=env)


def activation_hint(venv_dir: Path) -> str:
    if IS_WINDOWS:
        return f"  {venv_dir}\\Scripts\\Activate.ps1     (PowerShell)\n  {venv_dir}\\Scripts\\activate.bat    (CMD)"
    return f"  source {venv_dir}/bin/activate"


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Install App Review Analyzer.")
    parser.add_argument("--yes", action="store_true",
                        help="Accept all defaults non-interactively.")
    parser.add_argument("--no-venv", action="store_true",
                        help="Install into the current Python environment instead of creating a venv.")
    parser.add_argument("--venv", default=".venv",
                        help="Path to virtual environment (default: .venv)")
    parser.add_argument("--with-anthropic", action="store_true",
                        help="Also install the anthropic SDK (skipped by default).")
    parser.add_argument("--no-playwright", action="store_true",
                        help="Skip playwright + Chromium install.")
    parser.add_argument("--user", action="store_true",
                        help="With --no-venv, install with pip --user instead of system-wide.")
    args = parser.parse_args()

    print(f"{GREEN}App Review Analyzer — installer{NC}\n")

    check_python_version()
    check_architecture()
    info(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} "
         f"({platform.machine()}) at {sys.executable}")

    project_dir = Path(__file__).resolve().parent
    os.chdir(project_dir)

    # Parse dependency manifest from requirements.txt
    core_specs, optional_specs = parse_requirements(project_dir / "requirements.txt")
    playwright_spec = optional_specs.get("playwright", "playwright")
    anthropic_spec = optional_specs.get("anthropic", "anthropic")

    # ───── venv vs --no-venv ─────
    use_user = False
    if args.no_venv:
        warn("Skipping venv creation — installing into current environment")
        python_exe: Path | str = sys.executable
        in_venv = sys.prefix != sys.base_prefix

        if not in_venv:
            if is_externally_managed(python_exe):
                if args.user:
                    use_user = True
                    info("Detected PEP 668 externally-managed Python — using --user installs")
                else:
                    fail(
                        f"{sys.executable} is marked EXTERNALLY-MANAGED (PEP 668). "
                        f"Re-run with --user, or drop --no-venv to create a virtual environment."
                    )
                    return 1
            elif not args.yes:
                warn("You're not in a venv. Packages will install globally.")
                if not ask_yes_no("Continue anyway?", default_yes=False, accept_all=False):
                    info("Aborted — re-run without --no-venv to use a virtual environment.")
                    return 1
    else:
        venv_path = project_dir / args.venv
        python_exe = make_venv(venv_path, accept_all=args.yes)
        info(f"Activated  ({python_exe})")
        info("Upgrading pip / wheel / setuptools in venv")
        pip_upgrade(python_exe, "pip", "wheel", "setuptools")

    # ───── core deps ─────
    info("Installing core dependencies from requirements.txt")
    pip_install(python_exe, *core_specs, user=use_user)

    # ───── optional: playwright ─────
    print()
    print(f"{YELLOW}Optional dependencies:{NC}\n")
    install_pw = not args.no_playwright and ask_yes_no(
        "Install playwright for PDF output? (downloads ~150MB Chromium from Microsoft's CDN)",
        default_yes=True, accept_all=args.yes
    )
    if install_pw:
        pip_install(python_exe, playwright_spec, user=use_user)
        info("Downloading Chromium for headless rendering (~150MB)...")

        # --with-deps is only meaningful on Linux (it sudo-installs system libs).
        # On non-Linux it errors. On non-interactive shells it hangs on sudo prompt.
        use_with_deps = IS_LINUX and sys.stdin.isatty()
        pw_args = ["install", "chromium"]
        if use_with_deps:
            pw_args.append("--with-deps")
        try:
            subprocess.check_call([str(python_exe), "-m", "playwright", *pw_args])
        except subprocess.CalledProcessError:
            if use_with_deps:
                # --with-deps may have hit a sudo issue; retry without it
                warn("--with-deps failed; retrying without (system libs may need manual install)")
                subprocess.check_call([str(python_exe), "-m", "playwright", "install", "chromium"])
            else:
                raise
        info("PDF generation ready")
    else:
        warn("Skipped playwright — PDF format will not work")

    # ───── optional: anthropic ─────
    install_anthropic = args.with_anthropic or ask_yes_no(
        "Install anthropic for LLM-powered theme tagging?",
        default_yes=False, accept_all=args.yes
    )
    if install_anthropic:
        pip_install(python_exe, anthropic_spec, user=use_user)
        info("Anthropic SDK installed — set ANTHROPIC_API_KEY before using --llm-tagging")
    else:
        warn("Skipped anthropic — keyword tagging still works fine")

    # ───── smoke test ─────
    print()
    try:
        smoke_test(python_exe)
    except subprocess.CalledProcessError as e:
        fail(f"Smoke test failed: {e}")
        return 1

    print()
    print(f"{GREEN}✓ Setup complete.{NC}\n")
    if not args.no_venv:
        print("Activate the venv in future shells with:")
        print(activation_hint(project_dir / args.venv))
        print()
    print("Try it:\n")
    if IS_WINDOWS:
        print("  python -m scripts.run_pipeline ^")
    else:
        print("  python -m scripts.run_pipeline \\")
    print("      --play com.duolingo \\")
    print("      --appstore 570060128 \\")
    print("      --formats html,excel,csv \\")
    print("      --output ./output/duolingo\n")
    print('Or in Claude:  "Analyze reviews for Duolingo on both stores"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
