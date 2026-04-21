#!/bin/bash

set -e

NAME="zorin-icon-settings"
VERSION="2.1.0"
ARCH="all"
PKG="${NAME}_${VERSION}_${ARCH}"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTDIR="${ROOT_DIR}/dist"
TMPBUILD="$(mktemp -d "${HOME}/.cache/${NAME}.XXXXXX")"
PKGDIR="${TMPBUILD}/${PKG}"

run_dpkg_deb() {
    if command -v dpkg-deb >/dev/null 2>&1; then
        dpkg-deb "$@"
        return
    fi

    if command -v flatpak-spawn >/dev/null 2>&1; then
        flatpak-spawn --host dpkg-deb "$@"
        return
    fi

    echo "dpkg-deb not found" >&2
    exit 127
}

echo "==> Building ${PKG}.deb"
mkdir -p "${OUTDIR}"

install -d "${PKGDIR}/DEBIAN"
install -d "${PKGDIR}/usr/lib/${NAME}"
install -d "${PKGDIR}/usr/bin"
install -d "${PKGDIR}/usr/share/applications"
install -d "${PKGDIR}/usr/share/doc/${NAME}"
install -d "${PKGDIR}/usr/share/icons/hicolor/scalable/apps"
install -d "${PKGDIR}/usr/share/icons/hicolor/64x64/apps"
install -d "${PKGDIR}/usr/share/icons/hicolor/128x128/apps"

install -m 644 "${ROOT_DIR}/backend.py" "${PKGDIR}/usr/lib/${NAME}/backend.py"
install -m 644 "${ROOT_DIR}/autostart.py" "${PKGDIR}/usr/lib/${NAME}/autostart.py"
install -m 644 "${ROOT_DIR}/constants.py" "${PKGDIR}/usr/lib/${NAME}/constants.py"
install -m 644 "${ROOT_DIR}/desktop_entries.py" "${PKGDIR}/usr/lib/${NAME}/desktop_entries.py"
install -m 644 "${ROOT_DIR}/desktop_layouts.py" "${PKGDIR}/usr/lib/${NAME}/desktop_layouts.py"
install -m 644 "${ROOT_DIR}/desktop_watcher.py" "${PKGDIR}/usr/lib/${NAME}/desktop_watcher.py"
install -m 644 "${ROOT_DIR}/i18n.py" "${PKGDIR}/usr/lib/${NAME}/i18n.py"
install -m 644 "${ROOT_DIR}/layout_store.py" "${PKGDIR}/usr/lib/${NAME}/layout_store.py"
install -m 644 "${ROOT_DIR}/main.py" "${PKGDIR}/usr/lib/${NAME}/main.py"
install -m 644 "${ROOT_DIR}/preferences.py" "${PKGDIR}/usr/lib/${NAME}/preferences.py"
install -m 644 "${ROOT_DIR}/theme.py" "${PKGDIR}/usr/lib/${NAME}/theme.py"
install -m 644 "${ROOT_DIR}/ui.py" "${PKGDIR}/usr/lib/${NAME}/ui.py"
install -m 755 "${ROOT_DIR}/zorin-icon-settings.py" "${PKGDIR}/usr/lib/${NAME}/zorin-icon-settings.py"
install -m 644 "${ROOT_DIR}/assets/zorin-desktop-studio.svg" "${PKGDIR}/usr/share/icons/hicolor/scalable/apps/zorin-desktop-studio.svg"
if [ -f "${ROOT_DIR}/assets/zorin-desktop-studio-64.png" ]; then
    install -m 644 "${ROOT_DIR}/assets/zorin-desktop-studio-64.png" "${PKGDIR}/usr/share/icons/hicolor/64x64/apps/zorin-desktop-studio.png"
fi
if [ -f "${ROOT_DIR}/assets/zorin-desktop-studio-128.png" ]; then
    install -m 644 "${ROOT_DIR}/assets/zorin-desktop-studio-128.png" "${PKGDIR}/usr/share/icons/hicolor/128x128/apps/zorin-desktop-studio.png"
fi
install -m 644 "${ROOT_DIR}/README.md" "${PKGDIR}/usr/share/doc/${NAME}/README.md"

cat > "${PKGDIR}/usr/bin/${NAME}" << 'EOF'
#!/bin/bash
exec /usr/bin/python3 /usr/lib/zorin-icon-settings/main.py "$@"
EOF
chmod 755 "${PKGDIR}/usr/bin/${NAME}"

cat > "${PKGDIR}/usr/share/applications/${NAME}.desktop" << EOF
[Desktop Entry]
Name=Zorin Desktop Studio
Name[tr]=Zorin Masaüstü Stüdyo
Comment=Adjust desktop icon size and edit desktop launchers
Comment[tr]=Masaüstü simge boyutlarını ayarla ve masaüstü kısayollarını düzenle
Exec=${NAME}
Icon=zorin-desktop-studio
Terminal=false
Type=Application
Categories=Settings;DesktopSettings;Utility;
Keywords=zorin;desktop;icons;launcher;gtk;
StartupNotify=true
EOF

cat > "${PKGDIR}/DEBIAN/control" << EOF
Package: ${NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, gir1.2-gio-2.0
Maintainer: Ali <ali@example.com>
Description: Desktop tools suite for Zorin OS
 GTK-based utility for icon tuning, desktop launcher editing, and
 desktop layout save/restore workflows on Zorin OS.
EOF

cat > "${PKGDIR}/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
EOF
chmod 755 "${PKGDIR}/DEBIAN/postinst"

find "${PKGDIR}" -type d -exec chmod 755 {} +
find "${PKGDIR}" -type f -exec chmod 644 {} +
chmod 755 "${PKGDIR}/DEBIAN/postinst"
chmod 755 "${PKGDIR}/usr/bin/${NAME}"
chmod 755 "${PKGDIR}/usr/lib/${NAME}/zorin-icon-settings.py"

run_dpkg_deb --build --root-owner-group "${PKGDIR}"
cp "${TMPBUILD}/${PKG}.deb" "${OUTDIR}/${PKG}.deb"
rm -rf "${TMPBUILD}"

echo "==> Output: ${OUTDIR}/${PKG}.deb"
