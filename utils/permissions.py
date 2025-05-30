"""Permission utilities for command access control."""

from discord.ext import commands
import logging

logger = logging.getLogger("bot.permissions")

# Bot owner ID - Jaden Razo
BOT_OWNER_ID = 1351309423015886899


def is_bot_owner():
    """Check if the command invoker is the authorized bot owner."""
    async def predicate(ctx):
        return ctx.author.id == BOT_OWNER_ID
    return commands.check(predicate)


async def check_bot_owner(ctx) -> bool:
    """Check if a user is the bot owner.
    
    Args:
        ctx: Command context
        
    Returns:
        True if user is the bot owner, False otherwise
    """
    return ctx.author.id == BOT_OWNER_ID


class NotBotOwner(commands.CheckFailure):
    """Exception raised when user is not the bot owner."""
    pass


async def bot_owner_or_error(ctx):
    """Check if user is bot owner, raise error if not.
    
    Args:
        ctx: Command context
        
    Raises:
        NotBotOwner: If user is not the bot owner
    """
    if ctx.author.id != BOT_OWNER_ID:
        raise NotBotOwner("This command is restricted to the bot owner.")
    return True