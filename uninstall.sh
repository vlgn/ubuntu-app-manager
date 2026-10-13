#!/bin/sh
# Uninstall "Installed Apps".
APP_ID=io.github.vlgn.AppManager
rm -rf "$HOME/.local/share/app-manager"
rm -f "$HOME/.local/bin/app-manager" "$HOME/.local/share/applications/$APP_ID.desktop" \
      "$HOME/.local/share/applications/local.appmanager.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_ID.svg"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Removed."
