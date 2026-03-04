"""Pair chemistry and partnership API endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List

from backend.app.database import get_db
from backend.app.models import Player, PairStats
from backend.app.schemas import PairChemistry, PartnerSuggestion

router = APIRouter()


@router.get("/pairs", response_model=List[PairChemistry])
async def get_all_pairs(db: Session = Depends(get_db)):
    """
    Get all player pairs with their chemistry stats.
    
    Returns pairs sorted by matches played (most active partnerships first).
    """
    pairs = db.query(PairStats).order_by(PairStats.matches_played.desc()).all()
    
    result = []
    for pair in pairs:
        win_rate = (pair.wins / pair.matches_played * 100) if pair.matches_played > 0 else 0
        goal_diff = pair.goals_for - pair.goals_against
        avg_goals_for = pair.goals_for / pair.matches_played if pair.matches_played > 0 else 0
        
        result.append({
            "player1_id": pair.player1_id,
            "player1_name": pair.player1.name,
            "player2_id": pair.player2_id,
            "player2_name": pair.player2.name,
            "matches_played": pair.matches_played,
            "wins": pair.wins,
            "losses": pair.matches_played - pair.wins,  # Simplified (doesn't account for draws)
            "win_rate": win_rate,
            "goals_for": pair.goals_for,
            "goals_against": pair.goals_against,
            "goal_difference": goal_diff,
            "avg_goals_per_match": avg_goals_for,
            "last_played": pair.last_played,
        })
    
    return result


@router.get("/pairs/best", response_model=List[PairChemistry])
async def get_best_pairs(min_matches: int = 3, db: Session = Depends(get_db)):
    """
    Get best partnerships by win rate.
    
    Args:
        min_matches: Minimum matches played to qualify (default: 3)
    
    Returns pairs with at least min_matches, sorted by win rate.
    """
    pairs = db.query(PairStats).filter(PairStats.matches_played >= min_matches).all()
    
    result = []
    for pair in pairs:
        win_rate = (pair.wins / pair.matches_played * 100) if pair.matches_played > 0 else 0
        goal_diff = pair.goals_for - pair.goals_against
        avg_goals_for = pair.goals_for / pair.matches_played if pair.matches_played > 0 else 0
        
        result.append({
            "player1_id": pair.player1_id,
            "player1_name": pair.player1.name,
            "player2_id": pair.player2_id,
            "player2_name": pair.player2.name,
            "matches_played": pair.matches_played,
            "wins": pair.wins,
            "losses": pair.matches_played - pair.wins,
            "win_rate": win_rate,
            "goals_for": pair.goals_for,
            "goals_against": pair.goals_against,
            "goal_difference": goal_diff,
            "avg_goals_per_match": avg_goals_for,
            "last_played": pair.last_played,
        })
    
    # Sort by win rate, then by matches played
    result.sort(key=lambda x: (x["win_rate"], x["matches_played"]), reverse=True)
    
    return result


@router.get("/pairs/worst", response_model=List[PairChemistry])
async def get_worst_pairs(min_matches: int = 3, db: Session = Depends(get_db)):
    """
    Get worst partnerships by win rate.
    
    Args:
        min_matches: Minimum matches played to qualify (default: 3)
    
    Returns pairs with at least min_matches, sorted by win rate ascending.
    """
    pairs = db.query(PairStats).filter(PairStats.matches_played >= min_matches).all()
    
    result = []
    for pair in pairs:
        win_rate = (pair.wins / pair.matches_played * 100) if pair.matches_played > 0 else 0
        goal_diff = pair.goals_for - pair.goals_against
        avg_goals_for = pair.goals_for / pair.matches_played if pair.matches_played > 0 else 0
        
        result.append({
            "player1_id": pair.player1_id,
            "player1_name": pair.player1.name,
            "player2_id": pair.player2_id,
            "player2_name": pair.player2.name,
            "matches_played": pair.matches_played,
            "wins": pair.wins,
            "losses": pair.matches_played - pair.wins,
            "win_rate": win_rate,
            "goals_for": pair.goals_for,
            "goals_against": pair.goals_against,
            "goal_difference": goal_diff,
            "avg_goals_per_match": avg_goals_for,
            "last_played": pair.last_played,
        })
    
    # Sort by win rate ascending
    result.sort(key=lambda x: x["win_rate"])
    
    return result


@router.get("/suggest-partner/{player_id}", response_model=List[PartnerSuggestion])
async def suggest_partner(player_id: int, db: Session = Depends(get_db)):
    """
    Suggest best partners for a player based on past performance.
    
    Returns partners sorted by win rate when playing together.
    """
    # Get all pairs involving this player
    pairs = db.query(PairStats).filter(
        or_(
            PairStats.player1_id == player_id,
            PairStats.player2_id == player_id
        )
    ).all()
    
    suggestions = []
    for pair in pairs:
        # Determine which is the partner
        partner_id = pair.player2_id if pair.player1_id == player_id else pair.player1_id
        partner = db.query(Player).filter(Player.id == partner_id).first()
        
        win_rate = (pair.wins / pair.matches_played * 100) if pair.matches_played > 0 else 0
        goal_diff = pair.goals_for - pair.goals_against
        
        suggestions.append({
            "partner_id": partner_id,
            "partner_name": partner.name,
            "matches_together": pair.matches_played,
            "wins_together": pair.wins,
            "win_rate": win_rate,
            "goal_difference": goal_diff,
            "chemistry_score": win_rate + (goal_diff * 2),  # Simple weighted score
            "recommendation": (
                "🔥 Excellent chemistry!" if win_rate >= 70 else
                "✅ Good partnership" if win_rate >= 50 else
                "⚠️ Needs improvement" if win_rate >= 30 else
                "❌ Poor chemistry"
            )
        })
    
    # Sort by chemistry score
    suggestions.sort(key=lambda x: x["chemistry_score"], reverse=True)
    
    return suggestions
