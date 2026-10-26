# Super close and quit shortcuts

limDE's app-aware close and quit keys for labwc.

| Shortcut | Behavior |
| --- | --- |
| Super+W | App-native tab/document close in Firefox, PCManFM, LibreOffice and Zed; ordinary window close in Foot, MuPDF, Papers and other apps. |
| Super+Q | App-native quit in Firefox and LibreOffice; normal close requests to every main window with the active app's identifier in other apps, including Foot and MuPDF. |

Super is the Windows/logo key. The shortcuts fire when the key combination is
released. Existing Ctrl shortcuts and Alt+F4 remain available.

The helper never kills or signals app processes. Applications retain control over
save/confirmation prompts. Closing all windows may leave an app's background
service running. Foot's windows contain independent programs: Super+Q closes all
Foot windows in the desktop session. For unrecognized apps with tabs, Super+W
closes the window; another native shortcut rule can be added when needed.

## Installed files

- `~/.config/labwc/rc.xml`: two global keyboard bindings.
- `~/.local/bin/app-shortcut`: one-shot Wayland helper.
- `~/.local/share/mac-style-shortcuts/`: helper source, protocol, build script and this guide.
- `~/.local/state/mac-style-shortcuts/installation.json`: backup location and installation metadata.

The backup contains the complete pre-change `rc.xml`. To undo only this change
without overwriting subsequent desktop edits, remove the W-w and W-q keybinds
whose commands refer to `app-shortcut`, then reload labwc.

## Diagnostics and maintenance

`app-shortcut list`, `app-shortcut plan-close` and `app-shortcut plan-quit` are
read-only diagnostics. `close` and `quit` perform the actions on the focused app.
The list command exposes app identifiers and focus state, not window titles.

Rules live in `native_key()` in `app-shortcut.c`. Zed uses Ctrl+F4 for tab close
because its integrated terminal consumes Ctrl+W. Dialogs receive a window close
request instead of forwarding a document shortcut. Unknown or empty app IDs are
never used to close unrelated apps. Group closing excludes child dialogs so
existing confirmation dialogs are not automatically dismissed.

Run `sh build.sh` to rebuild (requires gcc, wayland-scanner and wayland-client
development files); copy `build/app-shortcut` to `~/.local/bin/app-shortcut`.
The runtime needs the installed `wtype` command and labwc's foreign-toplevel
protocol. No background daemon or startup program is added.

## Validation

The workspace's `tests/check_shortcuts.py` runs a separate headless compositor
using a temporary Wayland socket. Seven integration checks passed:

1. No focused app produces no action.
2. Super+W forwards native tab-close with Ctrl only, including when Super is held.
3. Super+Q invokes native app quit without closing another app.
4. Real Foot: Super+W closes only one terminal.
5. Real Foot: Super+Q closes all Foot windows and preserves an unrelated app.
6. Applications can refuse closure (e.g. for save prompts).
7. Original Ctrl+W reaches the application unchanged.

Real user windows were inspected only through read-only diagnostics.
