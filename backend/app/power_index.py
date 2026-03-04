"""
Weekly Power Index (WPI) calculation engine.

Composite ranking system combining:
- Skill Score (40%): TrueSkill ordinal normalized
- Form Score (35%): Recent performance (last 7-14 days)
- Impact Score (25%): Goal contribution and match impact
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from backend.app.models import Player, Match, RatingHistory, WeeklyRanking


def get_week_start(date: datetime = None) -> datetime:
    """Get Monday 00:00:00 of the week containing the given date."""
    if date is None:
        date = datetime.utcnow()
    
    # Get to Monday
    days_since_monday = date.weekday()
    monday = date - timedelta(days=days_since_monday)
    
    # Set to 00:00:00
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def calculate_skill_score(player_id: int, db: Session) -> float:
    """
    Calculate skill score (0-100) based on TrueSkill ordinal.
    
    Normalizes ordinal to 0-100 scale based on all active players.
    """
    # Get latest rating
    latest_rating = (
        db.query(RatingHistory)
        .filter(RatingHistory.player_id == player_id)
        .order_by(RatingHistory.created_at.desc())
        .first()
    )
    
    if not latest_rating:
        return 50.0  # Default for new players
    
    # Get all players' latest ratings for normalization
    all_players = db.query(Player).all()
    ordinals = []
    
    for player in all_players:
        lr = (
            db.query(RatingHistory)
            .filter(RatingHistory.player_id == player.id)
            .order_by(RatingHistory.created_at.desc())
            .first()
        )
        if lr:
            ordinals.append(lr.ordinal)
    
    if not ordinals:
        return 50.0
    
    min_ordinal = min(ordinals)
    max_ordinal = max(ordinals)
    
    # Normalize to 0-100 (with floor of 10 to avoid zeros)
    if max_ordinal == min_ordinal:
        return 50.0
    
    normalized = ((latest_rating.ordinal - min_ordinal) / (max_ordinal - min_ordinal)) * 90 + 10
    return min(100.0, max(0.0, normalized))


def calculate_form_score(player_id: int, db: Session, days: int = 14) -> float:
    """
    Calculate form score (0-100) based on recent performance.
    
    Looks at last N days of matches and weights recent matches higher.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get recent matches
    recent_matches = (
        db.query(Match)
        .filter(
            and_(
                Match.is_deleted == False,
                Match.played_at >= cutoff_date,
                ((Match.team1_player1 == player_id) | 
                 (Match.team1_player2 == player_id) |
                 (Match.team2_player1 == player_id) | 
                 (Match.team2_player2 == player_id))
            )
        )
        .order_by(Match.played_at.desc())
        .all()
    )
    
    if not recent_matches:
        return 50.0  # Default for inactive players
    
    # Calculate weighted win rate (recent matches weighted more)
    total_weight = 0.0
    weighted_points = 0.0
    
    for idx, match in enumerate(recent_matches):
        # Weight decreases linearly from 1.0 (most recent) to 0.5 (oldest)
        weight = 1.0 - (idx / len(recent_matches)) * 0.5
        
        # Determine if player won
        on_team1 = player_id in [match.team1_player1, match.team1_player2]
        
        if match.team1_score > match.team2_score:
            points = 1.0 if on_team1 else 0.0
        elif match.team2_score > match.team1_score:
            points = 0.0 if on_team1 else 1.0
        else:
            points = 0.5  # Draw
        
        weighted_points += points * weight
        total_weight += weight
    
    # Normalize to 0-100
    if total_weight == 0:
        return 50.0
    
    form_percentage = (weighted_points / total_weight) * 100
    return min(100.0, max(0.0, form_percentage))


def calculate_impact_score(player_id: int, db: Session, days: int = 14) -> float:
    """
    Calculate impact score (0-100) based on goal contribution.
    
    Factors:
    - Goals scored (team score when winning)
    - Margin of victory/defeat
    - Decisive matches (close scores)
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get recent matches
    recent_matches = (
        db.query(Match)
        .filter(
            and_(
                Match.is_deleted == False,
                Match.played_at >= cutoff_date,
                ((Match.team1_player1 == player_id) | 
                 (Match.team1_player2 == player_id) |
                 (Match.team2_player1 == player_id) | 
                 (Match.team2_player2 == player_id))
            )
        )
        .all()
    )
    
    if not recent_matches:
        return 50.0
    
    total_goals_for = 0
    total_goals_against = 0
    decisive_wins = 0  # Wins by 1-2 goals
    
    for match in recent_matches:
        on_team1 = player_id in [match.team1_player1, match.team1_player2]
        
        if on_team1:
            total_goals_for += match.team1_score
            total_goals_against += match.team2_score
            if 0 < match.team1_score - match.team2_score <= 2:
                decisive_wins += 1
        else:
            total_goals_for += match.team2_score
            total_goals_against += match.team1_score
            if 0 < match.team2_score - match.team1_score <= 2:
                decisive_wins += 1
    
    # Calculate components
    avg_goals_for = total_goals_for / len(recent_matches)
    avg_goals_against = total_goals_against / len(recent_matches)
    goal_diff = avg_goals_for - avg_goals_against
    decisive_ratio = decisive_wins / len(recent_matches)
    
    # Normalize components to 0-100 scale
    # Average goals for: 0-5 -> 0-50 points
    goals_component = min(50.0, avg_goals_for * 10)
    
    # Goal difference: -5 to +5 -> 0-30 points
    goal_diff_component = min(30.0, max(0.0, (goal_diff + 5) * 3))
    
    # Decisive wins: 0-100% -> 0-20 points
    decisive_component = decisive_ratio * 20
    
    impact = goals_component + goal_diff_component + decisive_component
    return min(100.0, max(0.0, impact))


def calculate_power_index(
    skill_score: float,
    form_score: float,
    impact_score: float,
    skill_weight: float = 0.40,
    form_weight: float = 0.35,
    impact_weight: float = 0.25
) -> float:
    """
    Calculate composite Power Index from component scores.
    
    Default weights:
    - Skill: 40% (TrueSkill is still primary indicator)
    - Form: 35% (Recent performance matters)
    - Impact: 25% (Goals and decisiveness)
    """
    return (skill_score * skill_weight + 
            form_score * form_weight + 
            impact_score * impact_weight)


def generate_weekly_rankings(db: Session, week_start: datetime = None) -> List[Dict]:
    """
    Generate Weekly Power Index rankings for all active players.
    
    Returns list of player rankings with component scores.
    """
    if week_start is None:
        week_start = get_week_start()
    
    all_players = db.query(Player).all()
    rankings = []
    
    for player in all_players:
        # Skip players with no rating history
        latest_rating = (
            db.query(RatingHistory)
            .filter(RatingHistory.player_id == player.id)
            .order_by(RatingHistory.created_at.desc())
            .first()
        )
        
        if not latest_rating:
            continue
        
        # Calculate component scores
        skill = calculate_skill_score(player.id, db)
        form = calculate_form_score(player.id, db, days=14)
        impact = calculate_impact_score(player.id, db, days=14)
        
        # Calculate Power Index
        power_index = calculate_power_index(skill, form, impact)
        
        # Get match stats for the week
        week_end = week_start + timedelta(days=7)
        week_matches = (
            db.query(Match)
            .filter(
                and_(
                    Match.is_deleted == False,
                    Match.played_at >= week_start,
                    Match.played_at < week_end,
                    ((Match.team1_player1 == player.id) | 
                     (Match.team1_player2 == player.id) |
                     (Match.team2_player1 == player.id) | 
                     (Match.team2_player2 == player.id))
                )
            )
            .all()
        )
        
        wins = 0
        losses = 0
        draws = 0
        
        for match in week_matches:
            on_team1 = player.id in [match.team1_player1, match.team1_player2]
            
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
        
        rankings.append({
            "player_id": player.id,
            "player_name": player.name,
            "power_index": power_index,
            "skill_score": skill,
            "form_score": form,
            "impact_score": impact,
            "matches_played": len(week_matches),
            "wins": wins,
            "losses": losses,
            "draws": draws,
        })
    
    # Sort by Power Index descending
    rankings.sort(key=lambda x: x["power_index"], reverse=True)
    
    # Assign ranks
    for rank, player in enumerate(rankings, start=1):
        player["rank"] = rank
    
    return rankings


def save_weekly_rankings(db: Session, week_start: datetime = None):
    """
    Calculate and save weekly rankings to database.
    
    This should be run via cron job every Monday.
    """
    if week_start is None:
        week_start = get_week_start()
    
    rankings = generate_weekly_rankings(db, week_start)
    
    for ranking in rankings:
        # Check if ranking already exists for this week
        existing = (
            db.query(WeeklyRanking)
            .filter(
                and_(
                    WeeklyRanking.player_id == ranking["player_id"],
                    WeeklyRanking.week_start == week_start
                )
            )
            .first()
        )
        
        if existing:
            # Update existing
            existing.skill_score = ranking["skill_score"]
            existing.form_score = ranking["form_score"]
            existing.impact_score = ranking["impact_score"]
            existing.power_index = ranking["power_index"]
            existing.rank = ranking["rank"]
            existing.matches_played = ranking["matches_played"]
            existing.wins = ranking["wins"]
            existing.draws = ranking["draws"]
            existing.losses = ranking["losses"]
        else:
            # Create new
            new_ranking = WeeklyRanking(
                player_id=ranking["player_id"],
                week_start=week_start,
                skill_score=ranking["skill_score"],
                form_score=ranking["form_score"],
                impact_score=ranking["impact_score"],
                power_index=ranking["power_index"],
                rank=ranking["rank"],
                matches_played=ranking["matches_played"],
                wins=ranking["wins"],
                draws=ranking["draws"],
                losses=ranking["losses"],
            )
            db.add(new_ranking)
    
    db.commit()
