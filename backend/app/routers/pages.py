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


@router.get("/matches", response_class=HTMLResponse)
async def matches_page(request: Request, db: Session = Depends(get_db)):
    """Recent matches page"""
    
    # Get recent matches (last 50)
    matches = (
        db.query(Match)
        .filter(Match.is_deleted == False)
        .order_by(Match.played_at.desc())
        .limit(50)
        .all()
    )
    
    # Build match data with player names
    matches_data = []
    for match in matches:
        # Determine winner
        if match.team1_score > match.team2_score:
            winner = "team1"
        elif match.team2_score > match.team1_score:
            winner = "team2"
        else:
            winner = "draw"
        
        matches_data.append({
            "id": match.id,
            "played_at": match.played_at,
            "team1_player1_id": match.team1_player1,
            "team1_player1_name": match.t1p1.name,
            "team1_player2_id": match.team1_player2,
            "team1_player2_name": match.t1p2.name,
            "team1_score": match.team1_score,
            "team2_player1_id": match.team2_player1,
            "team2_player1_name": match.t2p1.name,
            "team2_player2_id": match.team2_player2,
            "team2_player2_name": match.t2p2.name,
            "team2_score": match.team2_score,
            "winner": winner,
            "logged_by": match.logged_by,
        })
    
    return templates.TemplateResponse(
        "matches.html",
        {
            "request": request,
            "matches": matches_data,
        }
    )


@router.get("/players/{player_id}", response_class=HTMLResponse)
async def player_profile(player_id: int, request: Request, db: Session = Depends(get_db)):
    """Player profile page with stats and recent matches"""
    
    # Get player
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        # Return 404 page or redirect
        return templates.TemplateResponse(
            "home.html",
            {"request": request, "error": "Player not found"},
            status_code=404
        )
    
    # Get current rating
    latest_rating = (
        db.query(RatingHistory)
        .filter(RatingHistory.player_id == player_id)
        .order_by(RatingHistory.created_at.desc())
        .first()
    )
    
    # Calculate stats
    wins, losses, draws = get_player_stats(player_id, db)
    matches_played = wins + losses + draws
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    
    # Get player's rank
    all_players = db.query(Player).all()
    players_with_ratings = []
    for p in all_players:
        lr = (
            db.query(RatingHistory)
            .filter(RatingHistory.player_id == p.id)
            .order_by(RatingHistory.created_at.desc())
            .first()
        )
        if lr:
            players_with_ratings.append({"id": p.id, "ordinal": lr.ordinal})
    
    players_with_ratings.sort(key=lambda x: x["ordinal"], reverse=True)
    rank = next((i + 1 for i, p in enumerate(players_with_ratings) if p["id"] == player_id), None)
    
    # Get recent matches (last 10)
    matches = (
        db.query(Match)
        .filter(
            and_(
                Match.is_deleted == False,
                ((Match.team1_player1 == player_id) | 
                 (Match.team1_player2 == player_id) |
                 (Match.team2_player1 == player_id) | 
                 (Match.team2_player2 == player_id))
            )
        )
        .order_by(Match.played_at.desc())
        .limit(10)
        .all()
    )
    
    # Build recent matches data
    recent_matches = []
    for match in matches:
        on_team1 = player_id in [match.team1_player1, match.team1_player2]
        
        # Determine result
        if match.team1_score > match.team2_score:
            result = "win" if on_team1 else "loss"
        elif match.team2_score > match.team1_score:
            result = "loss" if on_team1 else "win"
        else:
            result = "draw"
        
        # Get partner and opponents
        if on_team1:
            partner_id = match.team1_player2 if match.team1_player1 == player_id else match.team1_player1
            partner = db.query(Player).filter(Player.id == partner_id).first()
            opponent1 = match.t2p1
            opponent2 = match.t2p2
            player_score = match.team1_score
            opponent_score = match.team2_score
        else:
            partner_id = match.team2_player2 if match.team2_player1 == player_id else match.team2_player1
            partner = db.query(Player).filter(Player.id == partner_id).first()
            opponent1 = match.t1p1
            opponent2 = match.t1p2
            player_score = match.team2_score
            opponent_score = match.team1_score
        
        # Get rating change for this match
        rating_history = (
            db.query(RatingHistory)
            .filter(
                and_(
                    RatingHistory.player_id == player_id,
                    RatingHistory.match_id == match.id
                )
            )
            .first()
        )
        
        # Calculate rating change
        rating_change = None
        if rating_history:
            # Get previous rating
            prev_rating = (
                db.query(RatingHistory)
                .filter(
                    and_(
                        RatingHistory.player_id == player_id,
                        RatingHistory.created_at < rating_history.created_at
                    )
                )
                .order_by(RatingHistory.created_at.desc())
                .first()
            )
            if prev_rating:
                rating_change = rating_history.ordinal - prev_rating.ordinal
        
        recent_matches.append({
            "played_at": match.played_at,
            "result": result,
            "partner_name": partner.name if partner else "Unknown",
            "opponent1_name": opponent1.name,
            "opponent2_name": opponent2.name,
            "player_score": player_score,
            "opponent_score": opponent_score,
            "rating_change": rating_change,
        })
    
    player_data = {
        "id": player.id,
        "name": player.name,
        "rank": rank,
        "mu": latest_rating.mu if latest_rating else 25.0,
        "sigma": latest_rating.sigma if latest_rating else 8.333,
        "ordinal": latest_rating.ordinal if latest_rating else 0.0,
        "matches_played": matches_played,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": win_rate,
    }
    
    return templates.TemplateResponse(
        "player_profile.html",
        {
            "request": request,
            "player": player_data,
            "recent_matches": recent_matches,
        }
    )


@router.get("/log-match", response_class=HTMLResponse)
async def log_match_page(request: Request, db: Session = Depends(get_db)):
    """Log match form page"""
    
    # Get all players for the dropdown
    players = db.query(Player).order_by(Player.name).all()
    
    return templates.TemplateResponse(
        "log_match.html",
        {
            "request": request,
            "players": players,
        }
    )
