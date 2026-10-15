#!/bin/bash
# Build a BookerOS live ISO.
#   EDITION=web   (default) ChromeOS-style shelf and launcher   -> bookeros-web.iso
#   EDITION=glass           glassy menu bar, dock and Spotlight -> bookeros-glass.iso
# Usage: sudo ./build.sh [workdir]
# Needs: debootstrap squashfs-tools grub-pc-bin grub-efi-amd64-bin xorriso mtools curl
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-$SRC/../webos-build}"
R="$WORK/rootfs"
ISO="$WORK/iso"
EDITION="${EDITION:-web}"
case "$EDITION" in
  glass) NAME="BookerOS Glass"; VOLID=BOOKEROS_GLASS ;;
  *)     EDITION=web; NAME="BookerOS Web"; VOLID=BOOKEROS_WEB ;;
esac
OUT="${OUT:-$WORK/bookeros-$EDITION.iso}"
PACKAGES="linux-image-virtual casper initramfs-tools systemd-sysv systemd-resolved libpam-systemd dbus udev kmod sudo
  iproute2 iputils-ping ca-certificates locales tzdata less nano procps
  xserver-xorg-core xserver-xorg-input-libinput xserver-xorg-video-fbdev xserver-xorg-video-vesa xserver-xorg-legacy xinit x11-xserver-utils x11-utils openbox picom xcompmgr xcape xdotool
  python3 python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 gir1.2-wnck-3.0 libwebkit2gtk-4.1-0 glib-networking
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-libav
  adwaita-icon-theme-full librsvg2-common libgl1-mesa-dri
  fonts-roboto fonts-inter fonts-dejavu-core fonts-noto-color-emoji fonts-jetbrains-mono
  network-manager wpasupplicant iw virtualbox-guest-utils virtualbox-guest-x11"

mounts() { umounts; mount --bind /dev "$R/dev"; mount -t devpts devpts "$R/dev/pts"; mount -t proc proc "$R/proc"; mount -t sysfs sys "$R/sys"; }
umounts() { for m in dev/pts dev proc sys; do umount -lf "$R/$m" 2>/dev/null || true; done; }
trap umounts EXIT

# 1. base system -------------------------------------------------------------
if [ ! -x "$R/usr/bin/apt-get" ]; then
  debootstrap --variant=minbase --components=main,universe,multiverse noble "$R" http://archive.ubuntu.com/ubuntu
fi
cat > "$R/etc/apt/sources.list" <<'EOF'
deb http://archive.ubuntu.com/ubuntu noble main universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-updates main universe multiverse
deb http://security.ubuntu.com/ubuntu noble-security main universe multiverse
EOF
printf '#!/bin/sh\nexit 101\n' > "$R/usr/sbin/policy-rc.d"; chmod +x "$R/usr/sbin/policy-rc.d"
rm -f "$R/etc/resolv.conf"; cp -L /etc/resolv.conf "$R/etc/resolv.conf"
mounts
chroot "$R" bash -c "export DEBIAN_FRONTEND=noninteractive; apt-get update -q && apt-get install -y -q --no-install-recommends $(echo $PACKAGES) && apt-get clean"

# Firefox, as a normal .deb from Mozilla's official repository (Ubuntu's own package is a snap)
install -d -m 0755 "$R/etc/apt/keyrings" "$R/etc/apt/preferences.d" "$R/etc/apt/sources.list.d"
if curl -fsSL -m 60 https://packages.mozilla.org/apt/repo-signing-key.gpg -o "$R/etc/apt/keyrings/packages.mozilla.org.asc"; then
  echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" \
    > "$R/etc/apt/sources.list.d/mozilla.list"
  printf 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' > "$R/etc/apt/preferences.d/mozilla"
  chroot "$R" bash -c "export DEBIAN_FRONTEND=noninteractive; apt-get update -q && apt-get install -y -q --no-install-recommends firefox && (apt-get install -y -q firefox-l10n-en-gb || true) && apt-get clean" \
    || echo "WARNING: Firefox install failed; the built-in browser will be used instead" >&2
else
  rm -f "$R/etc/apt/sources.list.d/mozilla.list" "$R/etc/apt/preferences.d/mozilla"
  echo "WARNING: could not reach packages.mozilla.org; building without Firefox (the built-in browser will be used)" >&2
fi
mkdir -p "$R/etc/firefox/policies"
cat > "$R/etc/firefox/policies/policies.json" <<'EOF'
{
  "policies": {
    "DisableAppUpdate": true,
    "DontCheckDefaultBrowser": true,
    "OverrideFirstRunPage": "",
    "OverridePostUpdatePage": "",
    "UserMessaging": { "WhatsNew": false, "ExtensionRecommendations": false, "FeatureRecommendations": false,
                       "SkipOnboarding": true, "MoreFromMozilla": false },
    "Preferences": {
      "browser.tabs.inTitlebar": { "Value": 1, "Status": "default" },
      "browser.aboutwelcome.enabled": { "Value": false, "Status": "default" }
    }
  }
}
EOF
mkdir -p "$R/etc/xdg"
cat > "$R/etc/xdg/mimeapps.list" <<'EOF'
[Default Applications]
x-scheme-handler/http=firefox.desktop
x-scheme-handler/https=firefox.desktop
text/html=firefox.desktop
EOF

# 2. BookerOS files ----------------------------------------------------------
rm -rf "$R/opt/bookeros"; mkdir -p "$R/opt/bookeros"
cp -r "$SRC/shell/." "$R/opt/bookeros/"
find "$R/opt/bookeros" -name '__pycache__' -prune -exec rm -rf {} +
install -m 755 "$SRC/system/bookeros-session" "$R/usr/local/bin/bookeros-session"
echo "$EDITION" > "$R/etc/bookeros-edition"
install -m 644 "$SRC/system/openbox-rc.xml" "$R/etc/xdg/openbox/bookeros-rc.xml"
install -m 644 "$SRC/system/picom.conf" "$R/etc/xdg/bookeros-picom.conf"

# start X on tty1 after automatic login
cat > "$R/etc/skel/.bash_profile" <<'EOF'
[ -f ~/.bashrc ] && . ~/.bashrc
if [ -z "${DISPLAY:-}" ] && [ "$(tty)" = /dev/tty1 ]; then
  exec startx /usr/local/bin/bookeros-session -- -nolisten tcp vt1 > ~/.xsession.log 2>&1
fi
EOF
mkdir -p "$R/etc/systemd/system/getty@tty1.service.d"
cat > "$R/etc/systemd/system/getty@tty1.service.d/autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin booker --noclear --skip-login --nohints --nohostname %I $TERM
EOF
printf 'allowed_users=anybody\nneeds_root_rights=yes\n' > "$R/etc/X11/Xwrapper.config"
mkdir -p "$R/etc/X11/xorg.conf.d"
cat > "$R/etc/X11/xorg.conf.d/00-keyboard.conf" <<'EOF'
Section "InputClass"
    Identifier "keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "gb"
EndSection
EOF
# let NetworkManager manage Ethernet as well as Wi-Fi
mkdir -p "$R/etc/NetworkManager/conf.d"
: > "$R/etc/NetworkManager/conf.d/10-globally-managed-devices.conf"
echo "booker ALL=(root) NOPASSWD: /usr/bin/hostnamectl, /usr/bin/nmcli" > "$R/etc/sudoers.d/bookeros"
chmod 440 "$R/etc/sudoers.d/bookeros"
echo bookeros > "$R/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 bookeros\n' > "$R/etc/hosts"
echo 'LANG=en_GB.UTF-8' > "$R/etc/default/locale"
ln -sf /usr/share/zoneinfo/Europe/London "$R/etc/localtime"; echo Europe/London > "$R/etc/timezone"
printf '%s 1.0 \\l\n\n' "$NAME" > "$R/etc/issue"; echo "$NAME 1.0" > "$R/etc/issue.net"
touch "$R/etc/skel/.hushlogin"; rm -f "$R"/etc/update-motd.d/*
cat > "$R/etc/os-release" <<'EOF'
PRETTY_NAME="__NAME__ 1.0"
NAME="__NAME__"
VERSION_ID="1.0"
VERSION="1.0"
ID=bookeros
ID_LIKE=ubuntu
VERSION_CODENAME=noble
UBUNTU_CODENAME=noble
EOF
sed -i "s/__NAME__/$NAME/g" "$R/etc/os-release"
chroot "$R" bash -c "locale-gen en_GB.UTF-8 >/dev/null; systemctl enable NetworkManager systemd-resolved >/dev/null 2>&1 || true; systemctl mask systemd-networkd-wait-online.service >/dev/null 2>&1 || true; update-initramfs -u >/dev/null"
ln -sf ../run/systemd/resolve/stub-resolv.conf "$R/etc/resolv.conf"
rm -f "$R/usr/sbin/policy-rc.d"; : > "$R/etc/machine-id"; rm -rf "$R/tmp/"* "$R/var/lib/apt/lists/"*
umounts

# 3. ISO ---------------------------------------------------------------------
rm -rf "$ISO"; mkdir -p "$ISO/casper" "$ISO/boot/grub"
cp "$R"/boot/vmlinuz-* "$ISO/casper/vmlinuz"
cp "$R"/boot/initrd.img-* "$ISO/casper/initrd"
mksquashfs "$R" "$ISO/casper/filesystem.squashfs" -noappend -comp xz -b 1M -e boot -wildcards -e 'proc/*' -e 'sys/*' -e 'dev/*' -e 'run/*'
du -sx --block-size=1 "$R" | cut -f1 > "$ISO/casper/filesystem.size"
cat > "$ISO/boot/grub/grub.cfg" <<'EOF'
set timeout=3
set default=0
insmod all_video
set menu_color_normal=white/black
set menu_color_highlight=black/light-gray
menuentry "__NAME__" {
    linux /casper/vmlinuz boot=casper username=booker hostname=bookeros userfullname=Booker noprompt quiet splash loglevel=3 systemd.show_status=false rd.systemd.show_status=false vt.global_cursor_default=0 ---
    initrd /casper/initrd
}
menuentry "__NAME__ (safe graphics)" {
    linux /casper/vmlinuz boot=casper username=booker hostname=bookeros userfullname=Booker noprompt nomodeset systemd.show_status=false ---
    initrd /casper/initrd
}
EOF
sed -i "s/__NAME__/$NAME/g" "$ISO/boot/grub/grub.cfg"
grub-mkrescue -o "$OUT" "$ISO" -- -volid "$VOLID"
ls -lh "$OUT"
