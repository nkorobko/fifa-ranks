"""Unit tests for TrueSkill ranking engine"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from openskill import Rating

from backend.app.models import Base, Player, Match, RatingHistory
from backend.app.ranking import (
    get_current_rating,
    update_ratings,
    recalculate_all_ratings,
    predict_win_probability,
)
from backend.app.config import settings


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db() -> Session:
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def players(db: Session):
    """Create 4 test players"""
    players = [
        Player(id=1, name="Alice", telegram_id=1001, telegram_username="alice"),
        Player(id=2, name="Bob", telegram_id=1002, telegram_username="bob"),
        Player(id=3, name="Charlie", telegram_id=1003, telegram_username="charlie"),
        Player(id=4, name="Diana", telegram_id=1004, telegram_username="diana"),
    ]
    for player in players:
        db.add(player)
    db.commit()
    return players


class TestGetCurrentRating:
    """Tests for get_current_rating function"""
    
    def test_new_player_returns_defaults(self, db: Session, players):
        """New players should get default mu/sigma values"""
        rating = get_current_rating(1, db)
        assert rating.mu == settings.TRUESKILL_MU
        assert rating.sigma == settings.TRUESKILL_SIGMA
    
    def test_existing_player_returns_latest_rating(self, db: Session, players):
        """Should return most recent rating for players with history"""
        # Create rating history
        history = RatingHistory(
            player_id=1,
            match_id=None,
            mu=27.5,
            sigma=7.5,
            ordinal=5.0,
        )
        db.add(history)
        db.commit()
        
        rating = get_current_rating(1, db)
        assert rating.mu == 27.5
        assert rating.sigma == 7.5


class TestUpdateRatings:
    """Tests for update_ratings function"""
    
    def test_winner_ordinal_increases(self, db: Session, players):
        """Winning team should see ordinal increase"""
        # Create a match where team1 wins
        match = Match(
            team1_player1_id=1,
            team1_player2_id=2,
            team2_player1_id=3,
            team2_player2_id=4,
            team1_score=5,
            team2_score=3,
            played_at=datetime.utcnow(),
        )
        db.add(match)
        db.commit()
        
        deltas = update_ratings(match, db)
        
        # Winners (team1) should have positive ordinal delta
        assert deltas[1]["ordinal_delta"] > 0
        assert deltas[2]["ordinal_delta"] > 0
        
        # Losers (team2) should have negative ordinal delta
        assert deltas[3]["ordinal_delta"] < 0
        assert deltas[4]["ordinal_delta"] < 0
    
    def test_loser_ordinal_decreases(self, db: Session, players):
        """Losing team should see ordinal decrease"""
        match = Match(
            team1_player1_id=1,
            team1_player2_id=2,
            team2_player1_id=3,
            team2_player2_id=4,
            team1_score=2,
            team2_score=6,
            played_at=datetime.utcnow(),
        )
        db.add(match)
        db.commit()
        
        deltas = update_ratings(match, db)
        
        # Losers (team1) should have negative ordinal delta
        assert deltas[1]["ordinal_delta"] < 0
        assert deltas[2]["ordinal_delta"] < 0
        
        # Winners (team2) should have positive ordinal delta
        assert deltas[3]["ordinal_delta"] > 0
        assert deltas[4]["ordinal_delta"] > 0
    
    def test_sigma_decreases_over_matches(self, db: Session, players):
        """Sigma (uncertainty) should decrease as players play more"""
        initial_sigma = settings.TRUESKILL_SIGMA
        
        # Play 3 matches with player 1
        for i in range(3):
            match = Match(
                team1_player1_id=1,
                team1_player2_id=2,
                team2_player1_id=3,
                team2_player2_id=4,
                team1_score=5,
                team2_score=3,
                played_at=datetime.utcnow(),
            )
            db.add(match)
            db.commit()
            update_ratings(match, db)
        
        # Check that sigma decreased
        final_rating = get_current_rating(1, db)
        assert final_rating.sigma < initial_sigma
    
    def test_draw_handling(self, db: Session, players):
        """Draws should result in minimal rating changes"""
        match = Match(
            team1_player1_id=1,
            team1_player2_id=2,
            team2_player1_id=3,
            team2_player2_id=4,
            team1_score=4,
            team2_score=4,
            played_at=datetime.utcnow(),
        )
        db.add(match)
        db.commit()
        
        deltas = update_ratings(match, db)
        
        # All ordinal deltas should be small for a draw
        for player_id in [1, 2, 3, 4]:
            assert abs(deltas[player_id]["ordinal_delta"]) < 2.0
    
    def test_rating_history_created(self, db: Session, players):
        """Each match should create 4 rating history entries"""
        match = Match(
            team1_player1_id=1,
            team1_player2_id=2,
            team2_player1_id=3,
            team2_player2_id=4,
            team1_score=5,
            team2_score=3,
            played_at=datetime.utcnow(),
        )
        db.add(match)
        db.commit()
        
        update_ratings(match, db)
        
        # Check that 4 history entries were created
        history_count = db.query(RatingHistory).filter(
            RatingHistory.match_id == match.id
        ).count()
        assert history_count == 4
    
    def test_ordinal_calculation(self, db: Session, players):
        """Ordinal should be calculated as mu - 3*sigma"""
        match = Match(
            team1_player1_id=1,
            team1_player2_id=2,
            team2_player1_id=3,
            team2_player2_id=4,
            team1_score=5,
            team2_score=3,
            played_at=datetime.utcnow(),
        )
        db.add(match)
        db.commit()
        
        update_ratings(match, db)
        
        # Check ordinal calculation for player 1
        history = db.query(RatingHistory).filter(
            RatingHistory.player_id == 1
        ).first()
        expected_ordinal = history.mu - 3 * history.sigma
        assert abs(history.ordinal - expected_ordinal) < 0.01


class TestRecalculateAllRatings:
    """Tests for recalculate_all_ratings function"""
    
    def test_recalculation_clears_history(self, db: Session, players):
        """Recalculation should wipe existing rating history"""
        # Create some rating history
        for i in range(1, 5):
            history = RatingHistory(
                player_id=i,
                match_id=None,
                mu=25.0,
                sigma=8.0,
                ordinal=1.0,
            )
            db.add(history)
        db.commit()
        
        assert db.query(RatingHistory).count() == 4
        
        recalculate_all_ratings(db)
        
        # History should be cleared (no matches to replay)
        assert db.query(RatingHistory).count() == 0
    
    def test_recalculation_replays_matches(self, db: Session, players):
        """Recalculation should replay all non-deleted matches"""
        # Create 2 matches
        match1 = Match(
            team1_player1_id=1,
            team1_player2_id=2,
            team2_player1_id=3,
            team2_player2_id=4,
            team1_score=5,
            team2_score=3,
            played_at=datetime(2025, 1, 1, 10, 0, 0),
        )
        match2 = Match(
            team1_player1_id=1,
            team1_player2_id=3,
            team2_player1_id=2,
            team2_player2_id=4,
            team1_score=6,
            team2_score=2,
            played_at=datetime(2025, 1, 1, 11, 0, 0),
        )
        db.add(match1)
        db.add(match2)
        db.commit()
        
        # Initial ratings
        update_ratings(match1, db)
        update_ratings(match2, db)
        
        # Store player 1's rating
        rating_before = get_current_rating(1, db)
        
        # Recalculate
        recalculate_all_ratings(db)
        
        # Rating should be the same (replayed in same order)
        rating_after = get_current_rating(1, db)
        assert abs(rating_after.mu - rating_before.mu) < 0.01
        assert abs(rating_after.sigma - rating_before.sigma) < 0.01
        
        # Should have 8 history entries (4 per match)
        assert db.query(RatingHistory).count() == 8
    
    def test_deleted_matches_excluded(self, db: Session, players):
        """Soft-deleted matches should not be included in recalculation"""
        # Create 2 matches, soft-delete one
        match1 = Match(
            team1_player1_id=1,
            team1_player2_id=2,
            team2_player1_id=3,
            team2_player2_id=4,
            team1_score=5,
            team2_score=3,
            played_at=datetime(2025, 1, 1, 10, 0, 0),
        )
        match2 = Match(
            team1_player1_id=1,
            team1_player2_id=3,
            team2_player1_id=2,
            team2_player2_id=4,
            team1_score=6,
            team2_score=2,
            played_at=datetime(2025, 1, 1, 11, 0, 0),
            deleted_at=datetime.utcnow(),  # Soft delete
        )
        db.add(match1)
        db.add(match2)
        db.commit()
        
        recalculate_all_ratings(db)
        
        # Should only have 4 history entries (1 match)
        assert db.query(RatingHistory).count() == 4


class TestPredictWinProbability:
    """Tests for predict_win_probability function"""
    
    def test_equal_ratings_50_50(self, db: Session, players):
        """Teams with equal ratings should have ~50% win probability"""
        prob = predict_win_probability(1, 2, 3, 4, db)
        assert 0.45 < prob < 0.55
    
    def test_stronger_team_higher_probability(self, db: Session, players):
        """Team with higher ratings should have >50% win probability"""
        # Give team1 players higher ratings
        for player_id in [1, 2]:
            history = RatingHistory(
                player_id=player_id,
                match_id=None,
                mu=30.0,
                sigma=5.0,
                ordinal=15.0,
            )
            db.add(history)
        db.commit()
        
        prob = predict_win_probability(1, 2, 3, 4, db)
        assert prob > 0.6  # Should be significantly higher than 50%
    
    def test_weaker_team_lower_probability(self, db: Session, players):
        """Team with lower ratings should have <50% win probability"""
        # Give team2 players higher ratings
        for player_id in [3, 4]:
            history = RatingHistory(
                player_id=player_id,
                match_id=None,
                mu=30.0,
                sigma=5.0,
                ordinal=15.0,
            )
            db.add(history)
        db.commit()
        
        prob = predict_win_probability(1, 2, 3, 4, db)
        assert prob < 0.4  # Should be significantly lower than 50%
    
    def test_probability_sums_to_one(self, db: Session, players):
        """Team1 prob + Team2 prob should sum to ~1.0"""
        prob_team1 = predict_win_probability(1, 2, 3, 4, db)
        prob_team2 = predict_win_probability(3, 4, 1, 2, db)
        
        # Should sum to approximately 1.0
        assert abs((prob_team1 + prob_team2) - 1.0) < 0.01


class TestIntegration:
    """Integration tests simulating real match sequences"""
    
    def test_multi_match_rating_progression(self, db: Session, players):
        """Simulate a series of matches and verify rating progression"""
        # Player 1 wins 3 matches in a row
        for i in range(3):
            match = Match(
                team1_player1_id=1,
                team1_player2_id=2,
                team2_player1_id=3,
                team2_player2_id=4,
                team1_score=5,
                team2_score=2,
                played_at=datetime.utcnow(),
            )
            db.add(match)
            db.commit()
            update_ratings(match, db)
        
        # Player 1 should have higher rating than player 3
        rating_p1 = get_current_rating(1, db)
        rating_p3 = get_current_rating(3, db)
        
        ordinal_p1 = rating_p1.mu - 3 * rating_p1.sigma
        ordinal_p3 = rating_p3.mu - 3 * rating_p3.sigma
        
        assert ordinal_p1 > ordinal_p3
    
    def test_comeback_scenario(self, db: Session, players):
        """Test that losing then winning affects ratings appropriately"""
        # Player 1 loses 2 matches
        for i in range(2):
            match = Match(
                team1_player1_id=1,
                team1_player2_id=2,
                team2_player1_id=3,
                team2_player2_id=4,
                team1_score=2,
                team2_score=5,
                played_at=datetime.utcnow(),
            )
            db.add(match)
            db.commit()
            update_ratings(match, db)
        
        rating_after_losses = get_current_rating(1, db)
        
        # Player 1 wins 2 matches
        for i in range(2):
            match = Match(
                team1_player1_id=1,
                team1_player2_id=2,
                team2_player1_id=3,
                team2_player2_id=4,
                team1_score=5,
                team2_score=2,
                played_at=datetime.utcnow(),
            )
            db.add(match)
            db.commit()
            update_ratings(match, db)
        
        rating_after_wins = get_current_rating(1, db)
        
        # Ordinal should be higher after comeback
        ordinal_after_losses = rating_after_losses.mu - 3 * rating_after_losses.sigma
        ordinal_after_wins = rating_after_wins.mu - 3 * rating_after_wins.sigma
        
        assert ordinal_after_wins > ordinal_after_losses
