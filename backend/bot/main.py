"""Telegram bot main entry point"""
import logging
import sys
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from backend.app.config import settings
from backend.bot import handlers


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Start the Telegram bot"""
    # Check for bot token
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in environment!")
        sys.exit(1)
    
    # Create application
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("match", handlers.match_command))
    application.add_handler(CommandHandler("rank", handlers.rank_command))
    application.add_handler(CommandHandler("stats", handlers.stats_command))
    application.add_handler(CommandHandler("teams", handlers.teams_command))
    application.add_handler(CommandHandler("streak", handlers.streak_command))
    application.add_handler(CommandHandler("today", handlers.today_command))
    application.add_handler(CommandHandler("undo", handlers.undo_command))
    
    # Register callback query handler (for inline buttons)
    application.add_handler(CallbackQueryHandler(handlers.undo_callback))
    
    # Register unknown command handler (must be last)
    application.add_handler(
        MessageHandler(filters.COMMAND, handlers.unknown_command)
    )
    
    # Log startup
    logger.info("🤖 FIFA Ranks Bot starting...")
    logger.info(f"API endpoint: {settings.API_HOST}:{settings.API_PORT}")
    
    # Start the bot
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
