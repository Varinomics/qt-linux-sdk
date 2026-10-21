#!/usr/bin/env python3
"""Assemble the frozen SDK inputs without installing them into the host."""

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parent.parent
SDK_VERSION = "2026.10.21.1"
SDK_NAME = f"varinomics-qt-6.12.0-linux-x86_64-gcc13-sdk-{SDK_VERSION}"
QT_REPOSITORY = "https://download.qt.io/online/qtsdkrepository/linux_x64/desktop/qt6_6120/qt6_6120"
QT_MODULES = [
    "qtbase", "qtsvg", "qtdeclarative", "qttools", "qttranslations", "qtwayland", "icu",
    "qtwebsockets", "qtshadertools", "qtimageformats", "qtmultimedia", "qttasktree",
]
HOST_PACKAGES = {
    "libc6", "libc-bin", "libc6-dev", "libc-dev-bin", "linux-libc-dev",
    "libstdc++6", "libgcc-s1", "gcc-14-base", "gcc-13-base",
}


def run(*arguments, **kwargs):
    return subprocess.run(arguments, check=True, text=True, **kwargs)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, path, expected=None, algorithm="sha256"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (not expected or hashlib.new(algorithm, path.read_bytes()).hexdigest() == expected):
        return path
    temporary = path.with_suffix(path.suffix + ".partial")
    print(f"Downloading {url}", flush=True)
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as stream:
        shutil.copyfileobj(response, stream)
    if expected and hashlib.new(algorithm, temporary.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"Checksum mismatch: {url}")
    temporary.replace(path)
    return path


def resolve(work):
    """Freeze exact vendor inputs once; assembly thereafter consumes only this lock."""
    xml_bytes = urllib.request.urlopen(QT_REPOSITORY + "/Updates.xml", timeout=120).read()
    packages = ET.fromstring(xml_bytes).findall("PackageUpdate")
    inputs = []
    for package in packages:
        name = package.findtext("Name", "")
        if name != "qt.qt6.6120.linux_gcc_64" and not any(
            name == f"qt.qt6.6120.addons.{module}.linux_gcc_64" for module in QT_MODULES
        ):
            continue
        for archive in package.findtext("DownloadableArchives", "").split(","):
            archive = archive.strip()
            module = archive.split("-")[0]
            if module not in QT_MODULES:
                continue
            filename = package.findtext("Version") + archive
            url = f"{QT_REPOSITORY}/{name}/{filename}"
            vendor_hash = urllib.request.urlopen(url + ".sha1", timeout=120).read().decode().strip()
            inputs.append({"kind": "qt", "module": module, "url": url, "sha1": vendor_hash})
    if sorted(item["module"] for item in inputs) != sorted(QT_MODULES):
        raise RuntimeError("Qt module resolution is incomplete")
    inputs.extend([
        {"kind": "cmake", "url": "https://github.com/Kitware/CMake/releases/download/v3.31.10/cmake-3.31.10-linux-x86_64.tar.gz"},
        {"kind": "ninja", "url": "https://github.com/ninja-build/ninja/releases/download/v1.13.2/ninja-linux.zip"},
        {"kind": "ninja_license", "url": "https://raw.githubusercontent.com/ninja-build/ninja/v1.13.2/COPYING"},
        {"kind": "qt_source", "url": "https://download.qt.io/official_releases/qt/6.12/6.12.0/single/qt-everywhere-src-6.12.0.tar.xz"},
        {"kind": "node", "url": "https://nodejs.org/dist/v22.23.4/node-v22.23.4-linux-x64.tar.xz"},
    ])
    package_names = [line.strip() for line in (ROOT / "support-packages.txt").read_text().splitlines()
                     if line.strip() and not line.startswith("#")]
    empty_apt_cache = work / "apt-empty-cache"
    empty_apt_cache.mkdir(exist_ok=True)
    if list(empty_apt_cache.glob("*.deb")):
        raise RuntimeError("The URI resolver requires an empty APT archive cache")
    result = run(
        "apt-get", "--print-uris", "--yes", "--no-install-recommends",
        "-o", "Dir::State::status=/dev/null", "-o", f"Dir::Cache::archives={empty_apt_cache}",
        "install", *package_names,
        stdout=subprocess.PIPE,
    )
    for line in result.stdout.splitlines():
        match = re.match(r"'([^']+)' (\S+) (\d+) (\S+)", line)
        if not match:
            continue
        url, filename, size, checksum = match.groups()
        package_name = filename.split("_")[0]
        if package_name in HOST_PACKAGES or re.fullmatch(r"gcc-\d+-base", package_name):
            continue
        version = urllib.parse.unquote(filename).split("_")[1]
        metadata = run("apt-cache", "show", f"{package_name}={version}", stdout=subprocess.PIPE).stdout
        expected = re.search(r"^SHA256: ([0-9a-f]{64})$", metadata, re.MULTILINE).group(1)
        inputs.append({"kind": "deb", "package": package_name, "url": url.replace("http:", "https:", 1),
                       "size": int(size), "sha256": expected})
    absent_packages = set(package_names) - {item.get("package") for item in inputs}
    if absent_packages:
        raise RuntimeError(f"Ubuntu package resolution omitted requested packages: {sorted(absent_packages)}")
    def fetch(item):
        expected = item.get("sha256") or item.get("sha1")
        algorithm = "sha256" if item.get("sha256") else "sha1"
        path = download(item["url"], work / "downloads" / item["url"].rsplit("/", 1)[1], expected, algorithm)
        item["sha256"] = sha256(path)
        item["size"] = path.stat().st_size
        return item
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        inputs = list(executor.map(fetch, inputs))
    lock = {"sdk_version": SDK_VERSION, "qt_version": "6.12.0", "qt_package_revision": "6.12.0-0-202609280346",
            "qt_metadata_url": QT_REPOSITORY + "/Updates.xml", "inputs": inputs}
    (ROOT / "inputs.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    print(f"Resolved {len(inputs)} frozen inputs", flush=True)


def relative_symlinks(root):
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        destination = os.readlink(path)
        if destination.startswith("/"):
            target = root / destination.lstrip("/")
            if target.exists():
                path.unlink()
                path.symlink_to(os.path.relpath(target, path.parent))


def share_tool_aliases(stage):
    aliases = {
        "qt/bin/androiddeployqt6": "qt/bin/androiddeployqt",
        "qt/bin/harmonydeployqt6": "qt/bin/harmonydeployqt",
        "qt/bin/qmake6": "qt/bin/qmake",
        "qt/bin/qtdiag6": "qt/bin/qtdiag",
        "qt/bin/qtpaths6": "qt/bin/qtpaths",
        "qt/bin/wasmdeployqt6": "qt/bin/wasmdeployqt",
        "support/usr/lib/git-core/git": "support/usr/bin/git",
        "support/usr/lib/git-core/git-shell": "support/usr/bin/git-shell",
        "support/usr/lib/git-core/scalar": "support/usr/bin/scalar",
        "support/usr/bin/perl5.38.2": "support/usr/bin/perl",
    }
    for alias_name, canonical_name in aliases.items():
        alias = stage / alias_name
        canonical = stage / canonical_name
        if alias.is_symlink():
            continue
        if sha256(alias) != sha256(canonical):
            raise RuntimeError(f"Tool alias has distinct content: {alias_name}")
        alias.unlink()
        alias.symlink_to(os.path.relpath(canonical, alias.parent))


def assemble(work):
    import py7zr
    lock = json.loads((ROOT / "inputs.lock.json").read_text())
    stage = work / "stage" / SDK_NAME
    if stage.exists():
        raise RuntimeError(f"Use a fresh stage directory: {stage}")
    stage.mkdir(parents=True)
    support = stage / "support"
    temporary_qt = work / "qt-extracted"
    deb_inventory = []
    for item in lock["inputs"]:
        path = download(item["url"], work / "downloads" / item["url"].rsplit("/", 1)[1], item["sha256"])
        if item["kind"] == "qt":
            with py7zr.SevenZipFile(path) as archive:
                destination = temporary_qt / "lib" if item["module"] == "icu" else temporary_qt
                archive.extractall(destination)
        elif item["kind"] == "deb":
            run("dpkg-deb", "--extract", str(path), str(support))
            metadata = run("dpkg-deb", "--field", str(path), stdout=subprocess.PIPE).stdout
            fields = dict(re.findall(r"^([A-Za-z-]+): (.+)$", metadata, re.MULTILINE))
            source = fields.get("Source", fields["Package"])
            source_match = re.fullmatch(r"([^ ]+)(?: \(([^)]+)\))?", source)
            source_name = source_match.group(1)
            source_version = source_match.group(2) or fields["Version"]
            deb_inventory.append({"package": fields["Package"], "version": fields["Version"],
                                  "source": source_name, "source_version": source_version,
                                  "source_url": f"https://launchpad.net/ubuntu/+source/{source_name}/{source_version}",
                                  "archive_url": item["url"], "sha256": item["sha256"]})
        elif item["kind"] == "cmake":
            with tarfile.open(path) as archive:
                archive.extractall(stage / "tools", filter="data")
            (stage / "tools" / "cmake-3.31.10-linux-x86_64").rename(stage / "tools" / "cmake")
        elif item["kind"] == "ninja":
            (stage / "tools" / "ninja").mkdir(parents=True)
            with zipfile.ZipFile(path) as archive:
                archive.extractall(stage / "tools" / "ninja")
            (stage / "tools" / "ninja" / "ninja").chmod(0o755)
        elif item["kind"] == "ninja_license":
            destination = stage / "licenses" / "ninja"
            destination.mkdir(parents=True)
            shutil.copy2(path, destination / "COPYING")
        elif item["kind"] == "qt_source":
            with tarfile.open(path) as archive:
                for member in archive:
                    if member.isfile() and re.match(r"(?:LICENSE|COPYING|NOTICE)", Path(member.name).name, re.I):
                        destination = stage / "licenses" / "qt-source" / member.name
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(archive.extractfile(member).read())
        elif item["kind"] == "node":
            with tarfile.open(path) as archive:
                for member_name, target in [
                    ("bin/node", support / "usr" / "bin" / "node"),
                    ("LICENSE", stage / "licenses" / "node" / "LICENSE"),
                ]:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(f"node-v22.23.4-linux-x64/{member_name}").read())
                    if member_name == "bin/node":
                        target.chmod(0o755)
    qt = stage / "qt"
    temporary_qt.rename(qt)
    (qt / "bin" / "qt.conf").write_text("[Paths]\nPrefix=..\n")
    build_internals = qt / "lib/cmake/Qt6BuildInternals/QtBuildInternalsExtra.cmake"
    text = build_internals.read_text()
    text = text.replace('set(qtbi_orig_prefix "/home/qt/work/install")',
                        'set(qtbi_orig_prefix "${QT_BUILD_INTERNALS_RELOCATABLE_INSTALL_PREFIX}")')
    text = re.sub(r'set\(QT_SOURCE_TREE "[^"]*" CACHE PATH\s*"[^"]*" FORCE\)',
                  'set(QT_SOURCE_TREE "" CACHE PATH "Explicit QtBase source path when building Qt modules.")', text)
    build_internals.write_text(text)
    # qmake-specific link metadata uses distributor /usr/lib64; CMake uses relative packages.
    for path in (qt / "lib" / "pkgconfig").glob("*.pc"):
        text = path.read_text()
        text = re.sub(r"^prefix=.*$", "prefix=${pcfiledir}/../..", text, flags=re.MULTILINE)
        path.write_text(text)
    cmake_notices = stage / "licenses" / "cmake"
    cmake_notices.mkdir(parents=True)
    for path in (stage / "tools" / "cmake" / "doc").rglob("*"):
        if path.is_file() and ("Copyright" in path.name or "LICENSE" in path.name):
            destination = cmake_notices / path.relative_to(stage / "tools" / "cmake" / "doc")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    for directory in [qt / "doc", qt / "examples", stage / "tools" / "cmake" / "doc"]:
        if directory.exists():
            shutil.rmtree(directory)
    for path in qt.rglob("*.debug"):
        path.unlink()
    relative_symlinks(support)
    # Debian's lib -> usr/lib merge is represented inside this SDK as relative links.
    if (support / "lib").is_dir() and not (support / "lib").is_symlink():
        shutil.copytree(support / "lib", support / "usr" / "lib", dirs_exist_ok=True, symlinks=True)
        shutil.rmtree(support / "lib")
        (support / "lib").symlink_to("usr/lib", target_is_directory=True)
    certificates = sorted((support / "usr" / "share" / "ca-certificates").rglob("*.crt"))
    certificate_bundle = support / "etc" / "ssl" / "certs" / "ca-certificates.crt"
    certificate_bundle.parent.mkdir(parents=True, exist_ok=True)
    certificate_bundle.write_bytes(b"".join(path.read_bytes() for path in certificates))
    # GLVND resolves bare library names through the SDK-scoped loader search path.
    for path in (support / "usr" / "share" / "glvnd" / "egl_vendor.d").glob("*.json"):
        text = path.read_text()
        text = re.sub(r'"library_path"\s*:\s*"[^"]*/([^/"]+)"', r'"library_path": "\1"', text)
        path.write_text(text)
    for name in ["activate.sh", "bin", "etc", "libexec", "fallback", "SDK_FOR_ASSISTANTS.md", "THIRD_PARTY_NOTICES.md", "LICENSE"]:
        source = ROOT / name
        if not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, stage / name, dirs_exist_ok=True)
        else:
            shutil.copy2(source, stage / name)
    (stage / "bin").mkdir(exist_ok=True)
    for name in ["cmake", "ctest", "cpack"]:
        (stage / "bin" / name).symlink_to(f"../tools/cmake/bin/{name}")
    (stage / "bin" / "ninja").symlink_to("../tools/ninja/ninja")
    (stage / "libexec").mkdir(exist_ok=True)
    run("gcc", "-O2", "-shared", "-fPIC", "-Wl,-z,relro,-z,now", "-o",
        str(stage / "libexec" / "lib-sdk-xvfb-paths.so"), str(ROOT / "src" / "xvfb_paths.c"), "-ldl")
    for path in (stage / "bin").iterdir():
        if not path.is_symlink():
            path.chmod(0o755)
    for path in (stage / "fallback" / "bin").iterdir():
        path.chmod(0o755)
    share_tool_aliases(stage)
    manifest = {
        "sdk_version": SDK_VERSION, "archive_basename": SDK_NAME + ".tar.xz",
        "platform": {"architecture": "x86_64", "glibc_minimum": "2.39", "gcc_major_minimum": 13,
                     "glibcxx_maximum": "GLIBCXX_3.4.32", "host_glibc": True,
                     "cpu_baseline": "x86-64-v2",
                     "cpu_required_flags": ["cx16", "lahf_lm", "popcnt", "pni", "ssse3", "sse4_1", "sse4_2"],
                     "cpu_provenance": "Qt compile architecture probe TEST_subarch_result; RHEL9.6 supplier GCC11.5; no -march=native"},
        "qt": {"version": "6.12.0", "package_revision": lock["qt_package_revision"],
               "modules": QT_MODULES, "provenance": "Qt official Linux RHEL9.6 GCC11.5 packages",
               "configuration": "shared release, relocatable, private headers, vendor separate debug info omitted",
               "local_patches": [], "source_url": "https://download.qt.io/official_releases/qt/6.12/6.12.0/single/qt-everywhere-src-6.12.0.tar.xz"},
        "tools": {"cmake": {"version": "3.31.10"}, "ninja": {"version": "1.13.2"},
                  "node": {"version": "22.23.4", "source_url": "https://nodejs.org/dist/v22.23.4/node-v22.23.4.tar.xz"},
                  "aqtinstall": {"version": "3.3.0", "preparation_only": True},
                  "py7zr": {"version": "1.1.3", "preparation_only": True}},
        "ubuntu_packages": deb_inventory,
        "source_policy": "Application and library checkouts remain external and are explicitly supplied to CMake.",
        "optional_capabilities": [
            {"name": "Qt Quick 3D spatial audio", "available": False, "requires": "qtquick3d module"},
            {"name": "Qt SQL server drivers", "available": False, "requires": "matching database client runtimes"},
            {"name": "GTK desktop theme", "available": False, "requires": "GTK desktop runtime"},
            {"name": "CUPS printing", "available": False, "requires": "CUPS client runtime and print service"},
        ],
        "vendor_binary_exception": "Required Qt static development helper libraries retain supplier embedded debug data; separate debug archives were not selected. SDK-owned helper is a symbol-free Release build.",
    }
    manifest["qt"]["repositories"] = []
    for path in (qt / "sbom").glob("*.spdx.json"):
        document = json.loads(path.read_text())
        for package in document.get("packages", []):
            if package.get("name") in QT_MODULES:
                manifest["qt"]["repositories"].append({key: package[key] for key in
                    ["name", "versionInfo", "downloadLocation", "comment"] if key in package})
    (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copy2(ROOT / "inputs.lock.json", stage / "inputs.lock.json")
    shutil.copytree(ROOT / "src", stage / "recipe-source")
    print(f"STAGE={stage}", flush=True)


def pack(work, qualification_snapshot=None):
    stage = work / "stage" / SDK_NAME
    output = work / "dist"
    output.mkdir(parents=True, exist_ok=True)
    (stage / "share").mkdir(exist_ok=True)
    if qualification_snapshot:
        snapshot = json.loads(qualification_snapshot.read_text())
        allowed_fields = {"key", "kind", "repository", "requested_ref", "commit", "checkout_path"}
        snapshot["sources"] = [{key: value for key, value in source.items() if key in allowed_fields}
                               for source in snapshot["sources"]]
        snapshot["purpose"] = "Historical SDK qualification inputs; future reviews supply their own sources."
        (stage / "share" / "qualification-sources.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    inventory_file = stage / "share" / "elf-inventory.json"
    run("python3", str(ROOT / "scripts" / "inspect_payload.py"), str(stage), "--output", str(inventory_file))
    inventory = json.loads(inventory_file.read_text())
    manifest_path = stage / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["platform"]["glibcxx_maximum"] = inventory["abi_maximum"]["GLIBCXX"]
    manifest["platform"]["measured_abi_maximum"] = inventory["abi_maximum"]
    manifest["platform"]["cpu_baseline"] = "x86-64-v2"
    manifest["platform"]["cpu_required_flags"] = ["cx16", "lahf_lm", "popcnt", "pni", "ssse3", "sse4_1", "sse4_2"]
    manifest["platform"]["cpu_provenance"] = "Qt compile architecture probe TEST_subarch_result; RHEL9.6 supplier GCC11.5; no -march=native"
    manifest["platform"].pop("cpu", None)
    manifest["optional_unavailable"] = inventory["optional_unavailable"]
    manifest["vendor_binary_exception"] = "Required Qt static development helper libraries retain supplier embedded debug data; separate debug archives were not selected. SDK-owned helper is a symbol-free Release build."
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    archive = output / (SDK_NAME + ".tar.xz")
    environment = os.environ.copy()
    environment["XZ_OPT"] = "-T1 -0"
    run("tar", "--sort=name", "--mtime=@1792537200", "--owner=0", "--group=0", "--numeric-owner",
        "-cJf", str(archive), "-C", str(stage.parent), SDK_NAME, env=environment)
    external_manifest = json.loads((stage / "manifest.json").read_text())
    release_tag = f"qt-6.12.0-linux-x86_64-gcc13-sdk-{SDK_VERSION}"
    external_manifest["archives"] = [{
        "filename": archive.name, "size": archive.stat().st_size, "sha256": sha256(archive),
        "url": f"https://github.com/Varinomics/qt-linux-sdk/releases/download/{release_tag}/{archive.name}",
    }]
    (output / "manifest.json").write_text(json.dumps(external_manifest, indent=2) + "\n")
    checksum_files = [archive, output / "manifest.json"]
    (output / "SHA256SUMS").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in checksum_files))
    print((output / "SHA256SUMS").read_text(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["resolve", "assemble", "pack"])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--qualification-snapshot", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.operation == "pack":
        pack(args.work.resolve(), args.qualification_snapshot)
    else:
        {"resolve": resolve, "assemble": assemble}[args.operation](args.work.resolve())


if __name__ == "__main__":
    main()
