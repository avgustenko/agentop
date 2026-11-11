#!/usr/bin/env bash
set -euo pipefail

DEST="${DEST:-$HOME/.local/bin}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/agentop"

if [[ ! -f "$SRC" ]]; then
  echo "error: $SRC not found" >&2
  exit 1
fi

mkdir -p "$DEST"
install -m 755 "$SRC" "$DEST/agentop"
echo "✓ installed: $DEST/agentop"

APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
cat > "$APPS/agentop.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=AgentOp
Comment=Terminal dashboard for AI agents
Exec=$DEST/agentop
Icon=utilities-system-monitor
Terminal=true
Categories=System;Monitor;Utility;
StartupNotify=false
EOF
update-desktop-database "$APPS" 2>/dev/null || true
echo "✓ desktop entry: $APPS/agentop.desktop"

# расширение GNOME Shell: индикатор лимитов в верхней панели
EXT_UUID="agentop@avgustenko"
if [[ -d "$HERE/gnome-extension/$EXT_UUID" ]] && command -v gnome-shell >/dev/null 2>&1 \
    && [[ "${NO_GNOME_EXTENSION:-0}" != "1" ]]; then
  EXT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$EXT_UUID"
  mkdir -p "$EXT_DIR"
  cp "$HERE/gnome-extension/$EXT_UUID/"{metadata.json,extension.js,stylesheet.css} "$EXT_DIR/"
  if ! gnome-extensions enable "$EXT_UUID" 2>/dev/null; then
    # новое расширение GNOME видит только после перезахода: включаем заранее через gsettings
    cur="$(gsettings get org.gnome.shell enabled-extensions 2>/dev/null || echo "@as []")"
    if [[ "$cur" != *"'$EXT_UUID'"* ]]; then
      if [[ "$cur" == "@as []" || "$cur" == "[]" ]]; then new="['$EXT_UUID']"; else new="${cur%]}, '$EXT_UUID']"; fi
      gsettings set org.gnome.shell enabled-extensions "$new" 2>/dev/null || true
    fi
    echo "✓ GNOME extension: $EXT_DIR (выйдите из сеанса и зайдите снова — индикатор появится в верхней панели)"
  else
    echo "✓ GNOME extension enabled: $EXT_DIR"
  fi
fi

case ":$PATH:" in
  *":$DEST:"*) ;;
  *) echo "note: $DEST is not in PATH" ;;
esac

echo
echo "Run: agentop"
