#!/bin/sh
# Install "Installed Apps" for the current user (root is only needed for dependencies).
set -e
APP_ID=io.github.vlgn.AppManager
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/app-manager"
APPS="$HOME/.local/share/applications"

if ! command -v dpkg-query >/dev/null 2>&1 || ! command -v apt-get >/dev/null 2>&1; then
    echo "Error: a Debian/Ubuntu-based distro is required (apt and dpkg)." >&2
    exit 1
fi

NEED=""
python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); from gi.repository import Gtk, Adw" 2>/dev/null \
    || NEED="python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
command -v pkexec >/dev/null 2>&1 || NEED="$NEED pkexec"  # asks for the password when uninstalling
if [ -n "$NEED" ]; then
    echo "Installing dependencies: $NEED"
    # shellcheck disable=SC2086
    sudo apt-get install -y $NEED
fi

ADW=$(python3 -c "import gi; gi.require_version('Adw','1'); from gi.repository import Adw; print(Adw.get_minor_version())")
if [ "$ADW" -lt 5 ]; then
    echo "Error: libadwaita 1.5+ is required (Ubuntu 24.04 or newer), found 1.$ADW." >&2
    exit 1
fi

install -Dm755 "$DIR/app-manager.py" "$DEST/app-manager.py"
mkdir -p "$APPS" "$HOME/.local/bin"
ln -sf "$DEST/app-manager.py" "$HOME/.local/bin/app-manager"
rm -f "$APPS/local.appmanager.desktop"  # old shortcut name
install -Dm644 "$DIR/$APP_ID.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_ID.svg"
touch "$HOME/.local/share/icons/hicolor"  # make the shell reload icons

# Exec= must be quoted per the desktop entry spec (spaces, quotes, $ or \ in the home path)
python3 - "$DIR/$APP_ID.desktop" "$APPS/$APP_ID.desktop" "$DEST/app-manager.py" <<'PY'
import sys
src, dst, script = sys.argv[1:]
arg = '"' + ''.join('\\' + c if c in '"`$\\' else c for c in script) + '"'
arg = arg.replace('\\', '\\\\')  # string-level escaping is applied before the quoting rule
with open(src) as f:
    text = f.read()
with open(dst, 'w') as f:
    f.write(text.replace('@EXEC@', 'python3 ' + arg))
PY
update-desktop-database "$APPS" 2>/dev/null || true

echo "Done! Open \"Installed Apps\" from the app menu or run: app-manager"
