#!/bin/bash
# Feishu Button Cards Plugin - Installer
set -e

PLUGIN_DIR="$HOME/.hermes/plugins/feishu_commands"
SKILL_DIR="$HOME/.hermes/skills/messaging/feishu-buttons"
CONFIG="$HOME/.hermes/config.yaml"

REPO="$1"
if [ -z "$REPO" ]; then
    echo "Enter your GitHub username (or 'owner/repo'):"
    read -r REPO
fi

BASE="https://raw.githubusercontent.com/$REPO/main"

echo " Installing Feishu Button Cards Plugin..."

# Plugin
mkdir -p "$PLUGIN_DIR"
for f in __init__.py plugin.yaml; do
    curl -sSL "$BASE/plugins/feishu_commands/$f" -o "$PLUGIN_DIR/$f"
    echo "  ✓ $f"
done

# Skill (optional)
echo ""
echo "  Install skill? [Y/n]"
read -r INSTALL_SKILL
if [[ "$INSTALL_SKILL" != "n" && "$INSTALL_SKILL" != "N" ]]; then
    mkdir -p "$SKILL_DIR"
    curl -sSL "$BASE/skills/feishu-buttons/SKILL.md" -o "$SKILL_DIR/SKILL.md"
    echo "  ✓ skill installed"
fi

# Enable in config
if grep -q "enabled:" "$CONFIG" 2>/dev/null; then
    if ! grep -q "feishu_commands" "$CONFIG"; then
        sed -i '/enabled:/a\    - feishu_commands' "$CONFIG"
        echo "  ✓ enabled in config.yaml"
    else
        echo "  already enabled"
    fi
fi

# Restart
echo ""
echo "  Restart gateway? [Y/n]"
read -r RESTART
if [[ "$RESTART" != "n" && "$RESTART" != "N" ]]; then
    hermes gateway restart 2>/dev/null || systemctl restart hermes-gateway 2>/dev/null || echo "  Please restart: hermes gateway restart"
fi

echo ""
echo " Done!"
echo "  Check: grep 'feishu_commands' ~/.hermes/logs/agent.log"
