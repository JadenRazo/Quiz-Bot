import os
from typing import Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field, validator, model_validator, field_validator
from dotenv import load_dotenv

# Load environment variables from .env file at the module level
load_dotenv()

# --- Default Prompts ---
# These are used if the corresponding environment variables are not set.

DEFAULT_STANDARD_QUIZ_PROMPT="""Generate a quiz with {num_questions} multiple-choice questions on the topic of '{topic}'.
Each question should have {num_options} options, with only one correct answer.

IMPORTANT RULES ABOUT OPTIONS:
1. All options should be similar in structure, length, and style
2. NEVER include dates, years, or other chronological markers that would make the correct answer obvious
3. For questions asking "which came first" or "when was", provide ONLY the names/places without years
4. Do not add any information in parentheses - present each option as a simple, clean statement
5. Make all options equally plausible to someone who doesn't know the answer
6. If the question involves a sequence or timeline, do not include any chronological hints in the options

For example, if asking "Which Disney park opened first outside the US?", only list park names like:
- Tokyo Disneyland
- Disneyland Paris
- Hong Kong Disneyland
- Shanghai Disneyland

Do NOT list as:
- Tokyo Disneyland (1983) ← This reveals the answer!
- Disneyland Paris (1992)
- Hong Kong Disneyland (2005)
- Shanghai Disneyland (2016)

Format the output as a VALID JSON list of objects, where each object represents a question and has the following keys: 'question' (string), 'options' (list of strings), 'correct_answer' (string - the exact text of the correct option).
Example JSON object:
{{"question": "What is the capital of France?", "options": ["Berlin", "Madrid", "Paris", "Rome"], "correct_answer": "Paris"}}
Ensure the entire output is ONLY the JSON list, starting with '[' and ending with ']'. Do not include any introductory text, explanations, or markdown formatting outside the JSON structure."""

DEFAULT_EDUCATIONAL_QUIZ_PROMPT="""Create an educational quiz with {num_questions} multiple-choice questions about '{topic}' suitable for a {difficulty} level.
Each question must have {num_options} options. Provide one correct answer and include a brief 'explanation' (1-2 sentences) for why the correct answer is right.

IMPORTANT RULES ABOUT OPTIONS:
1. All options should be similar in structure, length, and style
2. NEVER include dates, years, or other chronological markers that would make the correct answer obvious
3. For questions asking "which came first" or "when was", provide ONLY the names/places without years
4. Do not add any information in parentheses - present each option as a simple, clean statement
5. Make all options equally plausible to someone who doesn't know the answer
6. If the question involves a sequence or timeline, do not include any chronological hints in the options

For example, if asking "Which scientist first proposed the theory of general relativity?", only list names like:
- Albert Einstein
- Isaac Newton
- Stephen Hawking
- Nikola Tesla

Do NOT list as:
- Albert Einstein (1915) ← This reveals the answer!
- Isaac Newton (1687)
- Stephen Hawking (1988)
- Nikola Tesla (1900)

Format the output as a VALID JSON list of objects. Each object needs these keys: 'question' (string), 'options' (list of strings), 'correct_answer' (string), 'explanation' (string).
Example JSON object:
{{"question": "What causes seasons on Earth?", "options": ["Earth\'s distance from the sun", "Earth\'s tilt on its axis", "Ocean currents", "Volcanic activity"], "correct_answer": "Earth\'s tilt on its axis", "explanation": "Earth\'s axis is tilted about 23.5 degrees, causing different parts of the planet to receive more direct sunlight at different times of the year."}}
Output ONLY the JSON list, starting with '[' and ending with ']'. No extra text or formatting."""

DEFAULT_CHALLENGE_QUIZ_PROMPT="""Generate a challenging quiz with {num_questions} difficult multiple-choice questions on '{topic}'. Target an expert audience.
Include {num_options} options per question, one correct. Add a 'hint' (string, optional, max 1 short sentence) for particularly tough questions.

IMPORTANT RULES ABOUT OPTIONS:
1. All options should be similar in structure, length, and style
2. NEVER include dates, years, or other chronological markers that would make the correct answer obvious
3. For questions involving historical developments or discoveries, present ONLY the concepts/discoveries without their years
4. Do not add any information in parentheses - present each option as a simple, clean statement
5. All options must be equally professional and plausible-looking to someone with moderate subject knowledge
6. If the question involves a sequence or timeline, do not include any chronological hints in the options

For example, if asking "Which quantum theory was developed first?", only list the theories like:
- Wave mechanics
- Matrix mechanics
- Path integral formulation
- Copenhagen interpretation

Do NOT list as:
- Wave mechanics (1926, Schrödinger) ← This reveals the answer!
- Matrix mechanics (1925, Heisenberg)
- Path integral formulation (1948, Feynman)
- Copenhagen interpretation (1927, Bohr)

Format as a VALID JSON list of objects with keys: 'question' (string), 'options' (list of strings), 'correct_answer' (string), 'hint' (string or null).
Example JSON object:
{{"question": "What is the primary mechanism behind Maxwell\'s demon?", "options": ["Quantum entanglement", "Information theory and entropy reduction", "Brownian motion", "Special relativity"], "correct_answer": "Information theory and entropy reduction", "hint": "Think about the cost of information."}}
Output ONLY the JSON list, starting with '[' and ending with ']'. No extra text."""

DEFAULT_TRIVIA_QUIZ_PROMPT="""Generate a fun trivia quiz with {num_questions} multiple-choice questions covering various general knowledge topics like '{topic}'. Keep it engaging for a group setting.
Provide {num_options} options per question, with one correct answer.

IMPORTANT RULES FOR FAIR TRIVIA OPTIONS:
1. All options must be similar in length, structure, and style
2. NEVER include any dates, years, numbers, or information in parentheses
3. For "which was first" questions, list ONLY names/places/things without any chronological hints
4. All options must be equally plausible to someone who doesn't know the answer
5. For questions about events in sequence, never reveal the order in the options
6. For questions about records, discoveries, or "who was the first", never include dates

EXAMPLES OF BAD OPTIONS (NEVER DO THIS):
For a question "Which Disney park opened first outside the US?":
- Tokyo Disneyland (1983) ← WRONG: Reveals the answer!
- Disneyland Paris (1992) ← WRONG: Reveals the answer!

For a question "Which band had their first hit in the earliest year?":
- The Beatles (1962) ← WRONG: Reveals the answer!
- Queen (1974) ← WRONG: Reveals the answer!

EXAMPLES OF GOOD OPTIONS (DO THIS):
For a question "Which Disney park opened first outside the US?":
- Tokyo Disneyland ← CORRECT: No revealing information
- Disneyland Paris ← CORRECT: No revealing information

For a question "Which band had their first hit in the earliest year?":
- The Beatles ← CORRECT: No revealing information
- Queen ← CORRECT: No revealing information

Format as a VALID JSON list of objects with keys: 'question' (string), 'options' (list of strings), 'correct_answer' (string).
Example JSON object:
{{"question": "In Greek mythology, who flew too close to the sun?", "options": ["Daedalus", "Perseus", "Icarus", "Apollo"], "correct_answer": "Icarus"}}
Output ONLY the JSON list, starting with '[' and ending with ']'. No extra text."""

class OpenAIConfig(BaseModel):
    """Configuration for OpenAI LLM service."""
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"))
    temperature: float = Field(default=0.7, ge=0, le=1)
    max_tokens: int = Field(default=2048, gt=0)
    
    @validator('api_key', pre=True, always=True)
    def validate_api_key(cls, v):
        if not v:
            return os.getenv("OPENAI_API_KEY", "")
        return v

class AnthropicConfig(BaseModel):
    """Configuration for Anthropic LLM service."""
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229"))
    temperature: float = Field(default=0.7, ge=0, le=1)
    max_tokens: int = Field(default=2048, gt=0)
    
    @validator('api_key', pre=True, always=True)
    def validate_api_key(cls, v):
        if not v:
            return os.getenv("ANTHROPIC_API_KEY", "")
        return v

class GoogleAIConfig(BaseModel):
    """Configuration for Google AI LLM service."""
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GOOGLE_AI_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv("GOOGLE_MODEL", "gemini-1.5-flash-latest"))
    temperature: float = Field(default=0.7, ge=0, le=1)
    max_tokens: int = Field(default=4096, gt=0)
    
    @validator('api_key', pre=True, always=True)
    def validate_api_key(cls, v):
        if not v:
            return os.getenv("GOOGLE_AI_API_KEY", "")
        return v

class LLMConfig(BaseModel):
    """Configuration for all LLM services."""
    default_provider: str = Field(default_factory=lambda: os.getenv("DEFAULT_LLM_PROVIDER", "openai"))
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    google: GoogleAIConfig = Field(default_factory=GoogleAIConfig)
    default_temperature: float = Field(default=0.7, ge=0, le=1)
    default_max_tokens: int = Field(default=2048, gt=0)
    
    def get_config_for_provider(self, provider: str) -> Union[OpenAIConfig, AnthropicConfig, GoogleAIConfig]:
        """Get the configuration for a specific provider."""
        if provider == "openai":
            return self.openai
        elif provider == "anthropic":
            return self.anthropic
        elif provider == "google":
            return self.google
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

class QuizConfig(BaseModel):
    """Configuration for quiz functionality."""
    default_question_count: int = Field(default=5, description="Default number of questions per quiz")
    default_timeout: int = Field(default=60, description="Default timeout for answering in seconds")
    difficulty_levels: List[str] = Field(
        default=["easy", "medium", "hard"],
        description="Available difficulty levels"
    )
    max_retries: int = Field(default=3, description="Maximum number of retries per question")
    point_system: Dict[str, int] = Field(
        default={
            "easy": 1,
            "medium": 2,
            "hard": 3,
        },
        description="Points awarded per difficulty level"
    )
    categories: List[str] = Field(
        default=[
            "general", "science", "history", "geography", "literature", 
            "mathematics", "computer science", "arts", "music", "sports",
            "entertainment", "food", "technology", "languages"
        ],
        description="Available quiz categories"
    )
    question_types: List[str] = Field(
        default=["multiple_choice", "true_false", "short_answer"],
        description="Available question types"
    )
    countdown_intervals: List[int] = Field(
        default=[30, 20, 10, 5],
        description="Time intervals for countdown notifications"
    )

class TriviaConfig(BaseModel):
    """Configuration for group trivia functionality."""
    default_question_count: int = Field(default=10, description="Default number of questions for trivia")
    default_timeout: int = Field(default=30, description="Default timeout for answering in seconds")
    default_time_between_questions: int = Field(default=5, description="Default time between questions")
    max_participants: int = Field(default=20, description="Maximum number of participants")
    base_point_multiplier: int = Field(default=10, description="Base points per correct answer")
    countdown_intervals: List[int] = Field(
        default=[30, 20, 10, 5],
        description="Time intervals for countdown notifications"
    )
    
class DatabaseConfig(BaseModel):
    """Configuration for PostgreSQL database functionality."""
    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    database: str = Field(default="quizbot", description="PostgreSQL database name")
    user: str = Field(default="postgres", description="PostgreSQL username")
    password: str = Field(default="", description="PostgreSQL password")
    min_connections: int = Field(default=1, description="Minimum number of connections in pool")
    max_connections: int = Field(default=10, description="Maximum number of connections in pool")
    backup_path: str = Field(default="data/backups", description="Path for database backups")
    backup_frequency: int = Field(default=24, description="Backup frequency in hours")
    use_ssl: bool = Field(default=False, description="Whether to use SSL for database connection")
    connect_timeout: int = Field(default=10, description="Connection timeout in seconds")
    
    @validator('host', pre=True, always=True)
    def validate_host(cls, v):
        return os.getenv("POSTGRES_HOST", v)
    
    @validator('port', pre=True, always=True)
    def validate_port(cls, v):
        port_str = os.getenv("POSTGRES_PORT", str(v))
        try:
            return int(port_str)
        except ValueError:
            return v
    
    @validator('database', pre=True, always=True)
    def validate_database(cls, v):
        return os.getenv("POSTGRES_DB", v)
    
    @validator('user', pre=True, always=True)
    def validate_user(cls, v):
        return os.getenv("POSTGRES_USER", v)
    
    @validator('password', pre=True, always=True)
    def validate_password(cls, v):
        return os.getenv("POSTGRES_PASSWORD", v)
    
    @validator('use_ssl', pre=True, always=True)
    def validate_use_ssl(cls, v):
        ssl_str = os.getenv("POSTGRES_USE_SSL", str(v).lower())
        return ssl_str in ['true', 'yes', '1', 't', 'y']
    
    @model_validator(mode='after')
    def check_credentials(self):
        """Validate that we have the minimum required credentials."""
        required_fields = ['host', 'database', 'user']
        for field in required_fields:
            if not getattr(self, field, None):
                raise ValueError(f"Missing required PostgreSQL configuration: {field}")
        return self

class PromptConfig(BaseModel):
    """Configuration for LLM prompt templates."""
    standard_quiz: str = Field(default=DEFAULT_STANDARD_QUIZ_PROMPT, description="Prompt template for standard quizzes")
    educational_quiz: str = Field(default=DEFAULT_EDUCATIONAL_QUIZ_PROMPT, description="Prompt template for educational quizzes")
    challenge_quiz: str = Field(default=DEFAULT_CHALLENGE_QUIZ_PROMPT, description="Prompt template for challenge quizzes")
    trivia_quiz: str = Field(default=DEFAULT_TRIVIA_QUIZ_PROMPT, description="Prompt template for trivia quizzes")
    true_false_quiz: str = Field(default="", description="Prompt template for true/false quizzes")
    
    @validator('standard_quiz', pre=True, always=True)
    def validate_standard_quiz(cls, v):
        return os.getenv("STANDARD_QUIZ_PROMPT", v)
    
    @validator('educational_quiz', pre=True, always=True)
    def validate_educational_quiz(cls, v):
        return os.getenv("EDUCATIONAL_QUIZ_PROMPT", v)
    
    @validator('challenge_quiz', pre=True, always=True)
    def validate_challenge_quiz(cls, v):
        return os.getenv("CHALLENGE_QUIZ_PROMPT", v)
    
    @validator('trivia_quiz', pre=True, always=True)
    def validate_trivia_quiz(cls, v):
        return os.getenv("TRIVIA_QUIZ_PROMPT", v)
        
    @validator('true_false_quiz', pre=True, always=True)
    def validate_true_false_quiz(cls, v):
        return os.getenv("TRUE_FALSE_QUIZ_PROMPT", v)

class BotConfig(BaseModel):
    """Main configuration for the Discord bot."""
    bot_token: str = Field(default="", description="Discord bot token")
    default_prefix: str = Field(default="!", description="Default command prefix")
    owner_id: Optional[int] = Field(default=None, description="Bot owner's Discord user ID")
    admin_roles: List[str] = Field(default=["Admin", "Moderator"], description="Admin role names")
    admin_users: List[int] = Field(default=[], description="Admin user IDs")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    quiz: QuizConfig = Field(default_factory=QuizConfig, description="Quiz configuration")
    trivia: TriviaConfig = Field(default_factory=TriviaConfig, description="Trivia configuration")
    database: DatabaseConfig = Field(default_factory=DatabaseConfig, description="Database configuration")
    prompts: PromptConfig = Field(default_factory=PromptConfig, description="LLM Prompt templates")
    
    @validator('bot_token', pre=True, always=True)
    def validate_bot_token(cls, v):
        if not v:
            return os.getenv("DISCORD_TOKEN", "")
        return v
    
    @validator('default_prefix', pre=True, always=True)
    def validate_prefix(cls, v):
        return os.getenv("COMMAND_PREFIX", v)
    
    @validator('owner_id', pre=True, always=True)
    def validate_owner_id(cls, v):
        owner_id_str = os.getenv("OWNER_ID", "")
        if owner_id_str:
            try:
                return int(owner_id_str)
            except ValueError:
                return None
        return v

def load_config() -> BotConfig:
    """Load the bot configuration from environment variables."""
    return BotConfig() 