#!/usr/bin/python3
"""Exercise real keybindings inside an isolated headless labwc session."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

BASE = Path(__file__).resolve().parent.parent
HELPER = BASE / 'build/app-shortcut'

def fixture():
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, Gdk, Gio, GLib
    app_id, count, log_path, mode = sys.argv[2:]
    GLib.set_prgname(app_id)
    app = Gtk.Application(application_id=app_id, flags=Gio.ApplicationFlags.NON_UNIQUE)
    def log(event, **details):
        with open(log_path, 'a') as f:
            f.write(json.dumps(dict(event=event, **details)) + '\n')
    def activate(app):
        for number in range(int(count)):
            window = Gtk.ApplicationWindow(application=app, title=f'Shortcut test {number}')
            window.set_default_size(300, 200)
            window.set_child(Gtk.Label(label='Isolated shortcut test'))
            def close(w):
                log('close')
                return mode == 'refuse-close'
            window.connect('close-request', close)
            controller = Gtk.EventControllerKey.new()
            controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            def key(c, keyval, code, state):
                name = Gdk.keyval_name(keyval)
                log('key', key=name, state=int(state))
                if mode == 'native' and state == Gdk.ModifierType.CONTROL_MASK:
                    if name == 'w':
                        log('tab-close')
                        return True
                    if name == 'q':
                        log('quit')
                        app.quit()
                        return True
                return False
            controller.connect('key-pressed', key)
            window.add_controller(controller)
            window.present()
    app.connect('activate', activate)
    app.run([])

def main():
    processes = []
    results = []
    with tempfile.TemporaryDirectory(prefix='mac-keys-') as tmp:
        root = Path(tmp)
        runtime = root / 'run'
        runtime.mkdir(mode=0o700)
        config = root / 'config'
        config.mkdir()
        (config / 'rc.xml').write_text(f'''<labwc_config><keyboard><default/>
<keybind key="W-w" onRelease="yes"><action name="Execute" command="{HELPER} close"/></keybind>
<keybind key="W-q" onRelease="yes"><action name="Execute" command="{HELPER} quit"/></keybind>
</keyboard></labwc_config>''')
        env = os.environ.copy()
        env.update(XDG_RUNTIME_DIR=str(runtime), WLR_BACKENDS='headless',
                   WLR_RENDERER='pixman', WLR_HEADLESS_OUTPUTS='1',
                   GDK_BACKEND='wayland', GSK_RENDERER='cairo',
                   GTK_A11Y='none', DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent')
        def spawn(args, name):
            with open(root / (name + '.stderr'), 'w') as log:
                p = subprocess.Popen(args, env=env, stdout=log, stderr=log)
            processes.append(p)
            return p
        def wait_for(predicate, label, timeout=6):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if predicate(): return
                time.sleep(.05)
            raise AssertionError(label)
        def run(args):
            return subprocess.check_output(args, env=env, text=True, timeout=6)
        def windows():
            return json.loads(run([str(HELPER), 'list']))
        def count(app):
            return sum(w['app_id'] == app for w in windows())
        def active(app):
            return any(w['app_id'] == app and w['active'] for w in windows())
        def events(path):
            return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        def fixture_app(app, n, mode='ordinary'):
            log = root / (app + '.events')
            p = spawn([sys.executable, __file__, '--fixture', app, str(n), str(log), mode], app)
            try:
                wait_for(lambda: count(app) == n and active(app), 'fixture windows: ' + app)
            except AssertionError:
                print('Fixture diagnostics:', p.poll(), windows(), flush=True)
                raise
            return p, log
        def super_key(key):
            # Release the letter while Super is still held: catches modifier leakage.
            run(['/usr/bin/wtype', '-M', 'logo', '-P', key, '-s', '70', '-p', key,
                 '-s', '150', '-m', 'logo'])
        def passed(name):
            results.append(name)
            print('PASS:', name, flush=True)
        try:
            compositor = spawn([shutil.which('labwc') or '/usr/local/bin/labwc', '-C', str(config)], 'compositor')
            wait_for(lambda: any(p.is_socket() for p in runtime.glob('wayland-*')), 'compositor socket')
            env['WAYLAND_DISPLAY'] = next(p.name for p in runtime.glob('wayland-*') if p.is_socket())
            assert json.loads(run([str(HELPER), 'plan-quit']))['action'] == 'none'
            passed('No focused app produces no action')

            sentinel, _ = fixture_app('org.example.Unrelated', 1)
            browser, log = fixture_app('org.mozilla.firefox', 2, 'native')
            super_key('w')
            wait_for(lambda: any(e['event'] == 'tab-close' for e in events(log)), 'native Ctrl+W delivery')
            assert count('org.mozilla.firefox') == 2
            assert count('org.example.Unrelated') == 1
            passed('Super+W invokes tab close, keeps other windows, and strips Super')
            super_key('q')
            wait_for(lambda: browser.poll() is not None, 'native quit')
            assert any(e['event'] == 'quit' for e in events(log))
            assert count('org.example.Unrelated') == 1
            passed('Super+Q invokes normal app quit without touching another app')

            first = spawn(['/usr/bin/foot', '--app-id=foot', '/bin/sleep', '120'], 'foot1')
            wait_for(lambda: count('foot') == 1, 'first foot')
            second = spawn(['/usr/bin/foot', '--app-id=foot', '/bin/sleep', '120'], 'foot2')
            wait_for(lambda: count('foot') == 2 and active('foot'), 'second foot')
            super_key('w')
            wait_for(lambda: count('foot') == 1, 'one foot closes')
            assert count('org.example.Unrelated') == 1
            passed('Real Foot: Super+W closes exactly one terminal')
            third = spawn(['/usr/bin/foot', '--app-id=foot', '/bin/sleep', '120'], 'foot3')
            wait_for(lambda: count('foot') == 2 and active('foot'), 'third foot')
            super_key('q')
            wait_for(lambda: count('foot') == 0, 'all foot close')
            assert count('org.example.Unrelated') == 1
            passed('Real Foot: Super+Q closes all Foot windows, keeps unrelated app')

            refusing, log = fixture_app('org.example.Unsaved', 1, 'refuse-close')
            super_key('q')
            wait_for(lambda: any(e['event'] == 'close' for e in events(log)), 'close request')
            assert count('org.example.Unsaved') == 1
            assert refusing.poll() is None
            passed('Application can refuse closure or show a save prompt')

            run(['/usr/bin/wtype', '-M', 'ctrl', '-k', 'w', '-m', 'ctrl'])
            wait_for(lambda: any(e['event'] == 'key' and e['key'] == 'w' and e['state'] == 4
                                 for e in events(log)), 'original Ctrl+W')
            assert count('org.example.Unsaved') == 1
            passed('Original Ctrl+W remains available to applications')
        finally:
            for p in reversed(processes):
                if p.poll() is None:
                    p.terminate()
                    try: p.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        p.wait()
            reports = BASE.parents[1] / 'reports/shortcuts'
            reports.mkdir(parents=True, exist_ok=True)
            for source in root.glob('*.stderr'):
                (reports / source.name).write_text(source.read_text())
            (reports / 'results.json').write_text(json.dumps(results, indent=2) + '\n')

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--fixture': fixture()
    else: main()
