#!/usr/bin/env bash
set -euo pipefail

# === LeSphinx Deployment Script ===
# Usage: ./deploy.sh <VM_IP> [SSH_USER]
# Prerequisites:
#   - SSH access to the VM
#   - Caddy installed on the VM (apt install caddy)
#   - Python 3.11+ on the VM
#   - Cloudflare DNS A record pointing thesphinx.ai -> VM_IP

VM_IP="${1:?Usage: ./deploy.sh <VM_IP> [SSH_USER]}"
SSH_USER="${2:-$USER}"
REMOTE="$SSH_USER@$VM_IP"
APP_DIR="/opt/lesphinx"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Deploying LeSphinx to $REMOTE..."

echo "==> Creating app directory..."
ssh "$REMOTE" "sudo mkdir -p $APP_DIR && sudo chown $SSH_USER:$SSH_USER $APP_DIR"

echo "==> Syncing code..."
rsync -avz --delete \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.env' \
    --exclude 'frontend-lovable' \
    --exclude '.git' \
    --exclude 'scripts' \
    --exclude 'tests' \
    "$REPO_DIR/" "$REMOTE:$APP_DIR/"

echo "==> Setting up Python environment..."
ssh "$REMOTE" "cd $APP_DIR && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt"

echo "==> Copying Caddyfile..."
ssh "$REMOTE" "sudo cp $APP_DIR/deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy"

echo "==> Installing systemd service..."
ssh "$REMOTE" "sudo cp $APP_DIR/deploy/lesphinx.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable lesphinx && sudo systemctl restart lesphinx"

echo "==> Checking service status..."
ssh "$REMOTE" "sudo systemctl status lesphinx --no-pager" || true

echo ""
echo "==> Deployment complete!"
echo "    Make sure .env is configured on the VM: $APP_DIR/.env"
echo "    Make sure Cloudflare DNS A record points thesphinx.ai -> $VM_IP"
echo "    Site should be live at https://thesphinx.ai"
