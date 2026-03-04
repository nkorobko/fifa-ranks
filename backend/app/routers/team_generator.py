"""Balanced team generator API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from backend.app.database import get_db
from backend.app.team_generator import generate_balanced_teams


router = APIRouter()


class TeamGeneratorRequest(BaseModel):
    player_ids: List[int]
    top_n: int = 5


@router.post("/generate")
async def generate_teams(request: TeamGeneratorRequest, db: Session = Depends(get_db)):
    """
    Generate balanced 2v2 team matchups or rotation schedule.
    
    - 4 players: Returns top N balanced matchups
    - 5 players: Returns rotation schedule (5 games, each player sits once)
    - 6 players: Returns tournament bracket (3 games, round-robin)
    """
    if len(request.player_ids) < 4 or len(request.player_ids) > 6:
        raise HTTPException(
            status_code=400,
            detail="Requires 4-6 players for team generation"
        )
    
    try:
        result = generate_balanced_teams(request.player_ids, db, request.top_n)
        
        # Handle different return types
        if isinstance(result, dict) and "type" in result:
            # Rotation schedule (5 or 6 players)
            return result
        else:
            # Regular matchups (4 players)
            return {
                "matchups": result,
                "total": len(result)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
