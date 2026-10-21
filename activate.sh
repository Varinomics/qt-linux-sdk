#!/usr/bin/env bash
# Source this file so the SDK paths apply to the current shell.
if [[ -z ${BASH_VERSION:-} ]]; then
    printf '%s\n' 'Activate this SDK from Bash: source /path/to/sdk/activate.sh' >&2
    return 1 2>/dev/null || exit 1
fi

export SDK_ROOT
SDK_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || return 1
export LOGONOMIC_QT_DIR="$SDK_ROOT/qt"
export Qt6_ROOT="$SDK_ROOT/qt"
export PATH="$SDK_ROOT/bin:$SDK_ROOT/qt/bin:$PATH"
if ! command -v queued-build >/dev/null 2>&1; then
    export PATH="$PATH:$SDK_ROOT/fallback/bin"
fi
export CMAKE_PREFIX_PATH="$SDK_ROOT/qt:$SDK_ROOT/support/usr${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
export LD_LIBRARY_PATH="$SDK_ROOT/qt/lib:$SDK_ROOT/support/usr/lib/x86_64-linux-gnu:$SDK_ROOT/support/usr/lib/x86_64-linux-gnu/pulseaudio:$SDK_ROOT/support/lib/x86_64-linux-gnu:$SDK_ROOT/support/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LIBRARY_PATH="$SDK_ROOT/support/usr/lib/x86_64-linux-gnu:$SDK_ROOT/support/lib/x86_64-linux-gnu:$SDK_ROOT/support/usr/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
export CPATH="$SDK_ROOT/support/usr/include:$SDK_ROOT/support/usr/include/x86_64-linux-gnu${CPATH:+:$CPATH}"
export QT_PLUGIN_PATH="$SDK_ROOT/qt/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="$SDK_ROOT/qt/plugins/platforms"
export QML_IMPORT_PATH="$SDK_ROOT/qt/qml"
export QML2_IMPORT_PATH="$SDK_ROOT/qt/qml"
export FONTCONFIG_FILE="$SDK_ROOT/etc/fonts/fonts.conf"
export FONTCONFIG_PATH="$SDK_ROOT/etc/fonts"
export XKB_CONFIG_ROOT="$SDK_ROOT/support/usr/share/X11/xkb"
export LIBGL_DRIVERS_PATH="$SDK_ROOT/support/usr/lib/x86_64-linux-gnu/dri"

if [[ -f "$SDK_ROOT/support/etc/ssl/certs/ca-certificates.crt" ]]; then
    export SSL_CERT_FILE="$SDK_ROOT/support/etc/ssl/certs/ca-certificates.crt"
fi
