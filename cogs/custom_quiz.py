import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Optional, Any, Literal, ClassVar
import logging
import datetime
import asyncio
import json
import uuid
from config import load_config

logger = logging.getLogger("bot.custom_quiz")

class QuizCreationModal(discord.ui.Modal, title='Create Custom Quiz'):
    """Modal dialog for creating custom quizzes."""
    
    def __init__(self, cog: 'CustomQuizCog'):
        super().__init__()
        self.cog = cog
    
    quiz_name = discord.ui.TextInput(
        label='Quiz Name',
        placeholder='Enter a name for your quiz',
        required=True,
        max_length=100
    )
    topic = discord.ui.TextInput(
        label='Topic',
        placeholder='What is this quiz about?',
        required=True,
        max_length=100
    )
    questions = discord.ui.TextInput(
        label='Questions (one per line)',
        style=discord.TextStyle.paragraph,
        placeholder='Question 1\nQuestion 2\nQuestion 3',
        required=True
    )
    answers = discord.ui.TextInput(
        label='Answers (one per line)',
        style=discord.TextStyle.paragraph,
        placeholder='Answer 1\nAnswer 2\nAnswer 3',
        required=True
    )
    options = discord.ui.TextInput(
        label='Options (separate by | for each question)',
        style=discord.TextStyle.paragraph,
        placeholder='Option A|Option B|Option C|Option D\nOption A|Option B|Option C|Option D',
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get modal values
            quiz_name = self.quiz_name.value.strip()
            topic = self.topic.value.strip()
            questions_text = self.questions.value.strip().split('\n')
            answers_text = self.answers.value.strip().split('\n')
            options_text = self.options.value.strip().split('\n') if self.options.value else []
            
            # Validate input
            if len(questions_text) != len(answers_text):
                async with interaction.channel.typing():
                    await interaction.followup.send("❌ The number of questions and answers must match.", ephemeral=True)
                return
            
            if len(questions_text) < 1:
                async with interaction.channel.typing():
                    await interaction.followup.send("❌ You must provide at least one question.", ephemeral=True)
                return
            
            # Process questions and answers
            questions_data = []
            for i, (question_text, answer_text) in enumerate(zip(questions_text, answers_text)):
                if not question_text or not answer_text:
                    continue
                
                question_data = {
                    "id": str(uuid.uuid4()),
                    "question": question_text.strip(),
                    "answer": answer_text.strip(),
                    "question_type": "multiple_choice" if options_text and i < len(options_text) else "short_answer",
                    "difficulty": "medium",
                    "category": topic.lower(),
                    "explanation": f"Custom question created by {interaction.user.display_name}."
                }
                
                # Process options if provided
                if options_text and i < len(options_text) and '|' in options_text[i]:
                    options = [opt.strip() for opt in options_text[i].split('|')]
                    question_data["options"] = options
                
                questions_data.append(question_data)
            
            # Store the quiz in database
            guild_id = interaction.guild.id if interaction.guild else None
            quiz_id = await self.cog.db_service.create_custom_quiz(
                creator_id=interaction.user.id,
                guild_id=guild_id,
                name=quiz_name,
                topic=topic,
                questions=questions_data,
                is_public=False
            )
            
            if quiz_id:
                # Create confirmation embed
                embed = discord.Embed(
                    title="✅ Custom Quiz Created",
                    description=f"Your quiz **{quiz_name}** has been created successfully!",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )
                
                embed.add_field(
                    name="Details",
                    value=(
                        f"**Topic:** {topic}\n"
                        f"**Questions:** {len(questions_data)}\n"
                        f"**Quiz ID:** {quiz_id}"
                    ),
                    inline=False
                )
                
                embed.add_field(
                    name="Usage",
                    value=f"Start your custom quiz with: `/quiz custom id:{quiz_id}`",
                    inline=False
                )
                
                async with interaction.channel.typing():
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                async with interaction.channel.typing():
                    await interaction.followup.send("❌ Failed to create quiz. Please try again later.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error creating custom quiz: {e}")
            async with interaction.channel.typing():
                await interaction.followup.send("❌ An error occurred while creating your quiz. Please try again later.", ephemeral=True)

class CustomQuizCog(commands.Cog, name="Custom Quiz"):
    """Commands for creating and managing custom quizzes."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the custom quiz cog."""
        self.bot = bot
        self.config = load_config()
        
        # Set in set_context
        self.context = None
        self.db_service = None
    
    def set_context(self, context: Any) -> None:
        """Set the bot context with all required dependencies."""
        self.context = context
        self.config = context.config
        self.db_service = context.db_service
    
    def _create_quiz_embed(self, quiz: Dict[str, Any], include_questions: bool = False) -> discord.Embed:
        """Create an embed for a custom quiz."""
        embed = discord.Embed(
            title=f"📝 Custom Quiz: {quiz.get('name', 'Unnamed Quiz')}",
            description=f"Topic: {quiz.get('topic', 'General Knowledge')}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        creator_id = quiz.get("creator_id")
        if creator_id:
            try:
                creator = self.bot.get_user(creator_id)
                creator_name = creator.display_name if creator else f"User {creator_id}"
                embed.set_author(name=f"Created by: {creator_name}")
                if creator and creator.avatar:
                    embed.set_thumbnail(url=creator.avatar.url)
            except:
                pass
        
        # Add quiz details
        embed.add_field(
            name="Details",
            value=(
                f"**ID:** {quiz.get('id', 'Unknown')}\n"
                f"**Questions:** {quiz.get('question_count', 0)}\n"
                f"**Visibility:** {'Public' if quiz.get('is_public') else 'Private'}\n"
                f"**Created:** {quiz.get('created_at', 'Unknown')}"
            ),
            inline=False
        )
        
        # Add questions preview if requested
        if include_questions and "questions" in quiz:
            questions = quiz["questions"]
            preview = ""
            
            for i, q in enumerate(questions[:3]):  # Show first 3 questions
                preview += f"**{i+1}.** {q.get('question', 'Unknown question')}\n"
            
            if len(questions) > 3:
                preview += f"\n... and {len(questions) - 3} more questions"
            
            embed.add_field(
                name="Preview",
                value=preview,
                inline=False
            )
        
        embed.set_footer(text=f"ID: {quiz.get('id', 'Unknown')}")
        
        return embed
    
    @commands.hybrid_command(name="create_quiz", description="Create a custom quiz.")
    @app_commands.describe(public="Whether the quiz should be public (default: false)")
    async def create_quiz(self, ctx: commands.Context, public: bool = False):
        """Create a custom quiz using a modal dialog."""
        # Create and send the modal
        modal = QuizCreationModal(self)
        await ctx.interaction.response.send_modal(modal)
    
    @commands.hybrid_command(name="my_quizzes", description="View your custom quizzes.")
    async def my_quizzes(self, ctx: commands.Context):
        """View the custom quizzes you've created."""
        try:
            # Get custom quizzes from database
            quizzes = await self.db_service.get_custom_quizzes(ctx.author.id)
            
            if not quizzes:
                async with ctx.typing():
                    await ctx.send("📝 You haven't created any custom quizzes yet. Use `/create_quiz` to create one!")
                return
            
            # Create embed
            embed = discord.Embed(
                title="📚 Your Custom Quizzes",
                description=f"You have created {len(quizzes)} custom quizzes.",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            
            # Add quizzes to embed
            for i, quiz in enumerate(quizzes[:10]):  # Show top 10
                created_at = quiz.get("created_at", "Unknown")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.datetime.fromisoformat(created_at).strftime("%Y-%m-%d")
                    except:
                        pass
                
                embed.add_field(
                    name=f"{i+1}. {quiz.get('name', 'Unnamed Quiz')}",
                    value=(
                        f"**Topic:** {quiz.get('topic', 'Unknown')}\n"
                        f"**Questions:** {quiz.get('question_count', 0)}\n"
                        f"**Created:** {created_at}\n"
                        f"**ID:** {quiz.get('id', 'Unknown')}"
                    ),
                    inline=True
                )
            
            # Add usage instructions
            embed.add_field(
                name="Usage",
                value=f"Start a custom quiz with: `/quiz custom id:<quiz_id>`",
                inline=False
            )
            
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error fetching custom quizzes for {ctx.author.id}: {e}")
            async with ctx.typing():
                await ctx.send("❌ Error fetching your custom quizzes. Please try again later.", ephemeral=True)
    
    @commands.hybrid_command(name="quiz_info", description="View details about a custom quiz.")
    @app_commands.describe(quiz_id="ID of the custom quiz to view")
    async def quiz_info(self, ctx: commands.Context, quiz_id: int):
        """View detailed information about a specific custom quiz."""
        try:
            # Get custom quiz from database
            quiz = await self.db_service.get_custom_quiz(quiz_id)
            
            if not quiz:
                async with ctx.typing():
                    await ctx.send("❌ Custom quiz not found. Please check the ID and try again.", ephemeral=True)
                return
            
            # Create and send embed
            embed = self._create_quiz_embed(quiz, include_questions=True)
            async with ctx.typing():
                await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error fetching custom quiz {quiz_id}: {e}")
            async with ctx.typing():
                await ctx.send("❌ Error fetching quiz information. Please try again later.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    """Setup function for the cog."""
    await bot.add_cog(CustomQuizCog(bot))

async def setup_with_context(bot: commands.Bot, context: Any) -> commands.Cog:
    """Setup function that uses the context pattern."""
    cog = CustomQuizCog(bot)
    cog.set_context(context)
    await bot.add_cog(cog)
    return cog 