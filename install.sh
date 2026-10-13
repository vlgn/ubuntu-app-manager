#!/bin/sh
# Установка «Установленные программы» для текущего пользователя (без root, кроме установки зависимостей).
set -e
APP_ID=io.github.vlgn.AppManager
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/app-manager"
APPS="$HOME/.local/share/applications"

if ! command -v dpkg-query >/dev/null 2>&1 || ! command -v apt-get >/dev/null 2>&1; then
    echo "Ошибка: нужен дистрибутив на основе Debian/Ubuntu (apt и dpkg)." >&2
    exit 1
fi

if ! python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); from gi.repository import Gtk, Adw" 2>/dev/null; then
    echo "Устанавливаю зависимости: python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
    sudo apt-get install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
fi

ADW=$(python3 -c "import gi; gi.require_version('Adw','1'); from gi.repository import Adw; print(Adw.get_minor_version())")
if [ "$ADW" -lt 5 ]; then
    echo "Ошибка: нужна libadwaita 1.5+ (Ubuntu 24.04 или новее), у вас 1.$ADW." >&2
    exit 1
fi

install -Dm755 "$DIR/app-manager.py" "$DEST/app-manager.py"
mkdir -p "$APPS" "$HOME/.local/bin"
ln -sf "$DEST/app-manager.py" "$HOME/.local/bin/app-manager"
rm -f "$APPS/local.appmanager.desktop"  # старое имя ярлыка
install -Dm644 "$DIR/$APP_ID.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_ID.svg"
touch "$HOME/.local/share/icons/hicolor"  # чтобы оболочка перечитала значки
sed "s|@EXEC@|python3 $DEST/app-manager.py|" "$DIR/$APP_ID.desktop" > "$APPS/$APP_ID.desktop"
update-desktop-database "$APPS" 2>/dev/null || true

echo "Готово! Ищите «Установленные программы» в меню или запустите: app-manager"
