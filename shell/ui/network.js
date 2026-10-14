/* Network panel component, shared by the setup wizard and Settings.
   NetworkPanel(container, { onChange }) renders wired status + a Wi-Fi list with inline password entry. */
(function () {
  const css = `
  .np { display: flex; flex-direction: column; gap: 10px; }
  .np-row { display: flex; align-items: center; gap: 14px; padding: 12px 16px; background: var(--bg); border-radius: 16px; }
  .np-row .np-ic { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; background: var(--bg2); font-size: 17px; flex: none; }
  .np-row.on .np-ic { background: var(--accent); color: var(--on-accent); }
  .np-row .np-l { flex: 1; min-width: 0; }
  .np-row .np-l small { display: block; color: var(--muted); }
  .np-head { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
  .np-head b { font-weight: 500; flex: 1; }
  .np-wifi { display: flex; flex-direction: column; background: var(--bg); border-radius: 16px; overflow: hidden; }
  .np-net { display: flex; align-items: center; gap: 14px; padding: 11px 16px; cursor: pointer; border-bottom: 1px solid var(--line); }
  .np-net:last-child { border-bottom: 0; }
  .np-net:hover { background: var(--bg2); }
  .np-net .np-l { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .np-bars { display: inline-flex; align-items: flex-end; gap: 2px; height: 16px; }
  .np-bars i { width: 4px; background: var(--line); border-radius: 1px; }
  .np-bars i.f { background: var(--text); }
  .np-pw { display: flex; gap: 8px; padding: 0 16px 12px 66px; border-bottom: 1px solid var(--line); }
  .np-pw input { flex: 1; }
  .np-msg { padding: 18px 16px; color: var(--muted); text-align: center; }
  .np-err { color: var(--danger); font-size: 13px; padding: 0 16px 10px 66px; }
  .np-spin { width: 16px; height: 16px; border: 2px solid var(--line); border-top-color: var(--accent); border-radius: 50%; animation: np-s .8s linear infinite; }
  @keyframes np-s { to { transform: rotate(360deg); } }`;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const bars = (sig) => { const n = sig > 75 ? 4 : sig > 50 ? 3 : sig > 25 ? 2 : 1; return `<span class="np-bars">${[6, 9, 12, 16].map((h, i) => `<i style="height:${h}px" class="${i < n ? "f" : ""}"></i>`).join("")}</span>`; };

  window.NetworkPanel = function (root, opts = {}) {
    let status = null, nets = null, scanning = false, open = null, err = "", busy = null;
    root.innerHTML = `<div class="np"></div>`;
    const box = root.firstChild;
    function render() {
      let h = "";
      if (!status) { box.innerHTML = `<div class="np-row"><div class="np-spin"></div><div class="np-l">Checking network…</div></div>`; return; }
      const wired = status.devices.filter((d) => d.type === "ethernet");
      const wifiDev = status.devices.find((d) => d.type === "wifi");
      wired.forEach((d) => {
        const on = d.state.startsWith("connected");
        h += `<div class="np-row ${on ? "on" : ""}"><div class="np-ic">🔌</div><div class="np-l">Ethernet
          <small>${on ? "Connected" + (status.ip ? " · " + esc(status.ip) : "") : "Cable unplugged or not connected"}</small></div></div>`;
      });
      h += `<div class="np-head"><b>Wi-Fi</b>${wifiDev ? `<button class="ghost" data-a="scan">${scanning ? "Scanning…" : "Refresh"}</button>` : ""}</div>`;
      if (!wifiDev) {
        h += `<div class="np-wifi"><div class="np-msg">No Wi-Fi adapter found.${wired.some((d) => d.state.startsWith("connected"))
          ? "<br>You're online through Ethernet, so you don't need Wi-Fi." : ""}<br><small>Virtual machines connect through Ethernet; Wi-Fi appears here on computers with a wireless card.</small></div></div>`;
      } else if (!nets) {
        h += `<div class="np-wifi"><div class="np-msg"><div class="np-spin" style="margin:0 auto 8px"></div>Looking for networks…</div></div>`;
      } else if (!nets.length) {
        h += `<div class="np-wifi"><div class="np-msg">No networks found nearby.</div></div>`;
      } else {
        h += `<div class="np-wifi">`;
        nets.forEach((n, i) => {
          h += `<div class="np-net" data-i="${i}">${bars(n.signal)}<div class="np-l">${esc(n.ssid)}${n.active ? ` <small class="muted">· Connected</small>` : ""}</div>
            ${busy === n.ssid ? `<div class="np-spin"></div>` : n.secure ? "🔒" : ""}</div>`;
          if (open === n.ssid && !n.active) {
            h += `<form class="np-pw" data-i="${i}">${n.secure ? `<input type="password" placeholder="Password for ${esc(n.ssid)}" autofocus>` : `<span class="muted" style="flex:1">Open network</span>`}
              <button class="primary">Connect</button></form>`;
            if (err) h += `<div class="np-err">${esc(err)}</div>`;
          }
        });
        h += `</div>`;
      }
      box.innerHTML = h;
      box.querySelectorAll(".np-net").forEach((el) => el.onclick = () => {
        const n = nets[el.dataset.i];
        if (n.active) return;
        open = open === n.ssid ? null : n.ssid; err = ""; render();
        const pw = box.querySelector(".np-pw input"); if (pw) pw.focus();
      });
      box.querySelectorAll(".np-pw").forEach((f) => f.onsubmit = async (e) => {
        e.preventDefault();
        const n = nets[f.dataset.i], pw = f.querySelector("input");
        busy = n.ssid; err = ""; render();
        try { status = await os.net.connect(n.ssid, pw ? pw.value : ""); open = null; busy = null; await scan(); opts.onChange && opts.onChange(status); }
        catch (x) { busy = null; err = x.message.replace(/^Error:\s*/, ""); render(); }
      });
      const sb = box.querySelector('[data-a="scan"]'); if (sb) sb.onclick = scan;
    }
    async function scan() {
      if (scanning) return;
      scanning = true; render();
      try { nets = await os.net.wifiList(); } catch { nets = []; }
      scanning = false; render();
    }
    async function refresh() {
      status = await os.net.status();
      render();
      opts.onChange && opts.onChange(status);
      if (status.wifi) scan();
    }
    refresh();
    return { refresh, get status() { return status; } };
  };
})();
