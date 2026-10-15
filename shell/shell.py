#!/usr/bin/env python3
"""
BookerOS Web - desktop shell.

Every app on this system is a web app: a folder with a manifest.json and an
HTML entry point (local apps), or just a URL (remote apps). The shell draws
the desktop, the panel and the launcher as web pages too, and opens each app
in its own window with a WebKit view.

Local apps get a `window.os` bridge (files, settings, app management, system
calls). Remote websites never get the bridge.
"""
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, WebKit2  # noqa: E402
try:
    gi.require_version("Wnck", "3.0")
    gi.require_version("GdkX11", "3.0")
    from gi.repository import Wnck, GdkX11  # noqa: E402
except (ValueError, ImportError):
    Wnck = None

import base64
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = os.path.dirname(os.path.abspath(__file__))
SYSTEM_APPS = os.environ.get("BOOKEROS_APPS", os.path.join(BASE, "apps"))
UI = os.path.join(BASE, "ui")
HOME = os.path.expanduser("~")
DATA = os.path.join(HOME, ".local", "share", "bookeros")
USER_APPS = os.path.join(DATA, "apps")
ICONS = os.path.join(DATA, "icons")
DOCS = os.path.join(HOME, "Documents")
PANEL_H = 48
BOOT_TIME = time.time()

ACCENTS = {
    "blue":   {"light": ["#0b57d0", "#ffffff", "#d3e3fd"], "dark": ["#a8c7fa", "#062e6f", "#0842a0"]},
    "green":  {"light": ["#146c2e", "#ffffff", "#c4eed0"], "dark": ["#6dd58c", "#0a3818", "#0f5223"]},
    "purple": {"light": ["#6750a4", "#ffffff", "#e8def8"], "dark": ["#d0bcff", "#381e72", "#4f378b"]},
    "pink":   {"light": ["#b4237c", "#ffffff", "#ffd8ea"], "dark": ["#ffb0cf", "#5e1140", "#7d2a5a"]},
    "orange": {"light": ["#8b5000", "#ffffff", "#ffdcbe"], "dark": ["#ffb870", "#4a2800", "#693c00"]},
}

DEFAULT_SETTINGS = {
    "wallpaper": "meadow",
    "accent": "blue",
    "theme": "light",
    "pinned": ["browser", "files", "notes", "store", "settings"],
    "resolution": "",
    "username": os.environ.get("USER", "booker"),
    "hostname": socket.gethostname() or "bookeros",
}

SLOW_METHODS = {"net.status", "net.wifiList", "net.connect", "net.disconnect", "system.setHostname",
                "apps.install"}
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) "
      "Version/17.0 Safari/605.1.15 BookerOS/1.0")


def run_cmd(args, timeout=30, root=False):
    """Run a command, using passwordless sudo for system changes when not root."""
    if root and os.geteuid() != 0 and shutil.which("sudo"):
        args = ["sudo", "-n"] + args
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", args[0] + ": not installed"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


def nm_split(line):
    """Split a line of `nmcli -t` output on unescaped colons."""
    parts, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


class Network:
    @staticmethod
    def status():
        code, out, _ = run_cmd(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], 10)
        devices = []
        if code == 0:
            for line in out.splitlines():
                d = nm_split(line)
                if len(d) >= 4 and d[1] in ("ethernet", "wifi"):
                    devices.append({"device": d[0], "type": d[1], "state": d[2], "connection": d[3]})
        else:
            # NetworkManager not available (e.g. development machine): infer from the routing table
            code, out, _ = run_cmd(["ip", "-o", "route", "show", "default"], 5)
            m = re.search(r"dev (\S+)", out)
            if m:
                devices.append({"device": m.group(1), "type": "ethernet", "state": "connected", "connection": "Wired"})
        _, ip, _ = run_cmd(["hostname", "-I"], 5)
        return {"devices": devices, "ip": ip.strip().split(" ")[0] if ip.strip() else "",
                "wifi": any(d["type"] == "wifi" for d in devices),
                "online": any(d["state"] == "connected" for d in devices),
                "manager": code == 0 and shutil.which("nmcli") is not None}

    @staticmethod
    def wifi_list():
        code, out, err = run_cmd(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi",
                                  "list", "--rescan", "yes"], 30)
        if code != 0:
            return []
        nets = {}
        for line in out.splitlines():
            f = nm_split(line)
            if len(f) < 4 or not f[1]:
                continue
            n = {"ssid": f[1], "signal": int(f[2] or 0), "secure": bool(f[3] and f[3] != "--"),
                 "security": f[3], "active": f[0] == "*"}
            if n["ssid"] not in nets or n["signal"] > nets[n["ssid"]]["signal"]:
                nets[n["ssid"]] = n
        return sorted(nets.values(), key=lambda n: (not n["active"], -n["signal"]))

    @staticmethod
    def connect(ssid, password):
        args = ["nmcli", "device", "wifi", "connect", ssid]
        if password:
            args += ["password", password]
        code, out, err = run_cmd(args, 60)
        if code != 0:
            code, out, err = run_cmd(args, 60, root=True)
        if code != 0:
            msg = (err or out).strip().splitlines()
            raise RuntimeError(msg[-1] if msg else "Could not connect")
        return True

    @staticmethod
    def disconnect(device):
        run_cmd(["nmcli", "device", "disconnect", device], 20)
        return True

for d in (DATA, USER_APPS, DOCS, ICONS):
    os.makedirs(d, exist_ok=True)


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(value, f, indent=2)
    os.replace(tmp, path)


def file_uri(path):
    return "file://" + urllib.parse.quote(path)


def safe_doc_path(rel):
    """Resolve a path inside ~/Documents, refusing anything that escapes it."""
    rel = (rel or "").lstrip("/")
    full = os.path.realpath(os.path.join(DOCS, rel))
    if full != os.path.realpath(DOCS) and not full.startswith(os.path.realpath(DOCS) + os.sep):
        raise ValueError("path outside Documents")
    return full


# --------------------------------------------------------------------------
# Website name + icon lookup (used when a web app is installed)
# --------------------------------------------------------------------------
def http_get(url, limit=2_500_000, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.headers.get("Content-Type", ""), r.read(limit)


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.in_title, self.in_svg = "", False, 0
        self.meta, self.icons, self.manifest = {}, [], None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "svg":
            self.in_svg += 1
        elif tag == "title" and not self.in_svg:
            self.in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ("og:site_name", "application-name", "apple-mobile-web-app-title") and a.get("content"):
                self.meta.setdefault(key, a["content"].strip())
        elif tag == "link" and a.get("href"):
            rel = a.get("rel", "").lower().split()
            if "manifest" in rel:
                self.manifest = a["href"]
            elif {"icon", "apple-touch-icon", "apple-touch-icon-precomposed"} & set(rel):
                self.icons.append({"href": a["href"], "sizes": a.get("sizes", ""),
                                   "apple": any(r.startswith("apple") for r in rel), "type": a.get("type", "")})

    def handle_endtag(self, tag):
        if tag == "svg":
            self.in_svg = max(0, self.in_svg - 1)
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title and len(self.title) < 300:
            self.title += data


def _icon_size(sizes, href="", typ=""):
    if "any" in sizes or href.endswith(".svg") or "svg" in typ:
        return 256
    best = 0
    for m in re.finditer(r"(\d+)x(\d+)", sizes):
        best = max(best, int(m.group(1)))
    return best


def _host_labels(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    skip = {"www", "m", "en", "com", "co", "uk", "org", "net", "io", "app", "gov", "edu", "ac"}
    return [p for p in host.split(".") if p and p not in skip]


def site_name(p, url):
    for key in ("application-name", "apple-mobile-web-app-title", "og:site_name"):
        v = " ".join(p.meta.get(key, "").split())
        if 0 < len(v) <= 32:
            return v
    title = " ".join(p.title.split())
    labels = _host_labels(url)
    matches = lambda seg: any(l in seg.lower().replace(" ", "") for l in labels)
    segs = [x.strip() for x in re.split(r"\s+[-|\u2013\u2014\u00b7:\u2022]\s+", title) if x.strip()]
    if len(segs) > 1:
        title = next((x for x in segs if matches(x)), segs[0])
    if ", " in title and matches(title.split(", ")[0]):
        title = title.split(", ")[0]
    title = title[:40].strip()
    if title:
        return title
    host = (urllib.parse.urlparse(url).hostname or "Web app")
    return host[4:] if host.startswith("www.") else host


def _to_png(data, out_path):
    """Decode any image GdkPixbuf understands (png, ico, svg, jpeg, gif) and save a 128px PNG."""
    loader = GdkPixbuf.PixbufLoader()
    try:
        loader.write(data)
        loader.close()
    except GLib.Error:
        return False
    pb = loader.get_pixbuf()
    if pb is None or pb.get_width() < 16:
        return False
    if max(pb.get_width(), pb.get_height()) > 128:
        scale = 128 / max(pb.get_width(), pb.get_height())
        pb = pb.scale_simple(max(1, int(pb.get_width() * scale)), max(1, int(pb.get_height() * scale)),
                             GdkPixbuf.InterpType.BILINEAR)
    pb.savev(out_path, "png", [], [])
    return True


def fetch_site_meta(url, app_id):
    """Return (name, icon_png_path_or_None) for a website, as it would appear in a browser tab."""
    final, ctype, body = http_get(url)
    p = _MetaParser()
    p.feed(body.decode("utf-8", "replace"))
    name = site_name(p, final)
    cands = []
    if p.manifest:
        try:
            murl = urllib.parse.urljoin(final, p.manifest)
            _, _, mdata = http_get(murl, 500_000)
            for ic in json.loads(mdata.decode("utf-8", "replace")).get("icons", []):
                if ic.get("src"):
                    cands.append((_icon_size(ic.get("sizes", ""), ic["src"], ic.get("type", "")) + 1,
                                  urllib.parse.urljoin(murl, ic["src"])))
        except Exception:
            pass
    for ic in p.icons:
        size = _icon_size(ic["sizes"], ic["href"], ic["type"]) or (180 if ic["apple"] else 32)
        cands.append((size, urllib.parse.urljoin(final, ic["href"])))
    # prefer icons around 64-256px, then bigger, then smaller
    cands.sort(key=lambda c: (0 if 48 <= c[0] <= 256 else 1 if c[0] > 256 else 2, -c[0] if c[0] <= 256 else c[0]))
    cands.append((16, urllib.parse.urljoin(final, "/favicon.ico")))
    out = os.path.join(ICONS, app_id + ".png")
    for _, src in cands[:6]:
        try:
            if src.startswith("data:"):
                head, b64 = src.split(",", 1)
                data = base64.b64decode(b64) if ";base64" in head else urllib.parse.unquote(b64).encode()
            else:
                _, _, data = http_get(src, 1_500_000)
            if _to_png(data, out):
                return name, out
        except Exception:
            continue
    return name, None


# --------------------------------------------------------------------------
# App registry
# --------------------------------------------------------------------------
class Registry:
    def __init__(self):
        self.apps = {}
        self.reload()

    def reload(self):
        apps = {}
        if os.path.isdir(SYSTEM_APPS):
            for name in sorted(os.listdir(SYSTEM_APPS)):
                m = load_json(os.path.join(SYSTEM_APPS, name, "manifest.json"), None)
                if not m:
                    continue
                m.setdefault("id", name)
                m["dir"] = os.path.join(SYSTEM_APPS, name)
                m["system"] = True
                apps[m["id"]] = m
        for name in sorted(os.listdir(USER_APPS)):
            if name.endswith(".json"):
                m = load_json(os.path.join(USER_APPS, name), None)
                if m and "id" in m:
                    m["system"] = False
                    apps[m["id"]] = m
        names = load_json(os.path.join(ICONS, "names.json"), {})
        for m in apps.values():
            # native programs (e.g. Firefox) fall back to their web version if not installed
            if m.get("exec"):
                if shutil.which(m["exec"][0]):
                    m["native"] = True
                else:
                    m.update(m.get("fallback", {}))
                    m.pop("exec", None)
            if not m.get("native"):
                m.pop("iconCandidates", None)
            icon = None
            for c in m.get("iconCandidates", []):
                if os.path.exists(c):
                    icon = c
                    break
            cached = os.path.join(ICONS, m["id"] + ".png")
            if not icon and m.get("iconFile") and os.path.exists(m["iconFile"]):
                icon = m["iconFile"]
            if not icon and os.path.exists(cached):
                icon = cached
            m["iconFile"] = icon
            if m.get("autoName") and names.get(m["id"]):
                m["name"] = names[m["id"]]
        self.apps = apps

    def needs_meta(self):
        """Remote web apps that don't have a site icon cached yet."""
        return [m for m in self.apps.values()
                if not m.get("native") and not m.get("browser") and re.match(r"^https?://", m.get("url", ""))
                and not m.get("iconFile")]

    def public(self):
        out = []
        for m in self.apps.values():
            if m.get("hidden"):
                continue
            d = {k: m.get(k) for k in
                 ("id", "name", "icon", "color", "url", "description", "system", "category", "native")}
            d["url"] = d["url"] or ""
            d["iconUrl"] = file_uri(m["iconFile"]) if m.get("iconFile") else None
            out.append(d)
        out.sort(key=lambda a: (a["category"] != "system", a["name"].lower()))
        return out

    def entry_url(self, app, arg=None):
        url = app["url"]
        if re.match(r"^[a-z]+://", url):
            return url
        full = os.path.join(app["dir"], url)
        uri = file_uri(full)
        if arg is not None:
            uri += "?arg=" + urllib.parse.quote(str(arg))
        return uri

    def is_local(self, app):
        return not re.match(r"^[a-z]+://", app["url"])


# --------------------------------------------------------------------------
# Shell
# --------------------------------------------------------------------------
class Shell:
    def __init__(self):
        self.registry = Registry()
        self.settings = dict(DEFAULT_SETTINGS, **load_json(os.path.join(DATA, "settings.json"), {}))
        self.storage = load_json(os.path.join(DATA, "storage.json"), {})
        self.windows = {}
        self.next_win = 1
        self.ui_views = []           # desktop, panel, launcher
        self.popup_closed_at = {}

        data_dir = os.path.join(DATA, "webdata")
        cache_dir = os.path.join(HOME, ".cache", "bookeros")
        self.wdm = WebKit2.WebsiteDataManager(base_data_directory=data_dir, base_cache_directory=cache_dir)
        self.context = WebKit2.WebContext.new_with_website_data_manager(self.wdm)
        self.context.connect("download-started", self.on_download)
        try:
            self.wdm.get_cookie_manager().set_persistent_storage(
                os.path.join(data_dir, "cookies.sqlite"), WebKit2.CookiePersistentStorage.SQLITE)
        except Exception:
            pass

        with open(os.path.join(UI, "bridge.js")) as f:
            self.bridge_js = f.read()

        self.gtk_settings = Gtk.Settings.get_default()
        self.gtk_settings.set_property("gtk-decoration-layout", "icon:minimize,maximize,close")
        self.gtk_settings.set_property("gtk-font-name", "Roboto 10")
        self.apply_gtk_theme()
        css = Gtk.CssProvider()
        css.load_from_data(b"""
            headerbar { min-height: 34px; padding: 0 4px 0 10px; border: none; box-shadow: none;
                        background-image: none; background-color: @theme_base_color; }
            headerbar:backdrop { background-color: @theme_base_color; }
            headerbar entry { min-width: 420px; border-radius: 18px; }
            headerbar button { border-radius: 50%; min-width: 26px; min-height: 26px; }
            headerbar .title { font-weight: 500; }
            headerbar .appicon { font-size: 15px; margin-right: 6px; }
        """)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        if self.settings.get("resolution"):
            self.set_resolution(self.settings["resolution"])

        self.desktop = self.make_ui_window("desktop.html", Gdk.WindowTypeHint.DESKTOP)
        self.panel = self.make_ui_window("panel.html", Gdk.WindowTypeHint.DOCK)
        self.launcher = self.make_popup("launcher.html")
        self.quick = self.make_popup("quick.html")
        self.layout()
        Gdk.Screen.get_default().connect("size-changed", lambda *a: GLib.timeout_add(300, self.layout))

        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.toggle_launcher)
        GLib.timeout_add_seconds(1, self.tick)
        self.native = {}
        self.init_native_windows()
        self.meta_busy = False
        GLib.timeout_add_seconds(6, lambda: (self.refresh_meta(), False)[1])
        GLib.timeout_add_seconds(600, self.refresh_meta)

        self.setup = None
        if not self.storage.get("setup.done") and not os.environ.get("BOOKEROS_SKIP_SETUP"):
            self.show_setup()
        elif not self.storage.get("welcome.seen"):
            GLib.timeout_add(1500, lambda: (self.launch("welcome"), False)[1])

    def show_setup(self):
        win = Gtk.Window()
        win.set_decorated(False)
        win.set_skip_taskbar_hint(True)
        win.set_keep_above(True)
        view = self.make_view(True)
        win.add(view)
        win.view = view
        view.load_uri(file_uri(os.path.join(UI, "setup.html")))
        self.ui_views.append(view)
        g = self.screen_rect()
        win.move(g.x, g.y)
        win.resize(g.width, g.height)
        win.connect("delete-event", lambda *a: True)
        win.show_all()
        win.fullscreen()
        self.setup = win

    def finish_setup(self):
        self.storage["setup.done"] = True
        save_json(os.path.join(DATA, "storage.json"), self.storage)
        if self.setup:
            self.ui_views.remove(self.setup.view)
            self.setup.destroy()
            self.setup = None
        GLib.timeout_add(600, lambda: (self.launch("welcome"), False)[1])

    # ---- UI windows (desktop / panel / launcher) -------------------------
    def make_view(self, bridge):
        ucm = WebKit2.UserContentManager()
        view = WebKit2.WebView(web_context=self.context, user_content_manager=ucm)
        s = view.get_settings()
        s.set_enable_developer_extras(True)
        s.set_javascript_can_access_clipboard(True)
        s.set_enable_write_console_messages_to_stdout(True)
        if bridge:
            s.set_allow_file_access_from_file_urls(True)
            ucm.add_script(WebKit2.UserScript(self.bridge_js, WebKit2.UserContentInjectedFrames.TOP_FRAME,
                                              WebKit2.UserScriptInjectionTime.START, None, None))
            ucm.register_script_message_handler("os")
            ucm.connect("script-message-received::os", self.on_message, view)
        return view

    def make_popup(self, page):
        # DOCK type: the compositor skips its square shadow (the bubble draws its own rounded one)
        win = self.make_ui_window(page, Gdk.WindowTypeHint.DOCK, show=False)
        win.set_accept_focus(True)
        win.set_keep_above(True)
        win.connect("focus-out-event", lambda *a: self.close_popups(by_focus=True))
        return win

    def close_popups(self, by_focus=False):
        for name, w in (("launcher", self.launcher), ("quick", self.quick)):
            if w.get_visible() and by_focus:
                # Pressing the Windows key (or clicking the shelf button) takes focus away
                # just before the "toggle" arrives; remember this so the toggle closes it
                # instead of opening it again.
                self.popup_closed_at[name] = time.monotonic()
            w.hide()
        self.emit_to(self.panel.view, "popup", None)

    def apply_gtk_theme(self):
        dark = self.settings.get("theme") == "dark"
        self.gtk_settings.set_property("gtk-application-prefer-dark-theme", dark)
        bg, fg, hover = ("#2b2c2f", "#e3e3e3", "#3c3d41") if dark else ("#ffffff", "#1f1f1f", "#eceef2")
        edge = "#3c3d41" if dark else "#d5d9e0"
        css = f"""
            headerbar, headerbar:backdrop {{ background-color: {bg}; color: {fg}; }}
            headerbar label, headerbar button {{ color: {fg}; }}
            headerbar button {{ background: transparent; border: none; box-shadow: none; }}
            headerbar button:hover {{ background: {hover}; }}
            headerbar:backdrop label {{ opacity: .7; }}
            decoration, decoration:backdrop {{ box-shadow: none; margin: 0; border: none; border-radius: 0; }}
            window.csd, window.csd:backdrop {{ box-shadow: none; margin: 0; background-color: {bg}; }}
            window.solid-csd decoration, window.solid-csd decoration:backdrop {{
                padding: 4px; background-color: {bg}; border: 1px solid {edge}; box-shadow: none; }}
        """.encode()
        if not hasattr(self, "theme_css"):
            self.theme_css = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.theme_css,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self.theme_css.load_from_data(css)

    def public_settings(self):
        return dict(self.settings, accents=ACCENTS)

    def rgba(self, win):
        vis = win.get_screen().get_rgba_visual()
        if vis is not None and win.get_screen().is_composited():
            win.set_visual(vis)
            win.set_app_paintable(True)

    def make_ui_window(self, page, hint, show=True):
        win = Gtk.Window()
        self.rgba(win)
        win.set_decorated(False)
        win.set_type_hint(hint)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        view = self.make_view(True)
        view.set_background_color(Gdk.RGBA(0, 0, 0, 0))
        win.add(view)
        view.load_uri(file_uri(os.path.join(UI, page)))
        view.connect("decide-policy", self.ui_policy)
        win.connect("delete-event", lambda *a: True)
        self.ui_views.append(view)
        win.view = view
        if show:
            win.show_all()
        else:
            view.show()
        return win

    def ui_policy(self, view, decision, kind):
        # links clicked inside shell pages open as browser windows
        if kind == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            uri = decision.get_navigation_action().get_request().get_uri()
            if not uri.startswith("file://") and not uri.startswith("about:"):
                decision.ignore()
                self.open_browser(uri)
                return True
        return False

    def screen_rect(self):
        disp = Gdk.Display.get_default()
        mon = disp.get_primary_monitor() or disp.get_monitor(0)
        return mon.get_geometry()

    def layout(self):
        g = self.screen_rect()
        self.desktop.move(g.x, g.y)
        self.desktop.resize(g.width, g.height)
        self.panel.move(g.x, g.y + g.height - PANEL_H)
        self.panel.resize(g.width, PANEL_H)
        self.panel.set_size_request(g.width, PANEL_H)
        lw, lh = min(620, g.width - 20), min(560, g.height - PANEL_H - 10)
        self.launcher.resize(lw, lh)
        self.launcher.move(g.x, g.y + g.height - PANEL_H - lh)
        qw, qh = 380, min(500, g.height - PANEL_H - 10)
        self.quick.resize(qw, qh)
        self.quick.move(g.x + g.width - qw, g.y + g.height - PANEL_H - qh)
        GLib.timeout_add(200, self.set_strut)
        return False

    def set_strut(self):
        gw = self.panel.get_window()
        if not gw:
            return True
        g = self.screen_rect()
        try:
            xid = gw.get_xid()
            subprocess.run(["xprop", "-id", str(xid), "-f", "_NET_WM_STRUT_PARTIAL", "32c",
                            "-set", "_NET_WM_STRUT_PARTIAL",
                            f"0,0,0,{PANEL_H},0,0,0,0,0,0,{g.x},{g.x + g.width - 1}"], check=False)
            subprocess.run(["xprop", "-id", str(xid), "-f", "_NET_WM_STRUT", "32c",
                            "-set", "_NET_WM_STRUT", f"0,0,0,{PANEL_H}"], check=False)
        except Exception as e:
            print("strut:", e)
        return False

    def toggle_popup(self, which):
        win = self.launcher if which == "launcher" else self.quick
        if win.get_visible():
            self.close_popups()
            return True
        if time.monotonic() - self.popup_closed_at.get(which, 0) < 0.6:
            self.popup_closed_at[which] = 0
            return True
        self.close_popups()
        self.layout()
        win.show_all()
        win.present_with_time(Gdk.CURRENT_TIME)
        win.view.grab_focus()
        self.emit_to(win.view, which + "-open", None)
        self.emit_to(self.panel.view, "popup", which)
        return True

    def toggle_launcher(self, *a):
        return self.toggle_popup("launcher")

    def tick(self):
        return True

    # ---- events to pages ---------------------------------------------------
    def js(self, view, script):
        try:
            view.evaluate_javascript(script, -1, None, None, None, None, None)
        except Exception:
            view.run_javascript(script, None, None, None)

    def emit_to(self, view, event, data):
        self.js(view, f"window.os && window.os._emit({json.dumps(event)}, {json.dumps(data)})")

    def broadcast(self, event, data):
        for v in self.ui_views:
            self.emit_to(v, event, data)
        for w in self.windows.values():
            if w.local:
                self.emit_to(w.view, event, data)

    def windows_changed(self):
        self.broadcast("windows", self.window_list())

    def window_list(self):
        return [{"id": w.wid, "title": w.title_text, "appId": w.app_id, "icon": w.icon,
                 "iconUrl": file_uri(w.icon_file) if w.icon_file else None,
                 "color": w.color, "active": w.is_active(), "minimized": w.minimized}
                for w in self.windows.values()]

    # ---- native (non-web) programs such as Firefox -------------------------
    def init_native_windows(self):
        if Wnck is None:
            return
        Wnck.set_client_type(Wnck.ClientType.PAGER)
        self.wnck = Wnck.Screen.get_default()
        self.wnck.force_update()
        self.wnck.connect("window-opened", lambda s, ww: self.native_opened(ww))
        self.wnck.connect("window-closed", lambda s, ww: self.native_closed(ww))
        self.wnck.connect("active-window-changed", lambda *a: self.windows_changed())
        for ww in self.wnck.get_windows():
            self.native_opened(ww)

    def x_time(self):
        try:
            return GdkX11.x11_get_server_time(self.panel.get_window())
        except Exception:
            return Gtk.get_current_event_time()

    def native_opened(self, ww):
        if ww.get_pid() == os.getpid() or ww.get_window_type() != Wnck.WindowType.NORMAL \
                or ww.is_skip_tasklist():
            return
        names = {(ww.get_class_group_name() or "").lower(), (ww.get_class_instance_name() or "").lower()}
        app = next((m for m in self.registry.apps.values()
                    if names & {c.lower() for c in m.get("wmclass", [])}), None)
        nw = NativeWindow(self, ww, app)
        self.native[ww.get_xid()] = nw
        self.register(nw)
        ww.connect("name-changed", lambda *a: nw.refresh())
        ww.connect("state-changed", lambda *a: nw.refresh())

    def native_closed(self, ww):
        nw = self.native.pop(ww.get_xid(), None)
        if nw:
            self.unregister(nw)

    # ---- website icons + names ----------------------------------------------
    def refresh_meta(self):
        todo = self.registry.needs_meta()
        if not todo or self.meta_busy:
            return True
        self.meta_busy = True

        def work():
            names = load_json(os.path.join(ICONS, "names.json"), {})
            changed = False
            for m in todo:
                try:
                    name, icon = fetch_site_meta(m["url"], m["id"])
                except Exception as e:
                    print("meta", m["id"], e)
                    continue
                if name and m.get("autoName"):
                    names[m["id"]] = name
                    changed = True
                if icon:
                    changed = True
            if changed:
                save_json(os.path.join(ICONS, "names.json"), names)
                GLib.idle_add(self.apps_changed)
            self.meta_busy = False
        threading.Thread(target=work, daemon=True).start()
        return True

    def apps_changed(self):
        self.registry.reload()
        self.broadcast("apps", self.registry.public())
        for w in self.windows.values():
            w.refresh_icon() if hasattr(w, "refresh_icon") else None
        self.windows_changed()
        return False

    def install_app(self, m):
        url = (m.get("url") or "").strip()
        if not re.match(r"^https?://", url):
            url = "https://" + url
        host = urllib.parse.urlparse(url).hostname or ""
        if not host or "." not in host:
            raise ValueError("That doesn't look like a web address")
        slug = re.sub(r"[^a-z0-9]+", "-", (host[4:] if host.startswith("www.") else host) +
                      urllib.parse.urlparse(url).path.lower()).strip("-")
        app_id = "web-" + slug[:48]
        try:
            name, icon = fetch_site_meta(url, app_id)
        except Exception as e:
            print("install meta:", e)
            name, icon = None, None
        typed = (m.get("name") or "").strip()
        manifest = {"id": app_id, "name": typed or name or m.get("fallbackName") or host,
                    "url": url, "icon": m.get("icon") or "🌐", "iconFile": icon,
                    "color": m.get("color") or "#3b4a6b", "description": m.get("description") or host,
                    "category": "web", "width": 1100, "height": 720, "autoName": not typed}
        save_json(os.path.join(USER_APPS, app_id + ".json"), manifest)
        GLib.idle_add(self.apps_changed)
        return {"id": app_id, "name": manifest["name"], "iconFound": bool(icon)}

    # ---- power -------------------------------------------------------------
    def power(self, action):
        self.close_popups()
        win = Gtk.Window()
        win.set_decorated(False)
        win.set_keep_above(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_valign(Gtk.Align.CENTER)
        spinner = Gtk.Spinner()
        spinner.set_size_request(40, 40)
        spinner.start()
        label = Gtk.Label()
        label.set_markup(f"<span size='x-large' foreground='#e3e3e3'>"
                         f"{'Restarting' if action == 'reboot' else 'Shutting down'}…</span>")
        box.pack_start(spinner, False, False, 0)
        box.pack_start(label, False, False, 0)
        win.add(box)
        css = Gtk.CssProvider()
        css.load_from_data(b"window.power { background: #1b1c1e; } window.power spinner { color: #e3e3e3; }")
        win.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
        win.get_style_context().add_class("power")
        spinner.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
        win.show_all()
        win.fullscreen()
        GLib.timeout_add(900, lambda: (subprocess.Popen(["systemctl", action]), False)[1])

    # ---- bridge ------------------------------------------------------------
    def on_message(self, ucm, result, view):
        try:
            v = result.get_js_value()
            msg = json.loads(v.to_string())
        except Exception as e:
            print("bad message", e)
            return
        cid = msg.get("id")
        method, args = msg.get("method"), msg.get("args") or []

        def reply(ok, val):
            self.js(view, f"window.os._resolve({cid}, {'true' if ok else 'false'}, {json.dumps(val)})")
            return False

        if method in SLOW_METHODS:
            def work():
                try:
                    val = self.slow(method, args)
                    GLib.idle_add(reply, True, val)
                except Exception as e:
                    GLib.idle_add(reply, False, str(e))
            threading.Thread(target=work, daemon=True).start()
            return
        try:
            reply(True, self.dispatch(view, method, args))
        except Exception as e:
            print(f"bridge error in {method}: {e!r}", file=sys.stderr)
            reply(False, str(e))

    def slow(self, method, args):
        a = list(args) + [None] * 4
        if method == "net.status":
            return Network.status()
        if method == "net.wifiList":
            return Network.wifi_list()
        if method == "net.connect":
            Network.connect(a[0], a[1])
            return Network.status()
        if method == "net.disconnect":
            return Network.disconnect(a[0])
        if method == "apps.install":
            return self.install_app(a[0] or {})
        if method == "system.setHostname":
            name = (a[0] or "").strip().lower()
            if not re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", name):
                raise ValueError("Use letters, numbers and dashes only")
            code, _, err = run_cmd(["hostnamectl", "set-hostname", name], 15, root=True)
            if code != 0:
                print("hostnamectl failed:", err)
            GLib.idle_add(self.set_setting, "hostname", name)
            return name
        raise ValueError(method)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.save_settings()
        return False

    def dispatch(self, view, method, args):
        a = list(args) + [None] * 4
        if method == "storage.get":
            return self.storage.get(a[0])
        if method == "storage.set":
            self.storage[a[0]] = a[1]
            save_json(os.path.join(DATA, "storage.json"), self.storage)
            return True

        if method == "fs.list":
            p = safe_doc_path(a[0])
            out = []
            for n in sorted(os.listdir(p), key=str.lower):
                if n.startswith("."):
                    continue
                fp = os.path.join(p, n)
                st = os.stat(fp)
                out.append({"name": n, "dir": os.path.isdir(fp), "size": st.st_size, "mtime": st.st_mtime})
            out.sort(key=lambda e: (not e["dir"], e["name"].lower()))
            return out
        if method == "fs.read":
            with open(safe_doc_path(a[0]), encoding="utf-8", errors="replace") as f:
                return f.read()
        if method == "fs.readDataURL":
            p = safe_doc_path(a[0])
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
                    "svg": "image/svg+xml", "webp": "image/webp"}.get(ext, "application/octet-stream")
            with open(p, "rb") as f:
                return f"data:{mime};base64," + base64.b64encode(f.read()).decode()
        if method == "fs.write":
            p = safe_doc_path(a[0])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(a[1] or "")
            return True
        if method == "fs.writeDataURL":
            p = safe_doc_path(a[0])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            data = a[1].split(",", 1)[1]
            with open(p, "wb") as f:
                f.write(base64.b64decode(data))
            return True
        if method == "fs.mkdir":
            os.makedirs(safe_doc_path(a[0]), exist_ok=True)
            return True
        if method == "fs.remove":
            p = safe_doc_path(a[0])
            if p == os.path.realpath(DOCS):
                raise ValueError("refusing to remove Documents")
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            return True
        if method == "fs.rename":
            os.rename(safe_doc_path(a[0]), safe_doc_path(a[1]))
            return True

        if method == "apps.list":
            return self.registry.public()
        if method == "apps.launch":
            self.close_popups()
            self.launch(a[0], a[1])
            return True
        if method == "apps.uninstall":
            for p in (os.path.join(USER_APPS, a[0] + ".json"), os.path.join(ICONS, a[0] + ".png")):
                if os.path.exists(p):
                    os.remove(p)
            self.registry.reload()
            self.broadcast("apps", self.registry.public())
            return True

        if method == "settings.get":
            return self.public_settings()
        if method == "settings.set":
            self.settings[a[0]] = a[1]
            self.save_settings()
            if a[0] == "resolution":
                self.set_resolution(a[1])
            return True
        if method == "shelf.togglePin":
            pins = list(self.settings.get("pinned", []))
            pins.remove(a[0]) if a[0] in pins else pins.append(a[0])
            self.settings["pinned"] = pins
            self.save_settings()
            return True
        if method == "setup.finish":
            GLib.idle_add(lambda: (self.finish_setup(), False)[1])
            return True
        if method == "system.quick":
            return self.toggle_popup("quick")
        if method == "browser.open":
            self.close_popups()
            self.open_browser(a[0])
            return True

        if method == "windows.list":
            return self.window_list()
        if method == "windows.focus":
            w = self.windows.get(a[0])
            if w:
                if w.is_active() and not w.minimized:
                    w.iconify()
                else:
                    w.deiconify()
                    w.present()
            return True
        if method == "windows.minimize":
            w = self.windows.get(a[0])
            w and w.iconify()
            return True
        if method == "windows.close":
            w = self.windows.get(a[0])
            w and w.destroy()
            return True

        if method == "system.launcher":
            self.toggle_launcher()
            return True
        if method == "system.info":
            return self.system_info()
        if method == "system.exec":
            try:
                r = subprocess.run(a[0], shell=True, capture_output=True, text=True,
                                   timeout=20, cwd=safe_doc_path(a[1] or ""))
                return {"code": r.returncode, "out": r.stdout + r.stderr}
            except subprocess.TimeoutExpired:
                return {"code": 124, "out": "(command timed out after 20s)\n"}
        if method == "system.resolutions":
            return self.resolutions()
        if method == "system.shutdown":
            GLib.idle_add(lambda: (self.power("poweroff"), False)[1])
            return True
        if method == "system.reboot":
            GLib.idle_add(lambda: (self.power("reboot"), False)[1])
            return True
        if method == "app.close":
            for w in list(self.windows.values()):
                if getattr(w, "view", None) is view:
                    w.destroy()
                    break
            return True
        if method == "app.setTitle":
            for w in self.windows.values():
                if getattr(w, "view", None) is view:
                    w.set_app_title(a[0])
            return True
        raise ValueError("unknown method " + str(method))

    def save_settings(self):
        save_json(os.path.join(DATA, "settings.json"), self.settings)
        self.apply_gtk_theme()
        self.broadcast("settings", self.public_settings())

    def system_info(self):
        mem = {}
        try:
            for line in open("/proc/meminfo"):
                k, v = line.split(":", 1)
                mem[k] = int(v.split()[0])
        except Exception:
            pass
        cpu = ""
        try:
            for line in open("/proc/cpuinfo"):
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass
        ip = ""
        try:
            ip = subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.strip()
        except Exception:
            pass
        g = self.screen_rect()
        try:
            up = float(open("/proc/uptime").read().split()[0])
        except Exception:
            up = time.time() - BOOT_TIME
        return {"os": "BookerOS Web 1.0", "kernel": platform.release(), "cpu": cpu,
                "cores": os.cpu_count(), "memTotalMB": mem.get("MemTotal", 0) // 1024,
                "memAvailMB": mem.get("MemAvailable", 0) // 1024, "uptime": int(up),
                "ip": ip, "screen": f"{g.width}x{g.height}",
                "webkit": f"{WebKit2.get_major_version()}.{WebKit2.get_minor_version()}.{WebKit2.get_micro_version()}",
                "apps": len(self.registry.apps)}

    def resolutions(self):
        try:
            out = subprocess.run(["xrandr"], capture_output=True, text=True).stdout
        except Exception:
            return []
        modes = []
        for line in out.splitlines():
            m = re.match(r"^\s+(\d+x\d+)\s", line)
            if m and m.group(1) not in modes:
                modes.append(m.group(1))
        return modes

    def set_resolution(self, res):
        if not res:
            return
        out = subprocess.run(["xrandr"], capture_output=True, text=True).stdout
        m = re.search(r"^(\S+) connected", out, re.M)
        if m:
            subprocess.run(["xrandr", "--output", m.group(1), "--mode", res])
        else:
            subprocess.run(["xrandr", "-s", res])

    # ---- app windows -------------------------------------------------------
    def launch(self, app_id, arg=None):
        app = self.registry.apps.get(app_id)
        if not app:
            print("no such app", app_id)
            return
        if app.get("native"):
            subprocess.Popen(app["exec"] + ([str(arg)] if arg else []), start_new_session=True)
            return
        if app.get("single"):
            for w in self.windows.values():
                if w.app_id == app_id and getattr(w, "view", None):
                    w.deiconify()
                    w.present()
                    if arg is not None:
                        self.emit_to(w.view, "open", arg)
                    return
        AppWindow(self, app, self.registry.entry_url(app, arg), self.registry.is_local(app))

    def open_browser(self, url):
        app = self.registry.apps.get("browser")
        if not app:
            return
        if app.get("native"):
            subprocess.Popen(app["exec"] + [url], start_new_session=True)
        else:
            AppWindow(self, app, url, False, browser=True)

    def register(self, win):
        win.wid = self.next_win
        self.next_win += 1
        self.windows[win.wid] = win
        self.windows_changed()

    def unregister(self, win):
        self.windows.pop(win.wid, None)
        self.windows_changed()

    def on_download(self, ctx, download):
        def decide(dl, suggested):
            dest_dir = os.path.join(DOCS, "Downloads")
            os.makedirs(dest_dir, exist_ok=True)
            name = os.path.basename(suggested) or "download"
            dl.set_destination(file_uri(os.path.join(dest_dir, name)))
            return True
        download.connect("decide-destination", decide)
        download.connect("finished", lambda d: self.broadcast("download", d.get_destination()))


class AppWindow(Gtk.Window):
    def __init__(self, shell, app, url, local, browser=False, related=None):
        super().__init__()
        self.shell = shell
        self.app = app
        self.app_id = app["id"]
        self.local = local
        self.icon = app.get("icon", "🌐")
        self.icon_file = app.get("iconFile")
        self.color = app.get("color", "#3b4a6b")
        self.browser = browser or app.get("browser", False)
        self.minimized = False
        self.win_fs = False
        self.title_text = app["name"]

        g = shell.screen_rect()
        w = min(app.get("width", 900), g.width - 40)
        h = min(app.get("height", 640), g.height - PANEL_H - 40)
        self.set_default_size(w, h)
        n = len(shell.windows)
        self.move(g.x + max(10, (g.width - w) // 2 + (n % 6) * 28 - 70),
                  g.y + max(10, (g.height - PANEL_H - h) // 2 + (n % 6) * 28 - 70))

        if related is not None:
            self.view = WebKit2.WebView.new_with_related_view(related)
        else:
            self.view = shell.make_view(local)
        s = self.view.get_settings()
        s.set_enable_developer_extras(True)
        s.set_user_agent_with_application_details("BookerOS", "1.0")
        s.set_enable_smooth_scrolling(True)

        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        self.set_title(app["name"])
        self.icon_box = Gtk.Box()
        self.icon_box.get_style_context().add_class("appicon")
        hb.pack_start(self.icon_box)
        self.refresh_icon()
        self.title_label = Gtk.Label(label=app["name"])
        self.title_label.get_style_context().add_class("title")
        self.title_label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        self.title_label.set_max_width_chars(60)
        hb.set_custom_title(Gtk.Box())
        self.set_titlebar(hb)
        self.hb = hb

        if not local:
            back = Gtk.Button.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON)
            fwd = Gtk.Button.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON)
            reload = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
            back.connect("clicked", lambda *a: self.view.go_back())
            fwd.connect("clicked", lambda *a: self.view.go_forward())
            reload.connect("clicked", lambda *a: self.view.reload())
            box = Gtk.Box(spacing=0)
            box.get_style_context().add_class("linked")
            for b in (back, fwd):
                box.pack_start(b, False, False, 0)
            hb.pack_start(box)
            hb.pack_start(reload)
            if self.browser:
                self.entry = Gtk.Entry()
                self.entry.set_placeholder_text("Search or enter address")
                self.entry.connect("activate", self.on_entry)
                hb.set_custom_title(self.entry)

        if not self.browser:
            hb.pack_start(self.title_label)

        self.progress = Gtk.ProgressBar()
        self.progress.get_style_context().add_class("osd")
        overlay = Gtk.Overlay()
        overlay.add(self.view)
        self.progress.set_valign(Gtk.Align.START)
        overlay.add_overlay(self.progress)
        # "Press Esc to exit full screen" hint
        self.fs_hint = Gtk.Label(label="Press  Esc  to exit full screen")
        self.fs_hint.get_style_context().add_class("app-notification")
        self.fs_hint.set_halign(Gtk.Align.CENTER)
        self.fs_hint.set_valign(Gtk.Align.START)
        self.fs_hint.set_margin_top(24)
        self.fs_hint.set_no_show_all(True)
        overlay.add_overlay(self.fs_hint)
        self.add(overlay)
        self.view.connect("enter-fullscreen", self.on_enter_fullscreen)

        self.view.connect("notify::title", self.on_title)
        self.view.connect("notify::uri", self.on_uri)
        self.view.connect("notify::estimated-load-progress", self.on_progress)
        self.view.connect("create", self.on_create)
        self.view.connect("close", lambda *a: self.destroy())
        self.view.connect("permission-request", self.on_permission)
        self.view.connect("load-failed", self.on_failed)
        self.connect("destroy", lambda *a: shell.unregister(self))
        self.connect("notify::is-active", lambda *a: shell.windows_changed())
        self.connect("window-state-event", self.on_state)
        self.connect("key-press-event", self.on_key)

        shell.register(self)
        if related is None:
            self.view.load_uri(url)
            self.show_all()
            self.progress.hide()
        else:
            self.view.connect("ready-to-show", lambda *a: (self.show_all(), self.progress.hide()))

    def refresh_icon(self):
        app = self.shell.registry.apps.get(self.app_id, self.app)
        self.icon_file = app.get("iconFile")
        self.icon = app.get("icon", self.icon)
        for c in self.icon_box.get_children():
            self.icon_box.remove(c)
        widget = None
        if self.icon_file:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.icon_file, 18, 18, True)
                widget = Gtk.Image.new_from_pixbuf(pb)
            except GLib.Error:
                widget = None
        if widget is None:
            widget = Gtk.Label(label=self.icon)
        self.icon_box.pack_start(widget, False, False, 0)
        self.icon_box.show_all()

    def on_enter_fullscreen(self, view):
        self.fs_hint.show()
        GLib.timeout_add(3500, lambda: (self.fs_hint.hide(), False)[1])
        return False

    def exit_fullscreen(self):
        self.shell.js(self.view, "document.fullscreenElement && document.exitFullscreen()")
        self.unfullscreen()
        self.fs_hint.hide()

    def set_app_title(self, t):
        self.title_text = t or self.app["name"]
        self.title_label.set_text(self.title_text)
        self.set_title(self.title_text)
        self.shell.windows_changed()

    def on_title(self, *a):
        t = self.view.get_title()
        if not self.local and t:
            name = self.app["name"]
            self.set_app_title(t if self.browser or name.lower() in t.lower() else f"{name} — {t}")

    def on_uri(self, *a):
        if self.browser and hasattr(self, "entry") and not self.entry.has_focus():
            self.entry.set_text(self.view.get_uri() or "")

    def on_progress(self, *a):
        p = self.view.get_estimated_load_progress()
        if p < 1.0:
            self.progress.show()
            self.progress.set_fraction(p)
        else:
            self.progress.hide()

    def on_entry(self, entry):
        t = entry.get_text().strip()
        if not t:
            return
        if re.match(r"^[a-z]+://", t):
            url = t
        elif " " not in t and "." in t:
            url = "https://" + t
        else:
            url = "https://duckduckgo.com/?q=" + urllib.parse.quote(t)
        self.view.load_uri(url)
        self.view.grab_focus()

    def on_create(self, view, action):
        browser_app = self.shell.registry.apps.get("browser", self.app)
        w = AppWindow(self.shell, browser_app, None, False, browser=True, related=view)
        return w.view

    def on_permission(self, view, req):
        req.deny()
        return True

    def on_failed(self, view, event, uri, err):
        if err.matches(WebKit2.NetworkError.quark(), WebKit2.NetworkError.CANCELLED):
            return False
        html = f"""<html><body style="font-family:Inter,sans-serif;background:#14171f;color:#dfe3ee;
        display:grid;place-items:center;height:100vh;margin:0"><div style="text-align:center;max-width:420px">
        <div style="font-size:48px">📡</div><h2>Can't reach this page</h2>
        <p style="color:#8a92a6">{GLib.markup_escape_text(uri)}<br><br>{GLib.markup_escape_text(err.message)}</p>
        <p style="color:#8a92a6">Check that the virtual machine has a network adapter (NAT) enabled.</p>
        </div></body></html>"""
        view.load_alternate_html(html, uri, None)
        return True

    def on_state(self, w, ev):
        self.minimized = bool(ev.new_window_state & Gdk.WindowState.ICONIFIED)
        self.win_fs = bool(ev.new_window_state & Gdk.WindowState.FULLSCREEN)
        self.shell.windows_changed()
        return False

    def on_key(self, w, ev):
        ctrl = ev.state & Gdk.ModifierType.CONTROL_MASK
        key = Gdk.keyval_name(ev.keyval) or ""
        if ctrl and key.lower() == "w":
            self.destroy()
            return True
        if ctrl and key.lower() == "r" or key == "F5":
            self.view.reload()
            return True
        if ctrl and key.lower() == "l" and self.browser:
            self.entry.grab_focus()
            return True
        if ev.state & Gdk.ModifierType.MOD1_MASK and key == "Left":
            self.view.go_back()
            return True
        if key == "F12":
            self.view.get_inspector().show()
            return True
        if key == "Escape" and self.win_fs:
            self.exit_fullscreen()
            return True
        if key == "F11":
            if self.win_fs:
                self.exit_fullscreen()
            else:
                self.fullscreen()
                self.on_enter_fullscreen(self.view)
            return True
        return False


class NativeWindow:
    """A window of a normal (non-web) program, e.g. Firefox, tracked so it shows on the shelf."""
    local = False
    view = None

    def __init__(self, shell, ww, app):
        self.shell, self.ww = shell, ww
        self.app_id = app["id"] if app else "native:" + (ww.get_class_group_name() or "app")
        self.icon = app.get("icon", "🪟") if app else "🪟"
        self.icon_file = app.get("iconFile") if app else None
        self.color = app.get("color", "#5a6378") if app else "#5a6378"
        self.title_text = ww.get_name() or (app or {}).get("name", "Window")
        self.minimized = ww.is_minimized()

    def refresh(self):
        self.title_text = self.ww.get_name() or self.title_text
        self.minimized = self.ww.is_minimized()
        self.shell.windows_changed()

    def is_active(self):
        return self.ww.is_active()

    def present(self):
        self.ww.activate(self.shell.x_time())

    def deiconify(self):
        if self.ww.is_minimized():
            self.ww.unminimize(self.shell.x_time())

    def iconify(self):
        self.ww.minimize()

    def destroy(self):
        self.ww.close(self.shell.x_time())


def main():
    os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
    Shell()
    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
