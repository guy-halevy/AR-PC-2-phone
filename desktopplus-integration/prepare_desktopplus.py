#!/usr/bin/env python3
"""Apply the PhoneXR adapter to the exact Desktop+ v3.6 source tree."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

PIN = "031d74d69f08411a9a9b1030d3d428ac02b93549"
EXPECTED = {'OutputManager.h': '14f856d0c342e900de81552d5bff36b28617315b3463bd1c2c5bace763545625', 'OutputManager.cpp': 'f744a5e7aad7ef79e52c76e1966b9256eca79cb54bd255b2e0300c9d3a1c7dc5', 'DesktopPlus.vcxproj': 'd34fc89b8036ac9ff1b475988b0c2391a6b27420e610bef6b5ec88ed3eb703ad'}


def prepare(root: Path):
    root = root.resolve()
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN:
        raise SystemExit(f"Desktop+ must be pinned to {PIN}, found {head}")
    folder = root / "src/DesktopPlus"
    patches = {
        "OutputManager.h": [("        void BusyUpdate();", "        bool PhoneXRApply(unsigned int index, const float* row_major, float width);\n        void BusyUpdate();")],
        "OutputManager.cpp": [('#include "OutputManager.h"', '#include "OutputManager.h"\n#include "PhoneXRAdapter.h"'),
            ("    UINT64 sync_key = 1; //Key used by duplication threads", "    PhoneXRAdapterTick(*this); // PhoneXR: owning-thread snapshot and mutations\n\n    UINT64 sync_key = 1; //Key used by duplication threads")],
        "DesktopPlus.vcxproj": [('    <ClCompile Include="OutputManager.cpp" />', '    <ClCompile Include="OutputManager.cpp" />\n    <ClCompile Include="PhoneXRAdapter.cpp" />'),
            ('    <ClInclude Include="OutputManager.h" />', '    <ClInclude Include="OutputManager.h" />\n    <ClInclude Include="PhoneXRAdapter.h" />')],
    }
    results = {}
    for filename, replacements in patches.items():
        path = folder / filename
        original = subprocess.check_output(["git", "-C", str(root), "show", f"{PIN}:src/DesktopPlus/{filename}"])
        if hashlib.sha256(original).hexdigest() != EXPECTED[filename]:
            raise SystemExit(f"Pinned source hash mismatch: {filename}")
        text = original.decode("utf-8-sig").replace("\r\n", "\n")
        for before, after in replacements:
            if text.count(before) != 1:
                raise SystemExit(f"Expected exactly one patch anchor in {filename}: {before!r}")
            text = text.replace(before, after)
        current = path.read_text(encoding="utf-8-sig")
        baseline = original.decode("utf-8-sig").replace("\r\n", "\n")
        if current not in (baseline, text):
            raise SystemExit(f"Refusing to overwrite unrelated edits: {path}")
        results[path] = text
    # Validate all patch targets before changing any file. Re-running is idempotent.
    for path, text in results.items():
        path.write_text(text, encoding="utf-8")
    for filename in ("PhoneXRAdapter.cpp", "PhoneXRAdapter.h"):
        shutil.copyfile(Path(__file__).parent / "adapter" / filename, folder / filename)
    print(f"PhoneXR adapter applied to Desktop+ {PIN}: {root}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path, help="Desktop+ git checkout pinned to v3.6")
    prepare(parser.parse_args().upstream)
