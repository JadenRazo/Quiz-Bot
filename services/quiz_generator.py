import asyncio
import logging
import random
import re
from typing import List, Dict, Any, Optional, Union, Tuple
import json
import os

from services.llm_service import LLMService, Question
from config import BotConfig, load_config

logger = logging.getLogger("bot.quiz_generator")

# Define default prompts - These will ALWAYS be available as fallbacks
DEFAULT_PROMPTS = {
    "standard": """You are an expert educational content creator. Generate {num_questions} multiple-choice questions about '{topic}' at {difficulty} difficulty level.

GUIDELINES:
- Create factually accurate questions that test understanding
- Balance core concepts with interesting details
- Avoid ambiguous wording or trick questions
- Make questions culturally sensitive and inclusive

DIFFICULTY LEVELS:
- Easy: fundamental concepts, basic facts
- Medium: application of concepts, moderate complexity
- Hard: synthesis of ideas, complex relationships

ANSWER OPTION RULES (HIGHEST PRIORITY):
- Keep all options similar in structure and length
- NEVER include dates, years, or chronological markers in options
- Present only names/places without any revealing information
- Avoid parenthetical explanations or qualifying information
- Make all options equally plausible
- Never include information that makes one option stand out
- All options must have the same format, style, and structure

SECURITY REQUIREMENTS:
- No placeholder HTML, Markdown, or code elements
- No JavaScript, PHP, SQL, or other executable code
- No injection vectors such as template tags or format strings
- No comments or special characters that could break parsing
- No nested or malformed XML tags

FORMAT REQUIREMENTS:
- Use the exact XML-like tags below
- NO text outside the tags
- OPTION_A is ALWAYS correct
- Provide four distinct options (A-D)
- B, C, D must be plausible but wrong
- Maintain precise opening/closing tags
- DO NOT nest tags or use incomplete tags
- DO NOT add attributes to tags

REQUIRED FORMAT:
<QUESTION>Clear, specific question about {topic}</QUESTION>
<OPTION_A>The correct answer</OPTION_A>
<OPTION_B>Plausible but incorrect</OPTION_B>
<OPTION_C>Plausible but incorrect</OPTION_C>
<OPTION_D>Plausible but incorrect</OPTION_D>
<CORRECT>A</CORRECT>
<EXPLANATION>Why A is correct and others are wrong</EXPLANATION>

Repeat for all {num_questions} questions.""",

    "trivia": """You are a trivia expert with encyclopedic knowledge. Create {num_questions} engaging trivia questions about '{topic}' at {difficulty} level.

TRIVIA GUIDELINES:
- Use verified facts from authoritative sources
- Include fascinating details that surprise and educate
- Balance well-known facts with intriguing discoveries
- Make questions specific with one clear answer
- Ensure information is current or clearly dated

DIFFICULTY LEVELS:
- Easy: commonly known facts, popular culture, basic events
- Medium: less common knowledge, requires some expertise
- Hard: obscure facts, expert-level knowledge

ANSWER OPTION RULES (HIGHEST PRIORITY):
- Keep all options similar in structure and length
- NEVER include dates, years, or chronological markers in options
- Present only names/places without any revealing information
- Avoid parenthetical explanations or additional context
- Make all options equally plausible
- Never include information that makes one option stand out
- All options must have the same format, style, and structure

SECURITY REQUIREMENTS:
- No placeholder HTML, Markdown, or code elements
- No JavaScript, PHP, SQL, or other executable code
- No injection vectors such as template tags or format strings
- No comments or special characters that could break parsing
- No nested or malformed XML tags

FORMAT REQUIREMENTS:
- Use the exact XML-like tags below
- NO text outside the tags
- OPTION_A is ALWAYS correct
- Provide four distinct options (A-D)
- B, C, D must be plausible but wrong
- Maintain precise opening/closing tags
- DO NOT nest tags or use incomplete tags
- DO NOT add attributes to tags

REQUIRED FORMAT:
<QUESTION>Engaging trivia question about {topic}</QUESTION>
<OPTION_A>The correct answer - factual and verifiable</OPTION_A>
<OPTION_B>Plausible but incorrect - common misconception</OPTION_B>
<OPTION_C>Related but wrong - factual error</OPTION_C>
<OPTION_D>Reasonable but incorrect - distinct option</OPTION_D>
<CORRECT>A</CORRECT>
<EXPLANATION>Why A is correct, interesting context, brief note on wrong answers</EXPLANATION>

Repeat for all {num_questions} questions.""",

    "educational": """You are a master educator creating learning-focused quiz questions. Generate {num_questions} educational multiple-choice questions about '{topic}' at {difficulty} level.

EDUCATIONAL PRINCIPLES:
- Test conceptual understanding, not memorization
- Include real-world applications
- Address common misconceptions
- Promote critical thinking
- Use Bloom's Taxonomy levels

DIFFICULTY LEVELS:
- Easy: recall, recognition, basic comprehension
- Medium: application, analysis, problem-solving
- Hard: evaluation, synthesis, critical thinking

ANSWER OPTION RULES (HIGHEST PRIORITY):
- Keep all options similar in structure and length
- NEVER include dates, years, or chronological markers in options
- Present only names/places without any revealing information
- Avoid parenthetical explanations or additional context
- Make all options equally plausible
- Never include information that makes one option stand out
- All options must have the same format, style, and structure

SECURITY REQUIREMENTS:
- No placeholder HTML, Markdown, or code elements
- No JavaScript, PHP, SQL, or other executable code
- No injection vectors such as template tags or format strings
- No comments or special characters that could break parsing
- No nested or malformed XML tags

FORMAT REQUIREMENTS:
- Use the exact XML-like tags below
- NO text outside the tags
- OPTION_A is ALWAYS correct
- Provide four distinct options (A-D)
- B, C, D must be plausible but wrong
- Maintain precise opening/closing tags
- DO NOT nest tags or use incomplete tags
- DO NOT add attributes to tags

REQUIRED FORMAT:
<QUESTION>Educational question testing understanding of {topic}</QUESTION>
<OPTION_A>Correct answer showing complete understanding</OPTION_A>
<OPTION_B>Common misconception or partial understanding</OPTION_B>
<OPTION_C>Different misconception or incomplete grasp</OPTION_C>
<OPTION_D>Another typical error students make</OPTION_D>
<CORRECT>A</CORRECT>
<EXPLANATION>Mini-lesson explaining the concept, why A is right, addressing misconceptions, providing context/examples</EXPLANATION>

Repeat for all {num_questions} questions.""",

    "true_false": """You are a fact checker creating True/False questions. Generate {num_questions} True/False questions about '{topic}' at {difficulty} level.

TRUE/FALSE GUIDELINES:
- Create statements that are definitively true or false
- Use verified sources for accuracy
- Avoid ambiguity or exceptions
- Test understanding, not memorization
- Use precise, clear language

DIFFICULTY LEVELS:
- Easy: straightforward facts, basic concepts
- Medium: nuanced statements, deeper understanding
- Hard: complex relationships, subtle distinctions

BALANCE:
- Mix TRUE and FALSE statements
- Address common misconceptions
- Test both positive knowledge and false beliefs

SECURITY REQUIREMENTS:
- No placeholder HTML, Markdown, or code elements
- No JavaScript, PHP, SQL, or other executable code
- No injection vectors such as template tags or format strings
- No comments or special characters that could break parsing
- No nested or malformed XML tags

FORMAT REQUIREMENTS:
- Use the exact XML-like tags below
- NO text outside the tags
- <CORRECT> must contain ONLY "TRUE" or "FALSE"
- Maintain precise opening/closing tags
- DO NOT nest tags or use incomplete tags
- DO NOT add attributes to tags

REQUIRED FORMAT:
<QUESTION>Clear, unambiguous statement about {topic}</QUESTION>
<CORRECT>TRUE or FALSE only</CORRECT>
<EXPLANATION>Why the statement is true/false, supporting evidence, correct information if false, educational context</EXPLANATION>

Repeat for all {num_questions} questions.""",

    "challenge": """You are an elite expert crafting challenge-level questions. Generate {num_questions} advanced multiple-choice questions about '{topic}' at {difficulty} level.

CHALLENGE PRINCIPLES:
- Draw from academic sources and specialist knowledge
- Test synthesis, analysis, and complex applications
- Require multi-step reasoning
- Include nuanced details and edge cases
- Challenge misconceptions and oversimplifications
- Focus on implications and interconnections

QUALITY STANDARDS:
- Absolute factual accuracy
- Expert-level terminology
- Sophisticated distinctions
- Current field consensus
- Integration of multiple concepts

ANSWER OPTION RULES (HIGHEST PRIORITY):
- Keep all options similar in structure and length
- NEVER include dates, years, or chronological markers in options
- Present only names/places without any revealing information
- Avoid parenthetical explanations or additional context
- Make all options equally plausible
- Never include information that makes one option stand out
- All options must have the same format, style, and structure

INCORRECT OPTIONS MUST:
- Be highly plausible to experts
- Represent sophisticated misconceptions
- Include partial truths with critical flaws
- Test recognition of subtle differences

SECURITY REQUIREMENTS:
- No placeholder HTML, Markdown, or code elements
- No JavaScript, PHP, SQL, or other executable code
- No injection vectors such as template tags or format strings
- No comments or special characters that could break parsing
- No nested or malformed XML tags

FORMAT REQUIREMENTS:
- Use the exact XML-like tags below
- NO text outside the tags
- OPTION_A is ALWAYS correct
- Provide four distinct options (A-D)
- B, C, D must be plausible but wrong
- Maintain precise opening/closing tags
- DO NOT nest tags or use incomplete tags
- DO NOT add attributes to tags

REQUIRED FORMAT:
<QUESTION>Advanced question requiring expert analysis of {topic}</QUESTION>
<OPTION_A>Correct answer with precise expert details</OPTION_A>
<OPTION_B>Sophisticated misconception or outdated theory</OPTION_B>
<OPTION_C>Edge case or incomplete understanding</OPTION_C>
<OPTION_D>Partial truth with critical flaw</OPTION_D>
<CORRECT>A</CORRECT>
<EXPLANATION>Detailed analysis, subtle distinctions, theoretical frameworks, key insights</EXPLANATION>

Repeat for all {num_questions} questions."""
}

class PromptManager:
    """Handles prompt loading, selection and formatting with reliable fallbacks."""
    
    def __init__(self, prompt_dir: str = "prompts"):
        """Initialize the prompt manager with default prompts and load from files."""
        self.prompt_dir = prompt_dir
        self.default_prompts = DEFAULT_PROMPTS
        self.file_prompts = self._load_file_prompts()
        
    def _read_prompt_file(self, filename: str) -> Optional[str]:
        """Safely read the content of a single prompt file."""
        filepath = os.path.join(self.prompt_dir, filename)
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content and len(content) > 50: # Basic check for non-empty content
                        logger.debug(f"Successfully read prompt file: {filename}")
                        return content
                    else:
                        logger.warning(f"Prompt file '{filename}' is empty or too short.")
            else:
                logger.warning(f"Prompt file not found: {filepath}")
        except Exception as e:
            logger.error(f"Error reading prompt file '{filename}': {e}", exc_info=True)
        return None

    def _load_file_prompts(self) -> Dict[str, str]:
        """Load prompts from files in the specified directory."""
        file_prompts = {}
        prompt_files = {
            "standard": "standard.prompt",
            "trivia": "trivia.prompt",
            "educational": "educational.prompt",
            "true_false": "true_false.prompt",
            "challenge": "challenge.prompt"
        }
        
        # Ensure the prompt directory exists
        if not os.path.isdir(self.prompt_dir):
            logger.warning(f"Prompt directory '{self.prompt_dir}' not found. Cannot load prompts from files.")
            return {}
            
        for key, filename in prompt_files.items():
            content = self._read_prompt_file(filename)
            if content:
                file_prompts[key] = content
            else:
                logger.info(f"Could not load prompt for '{key}' from file '{filename}'. Will use default.")
                
        logger.info(f"Loaded {len(file_prompts)} prompts from the '{self.prompt_dir}' directory.")
        return file_prompts
    
    def get_prompt(self, quiz_type: str, question_type: str = "multiple_choice") -> str:
        """
        Get a prompt for the specified quiz type and question type.
        Prioritizes file prompts, then defaults.
        Always returns a valid, non-empty prompt string.
        """
        # Determine the key based on type
        if question_type == "true_false":
            key = "true_false"
        else:
            key = quiz_type.lower()
        
        # 1. Try file prompts
        if key in self.file_prompts:
            logger.debug(f"Using file prompt for {key}")
            return self.file_prompts[key]
        
        # 2. Try default prompts
        if key in self.default_prompts:
            logger.warning(f"Using default prompt for {key} (not found in files or files failed to load)")
            return self.default_prompts[key]
        
        # 3. If all else fails, use standard default prompt
        logger.critical(f"CRITICAL: No specific or default prompt found for key '{key}'. Falling back to hardcoded STANDARD default.")
        return self.default_prompts["standard"]
    
    def format_prompt(self, 
                      template: str,
                      num_questions: int,
                      topic: str,
                      difficulty: str,
                      category: str = "general") -> str:
        """
        Safely format a prompt template with error handling and fallbacks.
        """
        try:
            # Format dictionary with all possible values
            format_dict = {
                "num_questions": num_questions,
                "topic": topic,
                "difficulty": difficulty,
                "category": category
            }
            
            # Format the template
            return template.format(**format_dict)
            
        except Exception as e:
            logger.error(f"Error formatting prompt: {e}")
            # Fallback to simple formatting without using .format()
            return f"""Generate {num_questions} questions about '{topic}' at {difficulty} difficulty.

For each question, follow this format EXACTLY:

<QUESTION>
Question about {topic}?
</QUESTION>

<OPTION_A>
Correct answer
</OPTION_A>

<OPTION_B>
Wrong answer
</OPTION_B>

<OPTION_C>
Wrong answer
</OPTION_C>

<OPTION_D>
Wrong answer
</OPTION_D>

<CORRECT>A</CORRECT>

<EXPLANATION>
Why A is correct
</EXPLANATION>"""

# Create a singleton prompt manager (instantiated when the module loads)
prompt_manager = PromptManager()

class QuizTemplate:
    """
    A class that defines quiz templates for backward compatibility.
    This class is maintained for compatibility with existing code
    that might still reference it.
    """
    def __init__(self, name: str, template_id: str, description: str, prompt: str):
        """
        Initialize a quiz template.
        
        Args:
            name: Display name of the template
            template_id: Unique identifier for the template
            description: Description of the template
            prompt: The actual prompt template
        """
        self.name = name
        self.id = template_id
        self.description = description
        self.prompt = prompt
    
    @classmethod
    def get_default_templates(cls) -> List['QuizTemplate']:
        """
        Get a list of default quiz templates.
        
        Returns:
            A list of QuizTemplate objects
        """
        return [
            cls(
                name="Standard Quiz",
                template_id="standard",
                description="A standard general knowledge quiz.",
                prompt=prompt_manager.get_prompt("standard")
            ),
            cls(
                name="Educational Quiz",
                template_id="educational",
                description="An educational quiz focused on learning.",
                prompt=prompt_manager.get_prompt("educational")
            ),
            cls(
                name="True/False Quiz",
                template_id="true_false",
                description="A true/false quiz.",
                prompt=prompt_manager.get_prompt("true_false")
            )
        ]

class QuizGenerator:
    """Service for generating quiz content."""
    
    def __init__(self, config: BotConfig, llm_service: LLMService):
        """
        Initialize the quiz generator.
        
        Args:
            config: The application configuration object.
            llm_service: LLMService instance to use.
        """
        self.prompt_config = config.prompts
        self.llm_service = llm_service
        self.quiz_config = config.quiz
        # Track correct answer positions across the entire quiz
        self.correct_answer_positions = []
        # Use the prompt manager for reliable prompt handling
        self.prompt_manager = prompt_manager
    
    def get_available_quiz_types(self) -> List[Dict[str, str]]:
        """Return a list of available quiz types based on configured prompts."""
        return [
            {"name": "standard", "description": "A standard general knowledge quiz."},
            {"name": "educational", "description": "An educational quiz focused on learning."},
            {"name": "challenge", "description": "A challenging quiz for experts."},
            {"name": "trivia", "description": "A fun trivia quiz for groups."},
            {"name": "true_false", "description": "A true/false quiz."}
        ]
    
    def get_available_templates(self) -> List[Dict[str, str]]:
        """Return a list of available quiz templates (for backward compatibility)."""
        templates = QuizTemplate.get_default_templates()
        return [
            {"name": t.name, "id": t.id, "description": t.description}
            for t in templates
        ]
    
    def _select_prompt(self, quiz_type: str, question_type: str = "multiple_choice") -> str:
        """
        Select the appropriate prompt string based on quiz type and question type.
        Always returns a valid prompt from the prompt manager.
        """
        return self.prompt_manager.get_prompt(quiz_type, question_type)
    
    async def generate_quiz(
        self,
        topic: str,
        quiz_type: str = "standard",
        num_questions: Optional[int] = None,
        num_options_expected: int = 4,
        difficulty: Optional[str] = None,
        provider: Optional[str] = None,
        max_retries: int = 3, # Note: max_retries for the whole process, not per LLM call
        question_type: str = "multiple_choice", # Default, but trivia will override
        category: Optional[str] = None
    ) -> List[Question]:
        """
        Generates a quiz with questions, potentially mixing types for trivia.
        
        Args:
            topic: The topic of the quiz
            quiz_type: Type of quiz content (standard, educational, challenge, trivia)
            num_questions: Total number of questions to generate
            num_options_expected: Expected number of options per MC question
            difficulty: Difficulty level (easy, medium, hard)
            provider: LLM provider to use
            max_retries: Max attempts for the overall generation process
            question_type: Preferred question type (ignored for trivia)
            category: Difficulty level category (e.g., general, science)
            
        Returns:
            List of Question objects
        """
        self.correct_answer_positions = [] # Reset for new quiz

        # Determine defaults
        effective_provider = provider if provider is not None else self.llm_service.default_provider
        effective_num_questions = num_questions if num_questions is not None else self.quiz_config.default_question_count
        if quiz_type == "trivia" and hasattr(self.quiz_config, 'trivia') and self.quiz_config.trivia:
            effective_num_questions = num_questions if num_questions is not None else self.quiz_config.trivia.default_question_count
        effective_difficulty = difficulty if difficulty is not None else "medium"
        effective_category = category or "general" # Set default for category

        logger.info(f"Generating {quiz_type} quiz on '{topic}' (Category: {effective_category}, {effective_num_questions}q, {effective_difficulty} diff) using {effective_provider}.")

        all_questions: List[Question] = []
        attempts = 0

        while len(all_questions) < effective_num_questions and attempts < max_retries:
            attempts += 1
            needed = effective_num_questions - len(all_questions)
            logger.info(f"Attempt {attempts}/{max_retries}: Generating {needed} more questions for '{topic}'.")

            if quiz_type == "trivia":
                # For trivia, generate a mix of multiple choice and true/false
                # Aim for roughly 75% MC, 25% T/F, adjust counts based on what's needed
                num_mc_needed = max(1, int(needed * 0.75))
                num_tf_needed = needed - num_mc_needed

                mc_questions: List[Question] = []
                tf_questions: List[Question] = []

                # Generate Multiple Choice Trivia
                if num_mc_needed > 0:
                    logger.info(f"Generating {num_mc_needed} multiple-choice trivia questions.")
                    mc_questions = await self._generate_questions_tagged_format(
                        topic=topic,
                        question_count=num_mc_needed,
                        difficulty=effective_difficulty,
                        provider=effective_provider,
                        quiz_type="trivia", # Use the trivia MC prompt
                        question_type="multiple_choice",
                        category=effective_category
                    )
                    if not mc_questions:
                        logger.warning("Failed to generate multiple-choice trivia questions in this attempt.")

                # Generate True/False Trivia
                if num_tf_needed > 0:
                    logger.info(f"Generating {num_tf_needed} true/false trivia questions.")
                    tf_questions = await self._generate_questions_tagged_format(
                        topic=topic,
                        question_count=num_tf_needed,
                        difficulty=effective_difficulty,
                        provider=effective_provider,
                        quiz_type="trivia", # Can still categorize as trivia
                        question_type="true_false", # Use the T/F prompt
                        category=effective_category
                    )
                    if not tf_questions:
                        logger.warning("Failed to generate true/false trivia questions in this attempt.")
                
                # Combine and shuffle this attempt's results
                current_attempt_questions = mc_questions + tf_questions
                random.shuffle(current_attempt_questions)
                all_questions.extend(current_attempt_questions)

            else:
                # For non-trivia types, generate using the specified question_type
                logger.info(f"Generating {needed} {question_type} questions.")
                generated_questions = await self._generate_questions_tagged_format(
                    topic=topic,
                    question_count=needed,
                    difficulty=effective_difficulty,
                    provider=effective_provider,
                    quiz_type=quiz_type,
                    question_type=question_type,
                    category=effective_category
                )
                if generated_questions:
                    all_questions.extend(generated_questions)
                else:
                    logger.warning(f"Failed to generate any questions for {quiz_type} in attempt {attempts}.")
            
            # Small delay before retrying if needed
            if len(all_questions) < effective_num_questions and attempts < max_retries:
                await asyncio.sleep(1) # Avoid hammering the API immediately

        # Final check and logging
        if len(all_questions) < effective_num_questions:
            logger.error(f"Failed to generate the required {effective_num_questions} questions for '{topic}' after {max_retries} attempts. Generated {len(all_questions)}.")
            # If absolutely no questions generated, return error placeholder
            if not all_questions:
                 return await self._handle_generation_failure(
                    topic, effective_num_questions, effective_difficulty, effective_provider, f"Failed after {max_retries} attempts"
                )
        else:
            logger.info(f"Successfully generated {len(all_questions)} questions for '{topic}'.")
        
        # Apply post-processing to clean up any revealing information from options
        cleaned_questions = []
        for question in all_questions[:effective_num_questions]:
            cleaned_question = self._remove_revealing_information(question)
            cleaned_questions.append(cleaned_question)
        
        logger.info(f"Post-processed {len(cleaned_questions)} questions to remove revealing information.")
        return cleaned_questions

    async def _generate_questions_tagged_format(
        self,
        topic: str,
        question_count: int,
        difficulty: str,
        provider: str,
        quiz_type: str,
        question_type: str = "multiple_choice",
        category: str = "general"
    ) -> List[Question]:
        """
        Generate questions using the new tagged format (XML-like tags).
        
        Args:
            topic: The topic of the questions
            question_count: Number of questions to generate
            difficulty: Difficulty level
            provider: LLM provider to use
            quiz_type: Type of quiz (standard, educational, challenge, trivia)
            question_type: Type of questions (multiple_choice, true_false)
            category: Difficulty level category (e.g., general, science)
            
        Returns:
            List of Question objects
        """
        logger.info(f"Generating {question_count} {question_type} questions for {quiz_type} quiz on '{topic}'")
        
        # Get prompt template from our reliable prompt manager
        prompt_template = self.prompt_manager.get_prompt(quiz_type, question_type)
        
        # Format the prompt with our prompt manager
        prompt = self.prompt_manager.format_prompt(
            template=prompt_template,
            num_questions=question_count,
                topic=topic,
                difficulty=difficulty,
            category=category
        )
        
        logger.debug(f"Formatted prompt (first 100 chars): {prompt[:100]}...")
        
        # Generate response from LLM
        try:
            response = await self.llm_service.generate_raw_text(
                prompt=prompt,
                provider=provider
            )
            
            if not response:
                logger.warning(f"LLM returned empty response for '{topic}'")
                return []
                
            logger.debug(f"Received response (length: {len(response)})")
            
        except Exception as e:
            logger.error(f"Error generating content with LLM: {e}", exc_info=True)
            return []
        
        # Parse the response using the new tagged format
        questions = self._parse_tagged_questions(
            response_text=response,
            topic=topic,
            difficulty=difficulty,
            question_type=question_type,
            category=category
        )
        
        if not questions:
            logger.warning(f"Failed to parse any questions from the LLM response for '{topic}'")
        
        logger.info(f"Successfully parsed {len(questions)} questions using tagged format")
        return questions
    
    def _parse_tagged_questions(
        self,
        response_text: str,
        topic: str,
        difficulty: str,
        question_type: str = "multiple_choice",
        category: str = "general"
    ) -> List[Question]:
        """
        Parse questions with XML-like tags into Question objects.
        
        Args:
            response_text: The response from the LLM containing tagged questions
            topic: The topic of the questions
            difficulty: The difficulty level
            question_type: Type of questions (multiple_choice, true_false)
            category: Difficulty level category (e.g., general, science)
            
        Returns:
            List of Question objects
        """
        questions = []
        
        # Make sure we have a valid response to parse
        if not response_text or len(response_text) < 20:  # Arbitrary minimum length check
            logger.error("Response too short or empty to parse")
            return questions
            
        # Split the response into blocks that start with <QUESTION>
        blocks = re.split(r'(?=<QUESTION>)', response_text)
        
        for i, block in enumerate(block for block in blocks if '<QUESTION>' in block):
            try:
                # Extract question text
                question_match = re.search(r'<QUESTION>(.*?)</QUESTION>', block, re.DOTALL)
                if not question_match:
                    logger.warning(f"Could not find question text in block #{i+1}")
                    continue
                
                question_text = question_match.group(1).strip()
                
                # Extract correct answer indicator
                correct_match = re.search(r'<CORRECT>(.*?)</CORRECT>', block, re.DOTALL)
                if not correct_match:
                    logger.warning(f"Could not find correct answer marker in question: {question_text[:50]}...")
                    continue
                
                correct_indicator = correct_match.group(1).strip()
                
                # Handle multiple choice questions
                if question_type == "multiple_choice":
                    # Extract options
                    options = []
                    option_matches = {}
                    
                    for letter in ['A', 'B', 'C', 'D']:
                        option_match = re.search(f'<OPTION_{letter}>(.*?)</OPTION_{letter}>', block, re.DOTALL)
                        if option_match:
                            option_text = option_match.group(1).strip()
                            option_matches[letter] = option_text
                    
                    # Get the correct answer text
                    if correct_indicator in option_matches:
                        correct_answer = option_matches[correct_indicator]
                    elif correct_indicator == 'A' and 'A' in option_matches:
                        # Default to first option if marked as A
                        correct_answer = option_matches['A']
                    else:
                        logger.warning(f"Could not determine correct answer for: {question_text[:50]}...")
                        continue
                    
                    # Randomize the position of the correct answer and options
                    if len(option_matches) >= 2:  # Only randomize if we have at least 2 options
                        # Get all options
                        all_options = list(option_matches.values())
                        
                        # Remove the correct answer from the list if it's there
                        if correct_answer in all_options:
                            all_options.remove(correct_answer)
                        
                        # Randomize remaining options
                        random.shuffle(all_options)
                        
                        # Insert the correct answer at a random position
                        correct_position = random.randint(0, min(3, len(all_options)))
                        all_options.insert(correct_position, correct_answer)
                        
                        # Take first 4 options or pad if needed
                        options = all_options[:4]
                        
                        # Ensure we have exactly 4 options for multiple choice
                        while len(options) < 4:
                            options.append(f"Missing option {len(options) + 1}")
                    else:
                        # Fallback if we couldn't randomize
                        options = list(option_matches.values())
                        while len(options) < 4:
                            options.append(f"Missing option {len(options) + 1}")
                
                # Handle true/false questions
                elif question_type == "true_false":
                    correct_answer = correct_indicator.upper()
                    if correct_answer not in ["TRUE", "FALSE"]:
                        logger.warning(f"Invalid true/false value: {correct_answer}")
                        continue
                    options = ["TRUE", "FALSE"]
                else:
                    logger.warning(f"Unsupported question type: {question_type}")
                    continue
                
                # Extract explanation
                explanation_match = re.search(r'<EXPLANATION>(.*?)</EXPLANATION>', block, re.DOTALL)
                explanation = explanation_match.group(1).strip() if explanation_match else ""
                
                # Import content normalization utility
                from utils.content import truncate_content, normalize_quiz_content
                
                # Create the Question object with normalized content
                question = Question(
                    question_id=i,
                    question=truncate_content(question_text, "question"),
                    options=[truncate_content(opt, "choice") for opt in options],
                    answer=truncate_content(correct_answer, "answer"),
                    explanation=truncate_content(explanation, "explanation"),
                    category=truncate_content(category, "category"),
                    difficulty=truncate_content(difficulty, "category"),
                    question_type=question_type
                )
                
                questions.append(question)
            
            except Exception as e:
                logger.error(f"Error parsing question block #{i+1}: {str(e)}", exc_info=True)
                continue
        
        return questions

    async def _handle_generation_failure(
        self,
        topic: str, 
        num_questions: int, 
        difficulty: str, 
        provider: str, 
        reason: str
    ) -> List[Question]:
        """Handles failures in primary generation methods.
        Attempts one final LLM call with a super simple prompt.
        """
        logger.error(f"Quiz generation failed for topic '{topic}'. Reason: {reason}. Attempting final fallback generation.")
        
        # Final attempt: Ask LLM for just *one* simple question in tagged format
        try:
            # Use the simplest possible prompt for a single question
            very_simple_prompt = f"""Create EXACTLY ONE simple multiple-choice question about '{topic}'.
Use difficulty: {difficulty}.

FOLLOW THIS EXACT FORMAT, with tags:

<QUESTION>
Write one clear, specific question about {topic}?
</QUESTION>

<OPTION_A>
First option (make this the correct answer - accurate and factual)
</OPTION_A>

<OPTION_B>
Second option (make this plausible but incorrect)
</OPTION_B>

<OPTION_C>
Third option (make this plausible but incorrect)
</OPTION_C>

<OPTION_D>
Fourth option (make this plausible but incorrect)
</OPTION_D>

<CORRECT>A</CORRECT>

<EXPLANATION>
Brief explanation why the correct answer is right
</EXPLANATION>

IMPORTANT RULES:
- OPTION_A must be the correct answer
- All options must have similar length and structure
- No revealing information like dates in parentheses
- No HTML, code elements, special characters, or malformed tags
- Use exact tags as shown - correct closing tags are essential

The answer will be randomized when presented to the user.
"""
            
            logger.info(f"Attempting final fallback LLM call to {provider} for topic '{topic}'.")
            fallback_response = await self.llm_service.generate_raw_text(
                prompt=very_simple_prompt,
                provider=provider
            )

            if fallback_response:
                logger.info("Received fallback response. Attempting to parse...")
                # Use the tagged parser for this format
                parsed_fallback = self._parse_tagged_questions(
                    response_text=fallback_response, 
                    topic=topic, 
                    difficulty=difficulty,
                    question_type="multiple_choice"
                )
                if parsed_fallback:
                    logger.info(f"Successfully generated {len(parsed_fallback)} question(s) via final fallback.")
                    return parsed_fallback[:1] # Return only the first one if multiple somehow generated
                else:
                    logger.warning("Could not parse the response from the final fallback LLM call.")
            else:
                logger.warning("Final fallback LLM call returned an empty response.")
        except Exception as fallback_err:
            logger.critical(f"Final fallback generation attempt failed catastrophically: {fallback_err}", exc_info=True)

        # If everything fails, return a single error placeholder question
        logger.error(f"All generation attempts failed for topic '{topic}'. Returning error placeholder.")
        error_q = Question(
            question_id=0,
            question=f"Failed to generate quiz question for {topic}. (Reason: {reason})",
            options=["Error", "-", "-", "-"],
            answer="Error",
            explanation=f"Quiz generation failed due to: {reason}. Please try again later or contact an admin.",
            difficulty=difficulty,
            category=topic
        )
        return [error_q]

    # Keep other methods like _generate_questions_text_format, _validate_and_create_questions, etc.
    # for backward compatibility
    
    async def _generate_questions_text_format(
        self, 
        topic: str, 
        question_count: int, 
        difficulty: str,
        provider: str,
        quiz_type: str # Add quiz_type
    ) -> List[Question]:
        """Legacy method for generating questions in text format (kept for backward compatibility)."""
        logger.info(f"Generating questions via text format for quiz type: {quiz_type}")
        # This is now a wrapper around the new tagged format method
        return await self._generate_questions_tagged_format(
            topic=topic,
            question_count=question_count,
            difficulty=difficulty,
            provider=provider,
            quiz_type=quiz_type
        )

    def _parse_text_format_questions(self, text: str, topic: str, difficulty: str, category: str) -> List[Question]:
        """Legacy parser for text format questions (kept for backward compatibility)."""
        # First try parsing with the new tagged format
        questions = self._parse_tagged_questions(text, topic, difficulty, "multiple_choice")
        if questions:
            return questions
            
        # If that fails, fall back to the old parser
        # ... existing _parse_text_format_questions code ...
        # (Keep original implementation for backward compatibility)
        return []
        
    def _trim_explanation(self, explanation: str, max_length: int = 500) -> str:
        """Trim explanation text to a maximum length using the content utility."""
        from utils.content import truncate_content
        return truncate_content(explanation, "explanation", max_length)
        
    def _remove_revealing_information(self, question: Question) -> Question:
        """
        Clean up options to remove revealing information that might give away the answer.
        
        This function:
        1. Removes dates/years in parentheses: "Tokyo Disneyland (1983)" → "Tokyo Disneyland"
        2. Removes any option formatting that would make the correct answer obvious
        
        Args:
            question: Question object to process
            
        Returns:
            Cleaned Question object
        """
        if not hasattr(question, 'options') or not question.options:
            return question
            
        # Text patterns that could reveal answers
        patterns = [
            r'\(\d{4}\)',  # Years in parentheses: (1983)
            r'\(\d{1,2}/\d{1,2}/\d{2,4}\)',  # Dates: (12/25/1990)
            r'\(\d{1,2} \w+ \d{4}\)',  # Text dates: (25 December 1990)
            r'\(\d{1,2}\w{2} \w+ \d{4}\)',  # Text dates with ordinals: (25th December 1990)
            r'\((?:\w+ )?\d{1,2}(?:st|nd|rd|th)?,? \d{4}\)',  # More date formats: (December 25th, 1990)
        ]
        
        # Combined pattern
        combined_pattern = '|'.join(patterns)
        
        # Clean each option
        cleaned_options = []
        for option in question.options:
            # Remove parenthetical dates
            cleaned_option = re.sub(combined_pattern, '', option)
            # Remove any trailing/leading whitespace created by the removal
            cleaned_option = cleaned_option.strip()
            cleaned_options.append(cleaned_option)
        
        # Update the question with cleaned options
        question.options = cleaned_options
        
        # Make sure the correct_answer matches the cleaned version
        if hasattr(question, 'correct_answer') and question.correct_answer:
            for option in cleaned_options:
                if question.correct_answer in option:
                    question.correct_answer = option
                    break
        
        return question
        
    # ... keep other existing methods like _preprocess_llm_response, _parse_questions_from_response, etc.
    # for backward compatibility


# Singleton pattern
# Load the configuration once
config = load_config()

# Import the initialized llm_service instance
from services.llm_service import llm_service

# Check if llm_service was successfully imported/initialized
if not llm_service:
    logger.critical("LLM Service not initialized before QuizGenerator singleton creation!")
    quiz_generator = None
else:
    # Create the QuizGenerator singleton instance
    quiz_generator = QuizGenerator(config=config, llm_service=llm_service)
    logger.info("QuizGenerator singleton initialized successfully.")

# Optional: Add a getter function if needed elsewhere
def get_quiz_generator() -> Optional[QuizGenerator]:
    return quiz_generator 