"""Telegram bot command handlers"""
import logging
from datetime import datetime, timedelta
from typing import Optional
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from backend.bot.parser import (
    parse_match_command,
    parse_stats_command,
    parse_teams_command,
)
from backend.bot.formatter import (
    format_match_logged,
    format_rankings,
    format_player_stats,
    format_balanced_teams,
    format_streak_summary,
    format_today_matches,
    format_help,
)
from backend.app.config import settings


logger = logging.getLogger(__name__)

# API base URL
API_BASE = f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1"

# Rate limiting: track last match time per user
last_match_time = {}
MATCH_COOLDOWN_SECONDS = 10


async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /match command.
    
    Example: /match Noam Itay vs Ayal Ari 3-1
    """
    user_id = update.effective_user.id
    
    # Rate limiting
    now = datetime.utcnow()
    if user_id in last_match_time:
        time_since_last = (now - last_match_time[user_id]).total_seconds()
        if time_since_last < MATCH_COOLDOWN_SECONDS:
            remaining = int(MATCH_COOLDOWN_SECONDS - time_since_last)
            await update.message.reply_text(
                f"⏳ Please wait {remaining} seconds before logging another match."
            )
            return
    
    try:
        # Parse command
        match_data = parse_match_command(update.message.text)
        
        # Call API to log match
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Prepare match payload (API expects player names in arrays)
            payload = {
                "team1": [match_data["team1_player1"], match_data["team1_player2"]],
                "team2": [match_data["team2_player1"], match_data["team2_player2"]],
                "team1_score": match_data["team1_score"],
                "team2_score": match_data["team2_score"],
            }
            
            # Log match
            match_resp = await client.post(f"{API_BASE}/matches", json=payload)
            match_resp.raise_for_status()
            match = match_resp.json()
            
            # Update rate limit
            last_match_time[user_id] = now
            
            # Format and send response
            message = format_match_logged(match, match.get("rating_changes", []))
            await update.message.reply_text(message, parse_mode="Markdown")
            
    except ValueError as e:
        # Parsing error with helpful message
        await update.message.reply_text(f"❌ {str(e)}", parse_mode="Markdown")
    except httpx.HTTPStatusError as e:
        logger.error(f"API error: {e.response.status_code} - {e.response.text}")
        await update.message.reply_text(
            "❌ Server error. Please try again in a moment."
        )
    except Exception as e:
        logger.exception("Unexpected error in match_command")
        await update.message.reply_text(
            "❌ Something went wrong. Please try again."
        )


async def rank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rank command - show power rankings"""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(f"{API_BASE}/players")
            resp.raise_for_status()
            players = resp.json()
            
            # Sort by ordinal (descending)
            ranked_players = sorted(
                players,
                key=lambda p: p.get("ordinal", 0.0),
                reverse=True
            )
            
            message = format_rankings(ranked_players)
            await update.message.reply_text(message, parse_mode="Markdown")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"API error: {e.response.status_code} - {e.response.text}")
        await update.message.reply_text("❌ Could not fetch rankings.")
    except Exception as e:
        logger.exception("Unexpected error in rank_command")
        await update.message.reply_text("❌ Something went wrong.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /stats command - show player statistics.
    
    Example: /stats Noam
    """
    try:
        # Parse player name
        player_name = parse_stats_command(update.message.text)
        
        if not player_name:
            await update.message.reply_text(
                "Please specify a player. Example: `/stats Noam`",
                parse_mode="Markdown"
            )
            return
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Get all players
            players_resp = await client.get(f"{API_BASE}/players")
            players_resp.raise_for_status()
            players = players_resp.json()
            
            # Find player by name
            player = next((p for p in players if p["name"] == player_name), None)
            
            if not player:
                await update.message.reply_text(f"❌ Player '{player_name}' not found.")
                return
            
            # Get detailed player stats
            player_resp = await client.get(f"{API_BASE}/players/{player['id']}")
            player_resp.raise_for_status()
            player_detail = player_resp.json()
            
            message = format_player_stats(player_detail)
            await update.message.reply_text(message, parse_mode="Markdown")
            
    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}", parse_mode="Markdown")
    except httpx.HTTPStatusError as e:
        logger.error(f"API error: {e.response.status_code} - {e.response.text}")
        await update.message.reply_text("❌ Could not fetch player stats.")
    except Exception as e:
        logger.exception("Unexpected error in stats_command")
        await update.message.reply_text("❌ Something went wrong.")


async def teams_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /teams command - suggest balanced matchups.
    
    Example: /teams Noam Itay Ayal Ari
    """
    try:
        # Parse player names
        player_names = parse_teams_command(update.message.text)
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Get all players
            players_resp = await client.get(f"{API_BASE}/players")
            players_resp.raise_for_status()
            players = players_resp.json()
            
            # Build name -> ordinal map
            name_to_ordinal = {p["name"]: p.get("ordinal", 0.0) for p in players}
            
            # Get ordinals for our 4 players
            ordinals = [name_to_ordinal[name] for name in player_names]
            
            # Generate all possible team combinations
            # With 4 players [A, B, C, D], there are 3 unique matchups:
            # 1. AB vs CD
            # 2. AC vs BD
            # 3. AD vs BC
            from itertools import combinations
            
            options = []
            all_combos = list(combinations(range(4), 2))
            
            # Generate unique team pairings
            for i, combo in enumerate(all_combos):
                team1_indices = combo
                team2_indices = tuple(j for j in range(4) if j not in team1_indices)
                
                # Skip if we've already seen the reverse pairing
                pairing = (team1_indices, team2_indices)
                reverse_pairing = (team2_indices, team1_indices)
                if any(
                    opt["_pairing"] == reverse_pairing
                    for opt in options
                ):
                    continue
                
                team1_total = ordinals[team1_indices[0]] + ordinals[team1_indices[1]]
                team2_total = ordinals[team2_indices[0]] + ordinals[team2_indices[1]]
                
                # Balance score: how close the teams are (0.0 = perfect, 1.0 = maximum imbalance)
                avg = (team1_total + team2_total) / 2
                if avg > 0:
                    imbalance = abs(team1_total - team2_total) / avg
                    balance_score = max(0.0, 1.0 - imbalance)
                else:
                    balance_score = 1.0
                
                options.append({
                    "team1": {
                        "player1": player_names[team1_indices[0]],
                        "player2": player_names[team1_indices[1]],
                    },
                    "team2": {
                        "player1": player_names[team2_indices[0]],
                        "player2": player_names[team2_indices[1]],
                    },
                    "balance_score": balance_score,
                    "_pairing": pairing,
                })
            
            # Sort by balance score (best first)
            options.sort(key=lambda o: o["balance_score"], reverse=True)
            
            # Remove internal _pairing key
            for opt in options:
                del opt["_pairing"]
            
            message = format_balanced_teams(options)
            await update.message.reply_text(message, parse_mode="Markdown")
            
    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}", parse_mode="Markdown")
    except Exception as e:
        logger.exception("Unexpected error in teams_command")
        await update.message.reply_text("❌ Something went wrong.")


async def streak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /streak command - show everyone's current streaks"""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(f"{API_BASE}/players")
            resp.raise_for_status()
            players = resp.json()
            
            message = format_streak_summary(players)
            await update.message.reply_text(message, parse_mode="Markdown")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"API error: {e.response.status_code} - {e.response.text}")
        await update.message.reply_text("❌ Could not fetch streak data.")
    except Exception as e:
        logger.exception("Unexpected error in streak_command")
        await update.message.reply_text("❌ Something went wrong.")


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /today command - show all matches played today"""
    try:
        # Get today's date range
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                f"{API_BASE}/matches",
                params={
                    "start_date": today.isoformat(),
                    "end_date": tomorrow.isoformat(),
                }
            )
            resp.raise_for_status()
            matches = resp.json()
            
            message = format_today_matches(matches)
            await update.message.reply_text(message, parse_mode="Markdown")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"API error: {e.response.status_code} - {e.response.text}")
        await update.message.reply_text("❌ Could not fetch today's matches.")
    except Exception as e:
        logger.exception("Unexpected error in today_command")
        await update.message.reply_text("❌ Something went wrong.")


async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /undo command - delete last match with confirmation"""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Get the most recent match
            resp = await client.get(f"{API_BASE}/matches", params={"limit": 1})
            resp.raise_for_status()
            matches = resp.json()
            
            if not matches:
                await update.message.reply_text("📭 No matches to undo.")
                return
            
            last_match = matches[0]
            
            # Build confirmation message
            team1_score = last_match["team1_score"]
            team2_score = last_match["team2_score"]
            played_at = datetime.fromisoformat(last_match["played_at"].replace("Z", "+00:00"))
            time_str = played_at.strftime("%Y-%m-%d %H:%M")
            
            confirm_msg = (
                f"⚠️ **Confirm deletion:**\n\n"
                f"{last_match['team1_player1_name']}+{last_match['team1_player2_name']} "
                f"`{team1_score}-{team2_score}` "
                f"{last_match['team2_player1_name']}+{last_match['team2_player2_name']}\n"
                f"Played: {time_str}\n\n"
                f"Ratings will be recalculated."
            )
            
            # Inline keyboard for confirmation
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes, delete", callback_data=f"undo_yes:{last_match['id']}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="undo_no"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                confirm_msg,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            
    except httpx.HTTPStatusError as e:
        logger.error(f"API error: {e.response.status_code} - {e.response.text}")
        await update.message.reply_text("❌ Could not fetch last match.")
    except Exception as e:
        logger.exception("Unexpected error in undo_command")
        await update.message.reply_text("❌ Something went wrong.")


async def undo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle undo confirmation callback"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "undo_no":
        await query.edit_message_text("❌ Undo cancelled.")
        return
    
    if not data.startswith("undo_yes:"):
        await query.edit_message_text("❌ Invalid callback.")
        return
    
    match_id = int(data.split(":")[1])
    
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.delete(f"{API_BASE}/matches/{match_id}")
            resp.raise_for_status()
            
            await query.edit_message_text(
                "✅ Match deleted. Ratings recalculated.",
                parse_mode="Markdown"
            )
            
    except httpx.HTTPStatusError as e:
        logger.error(f"API error: {e.response.status_code} - {e.response.text}")
        await query.edit_message_text("❌ Could not delete match.")
    except Exception as e:
        logger.exception("Unexpected error in undo_callback")
        await query.edit_message_text("❌ Something went wrong.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command - show all available commands"""
    message = format_help()
    await update.message.reply_text(message, parse_mode="Markdown")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - welcome message"""
    welcome_msg = (
        "👋 **Welcome to FIFA Ranks Bot!**\n\n"
        "I help track your 2v2 FIFA matches and maintain power rankings.\n\n"
        "Use `/help` to see all available commands."
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands with suggestions"""
    command = update.message.text.split()[0].lower()
    
    # Known commands
    known = ["/match", "/rank", "/stats", "/teams", "/streak", "/today", "/undo", "/help", "/start"]
    
    # Find closest match using simple string comparison
    from difflib import get_close_matches
    suggestions = get_close_matches(command, known, n=1, cutoff=0.6)
    
    if suggestions:
        msg = f"❓ Unknown command. Did you mean `{suggestions[0]}`?"
    else:
        msg = "❓ Unknown command. Use `/help` to see all available commands."
    
    await update.message.reply_text(msg, parse_mode="Markdown")
