#!/usr/bin/env python3
"""Inventory the staged or extracted SDK's ELF closure and ABI requirements."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


BASELINE_LIBRARIES = {
    "libc.so.6", "libm.so.6", "libpthread.so.0", "libdl.so.2", "librt.so.1",
    "libutil.so.1", "libresolv.so.2", "libanl.so.1", "libstdc++.so.6", "libgcc_s.so.1",
    "ld-linux-x86-64.so.2",
}
OPTIONAL_LIBRARIES = {
    "libQt6Quick3D.so.6": "Qt Quick 3D spatial audio",
    "libQt6Quick3DRuntimeRender.so.6": "Qt Quick 3D spatial audio",
    "libQt6Quick3DUtils.so.6": "Qt Quick 3D spatial audio",
    "libmysqlclient.so.21": "Qt SQL MySQL driver",
    "libpq.so.5": "Qt SQL PostgreSQL driver",
    "libodbc.so.2": "Qt SQL ODBC driver",
    "libfbclient.so.2": "Qt SQL Firebird driver",
    "libmimerapi.so": "Qt SQL Mimer driver",
    "libclntsh.so.23.1": "Qt SQL Oracle driver",
}
OPTIONAL_PLUGINS = {
    "qt/plugins/platformthemes/libqgtk3.so": "GTK desktop theme",
    "qt/plugins/printsupport/libcupsprintersupport.so": "CUPS printing",
}


def output(*arguments, environment=None):
    return subprocess.run(arguments, env=environment, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, check=False).stdout


def version_key(value):
    return tuple(int(number) for number in re.findall(r"\d+", value))


def inspect(root):
    environment = os.environ.copy()
    library_directories = [root / "qt/lib", root / "support/usr/lib/x86_64-linux-gnu",
                           root / "support/usr/lib/x86_64-linux-gnu/pulseaudio", root / "support/usr/lib"]
    environment["LD_LIBRARY_PATH"] = ":".join(str(path) for path in library_directories)
    records = []
    failures = []
    optional = []
    all_versions = set()
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        dynamic = output("readelf", "--wide", "--dynamic", str(path))
        versions = set(re.findall(r"\b(?:GLIBC|GLIBCXX|CXXABI)_[\d.]+", output("readelf", "--version-info", str(path))))
        all_versions.update(versions)
        needed = re.findall(r"\(NEEDED\).*?\[([^]]+)\]", dynamic)
        loader_output = output("ldd", str(path), environment=environment) if needed else ""
        missing = re.findall(r"^\s*(\S+) => not found", loader_output, re.MULTILINE)
        host = []
        for name, target in re.findall(r"^\s*(\S+) => (/\S+)", loader_output, re.MULTILINE):
            if not Path(target).is_relative_to(root) and name not in BASELINE_LIBRARIES:
                host.append({"library": name, "path": target})
        relative = str(path.relative_to(root))
        optional_plugin = OPTIONAL_PLUGINS.get(relative)
        unexpected = [name for name in missing if name not in OPTIONAL_LIBRARIES]
        if optional_plugin:
            optional.append({"path": relative, "missing": missing,
                             "external_libraries": host, "capabilities": [optional_plugin]})
            unexpected = []
            host = []
        if unexpected or host:
            failures.append({"path": str(path.relative_to(root)), "missing": unexpected, "host_fallback": host})
        if missing:
            optional.append({"path": str(path.relative_to(root)), "missing": missing,
                             "capabilities": sorted({OPTIONAL_LIBRARIES.get(name, "unknown") for name in missing})})
        records.append({"path": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "needed": needed, "runpath": re.findall(r"\((?:RUNPATH|RPATH)\).*?\[([^]]+)\]", dynamic),
                        "required_versions": sorted(versions, key=version_key), "missing": missing})
    essential_paths = []
    for directory in [root / "qt/lib/cmake", root / "qt/lib/pkgconfig"]:
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {".cmake", ".pc"}:
                text = path.read_text(errors="replace")
                if re.search(r"/(?:home/(?:qt|imak|runner)|opt/(?:qt|Qt|varinomics))/", text):
                    essential_paths.append(str(path.relative_to(root)))
    if essential_paths:
        failures.append({"builder_paths_in_discovery": essential_paths})
    broken_symlinks = [str(path.relative_to(root)) for path in root.rglob("*")
                       if path.is_symlink() and not path.exists()]
    broken_required_links = [name for name in broken_symlinks if not name.startswith("support/usr/share/doc/")]
    if broken_required_links:
        failures.append({"broken_required_symlinks": broken_required_links})
    maxima = {}
    for family in ["GLIBC", "GLIBCXX", "CXXABI"]:
        matching = [value for value in all_versions if value.startswith(family + "_")]
        maxima[family] = max(matching, key=version_key) if matching else None
    return {"elf_files": len(records), "abi_maximum": maxima, "optional_unavailable": optional,
            "broken_symlinks": broken_symlinks,
            "failures": failures, "files": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.root.resolve())
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "files"}, indent=2))
    raise SystemExit(1 if result["failures"] else 0)


if __name__ == "__main__":
    main()
