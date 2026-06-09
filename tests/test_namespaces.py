"""
Verify both MSL namespaces resolve through the installed rtc-tools-standard-library.

  Modelica.Units.SI.*  (Units.mo, MSL 4.x)   — current namespace
  Modelica.SIunits.*   (SIunits.mo, MSL 3.x)  — backwards-compat namespace

Exit code: 0 = all pass, 1 = one or more parse failures

Standalone script (not pytest): pymoca is a heavy optional dep installed as a separate CI step.

Usage:
  pip install "pymoca>=0.11,<0.12" rtc-tools-standard-library
  python tests/test_namespaces.py
"""
import sys
import tempfile
from pathlib import Path
from importlib.metadata import entry_points
import importlib.resources

import pymoca.backends.casadi.api as pymoca_api


def library_folders():
    folders = []
    for ep in entry_points(group="rtctools.libraries.modelica"):
        if ep.name == "library_folder":
            folders.append(str(importlib.resources.files(ep.module).joinpath(ep.attr)))
    return folders


def parse(model_name, mo_src, lib_folders):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / f"{model_name}.mo").write_text(mo_src, encoding="utf-8")
        pymoca_api.transfer_model(d, model_name, {"cache": False, "library_folders": lib_folders})


if __name__ == "__main__":
    libs = library_folders()
    failed = False

    for label, name, src in [
        ("Modelica.Units.SI (MSL 4.x)", "TestUnits", "model TestUnits\n  Modelica.Units.SI.Length x = 1.0;\nend TestUnits;\n"),
        ("Modelica.SIunits (MSL 3.x)",  "TestSIunits", "model TestSIunits\n  Modelica.SIunits.Length x = 1.0;\nend TestSIunits;\n"),
    ]:
        try:
            parse(name, src, libs)
            print(f"PASS: {label}")
        except Exception as e:
            print(f"FAIL: {label} — {e}")
            failed = True

    sys.exit(1 if failed else 0)
