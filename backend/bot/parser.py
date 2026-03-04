"""Parse Telegram command arguments"""
import re
from typing import Optional, List, Tuple
from Levenshtein import distance as levenshtein_distance


# Known player names (from seed data)
PLAYERS = ["Noam", "Itay", "Ayal", "Ari", "Sharon", "Dori"]


def fuzzy_match_player(name: str, threshold: int = 2) -> Optional[str]:
    """
    Find the closest matching player name using Levenshtein distance.
    
    Args:
        name: Player name to match (case-insensitive)
        threshold: Maximum edit distance to consider a match
    
    Returns:
        Closest player name if found, None otherwise
    """
    name_lower = name.lower()
    
    # Exact match (case-insensitive)
    for player in PLAYERS:
        if player.lower() == name_lower:
            return player
    
    # Fuzzy match
    closest = None
    min_distance = threshold + 1
    
    for player in PLAYERS:
        dist = levenshtein_distance(name_lower, player.lower())
        if dist < min_distance:
            min_distance = dist
            closest = player
    
    return closest if min_distance <= threshold else None


def parse_match_command(text: str) -> dict:
    """
    Parse /match command.
    
    Format: /match Player1 Player2 vs Player3 Player4 Score1-Score2
    Alternative separators: vs, VS, v, -
    Alternative score formats: 3-1, 3 1, 3:1
    
    Args:
        text: Full command text including /match
    
    Returns:
        dict with team1_player1, team1_player2, team2_player1, team2_player2,
        team1_score, team2_score
    
    Raises:
        ValueError: If parsing fails with helpful error message
    """
    # Remove /match prefix
    text = text.strip()
    if text.lower().startswith("/match"):
        text = text[6:].strip()
    
    # Split on team separator (vs, VS, v, or standalone -)
    # Use regex to handle multiple separators
    parts = re.split(r'\s+(?:vs?|VS?)\s+|\s+-\s+', text, maxsplit=1)
    
    if len(parts) != 2:
        raise ValueError(
            "Invalid format. Use: `/match Player1 Player2 vs Player3 Player4 3-1`"
        )
    
    team1_text, rest = parts
    
    # Extract score from team2 text
    # Scores can be at the end or mixed in: "Player3 Player4 3-1" or "Player3 Player4 3 1"
    score_pattern = r'(\d+)[\s\-:](\d+)$'
    score_match = re.search(score_pattern, rest)
    
    if not score_match:
        raise ValueError(
            "Score not found. Use format like: `3-1` or `3:1` or `3 1`"
        )
    
    team1_score = int(score_match.group(1))
    team2_score = int(score_match.group(2))
    team2_text = rest[:score_match.start()].strip()
    
    # Parse player names from team1 and team2
    team1_players = team1_text.split()
    team2_players = team2_text.split()
    
    if len(team1_players) != 2:
        raise ValueError(
            f"Team 1 must have exactly 2 players, found {len(team1_players)}"
        )
    
    if len(team2_players) != 2:
        raise ValueError(
            f"Team 2 must have exactly 2 players, found {len(team2_players)}"
        )
    
    # Fuzzy match player names
    matched_players = []
    suggestions = []
    
    for i, player_input in enumerate(team1_players + team2_players):
        matched = fuzzy_match_player(player_input)
        if matched:
            matched_players.append(matched)
        else:
            # Try to suggest closest match even if over threshold
            closest = min(
                PLAYERS,
                key=lambda p: levenshtein_distance(player_input.lower(), p.lower())
            )
            suggestions.append((player_input, closest))
    
    if suggestions:
        suggestion_text = "\n".join(
            f"  • '{inp}' → did you mean '{sug}'?"
            for inp, sug in suggestions
        )
        raise ValueError(
            f"Unknown player(s):\n{suggestion_text}"
        )
    
    # Validate unique players (no player on both teams or duplicates)
    if len(set(matched_players)) != 4:
        duplicates = [p for p in matched_players if matched_players.count(p) > 1]
        raise ValueError(
            f"Each player can only appear once. Duplicates: {', '.join(set(duplicates))}"
        )
    
    return {
        "team1_player1": matched_players[0],
        "team1_player2": matched_players[1],
        "team2_player1": matched_players[2],
        "team2_player2": matched_players[3],
        "team1_score": team1_score,
        "team2_score": team2_score,
    }


def parse_stats_command(text: str) -> Optional[str]:
    """
    Parse /stats command to extract player name.
    
    Args:
        text: Full command text including /stats
    
    Returns:
        Player name if found, None if no player specified
    
    Raises:
        ValueError: If player name is invalid
    """
    # Remove /stats prefix
    text = text.strip()
    if text.lower().startswith("/stats"):
        text = text[6:].strip()
    
    if not text:
        return None
    
    # Fuzzy match player
    matched = fuzzy_match_player(text)
    if matched:
        return matched
    
    # Suggest closest
    closest = min(
        PLAYERS,
        key=lambda p: levenshtein_distance(text.lower(), p.lower())
    )
    raise ValueError(f"Unknown player '{text}'. Did you mean '{closest}'?")


def parse_teams_command(text: str) -> List[str]:
    """
    Parse /teams command to extract 4 player names for balanced matchup generation.
    
    Args:
        text: Full command text including /teams
    
    Returns:
        List of 4 player names
    
    Raises:
        ValueError: If wrong number of players or invalid names
    """
    # Remove /teams prefix
    text = text.strip()
    if text.lower().startswith("/teams"):
        text = text[6:].strip()
    
    if not text:
        raise ValueError(
            "Please provide 4 player names. Example: `/teams Noam Itay Ayal Ari`"
        )
    
    player_inputs = text.split()
    
    if len(player_inputs) != 4:
        raise ValueError(
            f"Expected 4 players, got {len(player_inputs)}. "
            "Example: `/teams Noam Itay Ayal Ari`"
        )
    
    # Fuzzy match all players
    matched_players = []
    suggestions = []
    
    for player_input in player_inputs:
        matched = fuzzy_match_player(player_input)
        if matched:
            matched_players.append(matched)
        else:
            closest = min(
                PLAYERS,
                key=lambda p: levenshtein_distance(player_input.lower(), p.lower())
            )
            suggestions.append((player_input, closest))
    
    if suggestions:
        suggestion_text = "\n".join(
            f"  • '{inp}' → did you mean '{sug}'?"
            for inp, sug in suggestions
        )
        raise ValueError(
            f"Unknown player(s):\n{suggestion_text}"
        )
    
    # Validate unique players
    if len(set(matched_players)) != 4:
        duplicates = [p for p in matched_players if matched_players.count(p) > 1]
        raise ValueError(
            f"All 4 players must be different. Duplicates: {', '.join(set(duplicates))}"
        )
    
    return matched_players
