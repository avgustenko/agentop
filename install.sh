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

case ":$PATH:" in
  *":$DEST:"*) ;;
  *) echo "note: $DEST is not in PATH" ;;
esac

echo
echo "Run: agentop"
