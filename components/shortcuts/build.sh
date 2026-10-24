#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p build
wayland-scanner client-header wlr-foreign-toplevel-management-unstable-v1.xml build/toplevel-protocol.h
wayland-scanner private-code wlr-foreign-toplevel-management-unstable-v1.xml build/toplevel-protocol.c
gcc -std=c11 -O2 -Wall -Wextra -Werror -Wno-unused-parameter \
    -Ibuild app-shortcut.c build/toplevel-protocol.c \
    $(pkg-config --cflags --libs wayland-client) -o build/app-shortcut
