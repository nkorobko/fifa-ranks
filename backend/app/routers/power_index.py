"""Weekly Power Index API endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from backend.app.database import get_db
from backend.app.schemas import PowerIndexRanking
from backend.app.power_index import generate_weekly_rankings, get_week_start

router = APIRouter()


@router.get("/current", response_model=List[PowerIndexRanking])
async def get_current_power_index(db: Session = Depends(get_db)):
    """
    Get current Weekly Power Index rankings.
    
    Returns live-calculated rankings based on recent performance.
    """
    rankings = generate_weekly_rankings(db)
    return rankings


@router.post("/generate")
async def generate_and_save_rankings(db: Session = Depends(get_db)):
    """
    Generate and save current week's rankings to database.
    
    This endpoint is intended for cron jobs or manual triggering.
    """
    from backend.app.power_index import save_weekly_rankings
    
    week_start = get_week_start()
    save_weekly_rankings(db, week_start)
    
    return {
        "status": "success",
        "message": f"Weekly rankings generated for week starting {week_start.strftime('%Y-%m-%d')}",
        "week_start": week_start.isoformat()
    }
