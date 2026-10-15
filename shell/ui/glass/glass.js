/* BookerOS Glass helpers shared by the menu bar, dock and popups. */
(function () {
  const esc = (t) => String(t == null ? "" : t).replace(/[&"<>]/g, (c) => ({ "&": "&amp;", '"': "&quot;", "<": "&lt;", ">": "&gt;" }[c]));

  window.Glass = {
    esc,
    /* Put a blurred "backdrop" behind a .glass element.
       css: a CSS background value; area: where that background sits relative to this window
       ({x, y, w, h}; defaults to the whole window). */
    backdrop(el, css, area) {
      let bg = el.querySelector(":scope > .glass-bg");
      if (!bg) {
        bg = document.createElement("div");
        bg.className = "glass-bg";
        el.prepend(bg);
      }
      if (!css) { bg.style.background = "none"; return; }
      const r = el.getBoundingClientRect();
      const a = area || { x: 0, y: 0, w: innerWidth, h: innerHeight };
      bg.style.left = (a.x - r.left) + "px";
      bg.style.top = (a.y - r.top) + "px";
      bg.style.width = a.w + "px";
      bg.style.height = a.h + "px";
      bg.style.background = css;
    },
    /* A screenshot taken by the shell just before the popup opened */
    snapshotCss: (dataUrl) => (dataUrl ? `url("${dataUrl}") center / 100% 100% no-repeat` : null),

    /* Markup for an app icon */
    icon(a, size) {
      const s = size || 48;
      if (a.iconUrl)
        return `<div class="app-icon has-img" style="width:${s}px;height:${s}px"><img src="${esc(a.iconUrl)}" draggable="false"></div>`;
      const c = a.color || "#5a6378";
      return `<div class="app-icon" style="width:${s}px;height:${s}px;background:linear-gradient(160deg, ${esc(c)}, ${esc(shade(c, -28))})">` +
             `<span class="glyph" style="font-size:${Math.round(s * .55)}px">${esc(a.icon)}</span></div>`;
    },

    /* Apply theme + accent from settings */
    applySettings(s) {
      document.documentElement.dataset.theme = s.theme === "dark" ? "dark" : "light";
      const acc = (s.accents || {})[s.accent];
      if (acc) {
        const p = s.theme === "dark" ? acc.dark : acc.light;
        document.documentElement.style.setProperty("--accent", p[0]);
        document.documentElement.style.setProperty("--on-accent", p[1]);
        document.documentElement.style.setProperty("--accent-soft", p[2]);
      }
    },

    svg: (path, cls) => `<svg class="i ${cls || ""}" viewBox="0 0 24 24" aria-hidden="true"><path fill-rule="evenodd" d="${path}"/></svg>`,
    ICONS: {
      wifi: "M12 21 0 8.6C3.3 5.7 7.5 4 12 4s8.7 1.7 12 4.6L12 21z",
      search: "M15.5 14h-.8l-.3-.3A6.5 6.5 0 1 0 14 15.5l.3.3v.8l5 5 1.5-1.5-5-5zm-6 0a4.5 4.5 0 1 1 0-9 4.5 4.5 0 0 1 0 9z",
      control: "M7 2.5h10a4.25 4.25 0 0 1 0 8.5H7a4.25 4.25 0 0 1 0-8.5zM7 4.6a2.15 2.15 0 1 0 0 4.3 2.15 2.15 0 0 0 0-4.3zM7 13h10a4.25 4.25 0 0 1 0 8.5H7A4.25 4.25 0 0 1 7 13zm10 2.1a2.15 2.15 0 1 0 0 4.3 2.15 2.15 0 0 0 0-4.3z",
      moon: "M12.3 22a10 10 0 0 1-2.9-19.6 8 8 0 0 0 10.2 11.9A10 10 0 0 1 12.3 22z",
      sun: "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM11 1h2v3h-2zm0 19h2v3h-2zM3.5 4.9l1.4-1.4L7 5.6 5.6 7zM17 18.4l1.4-1.4 2.1 2.1-1.4 1.4zM1 11h3v2H1zm19 0h3v2h-3zM3.5 19.1 5.6 17 7 18.4l-2.1 2.1zM17 5.6l2.1-2.1 1.4 1.4L18.4 7z",
      display: "M21 3H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h5v2h8v-2h5c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 14H3V5h18v12z",
      palette: "M12 3a9 9 0 0 0 0 18c.8 0 1.5-.7 1.5-1.5 0-.4-.1-.7-.4-1-.2-.3-.4-.6-.4-1 0-.8.7-1.5 1.5-1.5H16a5 5 0 0 0 5-5c0-4.4-4-8-9-8zm-5.5 9a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm3-4a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm5 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm3 4a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z",
      image: "M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3 3.5-4.5 4.5 6H5l3.5-4.5z",
      power: "M13 3h-2v10h2V3zm4.8 2.2-1.4 1.4A7 7 0 1 1 7.6 6.6L6.2 5.2A9 9 0 1 0 17.8 5.2z",
      restart: "M12 5V1L7 6l5 5V7a6 6 0 1 1-6 6H4a8 8 0 1 0 8-8z",
      gear: "M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.4 7.4 0 0 0-1.7-1L15 3h-4l-.4 2.7a7.4 7.4 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1c.5.4 1.1.7 1.7 1L11 21h4l.4-2.7c.6-.3 1.2-.6 1.7-1l2.5 1 2-3.5zM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z",
      grid: "M4 4h4v4H4zm6 0h4v4h-4zm6 0h4v4h-4zM4 10h4v4H4zm6 0h4v4h-4zm6 0h4v4h-4zM4 16h4v4H4zm6 0h4v4h-4zm6 0h4v4h-4z",
      calc: "M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm0 2v4h10V4zm1 7v2h2v-2zm4 0v2h2v-2zm4 0v6h2v-6zm-8 4v2h2v-2zm4 0v2h2v-2z",
      globe: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm6.9 6h-2.9a15.7 15.7 0 0 0-1.4-3.6A8 8 0 0 1 18.9 8zM12 4c.8 1.2 1.5 2.5 1.9 4h-3.8c.4-1.4 1.1-2.8 1.9-4zM4.3 14a8.2 8.2 0 0 1 0-4h3.4a16.5 16.5 0 0 0 0 4zm.8 2h2.9c.3 1.3.8 2.5 1.4 3.6A8 8 0 0 1 5.1 16zM8 8H5.1a8 8 0 0 1 4.3-3.6C8.8 5.5 8.3 6.7 8 8zm4 12c-.8-1.2-1.5-2.5-1.9-4h3.8c-.4 1.4-1.1 2.8-1.9 4zm2.3-6H9.7a14.7 14.7 0 0 1 0-4h4.6a14.7 14.7 0 0 1 0 4zm.3 5.6c.6-1.1 1.1-2.3 1.4-3.6h2.9a8 8 0 0 1-4.3 3.6zm1.8-5.6a16.5 16.5 0 0 0 0-4h3.4a8.2 8.2 0 0 1 0 4z",
      file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zm-1 7V3.5L18.5 9z",
    },
    /* The BookerOS Glass logo: a mountain over a lake (used in the menu bar) */
    LOGO: `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M2 15.5 8.2 6l3.3 5 2.1-3L22 15.5z"/><path fill="currentColor" opacity=".7" d="M3 17.5h18v1.6H3zM6 20.5h12v1.4H6z"/></svg>`,
  };

  function shade(hex, pct) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) return hex;
    const n = parseInt(m[1], 16);
    const f = (v) => Math.max(0, Math.min(255, Math.round(v + (pct / 100) * (pct < 0 ? v : 255 - v))));
    const r = f(n >> 16), g = f((n >> 8) & 255), b = f(n & 255);
    return "#" + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
  }
  window.Glass.shade = shade;
})();
