"""
Example Usage of the Unified Persistent UI System

This file demonstrates how to use the unified persistent UI system in your cogs.
"""

import discord
from discord.ext import commands
from datetime import timedelta
from typing import Optional

from utils.unified_persistent_ui import (
    PersistentView, ButtonAction, create_navigation_view, create_welcome_view
)


class PersistentUIExampleCog(commands.Cog):
    """Example cog showing persistent UI usage."""
    
    def __init__(self, bot):
        self.bot = bot
        self.context = None  # Will be set by the cog loader
    
    def set_context(self, context):
        """Set the bot context (called automatically)."""
        self.context = context
    
    @commands.hybrid_command(name="ui_example")
    async def ui_example(self, ctx):
        """Demonstrate various persistent UI components."""
        
        # Example 1: Simple navigation view
        view = create_navigation_view(
            self.context, 
            user_id=ctx.author.id, 
            current_page=0, 
            total_pages=5,
            guild_id=ctx.guild.id if ctx.guild else None
        )
        
        embed = discord.Embed(
            title="📋 Navigation Example",
            description="This view has persistent navigation buttons.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Page 1 of 5")
        
        await ctx.send(embed=embed, view=view)
    
    @commands.hybrid_command(name="welcome_example") 
    async def welcome_example(self, ctx):
        """Demonstrate welcome action buttons."""
        
        view = create_welcome_view(
            self.context,
            guild_id=ctx.guild.id if ctx.guild else None
        )
        
        embed = discord.Embed(
            title="🎉 Welcome to Quiz Bot!",
            description="Choose an action below to get started:",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed, view=view)
    
    @commands.hybrid_command(name="custom_ui")
    async def custom_ui(self, ctx):
        """Demonstrate custom persistent buttons."""
        
        # Create a custom view
        view = PersistentView(self.context)
        
        # Add custom buttons
        view.add_button(
            handler_name='StatsNavigationHandler',
            user_id=ctx.author.id,
            action=ButtonAction.NAVIGATE,
            data={
                'direction': 'next',
                'page': 0,
                'total': 3,
                'target_user_id': ctx.author.id
            },
            guild_id=ctx.guild.id if ctx.guild else None,
            expires_in=timedelta(minutes=30)
        )
        
        view.add_button(
            handler_name='LeaderboardToggleHandler',
            user_id=ctx.author.id,
            action=ButtonAction.TOGGLE,
            data={'scope': 'server'},
            guild_id=ctx.guild.id if ctx.guild else None,
            expires_in=timedelta(hours=1)
        )
        
        embed = discord.Embed(
            title="🔧 Custom UI Example",
            description="This view has custom persistent buttons with different handlers.",
            color=discord.Color.purple()
        )
        
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(PersistentUIExampleCog(bot))


async def setup_with_context(bot, context):
    """Setup function with context (preferred method)."""
    cog = PersistentUIExampleCog(bot)
    cog.set_context(context)
    await bot.add_cog(cog)
    return cog