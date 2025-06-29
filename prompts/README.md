# Quiz Bot Prompts

This directory contains prompt templates for different quiz types. Each prompt provides clear instructions for generating questions.

## Setup Instructions

After cloning this repository, you'll need to create your own prompt files:

1. Copy the example files and remove the `.example` extension:
   ```bash
   cp prompts/standard.prompt.example prompts/standard.prompt
   cp prompts/educational.prompt.example prompts/educational.prompt
   cp prompts/trivia.prompt.example prompts/trivia.prompt
   cp prompts/challenge.prompt.example prompts/challenge.prompt
   cp prompts/true_false.prompt.example prompts/true_false.prompt
   ```

2. Customize the prompt files to match your specific needs and preferences.

## Prompt Types

### standard.prompt
- General multiple-choice questions
- Focuses on factual accuracy and understanding
- Suitable for all topics and difficulty levels

### educational.prompt
- Learning-focused questions using educational principles
- Addresses misconceptions and promotes critical thinking
- Includes detailed explanations

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

## Format Structure

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

## Note

The actual `.prompt` files are not tracked in git for intellectual property protection. Use the provided `.example` files as templates to create your own customized prompts.