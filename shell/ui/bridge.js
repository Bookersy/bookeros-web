/* BookerOS Web bridge — injected into local apps and shell pages only. */
(function () {
  if (window.os) return;
  const ED = window.__EDITION || "web";
  (function mark() {
    if (document.documentElement) document.documentElement.dataset.edition = ED;
    else requestAnimationFrame(mark);
  })();
  let seq = 0;
  const pending = {};
  const listeners = {};
  function call(method, ...args) {
    return new Promise((resolve, reject) => {
      const id = ++seq;
      pending[id] = { resolve, reject };
      window.webkit.messageHandlers.os.postMessage(JSON.stringify({ id, method, args }));
    });
  }
  const params = new URLSearchParams(location.search);
  window.os = {
    _resolve(id, ok, val) {
      const p = pending[id];
      if (!p) return;
      delete pending[id];
      ok ? p.resolve(val) : p.reject(new Error(val));
    },
    _emit(ev, data) {
      (listeners[ev] || []).forEach((f) => { try { f(data); } catch (e) { console.error(e); } });
    },
    on(ev, f) { (listeners[ev] = listeners[ev] || []).push(f); },
    call,
    edition: ED,
    /* Markup for an app's round icon: the site's own icon on white, or the emoji on its colour. */
    tile(a, cls, extra) {
      const q = (t) => String(t == null ? "" : t).replace(/[&"<>]/g, (c) => ({ "&": "&amp;", '"': "&quot;", "<": "&lt;", ">": "&gt;" }[c]));
      if (a.iconUrl)
        return `<div class="${cls} has-img" style="background:#fff;${extra || ""}"><img src="${q(a.iconUrl)}" draggable="false" style="width:64%;height:64%;object-fit:contain;display:block"></div>`;
      return `<div class="${cls}" style="background:${q(a.color)};${extra || ""}">${q(a.icon)}</div>`;
    },
    arg: params.has("arg") ? params.get("arg") : null,
    storage: { get: (k) => call("storage.get", k), set: (k, v) => call("storage.set", k, v) },
    fs: {
      list: (p) => call("fs.list", p || ""),
      read: (p) => call("fs.read", p),
      readDataURL: (p) => call("fs.readDataURL", p),
      write: (p, t) => call("fs.write", p, t),
      writeDataURL: (p, d) => call("fs.writeDataURL", p, d),
      mkdir: (p) => call("fs.mkdir", p),
      remove: (p) => call("fs.remove", p),
      rename: (a, b) => call("fs.rename", a, b),
    },
    apps: {
      list: () => call("apps.list"),
      launch: (id, arg) => call("apps.launch", id, arg === undefined ? null : arg),
      install: (m) => call("apps.install", m),
      uninstall: (id) => call("apps.uninstall", id),
    },
    settings: { get: () => call("settings.get"), set: (k, v) => call("settings.set", k, v) },
    windows: {
      list: () => call("windows.list"),
      focus: (id) => call("windows.focus", id),
      minimize: (id) => call("windows.minimize", id),
      close: (id) => call("windows.close", id),
    },
    system: {
      info: () => call("system.info"),
      exec: (cmd, cwd) => call("system.exec", cmd, cwd || ""),
      resolutions: () => call("system.resolutions"),
      launcher: () => call("system.launcher"),
      shutdown: () => call("system.shutdown"),
      reboot: () => call("system.reboot"),
      setHostname: (n) => call("system.setHostname", n),
    },
    net: {
      status: () => call("net.status"),
      wifiList: () => call("net.wifiList"),
      connect: (ssid, password) => call("net.connect", ssid, password || ""),
      disconnect: (dev) => call("net.disconnect", dev),
    },
    setup: { finish: () => call("setup.finish") },
    app: {
      close: () => call("app.close"),
      setTitle: (t) => call("app.setTitle", t),
    },
  };
  /* apply the accent colour to every local page */
  function applySettings(s) {
    if (!s) return;
    document.documentElement.dataset.theme = s.theme === "dark" ? "dark" : "light";
    const acc = (s.accents || {})[s.accent];
    const root = document.documentElement.style;
    if (acc) {
      const pal = s.theme === "dark" ? acc.dark : acc.light;
      root.setProperty("--accent", pal[0]);
      root.setProperty("--on-accent", pal[1]);
      root.setProperty("--accent-soft", pal[2]);
    }
  }
  window.os.on("settings", applySettings);
  document.addEventListener("DOMContentLoaded", () => window.os.settings.get().then(applySettings).catch(() => {}));
})();
