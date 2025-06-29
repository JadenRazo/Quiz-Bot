#!/bin/bash

# Setup script for quiz bot prompts
# This script copies example prompt files to create working prompt files

echo "Setting up Quiz Bot prompts..."

# Check if prompts directory exists
if [ ! -d "prompts" ]; then
    echo "Error: prompts directory not found. Please run this script from the quiz_bot root directory."
    exit 1
fi

# Array of prompt files to copy
declare -a prompts=("standard" "educational" "trivia" "challenge" "true_false")

# Copy each example file to create the working prompt file
for prompt in "${prompts[@]}"; do
    example_file="prompts/${prompt}.prompt.example"
    target_file="prompts/${prompt}.prompt"
    
    if [ -f "$example_file" ]; then
        if [ -f "$target_file" ]; then
            echo "Warning: $target_file already exists. Skipping..."
        else
            cp "$example_file" "$target_file"
            echo "Created $target_file"
        fi
    else
        echo "Warning: $example_file not found. Skipping..."
    fi
done

echo ""
echo "Prompt setup complete!"
echo "You can now customize the .prompt files in the prompts/ directory to suit your needs."
echo "The original .example files will remain as templates."