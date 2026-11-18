"""Check the checkout and exercise the distributions built from it."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# tlaplus/tlaplus release v1.7.4, tla2tools.jar (TLC 2.19).
TLC_SHA256 = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"


def check_wheel(wheel: Path, work: Path) -> None:
    environment = work / "env"
    venv.EnvBuilder(with_pip=True).create(environment)
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    cli = scripts / ("itera-connect.exe" if os.name == "nt" else "itera-connect")
    subprocess.run(
        [python, "-I", "-m", "pip", "--isolated", "install", "--no-index", "--no-deps", wheel],
        cwd=work,
        check=True,
    )
    # Give the installed CLI and fixture suite a disposable home and state directory.
    env = {k: os.environ[k] for k in ("PATH", "SystemRoot", "TEMP", "TMP") if k in os.environ}
    env.update(HOME=str(work), USERPROFILE=str(work), ITERACONNECT_HOME=str(work / "state"))
    subprocess.run([cli, "init"], cwd=work, env=env, check=True)
    result = subprocess.run(
        [cli, "provider", "list"], cwd=work, env=env, check=True, capture_output=True
    )
    if json.loads(result.stdout)["active_provider"] != "iteracompute":
        raise SystemExit("Installed CLI failed to load the initialized profile")
    subprocess.run(
        [python, "-I", "-m", "unittest", "discover", "-v", "-s", ROOT / "tests", "-t", ROOT],
        cwd=work,
        env=env,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, help="new directory for the verified artifacts")
    parser.add_argument("--tlc-jar", type=Path, help="also check the native journal model with TLC")
    args = parser.parse_args()
    python = sys.executable
    lint_imports = Path(sysconfig.get_path("scripts")) / (
        "lint-imports.exe" if os.name == "nt" else "lint-imports"
    )
    for command in (
        [python, "-m", "ruff", "check", "."],
        [python, "-m", "ruff", "format", "--check", "."],
        [python, "-m", "mypy"],
        [lint_imports],
    ):
        subprocess.run(command, cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        if args.tlc_jar:
            jar = args.tlc_jar.resolve()
            with jar.open("rb") as file:
                if hashlib.file_digest(file, "sha256").hexdigest() != TLC_SHA256:
                    raise SystemExit("Unexpected digest for the TLC release jar")
            subprocess.run(
                ["java", "-cp", jar, "tlc2.TLC", "-metadir", work / "tlc", "NativeJournal"],
                cwd=ROOT / "verification",
                check=True,
            )
        dist = work / "dist"
        subprocess.run([python, "-m", "build", "--outdir", dist], cwd=ROOT, check=True)
        # The default build makes an sdist and builds its wheel from that sdist.
        (wheel,) = dist.glob("*.whl")
        (sdist,) = dist.glob("*.tar.gz")
        check_wheel(wheel, work)
        if args.dist_dir:
            args.dist_dir.mkdir(parents=True, exist_ok=False)
            for artifact in (sdist, wheel):
                shutil.copy2(artifact, args.dist_dir)


if __name__ == "__main__":
    main()
