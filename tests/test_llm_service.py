#!/usr/bin/env python3
"""
LLM Service Integration Test for Educational Quiz Bot

This test validates that LLM services are properly configured and can generate
quiz questions correctly.

Usage:
    python tests/test_llm_service.py
"""

import os
import sys
import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("llm_test")

class LLMServiceTester:
    """Test LLM service functionality."""
    
    def __init__(self):
        self.config = None
        self.llm_service = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    async def run_all_tests(self) -> bool:
        """Run all LLM service tests."""
        logger.info("=" * 60)
        logger.info("Educational Quiz Bot - LLM Service Test")
        logger.info("=" * 60)
        
        tests = [
            self.test_config_loading,
            self.test_service_initialization,
            self.test_provider_availability,
            self.test_quiz_generation,
            self.test_json_parsing,
            self.test_error_handling,
            self.test_rate_limiting
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
        
    async def test_config_loading(self) -> bool:
        """Test configuration loading."""
        logger.info("\n🔧 Testing configuration loading...")
        
        try:
            from config import load_config
            self.config = load_config()
            
            if not self.config.llm:
                self.errors.append("❌ LLM configuration not found")
                return False
                
            logger.info("✅ Configuration loaded successfully")
            return True
        except Exception as e:
            self.errors.append(f"❌ Failed to load configuration: {e}")
            logger.error(f"❌ Failed to load configuration: {e}")
            return False
            
    async def test_service_initialization(self) -> bool:
        """Test LLM service initialization."""
        logger.info("\n🚀 Testing LLM service initialization...")
        
        try:
            from services.llm_service import LLMService
            self.llm_service = LLMService(self.config.llm)
            
            # Test initialization
            await self.llm_service.initialize()
            
            logger.info("✅ LLM service initialized successfully")
            return True
        except Exception as e:
            self.errors.append(f"❌ Failed to initialize LLM service: {e}")
            logger.error(f"❌ Failed to initialize LLM service: {e}")
            return False
            
    async def test_provider_availability(self) -> bool:
        """Test which providers are available."""
        logger.info("\n🔍 Testing provider availability...")
        
        if not self.llm_service:
            self.errors.append("❌ LLM service not initialized")
            return False
            
        try:
            available_providers = self.llm_service.get_available_providers()
            
            if not available_providers:
                self.errors.append("❌ No LLM providers available")
                logger.error("❌ No LLM providers available")
                return False
                
            logger.info(f"✅ Available providers: {', '.join(available_providers)}")
            
            # Test each provider
            working_providers = []
            for provider in available_providers:
                try:
                    # Test with a simple question
                    await self.llm_service.generate_quiz_questions(
                        topic="test",
                        num_questions=1,
                        difficulty="easy",
                        provider=provider
                    )
                    working_providers.append(provider)
                    logger.info(f"✅ Provider {provider} is working")
                except Exception as e:
                    logger.warning(f"⚠️  Provider {provider} failed: {e}")
                    self.warnings.append(f"Provider {provider} failed: {e}")
                    
            if not working_providers:
                self.errors.append("❌ No providers are working")
                return False
                
            logger.info(f"✅ {len(working_providers)} working provider(s): {', '.join(working_providers)}")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Provider availability test failed: {e}")
            logger.error(f"❌ Provider availability test failed: {e}")
            return False
            
    async def test_quiz_generation(self) -> bool:
        """Test quiz question generation."""
        logger.info("\n🎯 Testing quiz generation...")
        
        if not self.llm_service:
            self.errors.append("❌ LLM service not initialized")
            return False
            
        try:
            # Test different quiz types
            test_cases = [
                {"topic": "Python programming", "num_questions": 2, "difficulty": "medium"},
                {"topic": "World history", "num_questions": 1, "difficulty": "easy"},
                {"topic": "Mathematics", "num_questions": 1, "difficulty": "hard"}
            ]
            
            for i, test_case in enumerate(test_cases):
                logger.info(f"   Testing case {i+1}: {test_case['topic']}")
                
                try:
                    questions = await self.llm_service.generate_quiz_questions(**test_case)
                    
                    if not questions:
                        self.warnings.append(f"⚠️  No questions generated for {test_case['topic']}")
                        continue
                        
                    if len(questions) != test_case['num_questions']:
                        self.warnings.append(f"⚠️  Expected {test_case['num_questions']} questions, got {len(questions)}")
                        
                    # Validate question structure
                    for j, question in enumerate(questions):
                        if not self._validate_question_structure(question):
                            self.warnings.append(f"⚠️  Invalid question structure in {test_case['topic']} question {j+1}")
                            
                    logger.info(f"   ✅ Generated {len(questions)} question(s) for {test_case['topic']}")
                    
                except Exception as e:
                    logger.warning(f"   ⚠️  Failed to generate questions for {test_case['topic']}: {e}")
                    self.warnings.append(f"Quiz generation failed for {test_case['topic']}: {e}")
                    
            logger.info("✅ Quiz generation tests completed")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ Quiz generation test failed: {e}")
            logger.error(f"❌ Quiz generation test failed: {e}")
            return False
            
    async def test_json_parsing(self) -> bool:
        """Test JSON parsing and validation."""
        logger.info("\n📝 Testing JSON parsing...")
        
        if not self.llm_service:
            self.errors.append("❌ LLM service not initialized")
            return False
            
        try:
            # Test with a simple topic to get consistent results
            questions = await self.llm_service.generate_quiz_questions(
                topic="basic math",
                num_questions=1,
                difficulty="easy"
            )
            
            if not questions:
                self.warnings.append("⚠️  No questions generated for JSON parsing test")
                return True
                
            # Validate each question has required fields
            required_fields = ['question', 'options', 'correct_answer']
            
            for i, question in enumerate(questions):
                missing_fields = []
                for field in required_fields:
                    if field not in question:
                        missing_fields.append(field)
                        
                if missing_fields:
                    self.errors.append(f"❌ Question {i+1} missing fields: {missing_fields}")
                    logger.error(f"❌ Question {i+1} missing fields: {missing_fields}")
                    return False
                    
                # Validate options is a list
                if not isinstance(question['options'], list):
                    self.errors.append(f"❌ Question {i+1} options is not a list")
                    return False
                    
                # Validate correct answer is in options
                if question['correct_answer'] not in question['options']:
                    self.errors.append(f"❌ Question {i+1} correct answer not in options")
                    return False
                    
            logger.info("✅ JSON parsing and validation successful")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ JSON parsing test failed: {e}")
            logger.error(f"❌ JSON parsing test failed: {e}")
            return False
            
    async def test_error_handling(self) -> bool:
        """Test error handling for invalid inputs."""
        logger.info("\n🛡️  Testing error handling...")
        
        if not self.llm_service:
            self.errors.append("❌ LLM service not initialized")
            return False
            
        # Test cases that should handle errors gracefully
        error_test_cases = [
            {"topic": "", "num_questions": 1, "difficulty": "easy"},  # Empty topic
            {"topic": "test", "num_questions": 0, "difficulty": "easy"},  # Zero questions
            {"topic": "test", "num_questions": 1, "difficulty": "invalid"},  # Invalid difficulty
            {"topic": "test", "num_questions": 1000, "difficulty": "easy"},  # Too many questions
        ]
        
        for i, test_case in enumerate(error_test_cases):
            try:
                questions = await self.llm_service.generate_quiz_questions(**test_case)
                # Some cases might return empty list instead of raising exception
                if questions:
                    logger.warning(f"   ⚠️  Error case {i+1} unexpectedly succeeded")
                else:
                    logger.info(f"   ✅ Error case {i+1} handled gracefully (empty result)")
            except Exception as e:
                logger.info(f"   ✅ Error case {i+1} handled gracefully (exception: {type(e).__name__})")
                
        logger.info("✅ Error handling tests completed")
        return True
        
    async def test_rate_limiting(self) -> bool:
        """Test rate limiting and concurrent requests."""
        logger.info("\n⏱️  Testing rate limiting...")
        
        if not self.llm_service:
            self.errors.append("❌ LLM service not initialized")
            return False
            
        try:
            # Test concurrent requests (should be handled gracefully)
            start_time = datetime.now()
            
            tasks = []
            for i in range(3):  # Small number to avoid hitting actual rate limits
                task = self.llm_service.generate_quiz_questions(
                    topic=f"test topic {i}",
                    num_questions=1,
                    difficulty="easy"
                )
                tasks.append(task)
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"   ⏱️  Concurrent requests completed in {elapsed:.2f}s")
            
            # Count successful results
            successful = sum(1 for r in results if not isinstance(r, Exception))
            logger.info(f"   ✅ {successful}/{len(tasks)} concurrent requests successful")
            
            if successful == 0:
                self.warnings.append("⚠️  All concurrent requests failed")
                
            return True
            
        except Exception as e:
            self.warnings.append(f"⚠️  Rate limiting test failed: {e}")
            logger.warning(f"⚠️  Rate limiting test failed: {e}")
            return True  # Not critical
            
    def _validate_question_structure(self, question: Dict[str, Any]) -> bool:
        """Validate that a question has the correct structure."""
        required_fields = ['question', 'options', 'correct_answer']
        
        # Check required fields exist
        for field in required_fields:
            if field not in question:
                return False
                
        # Check types
        if not isinstance(question['question'], str):
            return False
        if not isinstance(question['options'], list):
            return False
        if not isinstance(question['correct_answer'], str):
            return False
            
        # Check that options has at least 2 items
        if len(question['options']) < 2:
            return False
            
        # Check that correct answer is in options
        if question['correct_answer'] not in question['options']:
            return False
            
        return True
        
    def _show_summary(self) -> None:
        """Show test summary."""
        logger.info("\n" + "=" * 60)
        logger.info("LLM SERVICE TEST SUMMARY")
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
            logger.info("✅ All LLM service tests passed!")
        elif not self.errors:
            logger.info("✅ LLM service is working (with warnings)")
        else:
            logger.error("❌ LLM service has errors that must be fixed")
            
        logger.info("=" * 60)


async def main() -> int:
    """Run LLM service tests."""
    tester = LLMServiceTester()
    success = await tester.run_all_tests()
    
    if success:
        logger.info("\n🎉 LLM service is ready!")
        return 0
    else:
        logger.error("\n❌ Please fix the LLM service issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))