"""Match logging API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from backend.app.database import get_db
from backend.app.models import Match, Player, PairStats
from backend.app.schemas import MatchCreate, MatchResponse, MatchListResponse, MatchListItem, RatingChange
from backend.app import ranking

router = APIRouter()

def get_player_by_name(db: Session, name: str) -> Player:
    """Get player by name or raise 404"""
    player = db.query(Player).filter(Player.name == name).first()
    if not player:
        raise HTTPException(status_code=404, detail=f"Player '{name}' not found")
    return player

def update_pair_stats(
    db: Session,
    player1_id: int,
    player2_id: int,
    won: bool,
    goals_for: int,
    goals_against: int,
    played_at: datetime
):
    """Update stats for a player pair (canonical ordering: smaller ID first)"""
    p1, p2 = min(player1_id, player2_id), max(player1_id, player2_id)
    
    pair = db.query(PairStats).filter(
        PairStats.player1_id == p1,
        PairStats.player2_id == p2
    ).first()
    
    if not pair:
        pair = PairStats(
            player1_id=p1,
            player2_id=p2,
            matches_played=0,
            wins=0,
            goals_for=0,
            goals_against=0
        )
        db.add(pair)
    
    pair.matches_played += 1
    if won:
        pair.wins += 1
    pair.goals_for += goals_for
    pair.goals_against += goals_against
    pair.last_played = played_at

@router.post("/", response_model=MatchResponse)
async def log_match(match: MatchCreate, db: Session = Depends(get_db)):
    """
    Log a new 2v2 match
    
    Creates a match record, updates TrueSkill ratings, and tracks pair chemistry.
    """
    # Validate all players exist
    t1p1 = get_player_by_name(db, match.team1[0])
    t1p2 = get_player_by_name(db, match.team1[1])
    t2p1 = get_player_by_name(db, match.team2[0])
    t2p2 = get_player_by_name(db, match.team2[1])
    
    # Default played_at to now if not provided
    played_at = match.played_at or datetime.utcnow()
    
    # Create match record
    new_match = Match(
        played_at=played_at,
        team1_player1=t1p1.id,
        team1_player2=t1p2.id,
        team1_score=match.team1_score,
        team2_player1=t2p1.id,
        team2_player2=t2p2.id,
        team2_score=match.team2_score,
        logged_by=match.logged_by,
        is_deleted=False
    )
    
    db.add(new_match)
    db.flush()  # Get the match ID
    
    # Update pair stats
    team1_won = match.team1_score > match.team2_score
    team2_won = match.team2_score > match.team1_score
    
    update_pair_stats(db, t1p1.id, t1p2.id, team1_won, match.team1_score, match.team2_score, played_at)
    update_pair_stats(db, t2p1.id, t2p2.id, team2_won, match.team2_score, match.team1_score, played_at)
    
    # Update TrueSkill ratings
    rating_deltas = ranking.update_ratings(new_match, db)
    
    db.commit()
    db.refresh(new_match)
    
    # Build rating changes for response
    rating_changes = [
        RatingChange(
            player_name=t1p1.name,
            ordinal_delta=rating_deltas[t1p1.id]["ordinal_delta"],
            new_ordinal=rating_deltas[t1p1.id]["new_ordinal"]
        ),
        RatingChange(
            player_name=t1p2.name,
            ordinal_delta=rating_deltas[t1p2.id]["ordinal_delta"],
            new_ordinal=rating_deltas[t1p2.id]["new_ordinal"]
        ),
        RatingChange(
            player_name=t2p1.name,
            ordinal_delta=rating_deltas[t2p1.id]["ordinal_delta"],
            new_ordinal=rating_deltas[t2p1.id]["new_ordinal"]
        ),
        RatingChange(
            player_name=t2p2.name,
            ordinal_delta=rating_deltas[t2p2.id]["ordinal_delta"],
            new_ordinal=rating_deltas[t2p2.id]["new_ordinal"]
        ),
    ]
    
    # Build response
    response = MatchResponse(
        id=new_match.id,
        played_at=new_match.played_at,
        team1_player1=t1p1.name,
        team1_player2=t1p2.name,
        team1_score=new_match.team1_score,
        team2_player1=t2p1.name,
        team2_player2=t2p2.name,
        team2_score=new_match.team2_score,
        logged_by=new_match.logged_by,
        created_at=new_match.created_at,
        rating_changes=rating_changes
    )
    
    return response

@router.get("/", response_model=MatchListResponse)
async def list_matches(
    player_name: Optional[str] = Query(None, description="Filter by player name"),
    date: Optional[datetime] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db)
):
    """
    List matches with optional filters
    
    Returns matches in reverse chronological order (newest first).
    """
    query = db.query(Match).filter(Match.is_deleted == False)
    
    # Filter by player
    if player_name:
        player = get_player_by_name(db, player_name)
        query = query.filter(
            (Match.team1_player1 == player.id) |
            (Match.team1_player2 == player.id) |
            (Match.team2_player1 == player.id) |
            (Match.team2_player2 == player.id)
        )
    
    # Filter by date
    if date:
        # Match any time on that day
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        query = query.filter(Match.played_at >= start, Match.played_at <= end)
    
    # Count total
    total = query.count()
    
    # Paginate
    matches = query.order_by(Match.played_at.desc()).offset(offset).limit(limit).all()
    
    # Build response
    items = []
    for match in matches:
        # Get player names
        t1p1 = db.query(Player).filter(Player.id == match.team1_player1).first()
        t1p2 = db.query(Player).filter(Player.id == match.team1_player2).first()
        t2p1 = db.query(Player).filter(Player.id == match.team2_player1).first()
        t2p2 = db.query(Player).filter(Player.id == match.team2_player2).first()
        
        winner = "draw"
        if match.team1_score > match.team2_score:
            winner = "team1"
        elif match.team2_score > match.team1_score:
            winner = "team2"
        
        items.append(MatchListItem(
            id=match.id,
            played_at=match.played_at,
            team1_player1=t1p1.name,
            team1_player2=t1p2.name,
            team1_score=match.team1_score,
            team2_player1=t2p1.name,
            team2_player2=t2p2.name,
            team2_score=match.team2_score,
            winner=winner
        ))
    
    return MatchListResponse(
        matches=items,
        total=total,
        limit=limit,
        offset=offset
    )

@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(match_id: int, db: Session = Depends(get_db)):
    """Get a single match by ID"""
    match = db.query(Match).filter(Match.id == match_id, Match.is_deleted == False).first()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Get player names
    t1p1 = db.query(Player).filter(Player.id == match.team1_player1).first()
    t1p2 = db.query(Player).filter(Player.id == match.team1_player2).first()
    t2p1 = db.query(Player).filter(Player.id == match.team2_player1).first()
    t2p2 = db.query(Player).filter(Player.id == match.team2_player2).first()
    
    return MatchResponse(
        id=match.id,
        played_at=match.played_at,
        team1_player1=t1p1.name,
        team1_player2=t1p2.name,
        team1_score=match.team1_score,
        team2_player1=t2p1.name,
        team2_player2=t2p2.name,
        team2_score=match.team2_score,
        logged_by=match.logged_by,
        created_at=match.created_at,
        rating_changes=[]  # Will be populated by TrueSkill in #5
    )

@router.delete("/{match_id}")
async def delete_match(match_id: int, db: Session = Depends(get_db)):
    """
    Soft-delete a match
    
    Sets is_deleted=True instead of actually removing the record.
    This preserves historical data and allows for rating recalculation.
    All ratings are recalculated from scratch after deletion.
    """
    match = db.query(Match).filter(Match.id == match_id).first()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if match.is_deleted:
        raise HTTPException(status_code=400, detail="Match already deleted")
    
    match.is_deleted = True
    db.commit()
    
    # Recalculate all ratings from scratch
    ranking.recalculate_all_ratings(db)
    
    return {"success": True, "message": f"Match {match_id} soft-deleted and ratings recalculated"}
