#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <unistd.h>
#include <wayland-client.h>

#include "wlr-foreign-toplevel-management-unstable-v1-client-protocol.h"

struct window {
    uint32_t id;
    char *app_id;
    char *title;
    bool active;
    bool ready;
    struct zwlr_foreign_toplevel_handle_v1 *handle;
    struct zwlr_foreign_toplevel_handle_v1 *parent;
    struct window *next;
};

static struct wl_display *display;
static struct wl_seat *seat;
static struct zwlr_foreign_toplevel_manager_v1 *manager;
static struct window *windows;
static uint32_t next_id = 1;

static void json_string(const char *value)
{
    const unsigned char *p = (const unsigned char *)(value ? value : "");

    putchar('"');

    while (*p) {
        switch (*p) {
        case '"': fputs("\\\"", stdout); break;
        case '\\': fputs("\\\\", stdout); break;
        case '\b': fputs("\\b", stdout); break;
        case '\f': fputs("\\f", stdout); break;
        case '\n': fputs("\\n", stdout); break;
        case '\r': fputs("\\r", stdout); break;
        case '\t': fputs("\\t", stdout); break;
        default:
            if (*p < 0x20)
                printf("\\u%04x", *p);
            else
                putchar(*p);
        }
        p++;
    }

    putchar('"');
}

static void emit_snapshot(void)
{
    struct window *window;
    bool first = true;

    fputs("{\"windows\":[", stdout);

    for (window = windows; window; window = window->next) {
        if (!window->ready)
            continue;

        if (!first)
            putchar(',');

        printf("{\"id\":%u,\"app_id\":", window->id);
        json_string(window->app_id);
        fputs(",\"title\":", stdout);
        json_string(window->title);
        printf(",\"active\":%s,\"parent\":%s}",
            window->active ? "true" : "false",
            window->parent ? "true" : "false");
        first = false;
    }

    fputs("]}\n", stdout);
    fflush(stdout);
}

static void replace_string(char **destination, const char *value)
{
    char *copy = strdup(value ? value : "");

    if (!copy)
        return;

    free(*destination);
    *destination = copy;
}

static void handle_title(void *data,
    struct zwlr_foreign_toplevel_handle_v1 *handle, const char *title)
{
    replace_string(&((struct window *)data)->title, title);
}

static void handle_app_id(void *data,
    struct zwlr_foreign_toplevel_handle_v1 *handle, const char *app_id)
{
    replace_string(&((struct window *)data)->app_id, app_id);
}

static void handle_output_enter(void *data,
    struct zwlr_foreign_toplevel_handle_v1 *handle, struct wl_output *output) {}

static void handle_output_leave(void *data,
    struct zwlr_foreign_toplevel_handle_v1 *handle, struct wl_output *output) {}

static void handle_state(void *data,
    struct zwlr_foreign_toplevel_handle_v1 *handle, struct wl_array *state)
{
    struct window *window = data;
    uint32_t *value;

    window->active = false;

    wl_array_for_each(value, state) {
        if (*value == ZWLR_FOREIGN_TOPLEVEL_HANDLE_V1_STATE_ACTIVATED)
            window->active = true;
    }
}

static void handle_done(void *data,
    struct zwlr_foreign_toplevel_handle_v1 *handle)
{
    ((struct window *)data)->ready = true;
    emit_snapshot();
}

static void handle_closed(void *data,
    struct zwlr_foreign_toplevel_handle_v1 *handle)
{
    struct window *window = data;
    struct window **link = &windows;

    while (*link && *link != window)
        link = &(*link)->next;

    if (*link)
        *link = window->next;

    zwlr_foreign_toplevel_handle_v1_destroy(handle);
    free(window->app_id);
    free(window->title);
    free(window);
    emit_snapshot();
}

static void handle_parent(void *data,
    struct zwlr_foreign_toplevel_handle_v1 *handle,
    struct zwlr_foreign_toplevel_handle_v1 *parent)
{
    ((struct window *)data)->parent = parent;
}

static const struct zwlr_foreign_toplevel_handle_v1_listener handle_listener = {
    .title = handle_title,
    .app_id = handle_app_id,
    .output_enter = handle_output_enter,
    .output_leave = handle_output_leave,
    .state = handle_state,
    .done = handle_done,
    .closed = handle_closed,
    .parent = handle_parent,
};

static void manager_toplevel(void *data,
    struct zwlr_foreign_toplevel_manager_v1 *foreign_manager,
    struct zwlr_foreign_toplevel_handle_v1 *handle)
{
    struct window *window = calloc(1, sizeof(*window));
    struct window **tail = &windows;

    if (!window)
        exit(EXIT_FAILURE);

    window->id = next_id++;
    window->handle = handle;

    while (*tail)
        tail = &(*tail)->next;
    *tail = window;

    zwlr_foreign_toplevel_handle_v1_add_listener(
        handle, &handle_listener, window);
}

static void manager_finished(void *data,
    struct zwlr_foreign_toplevel_manager_v1 *foreign_manager)
{
    manager = NULL;
}

static const struct zwlr_foreign_toplevel_manager_v1_listener manager_listener = {
    .toplevel = manager_toplevel,
    .finished = manager_finished,
};

static void registry_global(void *data, struct wl_registry *registry,
    uint32_t name, const char *interface, uint32_t version)
{
    if (strcmp(interface,
            zwlr_foreign_toplevel_manager_v1_interface.name) == 0) {
        uint32_t bind_version = version < 3 ? version : 3;
        manager = wl_registry_bind(registry, name,
            &zwlr_foreign_toplevel_manager_v1_interface, bind_version);
        zwlr_foreign_toplevel_manager_v1_add_listener(
            manager, &manager_listener, NULL);
    } else if (!seat && strcmp(interface, wl_seat_interface.name) == 0) {
        uint32_t bind_version = version < 5 ? version : 5;
        seat = wl_registry_bind(registry, name,
            &wl_seat_interface, bind_version);
    }
}

static void registry_remove(void *data,
    struct wl_registry *registry, uint32_t name) {}

static const struct wl_registry_listener registry_listener = {
    .global = registry_global,
    .global_remove = registry_remove,
};

static void process_command(void)
{
    char line[64];
    unsigned int id;
    struct window *window;

    if (!fgets(line, sizeof(line), stdin)) {
        manager = NULL;
        return;
    }

    if (sscanf(line, "activate %u", &id) != 1)
        return;

    for (window = windows; window; window = window->next) {
        if (window->id == id) {
            zwlr_foreign_toplevel_handle_v1_activate(window->handle, seat);
            wl_display_flush(display);
            return;
        }
    }
}

int main(void)
{
    struct wl_registry *registry;
    int display_fd;

    display = wl_display_connect(NULL);
    if (!display) {
        fputs("tinybar-toplevel-helper: cannot connect to Wayland\n", stderr);
        return EXIT_FAILURE;
    }

    registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);

    if (wl_display_roundtrip(display) < 0 || !manager || !seat ||
        wl_display_roundtrip(display) < 0) {
        fputs("tinybar-toplevel-helper: required protocol unavailable\n", stderr);
        return EXIT_FAILURE;
    }

    emit_snapshot();
    display_fd = wl_display_get_fd(display);

    while (manager) {
        fd_set readers;
        int maximum = display_fd > STDIN_FILENO ? display_fd : STDIN_FILENO;

        FD_ZERO(&readers);
        FD_SET(display_fd, &readers);
        FD_SET(STDIN_FILENO, &readers);

        if (select(maximum + 1, &readers, NULL, NULL, NULL) < 0) {
            if (errno == EINTR)
                continue;
            break;
        }

        if (FD_ISSET(display_fd, &readers) &&
            wl_display_dispatch(display) < 0)
            break;

        if (FD_ISSET(STDIN_FILENO, &readers))
            process_command();
    }

    wl_display_disconnect(display);
    return EXIT_SUCCESS;
}
