"""Custom help command implementation with consolidated categories."""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Union, Dict
import asyncio

from cogs.base_cog import BaseCog
from utils.ui import create_embed


class SelectCategory(discord.ui.Select):
    """Dropdown menu for selecting command categories."""
    
    def __init__(self, categories: Dict[str, List[commands.Command]]):
        options = []
        
        # Define the order of categories
        category_order = ["Quiz Commands", "Data & Analytics", "User Commands", "Admin Commands", "Owner Commands", "Other Commands"]
        
        for category_name in category_order:
            if category_name in categories and categories[category_name]:
                # Get description based on category
                if category_name == "Quiz Commands":
                    desc = "All quiz-related commands"
                    emoji = "🎯"
                elif category_name == "Data & Analytics":
                    desc = "Stats, leaderboards, and analytics"
                    emoji = "📊"
                elif category_name == "User Commands":
                    desc = "Preferences and user features"
                    emoji = "👤"
                elif category_name == "Admin Commands":
                    desc = "Server administration commands"
                    emoji = "⚙️"
                elif category_name == "Owner Commands":
                    desc = "Bot owner only commands"
                    emoji = "👑"
                else:
                    desc = f"{len(categories[category_name])} commands"
                    emoji = "📂"
                
                options.append(discord.SelectOption(
                    label=category_name,
                    description=desc,
                    emoji=emoji
                ))
        
        # Add 'All Commands' option at the beginning
        options.insert(0, discord.SelectOption(
            label="All Commands",
            description="Show all available commands",
            emoji="📚",
            default=True
        ))
        
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options[:25]  # Discord limit
        )
        self.categories = categories
    
    async def callback(self, interaction: discord.Interaction):
        """Handle category selection."""
        view: HelpView = self.view
        selected = self.values[0]
        
        # Create a new dropdown with the selected option as default
        new_dropdown = SelectCategory(self.categories)
        for option in new_dropdown.options:
            option.default = (option.label == selected)
        
        # Replace the old dropdown with the new one
        view.clear_items()
        view.add_item(new_dropdown)
        
        # Re-add the buttons in the correct order
        for item in [view.guide_button, view.support_button, view.main_menu_button, view.close_button]:
            view.add_item(item)
        
        if selected == "All Commands":
            embed = view.cog.create_all_commands_embed(self.categories)
        else:
            commands_list = self.categories.get(selected, [])
            embed = view.cog.create_category_embed(selected, commands_list)
        
        await interaction.response.edit_message(embed=embed, view=view)


class HelpView(discord.ui.View):
    """Interactive view for help command."""
    
    def __init__(self, cog: 'HelpCog', categories: Dict[str, List[commands.Command]], author_id: int):
        # Set timeout to None for persistent view
        super().__init__(timeout=None)
        self.cog = cog
        self.bot = cog.bot
        self.categories = categories
        self.author_id = author_id
        
        # Create buttons first so they can be referenced
        self.guide_button = self.GuideButton()
        self.support_button = self.SupportButton()
        self.main_menu_button = self.MainMenuButton()
        self.close_button = self.CloseButton()
        
        # Add category selector
        if categories:
            self.add_item(SelectCategory(categories))
        
        # Add buttons
        self.add_item(self.guide_button)
        self.add_item(self.support_button)
        self.add_item(self.main_menu_button)
        self.add_item(self.close_button)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use the buttons."""
        if interaction.user.id != self.author_id:
            async with interaction.channel.typing():
                await interaction.response.send_message(
                    "This help menu is for another user. Use `/help` to open your own!",
                    ephemeral=True
                )
            return False
        return True
    
    class GuideButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Commands Guide", emoji="📖", style=discord.ButtonStyle.primary)
        
        async def callback(self, interaction: discord.Interaction):
            view: HelpView = self.view
            embed = view.cog.create_guide_embed()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class SupportButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Support", emoji="❓", style=discord.ButtonStyle.secondary)
        
        async def callback(self, interaction: discord.Interaction):
            view: HelpView = self.view
            embed = view.cog.create_support_embed()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class MainMenuButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Main Menu", emoji="🏠", style=discord.ButtonStyle.success)
        
        async def callback(self, interaction: discord.Interaction):
            view: HelpView = self.view
            embed = view.cog.create_main_embed()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class CloseButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Close", emoji="❌", style=discord.ButtonStyle.danger)
        
        async def callback(self, interaction: discord.Interaction):
            view: HelpView = self.view
            await interaction.response.defer()
            await interaction.delete_original_response()
            view.stop()


class HelpCog(BaseCog):
    """Custom help command implementation."""
    
    # Cogs to hide from help menu
    HIDDEN_COGS = {
        'GroupQuizSetup',  # Internal helper cog
        'SetupFix',        # Internal helper cog
        'TriviaStartFix',  # Internal helper cog
        'CogLoader',       # Internal utility
        'Version',         # Move to owner commands
    }
    
    # Map cogs to consolidated categories
    COG_CATEGORY_MAP = {
        'Quiz': 'Quiz Commands',
        'Group Quiz': 'Quiz Commands',  # GroupQuizCog registers as "Group Quiz"
        'Custom Quiz': 'Quiz Commands',  # CustomQuizCog registers as "Custom Quiz"
        'Stats': 'Data & Analytics',  # StatsCog registers as "Stats"
        'Preferences': 'User Commands',
        'FAQ': 'User Commands',
        'Admin': 'Admin Commands',
        'GuildPreferences': 'Admin Commands',
        'Onboarding': 'Admin Commands',
    }
    
    # Commands that should be owner-only
    OWNER_COMMANDS = {'broadcast', 'reload', 'shutdown', 'sync', 'version', 'active_servers'}
    
    # Commands to hide completely
    HIDDEN_COMMANDS = set()
    
    # Commands that should be in Data & Analytics
    DATA_COMMANDS = {'stats', 'leaderboard', 'history', 'analytics'}
    
    def __init__(self, bot: commands.Bot):
        """Initialize the help cog."""
        super().__init__(bot, "Help")
        # Remove default help command if it exists
        bot.remove_command('help')
    
    def get_command_categories(self, ctx: commands.Context) -> Dict[str, List[commands.Command]]:
        """Organize commands into categories based on user permissions."""
        categories = {}
        user_is_owner = ctx.author.id == self.config.owner_id if self.config else False
        processed_commands = set()  # Track processed commands to avoid duplicates
        
        for command in self.bot.commands:
            # Skip if already processed
            if command.qualified_name in processed_commands:
                continue
                
            # Skip hidden commands
            if command.hidden:
                continue
            
            # Skip explicitly hidden commands
            if command.name in self.HIDDEN_COMMANDS:
                continue
            
            # Skip owner commands if user is not owner
            if command.name in self.OWNER_COMMANDS and not user_is_owner:
                continue
            
            # Skip commands from hidden cogs
            if command.cog and command.cog.qualified_name in self.HIDDEN_COGS:
                continue
            
            # Determine category
            if command.name in self.OWNER_COMMANDS:
                category = "Owner Commands"
            elif command.name in self.DATA_COMMANDS:
                category = "Data & Analytics"
            elif command.cog:
                cog_name = command.cog.qualified_name
                # Try both the qualified name and the class name
                if cog_name not in self.COG_CATEGORY_MAP:
                    # Try the class name without "Cog" suffix
                    cog_class_name = command.cog.__class__.__name__
                    category = self.COG_CATEGORY_MAP.get(cog_class_name, self.COG_CATEGORY_MAP.get(cog_name, "Other Commands"))
                else:
                    category = self.COG_CATEGORY_MAP.get(cog_name, "Other Commands")
            else:
                category = "Other Commands"
            
            # Add to category
            if category not in categories:
                categories[category] = []
            
            # For group commands, don't add the group itself, just its subcommands
            if isinstance(command, commands.Group):
                for subcommand in command.commands:
                    if not subcommand.hidden and subcommand.qualified_name not in processed_commands:
                        categories[category].append(subcommand)
                        processed_commands.add(subcommand.qualified_name)
            else:
                categories[category].append(command)
                processed_commands.add(command.qualified_name)
        
        # Sort commands within each category by qualified name
        for category in categories:
            categories[category].sort(key=lambda x: x.qualified_name)
        
        return categories
    
    @commands.hybrid_command(name="help", description="Shows help information about the bot and its commands")
    @app_commands.describe(entity="The command or category to get help for")
    async def help(self, ctx: commands.Context, *, entity: Optional[str] = None):
        """
        Shows help information about the bot and its commands.
        
        Usage:
        - `!help` - Show all commands with interactive menu
        - `!help <command>` - Show help for a specific command
        - `!help <category>` - Show all commands in a category
        
        Example:
        - `!help quiz`
        - `!help User Commands`
        """
        if entity:
            # Check if it's a command
            command = self.bot.get_command(entity)
            if command:
                # Check if user can see this command
                if command.name in self.OWNER_COMMANDS and ctx.author.id != (self.config.owner_id if self.config else None):
                    embed = self.create_error_embed("You don't have permission to view this command.")
                else:
                    embed = self.create_command_embed(command)
                async with ctx.typing():
                    await ctx.send(embed=embed)
                return
            
            # Check if it's a category
            categories = self.get_command_categories(ctx)
            entity_title = entity.title()
            
            # Map common variations
            category_aliases = {
                "Quiz": "Quiz Commands",
                "Quizzes": "Quiz Commands",
                "User": "User Commands",
                "Admin": "Admin Commands",
                "Owner": "Owner Commands",
            }
            
            category_name = category_aliases.get(entity_title, entity_title)
            
            if category_name in categories:
                embed = self.create_category_embed(category_name, categories[category_name])
                async with ctx.typing():
                    await ctx.send(embed=embed)
                return
            
            # Neither command nor category found
            embed = self.create_error_embed(f"No command or category named '{entity}' found.")
            async with ctx.typing():
                await ctx.send(embed=embed)
        else:
            # Show interactive help menu
            categories = self.get_command_categories(ctx)
            embed = self.create_main_embed()
            view = HelpView(self, categories, ctx.author.id)
            async with ctx.typing():
                await ctx.send(embed=embed, view=view)
    
    def create_main_embed(self) -> discord.Embed:
        """Create the main help embed."""
        embed = create_embed(
            title="📚 Bot Help",
            description=(
                f"Welcome to {self.bot.user.name}!\n\n"
                "I'm an educational quiz bot that uses AI to generate questions. "
                "Use the dropdown menu below to explore different command categories, "
                "or use the buttons for guides and support.\n\n"
                f"**Prefix:** `{self.bot.command_prefix}`\n"
                f"**Total Commands:** {len(list(self.bot.commands))}\n"
            ),
            color=discord.Color.blue()
        )
        
        # Add quick start
        embed.add_field(
            name="🚀 Quick Start",
            value=(
                "• `!quiz start <topic>` - Start a quiz\n"
                "• `!trivia start <topic>` - Start group trivia\n"
                "• `!stats` - View your statistics\n"
                "• `!help <command>` - Get help for a command\n"
            ),
            inline=False
        )
        
        # Add tips
        embed.add_field(
            name="💡 Tips",
            value=(
                "• Most commands have slash command versions\n"
                "• Use the dropdown to browse categories\n"
                "• Commands are case-insensitive\n"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Use {self.bot.command_prefix}help <command> for detailed help")
        return embed
    
    def create_all_commands_embed(self, categories: Dict[str, List[commands.Command]]) -> discord.Embed:
        """Create embed showing all commands grouped by category."""
        embed = create_embed(
            title="📚 All Commands",
            description="Here are all available commands grouped by category:",
            color=discord.Color.blue()
        )
        
        # Define the order of categories
        category_order = ["Quiz Commands", "Data & Analytics", "User Commands", "Admin Commands", "Owner Commands", "Other Commands"]
        
        for category_name in category_order:
            if category_name not in categories or not categories[category_name]:
                continue
            
            commands_list = categories[category_name]
            
            # Format commands
            cmd_texts = []
            for cmd in commands_list:
                if isinstance(cmd, commands.Group):
                    cmd_texts.append(f"`{cmd.name}*`")
                else:
                    # Show full qualified name for subcommands
                    if hasattr(cmd, 'parent') and cmd.parent:
                        cmd_texts.append(f"`{cmd.qualified_name}`")
                    else:
                        cmd_texts.append(f"`{cmd.name}`")
            
            # Choose emoji based on category
            if category_name == "Quiz Commands":
                emoji = "🎯"
            elif category_name == "Data & Analytics":
                emoji = "📊"
            elif category_name == "User Commands":
                emoji = "👤"
            elif category_name == "Admin Commands":
                emoji = "⚙️"
            elif category_name == "Owner Commands":
                emoji = "👑"
            else:
                emoji = "📂"
            
            # Add field
            cmd_text = " • ".join(cmd_texts)
            if len(cmd_text) > 1024:
                cmd_text = cmd_text[:1021] + "..."
            
            embed.add_field(
                name=f"{emoji} {category_name}",
                value=cmd_text,
                inline=False
            )
        
        embed.set_footer(text="Commands marked with * are groups with subcommands")
        return embed
    
    def create_category_embed(self, category_name: str, commands_list: List[commands.Command]) -> discord.Embed:
        """Create embed for a specific category."""
        # Choose emoji based on category
        if category_name == "Quiz Commands":
            emoji = "🎯"
            description = "Commands for starting and managing quizzes"
        elif category_name == "Data & Analytics":
            emoji = "📊"
            description = "View statistics, leaderboards, history, and analytics"
        elif category_name == "User Commands":
            emoji = "👤"
            description = "Commands for preferences and user features"
        elif category_name == "Admin Commands":
            emoji = "⚙️"
            description = "Commands for server administration"
        elif category_name == "Owner Commands":
            emoji = "👑"
            description = "Commands restricted to the bot owner"
        else:
            emoji = "📂"
            description = "Miscellaneous commands"
        
        embed = create_embed(
            title=f"{emoji} {category_name}",
            description=description,
            color=discord.Color.blue()
        )
        
        if commands_list:
            for command in commands_list:
                # Get command signature
                signature = self.get_command_signature(command)
                
                # Add field for each command
                embed.add_field(
                    name=signature,
                    value=command.short_doc or "No description available.",
                    inline=False
                )
        else:
            embed.description += "\n\n*No commands in this category.*"
        
        return embed
    
    def create_command_embed(self, command: commands.Command) -> discord.Embed:
        """Create embed for a specific command."""
        embed = create_embed(
            title=f"Command: {command.name}",
            description=command.help or command.description or "No description available.",
            color=discord.Color.blue()
        )
        
        # Add usage
        signature = self.get_command_signature(command)
        embed.add_field(name="Usage", value=f"`{signature}`", inline=False)
        
        # Add aliases
        if command.aliases:
            embed.add_field(
                name="Aliases",
                value=" • ".join([f"`{alias}`" for alias in command.aliases]),
                inline=False
            )
        
        # Add cooldown info
        if command._max_concurrency:
            embed.add_field(
                name="Cooldown",
                value=f"{command._max_concurrency.number} uses per {command._max_concurrency.per.name}",
                inline=False
            )
        
        # Add permissions
        if hasattr(command, 'brief') and command.brief:
            embed.add_field(name="Note", value=command.brief, inline=False)
        
        # For command groups, show subcommands
        if isinstance(command, commands.Group):
            subcommands = sorted(command.commands, key=lambda x: x.name)
            if subcommands:
                sub_text = []
                for sub in subcommands:
                    sub_sig = f"{command.name} {sub.name}"
                    if sub.signature:
                        sub_sig += f" {sub.signature}"
                    sub_text.append(f"`{sub_sig}` - {sub.short_doc or 'No description'}")
                
                embed.add_field(
                    name="Subcommands",
                    value="\n".join(sub_text),
                    inline=False
                )
        
        # Add examples if available
        if hasattr(command.callback, '__doc__') and command.callback.__doc__:
            doc = command.callback.__doc__
            if "Example:" in doc:
                example_text = doc.split("Example:")[1].strip().split("\n")[0]
                embed.add_field(name="Example", value=example_text, inline=False)
        
        return embed
    
    def create_guide_embed(self) -> discord.Embed:
        """Create embed with commands guide."""
        embed = create_embed(
            title="📖 Commands Guide",
            description="Learn how to use the bot effectively!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🎮 Getting Started",
            value=(
                "1. Use `!quiz start <topic>` to start a solo quiz\n"
                "2. Use `!trivia start <topic>` for group trivia\n"
                "3. Answer questions using reactions or text\n"
                "4. Track your progress with `!stats`\n"
                "5. Compete on the `!leaderboard`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📝 Command Syntax",
            value=(
                "• `<required>` - Required parameter\n"
                "• `[optional]` - Optional parameter\n"
                "• `...` - Multiple parameters allowed\n"
                "• `command*` - Command group with subcommands"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎯 Popular Commands",
            value=(
                "• `!quiz start <topic>` - Start a quiz session\n"
                "• `!trivia start <topic>` - Start group trivia\n"
                "• `!trivia stop` - Stop current trivia\n"
                "• `!stats` - View your statistics\n"
                "• `!preferences` - Set your preferences\n"
                "• `!leaderboard` - View server rankings\n"
                "• `!help <command>` - Get detailed help"
            ),
            inline=False
        )
        
        return embed
    
    def create_support_embed(self) -> discord.Embed:
        """Create embed with support information."""
        embed = create_embed(
            title="❓ Support",
            description="Need help or have questions?",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="🐛 Report Issues",
            value=(
                "Found a bug? Let us know!\n"
                "• Use `!feedback` command\n"
                "• Contact server admins\n"
                "• Check pinned messages"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Feature Requests",
            value=(
                "Have an idea for improvement?\n"
                "• Use `!suggest` command\n"
                "• Discuss in general chat\n"
                "• Vote on community polls"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔗 Useful Links",
            value=(
                "• [Getting Started Guide](https://github.com/anthropics/claude-code/issues)\n"
                "• [Command Reference](https://docs.anthropic.com/en/docs/claude-code)\n"
                "• Join our support server for help!"
            ),
            inline=False
        )
        
        return embed
    
    def create_error_embed(self, error_message: str) -> discord.Embed:
        """Create error embed."""
        return create_embed(
            title="❌ Error",
            description=error_message,
            color=discord.Color.red()
        )
    
    def get_command_signature(self, command: commands.Command) -> str:
        """Get formatted command signature."""
        # For subcommands, show the full qualified name
        parts = [command.qualified_name]
        
        if command.signature:
            parts.append(command.signature)
        
        return f"{self.bot.command_prefix}{' '.join(parts)}"
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Suggest help command on command errors."""
        if isinstance(error, commands.CommandNotFound):
            # Extract the command name from the error
            command_name = str(error).split('"')[1]
            
            # Find similar commands
            similar = []
            for cmd in self.bot.commands:
                if cmd.hidden:
                    continue
                if command_name.lower() in cmd.name.lower() or cmd.name.lower() in command_name.lower():
                    similar.append(cmd.name)
            
            embed = self.create_error_embed(f"Command '{command_name}' not found.")
            
            if similar:
                embed.add_field(
                    name="Did you mean:",
                    value=" • ".join([f"`{cmd}`" for cmd in similar[:5]]),
                    inline=False
                )
            
            embed.add_field(
                name="💡 Tip",
                value=f"Use `{ctx.prefix}help` to see all available commands.",
                inline=False
            )
            
            async with ctx.typing():
                await ctx.send(embed=embed, ephemeral=True)
            return
        
        # Let other error handlers deal with other errors
        pass


async def setup(bot: commands.Bot):
    """Setup the help cog."""
    cog = HelpCog(bot)
    await bot.add_cog(cog)
    return cog


async def setup_with_context(bot: commands.Bot, context) -> commands.Cog:
    """Setup with context pattern."""
    cog = HelpCog(bot)
    cog.set_context(context)
    await bot.add_cog(cog)
    return cog