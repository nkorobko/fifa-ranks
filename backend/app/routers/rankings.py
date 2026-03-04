"""Rankings API endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List

from backend.app.database import get_db
from backend.app.models import Player, Match, RatingHistory
from backend.app.schemas import PlayerRanking

router = APIRouter()


def get_player_stats(player_id: int, db: Session):
    """Calculate wins/losses/draws for a player"""
    matches = db.query(Match).filter(
        and_(
            Match.is_deleted == False,
            ((Match.team1_player1 == player_id) | 
             (Match.team1_player2 == player_id) |
             (Match.team2_player1 == player_id) | 
             (Match.team2_player2 == player_id))
        )
    ).all()
    
    wins = 0
    losses = 0
    draws = 0
    
    for match in matches:
        on_team1 = player_id in [match.team1_player1, match.team1_player2]
        
        if match.team1_score > match.team2_score:
            wins += 1 if on_team1 else 0
            losses += 0 if on_team1 else 1
        elif match.team2_score > match.team1_score:
            losses += 1 if on_team1 else 0
            wins += 0 if on_team1 else 1
        else:
            draws += 1
    
    return wins, losses, draws


@router.get("/current", response_model=List[PlayerRanking])
async def get_current_rankings(db: Session = Depends(get_db)):
    """
    Get current player rankings sorted by TrueSkill ordinal.
    
    Returns list of players with their current rating, stats, and rank.
    """
    players_with_ratings = []
    all_players = db.query(Player).all()
    
    for player in all_players:
        latest_rating = (
            db.query(RatingHistory)
            .filter(RatingHistory.player_id == player.id)
            .order_by(RatingHistory.created_at.desc())
            .first()
        )
        
        if latest_rating:
            wins, losses, draws = get_player_stats(player.id, db)
            matches_played = wins + losses + draws
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            
            players_with_ratings.append({
                "player_id": player.id,
                "player_name": player.name,
                "mu": latest_rating.mu,
                "sigma": latest_rating.sigma,
                "ordinal": latest_rating.ordinal,
                "matches_played": matches_played,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": win_rate,
            })
    
    # Sort by ordinal descending
    players_with_ratings.sort(key=lambda x: x["ordinal"], reverse=True)
    
    # Add rank
    for rank, player in enumerate(players_with_ratings, start=1):
        player["rank"] = rank
    
    return players_with_ratings
