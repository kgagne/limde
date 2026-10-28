"""Panel icons: SVG icons from the icon theme (limde's by default), never font glyphs.

Every icon is drawn by a Gtk.Image from the theme's "-symbolic" variant, so GTK colours it
like the surrounding text. Sizes come from CSS (-gtk-icon-size), one per place: the panel,
popover rows, and the level overlay.
"""
import re
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GioUnix', '2.0')
from gi.repository import Gtk, Gdk, Gio, GioUnix


def brightness_glyph(percent):
    return 'brightness-low' if percent < 34 else 'brightness' if percent < 67 else 'sun-bright'


def volume_glyph(percent, muted=False):
    if muted:
        return 'volume-xmark'
    return 'volume-off' if percent == 0 else 'volume-low' if percent < 50 else 'volume-high'


def signal_glyph(strength):
    return 'wifi-weak' if strength < 35 else 'wifi-fair' if strength < 65 else 'wifi'


# Partial signal icons; these get the dimmed full icon drawn behind them.
PARTIAL_SIGNAL = ('wifi-weak', 'wifi-fair')

# Default icon for each status indicator, before its value refines it.
STATUS_ICONS = {
    'cpu': 'microchip', 'memory': 'memory', 'wifi': 'wifi', 'brightness': 'brightness',
    'volume': 'volume-high', 'battery': 'battery-half', 'notifications': 'bell',
}

# Window app IDs that match no desktop entry, mapped to an icon name.
APP_ICON_FALLBACKS = {
    'soffice': 'libreoffice-startcenter',
    'soffice.bin': 'libreoffice-startcenter',
    'limde.preview': 'eye',
}


def glyph_widget(css_class=None):
    """An empty icon image; set_glyph() fills it."""
    image = Gtk.Image()
    if css_class:
        image.add_css_class(css_class)
    return image


def layered_glyph(css_class):
    """Icon over a dimmed backdrop icon. The icons share one 24-unit box, so the two
    line up when given the same size."""
    back = glyph_widget(css_class)
    back.add_css_class('icon-backdrop')
    front = glyph_widget(css_class)
    stack = Gtk.Overlay()
    stack.set_child(back)
    stack.add_overlay(front)
    return stack, front, back


def set_layered_glyph(library, front, back, name):
    """Draw name on front; behind a partial signal icon, show the full one dimmed."""
    rendered = library.set_glyph(front, name)
    if not (rendered and name in PARTIAL_SIGNAL and library.set_glyph(back, 'wifi')):
        # Keep the backdrop's size as the overlay's base, just invisible.
        library.set_glyph(back, name)
        back.set_opacity(0)
    else:
        back.set_opacity(1)
    return rendered


class IconLibrary:
    def __init__(self):
        self.theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())

    def has(self, name):
        return self.theme.has_icon(name + '-symbolic') or self.theme.has_icon(name)

    def set_glyph(self, image, name):
        """Show icon `name` in image; hide it and return False if the theme lacks it."""
        if not name or not self.has(name):
            image.set_visible(False)
            return False
        image.set_from_icon_name(name if name.endswith('-symbolic') else name + '-symbolic')
        image.set_visible(True)
        return True

    def is_brand(self, name):
        """True when the theme answers name with one of limde's brand icons."""
        if not name or not self.theme.has_icon(name):
            return False
        icon = self.theme.lookup_icon(name, None, 16, 1, Gtk.TextDirection.NONE, 0)
        file = icon.get_file() if icon else None
        path = file.get_path() if file else None
        return bool(path) and Path(path).resolve().name.startswith('brand-')

    def application_widget(self, app_id):
        """The window's app icon: the theme's symbolic version when there is one (limde
        ships many), else the app's own icon drawn at the same visual size."""
        names = []
        fallback = APP_ICON_FALLBACKS.get(app_id.casefold())
        if fallback:
            names.append(fallback)
        native_icon = None
        for candidate in (app_id, app_id + '.desktop', app_id.casefold() + '.desktop'):
            try:
                desktop = GioUnix.DesktopAppInfo.new(candidate)
            except TypeError:
                desktop = None
            if desktop is None:
                continue
            icon = desktop.get_icon()
            if icon is None:
                continue
            if isinstance(icon, Gio.FileIcon) and not icon.get_file().query_exists(None):
                continue
            if isinstance(icon, Gio.ThemedIcon):
                names.extend(icon.get_names())
            native_icon = icon
            break
        names += [app_id, app_id.casefold()]

        for name in dict.fromkeys(names):
            if self.is_brand(name.removesuffix('-symbolic')):
                # limde's app icons carry the app's own colour in their plain copy.
                image = glyph_widget('task-icon')
                image.set_from_icon_name(name.removesuffix('-symbolic'))
                image.set_visible(True)
                return image
            if self.theme.has_icon(name.removesuffix('-symbolic') + '-symbolic'):
                image = glyph_widget('task-icon')
                self.set_glyph(image, name.removesuffix('-symbolic'))
                return image

        if isinstance(native_icon, Gio.FileIcon):
            # Some portable apps bundle a symbolic icon beside their native one.
            path = Path(native_icon.get_file().get_path() or '')
            symbolic = path.with_name(path.stem.removesuffix('-symbolic') + '-symbolic.svg')
            if symbolic.is_file():
                image = Gtk.Image.new_from_gicon(Gio.FileIcon.new(Gio.File.new_for_path(str(symbolic))))
                image.add_css_class('task-icon')
                return image

        if native_icon is not None:
            # Another theme's full-colour icon, usually drawn edge to edge: the
            # task-icon-foreign class shrinks it to the same margin as limde's.
            image = Gtk.Image.new_from_gicon(native_icon)
            image.add_css_class('task-icon')
            image.add_css_class('task-icon-foreign')
            return image
        return None  # Unknown apps keep their text label.

    def status_name(self, kind, text):
        name = STATUS_ICONS.get(kind)
        if kind == 'wifi' and (' OFF' in text or '?' in text):
            name = 'wifi-slash'
        elif kind == 'brightness':
            match = re.search(r'(\d+)%', text)
            if match:
                name = brightness_glyph(int(match.group(1)))
        elif kind == 'volume':
            if 'MUTED' in text:
                name = 'volume-xmark'
            else:
                match = re.search(r'(\d+)%', text)
                if match:
                    name = volume_glyph(int(match.group(1)))
        elif kind == 'battery':
            match = re.search(r'(\d+)%', text)
            if '+' in text.split('|')[0]:
                name = 'battery-bolt'
            elif match:
                level = int(match.group(1))
                name = ('battery-full' if level >= 90 else 'battery-three-quarters' if level >= 65
                        else 'battery-half' if level >= 40 else 'battery-quarter' if level >= 15
                        else 'battery-empty')
            else:
                name = 'battery-exclamation'
        return name


class StatusIndicator(Gtk.Box):
    """Icon plus value. With show_value=False only the icon shows, and the value
    moves to the tooltip; the text still shows if the icon cannot be drawn."""

    def __init__(self, library, kind, show_value=True, layered=False):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.library = library
        self.kind = kind
        self.show_value = show_value
        self.last_text = None
        self.backdrop = None
        if layered:
            holder, self.icon, self.backdrop = layered_glyph('status-icon')
        else:
            holder = self.icon = glyph_widget('status-icon')
        self.value = Gtk.Label()
        self.append(holder)
        self.append(self.value)

    def set_text(self, text, *, display_text=None, icon=None):
        state = (text, display_text, icon)
        if state == self.last_text:
            return
        self.last_text = state
        name = icon or self.library.status_name(self.kind, text)
        if self.backdrop is None:
            rendered = self.library.set_glyph(self.icon, name)
        else:
            rendered = set_layered_glyph(self.library, self.icon, self.backdrop, name)
        visible = text if display_text is None else display_text
        self.value.set_text(visible.partition(' ')[2] if rendered and ' ' in visible else visible)
        shown = (self.show_value or not rendered) and bool(self.value.get_text())
        self.value.set_visible(shown)
        # The icon's margin is its gap to the value; drop it when it stands alone.
        for icon in (self.icon, self.backdrop):
            if icon is None:
                continue
            if shown:
                icon.remove_css_class('icon-only')
            else:
                icon.add_css_class('icon-only')
        self.set_tooltip_text(text)
        self.update_property([Gtk.AccessibleProperty.LABEL], [text])
