# Third-party software

This development SDK combines unmodified vendor development modules and Ubuntu
support packages. Their licenses apply independently of the recipe's BSD license.
No private application or dependency source is included.

Qt 6.12.0 comes from The Qt Company's public Linux RHEL 9.6 GCC 11.5 binary
packages, package revision `6.12.0-0-202609280346`. The selected modules and exact
archive hashes are in `inputs.lock.json`. Qt's supplier SBOMs in `qt/sbom` retain
the actual per-module source revisions, configurations, copyright and license
declarations, including bundled third-party components. License and copyright
files from the matching public source are in `licenses/qt-source`.

Qt modules offer the licenses stated by their source and SBOM, including
LGPL-3.0-only, GPL-3.0-only and Qt's GPL exception where applicable. GPL-only host
tools do not grant a license for applications compiled using the SDK. Read the
applicable source licenses before redistributing an application.

The complete corresponding Qt source is available separately at:

- https://download.qt.io/official_releases/qt/6.12/6.12.0/single/qt-everywhere-src-6.12.0.tar.xz
- https://github.com/Varinomics/qt-freebsd/releases/download/qt-6.12.0-freebsd-15-amd64-38092937062-1/qt-everywhere-src-6.12.0.tar.xz

These binaries use shared Qt. Development headers, CMake packages and required
static development libraries remain available for rebuilding and relinking; no
application object code or private application source is distributed here.
The Qt packages are unmodified apart from relative installation metadata and
omission of documentation, examples and separate debugging files.

CMake 3.31.10 uses its BSD license and third-party notices retained under
`licenses/cmake` and `tools/cmake/share/cmake-3.31/Licenses`. Matching source:
https://github.com/Kitware/CMake/releases/download/v3.31.10/cmake-3.31.10.tar.gz

Ninja 1.13.2 uses Apache-2.0; its notice is `licenses/ninja/COPYING`. Matching
source: https://github.com/ninja-build/ninja/archive/refs/tags/v1.13.2.tar.gz

Node.js 22.23.4 is the official portable Linux x64 distribution. Its complete
upstream and bundled-component notices are in `licenses/node/LICENSE`. Matching
source: https://nodejs.org/dist/v22.23.4/node-v22.23.4.tar.xz

Ubuntu Noble support packages retain copyright and license notices in
`support/usr/share/doc/<package>/copyright`. `manifest.json` records each exact
binary version, source package/version, upstream download and corresponding
Ubuntu source URL. The package sources remain separately available through
those source pages. Ubuntu packages and their upstream components include GPL,
LGPL, BSD, MIT, OpenSSL, Apache and other licenses stated in their notices.

The `src/xvfb_paths.c` shim is SDK recipe code under the included BSD license.
Its source is included under `recipe-source`; it only directs Xvfb's external
XKB compiler lookup to the extracted support directory. It does not modify
the host or replace production containment behavior.
