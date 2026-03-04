"""Web page routes (HTML templates)"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta

from backend.app.database import get_db
from backend.app.models import Player, Match, RatingHistory

router = APIRouter()
templates = Jinja2Templates(directory="backend/app/templates")


def get_player_stats(player_id: int, db: Session):
    """Calculate wins/losses/draws for a player"""
    # Get all non-deleted matches where this player participated
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
        # Determine if player was on team1 or team2
        on_team1 = player_id in [match.team1_player1, match.team1_player2]
        
        if match.team1_score > match.team2_score:
            if on_team1:
                wins += 1
            else:
                losses += 1
        elif match.team2_score > match.team1_score:
            if on_team1:
                losses += 1
            else:
                wins += 1
        else:
            draws += 1
    
    return wins, losses, draws


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Home page with overview stats"""
    
    # Total matches
    total_matches = db.query(Match).filter(Match.is_deleted == False).count()
    
    # Active players (players with at least one rating)
    active_players = db.query(Player).join(RatingHistory).distinct().count()
    
    # Matches today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    matches_today = db.query(Match).filter(
        and_(
            Match.is_deleted == False,
            Match.played_at >= today_start
        )
    ).count()
    
    # Get top 3 players with current ratings
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
                "id": player.id,
                "name": player.name,
                "mu": latest_rating.mu,
                "sigma": latest_rating.sigma,
                "ordinal": latest_rating.ordinal,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "matches_played": matches_played,
                "win_rate": win_rate,
            })
    
    # Sort by ordinal descending
    players_with_ratings.sort(key=lambda x: x["ordinal"], reverse=True)
    
    stats = {
        "total_matches": total_matches,
        "active_players": active_players,
        "matches_today": matches_today,
    }
    
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "stats": stats,
            "top_players": players_with_ratings[:3],
        }
    )


@router.get("/rankings", response_class=HTMLResponse)
async def rankings_page(request: Request, db: Session = Depends(get_db)):
    """Rankings leaderboard page"""
    
    # Get all players with their latest ratings
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
                "id": player.id,
                "name": player.name,
                "mu": latest_rating.mu,
                "sigma": latest_rating.sigma,
                "ordinal": latest_rating.ordinal,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "matches_played": matches_played,
                "win_rate": win_rate,
            })
    
    # Sort by ordinal descending
    players_with_ratings.sort(key=lambda x: x["ordinal"], reverse=True)
    
    return templates.TemplateResponse(
        "rankings.html",
        {
            "request": request,
            "rankings": players_with_ratings,
        }
    )
