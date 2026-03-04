"""
Weekly Awards calculation engine.

Fun achievements based on recent performance:
- MVP: Best power index this week
- On Fire: Longest active win streak
- Comeback King: Best goal differential in losses turned to wins
- Clutch Player: Most decisive wins (1-goal margin)
- Goal Machine: Most goals scored
- Wall: Fewest goals conceded
- Underdog: Biggest upsets (wins against higher-rated opponents)
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from backend.app.models import Player, Match, RatingHistory


def get_mvp(db: Session, days: int = 7) -> Optional[Dict]:
    """
    Most Valuable Player: Best overall performance this week.
    
    Based on highest power index + most wins.
    """
    from backend.app.power_index import generate_weekly_rankings
    
    rankings = generate_weekly_rankings(db)
    
    if not rankings:
        return None
    
    # Filter to players with at least 3 matches in period
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    active_players = []
    
    for ranking in rankings:
        # Count recent matches
        recent_matches = (
            db.query(Match)
            .filter(
                and_(
                    Match.is_deleted == False,
                    Match.played_at >= cutoff_date,
                    ((Match.team1_player1 == ranking["player_id"]) | 
                     (Match.team1_player2 == ranking["player_id"]) |
                     (Match.team2_player1 == ranking["player_id"]) | 
                     (Match.team2_player2 == ranking["player_id"]))
                )
            )
            .count()
        )
        
        if recent_matches >= 3:
            active_players.append(ranking)
    
    if not active_players:
        return None
    
    # Sort by power index
    mvp = max(active_players, key=lambda x: x["power_index"])
    
    return {
        "award": "🏆 MVP",
        "player_id": mvp["player_id"],
        "player_name": mvp["player_name"],
        "description": f"Highest Power Index ({mvp['power_index']:.1f})",
        "stat": f"{mvp['power_index']:.1f} PI",
    }


def get_on_fire(db: Session) -> Optional[Dict]:
    """
    On Fire: Longest active win streak.
    """
    all_players = db.query(Player).all()
    
    best_streak_player = None
    best_streak_length = 0
    
    for player in all_players:
        # Get recent matches in reverse chronological order
        recent_matches = (
            db.query(Match)
            .filter(
                and_(
                    Match.is_deleted == False,
                    ((Match.team1_player1 == player.id) | 
                     (Match.team1_player2 == player.id) |
                     (Match.team2_player1 == player.id) | 
                     (Match.team2_player2 == player.id))
                )
            )
            .order_by(Match.played_at.desc())
            .limit(20)
            .all()
        )
        
        # Count consecutive wins from most recent
        streak = 0
        for match in recent_matches:
            on_team1 = player.id in [match.team1_player1, match.team1_player2]
            
            if match.team1_score > match.team2_score and on_team1:
                streak += 1
            elif match.team2_score > match.team1_score and not on_team1:
                streak += 1
            else:
                break  # Streak ended
        
        if streak > best_streak_length and streak >= 3:
            best_streak_length = streak
            best_streak_player = player
    
    if not best_streak_player:
        return None
    
    return {
        "award": "🔥 On Fire",
        "player_id": best_streak_player.id,
        "player_name": best_streak_player.name,
        "description": f"{best_streak_length}-game win streak",
        "stat": f"{best_streak_length}W",
    }


def get_clutch_player(db: Session, days: int = 14) -> Optional[Dict]:
    """
    Clutch Player: Most wins by 1-goal margin.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    all_players = db.query(Player).all()
    
    best_player = None
    most_clutch_wins = 0
    
    for player in all_players:
        recent_matches = (
            db.query(Match)
            .filter(
                and_(
                    Match.is_deleted == False,
                    Match.played_at >= cutoff_date,
                    ((Match.team1_player1 == player.id) | 
                     (Match.team1_player2 == player.id) |
                     (Match.team2_player1 == player.id) | 
                     (Match.team2_player2 == player.id))
                )
            )
            .all()
        )
        
        clutch_wins = 0
        for match in recent_matches:
            on_team1 = player.id in [match.team1_player1, match.team1_player2]
            margin = abs(match.team1_score - match.team2_score)
            
            # Win by exactly 1 goal
            if margin == 1:
                if (match.team1_score > match.team2_score and on_team1) or \
                   (match.team2_score > match.team1_score and not on_team1):
                    clutch_wins += 1
        
        if clutch_wins > most_clutch_wins and clutch_wins >= 2:
            most_clutch_wins = clutch_wins
            best_player = player
    
    if not best_player:
        return None
    
    return {
        "award": "💪 Clutch Player",
        "player_id": best_player.id,
        "player_name": best_player.name,
        "description": f"{most_clutch_wins} wins by 1-goal margin",
        "stat": f"{most_clutch_wins} clutch",
    }


def get_goal_machine(db: Session, days: int = 14) -> Optional[Dict]:
    """
    Goal Machine: Most goals scored (team total when playing).
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    all_players = db.query(Player).all()
    
    best_player = None
    most_goals = 0
    
    for player in all_players:
        recent_matches = (
            db.query(Match)
            .filter(
                and_(
                    Match.is_deleted == False,
                    Match.played_at >= cutoff_date,
                    ((Match.team1_player1 == player.id) | 
                     (Match.team1_player2 == player.id) |
                     (Match.team2_player1 == player.id) | 
                     (Match.team2_player2 == player.id))
                )
            )
            .all()
        )
        
        total_goals = 0
        for match in recent_matches:
            on_team1 = player.id in [match.team1_player1, match.team1_player2]
            total_goals += match.team1_score if on_team1 else match.team2_score
        
        if total_goals > most_goals and len(recent_matches) >= 3:
            most_goals = total_goals
            best_player = player
    
    if not best_player:
        return None
    
    return {
        "award": "⚽ Goal Machine",
        "player_id": best_player.id,
        "player_name": best_player.name,
        "description": f"{most_goals} goals in {len(recent_matches)} matches",
        "stat": f"{most_goals}G",
    }


def get_defensive_wall(db: Session, days: int = 14) -> Optional[Dict]:
    """
    The Wall: Fewest goals conceded per match (min 3 matches).
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    all_players = db.query(Player).all()
    
    best_player = None
    best_avg = float('inf')
    
    for player in all_players:
        recent_matches = (
            db.query(Match)
            .filter(
                and_(
                    Match.is_deleted == False,
                    Match.played_at >= cutoff_date,
                    ((Match.team1_player1 == player.id) | 
                     (Match.team1_player2 == player.id) |
                     (Match.team2_player1 == player.id) | 
                     (Match.team2_player2 == player.id))
                )
            )
            .all()
        )
        
        if len(recent_matches) < 3:
            continue
        
        total_conceded = 0
        for match in recent_matches:
            on_team1 = player.id in [match.team1_player1, match.team1_player2]
            total_conceded += match.team2_score if on_team1 else match.team1_score
        
        avg_conceded = total_conceded / len(recent_matches)
        
        if avg_conceded < best_avg:
            best_avg = avg_conceded
            best_player = player
    
    if not best_player:
        return None
    
    return {
        "award": "🛡️ The Wall",
        "player_id": best_player.id,
        "player_name": best_player.name,
        "description": f"Only {best_avg:.1f} goals conceded per match",
        "stat": f"{best_avg:.1f} GA/M",
    }


def get_comeback_king(db: Session, days: int = 14) -> Optional[Dict]:
    """
    Comeback King: Player with best recovery from losses.
    Measures: wins after a loss.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    all_players = db.query(Player).all()
    
    best_player = None
    most_comebacks = 0
    
    for player in all_players:
        recent_matches = (
            db.query(Match)
            .filter(
                and_(
                    Match.is_deleted == False,
                    Match.played_at >= cutoff_date,
                    ((Match.team1_player1 == player.id) | 
                     (Match.team1_player2 == player.id) |
                     (Match.team2_player1 == player.id) | 
                     (Match.team2_player2 == player.id))
                )
            )
            .order_by(Match.played_at.asc())
            .all()
        )
        
        comebacks = 0
        previous_was_loss = False
        
        for match in recent_matches:
            on_team1 = player.id in [match.team1_player1, match.team1_player2]
            
            # Check if won
            won = (match.team1_score > match.team2_score and on_team1) or \
                  (match.team2_score > match.team1_score and not on_team1)
            
            if won and previous_was_loss:
                comebacks += 1
            
            # Update previous state
            lost = (match.team1_score > match.team2_score and not on_team1) or \
                   (match.team2_score > match.team1_score and on_team1)
            previous_was_loss = lost
        
        if comebacks > most_comebacks and comebacks >= 2:
            most_comebacks = comebacks
            best_player = player
    
    if not best_player:
        return None
    
    return {
        "award": "👑 Comeback King",
        "player_id": best_player.id,
        "player_name": best_player.name,
        "description": f"{most_comebacks} bouncebacks after losses",
        "stat": f"{most_comebacks} CB",
    }


def get_all_awards(db: Session, days: int = 7) -> List[Dict]:
    """
    Get all weekly awards.
    
    Returns list of award dictionaries (empty list if none awarded).
    """
    awards = []
    
    # Calculate each award
    award_functions = [
        get_mvp,
        get_on_fire,
        get_clutch_player,
        get_goal_machine,
        get_defensive_wall,
        get_comeback_king,
    ]
    
    for func in award_functions:
        try:
            award = func(db, days) if func != get_on_fire else func(db)
            if award:
                awards.append(award)
        except Exception as e:
            # Log error but continue with other awards
            print(f"Error calculating award {func.__name__}: {e}")
    
    return awards
