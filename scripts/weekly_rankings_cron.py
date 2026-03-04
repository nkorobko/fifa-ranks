#!/usr/bin/env python3
"""
Weekly Rankings Cron Job

Run this script every Monday at 00:00 to generate and save weekly Power Index snapshots.

Setup (crontab):
    0 0 * * 1 cd /home/ubuntu/fifa-ranks && /home/ubuntu/fifa-ranks/fifa-env/bin/python3 scripts/weekly_rankings_cron.py

Or use systemd timer (preferred).
"""

import sys
import os
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from backend.app.database import SessionLocal
from backend.app.power_index import save_weekly_rankings, get_week_start
from datetime import datetime


def main():
    """Generate and save weekly Power Index rankings."""
    db = SessionLocal()
    
    try:
        week_start = get_week_start()
        print(f"[{datetime.now().isoformat()}] Generating weekly rankings for week starting {week_start.strftime('%Y-%m-%d')}")
        
        save_weekly_rankings(db, week_start)
        
        print(f"[{datetime.now().isoformat()}] Weekly rankings saved successfully!")
        return 0
        
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: {e}", file=sys.stderr)
        return 1
        
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
