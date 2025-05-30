import os
import json
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple, Type
import importlib.util
import aiohttp

from config import load_config, LLMConfig, OpenAIConfig, AnthropicConfig, GoogleAIConfig
from utils.errors import APIError, ConfigurationError, safe_execute
from utils.decorators import cache_result, time_execution
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("bot.llm")

class Question:
    """Represents a quiz question with its metadata."""
    
    def __init__(
        self,
        question_id: int,
        question: str,
        answer: str,
        explanation: Optional[str] = None,
        options: Optional[List[str]] = None,
        category: str = "general",
        difficulty: str = "medium",
        question_type: str = "multiple_choice"
    ):
        """
        Initialize a Question object.
        
        Args:
            question_id: Unique identifier for the question
            question: The question text
            answer: The correct answer
            explanation: Explanation of the answer (optional)
            options: List of possible answer options for multiple choice questions
            category: Question category (e.g., "science", "history")
            difficulty: Question difficulty level (e.g., "easy", "medium", "hard")
            question_type: Type of question (e.g., "multiple_choice", "true_false", "short_answer")
        """
        self.question_id = question_id
        self.question = question
        self.answer = answer
        self.explanation = explanation
        self.options = options or []
        self.category = category
        self.difficulty = difficulty
        self.question_type = question_type

class TokenOptimizer:
    """Utility for optimizing token usage in LLM requests."""
    
    @staticmethod
    def optimize_prompt(prompt: str, max_tokens: int = 4000) -> str:
        """
        Optimize a prompt to fit within token limits.
        
        Args:
            prompt: The prompt to optimize
            max_tokens: Maximum tokens allowed
            
        Returns:
            Optimized prompt
        """
        # Simple estimation (not perfect but better than nothing)
        # Average English word is ~4-5 characters, and ~1.3 tokens
        char_count = len(prompt)
        estimated_tokens = char_count / 4
        
        if estimated_tokens <= max_tokens:
            return prompt
            
        # Need to truncate
        truncation_ratio = max_tokens / estimated_tokens
        truncated_length = int(char_count * truncation_ratio * 0.9)  # 10% safety margin
        
        # Try to truncate at a sentence boundary
        truncated_prompt = prompt[:truncated_length]
        last_period = truncated_prompt.rfind('.')
        
        if last_period > truncated_length * 0.7:  # If we found a period in the last 30%
            return prompt[:last_period + 1]
        
        return truncated_prompt
    
    @staticmethod
    def batch_requests(items: List[Any], batch_size: int = 5) -> List[List[Any]]:
        """
        Split a list of items into batches for more efficient API calls.
        
        Args:
            items: List of items to batch
            batch_size: Maximum items per batch
            
        Returns:
            List of batches
        """
        return [items[i:i+batch_size] for i in range(0, len(items), batch_size)]

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text from a prompt."""
        pass
    
    @abstractmethod
    def _setup_client(self):
        """Set up the client for the LLM provider."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""
    
    def __init__(self, config: OpenAIConfig):
        self.config = config
        self._setup_client()
        logger.info("Initialized OpenAI provider")
    
    def _setup_client(self):
        """Set up the OpenAI client."""
        try:
            import openai
            self.client = openai
            self.client.api_key = self.config.api_key
        except ImportError:
            logger.error("Failed to import OpenAI library. Make sure it's installed.")
            raise
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using OpenAI."""
        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        
        try:
            # Run in a thread pool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.ChatCompletion.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a helpful educational assistant that creates quiz questions."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating text with OpenAI: {e}")
            raise APIError(
                message=f"OpenAI API error: {str(e)}",
                original_exception=e,
                details={"model": model, "temperature": temperature}
            )


class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider."""
    
    def __init__(self, config: AnthropicConfig):
        self.config = config
        self._setup_client()
        logger.info("Initialized Anthropic provider")
    
    def _setup_client(self):
        """Set up the Anthropic client."""
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.config.api_key)
        except ImportError:
            logger.error("Failed to import Anthropic library. Make sure it's installed.")
            raise
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using Anthropic."""
        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        
        try:
            # Run in a thread pool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    system="You are a helpful educational assistant that creates quiz questions.",
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            )
            
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error generating text with Anthropic: {e}")
            raise APIError(
                message=f"Anthropic API error: {str(e)}",
                original_exception=e,
                details={"model": model, "temperature": temperature}
            )


class GoogleAIProvider(LLMProvider):
    """Google AI LLM provider."""
    
    def __init__(self, config: GoogleAIConfig):
        self.config = config
        self._setup_client()
        logger.info(f"Initialized Google AI provider with configured model: {self.config.model}")
    
    def _setup_client(self):
        """Set up the Google AI client."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.config.api_key)
            self.client = genai
        except ImportError:
            logger.error("Failed to import Google Generative AI library. Make sure it's installed.")
            raise
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using Google AI."""
        # Model determination: prioritize kwargs, then the already-loaded self.config.model
        model_name = kwargs.get("model")
        
        # If model is None, explicitly use the instance config model
        if not model_name:
            model_name = self.config.model if self.config.model else "gemini-1.5-flash-latest"
            logger.debug(f"No model specified in kwargs, using instance model: {model_name}")
        
        # Validate the determined model name. It MUST be a valid string from config.
        if not model_name or not isinstance(model_name, str):
            logger.critical(
                f"CRITICAL: Google AI model name is None or invalid after config load and kwargs check. "
                f"Value received: {model_name}. This indicates a problem with config loading or Pydantic validation."
            )
            # Fallback to a default instead of raising an error
            model_name = "gemini-1.5-flash-latest"
            logger.warning(f"Using fallback model: {model_name}")
        
        # Temperature and max_tokens validation (remains the same)
        temperature = kwargs.get("temperature", self.config.temperature)
        if not isinstance(temperature, (float, int)):
            logger.warning(f"Invalid temperature type ({type(temperature)}), defaulting to {self.config.temperature}")
            temperature = self.config.temperature
        
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        if not isinstance(max_tokens, int):
            logger.warning(f"Invalid max_tokens type ({type(max_tokens)}), defaulting to {self.config.max_tokens}")
            max_tokens = self.config.max_tokens
        
        try:
            # Ensure prompt is not None or empty
            if not prompt or not prompt.strip():
                prompt = "Generate a quiz question."
                logger.warning("Received empty prompt in GoogleAIProvider, using default prompt.")
            
            # Create a well-formed prompt
            combined_prompt = "You are a helpful educational assistant that creates quiz questions.\n\n" + prompt
            
            # Run in a thread pool
            loop = asyncio.get_event_loop()
            
            try:
                # Log the actual model name being used before the API call
                logger.info(f"Using Google AI model: {model_name}")
                model_obj = self.client.GenerativeModel(model_name=model_name)
                
                # Construct generation_config carefully
                gen_config = {
                    "temperature": float(temperature), # Ensure float
                    "max_output_tokens": int(max_tokens) # Ensure int
                }
                logger.debug(f"Google AI generation config: {gen_config}")
                
                response = await loop.run_in_executor(
                    None,
                    lambda: model_obj.generate_content(
                        combined_prompt,  # Pass a single string
                        generation_config=gen_config # Pass validated config
                    )
                )
                
                if not response:
                    logger.error("Google AI returned empty response")
                    return ""
                
                if not hasattr(response, "text"):
                    logger.error("Google AI response missing 'text' attribute")
                    return ""
                
                return response.text or ""
                
            except Exception as api_error:
                logger.error(f"Error calling Google AI API: {api_error}", exc_info=True)
                if "argument of type 'NoneType' is not iterable" in str(api_error):
                    logger.error("Google AI API received a None value where an iterable was expected. Check config/prompt.")
                return ""
                
        except Exception as e:
            logger.error(f"Error generating text with Google AI: {e}", exc_info=True)
            raise APIError(
                message=f"Google AI API error: {str(e)}",
                original_exception=e,
                details={"model": model_name, "temperature": temperature}
            )
        
        # The response check needs to happen *after* the try/except block for the API call
        if not response:
            logger.error("Google AI returned empty response object")
            return ""
        
        if not hasattr(response, "text"):
            logger.error("Google AI response missing 'text' attribute")
            return ""
            
        return response.text or "" # Final check for None/empty text


class LLMService:
    """Service for generating content using various LLM providers."""
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None, config: Optional[Any] = None):
        """
        Initialize the LLM service.
        
        Args:
            api_keys: Dictionary of API keys for different providers
            config: Optional config object
        """
        self.api_keys = api_keys or {}
        self.config = config or load_config().llm
        self._openai_client = None
        self._anthropic_client = None
        self._google_client = None
        self._available_providers = self._get_available_providers()
    
    def _get_available_providers(self) -> List[str]:
        """
        Get a list of available LLM providers based on API keys.
        
        Returns:
            List of available provider names
        """
        available = []
        
        # Try getting providers from config first
        if hasattr(self, 'config'):
            # Check OpenAI
            if hasattr(self.config, 'openai') and self.config.openai.api_key:
                available.append("openai")
                
            # Check Anthropic
            if hasattr(self.config, 'anthropic') and self.config.anthropic.api_key:
                available.append("anthropic")
                
            # Check Google
            if hasattr(self.config, 'google') and self.config.google.api_key:
                available.append("google")
        
        # If no providers found from config, try API keys
        if not available and self.api_keys:
            # Check for OpenAI
            openai_key = self.api_keys.get("openai") or os.getenv("OPENAI_API_KEY")
            if openai_key:
                available.append("openai")
                
            # Check for Anthropic
            anthropic_key = self.api_keys.get("anthropic") or os.getenv("ANTHROPIC_API_KEY")
            if anthropic_key:
                available.append("anthropic")
                
            # Check for Google
            google_key = self.api_keys.get("google") or os.getenv("GOOGLE_AI_API_KEY")
            if google_key:
                available.append("google")
        
        if not available:
            logger.warning("No LLM providers are available! Make sure API keys are configured.")
            
        logger.info(f"Available LLM providers: {', '.join(available) or 'None'}")
        return available
    
    def get_provider(self, provider_name: str = None) -> Optional[LLMProvider]:
        """
        Get an LLM provider instance by name.
        
        Args:
            provider_name: Name of the provider to get, or None for default
            
        Returns:
            LLM provider instance or None if not available
        """
        # If no provider specified, use the first available one
        available = self._get_available_providers()
        if not provider_name:
            if not available:
                logger.error("No LLM providers available")
                return None
            provider_name = available[0]
        
        # Make sure the requested provider is available
        if provider_name not in available:
            logger.error(f"Requested provider {provider_name} is not available")
            return None
            
        # Return the appropriate provider
        if provider_name == "openai":
            if hasattr(self.config, 'openai'):
                provider_config = self.config.openai
                return OpenAIProvider(provider_config)
            else:
                # Use API key if config not available
                api_key = self.api_keys.get("openai") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.error("OpenAI API key not found")
                    return None
                
                # Create minimal config for provider
                from config import OpenAIConfig
                provider_config = OpenAIConfig(api_key=api_key)
                return OpenAIProvider(provider_config)
                
        elif provider_name == "anthropic":
            if hasattr(self.config, 'anthropic'):
                provider_config = self.config.anthropic
                return AnthropicProvider(provider_config)
            else:
                # Use API key if config not available
                api_key = self.api_keys.get("anthropic") or os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.error("Anthropic API key not found")
                    return None
                
                # Create minimal config for provider
                from config import AnthropicConfig
                provider_config = AnthropicConfig(api_key=api_key)
                return AnthropicProvider(provider_config)
                
        elif provider_name == "google":
            if hasattr(self.config, 'google') and self.config.google.api_key:
                provider_config = self.config.google
                return GoogleAIProvider(provider_config)
            else:
                # Use API key if config not available
                api_key = self.api_keys.get("google") or os.getenv("GOOGLE_AI_API_KEY")
                if not api_key:
                    logger.error("Google API key not found")
                    return None
                
                # Create minimal config for provider
                from config import GoogleAIConfig
                provider_config = GoogleAIConfig(api_key=api_key)
                return GoogleAIProvider(provider_config)
        
        return None
    
    def get_available_providers(self) -> List[str]:
        """
        Get a list of available LLM providers based on API keys and config.
        Ensures that the list is populated correctly on initialization.
        """
        if not hasattr(self, '_available_providers') or not self._available_providers:
            self._available_providers = self._get_available_providers() # Call the internal method
        return self._available_providers

    @property
    def default_provider(self) -> Optional[str]:
        """Get the default LLM provider."""
        if self._available_providers:
            return self._available_providers[0]
        return None

    async def generate_raw_text(self, prompt: str, provider: str, **kwargs) -> str:
        """
        Generates raw text from a given provider using the specified prompt.
        """
        if not provider or provider not in self.get_available_providers(): # Use getter
            logger.error(f"Provider '{provider}' is not available or not specified.")
            default_prov = self.default_provider
            if default_prov:
                logger.warning(f"Falling back to default provider: {default_prov}")
                provider = default_prov
            else:
                raise ConfigurationError(f"Provider '{provider}' not available and no default fallback.")

        model = kwargs.get("model")
        temperature = kwargs.get("temperature", self.config.default_temperature if hasattr(self.config, 'default_temperature') else 0.7)
        max_tokens = kwargs.get("max_tokens", self.config.default_max_tokens if hasattr(self.config, 'default_max_tokens') else 2048)

        provider_instance: Optional[LLMProvider] = None

        if provider == "openai":
            if hasattr(self.config, 'openai') and self.config.openai.api_key:
                provider_instance = OpenAIProvider(self.config.openai)
                # Ensure model is passed to provider
                if not model and hasattr(self.config, 'openai') and self.config.openai.model:
                    kwargs["model"] = self.config.openai.model
            else:
                raise ConfigurationError("OpenAI provider selected, but API key or config is missing.")
        elif provider == "anthropic":
            if hasattr(self.config, 'anthropic') and self.config.anthropic.api_key:
                provider_instance = AnthropicProvider(self.config.anthropic)
                # Ensure model is passed to provider
                if not model and hasattr(self.config, 'anthropic') and self.config.anthropic.model:
                    kwargs["model"] = self.config.anthropic.model
            else:
                raise ConfigurationError("Anthropic provider selected, but API key or config is missing.")
        elif provider == "google":
            if hasattr(self.config, 'google') and self.config.google.api_key:
                # Explicitly pass the model name from config to provider
                if not model and hasattr(self.config, 'google') and self.config.google.model:
                    # Add model to kwargs so it's passed to generate_text
                    kwargs["model"] = self.config.google.model
                    logger.debug(f"Setting Google model from config: {self.config.google.model}")
                
                provider_instance = GoogleAIProvider(self.config.google)
            else:
                raise ConfigurationError("Google provider selected, but API key or config is missing.")
        else:
            raise ConfigurationError(f"Unknown or unconfigured provider: {provider}")

        if not provider_instance:
            # This case should ideally be caught by the initial check, but as a safeguard:
            raise ConfigurationError(f"Failed to initialize provider instance for {provider}.")

        # Log the model being used for clarity
        if "model" in kwargs:
            logger.info(f"Using {provider} model: {kwargs['model']}")
        else:
            logger.warning(f"No model specified for {provider}, will use default")

        # The individual provider's generate_text method should handle its own retry logic if any.
        # For this example, we are not adding explicit retry here, assuming provider methods might have it.
        return await provider_instance.generate_text(
            prompt,
            **kwargs  # Pass all kwargs to maintain any model settings
        )
    
    def _get_openai_client(self):
        """Get or create the OpenAI client."""
        if self._openai_client is None:
            try:
                import openai
                openai_key = self.api_keys.get("openai") or os.getenv("OPENAI_API_KEY")
                if not openai_key:
                    raise ConfigurationError(
                        "OpenAI API key not found. Please set OPENAI_API_KEY environment variable.",
                        details={"provider": "openai"}
                    )
                
                self._openai_client = openai.OpenAI(api_key=openai_key)
                logger.debug("Initialized OpenAI client")
            except ImportError:
                raise ConfigurationError(
                    "OpenAI Python package not installed. Please install it with 'pip install openai'.",
                    details={"provider": "openai"}
                )
            
        return self._openai_client
    
    def _get_anthropic_client(self):
        """Get or create the Anthropic client."""
        if self._anthropic_client is None:
            try:
                import anthropic
                anthropic_key = self.api_keys.get("anthropic") or os.getenv("ANTHROPIC_API_KEY")
                if not anthropic_key:
                    raise ConfigurationError(
                        "Anthropic API key not found. Please set ANTHROPIC_API_KEY environment variable.",
                        details={"provider": "anthropic"}
                    )
                
                self._anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
                logger.debug("Initialized Anthropic client")
            except ImportError:
                raise ConfigurationError(
                    "Anthropic Python package not installed. Please install it with 'pip install anthropic'.",
                    details={"provider": "anthropic"}
                )
            
        return self._anthropic_client
    
    def _get_google_client(self):
        """Get or create the Google client."""
        if self._google_client is None:
            try:
                import google.generativeai as genai
                google_key = self.api_keys.get("google") or os.getenv("GOOGLE_AI_API_KEY")
                if not google_key:
                    raise ConfigurationError(
                        "Google AI API key not found. Please set GOOGLE_AI_API_KEY environment variable.",
                        details={"provider": "google"}
                    )
                
                genai.configure(api_key=google_key)
                self._google_client = genai
                logger.debug("Initialized Google AI client")
            except ImportError:
                raise ConfigurationError(
                    "Google AI Python package not installed. Please install it with 'pip install google-generativeai'.",
                    details={"provider": "google"}
                )
            
        return self._google_client
    
    @time_execution
    @cache_result(expire_seconds=3600, key_prefix="llm_question")
    async def generate_questions(
        self,
        topic: str,
        question_count: int = 5,
        difficulty: str = "medium",
        question_type: str = "multiple_choice",
        category: str = "general",
        provider: str = "openai",
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> List[Question]:
        """
        Generate quiz questions on a given topic.
        
        Args:
            topic: The topic for the questions
            question_count: Number of questions to generate
            difficulty: Difficulty level ("easy", "medium", "hard")
            question_type: Type of questions ("multiple_choice", "true_false", "short_answer")
            category: Question category
            provider: LLM provider to use
            model: Specific model to use (defaults to provider's default)
            temperature: Creativity parameter (0.0 to 1.0)
            
        Returns:
            List of Question objects
            
        Raises:
            ConfigurationError: If provider is not configured
            APIError: If the LLM API request fails
        """
        # Check if the requested provider is available
        if provider not in self._available_providers:
            available = ", ".join(self._available_providers) if self._available_providers else "None"
            raise ConfigurationError(
                f"Provider '{provider}' is not available. Available providers: {available}",
                details={"provider": provider, "available": self._available_providers}
            )
        
        # Optimize question count
        question_count = min(max(1, question_count), 20)  # Hard limit to avoid excessive token usage
        
        # Create prompt for generating questions
        prompt = self._create_question_prompt(
            topic, question_count, difficulty, question_type, category
        )
        
        # Choose provider implementation
        if provider == "openai":
            response = await self._generate_with_openai(prompt, model, temperature)
        elif provider == "anthropic":
            response = await self._generate_with_anthropic(prompt, model, temperature)
        elif provider == "google":
            response = await self._generate_with_google(prompt, model, temperature)
        else:
            raise ConfigurationError(f"Unknown provider: {provider}")
        
        # Parse the response into Question objects
        questions = self._parse_questions(response, question_type, category, difficulty)
        
        # If we got fewer questions than requested, log a warning
        if len(questions) < question_count:
            logger.warning(
                f"Requested {question_count} questions but only parsed {len(questions)}",
                extra={"topic": topic, "provider": provider}
            )
        
        return questions
    
    def _create_question_prompt(
        self, 
        topic: str, 
        question_count: int, 
        difficulty: str, 
        question_type: str,
        category: str
    ) -> str:
        """
        Create a prompt for generating quiz questions.
        
        Args:
            topic: The topic for the questions
            question_count: Number of questions to generate
            difficulty: Difficulty level
            question_type: Type of questions
            category: Question category
            
        Returns:
            Formatted prompt string
        """
        question_type_desc = ""
        if question_type == "multiple_choice":
            question_type_desc = "Each question should have 4 options labeled A, B, C, D with only one correct answer."
        elif question_type == "true_false":
            question_type_desc = "Each question should be answerable with True or False only."
        else:  # short_answer
            question_type_desc = "Each question should have a short answer (1-3 words)."
        
        difficulty_desc = ""
        if difficulty == "easy":
            difficulty_desc = "suitable for beginners"
        elif difficulty == "medium":
            difficulty_desc = "requiring intermediate knowledge"
        else:  # hard
            difficulty_desc = "challenging even for experts"
        
        # The JSON format is easier to parse
        prompt = f"""Generate {question_count} {difficulty} {question_type} questions about {topic} in the category of {category}.
{question_type_desc}
The questions should be {difficulty_desc}.

For each question, provide:
1. The question text
2. The correct answer
3. A brief explanation of why the answer is correct
4. For multiple choice, provide 4 options with only one correct answer

Return the questions in the following JSON format:
{{
  "questions": [
    {{
      "question": "Question text",
      "answer": "Correct answer",
      "explanation": "Explanation of the answer",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "category": "{category}",
      "difficulty": "{difficulty}",
      "question_type": "{question_type}"
    }}
  ]
}}

Only include the raw JSON in your response with no additional text.
"""
        return TokenOptimizer.optimize_prompt(prompt)
    
    async def _generate_with_openai(
        self, 
        prompt: str, 
        model: Optional[str] = None, 
        temperature: float = 0.7
    ) -> str:
        """
        Generate content using the OpenAI API.
        
        Args:
            prompt: The prompt to send
            model: The model to use (e.g., "gpt-4")
            temperature: Creativity parameter
            
        Returns:
            Generated content as a string
            
        Raises:
            APIError: If the API request fails
        """
        client = self._get_openai_client()
        if not model:
            logger.error("OpenAI generation called without a model specified.")
            model = self.config.openai.model # Correct: Use specific provider config
            logger.warning(f"Falling back to configured OpenAI model: {model}")
            if not model: 
                raise ConfigurationError("No valid OpenAI model could be determined.")
        
        try:
            start_time = time.time()
            
            response = await safe_execute(
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=2048,
                    n=1,
                    response_format={"type": "json_object"}
                ),
                error_msg="Failed to generate content with OpenAI",
                context={"model": model, "temperature": temperature},
                reraise=True
            )
            
            elapsed = time.time() - start_time
            logger.info(f"OpenAI API response time: {elapsed:.2f}s for model {model}")
            
            if not response or not hasattr(response, "choices") or not response.choices:
                raise APIError("Empty response from OpenAI API")
                
            content = response.choices[0].message.content.strip()
            return content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise APIError(
                message=f"OpenAI API error: {str(e)}",
                original_exception=e,
                details={"model": model, "temperature": temperature}
            )
    
    async def _generate_with_anthropic(
        self, 
        prompt: str, 
        model: Optional[str] = None, 
        temperature: float = 0.7
    ) -> str:
        """
        Generate content using the Anthropic API.
        
        Args:
            prompt: The prompt to send
            model: The model to use (e.g., "claude-3-opus-20240229")
            temperature: Creativity parameter
            
        Returns:
            Generated content as a string
            
        Raises:
            APIError: If the API request fails
        """
        client = self._get_anthropic_client()
        if not model:
            logger.error("Anthropic generation called without a model specified.")
            model = self.config.anthropic.model # Correct: Use specific provider config
            logger.warning(f"Falling back to configured Anthropic model: {model}")
            if not model:
                raise ConfigurationError("No valid Anthropic model could be determined.")
        
        try:
            start_time = time.time()
            
            response = await safe_execute(
                lambda: client.messages.create(
                    model=model,
                    max_tokens=2048,
                    temperature=temperature,
                    system="You are an education expert creating high-quality questions. Respond in JSON format only.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                ),
                error_msg="Failed to generate content with Anthropic",
                context={"model": model, "temperature": temperature},
                reraise=True
            )
            
            elapsed = time.time() - start_time
            logger.info(f"Anthropic API response time: {elapsed:.2f}s for model {model}")
            
            if not response or not hasattr(response, "content"):
                raise APIError("Empty response from Anthropic API")
                
            content = response.content[0].text
            return content
            
        except Exception as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise APIError(
                message=f"Anthropic API error: {str(e)}",
                original_exception=e,
                details={"model": model, "temperature": temperature}
            )
    
    async def _generate_with_google(
        self, 
        prompt: str, 
        model: Optional[str] = None, 
        temperature: float = 0.7
    ) -> str:
        """
        Generate content using the Google AI API.
        
        Args:
            prompt: The prompt to send
            model: The model to use (e.g., "gemini-1.5-pro")
            temperature: Creativity parameter
            
        Returns:
            Generated content as a string
            
        Raises:
            APIError: If the API request fails
        """
        client = self._get_google_client()
        if not model:
            logger.error("Google generation called without a model specified.")
            model = self.config.google.model # Correct: Use specific provider config
            logger.warning(f"Falling back to configured Google model: {model}")
            if not model:
                raise ConfigurationError("No valid Google model could be determined.")
        
        try:
            start_time = time.time()
            
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": 2048,
            }
            
            model_obj = client.GenerativeModel(model_name=model, generation_config=generation_config)
            
            response = await safe_execute(
                lambda: model_obj.generate_content(prompt),
                error_msg="Failed to generate content with Google AI",
                context={"model": model, "temperature": temperature},
                reraise=True
            )
            
            elapsed = time.time() - start_time
            logger.info(f"Google AI API response time: {elapsed:.2f}s for model {model}")
            
            if not response or not hasattr(response, "text"):
                raise APIError("Empty response from Google AI API")
                
            content = response.text
            return content
            
        except Exception as e:
            logger.error(f"Google AI API error: {str(e)}")
            raise APIError(
                message=f"Google AI API error: {str(e)}",
                original_exception=e,
                details={"model": model, "temperature": temperature}
            )
    
    def _parse_questions(
        self, 
        response: str, 
        question_type: str, 
        category: str, 
        difficulty: str
    ) -> List[Question]:
        """
        Parse the response from the LLM into Question objects.
        
        Args:
            response: The LLM response text
            question_type: Type of questions
            category: Question category
            difficulty: Difficulty level
            
        Returns:
            List of Question objects
        """
        questions = []
        
        try:
            # Extract JSON from the response
            json_start = response.find("{")
            json_end = response.rfind("}")
            
            if json_start == -1 or json_end == -1:
                logger.warning("No JSON found in LLM response", extra={"response": response[:200]})
                return questions
                
            json_str = response[json_start:json_end + 1]
            
            # Parse the JSON
            data = json.loads(json_str)
            
            if not isinstance(data, dict) or "questions" not in data:
                logger.warning("Invalid JSON format in LLM response", extra={"data": str(data)[:200]})
                return questions
                
            for i, q_data in enumerate(data["questions"]):
                # Extract question fields with fallbacks
                q_text = q_data.get("question", "")
                answer = q_data.get("answer", "")
                explanation = q_data.get("explanation", "")
                options = q_data.get("options", [])
                q_type = q_data.get("question_type", question_type)
                q_category = q_data.get("category", category)
                q_difficulty = q_data.get("difficulty", difficulty)
                
                # Skip invalid questions
                if not q_text or not answer:
                    logger.warning(f"Skipping invalid question: {q_data}")
                    continue
                    
                # Create Question object
                question = Question(
                    question_id=i,
                    question=q_text,
                    answer=answer,
                    explanation=explanation,
                    options=options,
                    category=q_category,
                    difficulty=q_difficulty,
                    question_type=q_type
                )
                
                questions.append(question)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            logger.debug(f"LLM response: {response[:500]}")
        except Exception as e:
            logger.error(f"Error parsing questions: {e}")
            
        return questions

    async def generate_quiz_questions(
        self,
        topic: str,
        question_count: int = 5,
        question_type: str = "multiple_choice",
        difficulty: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Generate quiz questions about a specific topic.
        
        Args:
            topic: The topic to generate questions about
            question_count: Number of questions to generate
            question_type: Type of question (e.g., "multiple_choice", "true_false", "short_answer")
            difficulty: Difficulty level of questions
            
        Returns:
            List of question dictionaries
        """
        # Adjust the prompt based on the question type
        if question_type == "multiple_choice":
            prompt = (
                f"Generate {question_count} {difficulty} difficulty multiple choice questions about {topic}.\n\n"
                f"IMPORTANT REQUIREMENTS FOR OPTIONS:\n"
                f"1. Each question MUST have REALISTIC, DISTINCT, and PLAUSIBLE answer options - NOT placeholder text\n"
                f"2. NEVER use generic placeholders like 'Option A' or '{topic} answer 1'\n"
                f"3. Each option should be a complete, specific, and contextually appropriate answer\n"
                f"4. For historical topics, use actual historical figures, places, events, or concepts\n"
                f"5. For scientific topics, use actual scientific terms, theories, or values\n\n"
                f"Format the response as a JSON array of objects. Each object should include:\n"
                f"- question: The question text\n"
                f"- options: Array of 4 possible answers (no letter prefixes like A., B.)\n"
                f"- answer: The correct answer (must exactly match one of the options)\n"
                f"- explanation: Brief explanation of why the answer is correct\n\n"
                f"Example format:\n"
                f"[\n"
                f"  {{\n"
                f"    \"question\": \"Which device was invented by Charles Babbage?\",\n"
                f"    \"options\": [\"Analytical Engine\", \"Transistor\", \"Microprocessor\", \"Vacuum Tube\"],\n"
                f"    \"answer\": \"Analytical Engine\",\n"
                f"    \"explanation\": \"Charles Babbage designed the Analytical Engine in the 1830s as the first general-purpose mechanical computer.\"\n"
                f"  }},\n"
                f"  ...\n"
                f"]\n"
                f"Remember, all options must be REALISTIC answers - never use generic placeholders!"
            )
        elif question_type == "true_false":
            prompt = (
                f"Generate {question_count} {difficulty} difficulty true/false questions about {topic}.\n\n"
                f"Format the response as a JSON array of objects. Each object should include:\n"
                f"- question: The question text (should be phrased as a statement without 'True or False:' prefix)\n"
                f"- answer: Either 'True' or 'False'\n" 
                f"- explanation: Brief explanation of why the statement is true or false\n\n"
                f"Example format:\n"
                f"[\n"
                f"  {{\n"
                f"    \"question\": \"The first programmable computer was invented in the 1940s.\",\n"
                f"    \"answer\": \"False\",\n"
                f"    \"explanation\": \"The first programmable computer was the Z1, invented by Konrad Zuse in 1938.\"\n"
                f"  }},\n"
                f"  ...\n"
                f"]\n"
            )
        else:  # short_answer
            prompt = (
                f"Generate {question_count} {difficulty} difficulty short answer questions about {topic}.\n\n"
                f"Format the response as a JSON array of objects. Each object should include:\n"
                f"- question: The question text\n"
                f"- answer: The correct answer (should be brief, 1-5 words)\n"
                f"- explanation: Brief explanation of the answer\n\n"
                f"Example format:\n"
                f"[\n"
                f"  {{\n"
                f"    \"question\": \"What programming language was created by Guido van Rossum in 1991?\",\n"
                f"    \"answer\": \"Python\",\n"
                f"    \"explanation\": \"Python was created by Guido van Rossum and first released in 1991.\"\n"
                f"  }},\n"
                f"  ...\n"
                f"]\n"
            )
        
        # Get response from the model
        response = await self.generate_text(prompt)
        
        # Extract JSON response
        try:
            # Try to extract the JSON part if the response contains non-JSON text
            response = response.strip()
            if response.startswith("```json"):
                response = response.split("```json")[1].split("```")[0].strip()
            elif response.startswith("```"):
                response = response.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            questions = json.loads(response)
            return questions
        except Exception as e:
            logger.error(f"Failed to parse response as JSON: {e}")
            logger.debug(f"Raw response: {response}")
            raise


# Create a singleton service instance
config = load_config()
llm_service = LLMService(config=config.llm) 