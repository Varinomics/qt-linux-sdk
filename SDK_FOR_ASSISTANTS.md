# Linux Qt SDK for repository work

This guide covers the public Qt/toolchain base. For the complete private
Logonomic environment with prebuilt product dependencies, use the single
combined archive identified by
[Logonomic's build documentation](https://github.com/Varinomics/logonomic/blob/master/docs/linux_assistant_sdk.md).
That archive already includes this base; it does not require this separate
download or the source-dependency preparation below.

SDK version **2026.10.21.1** packages **Qt 6.12.0**, Linux x86_64 shared
libraries, CMake 3.31.10, Ninja 1.13.2, and Ubuntu 24.04 support tools and
libraries. It matches the Qt patch version used by the inspected Logonomic and
Soter Windows builds. Linux uses GCC and Mesa; it does not validate Windows,
Direct3D, Android behavior, or hardware performance.

Release:
<https://github.com/Varinomics/qt-linux-sdk/releases/tag/qt-6.12.0-linux-x86_64-gcc13-sdk-2026.10.21.1>

Archive: `varinomics-qt-6.12.0-linux-x86_64-gcc13-sdk-2026.10.21.1.tar.xz`.
SHA-256: `05e8be4d5fb13a8b64f0316e473b76b43ec5b72997948828b4f31c5c0951d23f`.
The repository handoff records the finished archive's hash. Its archived copy
uses the accompanying external checksums to avoid a circular hash.

The archive contains development headers, versioned Qt private headers, CMake
packages, QML imports and plugins, Qt host tools and `qsb`. Selected modules are
qtbase, qtdeclarative, qtsvg, qtwebsockets, qtshadertools, qtimageformats,
qtmultimedia and qttasktree. `manifest.json` records the installed configuration
and ABI requirements; `inputs.lock.json` records exact preparation inputs.
Application and library source is supplied separately and remains writable.
Complete selected-module contents are preserved. Optional imports such as
QtMultimedia SpatialAudio need unselected QtQuick3D libraries, and optional SQL
drivers can need external database clients. Preflight reports these unavailable
capabilities separately; the required project import closure remains a hard gate.

## Download and activate

Use a writable Linux x86_64 directory on Ubuntu 24.04 with glibc 2.39 or newer,
GCC/G++ 13 or newer, Bash, coreutils and tar/xz. The supplied RHEL 9 Qt binaries
require the x86-64-v2 CPU baseline (SSE3, SSSE3, SSE4.1/4.2, POPCNT, CX16 and
LAHF/SAHF); preflight checks exposed CPU features before running SDK binaries.
The 21 October target snapshot did not record CPU flags, so run this check on
the actual consumer. The initial download command
uses the host's curl; downloading the same two files through ChatGPT's file
tools is equivalent. Subsequent commands use the extracted tools. No Docker,
administrator access, system installation, or new Qt download is needed.

```bash
mkdir -p assistant-work
cd assistant-work
sdk_tag=qt-6.12.0-linux-x86_64-gcc13-sdk-2026.10.21.1
sdk_name=varinomics-qt-6.12.0-linux-x86_64-gcc13-sdk-2026.10.21.1
sdk_url="https://github.com/Varinomics/qt-linux-sdk/releases/download/$sdk_tag"
curl --fail --location --output "$sdk_name.tar.xz" "$sdk_url/$sdk_name.tar.xz"
curl --fail --location --output SHA256SUMS "$sdk_url/SHA256SUMS"
sha256sum --check --ignore-missing SHA256SUMS
printf '%s  %s\n' 05e8be4d5fb13a8b64f0316e473b76b43ec5b72997948828b4f31c5c0951d23f "$sdk_name.tar.xz" | sha256sum --check -
tar -xJf "$sdk_name.tar.xz"
source "$PWD/$sdk_name/activate.sh"
sdk-preflight
```

Checksums and the external release manifest accompany the exact archive.
Preflight checks the host ABI, tool execution, Qt development files, QML import
resolution and ELF dependencies. Rendering and native containment require their
own applicable tests. Activation uses paths relative to its own location,
including the ELF library search path; `qt.conf` alone is insufficient.

Use `sdk-run COMMAND ...` instead of sourcing activation when only one command
should inherit the SDK. Rendering wrappers also activate the SDK for their child
commands. None changes system configuration or replaces the host glibc,
libstdc++ or compiler.

## Prepare source inputs

Use the Logonomic checkout being reviewed. For an initial checkout, authenticate
Git normally if access requires it, then run:

```bash
mkdir -p sources
git clone https://github.com/Varinomics/logonomic.git sources/logonomic
export LOGONOMIC_SOURCE="$PWD/sources/logonomic"
python3 "$LOGONOMIC_SOURCE/tools/linux_sdk_sources.py" prepare \
    --source-root "$LOGONOMIC_SOURCE" --workspace "$PWD/sources" \
    --tuple "$SDK_ROOT/share/qualification-sources.json" \
    --output "$PWD/source-paths.cmake" --manifest "$PWD/resolved-sources.json"
```

`release/sources.json` and its existing resolver own the dependency graph. The
recorded tuple gives exact historical qualification inputs; it does not pin the
repositories' forward dependency declarations. Source preparation retrieves
those inputs explicitly. It requires network access and authorization for any
private repositories. Credentials and private source are excluded from the
public SDK.

For a modified dependency, add its source override to the same command, for
example `--source vnm_plot="$PWD/review/vnm_plot"`. The application is always
the `--source-root` checkout. The generated initial cache directs CMake to these
source trees, rather than prebuilt copies of changing product libraries.
`resolved-sources.json` records actual revisions, overrides and dirty state.

Once every declared input is present, rerun preparation with `--offline` to
check completeness and disable CMake FetchContent retrieval. For existing sibling
checkouts, use `cache --offline` instead of `prepare` and omit `--tuple`.
Offline operation requires all source inputs, including vnm_cmake, GLM,
FreeType, msdfgen and font sources; the SDK alone does not provide them.

## Configure, build and run focused tests

The existing focused helper preserves CTest's registered command, environment,
working directory and diagnostics. Select exact targets and registrations;
`ctest -R` selects registrations rather than individual QTest functions.

```bash
export LOGONOMIC_EDITION=Pro
export CCACHE_DIR="$PWD/compiler-cache"
export CCACHE_MAXSIZE=2GiB
mkdir -p "$CCACHE_DIR"
export LOGONOMIC_CI_SELECTION='{"build_targets":["logonomic_terminal_settings_tests","logonomic_startup_failure_tests","logonomic_startup_window_tests"],"tests":{"logonomic_terminal_settings_tests":[],"logonomic_startup_failure_tests":[],"logonomic_startup_window_tests":[]},"companion_host":false}'
python3 "$LOGONOMIC_SOURCE/.github/scripts/run_focused_tests.py" prepare --build-dir build
queued-build --slots 1 -- cmake -C "$PWD/source-paths.cmake" \
    -S "$LOGONOMIC_SOURCE" -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$SDK_ROOT/qt;$SDK_ROOT/support/usr" \
    -DLOGONOMIC_EDITION=Pro -DLOGONOMIC_BUILD_TESTS=ON \
    -DLOGONOMIC_BUILD_COMPANION_HOST=OFF -DLOGONOMIC_BUILD_COMPANION_TESTS=OFF \
    -DLOGONOMIC_CLI_ADDON_PACKAGES=OFF \
    -DLOGONOMIC_CCACHE_DIRECTORY="$CCACHE_DIR" -DLOGONOMIC_CCACHE_MAX_SIZE="$CCACHE_MAXSIZE"
queued-build --slots 4 -- python3 \
    "$LOGONOMIC_SOURCE/.github/scripts/run_focused_tests.py" build --build-dir build
sdk-run-headless python3 \
    "$LOGONOMIC_SOURCE/.github/scripts/run_focused_tests.py" test --build-dir build
```

Keep this build directory separate from other Qt kits, compilers or generators.
The focused helper builds with `--parallel 4`, matching the declared queue
width. The SDK supplies ccache; Logonomic uses it when available. Preserve its
writable cache between related builds.

On a fresh assistant host without an existing `queued-build`, activation adds
the SDK's small Linux fallback. It serializes builds with a per-user flock,
requires `--slots 1..4`, and checks explicit CMake/Ninja/Make parallel widths.
For commands that run scripts, the caller must match their internal width.
An existing owner queue takes precedence. Owner Windows/WSL preparation and
qualification continue through that owner's authoritative queue.

## Headless and rendering modes

`sdk-run-headless COMMAND ...` selects the offscreen platform and Qt Quick
software backend. Use it for qualified unit and compatible GUI/QML tests.
Rendering tests need a separate mode; passing an ordinary headless test does
not establish shader rendering.

`sdk-run-opengl COMMAND ...` starts a private bundled Xvfb, selects xcb and
requests Qt RHI OpenGL with Mesa llvmpipe. It clears the Qt Quick software
backend setting. Failure to start Xvfb is an error. The actual rendering test
must verify its backend and readback; the wrapper's requested settings are not
proof that a renderer executed.

The existing plot tests `LinePrecision` and `FontRendererDrawRanges` exercise
QSB line rendering and MSDF text shaders with pixel readback:

```bash
queued-build --slots 1 -- cmake -C "$PWD/source-paths.cmake" \
    -S "$PWD/sources/vnm_plot" -B build-plot -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$SDK_ROOT/qt;$SDK_ROOT/support/usr" \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
    -DVNM_PLOT_BUILD_TESTS=ON -DVNM_PLOT_BUILD_EXAMPLES=OFF
queued-build --slots 4 -- cmake --build build-plot \
    --target test_typed_api test_qml_module test_line_precision test_font_renderer_draw_ranges \
    --parallel 4
sdk-run-headless ctest --test-dir build-plot -R '^(TypedApi|QmlModule)$' \
    --output-on-failure --no-tests=error
sdk-run-opengl ctest --test-dir build-plot -R '^(LinePrecision|FontRendererDrawRanges)$' \
    --verbose --output-on-failure --no-tests=error
```

Some application CTest registrations explicitly set the software backend.
For an applicable Logonomic selection that needs OpenGL, use
`sdk-run-opengl python3 "$LOGONOMIC_SOURCE/.github/scripts/run_focused_tests.py" test --build-dir build --rendering-mode software-opengl`.
That explicit mode rewrites only rendering settings in the selected resolved
registrations. Preserve all other registered properties. The two wrappers scope
their variables to the child process and clean up temporary runtime directories.

## Native host checks

SDK availability does not grant kernel permissions or systemd delegation.
Ordinary Logonomic startup needs pidfds, readable process-child information and
subreaper support. PID 1 being supervisord and a read-only cgroup mount do not,
by themselves, establish that startup is blocked. Positive containment after
custodian loss requires the stronger native preflight, including writable
delegated cgroups and the actual filesystem identity operations. Do not disable
or replace those production checks to pass a restricted-host test.

The Linux application target can compile without a Soter payload. Protected
terminal recovery needs a compatible Linux x86_64 **Soter for Logonomic** artifact
and its fixed layout; recovery observer gates need its test observer and
diagnostic artifacts too. The native focused route below does not supply those
artifacts and rejects `soter_artifact=true` selections.

Run affected containment checks using the existing private native workflow,
with the owner's explicit hosted-CI authorization. Keep `--ref master`: the job
uses the trusted master driver. Supply exact proposed commits independently;
a default-branch run does not validate a different local patch.

```bash
application_revision=$(git -C "$LOGONOMIC_SOURCE" rev-parse HEAD)
plot_revision=$(git -C "$PWD/sources/vnm_plot" rev-parse HEAD)
source_revisions=$(python3 -c 'import json,sys; print(json.dumps(dict(application=sys.argv[1],vnm_plot=sys.argv[2])))' \
    "$application_revision" "$plot_revision")
gh workflow run linux-native-validation.yml --repo Varinomics/logonomic --ref master \
    --field source_revisions="$source_revisions" \
    --field validation_selection='{"build_targets":["logonomic_generation_containment_tests","logonomic_cli_addon_native_family_tests"],"tests":{"logonomic_generation_containment_hosted_normal":[],"logonomic_generation_containment_hosted_loss":[],"logonomic_cli_addon_native_family_tests":[]},"companion_host":false}'
gh run list --repo Varinomics/logonomic --workflow linux-native-validation.yml --limit 5
```

Select the run ID returned by the dispatch/listing, then retrieve its exact
tuple, selection and results:

```bash
read -r -p 'Native workflow run ID: ' native_run_id
gh run watch "$native_run_id" --repo Varinomics/logonomic --exit-status
gh run download "$native_run_id" --repo Varinomics/logonomic \
    --pattern 'linux-native-validation-*' --dir native-results
```

Commit and publish the proposed source before requesting its revision in CI;
uncommitted changes cannot be fetched by a runner. Other changed dependencies
must also appear in `source_revisions` using their catalog keys. Verify the
downloaded `native-source-tuple.json` and `native-source-selection.json` match
the intended sources. Artifacts expire after 14 days, so retain needed results.

GitHub CLI is used on an authorized developer machine for this native route; it
is not needed to compile or run restricted-host tests with the SDK.

For an indirect source such as vnm_cmake, append
`--field indirect_source_revisions='{"vnm_cmake":"<40-character commit>"}'`
to the workflow command; GLM, FreeType and msdfgen use keys `glm`, `freetype`
and `msdfgen`. The trusted helper derives these repositories from the selected
owners' declarations. The artifact additionally retains
`native-indirect-revisions.json` and `native-source-inputs.json`. See the
[Logonomic SDK build documentation](https://github.com/Varinomics/logonomic/blob/master/docs/linux_assistant_sdk.md)
for the maintained native workflow input contract.

## Message to paste into ChatGPT

> Download the versioned Varinomics Linux Qt SDK and its SHA256SUMS from the
> release above. Verify, extract into a writable directory, read
> SDK_FOR_ASSISTANTS.md, activate it, and run sdk-preflight. Use my supplied
> writable source checkouts and explicit dependency overrides. Run the focused
> tests applicable to the change; use the OpenGL wrapper for shader tests and
> inspect the actual backend/readback. Preserve native containment requirements
> and report any host restrictions separately.
