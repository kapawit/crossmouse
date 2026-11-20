#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-0.1.0}"
OUT="$ROOT/dist"
PKG="$ROOT/.deb-build/crossmouse"

rm -rf "$ROOT/.deb-build" "$OUT"
mkdir -p "$PKG/DEBIAN" "$PKG/usr/lib/crossmouse" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/etc/crossmouse" "$OUT"

cp -r "$ROOT/crossmouse" "$PKG/usr/lib/crossmouse/"
cp -r "$ROOT/.deps" "$PKG/usr/lib/crossmouse/.deps"
rm -rf "$PKG/usr/lib/crossmouse/__pycache__"
find "$PKG/usr/lib/crossmouse" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
mkdir -p "$PKG/usr/share/doc/crossmouse"
cp "$ROOT/README.md" "$PKG/usr/share/doc/crossmouse/"
cp "$ROOT/config.example.json" "$PKG/etc/crossmouse/config.json"

cat > "$PKG/DEBIAN/control" <<EOF
Package: crossmouse
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.10), python3-cryptography
Maintainer: CrossMouse <crossmouse@local>
Description: Share one mouse and keyboard between two machines over LAN
 CrossMouse lets one mouse and keyboard drive a Linux and a Windows
 machine over a local network, paired by IP address and a shared secret.
 It supports bidirectional edge handoff and plain-text clipboard sync.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
chmod 644 /etc/crossmouse/config.json
mkdir -p /var/log/crossmouse
chmod 777 /var/log/crossmouse
EOF
chmod 755 "$PKG/DEBIAN/postinst"

cat > "$PKG/usr/bin/crossmouse" <<'EOF'
#!/bin/sh
export PYTHONPATH=/usr/lib/crossmouse/.deps:/usr/lib/crossmouse
exec python3 -m crossmouse.main "$@"
EOF
chmod 755 "$PKG/usr/bin/crossmouse"

cat > "$PKG/usr/share/applications/crossmouse.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=CrossMouse
Comment=Share one mouse and keyboard over LAN
Exec=/usr/bin/crossmouse
Terminal=false
Categories=Utility;Network;
EOF

dpkg-deb --root-owner-group --build "$PKG" "$OUT/crossmouse_${VERSION}_amd64.deb"
echo "Built: $OUT/crossmouse_${VERSION}_amd64.deb"
