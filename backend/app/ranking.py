"""TrueSkill rating calculation engine using openskill"""
from typing import List, Tuple, Any
from sqlalchemy.orm import Session
from openskill.models import PlackettLuce

from backend.app.models import Match, Player, RatingHistory
from backend.app.config import settings


# Initialize the rating model (patent-free TrueSkill equivalent)
model = PlackettLuce(
    mu=settings.TRUESKILL_MU,
    sigma=settings.TRUESKILL_SIGMA,
    beta=settings.TRUESKILL_BETA,
    tau=settings.TRUESKILL_TAU,
)


def get_current_rating(player_id: int, db: Session) -> Any:
    """Get a player's current rating or return defaults for new players"""
    latest = (
        db.query(RatingHistory)
        .filter(RatingHistory.player_id == player_id)
        .order_by(RatingHistory.created_at.desc())
        .first()
    )
    
    if latest:
        return model.rating(mu=latest.mu, sigma=latest.sigma)
    else:
        # New player defaults
        return model.rating(mu=settings.TRUESKILL_MU, sigma=settings.TRUESKILL_SIGMA)


def update_ratings(match: Match, db: Session) -> dict:
    """
    Update player ratings based on a match result.
    
    Args:
        match: Match object with team1/team2 player IDs and winner
        db: Database session
    
    Returns:
        dict: Rating deltas for all 4 players (for API response)
    """
    # Load current ratings for all 4 players
    team1_ratings = [
        get_current_rating(match.team1_player1_id, db),
        get_current_rating(match.team1_player2_id, db),
    ]
    team2_ratings = [
        get_current_rating(match.team2_player1_id, db),
        get_current_rating(match.team2_player2_id, db),
    ]
    
    # Determine ranks based on match scores
    if match.team1_score > match.team2_score:
        ranks = [1, 2]  # team1 won
    elif match.team2_score > match.team1_score:
        ranks = [2, 1]  # team2 won
    else:
        ranks = [1, 1]  # draw
    
    # Calculate new ratings
    [[new_t1_p1, new_t1_p2], [new_t2_p1, new_t2_p2]] = model.rate(
        [team1_ratings, team2_ratings],
        ranks=ranks
    )
    
    # Calculate ordinals (conservative estimate: mu - 3*sigma)
    ordinal_t1_p1 = new_t1_p1.mu - 3 * new_t1_p1.sigma
    ordinal_t1_p2 = new_t1_p2.mu - 3 * new_t1_p2.sigma
    ordinal_t2_p1 = new_t2_p1.mu - 3 * new_t2_p1.sigma
    ordinal_t2_p2 = new_t2_p2.mu - 3 * new_t2_p2.sigma
    
    # Save new RatingHistory entries
    player_ratings = [
        (match.team1_player1_id, new_t1_p1, ordinal_t1_p1),
        (match.team1_player2_id, new_t1_p2, ordinal_t1_p2),
        (match.team2_player1_id, new_t2_p1, ordinal_t2_p1),
        (match.team2_player2_id, new_t2_p2, ordinal_t2_p2),
    ]
    
    deltas = {}
    for player_id, new_rating, ordinal in player_ratings:
        # Get old rating for delta calculation
        old_rating = get_current_rating(player_id, db)
        old_ordinal = old_rating.mu - 3 * old_rating.sigma
        
        # Create rating history entry
        history = RatingHistory(
            player_id=player_id,
            match_id=match.id,
            mu=new_rating.mu,
            sigma=new_rating.sigma,
            ordinal=ordinal,
        )
        db.add(history)
        
        # Track deltas for response
        deltas[player_id] = {
            "mu_delta": new_rating.mu - old_rating.mu,
            "sigma_delta": new_rating.sigma - old_rating.sigma,
            "ordinal_delta": ordinal - old_ordinal,
            "new_ordinal": ordinal,
        }
    
    db.commit()
    return deltas


def recalculate_all_ratings(db: Session):
    """
    Recalculate all ratings from scratch by replaying all matches.
    
    Used after a match is soft-deleted or corrected.
    Wipes all RatingHistory and rebuilds from non-deleted matches in chronological order.
    """
    # Delete all existing rating history
    db.query(RatingHistory).delete()
    db.commit()
    
    # Get all non-deleted matches in chronological order
    matches = (
        db.query(Match)
        .filter(Match.deleted_at.is_(None))
        .order_by(Match.played_at.asc())
        .all()
    )
    
    # Replay each match
    for match in matches:
        update_ratings(match, db)


def predict_win_probability(
    team1_player1_id: int,
    team1_player2_id: int,
    team2_player1_id: int,
    team2_player2_id: int,
    db: Session
) -> float:
    """
    Predict the probability of team1 winning against team2.
    
    Returns:
        float: Probability (0.0 to 1.0) that team1 wins
    """
    team1_ratings = [
        get_current_rating(team1_player1_id, db),
        get_current_rating(team1_player2_id, db),
    ]
    team2_ratings = [
        get_current_rating(team2_player1_id, db),
        get_current_rating(team2_player2_id, db),
    ]
    
    # openskill's predict_win returns list of probabilities for each team
    probabilities = model.predict_win([team1_ratings, team2_ratings])
    return probabilities[0]  # team1's probability
