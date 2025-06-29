"""
Standardized Modal Framework for Discord.py 2.5.2

This module provides a comprehensive OOP modal system with validation,
error handling, and consistent patterns. Designed to work seamlessly
with the unified persistent UI system.
"""

import logging
from typing import Dict, Any, Optional, List, Union, Callable, Awaitable
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass

import discord
from discord.ext import commands

from utils.context import BotContext
from utils.ui import create_embed
from cogs.utils.embeds import create_error_embed
from utils.errors import BotError, log_exception


class ModalType(Enum):
    """Types of modals for categorization and styling."""
    FORM = "form"           # Data collection forms
    CONFIRMATION = "confirm" # Confirmation dialogs
    SETTINGS = "settings"   # Configuration modals
    CREATION = "creation"   # Content creation modals
    FEEDBACK = "feedback"   # User feedback modals


class ValidationResult:
    """Result of modal input validation."""
    
    def __init__(self, is_valid: bool, errors: Optional[List[str]] = None, warnings: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
    
    def add_error(self, error: str) -> None:
        """Add a validation error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a validation warning."""
        self.warnings.append(warning)
    
    def get_error_message(self) -> str:
        """Get formatted error message for display."""
        if not self.errors:
            return ""
        
        if len(self.errors) == 1:
            return f"❌ {self.errors[0]}"
        
        error_list = "\n".join(f"• {error}" for error in self.errors)
        return f"❌ **Validation Errors:**\n{error_list}"
    
    def get_warning_message(self) -> str:
        """Get formatted warning message for display."""
        if not self.warnings:
            return ""
        
        if len(self.warnings) == 1:
            return f"⚠️ {self.warnings[0]}"
        
        warning_list = "\n".join(f"• {warning}" for warning in self.warnings)
        return f"⚠️ **Warnings:**\n{warning_list}"


@dataclass
class ModalField:
    """Configuration for a modal input field."""
    key: str
    label: str
    placeholder: Optional[str] = None
    required: bool = True
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    style: discord.TextStyle = discord.TextStyle.short
    default_value: Optional[str] = None
    validator: Optional[Callable[[str], ValidationResult]] = None


class BaseModal(discord.ui.Modal, ABC):
    """
    Abstract base class for all standardized modals.
    
    Provides common functionality including validation, error handling,
    and consistent user experience patterns.
    """
    
    def __init__(self, 
                 context: BotContext,
                 title: str,
                 modal_type: ModalType = ModalType.FORM,
                 timeout: Optional[float] = 300):
        super().__init__(title=title, timeout=timeout)
        self.context = context
        self.modal_type = modal_type
        self.logger = logging.getLogger(f"Modal.{self.__class__.__name__}")
        
        # Track field values for validation
        self._field_values: Dict[str, str] = {}
        self._validation_result: Optional[ValidationResult] = None
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission with validation and error handling."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Extract field values
            self._extract_field_values()
            
            # Validate inputs
            validation_result = await self.validate_inputs()
            self._validation_result = validation_result
            
            if not validation_result.is_valid:
                # Show validation errors
                await interaction.followup.send(
                    validation_result.get_error_message(),
                    ephemeral=True
                )
                return
            
            # Show warnings if any
            if validation_result.warnings:
                await interaction.followup.send(
                    validation_result.get_warning_message(),
                    ephemeral=True
                )
            
            # Process the submission
            await self.handle_submit(interaction)
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def on_timeout(self) -> None:
        """Handle modal timeout."""
        self.logger.info(f"Modal {self.__class__.__name__} timed out")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors."""
        await self.handle_error(interaction, error)
    
    def _extract_field_values(self) -> None:
        """Extract values from all modal fields."""
        self._field_values.clear()
        
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                self._field_values[child.label] = child.value or ""
    
    def get_field_value(self, field_key: str) -> str:
        """Get the value of a specific field."""
        return self._field_values.get(field_key, "")
    
    async def validate_inputs(self) -> ValidationResult:
        """
        Validate all modal inputs.
        Override this method to add custom validation logic.
        """
        result = ValidationResult(True)
        
        # Basic validation for required fields
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                value = child.value or ""
                
                if child.required and not value.strip():
                    result.add_error(f"{child.label} is required")
                
                if child.max_length and len(value) > child.max_length:
                    result.add_error(f"{child.label} must be {child.max_length} characters or less")
                
                if child.min_length and len(value) < child.min_length:
                    result.add_error(f"{child.label} must be at least {child.min_length} characters")
        
        return result
    
    @abstractmethod
    async def handle_submit(self, interaction: discord.Interaction) -> None:
        """
        Handle successful modal submission.
        Override this method to implement modal-specific logic.
        """
        pass
    
    async def handle_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle errors that occur during modal processing."""
        self.logger.error(f"Error in modal {self.__class__.__name__}: {error}", exc_info=True)
        log_exception(error, context={"modal": self.__class__.__name__, "values": self._field_values})
        
        error_message = "❌ An error occurred while processing your request. Please try again."
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        except Exception as follow_error:
            self.logger.error(f"Failed to send error message: {follow_error}")


class ConfirmationModal(BaseModal):
    """Modal for confirmation dialogs with custom reasoning."""
    
    def __init__(self, 
                 context: BotContext,
                 title: str,
                 prompt: str,
                 confirmation_callback: Callable[[discord.Interaction, str], Awaitable[None]],
                 required_confirmation: Optional[str] = None):
        super().__init__(context, title, ModalType.CONFIRMATION)
        
        self.confirmation_callback = confirmation_callback
        self.required_confirmation = required_confirmation
        
        # Add confirmation field
        self.confirmation_input = discord.ui.TextInput(
            label="Confirmation",
            placeholder=f"Type '{required_confirmation}' to confirm" if required_confirmation else "Please confirm your action",
            required=True,
            max_length=100
        )
        self.add_item(self.confirmation_input)
        
        # Add reasoning field
        self.reason_input = discord.ui.TextInput(
            label="Reason (Optional)",
            placeholder=prompt,
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.reason_input)
    
    async def validate_inputs(self) -> ValidationResult:
        """Validate confirmation input."""
        result = await super().validate_inputs()
        
        if self.required_confirmation:
            confirmation = self.confirmation_input.value.strip()
            if confirmation != self.required_confirmation:
                result.add_error(f"You must type '{self.required_confirmation}' to confirm")
        
        return result
    
    async def handle_submit(self, interaction: discord.Interaction) -> None:
        """Handle confirmation submission."""
        reason = self.reason_input.value or "No reason provided"
        await self.confirmation_callback(interaction, reason)


class FormModal(BaseModal):
    """Generic form modal that can be configured with fields."""
    
    def __init__(self, 
                 context: BotContext,
                 title: str,
                 fields: List[ModalField],
                 submit_callback: Callable[[discord.Interaction, Dict[str, str]], Awaitable[None]]):
        super().__init__(context, title, ModalType.FORM)
        
        self.submit_callback = submit_callback
        self.field_configs = {field.key: field for field in fields}
        
        # Add fields to modal
        for field in fields[:5]:  # Discord limit of 5 fields per modal
            text_input = discord.ui.TextInput(
                label=field.label,
                placeholder=field.placeholder,
                required=field.required,
                max_length=field.max_length,
                style=field.style,
                default=field.default_value
            )
            self.add_item(text_input)
    
    async def validate_inputs(self) -> ValidationResult:
        """Validate form inputs using field validators."""
        result = await super().validate_inputs()
        
        # Run custom validators
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                field_config = None
                for config in self.field_configs.values():
                    if config.label == child.label:
                        field_config = config
                        break
                
                if field_config and field_config.validator:
                    value = child.value or ""
                    field_result = field_config.validator(value)
                    
                    result.errors.extend(field_result.errors)
                    result.warnings.extend(field_result.warnings)
                    
                    if not field_result.is_valid:
                        result.is_valid = False
        
        return result
    
    async def handle_submit(self, interaction: discord.Interaction) -> None:
        """Handle form submission."""
        # Create field value mapping using keys
        values = {}
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                for key, config in self.field_configs.items():
                    if config.label == child.label:
                        values[key] = child.value or ""
                        break
        
        await self.submit_callback(interaction, values)


# Pre-built Common Modals
class QuizCreationModal(FormModal):
    """Standardized modal for creating custom quizzes."""
    
    def __init__(self, context: BotContext, submit_callback: Callable[[discord.Interaction, Dict[str, str]], Awaitable[None]]):
        fields = [
            ModalField(
                key="name",
                label="Quiz Name",
                placeholder="Enter a name for your quiz",
                max_length=100,
                validator=self._validate_quiz_name
            ),
            ModalField(
                key="topic",
                label="Topic",
                placeholder="What is this quiz about?",
                max_length=100
            ),
            ModalField(
                key="questions",
                label="Questions (one per line)",
                style=discord.TextStyle.paragraph,
                placeholder="Question 1\nQuestion 2\nQuestion 3",
                validator=self._validate_questions
            ),
            ModalField(
                key="answers",
                label="Answers (one per line)",
                style=discord.TextStyle.paragraph,
                placeholder="Answer 1\nAnswer 2\nAnswer 3",
                validator=self._validate_answers
            ),
            ModalField(
                key="options",
                label="Options (optional, | separated)",
                style=discord.TextStyle.paragraph,
                placeholder="Option A|Option B|Option C|Option D",
                required=False
            )
        ]
        
        super().__init__(context, "Create Custom Quiz", fields, submit_callback)
    
    def _validate_quiz_name(self, value: str) -> ValidationResult:
        """Validate quiz name."""
        result = ValidationResult(True)
        
        if len(value.strip()) < 3:
            result.add_error("Quiz name must be at least 3 characters long")
        
        if any(char in value for char in ['<', '>', '@', '#']):
            result.add_error("Quiz name cannot contain special characters")
        
        return result
    
    def _validate_questions(self, value: str) -> ValidationResult:
        """Validate questions format."""
        result = ValidationResult(True)
        
        questions = [q.strip() for q in value.split('\n') if q.strip()]
        
        if len(questions) < 1:
            result.add_error("You must provide at least one question")
        elif len(questions) > 20:
            result.add_error("Maximum 20 questions allowed")
        
        for i, question in enumerate(questions, 1):
            if len(question) < 5:
                result.add_error(f"Question {i} is too short (minimum 5 characters)")
            elif len(question) > 500:
                result.add_error(f"Question {i} is too long (maximum 500 characters)")
        
        return result
    
    def _validate_answers(self, value: str) -> ValidationResult:
        """Validate answers format."""
        result = ValidationResult(True)
        
        answers = [a.strip() for a in value.split('\n') if a.strip()]
        questions = [q.strip() for q in self.get_field_value("questions").split('\n') if q.strip()]
        
        if len(answers) != len(questions):
            result.add_error("Number of answers must match number of questions")
        
        for i, answer in enumerate(answers, 1):
            if len(answer) < 1:
                result.add_error(f"Answer {i} cannot be empty")
            elif len(answer) > 200:
                result.add_error(f"Answer {i} is too long (maximum 200 characters)")
        
        return result


class FeedbackModal(FormModal):
    """Modal for collecting user feedback."""
    
    def __init__(self, context: BotContext, submit_callback: Callable[[discord.Interaction, Dict[str, str]], Awaitable[None]]):
        fields = [
            ModalField(
                key="category",
                label="Feedback Category",
                placeholder="Bug Report, Feature Request, General Feedback, etc.",
                max_length=50
            ),
            ModalField(
                key="summary",
                label="Brief Summary",
                placeholder="Short description of your feedback",
                max_length=100
            ),
            ModalField(
                key="details",
                label="Detailed Feedback",
                style=discord.TextStyle.paragraph,
                placeholder="Please provide detailed information about your feedback...",
                max_length=1000
            ),
            ModalField(
                key="contact",
                label="Contact Information (Optional)",
                placeholder="Discord username, email, etc. (if you want a response)",
                required=False,
                max_length=100
            )
        ]
        
        super().__init__(context, "Submit Feedback", fields, submit_callback)


# Modal Factory Functions
def create_confirmation_modal(context: BotContext,
                            title: str,
                            prompt: str,
                            callback: Callable[[discord.Interaction, str], Awaitable[None]],
                            required_text: Optional[str] = None) -> ConfirmationModal:
    """Factory function for creating confirmation modals."""
    return ConfirmationModal(context, title, prompt, callback, required_text)


def create_quiz_modal(context: BotContext,
                     callback: Callable[[discord.Interaction, Dict[str, str]], Awaitable[None]]) -> QuizCreationModal:
    """Factory function for creating quiz creation modals."""
    return QuizCreationModal(context, callback)


def create_feedback_modal(context: BotContext,
                         callback: Callable[[discord.Interaction, Dict[str, str]], Awaitable[None]]) -> FeedbackModal:
    """Factory function for creating feedback modals."""
    return FeedbackModal(context, callback)


# Integration with Unified UI System
class ModalHandler:
    """Handler for triggering modals from persistent buttons."""
    
    def __init__(self, context: BotContext):
        self.context = context
        self.logger = logging.getLogger("ModalHandler")
    
    async def show_modal(self, interaction: discord.Interaction, modal: BaseModal) -> None:
        """Show a modal in response to interaction."""
        try:
            await interaction.response.send_modal(modal)
        except Exception as e:
            self.logger.error(f"Failed to show modal: {e}")
            await interaction.response.send_message(
                "❌ Unable to open the requested form. Please try again.",
                ephemeral=True
            )


# Utility Functions
def validate_email(email: str) -> ValidationResult:
    """Validate email format."""
    import re
    result = ValidationResult(True)
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        result.add_error("Please enter a valid email address")
    
    return result


def validate_url(url: str) -> ValidationResult:
    """Validate URL format."""
    import re
    result = ValidationResult(True)
    
    url_pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
    if not re.match(url_pattern, url):
        result.add_error("Please enter a valid URL")
    
    return result


def validate_discord_tag(tag: str) -> ValidationResult:
    """Validate Discord username format."""
    import re
    result = ValidationResult(True)
    
    # Modern Discord usernames (no discriminator) or legacy format
    if '#' in tag:
        # Legacy format: username#1234
        if not re.match(r'^.{2,32}#\d{4}$', tag):
            result.add_error("Discord tag must be in format 'username#1234'")
    else:
        # Modern format: just username
        if not re.match(r'^[a-z0-9_.]{2,32}$', tag):
            result.add_error("Discord username must be 2-32 characters (lowercase, numbers, periods, underscores)")
    
    return result