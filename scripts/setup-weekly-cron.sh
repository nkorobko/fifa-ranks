#!/bin/bash
# Setup systemd timer for weekly Power Index generation

set -e

echo "📅 Setting up FIFA Ranks weekly rankings timer..."

# Copy service and timer files
sudo cp fifa-weekly.service /etc/systemd/system/
sudo cp fifa-weekly.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the timer
sudo systemctl enable fifa-weekly.timer
sudo systemctl start fifa-weekly.timer

echo "✅ Weekly rankings timer installed!"
echo ""
echo "Status:"
sudo systemctl status fifa-weekly.timer --no-pager
echo ""
echo "Next scheduled run:"
sudo systemctl list-timers fifa-weekly.timer --no-pager
echo ""
echo "To manually trigger: sudo systemctl start fifa-weekly.service"
echo "To check logs: sudo journalctl -u fifa-weekly.service"
