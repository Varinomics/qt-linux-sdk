# Linux Qt SDK

An extraction-based development SDK for rebuilding modified Varinomics C++/Qt
repositories on Ubuntu 24.04 x86_64 without administrator access, a desktop,
Docker or an additional Qt download.

[SDK_FOR_ASSISTANTS.md](SDK_FOR_ASSISTANTS.md) contains the download, activation,
source preparation, build and focused-test commands. The SDK supplies Qt 6.12.0,
CMake 3.31.10, Ninja 1.13.2 and scoped Linux support dependencies. The host
supplies Bash, ordinary core tools and GCC/G++ 13. The preflight checks the
actual architecture and library ABI rather than trusting a distribution label.

Changing application and library source remains outside the SDK. Explicit
source paths let review sessions compile their modified checkouts. Some native
Logonomic integration checks require delegated systemd/cgroup capabilities;
the handoff links the separate native CI procedure without weakening them.

## Reproduce the SDK

Use Ubuntu 24.04 x86_64 with Python 3.12, `python3-venv`, GCC 13, APT metadata,
`dpkg-deb`, `tar`, `xz` and `readelf`. Preparation may retrieve public binary
inputs; using the finished SDK does not require system package installation.
All compile-capable commands on the owner's workstation run through its
existing `queued-build`. On Windows, wrap the corresponding `wsl` command with
the Windows queue. The portable fallback queue is only for consumer machines
without an existing owner queue.

```bash
python3 -m venv /tmp/qt-sdk-preparation
/tmp/qt-sdk-preparation/bin/python -m pip install --only-binary=:all: \
    --requirement preparation-requirements.txt
queued-build --slots 1 -- /tmp/qt-sdk-preparation/bin/python scripts/prepare.py \
    assemble --work /path/to/writable/sdk-work
queued-build --slots 1 -- /tmp/qt-sdk-preparation/bin/python scripts/prepare.py \
    pack --work /path/to/writable/sdk-work
```

`inputs.lock.json` freezes the exact public binary archives, their SHA-256
hashes and sizes. Preparation reuses valid cached downloads. `assemble` requires
a fresh staging directory and builds only the small SDK-owned Xvfb path helper;
Qt and all support libraries are prebuilt supplier inputs. The Qt installed
development structure, including private headers and imported targets, remains
complete for the selected module archives. Optional features whose additional
modules are not selected are listed as unavailable in the manifest.

`scripts/prepare.py resolve --work /path/to/writable/sdk-work` is the explicit
maintainer operation for selecting a new frozen input set. It uses an empty APT
installation state and archive cache, so the builder's installed or cached
packages cannot disappear from the resulting dependency closure. Do not run
it merely because application commits changed.

Inspect staged and relocated payloads with:

```bash
python3 scripts/inspect_payload.py /path/to/sdk --output /path/to/elf-inventory.json
```

The inventory records every ELF dependency and ABI requirement. Required
dependencies must resolve inside the SDK or the declared glibc/GCC runtime
baseline. Optional SQL server drivers and Qt Quick 3D spatial audio remain
explicitly unavailable unless their external capabilities are supplied.

[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) identifies licenses and exact
corresponding-source locations. Large binary archives belong in versioned
GitHub Releases; this repository contains only the reproducible recipe,
consumer scripts and documentation.
