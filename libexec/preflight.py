#!/usr/bin/env python3
"""Check the extracted SDK and its declared host ABI without configuring a build."""

import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile


def version_tuple(value):
    return tuple(int(part) for part in value.split("."))


def main():
    sdk_root = Path(__file__).resolve().parent.parent
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)
            print(f"FAIL: {message}", file=sys.stderr)

    def run(arguments):
        try:
            result = subprocess.run(arguments, capture_output=True, text=True, check=False)
        except OSError as error:
            require(False, f"Cannot run {arguments[0]}: {error}")
            return ""
        require(result.returncode == 0, f"{' '.join(map(str, arguments))}: {result.stderr.strip()}")
        return result.stdout.strip()

    manifest_path = sdk_root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, ValueError) as error:
        print(f"FAIL: Cannot read {manifest_path}: {error}", file=sys.stderr)
        return 1

    requirements = manifest["platform"]
    print(f"SDK: {manifest['sdk_version']} at {sdk_root}")
    require(platform.system() == "Linux", "The SDK requires Linux.")
    require(platform.machine() == requirements["architecture"], "The SDK requires x86_64.")
    libc_name, libc_version = platform.libc_ver()
    print(f"Host: {platform.system()} {platform.machine()}, {libc_name} {libc_version}")
    print(f"Vendor CPU baseline: {requirements['cpu_baseline']}")
    require(libc_name == "glibc", "The host must use glibc.")
    if libc_version:
        require(
            version_tuple(libc_version) >= version_tuple(requirements["glibc_minimum"]),
            f"glibc >= {requirements['glibc_minimum']} is required.",
        )
    else:
        require(False, "Cannot determine the host glibc version.")

    try:
        with tempfile.TemporaryFile(dir=sdk_root):
            pass
    except OSError as error:
        require(False, f"Extract the SDK into a writable directory: {error}")

    for executable in ("bash", "tar", "sha256sum", "readlink", "mktemp", "ldd", "gcc", "g++"):
        require(shutil.which(executable) is not None, f"Required host tool is missing: {executable}")

    compiler_version = run(["g++", "-dumpfullversion", "-dumpversion"])
    if compiler_version:
        print(f"Host G++: {compiler_version}")
        require(
            int(compiler_version.split(".")[0]) >= requirements["gcc_major_minimum"],
            f"GCC >= {requirements['gcc_major_minimum']} is required.",
        )
        standard_library = run(["g++", "-print-file-name=libstdc++.so.6"])
        try:
            symbols = set(re.findall(rb"GLIBCXX_[0-9]+\.[0-9]+(?:\.[0-9]+)?", Path(standard_library).read_bytes()))
            maximum = max(version_tuple(symbol.decode().removeprefix("GLIBCXX_")) for symbol in symbols)
            required = requirements["glibcxx_maximum"].removeprefix("GLIBCXX_")
            print(f"Host libstdc++: GLIBCXX_{'.'.join(map(str, maximum))}")
            require(maximum >= version_tuple(required), f"The SDK needs GLIBCXX_{required}.")
        except (OSError, ValueError) as error:
            require(False, f"Cannot inspect the host libstdc++ ABI: {error}")

    tool_commands = (
        (sdk_root / "bin/cmake", ["--version"]),
        (sdk_root / "bin/ninja", ["--version"]),
        (sdk_root / "bin/python3", ["--version"]),
        (sdk_root / "bin/node", ["--version"]),
        (sdk_root / "bin/git", ["--version"]),
        (sdk_root / "bin/curl", ["--version"]),
        (sdk_root / "bin/pkg-config", ["--version"]),
        (sdk_root / "bin/ccache", ["--version"]),
        (sdk_root / "qt/libexec/moc", ["-v"]),
        (sdk_root / "qt/libexec/rcc", ["-v"]),
        (sdk_root / "qt/libexec/uic", ["-v"]),
        (sdk_root / "qt/bin/qsb", ["-v"]),
        (sdk_root / "qt/bin/qmllint", ["--version"]),
    )
    expected_tool_versions = {
        "cmake": manifest["tools"]["cmake"]["version"],
        "ninja": manifest["tools"]["ninja"]["version"],
    }
    for tool, arguments in tool_commands:
        output = run([str(tool), *arguments])
        if output:
            print(f"{tool.relative_to(sdk_root)}: {output.splitlines()[0]}")
            expected = expected_tool_versions.get(tool.name)
            if expected:
                actual = re.search(r"(?:^|\s)(\d+\.\d+\.\d+)(?:$|\s)", output.splitlines()[0])
                require(actual is not None and actual[1] == expected,
                        f"{tool.name} does not match its manifest version.")

    qt_version = run([str(sdk_root / "qt/bin/qmake"), "-query", "QT_VERSION"])
    require(qt_version == manifest["qt"]["version"], "The Qt installation does not match its manifest.")
    qt_prefix = run([str(sdk_root / "qt/bin/qmake"), "-query", "QT_INSTALL_PREFIX"])
    require(qt_prefix == str(sdk_root / "qt"), "Qt's installation prefix is not the extracted Qt directory.")

    for component in (
        "Core", "Gui", "Qml", "Quick", "QuickControls2", "OpenGL", "Widgets", "Concurrent", "Network",
        "Svg", "WebSockets", "Test", "QuickTest", "ShaderTools", "Multimedia", "TaskTree",
    ):
        package = sdk_root / f"qt/lib/cmake/Qt6{component}/Qt6{component}Config.cmake"
        require(package.is_file(), f"Missing Qt development package: {component}")

    for relative_path in (
        f"include/QtGui/{qt_version}/QtGui/private/qfontengine_p.h",
        f"include/QtGui/{qt_version}/QtGui/private/qrawfont_p.h",
        f"include/QtQuick/{qt_version}/QtQuick/private/qquickwindow_p.h",
        "libexec/qmlcachegen", "libexec/qmltyperegistrar", "libexec/qmlimportscanner",
        "bin/qmltestrunner", "qml/QtQuick/Controls/Basic/qmldir", "qml/QtQuick/Effects/qmldir",
        "qml/QtQuick/Shapes/qmldir", "qml/QtTest/qmldir", "plugins/platforms/libqoffscreen.so",
        "plugins/platforms/libqxcb.so", "plugins/imageformats/libqsvg.so",
    ):
        require((sdk_root / "qt" / relative_path).is_file(), f"Missing Qt SDK file: {relative_path}")

    for package in ("openssl", "gl", "egl", "fontconfig", "freetype2", "xkbcommon", "xcb"):
        output = run([str(sdk_root / "bin/pkg-config"), "--modversion", package])
        if output:
            print(f"pkg-config {package}: {output}")

    qml_imports = (
        "QtQuick", "QtQuick.Controls.Basic", "QtQuick.Layouts", "QtQuick.Effects", "QtQuick.Shapes",
        "QtQuick.Dialogs", "QtTest", "QtMultimedia",
    )
    required_qml_directories = set()
    with tempfile.TemporaryDirectory(prefix="qt-sdk-imports-") as temporary_directory:
        qml_path = Path(temporary_directory) / "Imports.qml"
        qml_path.write_text("\n".join(f"import {name}" for name in qml_imports) + "\nItem {}\n")
        output = run([
            str(sdk_root / "qt/libexec/qmlimportscanner"), "-rootPath", temporary_directory,
            "-importPath", str(sdk_root / "qt/qml"),
        ])
        try:
            imports = {entry["name"]: entry for entry in json.loads(output)}
            for entry in imports.values():
                resolved_path = Path(entry.get("path", "/unresolved"))
                if resolved_path.is_dir() and resolved_path.is_relative_to(sdk_root / "qt/qml"):
                    required_qml_directories.add(resolved_path)
            for name in qml_imports:
                resolved_path = Path(imports.get(name, {}).get("path", "/unresolved"))
                require(
                    resolved_path.is_dir() and resolved_path.is_relative_to(sdk_root / "qt/qml"),
                    f"QML import {name} does not resolve inside the extracted SDK.",
                )
        except (ValueError, KeyError, TypeError) as error:
            require(False, f"Cannot parse QML import inventory: {error}")

    elf_paths = [tool for tool, unused in tool_commands if tool.parent.name != "bin"]
    elf_paths.extend(sdk_root.glob("qt/plugins/platforms/*.so"))
    required_qml_plugins = {path for directory in required_qml_directories for path in directory.glob("*.so")}
    elf_paths.extend(sorted(required_qml_plugins))
    elf_paths.extend(sdk_root.glob("qt/plugins/imageformats/*.so"))
    elf_paths.extend(sdk_root.glob("qt/plugins/tls/*.so"))
    elf_paths.extend(sdk_root.glob("qt/plugins/multimedia/*.so"))
    elf_paths.extend((sdk_root / "support/usr/bin/Xvfb", sdk_root / "libexec/lib-sdk-xvfb-paths.so"))
    for elf_path in elf_paths:
        if not elf_path.is_file():
            require(False, f"Missing SDK executable or plugin: {elf_path}")
            continue
        dependencies = run(["ldd", str(elf_path)])
        require("not found" not in dependencies, f"Unresolved libraries for {elf_path}: {dependencies}")

    optional_plugins = set(sdk_root.glob("qt/qml/**/*.so")) - required_qml_plugins
    optional_plugins.update(sdk_root.glob("qt/plugins/sqldrivers/*.so"))
    for plugin in sorted(optional_plugins):
        inventory = subprocess.run(["ldd", str(plugin)], capture_output=True, text=True, check=False)
        unresolved = [line.strip() for line in inventory.stdout.splitlines() if "not found" in line]
        if inventory.returncode != 0 or unresolved:
            detail = "; ".join(unresolved) or inventory.stderr.strip()
            print(f"Optional capability unavailable: {plugin.relative_to(sdk_root)}: {detail}")

    cgroup_writable = os.access("/sys/fs/cgroup", os.W_OK)
    print(f"Native host information: PID 1={Path('/proc/1/comm').read_text().strip()}, cgroup root writable={cgroup_writable}")
    print("Logonomic native containment is qualified by the repository's native preflight; SDK availability does not satisfy it.")
    print("Rendering requires the selected real test to confirm its backend and readback; preflight does not render.")
    if errors:
        print(f"SDK preflight failed: {len(errors)} check(s).", file=sys.stderr)
        return 1
    print("SDK tooling, installed development files, and host ABI preflight passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
