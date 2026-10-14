# BookerOS Web

A graphical operating system where **every app is a web app**. It boots straight
into a ChromeOS-style desktop: a shelf at the bottom, a round launcher button,
Quick Settings behind the clock, and apps that each open in their own window.

Under the hood it is a small Ubuntu 24.04 live system running X11, Openbox and a
desktop shell written in Python + WebKitGTK. The desktop, shelf, launcher, setup
wizard and every built-in app are HTML/CSS/JS.

## Run it in VirtualBox

1. **New** VM — Name `BookerOS Web`, Type **Linux**, Version **Ubuntu (64-bit)**.
   Skip unattended installation.
2. Memory **3 GB** or more, **2+ CPUs**. No hard disk is needed (it's a live system).
3. Settings → Display → Graphics Controller **VMSVGA**, Video Memory **128 MB**.
   Leave 3D acceleration off.
4. Settings → Network → Adapter 1 **NAT** (the default) so web apps work.
5. Settings → Storage → optical drive → choose **bookeros-web.iso**. Start.

First boot opens the **setup wizard**: theme, accent colour, wallpaper, your name,
the computer's hostname, and a network to connect to.

> Wi-Fi: VirtualBox gives VMs an Ethernet connection, never a Wi-Fi card, so in a
> VM the network step shows "Connected via Ethernet". The Wi-Fi list and password
> flow use NetworkManager and work on real hardware with a supported Wi-Fi card.

Everything resets on reboot because it's a live ISO (see "Next steps").

## Using it

| | |
|---|---|
| Launcher | circle at bottom-left, or tap the **Windows/Super key**. Type to search apps or the web |
| Shelf | pinned apps in the middle; right-click to unpin, pin from the launcher's 📌 |
| Quick Settings | click the clock: dark theme, accent, network, display, power |
| Windows | **Alt+Tab** switch · **Ctrl+W** close · **Win+↑/↓** maximise/restore · **Win+←/→** snap · **F11** full screen, **Esc** to leave · **F12** dev tools |
| Wallpaper | right-click the desktop |

## Built-in apps

Files · Notes · Calculator · Paint · Terminal · Browser · Settings · App Store ·
Clock (stopwatch/timer) · Snake · Mines · Welcome, plus web apps Wikipedia, Maps
(OpenStreetMap) and Whiteboard (Excalidraw). **Firefox** is the full web browser
(installed from Mozilla's official repository at build time; if that's unreachable
the build falls back to the built-in browser). The **App Store** installs any URL as
an app, picking up the site's own icon and its browser-tab name.

## Making an app

An app is a folder in `shell/apps/<id>/` with a `manifest.json`:

```json
{ "id": "todo", "name": "To-do", "icon": "✅", "color": "#188038",
  "url": "index.html", "category": "tools", "width": 600, "height": 500 }
```

`url` is either a local HTML file (gets the `window.os` API) or an `https://` URL
(an ordinary website, no API). Local apps can use:

```js
await os.fs.list("")            // ~/Documents
await os.fs.write("todo.txt", text);  await os.fs.read("todo.txt")
await os.storage.set("k", v);   await os.storage.get("k")
await os.apps.launch("notes", "todo.txt")
await os.settings.get()          // theme, accent, wallpaper, username, hostname
await os.net.status();  await os.net.wifiList();  await os.net.connect(ssid, pw)
await os.system.exec("uname -a") // run a shell command
os.on("settings", s => ...)      // react to theme changes
```

Link `../../ui/app.css` for the shared look (light/dark aware via CSS variables).

## Building the ISO

**Easiest:** let GitHub build it. See `GITHUB-SETUP.md`: upload this folder to a GitHub
repository and every change produces a downloadable ISO on the Releases page.

**Locally,** on Ubuntu 24.04 (or WSL):


```sh
apt install debootstrap squashfs-tools grub-pc-bin grub-efi-amd64-bin xorriso mtools curl
./build.sh /path/to/workdir
```

Layout: `shell/shell.py` (window manager glue + `window.os` bridge), `shell/ui/`
(desktop, shelf, launcher, Quick Settings, setup wizard), `shell/apps/`,
`system/` (session script, Openbox config), `build.sh`.

## Next steps

- Persistence: add a second virtual disk labelled `casper-rw` so settings and files survive reboots.
- An installer to copy the live system onto a virtual hard disk.
