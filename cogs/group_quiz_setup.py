async def setup(bot):
    """Setup function for the cog."""
    try:
        # Create and add cog
        cog = GroupQuizCog(bot)
        await bot.add_cog(cog)
        logger.debug("GroupQuizCog loaded via setup function")
        return cog
    except Exception as e:
        logger.error(f"Error loading GroupQuizCog: {e}")
        raise

async def setup_with_context(bot, context):
    """Setup function that uses the context pattern."""
    try:
        # Create and add cog with context
        cog = GroupQuizCog(bot)
        cog.set_context(context)
        await bot.add_cog(cog)
        logger.debug("GroupQuizCog loaded via setup_with_context function")
        return cog
    except Exception as e:
        logger.error(f"Error loading GroupQuizCog with context: {e}")
        raise