#!/usr/bin/env python3
"""Initialize database with tables and seed players - standalone script"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app.database import SessionLocal, init_db
from backend.app.models import Player

# The 6 players
PLAYERS = [
    "Noam",
    "Itay",
    "Ayal",
    "Ari",
    "Sharon",
    "Dori",
]

def seed_players():
    """Insert the 6 players if they don't exist"""
    db = SessionLocal()
    
    try:
        # Check if players already exist
        existing_count = db.query(Player).count()
        
        if existing_count > 0:
            print(f"✅ Database already has {existing_count} players. Skipping seed.")
            return
        
        # Insert players
        for name in PLAYERS:
            player = Player(name=name)
            db.add(player)
        
        db.commit()
        print(f"✅ Seeded {len(PLAYERS)} players: {', '.join(PLAYERS)}")
    
    except Exception as e:
        print(f"❌ Error seeding players: {e}")
        db.rollback()
    
    finally:
        db.close()


if __name__ == "__main__":
    print("🏗️  Initializing database...")
    init_db()
    print("✅ Database tables created")
    
    print("\n🌱 Seeding players...")
    seed_players()
    
    print("\n🎉 Database initialization complete!")
