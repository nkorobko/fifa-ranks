"""SQLAlchemy ORM models"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, CheckConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base

class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    rating_history = relationship("RatingHistory", back_populates="player", cascade="all, delete-orphan")
    weekly_rankings = relationship("WeeklyRanking", back_populates="player", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Player {self.name}>"


class Match(Base):
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    played_at = Column(DateTime, nullable=False, index=True)
    
    # Team 1
    team1_player1 = Column(Integer, ForeignKey("players.id"), nullable=False)
    team1_player2 = Column(Integer, ForeignKey("players.id"), nullable=False)
    team1_score = Column(Integer, nullable=False)
    
    # Team 2
    team2_player1 = Column(Integer, ForeignKey("players.id"), nullable=False)
    team2_player2 = Column(Integer, ForeignKey("players.id"), nullable=False)
    team2_score = Column(Integer, nullable=False)
    
    # Metadata
    logged_by = Column(String, nullable=True)  # Who logged the match (for audit)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    rating_history = relationship("RatingHistory", back_populates="match", cascade="all, delete-orphan")
    
    # Relationships to players (read-only, no back_populates to avoid clutter)
    t1p1 = relationship("Player", foreign_keys=[team1_player1])
    t1p2 = relationship("Player", foreign_keys=[team1_player2])
    t2p1 = relationship("Player", foreign_keys=[team2_player1])
    t2p2 = relationship("Player", foreign_keys=[team2_player2])
    
    __table_args__ = (
        # Ensure all 4 players are distinct
        CheckConstraint(
            "team1_player1 != team1_player2 AND "
            "team1_player1 != team2_player1 AND "
            "team1_player1 != team2_player2 AND "
            "team1_player2 != team2_player1 AND "
            "team1_player2 != team2_player2 AND "
            "team2_player1 != team2_player2",
            name="distinct_players"
        ),
        Index("idx_match_played_at", "played_at"),
        Index("idx_match_is_deleted", "is_deleted"),
    )
    
    def __repr__(self):
        return f"<Match {self.id}: {self.team1_score}-{self.team2_score}>"


class RatingHistory(Base):
    __tablename__ = "rating_history"
    
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    
    # TrueSkill ratings after this match
    mu = Column(Float, nullable=False)
    sigma = Column(Float, nullable=False)
    ordinal = Column(Float, nullable=False)  # mu - 3*sigma (conservative skill estimate)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    player = relationship("Player", back_populates="rating_history")
    match = relationship("Match", back_populates="rating_history")
    
    __table_args__ = (
        Index("idx_rating_player_created", "player_id", "created_at"),
    )
    
    def __repr__(self):
        return f"<RatingHistory player={self.player_id} mu={self.mu:.2f} σ={self.sigma:.2f}>"


class WeeklyRanking(Base):
    __tablename__ = "weekly_rankings"
    
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    week_start = Column(DateTime, nullable=False)  # Monday 00:00:00 of the week
    
    # Component scores (0-100 scale)
    skill_score = Column(Float, nullable=False)
    form_score = Column(Float, nullable=False)
    impact_score = Column(Float, nullable=False)
    
    # Final composite score
    power_index = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)
    
    # Weekly stats
    matches_played = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    draws = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    
    # Relationships
    player = relationship("Player", back_populates="weekly_rankings")
    
    __table_args__ = (
        Index("idx_weekly_week_rank", "week_start", "rank"),
    )
    
    def __repr__(self):
        return f"<WeeklyRanking player={self.player_id} week={self.week_start.date()} rank={self.rank}>"


class PairStats(Base):
    __tablename__ = "pair_stats"
    
    # Composite primary key
    player1_id = Column(Integer, ForeignKey("players.id"), primary_key=True)
    player2_id = Column(Integer, ForeignKey("players.id"), primary_key=True)
    
    # Stats when this pair plays together
    matches_played = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    goals_for = Column(Integer, nullable=False, default=0)
    goals_against = Column(Integer, nullable=False, default=0)
    last_played = Column(DateTime, nullable=True)
    
    # Relationships
    player1 = relationship("Player", foreign_keys=[player1_id])
    player2 = relationship("Player", foreign_keys=[player2_id])
    
    __table_args__ = (
        # Ensure player1_id < player2_id (canonical ordering)
        CheckConstraint("player1_id < player2_id", name="canonical_pair_order"),
    )
    
    def __repr__(self):
        return f"<PairStats {self.player1_id}-{self.player2_id}: {self.wins}/{self.matches_played} wins>"
