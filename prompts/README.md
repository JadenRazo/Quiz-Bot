# Quiz Bot Prompts

This directory contains concise prompt templates for different quiz types. Each prompt is under 200 words and provides clear instructions for generating questions.

## Prompt Files

### standard.prompt
- General multiple-choice questions
- Focuses on factual accuracy and understanding
- Suitable for all topics and difficulty levels

### educational.prompt
- Learning-focused questions using Bloom's Taxonomy
- Addresses misconceptions and promotes critical thinking
- Includes mini-lessons in explanations

### trivia.prompt
- Engaging trivia questions with fascinating facts
- Balances well-known and obscure information
- Perfect for entertainment and learning

### challenge.prompt
- Expert-level questions requiring deep knowledge
- Tests synthesis and complex reasoning
- Includes sophisticated incorrect options

### true_false.prompt
- Clear statements that are definitively true or false
- Tests understanding through precise language
- Addresses common misconceptions

## Common Format

All prompts use the same XML-like format:
- `<QUESTION>` - The question text
- `<OPTION_A>` through `<OPTION_D>` - Answer choices (A is always correct)
- `<CORRECT>` - The correct answer (A for multiple choice, TRUE/FALSE for T/F)
- `<EXPLANATION>` - Educational explanation of the answer

## Variables

- `{num_questions}` - Number of questions to generate
- `{topic}` - The quiz topic
- `{difficulty}` - Difficulty level (easy/medium/hard)
- `{category}` - Optional category specification