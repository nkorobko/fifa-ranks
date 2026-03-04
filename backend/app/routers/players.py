"""Player profile and stats API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional
from collections import defaultdict

from backend.app.database import get_db
from backend.app.models import Player, Match, RatingHistory, PairStats
from backend.app.config import settings

router = APIRouter()

# Response schemas
from pydantic import BaseModel, field_validator

class PlayerCreate(BaseModel):
    name: str
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError('Player name must be at least 2 characters')
        if len(v) > 50:
            raise ValueError('Player name must be at most 50 characters')
        return v

class PlayerStats(BaseModel):
    id: int
    name: str
    mu: float
    sigma: float
    ordinal: float
    matches_played: int
    wins: int
    draws: int
    losses: int
    win_rate: float
    goals_for: int
    goals_against: int

class Streak(BaseModel):
    type: str  # "W", "L", or "D"
    count: int

class PlayerProfile(BaseModel):
    id: int
    name: str
    current_rating: dict
    all_time_stats: dict
    current_streak: Streak
    best_streak: Streak

class RatingPoint(BaseModel):
    match_id: int
    played_at: str
    ordinal: float
    mu: float
    sigma: float

class PartnerStats(BaseModel):
    partner_id: int
    partner_name: str
    matches_together: int
    wins: int
    win_rate: float

class OpponentStats(BaseModel):
    opponent_id: int
    opponent_name: str
    matches_against: int
    wins: int
    losses: int
    win_rate: float

def get_player_matches(db: Session, player_id: int) -> List[Match]:
    """Get all non-deleted matches involving this player"""
    return db.query(Match).filter(
        Match.is_deleted == False,
        or_(
            Match.team1_player1 == player_id,
            Match.team1_player2 == player_id,
            Match.team2_player1 == player_id,
            Match.team2_player2 == player_id
        )
    ).order_by(Match.played_at.desc()).all()

def calculate_streak(matches: List[Match], player_id: int) -> Streak:
    """Calculate current win/loss/draw streak"""
    if not matches:
        return Streak(type="", count=0)
    
    streak_type = None
    count = 0
    
    for match in matches:
        # Determine if player was on team1 or team2
        on_team1 = player_id in [match.team1_player1, match.team1_player2]
        
        if match.team1_score > match.team2_score:
            result = "W" if on_team1 else "L"
        elif match.team2_score > match.team1_score:
            result = "L" if on_team1 else "W"
        else:
            result = "D"
        
        if streak_type is None:
            streak_type = result
            count = 1
        elif result == streak_type:
            count += 1
        else:
            break
    
    return Streak(type=streak_type or "", count=count)

def calculate_best_streak(matches: List[Match], player_id: int) -> Streak:
    """Calculate best win streak ever"""
    if not matches:
        return Streak(type="", count=0)
    
    # Reverse to go chronologically
    matches = list(reversed(matches))
    
    current_streak = 0
    best_streak = 0
    best_type = ""
    
    for match in matches:
        on_team1 = player_id in [match.team1_player1, match.team1_player2]
        
        if match.team1_score > match.team2_score:
            result = "W" if on_team1 else "L"
        elif match.team2_score > match.team1_score:
            result = "L" if on_team1 else "W"
        else:
            result = "D"
        
        if result == "W":
            current_streak += 1
            if current_streak > best_streak:
                best_streak = current_streak
                best_type = "W"
        else:
            current_streak = 0
    
    return Streak(type=best_type, count=best_streak)

@router.get("/", response_model=List[PlayerStats])
async def list_players(db: Session = Depends(get_db)):
    """
    List all players with current ratings and stats
    """
    players = db.query(Player).all()
    
    result = []
    for player in players:
        matches = get_player_matches(db, player.id)
        
        # Get current rating (latest rating history or defaults)
        latest_rating = db.query(RatingHistory).filter(
            RatingHistory.player_id == player.id
        ).order_by(RatingHistory.created_at.desc()).first()
        
        if latest_rating:
            mu, sigma, ordinal = latest_rating.mu, latest_rating.sigma, latest_rating.ordinal
        else:
            mu, sigma = settings.TRUESKILL_MU, settings.TRUESKILL_SIGMA
            ordinal = mu - 3 * sigma
        
        # Calculate stats
        wins = draws = losses = 0
        goals_for = goals_against = 0
        
        for match in matches:
            on_team1 = player.id in [match.team1_player1, match.team1_player2]
            
            if on_team1:
                goals_for += match.team1_score
                goals_against += match.team2_score
                if match.team1_score > match.team2_score:
                    wins += 1
                elif match.team1_score == match.team2_score:
                    draws += 1
                else:
                    losses += 1
            else:
                goals_for += match.team2_score
                goals_against += match.team1_score
                if match.team2_score > match.team1_score:
                    wins += 1
                elif match.team1_score == match.team2_score:
                    draws += 1
                else:
                    losses += 1
        
        matches_played = len(matches)
        win_rate = wins / matches_played if matches_played > 0 else 0.0
        
        result.append(PlayerStats(
            id=player.id,
            name=player.name,
            mu=mu,
            sigma=sigma,
            ordinal=ordinal,
            matches_played=matches_played,
            wins=wins,
            draws=draws,
            losses=losses,
            win_rate=round(win_rate, 3),
            goals_for=goals_for,
            goals_against=goals_against
        ))
    
    return result


@router.post("/", response_model=PlayerStats)
async def create_player(player: PlayerCreate, db: Session = Depends(get_db)):
    """
    Create a new player
    """
    # Check if player name already exists
    existing = db.query(Player).filter(Player.name == player.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Player '{player.name}' already exists")
    
    # Create new player
    new_player = Player(name=player.name)
    db.add(new_player)
    db.commit()
    db.refresh(new_player)
    
    # Return with default ratings
    return PlayerStats(
        id=new_player.id,
        name=new_player.name,
        mu=settings.TRUESKILL_MU,
        sigma=settings.TRUESKILL_SIGMA,
        ordinal=settings.TRUESKILL_MU - 3 * settings.TRUESKILL_SIGMA,
        matches_played=0,
        wins=0,
        draws=0,
        losses=0,
        win_rate=0.0,
        goals_for=0,
        goals_against=0
    )


@router.get("/{player_id}", response_model=PlayerProfile)
async def get_player_profile(player_id: int, db: Session = Depends(get_db)):
    """
    Get full player profile with stats and streaks
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    matches = get_player_matches(db, player.id)
    
    # Get current rating
    latest_rating = db.query(RatingHistory).filter(
        RatingHistory.player_id == player.id
    ).order_by(RatingHistory.created_at.desc()).first()
    
    if latest_rating:
        mu, sigma, ordinal = latest_rating.mu, latest_rating.sigma, latest_rating.ordinal
    else:
        mu, sigma = settings.TRUESKILL_MU, settings.TRUESKILL_SIGMA
        ordinal = mu - 3 * sigma
    
    # Calculate all-time stats
    wins = draws = losses = 0
    goals_for = goals_against = 0
    
    for match in matches:
        on_team1 = player.id in [match.team1_player1, match.team1_player2]
        
        if on_team1:
            goals_for += match.team1_score
            goals_against += match.team2_score
            if match.team1_score > match.team2_score:
                wins += 1
            elif match.team1_score == match.team2_score:
                draws += 1
            else:
                losses += 1
        else:
            goals_for += match.team2_score
            goals_against += match.team1_score
            if match.team2_score > match.team1_score:
                wins += 1
            elif match.team1_score == match.team2_score:
                draws += 1
            else:
                losses += 1
    
    matches_played = len(matches)
    win_rate = wins / matches_played if matches_played > 0 else 0.0
    
    # Calculate streaks
    current_streak = calculate_streak(matches, player.id)
    best_streak = calculate_best_streak(matches, player.id)
    
    return PlayerProfile(
        id=player.id,
        name=player.name,
        current_rating={
            "mu": round(mu, 2),
            "sigma": round(sigma, 2),
            "ordinal": round(ordinal, 2)
        },
        all_time_stats={
            "matches_played": matches_played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "win_rate": round(win_rate, 3),
            "goals_for": goals_for,
            "goals_against": goals_against,
            "goal_diff": goals_for - goals_against
        },
        current_streak=current_streak,
        best_streak=best_streak
    )

@router.get("/{player_id}/history", response_model=List[RatingPoint])
async def get_player_rating_history(player_id: int, db: Session = Depends(get_db)):
    """
    Get rating history over time for trend charts
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    history = db.query(RatingHistory).filter(
        RatingHistory.player_id == player_id
    ).order_by(RatingHistory.created_at.asc()).all()
    
    result = []
    for entry in history:
        match = db.query(Match).filter(Match.id == entry.match_id).first()
        result.append(RatingPoint(
            match_id=entry.match_id,
            played_at=match.played_at.isoformat() if match else "",
            ordinal=round(entry.ordinal, 2),
            mu=round(entry.mu, 2),
            sigma=round(entry.sigma, 2)
        ))
    
    return result

@router.get("/{player_id}/partners", response_model=List[PartnerStats])
async def get_player_partners(player_id: int, db: Session = Depends(get_db)):
    """
    Win rate with each partner
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    # Get all pair stats involving this player
    pairs_as_p1 = db.query(PairStats).filter(PairStats.player1_id == player_id).all()
    pairs_as_p2 = db.query(PairStats).filter(PairStats.player2_id == player_id).all()
    
    result = []
    
    for pair in pairs_as_p1:
        partner = db.query(Player).filter(Player.id == pair.player2_id).first()
        if pair.matches_played > 0:
            result.append(PartnerStats(
                partner_id=partner.id,
                partner_name=partner.name,
                matches_together=pair.matches_played,
                wins=pair.wins,
                win_rate=round(pair.wins / pair.matches_played, 3)
            ))
    
    for pair in pairs_as_p2:
        partner = db.query(Player).filter(Player.id == pair.player1_id).first()
        if pair.matches_played > 0:
            result.append(PartnerStats(
                partner_id=partner.id,
                partner_name=partner.name,
                matches_together=pair.matches_played,
                wins=pair.wins,
                win_rate=round(pair.wins / pair.matches_played, 3)
            ))
    
    # Sort by win rate descending
    result.sort(key=lambda x: x.win_rate, reverse=True)
    
    return result

@router.get("/{player_id}/opponents", response_model=List[OpponentStats])
async def get_player_opponents(player_id: int, db: Session = Depends(get_db)):
    """
    Record vs each opponent (head-to-head when on opposite teams)
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    # Get all players
    all_players = db.query(Player).filter(Player.id != player_id).all()
    
    result = []
    
    for opponent in all_players:
        # Find matches where player and opponent were on opposite teams
        matches = db.query(Match).filter(
            Match.is_deleted == False,
            or_(
                # Player on team1, opponent on team2
                and_(
                    or_(Match.team1_player1 == player_id, Match.team1_player2 == player_id),
                    or_(Match.team2_player1 == opponent.id, Match.team2_player2 == opponent.id)
                ),
                # Player on team2, opponent on team1
                and_(
                    or_(Match.team2_player1 == player_id, Match.team2_player2 == player_id),
                    or_(Match.team1_player1 == opponent.id, Match.team1_player2 == opponent.id)
                )
            )
        ).all()
        
        if not matches:
            continue
        
        wins = losses = 0
        
        for match in matches:
            player_on_team1 = player_id in [match.team1_player1, match.team1_player2]
            
            if player_on_team1:
                if match.team1_score > match.team2_score:
                    wins += 1
                elif match.team1_score < match.team2_score:
                    losses += 1
            else:
                if match.team2_score > match.team1_score:
                    wins += 1
                elif match.team2_score < match.team1_score:
                    losses += 1
        
        matches_against = len(matches)
        win_rate = wins / matches_against if matches_against > 0 else 0.0
        
        result.append(OpponentStats(
            opponent_id=opponent.id,
            opponent_name=opponent.name,
            matches_against=matches_against,
            wins=wins,
            losses=losses,
            win_rate=round(win_rate, 3)
        ))
    
    # Sort by matches against descending
    result.sort(key=lambda x: x.matches_against, reverse=True)
    
    return result
