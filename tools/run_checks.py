"""Compile and run the portable checkpoint; does not test the XR product."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
BUILD.mkdir(exist_ok=True)
compiler = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++")
if not compiler:
    raise SystemExit("A C++17 g++ or clang++ compiler is required (set CXX to its executable).")
executable = BUILD / ("test_pose.exe" if os.name == "nt" else "test_pose")
commands = [
    [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
     str(ROOT / "tests/math/test_pose.cpp"), "-o", str(executable)],
    [str(executable)],
    [sys.executable, "-m", "unittest", "discover", "-s", "tests/protocol", "-p", "test_*.py", "-v"],
]
results = []
for command in commands:
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    print(result.stdout, end="", flush=True)
    results.append("COMMAND: " + " ".join(command) + "\nEXIT: " + str(result.returncode)
                   + "\n" + result.stdout)
    if result.returncode:
        (BUILD / "checks.log").write_text("\n".join(results), encoding="utf-8")
        raise SystemExit(result.returncode)
(BUILD / "checks.log").write_text("\n".join(results), encoding="utf-8")
print("Portable checkpoint passed. Android/Windows/SteamVR hardware acceptance remains untested.")
