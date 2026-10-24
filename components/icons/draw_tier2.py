#!/usr/bin/env python3
"""Draw tiers 2 and 3 of elachisto's icons into src/: the system concepts apps request
through freedesktop icon names, and text-editing controls. Names that only rename an
existing icon are aliases (aliases.toml), not drawings. Style rules: README.md.
"""
import math

from _draw import (FILE, FOLDER, SLASH, SRC, arc_arrow, circle, dot, f, gear, path, polar,
                   polygon, rect, star, star_left_half, write)

# --- navigation ---------------------------------------------------------------------
write('chevron-left', path('M15 4.5L7.5 12l7.5 7.5'))
write('chevron-right', path('M9 4.5l7.5 7.5L9 19.5'))
write('chevron-up', path('M4.5 15.5L12 8l7.5 7.5'))
write('chevron-down', path('M4.5 8.5L12 16l7.5-7.5'))
write('go-first', path('M18 5l-7 7 7 7'), path('M6.5 5v14'))
write('go-last', path('M6 5l7 7-7 7'), path('M17.5 5v14'))
write('go-top', path('M5 18l7-7 7 7'), path('M5 6.5h14'))
write('go-bottom', path('M5 6l7 7 7-7'), path('M5 17.5h14'))
write('go-jump', path('M4 19.5V13a5 5 0 0 1 5-5h11'), path('M16.25 4.25L20 8l-3.75 3.75'))
write('menu', path('M3.5 6h17M3.5 12h17M3.5 18h17'))
write('more-vertical', dot(12, 5, 1.6), dot(12, 12, 1.6), dot(12, 19, 1.6))
write('more-horizontal', dot(5, 12, 1.6), dot(12, 12, 1.6), dot(19, 12, 1.6))
write('drag-handle', *(dot(x, y, 1.35) for x in (9, 15) for y in (6, 12, 18)))
write('sort-ascending', path('M3 6h5M3 12h8.5M3 18h12'), path('M19 19.5V4.5M16 7.5l3-3 3 3'))
write('sort-descending', path('M3 6h12M3 12h8.5M3 18h5'), path('M19 4.5v15M16 16.5l3 3 3-3'))

# --- windows and views --------------------------------------------------------------
write('window-maximize', rect(4, 4, 16, 16))
write('window-minimize', path('M5 18.5h14'))
write('window-restore', rect(3.5, 8, 12.5, 12.5, 2),
      path('M8 8V5.25A1.75 1.75 0 0 1 9.75 3.5h9A1.75 1.75 0 0 1 20.5 5.25v9'
           'a1.75 1.75 0 0 1-1.75 1.75H16'))
write('window-new', rect(2.25, 3.75, 19.5, 16.5), path('M2.25 8h19.5'), path('M12 11v6.25M8.875 14.125h6.25'))
write('sidebar', rect(2.25, 3.75, 19.5, 16.5), path('M9 3.75v16.5'))
write('fullscreen', path('M3.5 8.5V3.5h5M15.5 3.5h5v5M20.5 15.5v5h-5M8.5 20.5h-5v-5'))
write('fullscreen-exit', path('M8.5 3.5v5h-5M15.5 3.5v5h5M15.5 20.5v-5h5M8.5 20.5v-5h-5'))
write('view-grid', *(rect(x, y, 7.75, 7.75, 1.5) for x in (2.75, 13.5) for y in (2.75, 13.5)))
write('app-grid', *(dot(x, y, 1.6) for x in (5, 12, 19) for y in (5, 12, 19)))
write('pin', path('M9 2.75h6M10 2.75v6.5L6.5 12.75v1.75h11v-1.75L14 9.25v-6.5M12 14.5v6.75'))
write('eye-slash', path('M1.75 12C4 7.5 7.75 5.25 12 5.25s8 2.25 10.25 6.75C20 16.5 16.25 18.75 12 18.75'
                        'S4 16.5 1.75 12z'), circle(12, 12, 3.25), SLASH)

# --- editing and documents ----------------------------------------------------------
PENCIL = path('M15.5 4.5l4 4L9 19 3.75 20.25 5 15z')
write('pencil', PENCIL, path('M13 7l4 4'))
write('edit-clear', path('M8.5 4.75h11a1.75 1.75 0 0 1 1.75 1.75v11a1.75 1.75 0 0 1-1.75 1.75h-11L2.25 12z'),
      path('M11.5 9.5l5 5M16.5 9.5l-5 5'))
write('select-all', '<rect x="3.25" y="3.25" width="17.5" height="17.5" rx="2.25" stroke-dasharray="3 3.5"/>',
      rect(8, 8, 8, 8, 1))
write('check', path('M4.25 12.75l5 5L19.75 6.5'))
write('file-plus', *FILE, path('M12 11.5v6.5M8.75 14.75h6.5'))
write('clock', circle(12, 12, 9.75), path('M12 6.75V12l3.5 2.25'))
write('printer', path('M6.5 9V3.25h11V9'), rect(2.25, 9, 19.5, 8.5, 2),
      path('M6.5 14.25h11v7h-11z'), dot(17.75, 12, 1))
write('scanner', rect(2.25, 12.75, 19.5, 7.5, 2), path('M3.25 12.25L20 5.5'), path('M5.75 16.5h4'),
      dot(17.75, 16.5, 1))
write('paper-plane', path('M21.5 2.5L2.5 10l7.75 3.75L14 21.5z'), path('M21.5 2.5L10.25 13.75'))
write('log-out', path('M10 20.75H5.5a1.75 1.75 0 0 1-1.75-1.75V5A1.75 1.75 0 0 1 5.5 3.25H10'),
      path('M15.75 7.5l4.5 4.5-4.5 4.5M20.25 12H9'))
write('share', path('M10.5 4H5.75A1.75 1.75 0 0 0 4 5.75v12.5A1.75 1.75 0 0 0 5.75 20h12.5'
                    'A1.75 1.75 0 0 0 20 18.25V13.5'),
      path('M14 3.75h6.25V10M20.25 3.75L11 13'))
write('link', path('M10 14a4.5 4.5 0 0 0 6.36 0l3-3a4.5 4.5 0 0 0-6.36-6.36l-1.25 1.25'),
      path('M14 10a4.5 4.5 0 0 0-6.36 0l-3 3a4.5 4.5 0 0 0 6.36 6.36l1.25-1.25'))
write('cube', path('M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5z'), path('M3.5 7.25L12 12l8.5-4.75M12 12v9.5'))
write('text-cursor', path('M12 5.5v13'),
      path('M8.75 3.75c1.75 0 3.25.5 3.25 1.75 0-1.25 1.5-1.75 3.25-1.75'),
      path('M8.75 20.25c1.75 0 3.25-.5 3.25-1.75 0 1.25 1.5 1.75 3.25 1.75'))
PICTURE = [rect(2.25, 3.75, 19.5, 16.5), circle(8.25, 9, 1.75),
           path('M2.75 17.25l5-5 4 4 2.75-2.75 6.75 6.5')]
write('picture', *PICTURE)
write('picture-slash', *PICTURE, SLASH)
write('eyedropper', path('M14.5 6.5l3 3'),
      path('M16.25 2.75a2.5 2.5 0 0 1 3.5 3.5L17.5 8.5l-3.5-3.5z'),
      path('M15.75 7.75L7 16.5l-2.75.5.5-2.75 8.75-8.75'), path('M4.25 17l-1.5 1.5a1.25 1.25 0 0 0 1.75 1.75L6 18.75'))

# --- checkboxes and radio buttons ---------------------------------------------------
BOX = rect(3.25, 3.25, 17.5, 17.5, 3)
write('checkbox', BOX)
write('checkbox-checked', BOX, path('M7.5 12.25l3.25 3.25 5.75-6.5'))
write('checkbox-mixed', BOX, path('M8 12h8'))
RING = circle(12, 12, 8.75)
write('radio', RING)
write('radio-checked', RING, '<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>')
write('radio-mixed', RING, path('M8 12h8'))

# --- dialogs and status -------------------------------------------------------------
write('warning', path('M10.27 3.9a2 2 0 0 1 3.46 0l8 13.6A2 2 0 0 1 20 20.5H4a2 2 0 0 1-1.73-3z'),
      path('M12 9v5'), dot(12, 17))
write('error', circle(12, 12, 9.75), path('M9 9l6 6M15 9l-6 6'))
write('question', circle(12, 12, 9.75),
      path('M9.25 9.25a2.75 2.75 0 1 1 3.85 2.52c-.66.29-1.1.92-1.1 1.64v.34'), dot(12, 17))
write('key', circle(7.5, 16.5, 4.25), path('M10.5 13.5l9.25-9.25M16.75 7.25l2.5 2.5M14 10l2 2'))
write('circle-slash', circle(12, 12, 9.75), path('M5.1 5.1l13.8 13.8'))
write('stop-sign', polygon(12, 12, 10, 8, 22.5), path('M9 9l6 6M15 9l-6 6'))
SHIELD = path('M12 2.5l7.75 3v6c0 4.75-3.25 8.5-7.75 10-4.5-1.5-7.75-5.25-7.75-10v-6z')
write('shield-check', SHIELD, path('M8.5 12l2.5 2.5 4.5-5'))
write('shield-exclamation', SHIELD, path('M12 7.5v5'), dot(12, 15.75))
write('shield-xmark', SHIELD, path('M9.5 9.5l5 5M14.5 9.5l-5 5'))
write('shield-lock', SHIELD, rect(8.75, 11, 6.5, 5, 1), path('M10.25 11V9.5a1.75 1.75 0 0 1 3.5 0V11'))
write('lock-open', rect(4, 10, 16, 11.75), path('M7.5 10V7a4.5 4.5 0 0 1 8.75-1.5'), path('M12 14.5v2.75'))
write('update', circle(12, 12, 9.75), path('M12 6.75v9.5M8 12.5l4 4 4-4'))
write('loading', dot(5, 12, 1.6), dot(12, 12, 1.6), dot(19, 12, 1.6))

# --- media --------------------------------------------------------------------------
write('play', path('M7 4.5v15l12-7.5z'))
write('pause', rect(6, 4.5, 4, 15, 1), rect(14, 4.5, 4, 15, 1))
write('stop', rect(5, 5, 14, 14, 2))
write('record', '<circle cx="12" cy="12" r="6.5" fill="currentColor"/>')
write('seek-forward', path('M3 6v12l8.5-6zM12.5 6v12L21 12z'))
write('seek-backward', path('M21 6v12l-8.5-6zM11.5 6v12L3 12z'))
write('skip-forward', path('M5 5.5v13l10-6.5z'), path('M19 5.5v13'))
write('skip-backward', path('M19 5.5v13L9 12z'), path('M5 5.5v13'))
REPEAT = [path('M17 3.5l3 3-3 3M20 6.5H7.5A3.5 3.5 0 0 0 4 10v1.5'),
          path('M7 20.5l-3-3 3-3M4 17.5h12.5A3.5 3.5 0 0 0 20 14v-1.5')]
write('repeat', *REPEAT)
write('repeat-one', *REPEAT, path('M11.25 10.75L12.5 10v4.5'))
write('shuffle', path('M2.75 7h3.5c2.5 0 3.75 1.5 5.75 5s3.25 5 5.75 5h3.5'),
      path('M18.25 14l3 3-3 3'), path('M2.75 17h3.5c1.25 0 2.25-.4 3-1.2M14.75 8.2c.75-.8 1.75-1.2 3-1.2h3.5'),
      path('M18.25 4l3 3-3 3'))

# --- communication, people, places --------------------------------------------------
ENVELOPE = [rect(2, 4.75, 20, 14.5), path('M2.75 6.5l9.25 7 9.25-7')]
write('envelope', *ENVELOPE)
write('envelope-dot', rect(2, 4.75, 15.5, 14.5), path('M2.75 6.5l9.25 7 4-3'),
      f'<circle cx="19.5" cy="5.5" r="3" fill="currentColor" stroke="none"/>')
write('reply', path('M9.5 5L3 11.5l6.5 6.5'), path('M3 11.5h10.5a7 7 0 0 1 7 7V20'))
write('reply-all', path('M8.5 5L2 11.5 8.5 18'), path('M13 5l-6.5 6.5L13 18'), path('M6.5 11.5h7.5a7 7 0 0 1 7 7V20'))
write('forward', path('M14.5 5l6.5 6.5-6.5 6.5'), path('M21 11.5H10.5a7 7 0 0 0-7 7V20'))
write('paperclip', path('M16 7.25l-7 7a2.1 2.1 0 0 0 3 3l7.25-7.25a4.25 4.25 0 0 0-6-6l-7.5 7.5'
                        'a6.25 6.25 0 0 0 8.84 8.84l6.16-6.16'))
write('chat', path('M3.75 5.75A1.75 1.75 0 0 1 5.5 4h13a1.75 1.75 0 0 1 1.75 1.75v9.5A1.75 1.75 0 0 1 18.5 17H10'
                   'l-4.25 3.75V17H5.5a1.75 1.75 0 0 1-1.75-1.75z'))
write('phone-call', path('M4.5 2.75h3l1.75 4.5L7 8.75a11.5 11.5 0 0 0 8.25 8.25l1.5-2.25 4.5 1.75v3'
                         'a1.75 1.75 0 0 1-1.75 1.75C10.75 21.25 2.75 13.25 2.75 4.5A1.75 1.75 0 0 1 4.5 2.75z'))
CALENDAR = [rect(2.75, 4.5, 18.5, 17), path('M2.75 9.5h18.5M8 2.75v3.5M16 2.75v3.5')]
write('calendar', *CALENDAR, *(dot(x, y, 1) for x in (8, 12, 16) for y in (13.5, 17.5)))
write('calendar-plus', *CALENDAR, path('M12 12.5v6M9 15.5h6'))
PERSON = [circle(12, 8, 4), path('M4.25 21a7.75 7.75 0 0 1 15.5 0')]
write('person', *PERSON)
write('person-plus', circle(9.5, 8, 4), path('M2 21a7.5 7.5 0 0 1 15 0'), path('M19.5 8v6M16.5 11h6'))
write('people', circle(8.75, 8.5, 3.5), path('M2 20.5a6.75 6.75 0 0 1 13.5 0'),
      path('M15 4.75a3.5 3.5 0 0 1 0 7.5M17.75 14.25A6.75 6.75 0 0 1 22 20.5'))
write('star', star(12, 12.5, 10.25, 4.4))
write('star-filled', star(12, 12.5, 10.25, 4.4, fill='currentColor'))
write('star-half', star(12, 12.5, 10.25, 4.4), star_left_half(12, 12.5, 10.25, 4.4))
write('bookmark', path('M6 4.25A1.5 1.5 0 0 1 7.5 2.75h9A1.5 1.5 0 0 1 18 4.25V21.25l-6-4.5-6 4.5z'))
MAP_PIN = [path('M12 21.75s-7.25-6.5-7.25-12.25a7.25 7.25 0 0 1 14.5 0c0 5.75-7.25 12.25-7.25 12.25z'),
           circle(12, 9.5, 2.5)]
write('map-pin', *MAP_PIN)
write('map-pin-slash', *MAP_PIN, SLASH)
write('server', rect(2.75, 3, 18.5, 7.5, 1.75), rect(2.75, 13.5, 18.5, 7.5, 1.75),
      dot(7, 6.75), dot(7, 17.25), path('M11.5 6.75h6M11.5 17.25h6'))

# --- files and folders (more types) -------------------------------------------------
write('file-table', *FILE, path('M7.5 11.5h9v7h-9zM7.5 15h9M12 11.5v7'))
write('file-slides', *FILE, rect(7.25, 11.25, 9.5, 6.25, .75), path('M12 17.5v2'))
write('file-shapes', *FILE, circle(9.75, 13.75, 2), path('M12.75 18.75l2.25-4 2.25 4z'))
write('file-font', *FILE, path('M8.25 18.75l3.75-8 3.75 8M9.75 15.75h4.5'))
write('file-gear', *FILE, *gear(12, 15, 4.25, 3.15, 1.25, teeth=6, half=.22, root=.4))
write('file-certificate', *FILE, circle(12, 13.25, 2.75), path('M10.25 15.5v5l1.75-1 1.75 1v-5'))
write('rss', dot(5, 19, 1.5), path('M4.5 11.5a8 8 0 0 1 8 8'), path('M4.5 4.5a15 15 0 0 1 15 15'))
write('puzzle', path('M10 4.75a2 2 0 0 1 4 0V5.5h4.25a1 1 0 0 1 1 1v4.25H18.5a2 2 0 0 0 0 4h.75V19'
                     'a1 1 0 0 1-1 1H14v-.75a2 2 0 0 0-4 0V20H5.75a1 1 0 0 1-1-1v-4.25H5.5a2 2 0 0 0 0-4'
                     'h-.75V6.5a1 1 0 0 1 1-1H10z'))
write('folder-lines', FOLDER, path('M7 12.5h10M7 15.75h7'))
write('folder-play', FOLDER, path('M10.25 10.75v5.75l4.75-2.875z'))
write('folder-layout', FOLDER, rect(6.5, 10.25, 11, 6.5, .75), path('M6.5 13h11M10.5 13v3.75'))
write('folder-magnifying-glass', FOLDER, circle(11.25, 13.25, 2.75), path('M13.25 15.25l2.25 2.25'))
write('folder-person', FOLDER, circle(12, 12, 1.75), path('M8.75 17.5a3.25 3.25 0 0 1 6.5 0'))
write('folder-network', FOLDER, circle(12, 10.75, 1.25), circle(8.25, 16.25, 1.25), circle(15.75, 16.25, 1.25),
      path('M12 12v1.75M8.25 15v-1.25h7.5V15'))

# --- devices ------------------------------------------------------------------------
write('laptop', rect(4, 4.5, 16, 11, 1.75),
      path('M2.25 18.75l1.75-3.25h16l1.75 3.25a1 1 0 0 1-.9 1.5H3.15a1 1 0 0 1-.9-1.5z'))
write('smartphone', rect(6, 2.25, 12, 19.5, 2.5), path('M10.5 18.75h3'))
write('tablet', rect(3.5, 2.75, 17, 18.5), path('M10.5 18.25h3'))
write('tv', rect(1.75, 4.25, 20.5, 13.5), path('M8 20.75h8'))
write('displays', rect(1.75, 5, 9.75, 8.5, 1.5), rect(12.5, 5, 9.75, 8.5, 1.5),
      path('M6.625 13.5v3.5M17.375 13.5v3.5M4.25 17h4.75M15 17h4.75'))
write('projector', rect(2, 8, 20, 9.25), circle(16, 12.625, 2.5), dot(6.5, 12.625),
      path('M5 17.25v2.5M19 17.25v2.5'))
write('headphones', path('M3.5 18v-5a8.5 8.5 0 0 1 17 0v5'), rect(3.5, 14, 4, 7, 1.5), rect(16.5, 14, 4, 7, 1.5))
write('headset', path('M3.5 15v-2a8.5 8.5 0 0 1 17 0v2'), rect(3.5, 12.5, 4, 6.5, 1.5), rect(16.5, 12.5, 4, 6.5, 1.5),
      path('M18.5 19v.25a2.5 2.5 0 0 1-2.5 2.5h-2.75'))
MIC = [rect(9, 2.75, 6, 11, 3), path('M5.5 11a6.5 6.5 0 0 0 13 0'), path('M12 17.5v3.75')]
write('microphone', *MIC)
write('microphone-slash', *MIC, SLASH)
write('speaker', rect(5, 2.75, 14, 18.5), circle(12, 14.25, 3.5), dot(12, 7, 1.1))
CAMERA = [path('M2.75 8.25A1.75 1.75 0 0 1 4.5 6.5h2.75L9 4h6l1.75 2.5h2.75a1.75 1.75 0 0 1 1.75 1.75v10'
               'a1.75 1.75 0 0 1-1.75 1.75h-15a1.75 1.75 0 0 1-1.75-1.75z'), circle(12, 13, 3.75)]
write('camera', *CAMERA)
write('camera-slash', *CAMERA, SLASH)
write('video-camera', rect(1.75, 6, 14, 12), path('M15.75 10.5l6.5-3.5v10l-6.5-3.5'))
write('webcam', circle(12, 10, 7), circle(12, 10, 2.5), path('M12 17v4.25M7.5 21.25h9'))
write('disc', circle(12, 12, 9.75), circle(12, 12, 2.5))
write('sd-card', path('M8.75 2.75h9.5A1.75 1.75 0 0 1 20 4.5v15a1.75 1.75 0 0 1-1.75 1.75H5.75A1.75 1.75 0 0 1 4 19.5V7.5z'),
      path('M10 5.75v2.5M13 5.75v2.5M16 5.75v2.5'))
write('gamepad', path('M7 7h10a5 5 0 0 1 4.9 6l-.85 4.25a2.5 2.5 0 0 1-4.4 1.05L14.6 15.5H9.4l-2.05 2.8'
                      'a2.5 2.5 0 0 1-4.4-1.05L2.1 13A5 5 0 0 1 7 7z'),
      path('M7.25 10v4M5.25 12h4'), dot(15.5, 11), dot(17.75, 13.25))
write('pen-tablet', rect(2.25, 5, 19.5, 14), rect(6.25, 8.25, 11.5, 7.5, 1))
write('touchpad', rect(3, 3.75, 18, 16.5), path('M3 15h18M12 15v5.25'))
write('signal-bars', rect(2.75, 16, 3.5, 5, 1), rect(7.75, 12, 3.5, 9, 1), rect(12.75, 8, 3.5, 13, 1),
      rect(17.75, 4, 3.5, 17, 1))
write('plug', path('M9 2.75v4.5M15 2.75v4.5'), path('M6 7.25h12v3.5a6 6 0 0 1-12 0z'), path('M12 16.75v4.5'))
write('bolt', path('M13.5 2.5L5 13.5h6.5L10 21.5l9-11.5h-6.5z'))
write('bluetooth', path('M7 7.5l10 9-5 4.5V3l5 4.5-10 9'))
write('bluetooth-slash', path('M7 7.5l10 9-5 4.5V3l5 4.5-10 9'), SLASH)
write('fingerprint', path('M7.5 4.5a8.5 8.5 0 0 1 12.5 7.5v1.5'), path('M4 11a8.5 8.5 0 0 1 1.25-4'),
      path('M4 15v-3.5'), path('M8 19.5a12 12 0 0 1-1.5-6.5V12a5.5 5.5 0 0 1 11 0v1.5'),
      path('M12 12v1.5a12 12 0 0 0 1.75 6.25'), path('M17.25 17.5a17 17 0 0 0 .25-2.25'),
      path('M9.25 16.5a12 12 0 0 0 1 3.25'))
write('airplane', path('M12 2.5c.9 0 1.5 1 1.5 2.5v4.75l7.5 4.25v2l-7.5-2.25v4.25l2.25 1.75v1.75L12 20.5'
                       'l-3.75 1.25v-1.75l2.25-1.75V13.25L3 15.5v-2l7.5-4.25V5c0-1.5.6-2.5 1.5-2.5z'))
write('moon', path('M20.5 14.5A8.75 8.75 0 1 1 9.5 3.5a7 7 0 0 0 11 11z'))
write('bell-slash', path('M5.25 16.75V11a6.75 6.75 0 0 1 13.5 0v5.75l2 2H3.25z'),
      path('M9.75 21a2.25 2.25 0 0 0 4.5 0'), path('M12 2.25v2'), SLASH)
write('arrows-up-down', path('M8 20V4M4.5 7.5L8 4l3.5 3.5'), path('M16 4v16M12.5 16.5L16 20l3.5-3.5'))
write('gauge-high', path('M3.5 17a8.5 8.5 0 1 1 17 0'), path('M12 17l4.75-5.5'), dot(12, 17, 1.25))
write('gauge-middle', path('M3.5 17a8.5 8.5 0 1 1 17 0'), path('M12 17V10'), dot(12, 17, 1.25))
write('leaf', path('M5 19c0-8 5-14 15-14 0 10-6 15-14 15z'), path('M5 19l7.5-7.5'))
write('monitor-share', rect(1.75, 3.25, 20.5, 13.5), path('M12 16.75v4M8.5 20.75h7'),
      path('M9.5 12.25l5-5M10.75 7.25h3.75V11'))

# --- categories ---------------------------------------------------------------------
write('wrench', path('M20.25 6.75a4.75 4.75 0 0 1-6.4 4.45L6.6 18.45a1.9 1.9 0 0 1-2.7-2.7l7.25-7.25'
                     'A4.75 4.75 0 0 1 17.25 2.6L14.6 5.25l.9 3.25 3.25.9z'))
write('brush', path('M21 3L11.25 12.75'), path('M10.75 12.25l1 1'),
      path('M10.25 11.25c-2.25 0-4 1.75-4 4 0 1.75-1 3-3 3.75 1.75 1.5 3.75 2.25 5.75 2.25 3.25 0 5-2.25 5-4.75'
           'l-.25-1.5z'))
write('flask', path('M9 2.75h6M10 2.75v6.25L4.5 18.5A1.75 1.75 0 0 0 6 21.25h12a1.75 1.75 0 0 0 1.5-2.75'
                    'L14 9V2.75'), path('M7 14.75h10'))
write('music', circle(6.75, 18, 2.5), circle(16.75, 16, 2.5), path('M9.25 18V5.5l10-2.25v12.75M9.25 9.25l10-2.25'))
write('set-square', path('M3.5 20.5V3.5l17 17z'), path('M7.25 16.75V12.5l4.25 4.25z'),
      path('M3.5 8h1.75M3.5 12h1.75M3.5 16h1.75'))

# --- tier 3: text editing -----------------------------------------------------------
BOLD = ' stroke-width="2.25"'
write('text-bold', f'<path d="M7 4.25h5.75a3.75 3.75 0 0 1 0 7.5H7zM7 11.75h6.75a4 4 0 0 1 0 8H7z"{BOLD}/>')
write('text-italic', path('M10 4.25h7.5M6.5 19.75H14M14.25 4.25l-4.5 15.5'))
write('text-underline', path('M7 3.75v7.25a5 5 0 0 0 10 0V3.75'), path('M5 20.75h14'))
write('text-strikethrough', path('M16.25 6.5C15.5 5 14 4.25 12 4.25c-2.5 0-4.25 1.25-4.25 3.25 0 1.6 1.2 2.6 2.95 3.25'),
      path('M15.75 13.5c.45.6.75 1.25.75 2 0 2.4-2 4-4.5 4-2.25 0-4-1-4.75-2.75'), path('M3.75 12h16.5'))
write('text-heading', path('M5.5 4.5v15M18.5 4.5v15M5.5 12h13'))
write('text', path('M5 5.25h14M12 5.25V19.5'))
write('text-color', path('M6.5 16L12 3.5 17.5 16M8.4 11.75h7.2'), rect(3.5, 18.5, 17, 2.5, .75, filled=True))
write('quote', '<circle cx="7.5" cy="14" r="2.75" fill="currentColor" stroke="none"/>',
      path('M4.75 14c0-4.25 1.75-7 5-8.5'),
      '<circle cx="16.5" cy="14" r="2.75" fill="currentColor" stroke="none"/>',
      path('M13.75 14c0-4.25 1.75-7 5-8.5'))
write('code', path('M8 7l-5 5 5 5M16 7l5 5-5 5M13.75 4.5l-3.5 15'))
for name, lines in (('align-left', ((3, 21), (3, 15), (3, 21), (3, 15))),
                    ('align-center', ((3, 21), (6, 18), (3, 21), (6, 18))),
                    ('align-right', ((3, 21), (9, 21), (3, 21), (9, 21))),
                    ('align-justify', ((3, 21), (3, 21), (3, 21), (3, 21)))):
    write(name, path(''.join(f'M{f(a, y)}H{f(b)}' for (a, b), y in zip(lines, (4.5, 9.5, 14.5, 19.5)))))
write('indent', path('M3 9l3.25 3L3 15'), path('M3 4.5h18M10 9.5h11M10 14.5h11M3 19.5h18'))
write('outdent', path('M6.25 9L3 12l3.25 3'), path('M3 4.5h18M10 9.5h11M10 14.5h11M3 19.5h18'))
write('list-ordered', path('M3.25 4.75L4.5 4v4.75'),
      path('M3.25 11.25a1.4 1.4 0 0 1 2.75.25c0 1-2.75 2.25-2.75 3.25H6'),
      path('M8.75 6.5h12M8.75 13h12M8.75 19.5h12'),
      path('M3.25 17.5h2.5l-1.5 1.75a1.25 1.25 0 1 1-1.1 1.9'))

if __name__ == '__main__':
    print(f'{len(list(SRC.glob("*.svg")))} icons in {SRC}')
