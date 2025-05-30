    @trivia_group.command(name="start", description="Start a new group trivia quiz on a specific topic")
    @app_commands.describe(
        topic="The topic for the quiz (e.g., 'Space Exploration')",
        question_count="Number of questions (default: 5, max: 5)",
        difficulty="Difficulty level (easy, medium, hard)",
        provider="LLM provider to use (openai, anthropic, google)",
        category="Question category (e.g., science)",
        template="Quiz template to use (e.g., trivia)",
        timeout="Time limit for each question in seconds (default: 30)",
        one_winner="If True, only the first correct answer earns points (default: False)",
        is_private="If True, sends questions and answers via DM instead of public chat (default: False)"
    )
    @app_commands.autocomplete(topic=_topic_autocomplete)
    @cooldown_with_bypass(rate=1, per=90, bypass_roles=["admin", "moderator", "bot_admin"])
    @require_context
    @in_guild_only
    async def trivia_start(
        self,
        ctx: commands.Context,
        topic: str,
        question_count: Optional[int] = 5,
        difficulty: str = "medium",
        provider: str = "openai",
        category: Optional[str] = None,
        template: Optional[str] = None,
        timeout: Optional[int] = 30,
        one_winner: bool = False,
        is_private: bool = False
    ):
        """Start a new group trivia quiz on a specific topic."""
        # Call the implementation method
        await self._trivia_start_impl(
            ctx, 
            topic=topic,
            question_count=question_count,
            difficulty=difficulty,
            provider=provider,
            category=category,
            template=template,
            timeout=timeout,
            one_winner=one_winner,
            is_private=is_private
        )