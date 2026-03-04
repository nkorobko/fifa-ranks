"""Format API responses as Telegram messages"""
from datetime import datetime
from typing import List, Dict, Any


def format_match_logged(match_data: dict, rating_changes: dict) -> str:
    """
    Format a successful match log message.
    
    Args:
        match_data: Match object from API
        rating_changes: Dict of player_id -> {mu_delta, sigma_delta, ordinal_delta, new_ordinal}
    
    Returns:
        Formatted message string
    """
    team1_score = match_data["team1_score"]
    team2_score = match_data["team2_score"]
    
    # Determine match result emoji
    if team1_score > team2_score:
        result_emoji = "🏆"
    elif team2_score > team1_score:
        result_emoji = "🎯"
    else:
        result_emoji = "🤝"
    
    msg = f"{result_emoji} **Match logged!**\n\n"
    
    # Team names and scores
    msg += (
        f"**{match_data['team1_player1_name']}** + **{match_data['team1_player2_name']}**  "
        f"`{team1_score}` - `{team2_score}`  "
        f"**{match_data['team2_player1_name']}** + **{match_data['team2_player2_name']}**\n\n"
    )
    
    # Rating changes
    msg += "📊 **Rating changes:**\n"
    
    # Format each player's rating change
    for player_id_str, change in rating_changes.items():
        player_id = int(player_id_str)
        
        # Find player name from match data
        if player_id == match_data["team1_player1_id"]:
            name = match_data["team1_player1_name"]
        elif player_id == match_data["team1_player2_id"]:
            name = match_data["team1_player2_name"]
        elif player_id == match_data["team2_player1_id"]:
            name = match_data["team2_player1_name"]
        else:
            name = match_data["team2_player2_name"]
        
        delta = change["ordinal_delta"]
        new_ordinal = change["new_ordinal"]
        old_ordinal = new_ordinal - delta
        
        # Arrow and sign
        if delta > 0:
            arrow = "📈"
            sign = "+"
        elif delta < 0:
            arrow = "📉"
            sign = ""
        else:
            arrow = "➡️"
            sign = ""
        
        msg += (
            f"  {arrow} **{name:8s}**  "
            f"`{old_ordinal:5.1f}` → `{new_ordinal:5.1f}`  "
            f"*{sign}{delta:+.1f}*\n"
        )
    
    return msg


def format_rankings(rankings: List[dict]) -> str:
    """
    Format the power rankings leaderboard.
    
    Args:
        rankings: List of player objects with rank, name, ordinal, streak
    
    Returns:
        Formatted rankings message
    """
    msg = "🏆 **Power Rankings**\n\n"
    
    for i, player in enumerate(rankings, 1):
        crown = "👑 " if i == 1 else "   "
        name = player["name"]
        ordinal = player.get("ordinal", 0.0)
        streak = player.get("current_streak", 0)
        
        # Streak emoji and text
        if streak > 0:
            streak_text = f"(W{streak})"
            streak_emoji = "🔥" if streak >= 3 else ""
        elif streak < 0:
            streak_text = f"(L{abs(streak)})"
            streak_emoji = "❄️" if streak <= -3 else ""
        else:
            streak_text = ""
            streak_emoji = ""
        
        msg += f"{i}. {crown}**{name:8s}** — Rating `{ordinal:5.1f}`  {streak_emoji}{streak_text}\n"
    
    return msg


def format_player_stats(player: dict) -> str:
    """
    Format detailed player statistics.
    
    Args:
        player: Player object from API with full stats
    
    Returns:
        Formatted stats message
    """
    name = player["name"]
    rank = player.get("rank", "?")
    ordinal = player.get("ordinal", 0.0)
    wins = player.get("total_wins", 0)
    draws = player.get("total_draws", 0)
    losses = player.get("total_losses", 0)
    total = wins + draws + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    
    msg = f"📊 **{name}'s Stats**\n\n"
    msg += f"**Rank:** #{rank}\n"
    msg += f"**Rating:** `{ordinal:.1f}`\n"
    msg += f"**Record:** {wins}W - {draws}D - {losses}L ({win_rate:.1f}% win rate)\n"
    
    # Streak
    streak = player.get("current_streak", 0)
    if streak > 0:
        msg += f"**Streak:** 🔥 {streak} wins\n"
    elif streak < 0:
        msg += f"**Streak:** ❄️ {abs(streak)} losses\n"
    else:
        msg += f"**Streak:** —\n"
    
    # Best/worst partners (if available)
    best_partner = player.get("best_partner")
    worst_partner = player.get("worst_partner")
    
    if best_partner:
        msg += f"**Best partner:** {best_partner['name']} ({best_partner['win_rate']:.1f}% win rate)\n"
    
    if worst_partner:
        msg += f"**Worst partner:** {worst_partner['name']} ({worst_partner['win_rate']:.1f}% win rate)\n"
    
    return msg


def format_balanced_teams(options: List[dict]) -> str:
    """
    Format balanced team matchup suggestions.
    
    Args:
        options: List of team matchup options with balance scores
    
    Returns:
        Formatted message
    """
    msg = "⚖️ **Balanced Matchups**\n\n"
    
    for i, option in enumerate(options, 1):
        team1 = option["team1"]
        team2 = option["team2"]
        balance = option["balance_score"]
        
        msg += f"**Option {i}** ({balance:.0%} balanced):\n"
        msg += (
            f"  {team1['player1']} + {team1['player2']}  "
            f"**vs**  "
            f"{team2['player1']} + {team2['player2']}\n\n"
        )
    
    return msg


def format_streak_summary(players: List[dict]) -> str:
    """
    Format current streaks for all players.
    
    Args:
        players: List of player objects with streak data
    
    Returns:
        Formatted streak message
    """
    msg = "🔥 **Current Streaks**\n\n"
    
    # Sort by streak magnitude (absolute value)
    sorted_players = sorted(
        players,
        key=lambda p: abs(p.get("current_streak", 0)),
        reverse=True
    )
    
    for player in sorted_players:
        name = player["name"]
        streak = player.get("current_streak", 0)
        
        if streak > 0:
            emoji = "🔥" if streak >= 3 else "📈"
            msg += f"{emoji} **{name}**: {streak} wins\n"
        elif streak < 0:
            emoji = "❄️" if streak <= -3 else "📉"
            msg += f"{emoji} **{name}**: {abs(streak)} losses\n"
        else:
            msg += f"➡️ **{name}**: No streak\n"
    
    return msg


def format_today_matches(matches: List[dict]) -> str:
    """
    Format all matches played today.
    
    Args:
        matches: List of match objects
    
    Returns:
        Formatted message
    """
    if not matches:
        return "📅 No matches played today yet."
    
    msg = f"📅 **Today's Matches** ({len(matches)} total)\n\n"
    
    for i, match in enumerate(matches, 1):
        team1_score = match["team1_score"]
        team2_score = match["team2_score"]
        
        # Result emoji
        if team1_score > team2_score:
            result = "🏆"
        elif team2_score > team1_score:
            result = "🎯"
        else:
            result = "🤝"
        
        # Time
        played_at = datetime.fromisoformat(match["played_at"].replace("Z", "+00:00"))
        time_str = played_at.strftime("%H:%M")
        
        msg += (
            f"{i}. {result} `{time_str}`  "
            f"{match['team1_player1_name']}+{match['team1_player2_name']} "
            f"`{team1_score}-{team2_score}` "
            f"{match['team2_player1_name']}+{match['team2_player2_name']}\n"
        )
    
    return msg


def format_help() -> str:
    """Format the help message with all available commands."""
    return """
🤖 **FIFA Ranks Bot Commands**

**Match Logging:**
`/match Noam Itay vs Ayal Ari 3-1` — Log a match result

**Rankings & Stats:**
`/rank` — Show current power rankings
`/stats Noam` — Player stats and rating
`/streak` — Everyone's current win/loss streak
`/today` — All matches played today

**Team Building:**
`/teams Noam Itay Ayal Ari` — Suggest balanced 2v2 matchups

**Admin:**
`/undo` — Delete last match (with confirmation)

**Other:**
`/help` — Show this help message

*All player names are case-insensitive and typo-tolerant.*
"""
