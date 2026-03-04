"""Pydantic schemas for API request/response validation"""
from pydantic import BaseModel, field_validator, model_validator
from datetime import datetime
from typing import Optional, List

# Player schemas
class PlayerBase(BaseModel):
    name: str

class PlayerResponse(PlayerBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Match schemas
class MatchCreate(BaseModel):
    team1: List[str]  # 2 player names
    team2: List[str]  # 2 player names
    team1_score: int
    team2_score: int
    played_at: Optional[datetime] = None  # Defaults to now if not provided
    logged_by: Optional[str] = None
    
    @field_validator('team1', 'team2')
    @classmethod
    def validate_team_size(cls, v):
        if len(v) != 2:
            raise ValueError('Each team must have exactly 2 players')
        if v[0] == v[1]:
            raise ValueError('Cannot have the same player twice on one team')
        return v
    
    @field_validator('team1_score', 'team2_score')
    @classmethod
    def validate_score(cls, v):
        if v < 0:
            raise ValueError('Score cannot be negative')
        return v
    
    @model_validator(mode='after')
    def validate_no_duplicate_players(self):
        all_players = self.team1 + self.team2
        if len(set(all_players)) != 4:
            raise ValueError('All 4 players must be distinct')
        return self

class RatingChange(BaseModel):
    player_name: str
    ordinal_delta: float  # Change in conservative rating (mu - 3*sigma)
    new_ordinal: float    # New conservative rating after match

class MatchResponse(BaseModel):
    id: int
    played_at: datetime
    team1_player1: str
    team1_player2: str
    team1_score: int
    team2_player1: str
    team2_player2: str
    team2_score: int
    logged_by: Optional[str]
    created_at: datetime
    rating_changes: Optional[List[RatingChange]] = []
    
    class Config:
        from_attributes = True

class MatchListItem(BaseModel):
    id: int
    played_at: datetime
    team1_player1: str
    team1_player2: str
    team1_score: int
    team2_player1: str
    team2_player2: str
    team2_score: int
    winner: str  # "team1", "team2", or "draw"
    
    class Config:
        from_attributes = True

class MatchListResponse(BaseModel):
    matches: List[MatchListItem]
    total: int
    limit: int
    offset: int
