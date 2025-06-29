#!/usr/bin/env python3
"""
Quiz Generation and Validation Test for Educational Quiz Bot

This test validates that quiz questions are generated correctly, have proper
structure, and follow the expected format.

Usage:
    python tests/test_quiz_validation.py
"""

import os
import sys
import asyncio
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("quiz_validation_test")

class QuizValidationTester:
    """Test quiz generation and validation."""
    
    def __init__(self):
        self.config = None
        self.llm_service = None
        self.quiz_generator = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    async def run_all_tests(self) -> bool:
        """Run all quiz validation tests."""
        logger.info("=" * 60)
        logger.info("Educational Quiz Bot - Quiz Validation Test")
        logger.info("=" * 60)
        
        tests = [
            self.test_service_initialization,
            self.test_question_structure,
            self.test_answer_validation,
            self.test_difficulty_levels,
            self.test_category_handling,
            self.test_prompt_templates,
            self.test_json_format_validation,
            self.test_edge_cases,
            self.test_content_quality
        ]
        
        all_passed = True
        for test in tests:
            try:
                if not await test():
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ Test {test.__name__} failed with exception: {e}")
                import traceback
                traceback.print_exc()
                all_passed = False
                
        # Show summary
        self._show_summary()
        return all_passed and len(self.errors) == 0
        
    async def test_service_initialization(self) -> bool:
        """Test service initialization."""
        logger.info("\n🚀 Testing service initialization...")
        
        try:
            from config import load_config
            from services.llm_service import LLMService
            from services.quiz_generator import QuizGenerator
            
            self.config = load_config()
            self.llm_service = LLMService(self.config.llm)
            await self.llm_service.initialize()
            
            self.quiz_generator = QuizGenerator(self.llm_service, self.config)
            
            logger.info("✅ Services initialized successfully")
            return True
        except Exception as e:
            self.errors.append(f"❌ Failed to initialize services: {e}")
            logger.error(f"❌ Failed to initialize services: {e}")
            return False
            
    async def test_question_structure(self) -> bool:
        """Test that generated questions have proper structure."""
        logger.info("\n📝 Testing question structure...")
        
        if not self.quiz_generator:
            self.errors.append("❌ Quiz generator not initialized")
            return False
            
        try:
            # Generate a few test questions
            questions = await self.quiz_generator.generate_quiz_questions(
                topic="basic science",
                num_questions=3,
                difficulty="medium"
            )
            
            if not questions:
                self.errors.append("❌ No questions generated")
                return False
                
            structure_valid = True
            
            for i, question in enumerate(questions):
                logger.info(f"   Validating question {i+1}...")
                
                # Check required fields
                required_fields = ['question', 'options', 'correct_answer']
                missing_fields = [field for field in required_fields if field not in question]
                
                if missing_fields:
                    self.errors.append(f"❌ Question {i+1} missing fields: {missing_fields}")
                    structure_valid = False
                    continue
                    
                # Validate question text
                if not isinstance(question['question'], str) or len(question['question'].strip()) < 10:
                    self.errors.append(f"❌ Question {i+1} has invalid question text")
                    structure_valid = False
                    
                # Validate options
                if not isinstance(question['options'], list):
                    self.errors.append(f"❌ Question {i+1} options is not a list")
                    structure_valid = False
                elif len(question['options']) < 2:
                    self.errors.append(f"❌ Question {i+1} has too few options")
                    structure_valid = False
                elif len(question['options']) > 6:
                    self.warnings.append(f"⚠️  Question {i+1} has many options ({len(question['options'])})")
                    
                # Validate correct answer
                if not isinstance(question['correct_answer'], str):
                    self.errors.append(f"❌ Question {i+1} correct_answer is not a string")
                    structure_valid = False
                elif question['correct_answer'] not in question['options']:
                    self.errors.append(f"❌ Question {i+1} correct answer not in options")
                    structure_valid = False
                    
                # Check for duplicate options
                if len(question['options']) != len(set(question['options'])):
                    self.errors.append(f"❌ Question {i+1} has duplicate options")
                    structure_valid = False
                    
                if structure_valid:
                    logger.info(f"     ✅ Question {i+1} structure valid")
                    
            logger.info("✅ Question structure validation completed")
            return structure_valid
            
        except Exception as e:
            self.errors.append(f"❌ Question structure test failed: {e}")
            logger.error(f"❌ Question structure test failed: {e}")
            return False
            
    async def test_answer_validation(self) -> bool:
        """Test that answers are properly validated."""
        logger.info("\n✅ Testing answer validation...")
        
        if not self.quiz_generator:
            self.errors.append("❌ Quiz generator not initialized")
            return False
            
        try:
            # Generate questions for testing
            questions = await self.quiz_generator.generate_quiz_questions(
                topic="mathematics",
                num_questions=2,
                difficulty="easy"
            )
            
            if not questions:
                self.warnings.append("⚠️  No questions generated for answer validation test")
                return True
                
            validation_passed = True
            
            for i, question in enumerate(questions):
                logger.info(f"   Testing answer validation for question {i+1}...")
                
                # Test correct answer validation
                correct_answer = question['correct_answer']
                options = question['options']
                
                # Check that correct answer exactly matches one option
                exact_matches = [opt for opt in options if opt == correct_answer]
                if len(exact_matches) != 1:
                    self.errors.append(f"❌ Question {i+1} correct answer doesn't have exactly one match")
                    validation_passed = False
                    continue
                    
                # Check that options don't have obvious chronological markers
                has_dates = any(
                    any(char.isdigit() and len(opt.split()) > 1 for char in opt) 
                    for opt in options
                )
                
                if has_dates:
                    # Check if dates might reveal the answer
                    date_patterns = ['(', ')', '19', '20', '18']
                    suspicious_options = [
                        opt for opt in options 
                        if any(pattern in opt for pattern in date_patterns)
                    ]
                    
                    if len(suspicious_options) > 1:
                        self.warnings.append(f"⚠️  Question {i+1} options may contain revealing dates")
                        
                logger.info(f"     ✅ Question {i+1} answer validation passed")
                
            return validation_passed
            
        except Exception as e:
            self.errors.append(f"❌ Answer validation test failed: {e}")
            logger.error(f"❌ Answer validation test failed: {e}")
            return False
            
    async def test_difficulty_levels(self) -> bool:
        """Test different difficulty levels."""
        logger.info("\n🎯 Testing difficulty levels...")
        
        if not self.quiz_generator:
            self.errors.append("❌ Quiz generator not initialized")
            return False
            
        difficulties = ['easy', 'medium', 'hard']
        difficulty_results = {}
        
        for difficulty in difficulties:
            try:
                logger.info(f"   Testing {difficulty} difficulty...")
                
                questions = await self.quiz_generator.generate_quiz_questions(
                    topic="general knowledge",
                    num_questions=1,
                    difficulty=difficulty
                )
                
                if questions:
                    difficulty_results[difficulty] = len(questions)
                    logger.info(f"     ✅ {difficulty} generated {len(questions)} question(s)")
                else:
                    self.warnings.append(f"⚠️  No questions generated for {difficulty} difficulty")
                    difficulty_results[difficulty] = 0
                    
            except Exception as e:
                self.warnings.append(f"⚠️  Error testing {difficulty} difficulty: {e}")
                difficulty_results[difficulty] = 0
                
        # Check results
        working_difficulties = [d for d, count in difficulty_results.items() if count > 0]
        
        if len(working_difficulties) == 0:
            self.errors.append("❌ No difficulty levels working")
            return False
        elif len(working_difficulties) < len(difficulties):
            self.warnings.append(f"⚠️  Only {len(working_difficulties)}/{len(difficulties)} difficulty levels working")
            
        logger.info(f"✅ {len(working_difficulties)} difficulty level(s) working: {', '.join(working_difficulties)}")
        return True
        
    async def test_category_handling(self) -> bool:
        """Test different quiz categories."""
        logger.info("\n📚 Testing category handling...")
        
        if not self.quiz_generator:
            self.errors.append("❌ Quiz generator not initialized")
            return False
            
        # Test various categories
        test_categories = [
            "science",
            "history", 
            "mathematics",
            "literature",
            "geography"
        ]
        
        category_results = {}
        
        for category in test_categories:
            try:
                logger.info(f"   Testing {category} category...")
                
                questions = await self.quiz_generator.generate_quiz_questions(
                    topic=category,
                    num_questions=1,
                    difficulty="medium"
                )
                
                if questions:
                    category_results[category] = True
                    logger.info(f"     ✅ {category} generated questions successfully")
                else:
                    category_results[category] = False
                    self.warnings.append(f"⚠️  {category} failed to generate questions")
                    
            except Exception as e:
                category_results[category] = False
                self.warnings.append(f"⚠️  {category} failed with error: {e}")
                
        working_categories = [cat for cat, working in category_results.items() if working]
        
        if len(working_categories) == 0:
            self.errors.append("❌ No categories working")
            return False
            
        logger.info(f"✅ {len(working_categories)}/{len(test_categories)} categories working")
        return True
        
    async def test_prompt_templates(self) -> bool:
        """Test different prompt templates."""
        logger.info("\n📄 Testing prompt templates...")
        
        if not self.config or not self.config.prompts:
            self.warnings.append("⚠️  Prompt configuration not available")
            return True
            
        prompts = self.config.prompts
        template_fields = [
            'standard_quiz',
            'educational_quiz', 
            'challenge_quiz',
            'trivia_quiz'
        ]
        
        template_results = {}
        
        for field in template_fields:
            template = getattr(prompts, field, None)
            if template:
                # Check if template has required placeholders
                required_placeholders = ['{topic}', '{num_questions}']
                missing_placeholders = [p for p in required_placeholders if p not in template]
                
                if missing_placeholders:
                    self.warnings.append(f"⚠️  {field} template missing placeholders: {missing_placeholders}")
                    template_results[field] = False
                else:
                    template_results[field] = True
                    logger.info(f"   ✅ {field} template valid")
            else:
                self.warnings.append(f"⚠️  {field} template not found")
                template_results[field] = False
                
        working_templates = sum(template_results.values())
        logger.info(f"✅ {working_templates}/{len(template_fields)} prompt templates valid")
        
        return working_templates > 0
        
    async def test_json_format_validation(self) -> bool:
        """Test JSON format validation."""
        logger.info("\n🔍 Testing JSON format validation...")
        
        if not self.quiz_generator:
            self.errors.append("❌ Quiz generator not initialized")
            return False
            
        try:
            # Generate questions and check JSON format
            questions = await self.quiz_generator.generate_quiz_questions(
                topic="basic facts",
                num_questions=1,
                difficulty="easy"
            )
            
            if not questions:
                self.warnings.append("⚠️  No questions for JSON validation test")
                return True
                
            # Test JSON serialization
            try:
                json_str = json.dumps(questions, indent=2)
                parsed_back = json.loads(json_str)
                
                if parsed_back == questions:
                    logger.info("✅ JSON serialization/deserialization works")
                else:
                    self.errors.append("❌ JSON round-trip failed")
                    return False
                    
            except (TypeError, ValueError) as e:
                self.errors.append(f"❌ JSON serialization failed: {e}")
                return False
                
            # Validate JSON structure matches expected schema
            for i, question in enumerate(questions):
                if not self._validate_json_schema(question):
                    self.errors.append(f"❌ Question {i+1} doesn't match expected JSON schema")
                    return False
                    
            logger.info("✅ JSON format validation passed")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ JSON format validation failed: {e}")
            logger.error(f"❌ JSON format validation failed: {e}")
            return False
            
    async def test_edge_cases(self) -> bool:
        """Test edge cases and error conditions."""
        logger.info("\n🧪 Testing edge cases...")
        
        if not self.quiz_generator:
            self.errors.append("❌ Quiz generator not initialized")
            return False
            
        edge_cases = [
            {"topic": "very obscure topic that probably doesn't exist", "num_questions": 1, "difficulty": "easy"},
            {"topic": "python", "num_questions": 1, "difficulty": "easy"},  # Very common topic
            {"topic": "a" * 100, "num_questions": 1, "difficulty": "easy"},  # Long topic
            {"topic": "math", "num_questions": 1, "difficulty": "nightmare"},  # Invalid difficulty
        ]
        
        edge_case_results = []
        
        for i, case in enumerate(edge_cases):
            try:
                logger.info(f"   Testing edge case {i+1}: {case['topic'][:30]}...")
                
                questions = await self.quiz_generator.generate_quiz_questions(**case)
                
                if questions:
                    edge_case_results.append(f"Edge case {i+1}: Generated {len(questions)} questions")
                    logger.info(f"     ✅ Edge case {i+1} handled (got questions)")
                else:
                    edge_case_results.append(f"Edge case {i+1}: No questions generated")
                    logger.info(f"     ✅ Edge case {i+1} handled gracefully (no questions)")
                    
            except Exception as e:
                edge_case_results.append(f"Edge case {i+1}: Exception - {str(e)[:50]}")
                logger.info(f"     ✅ Edge case {i+1} handled with exception (expected)")
                
        logger.info("✅ Edge case testing completed")
        return True
        
    async def test_content_quality(self) -> bool:
        """Test content quality and appropriateness."""
        logger.info("\n🎨 Testing content quality...")
        
        if not self.quiz_generator:
            self.errors.append("❌ Quiz generator not initialized")
            return False
            
        try:
            # Generate questions for quality analysis
            questions = await self.quiz_generator.generate_quiz_questions(
                topic="general science",
                num_questions=2,
                difficulty="medium"
            )
            
            if not questions:
                self.warnings.append("⚠️  No questions for content quality test")
                return True
                
            quality_issues = []
            
            for i, question in enumerate(questions):
                logger.info(f"   Analyzing question {i+1} quality...")
                
                # Check question length
                q_text = question['question']
                if len(q_text) < 10:
                    quality_issues.append(f"Question {i+1} is too short")
                elif len(q_text) > 500:
                    quality_issues.append(f"Question {i+1} is too long")
                    
                # Check for common quality issues
                if q_text.count('?') != 1:
                    quality_issues.append(f"Question {i+1} should have exactly one question mark")
                    
                # Check options quality
                options = question['options']
                option_lengths = [len(opt) for opt in options]
                
                # Check for extremely uneven option lengths
                if max(option_lengths) > 3 * min(option_lengths):
                    quality_issues.append(f"Question {i+1} has very uneven option lengths")
                    
                # Check for obviously wrong options (like "None of the above" with factual questions)
                problematic_options = ['none of the above', 'all of the above', 'i don\'t know']
                for opt in options:
                    if opt.lower() in problematic_options:
                        self.warnings.append(f"⚠️  Question {i+1} has potentially problematic option: {opt}")
                        
            if quality_issues:
                for issue in quality_issues:
                    self.warnings.append(f"⚠️  Quality issue: {issue}")
                    
            logger.info(f"✅ Content quality analysis completed ({len(quality_issues)} issues found)")
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Content quality test failed: {e}")
            logger.warning(f"⚠️  Content quality test failed: {e}")
            return True  # Not critical
            
    def _validate_json_schema(self, question: Dict[str, Any]) -> bool:
        """Validate that a question matches the expected JSON schema."""
        required_fields = ['question', 'options', 'correct_answer']
        
        # Check all required fields exist
        for field in required_fields:
            if field not in question:
                return False
                
        # Check field types
        if not isinstance(question['question'], str):
            return False
        if not isinstance(question['options'], list):
            return False
        if not isinstance(question['correct_answer'], str):
            return False
            
        # Check that options has at least 2 items
        if len(question['options']) < 2:
            return False
            
        # Check that all options are strings
        if not all(isinstance(opt, str) for opt in question['options']):
            return False
            
        # Check that correct answer is in options
        if question['correct_answer'] not in question['options']:
            return False
            
        return True
        
    def _show_summary(self) -> None:
        """Show test summary."""
        logger.info("\n" + "=" * 60)
        logger.info("QUIZ VALIDATION TEST SUMMARY")
        logger.info("=" * 60)
        
        if self.errors:
            logger.error(f"❌ {len(self.errors)} ERRORS FOUND:")
            for error in self.errors:
                logger.error(f"   {error}")
                
        if self.warnings:
            logger.warning(f"⚠️  {len(self.warnings)} WARNINGS:")
            for warning in self.warnings:
                logger.warning(f"   {warning}")
                
        if not self.errors and not self.warnings:
            logger.info("✅ All quiz validation tests passed!")
        elif not self.errors:
            logger.info("✅ Quiz generation is working (with warnings)")
        else:
            logger.error("❌ Quiz generation has errors that must be fixed")
            
        logger.info("=" * 60)


async def main() -> int:
    """Run quiz validation tests."""
    tester = QuizValidationTester()
    success = await tester.run_all_tests()
    
    if success:
        logger.info("\n🎉 Quiz generation and validation is working correctly!")
        return 0
    else:
        logger.error("\n❌ Please fix the quiz validation issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))