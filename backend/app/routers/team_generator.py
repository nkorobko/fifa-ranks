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
    Generate balanced 2v2 team matchups.
    
    Requires exactly 4 player IDs.
    Returns top N most balanced matchups sorted by fairness.
    """
    if len(request.player_ids) != 4:
        raise HTTPException(
            status_code=400,
            detail="Exactly 4 players required for 2v2 team generation"
        )
    
    try:
        matchups = generate_balanced_teams(request.player_ids, db, request.top_n)
        return {
            "matchups": matchups,
            "total": len(matchups)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
