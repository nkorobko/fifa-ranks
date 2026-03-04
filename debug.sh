#!/bin/bash
# FIFA Ranks Debug Script - Captures all diagnostic info

echo "🔍 FIFA Ranks Diagnostic Report"
echo "================================"
echo ""
echo "Generated: $(date)"
echo ""

echo "📍 Current Location:"
pwd
echo ""

echo "👤 Current User:"
whoami
echo ""

echo "🐍 Python Environment:"
which python3
python3 --version
echo ""

echo "📦 Virtual Environment:"
if [ -d "fifa-env" ]; then
    echo "✅ fifa-env exists"
    ls -la fifa-env/bin/python* 2>&1 | head -5
else
    echo "❌ fifa-env not found"
fi
echo ""

echo "📁 Project Files:"
ls -la | grep -E "\.py|\.service|\.env|backend|fifa"
echo ""

echo "🔧 .env Configuration:"
if [ -f .env ]; then
    echo "✅ .env exists"
    cat .env | sed 's/TELEGRAM_BOT_TOKEN=.*/TELEGRAM_BOT_TOKEN=***REDACTED***/'
else
    echo "❌ .env not found"
fi
echo ""

echo "🗄️  Database Status:"
if [ -f fifa.db ]; then
    echo "✅ fifa.db exists"
    ls -lh fifa.db
    sqlite3 fifa.db "SELECT COUNT(*) as player_count FROM players;" 2>&1 || echo "Could not query database"
else
    echo "❌ fifa.db not found"
fi
echo ""

echo "🌐 API Service Status:"
sudo systemctl status fifa-api --no-pager -l | head -20
echo ""

echo "🤖 Bot Service Status:"
sudo systemctl status fifa-bot --no-pager -l | head -20
echo ""

echo "📜 Recent Bot Logs (last 50 lines):"
sudo journalctl -u fifa-bot -n 50 --no-pager
echo ""

echo "🔥 Bot Error Logs:"
sudo journalctl -u fifa-bot | grep -i "error\|exception\|traceback\|failed" | tail -20
echo ""

echo "🌐 API Health Check:"
curl -s http://localhost:8000/health || echo "❌ API not responding"
echo ""

echo "👥 Players in Database:"
curl -s http://localhost:8000/api/v1/players | head -c 500 || echo "❌ Could not fetch players"
echo ""

echo "🔌 Network & Ports:"
sudo netstat -tlnp | grep -E ":8000|python" || echo "netstat not available"
echo ""

echo "💾 Disk Space:"
df -h . | tail -1
echo ""

echo "🧪 Manual Bot Test (5 seconds):"
echo "Attempting to start bot manually for 5 seconds..."
cd ~/fifa-ranks
source fifa-env/bin/activate 2>/dev/null
timeout 5 python -m backend.bot.main 2>&1 | head -30 || echo "Bot test failed"
echo ""

echo "✅ Debug report complete!"
echo ""
echo "📋 Copy the output above and share it for diagnosis."
