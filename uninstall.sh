#!/bin/sh
# Удаление «Установленные программы».
APP_ID=io.github.vlgn.AppManager
rm -rf "$HOME/.local/share/app-manager"
rm -f "$HOME/.local/bin/app-manager" "$HOME/.local/share/applications/$APP_ID.desktop" \
      "$HOME/.local/share/applications/local.appmanager.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Удалено."
