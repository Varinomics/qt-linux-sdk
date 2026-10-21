/* Xvfb's exported directory pointer otherwise invokes the host /usr/bin/xkbcomp. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>

__attribute__((constructor)) static void configure_xkb_directory(void)
{
    const char* directory = getenv("SDK_XKB_BIN_DIR");
    char** binary_directory = (char**) dlsym(RTLD_DEFAULT, "XkbBinDirectory");
    if (directory && binary_directory) {
        *binary_directory = (char*) directory;
    }
}
