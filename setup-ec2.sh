#!/bin/bash
# FIFA Ranks - EC2 Setup Script

set -e

echo "🏆 FIFA Ranks Setup for EC2"
echo "=============================="
echo ""

# Get current directory
INSTALL_DIR=$(pwd)
CURRENT_USER=$(whoami)

echo "📁 Install directory: $INSTALL_DIR"
echo "👤 User: $CURRENT_USER"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Creating .env template..."
    cat > .env << 'EOF'
DATABASE_URL=sqlite:///./fifa.db
API_HOST=0.0.0.0
API_PORT=8000
TELEGRAM_BOT_TOKEN=8650968965:AAFr17sboXlnKsvmmKZlWqOUF6l7dwYy7Jg
DEBUG=false
EOF
    echo "✅ Created .env file"
else
    echo "✅ Found .env file"
fi

echo ""
echo "1️⃣  Creating virtual environment..."
python3 -m venv fifa-env
echo "✅ Virtual environment created"

echo ""
echo "2️⃣  Installing dependencies..."
source fifa-env/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Dependencies installed"

echo ""
echo "3️⃣  Initializing database..."
python -m backend.seed
echo "✅ Database initialized"

echo ""
echo "4️⃣  Creating systemd service files..."

# Create API service
cat > fifa-api.service << EOF
[Unit]
Description=FIFA Ranks API Server
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/fifa-env/bin"
ExecStart=$INSTALL_DIR/fifa-env/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create Bot service
cat > fifa-bot.service << EOF
[Unit]
Description=FIFA Ranks Telegram Bot
After=network.target fifa-api.service
Requires=fifa-api.service

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/fifa-env/bin"
ExecStart=$INSTALL_DIR/fifa-env/bin/python -m backend.bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service files created"

echo ""
echo "5️⃣  Installing systemd services (requires sudo)..."
sudo cp fifa-api.service /etc/systemd/system/
sudo cp fifa-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
echo "✅ Services installed"

echo ""
echo "6️⃣  Starting services..."
sudo systemctl enable fifa-api
sudo systemctl enable fifa-bot
sudo systemctl start fifa-api
sudo systemctl start fifa-bot
echo "✅ Services started"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📊 Service Status:"
sudo systemctl status fifa-api --no-pager -l
echo ""
sudo systemctl status fifa-bot --no-pager -l

echo ""
echo "📝 Useful commands:"
echo "  sudo systemctl status fifa-api   # Check API status"
echo "  sudo systemctl status fifa-bot   # Check bot status"
echo "  sudo systemctl restart fifa-api  # Restart API"
echo "  sudo systemctl restart fifa-bot  # Restart bot"
echo "  sudo journalctl -u fifa-api -f   # View API logs"
echo "  sudo journalctl -u fifa-bot -f   # View bot logs"
echo ""
echo "🤖 Your bot should now be online!"
echo "Add it to your Telegram group and try: /help"
