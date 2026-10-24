#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p build
protocol=wlr-foreign-toplevel-management-unstable-v1
wayland-scanner client-header "$protocol.xml" "build/$protocol-client-protocol.h"
wayland-scanner private-code "$protocol.xml" "build/$protocol-protocol.c"
cc -std=c11 -O2 -Wall -Wextra -Werror -Wno-unused-parameter -Ibuild \
    toplevel-helper.c "build/$protocol-protocol.c" \
    $(pkg-config --cflags --libs wayland-client) -o build/toplevel-helper
