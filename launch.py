#!/usr/bin/env python3
"""
Arooohi — cross-platform one-command launcher (Linux / macOS / Windows).

    launch.py [start]                  start backend+frontend, show the logo, open the
                                       site in your browser, wait until the browser
                                       closes (or Ctrl+C), then save the DB and stop.
    launch.py --browser chrome|firefox force a browser engine
    launch.py --no-browser             boot servers only (stay running; `stop` later)
    launch.py --windowed               open the browser without fullscreen
    launch.py --kiosk                  Firefox/Zen in hard kiosk (no exit key)
    launch.py stop                     stop backend + frontend (with DB checkpoint)
    launch.py status                   show what is running
    launch.py --detect                 show which browser engine would be opened

Pure standard library. Uses explicit IPv4 127.0.0.1 everywhere so it behaves the
same in Chromium and Firefox and on any OS (avoids the localhost -> IPv6 loopback
pitfall that breaks Firefox/gecko).
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT, "backend")
FRONTEND_DIR = os.path.join(ROOT, "frontend")
LOGO_PNG = os.path.join(ROOT, "Misc.", "logo2.png")
LOGO_PY = os.path.join(ROOT, "scripts", "ascii_logo.py")
DB_PATH = os.path.join(BACKEND_DIR, "arooohi.db")
LOG_DIR = os.path.join(tempfile.gettempdir(), "opencode")
STATE_FILE = os.path.join(LOG_DIR, "launch.json")

SITE_URL = "http://127.0.0.1:3000"
BACKEND_HEALTH = "http://127.0.0.1:8000/api/health"

WAIT_SECONDS = 150
IS_WIN = sys.platform.startswith("win")

C = {"cyan": "\033[1;36m", "green": "\033[1;32m", "yellow": "\033[1;33m",
     "red": "\033[1;31m", "dim": "\033[2m", "off": "\033[0m"}


def colour(code, text=""):
    if not sys.stdout.isatty():
        return text
    return f"{C[code]}{text}{C['off']}"


def say(text):
    print(colour("cyan", "[Arooohi]") + " " + text)


def ok(text):
    print(colour("green", "\u2713") + " " + text)


def warn(text):
    print(colour("yellow", "!") + " " + text)


def die(text):
    print(colour("red", "[Arooohi error]") + " " + text, file=sys.stderr)
    sys.exit(1)


def url_up(url, timeout=2.0):
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def read_state():
    try:
        with open(STATE_FILE) as fh:
            return json.load(fh)
    except Exception:
        return {}


def write_state(state):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as fh:
        json.dump(state, fh, indent=2)


# ── tool discovery ─────────────────────────────────────────────────────────────
def backend_python():
    cand = os.path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe") if IS_WIN \
        else os.path.join(BACKEND_DIR, ".venv", "bin", "python")
    return cand if os.path.exists(cand) else sys.executable


def node_path_extra():
    if os.environ.get("NODE_BIN") and os.path.isdir(os.environ["NODE_BIN"]):
        return os.environ["NODE_BIN"]
    if not IS_WIN:
        cand = os.path.join(os.path.expanduser("~"), ".local", "bin")
        if os.path.isdir(cand) and shutil.which("node", path=cand):
            return cand
    return None


# ── servers ────────────────────────────────────────────────────────────────────
def _spawn(name, cmd, logfile, cwd, env=None):
    os.makedirs(LOG_DIR, exist_ok=True)
    logh = open(os.path.join(LOG_DIR, logfile), "ab", buffering=0)
    try:
        if IS_WIN:
            proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=logh,
                                    stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=logh,
                                    stderr=subprocess.STDOUT,
                                    start_new_session=True)
    finally:
        logh.close()
    return {"name": name, "pid": proc.pid}


def start_backend():
    py = backend_python()
    return _spawn("backend",
                  [py, "-m", "uvicorn", "app.main:app",
                   "--host", "127.0.0.1", "--port", "8000", "--reload"],
                  "backend.log", BACKEND_DIR)


def start_frontend():
    npm = "npm.cmd" if IS_WIN else "npm"
    env = dict(os.environ)
    extra = node_path_extra()
    if extra:
        env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    return _spawn("frontend", [npm, "run", "dev"], "frontend.log",
                  FRONTEND_DIR, env)


def wait_for(url, name, logfile, timeout=WAIT_SECONDS):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if url_up(url):
            ok(f"{name} is up: {url}")
            return
        time.sleep(1)
    die(f"{name} did not come up at {url} in {timeout}s "
        f"— check {os.path.join(LOG_DIR, logfile)}")


# ── shutdown / checkpoint ──────────────────────────────────────────────────────
def _kill(pid):
    if IS_WIN:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass


def _kill_forced(pid):
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(pid, signal.SIGKILL)
    except Exception:
        pass


def stop_servers():
    state = read_state()
    any_killed = False
    for key in ("backend", "frontend"):
        pid = state.get(key, {}).get("pid")
        if not pid:
            continue
        print(f"[{colour('cyan', 'Arooohi')}] Stopping {key} (pid {pid}) ...")
        _kill(pid)
        any_killed = True

    n = 0
    while (url_up(BACKEND_HEALTH) or url_up(SITE_URL)) and n < 25:
        time.sleep(1)
        n += 1
    if url_up(BACKEND_HEALTH) or url_up(SITE_URL):
        warn("Ports still busy — forcing shutdown.")
        for key in ("backend", "frontend"):
            pid = state.get(key, {}).get("pid")
            if pid:
                _kill_forced(pid)

    checkpoint_db()
    write_state({})
    if not any_killed:
        ok("Nothing was running that this launcher started.")


def checkpoint_db():
    if not os.path.exists(DB_PATH):
        return
    py = backend_python()
    code = ("import sqlite3, sys\n"
            "c=sqlite3.connect(sys.argv[1], timeout=5); q=c.cursor()\n"
            "q.execute('PRAGMA integrity_check').fetchone()[0]\n"
            "q.execute('PRAGMA wal_checkpoint(TRUNCATE)')\n"
            "print('integrity OK, WAL checkpointed')")
    try:
        out = subprocess.check_output([py, "-c", code, DB_PATH],
                                      stderr=subprocess.DEVNULL, text=True).strip()
        if out:
            ok(f"Database: {out}")
    except Exception:
        pass


def cleanup():
    stop_servers()


# ── browser resolution ─────────────────────────────────────────────────────────
def _which(names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def _chrome_exe():
    if os.path.exists("/opt/helium/chrome"):
        return "/opt/helium/chrome"
    return _which(["google-chrome-stable", "google-chrome", "chromium",
                   "chromium-browser", "msedge", "microsoft-edge"])


def _firefox_argv():
    try:
        if subprocess.call(["flatpak", "info", "app.zen_browser.zen"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0:
            return ["flatpak", "run", "app.zen_browser.zen"]
    except Exception:
        pass
    exe = _which(["firefox", "firefox-esr"])
    return [exe] if exe else None


def _default_engine():
    if IS_WIN or sys.platform == "darwin":
        return "defer"
    try:
        out = subprocess.check_output(["xdg-mime", "query", "default",
                                       "x-scheme-handler/https"],
                                      stderr=subprocess.DEVNULL, text=True).strip().lower()
    except Exception:
        return "defer"
    if any(k in out for k in ("zen", "firefox")):
        return "firefox"
    if any(k in out for k in ("chrome", "chrom", "edge")):
        return "chrome"
    return "defer"


def browser_cmd(engine, fullscreen, kiosk):
    """Return (kind, argv); argv is None when we must fall back to webbrowser."""
    if engine == "auto":
        engine = _default_engine()

    if engine in ("chrome", "chromium", "edge"):
        exe = _chrome_exe()
        if exe:
            argv = [exe, "--no-first-run", "--no-default-browser-check",
                    "--disable-background-mode"]
            if fullscreen:
                argv.append("--start-fullscreen")
            argv.append(SITE_URL)
            return "chromium", argv

    if engine in ("firefox", "gecko", "zen", "defer", "chrome", "chromium", "edge"):
        fzv = _firefox_argv()
        if fzv:
            argv = list(fzv)
            if kiosk:
                argv.append("--kiosk")
            argv.append(SITE_URL)
            return "firefox", argv

    return engine, None


# ── actions ────────────────────────────────────────────────────────────────────
def print_credentials():
    print("\u2500" * 64)
    print(f"  Login page : {SITE_URL}/login")
    print("  Admin      : admin@g.bracu.ac.bd        / admin123")
    print("  Driver     : driver.live@g.bracu.ac.bd  / secret1")
    print("  Rider      : rider.live@g.bracu.ac.bd   / secret2")
    print("  Intruder   : intruder.live@g.bracu.ac.bd / secret3")
    print("  (Fresh @g.bracu.ac.bd accounts work too; the OTP is shown on-screen.)")
    print("\u2500" * 64)


def show_logo():
    try:
        if os.path.exists(LOGO_PY) and os.path.exists(LOGO_PNG):
            import runpy
            code = runpy.run_path(LOGO_PY)
            code["main"]()
    except Exception:
        pass
    print(colour("green", "   A R O O H I") + colour("dim") + "  —  campus ride-sharing" + colour("off"))
    print()


def _wait_forever():
    try:
        while True:
            time.sleep(600)
    except KeyboardInterrupt:
        cleanup()


def action_start(no_browser, engine, fullscreen, kiosk):
    show_logo()
    state = read_state()

    if not url_up(BACKEND_HEALTH):
        say("Starting backend (FastAPI) on :8000 ...")
        state["backend"] = start_backend()
        wait_for(BACKEND_HEALTH, "Backend", "backend.log")
    else:
        warn("Backend already responding on :8000 — leaving it alone.")

    if not url_up(SITE_URL):
        say("Starting frontend (Next.js) on :3000 ...")
        state["frontend"] = start_frontend()
        wait_for(SITE_URL, "Frontend", "frontend.log")
    else:
        warn("Frontend already responding on :3000 — leaving it alone.")

    write_state(state)
    print_credentials()
    print(colour("dim") + f"Site is ready: {SITE_URL}" + colour("off"))

    if no_browser:
        say("--no-browser given; servers stay up — run 'launch.py stop' when done.")
        return

    kind, argv = browser_cmd(engine, fullscreen, kiosk)
    if not argv:
        import webbrowser
        webbrowser.open(SITE_URL)
        warn("Opened via the OS default browser (can't track its close); "
             "press Ctrl+C here to shut down.")
        _wait_forever()
        return

    os.makedirs(LOG_DIR, exist_ok=True)
    logh = open(os.path.join(LOG_DIR, "browser.log"), "ab", buffering=0)
    try:
        proc = subprocess.Popen(argv, stdout=logh, stderr=subprocess.STDOUT)
    finally:
        logh.close()
    say(f"Opening {colour('green', kind)} browser ...")
    say("Closing the browser window will save the DB and stop the app.")
    try:
        proc.wait()
    except KeyboardInterrupt:
        pass
    cleanup()


def do_status():
    print("Status")
    if url_up(BACKEND_HEALTH):
        ok("Backend  :8000  up")
    else:
        warn("Backend  :8000  down")
    if url_up(SITE_URL):
        ok("Frontend :3000  up")
    else:
        warn("Frontend :3000  down")
    state = read_state()
    if state:
        print("Managed pids:")
        for k, v in state.items():
            print(f"  {k}: {v.get('pid')}")
    else:
        print("No servers are managed by this launcher right now.")


def do_detect(engine, kiosk):
    kind, argv = browser_cmd(engine, True, kiosk)
    print(f"Engine   : {kind}")
    print("Command  : " + (" ".join(argv) if argv else "<none — fall back to OS default>"))


def main():
    raw = sys.argv[1:]
    no_browser = "--no-browser" in raw
    windowed = "--windowed" in raw
    kiosk = "--kiosk" in raw
    browser = "auto"
    if "--browser" in raw:
        i = raw.index("--browser")
        if len(raw) > i + 1:
            browser = raw[i + 1]
    fullscreen = not windowed

    if "help" in raw or "-h" in raw or "--help" in raw:
        print(__doc__)
        return
    if "stop" in raw:
        stop_servers()
        ok("Stopped.")
        return
    if "--detect" in raw:
        do_detect(browser, kiosk)
        return
    if "status" in raw:
        do_status()
        return

    try:
        action_start(no_browser=no_browser, engine=browser, fullscreen=fullscreen,
                     kiosk=kiosk)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()