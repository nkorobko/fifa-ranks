"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-03-03

"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Players table
    op.create_table(
        'players',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_players_id'), 'players', ['id'], unique=False)
    
    # Matches table
    op.create_table(
        'matches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('played_at', sa.DateTime(), nullable=False),
        sa.Column('team1_player1', sa.Integer(), nullable=False),
        sa.Column('team1_player2', sa.Integer(), nullable=False),
        sa.Column('team1_score', sa.Integer(), nullable=False),
        sa.Column('team2_player1', sa.Integer(), nullable=False),
        sa.Column('team2_player2', sa.Integer(), nullable=False),
        sa.Column('team2_score', sa.Integer(), nullable=False),
        sa.Column('logged_by', sa.String(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['team1_player1'], ['players.id'], ),
        sa.ForeignKeyConstraint(['team1_player2'], ['players.id'], ),
        sa.ForeignKeyConstraint(['team2_player1'], ['players.id'], ),
        sa.ForeignKeyConstraint(['team2_player2'], ['players.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            'team1_player1 != team1_player2 AND '
            'team1_player1 != team2_player1 AND '
            'team1_player1 != team2_player2 AND '
            'team1_player2 != team2_player1 AND '
            'team1_player2 != team2_player2 AND '
            'team2_player1 != team2_player2',
            name='distinct_players'
        )
    )
    op.create_index(op.f('ix_matches_id'), 'matches', ['id'], unique=False)
    op.create_index('idx_match_played_at', 'matches', ['played_at'], unique=False)
    op.create_index('idx_match_is_deleted', 'matches', ['is_deleted'], unique=False)
    
    # Rating history table
    op.create_table(
        'rating_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=False),
        sa.Column('mu', sa.Float(), nullable=False),
        sa.Column('sigma', sa.Float(), nullable=False),
        sa.Column('ordinal', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rating_history_id'), 'rating_history', ['id'], unique=False)
    op.create_index('idx_rating_player_created', 'rating_history', ['player_id', 'created_at'], unique=False)
    
    # Weekly rankings table
    op.create_table(
        'weekly_rankings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('week_start', sa.DateTime(), nullable=False),
        sa.Column('skill_score', sa.Float(), nullable=False),
        sa.Column('form_score', sa.Float(), nullable=False),
        sa.Column('impact_score', sa.Float(), nullable=False),
        sa.Column('power_index', sa.Float(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('matches_played', sa.Integer(), nullable=False),
        sa.Column('wins', sa.Integer(), nullable=False),
        sa.Column('draws', sa.Integer(), nullable=False),
        sa.Column('losses', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_weekly_rankings_id'), 'weekly_rankings', ['id'], unique=False)
    op.create_index('idx_weekly_week_rank', 'weekly_rankings', ['week_start', 'rank'], unique=False)
    
    # Pair stats table
    op.create_table(
        'pair_stats',
        sa.Column('player1_id', sa.Integer(), nullable=False),
        sa.Column('player2_id', sa.Integer(), nullable=False),
        sa.Column('matches_played', sa.Integer(), nullable=False),
        sa.Column('wins', sa.Integer(), nullable=False),
        sa.Column('goals_for', sa.Integer(), nullable=False),
        sa.Column('goals_against', sa.Integer(), nullable=False),
        sa.Column('last_played', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['player1_id'], ['players.id'], ),
        sa.ForeignKeyConstraint(['player2_id'], ['players.id'], ),
        sa.PrimaryKeyConstraint('player1_id', 'player2_id'),
        sa.CheckConstraint('player1_id < player2_id', name='canonical_pair_order')
    )


def downgrade() -> None:
    op.drop_table('pair_stats')
    op.drop_table('weekly_rankings')
    op.drop_table('rating_history')
    op.drop_table('matches')
    op.drop_table('players')
