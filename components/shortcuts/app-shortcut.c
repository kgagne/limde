#define _POSIX_C_SOURCE 200809L
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <wayland-client.h>
#include "toplevel-protocol.h"

/* One-shot client: snapshot the focused app, then send ordinary close requests
 * or that app's native shortcut. Never signal/kill application processes. */
struct window {
    struct zwlr_foreign_toplevel_handle_v1 *handle, *parent;
    char *app;
    bool active, ready;
    unsigned id;
    struct window *next;
};
static struct wl_display *display;
static struct zwlr_foreign_toplevel_manager_v1 *manager;
static struct window *windows;
static unsigned next_id;

static void title(void *d, struct zwlr_foreign_toplevel_handle_v1 *h, const char *s) {}
static void app_id(void *d, struct zwlr_foreign_toplevel_handle_v1 *h, const char *s) {
    struct window *w = d;
    free(w->app);
    w->app = strdup(s);
    if (!w->app) exit(1);
}
static void output(void *d, struct zwlr_foreign_toplevel_handle_v1 *h, struct wl_output *o) {}
static void state(void *d, struct zwlr_foreign_toplevel_handle_v1 *h, struct wl_array *a) {
    struct window *w = d;
    uint32_t *v;
    w->active = false;
    wl_array_for_each(v, a)
        if (*v == ZWLR_FOREIGN_TOPLEVEL_HANDLE_V1_STATE_ACTIVATED) w->active = true;
}
static void done(void *d, struct zwlr_foreign_toplevel_handle_v1 *h) {
    ((struct window *)d)->ready = true;
}
static void closed(void *d, struct zwlr_foreign_toplevel_handle_v1 *h) {
    struct window *w = d, **p = &windows;
    while (*p && *p != w) p = &(*p)->next;
    if (*p) *p = w->next;
    for (struct window *child = windows; child; child = child->next)
        if (child->parent == h) child->parent = NULL;
    zwlr_foreign_toplevel_handle_v1_destroy(h);
    free(w->app);
    free(w);
}
static void parent(void *d, struct zwlr_foreign_toplevel_handle_v1 *h,
                   struct zwlr_foreign_toplevel_handle_v1 *p) {
    ((struct window *)d)->parent = p;
}
static const struct zwlr_foreign_toplevel_handle_v1_listener listener = {
    .title = title, .app_id = app_id, .output_enter = output,
    .output_leave = output, .state = state, .done = done,
    .closed = closed, .parent = parent,
};
static void toplevel(void *d, struct zwlr_foreign_toplevel_manager_v1 *m,
                     struct zwlr_foreign_toplevel_handle_v1 *h) {
    struct window *w = calloc(1, sizeof(*w));
    if (!w) exit(1);
    w->handle = h;
    w->id = ++next_id;
    w->next = windows;
    windows = w;
    zwlr_foreign_toplevel_handle_v1_add_listener(h, &listener, w);
}
static void finished(void *d, struct zwlr_foreign_toplevel_manager_v1 *m) { manager = NULL; }
static const struct zwlr_foreign_toplevel_manager_v1_listener manager_listener = {
    .toplevel = toplevel, .finished = finished,
};
static void global(void *d, struct wl_registry *r, uint32_t name,
                   const char *interface, uint32_t version) {
    if (!strcmp(interface, zwlr_foreign_toplevel_manager_v1_interface.name)) {
        manager = wl_registry_bind(r, name,
            &zwlr_foreign_toplevel_manager_v1_interface, version < 3 ? version : 3);
        zwlr_foreign_toplevel_manager_v1_add_listener(manager, &manager_listener, NULL);
    }
}
static void removed(void *d, struct wl_registry *r, uint32_t n) {}
static const struct wl_registry_listener registry_listener = {global, removed};

static void json_string(const char *s) {
    putchar('"');
    for (const unsigned char *p = (const unsigned char *)(s ? s : ""); *p; p++) {
        if (*p == '"' || *p == '\\') printf("\\%c", *p);
        else if (*p < 32) printf("\\u%04x", *p);
        else putchar(*p);
    }
    putchar('"');
}
static bool is(const char *app, const char *name) { return app && !strcasecmp(app, name); }
static bool firefox(const char *app) {
    return is(app, "firefox") || is(app, "firefox-esr") ||
        is(app, "Navigator") || is(app, "org.mozilla.firefox");
}
static bool office(const char *app) {
    return app && (!strncasecmp(app, "libreoffice", 11) || is(app, "soffice"));
}
static const char *native_key(const struct window *w, bool quit) {
    /* A dialog's Close should dismiss the dialog, not its parent document. */
    if (w->parent) return NULL;
    if (firefox(w->app) || office(w->app)) return quit ? "q" : "w";
    if (!quit && is(w->app, "pcmanfm")) return "w";
    /* Zed's terminal captures Ctrl+W/Q. Ctrl+F4 closes the active pane item. */
    if (!quit && (is(w->app, "dev.zed.Zed") || is(w->app, "zed"))) return "F4";
    return NULL;
}
static struct window *root_of(struct window *w) {
    for (unsigned depth = 0; w->parent && depth < next_id; depth++) {
        struct window *p;
        for (p = windows; p && p->handle != w->parent; p = p->next) {}
        if (!p || p == w) break;
        w = p;
    }
    return w;
}
static bool same_app(const struct window *w, const struct window *active) {
    /* Missing app IDs must never group unrelated windows together. */
    return w == active || (w->app && active->app && *active->app &&
        !strcasecmp(w->app, active->app));
}
int main(int argc, char **argv) {
    if (argc != 2 || (strcmp(argv[1], "close") && strcmp(argv[1], "quit") &&
        strcmp(argv[1], "list") && strcmp(argv[1], "plan-close") && strcmp(argv[1], "plan-quit"))) {
        fputs("Usage: app-shortcut close|quit|list|plan-close|plan-quit\n", stderr);
        return 2;
    }
    alarm(5);
    display = wl_display_connect(NULL);
    if (!display) { perror("app-shortcut: Wayland connection"); return 1; }
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    if (wl_display_roundtrip(display) < 0 || !manager || wl_display_roundtrip(display) < 0) {
        fputs("app-shortcut: window management protocol unavailable\n", stderr);
        wl_display_disconnect(display);
        return 1;
    }
    if (!strcmp(argv[1], "list")) {
        bool first = true;
        putchar('[');
        for (struct window *w = windows; w; w = w->next) {
            if (!w->ready) continue;
            if (!first) putchar(',');
            first = false;
            printf("{\"id\":%u,\"app_id\":", w->id);
            json_string(w->app);
            printf(",\"active\":%s,\"parent\":%s}", w->active ? "true" : "false",
                w->parent ? "true" : "false");
        }
        puts("]");
        wl_display_disconnect(display);
        return 0;
    }
    struct window *active = NULL;
    for (struct window *w = windows; w; w = w->next)
        if (w->ready && w->active) { active = w; break; }
    /* No focused application (desktop, launcher, or lock screen): no action. */
    if (!active) {
        puts("{\"action\":\"none\"}");
        wl_display_disconnect(display);
        return 0;
    }
    bool quit = strstr(argv[1], "quit") != NULL;
    bool dry = !strncmp(argv[1], "plan-", 5);
    const char *key = native_key(active, quit);
    struct window *target = quit ? root_of(active) : active;
    unsigned count = 0;
    for (struct window *w = windows; w; w = w->next)
        if (w->ready && ((!quit && w == target) || (quit && !w->parent && same_app(w, target)))) count++;
    printf("{\"app_id\":");
    json_string(target->app);
    printf(",\"action\":\"%s\",\"windows\":%u", key ? "native-shortcut" : "close-windows", count);
    if (key) { fputs(",\"key\":\"Ctrl+", stdout); fputs(key, stdout); putchar('"'); }
    puts("}");
    fflush(stdout);
    if (dry) { wl_display_disconnect(display); return 0; }
    if (key) {
        wl_display_disconnect(display);
        execl("/usr/bin/wtype", "wtype", "-M", "ctrl", "-k", key, "-m", "ctrl", (char *)NULL);
        perror("app-shortcut: wtype");
        return 1;
    }
    for (struct window *w = windows; w; w = w->next)
        if (w->ready && ((!quit && w == target) || (quit && !w->parent && same_app(w, target))))
            zwlr_foreign_toplevel_handle_v1_close(w->handle);
    int result = wl_display_roundtrip(display);
    wl_display_disconnect(display);
    return result < 0 ? 1 : 0;
}
