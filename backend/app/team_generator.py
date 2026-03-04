"""
Balanced Team Generator

Suggests fair 2v2 team matchups from a pool of players.
Uses TrueSkill ratings to create balanced teams.
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Tuple
from itertools import combinations

from backend.app.models import Player, RatingHistory
from backend.app.ranking import predict_win_probability


def get_player_ordinal(player_id: int, db: Session) -> float:
    """Get player's current rating ordinal."""
    latest_rating = (
        db.query(RatingHistory)
        .filter(RatingHistory.player_id == player_id)
        .order_by(RatingHistory.created_at.desc())
        .first()
    )
    
    if latest_rating:
        return latest_rating.ordinal
    else:
        return 0.0  # Default for new players


def calculate_matchup_balance(
    team1_player1_id: int,
    team1_player2_id: int,
    team2_player1_id: int,
    team2_player2_id: int,
    db: Session
) -> Dict:
    """
    Calculate balance score for a team matchup.
    
    Returns dict with:
    - team1_strength: Average ordinal of team 1
    - team2_strength: Average ordinal of team 2
    - balance_score: 100 - abs(difference) (higher = more balanced)
    - predicted_win_prob: Probability team 1 wins (0.0-1.0)
    """
    # Get ordinals
    t1p1_ord = get_player_ordinal(team1_player1_id, db)
    t1p2_ord = get_player_ordinal(team1_player2_id, db)
    t2p1_ord = get_player_ordinal(team2_player1_id, db)
    t2p2_ord = get_player_ordinal(team2_player2_id, db)
    
    # Calculate team strengths (average)
    team1_strength = (t1p1_ord + t1p2_ord) / 2
    team2_strength = (t2p1_ord + t2p2_ord) / 2
    
    # Balance score: closer to 0 difference = higher score
    difference = abs(team1_strength - team2_strength)
    balance_score = max(0, 100 - difference)
    
    # Predict win probability using TrueSkill
    try:
        win_prob = predict_win_probability(
            team1_player1_id,
            team1_player2_id,
            team2_player1_id,
            team2_player2_id,
            db
        )
    except:
        # Fallback if prediction fails
        win_prob = 0.5
    
    return {
        "team1_strength": team1_strength,
        "team2_strength": team2_strength,
        "balance_score": balance_score,
        "predicted_win_prob": win_prob,
    }


def generate_rotation_schedule(player_ids: List[int], db: Session) -> Dict:
    """
    Generate rotation schedule for 5-6 players.
    
    For 5 players: Creates games where one sits out each round (4 games total, each player sits once)
    For 6 players: Creates tournament bracket (3 games, everyone plays)
    
    Returns schedule with game order and balanced matchups.
    """
    if len(player_ids) not in [5, 6]:
        raise ValueError("Rotation schedule requires 5 or 6 players")
    
    players = {
        pid: db.query(Player).filter(Player.id == pid).first()
        for pid in player_ids
    }
    
    if len(player_ids) == 5:
        # 5-player rotation: Each player sits out one game
        games = []
        
        for sitting_out_id in player_ids:
            # Get the 4 playing players
            playing = [pid for pid in player_ids if pid != sitting_out_id]
            
            # Generate best matchup for these 4 players
            matchup = generate_balanced_teams(playing, db, top_n=1)[0]
            
            games.append({
                "game_number": len(games) + 1,
                "matchup": matchup,
                "sitting_out": {
                    "id": sitting_out_id,
                    "name": players[sitting_out_id].name
                }
            })
        
        return {
            "type": "rotation_5",
            "total_games": len(games),
            "description": "5-player rotation: Each player sits out one game",
            "games": games
        }
    
    else:  # 6 players
        # 6-player tournament: 3 games with different matchups
        # Game 1: Best balanced from all 6
        # Game 2: Second best
        # Game 3: Third best (or rematch of closest game)
        
        # Generate all possible pairs
        all_pairs = list(combinations(player_ids, 2))
        
        # Try different matchup combinations
        all_matchups = []
        seen = set()
        
        for team1_pair in all_pairs:
            remaining = [p for p in player_ids if p not in team1_pair]
            for team2_pair in combinations(remaining, 2):
                team3_pair = tuple(sorted([p for p in remaining if p not in team2_pair]))
                
                # Create matchup key
                matchup_key = tuple(sorted([team1_pair, team2_pair, team3_pair]))
                if matchup_key in seen:
                    continue
                seen.add(matchup_key)
                
                # Evaluate balance for each game
                game1_balance = calculate_matchup_balance(*team1_pair, *team2_pair, db)
                game2_balance = calculate_matchup_balance(*team1_pair, *team3_pair, db)
                game3_balance = calculate_matchup_balance(*team2_pair, *team3_pair, db)
                
                avg_balance = (game1_balance["balance_score"] + 
                              game2_balance["balance_score"] + 
                              game3_balance["balance_score"]) / 3
                
                all_matchups.append({
                    "teams": [team1_pair, team2_pair, team3_pair],
                    "avg_balance": avg_balance,
                    "game_balances": [game1_balance, game2_balance, game3_balance]
                })
        
        # Pick best overall combination
        all_matchups.sort(key=lambda x: x["avg_balance"], reverse=True)
        best = all_matchups[0]
        
        # Format games
        games = []
        matchup_pairs = [
            (0, 1),  # Team 1 vs Team 2
            (0, 2),  # Team 1 vs Team 3
            (1, 2),  # Team 2 vs Team 3
        ]
        
        for idx, (t1_idx, t2_idx) in enumerate(matchup_pairs):
            t1 = best["teams"][t1_idx]
            t2 = best["teams"][t2_idx]
            balance = best["game_balances"][idx]
            
            games.append({
                "game_number": idx + 1,
                "matchup": {
                    "team1": {
                        "player1_id": t1[0],
                        "player1_name": players[t1[0]].name,
                        "player2_id": t1[1],
                        "player2_name": players[t1[1]].name,
                        "strength": balance["team1_strength"],
                    },
                    "team2": {
                        "player1_id": t2[0],
                        "player1_name": players[t2[0]].name,
                        "player2_id": t2[1],
                        "player2_name": players[t2[1]].name,
                        "strength": balance["team2_strength"],
                    },
                    "balance_score": balance["balance_score"],
                    "predicted_win_prob": balance["predicted_win_prob"],
                    "fairness": "Excellent" if balance["balance_score"] >= 90 else
                               "Good" if balance["balance_score"] >= 70 else
                               "Fair" if balance["balance_score"] >= 50 else
                               "Unbalanced"
                },
                "sitting_out": None
            })
        
        return {
            "type": "tournament_6",
            "total_games": len(games),
            "description": "6-player round-robin: 3 games, everyone plays twice",
            "games": games,
            "avg_balance": best["avg_balance"]
        }


def generate_balanced_teams(player_ids: List[int], db: Session, top_n: int = 5) -> List[Dict]:
    """
    Generate balanced 2v2 team matchups from a list of players.
    
    Args:
        player_ids: List of player IDs (4 for matchups, 5-6 for rotation)
        db: Database session
        top_n: Number of top matchups to return
    
    Returns:
        List of matchup dictionaries sorted by balance score.
        OR rotation schedule dict for 5-6 players.
    """
    if len(player_ids) in [5, 6]:
        return generate_rotation_schedule(player_ids, db)
    
    if len(player_ids) != 4:
        raise ValueError("Requires 4 players for matchups or 5-6 for rotation")
    
    # Get player details
    players = {
        pid: db.query(Player).filter(Player.id == pid).first()
        for pid in player_ids
    }
    
    # Generate all possible team combinations
    # For 4 players (A, B, C, D), possible matchups are:
    # AB vs CD, AC vs BD, AD vs BC
    matchups = []
    
    # Get all 2-player combinations
    all_pairs = list(combinations(player_ids, 2))
    
    # For each pair that could be team1, the remaining two are team2
    seen = set()
    for team1_pair in all_pairs:
        team2_pair = tuple(sorted([p for p in player_ids if p not in team1_pair]))
        
        # Avoid duplicates (AB vs CD is same as CD vs AB)
        matchup_key = tuple(sorted([team1_pair, team2_pair]))
        if matchup_key in seen:
            continue
        seen.add(matchup_key)
        
        t1p1, t1p2 = team1_pair
        t2p1, t2p2 = team2_pair
        
        # Calculate balance
        balance = calculate_matchup_balance(t1p1, t1p2, t2p1, t2p2, db)
        
        matchups.append({
            "team1": {
                "player1_id": t1p1,
                "player1_name": players[t1p1].name,
                "player2_id": t1p2,
                "player2_name": players[t1p2].name,
                "strength": balance["team1_strength"],
            },
            "team2": {
                "player1_id": t2p1,
                "player1_name": players[t2p1].name,
                "player2_id": t2p2,
                "player2_name": players[t2p2].name,
                "strength": balance["team2_strength"],
            },
            "balance_score": balance["balance_score"],
            "predicted_win_prob": balance["predicted_win_prob"],
            "fairness": "Excellent" if balance["balance_score"] >= 90 else
                       "Good" if balance["balance_score"] >= 70 else
                       "Fair" if balance["balance_score"] >= 50 else
                       "Unbalanced"
        })
    
    # Sort by balance score (most balanced first)
    matchups.sort(key=lambda x: x["balance_score"], reverse=True)
    
    return matchups[:top_n]
