#!/usr/bin/env python3
"""
Comprehensive Test Runner for Educational Quiz Bot

This script runs all available tests in the correct order and provides
detailed diagnostics to help developers identify and fix issues.

Usage:
    python tests/run_comprehensive_tests.py                    # Run all tests
    python tests/run_comprehensive_tests.py --quick           # Run essential tests only
    python tests/run_comprehensive_tests.py --category config # Run specific category
    python tests/run_comprehensive_tests.py --help           # Show help

Categories:
    config     - Configuration and environment validation
    database   - Database connectivity and operations
    services   - LLM and other service functionality  
    cogs       - Discord cog functionality
    integration- End-to-end workflow testing
    all        - All tests (default)
"""

import os
import sys
import asyncio
import subprocess
import argparse
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("comprehensive_test")

class ComprehensiveTestRunner:
    """Run all tests with detailed diagnostics."""
    
    def __init__(self):
        self.test_results: Dict[str, Dict[str, Any]] = {}
        self.start_time = datetime.now()
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        
        # Define test categories and their tests
        self.test_categories = {
            'config': {
                'name': 'Configuration & Environment',
                'description': 'Validates configuration files, environment variables, and file structure',
                'tests': [
                    ('test_configuration.py', 'Configuration validation', True)
                ],
                'required': True
            },
            'database': {
                'name': 'Database Operations',
                'description': 'Tests database connectivity, schema, and operations',
                'tests': [
                    ('test_database_setup.py', 'Database setup and connectivity', True),
                    ('test_database_operations.py', 'Database operations', False)
                ],
                'required': True
            },
            'services': {
                'name': 'Service Integration',
                'description': 'Tests LLM services and other external integrations',
                'tests': [
                    ('test_llm_service.py', 'LLM service functionality', False),
                    ('test_quiz_validation.py', 'Quiz generation and validation', False)
                ],
                'required': True
            },
            'cogs': {
                'name': 'Discord Cogs',
                'description': 'Tests Discord bot cog functionality',
                'tests': [
                    ('test_cog_functionality.py', 'Cog loading and functionality', False),
                    ('test_multi_guild_quizzes.py', 'Multi-guild functionality', False)
                ],
                'required': False
            },
            'integration': {
                'name': 'Integration Testing',
                'description': 'End-to-end workflow and integration tests',
                'tests': [
                    ('test_integration_workflow.py', 'Complete workflow integration', False)
                ],
                'required': False
            },
            'performance': {
                'name': 'Performance Testing',
                'description': 'Performance benchmarks and optimization metrics',
                'tests': [
                    ('performance/run_performance_tests.py', 'Comprehensive performance testing', False)
                ],
                'required': False
            }
        }
        
    async def run_tests(self, categories: List[str] = None, quick_mode: bool = False) -> bool:
        """Run tests for specified categories."""
        logger.info("=" * 80)
        logger.info("Educational Quiz Bot - Comprehensive Test Suite")
        logger.info("=" * 80)
        
        # Determine which categories to run
        if categories is None:
            categories = list(self.test_categories.keys())
        elif 'all' in categories:
            categories = list(self.test_categories.keys())
            
        # In quick mode, only run essential tests
        if quick_mode:
            categories = [cat for cat in categories if self.test_categories[cat]['required']]
            logger.info("🚀 Running in QUICK MODE - essential tests only")
            
        logger.info(f"📋 Running tests for categories: {', '.join(categories)}")
        logger.info(f"⏰ Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Pre-flight checks
        if not await self._pre_flight_checks():
            logger.error("❌ Pre-flight checks failed!")
            return False
            
        # Run tests by category
        overall_success = True
        
        for category in categories:
            if category not in self.test_categories:
                logger.error(f"❌ Unknown test category: {category}")
                continue
                
            category_info = self.test_categories[category]
            success = await self._run_category_tests(category, category_info, quick_mode)
            
            if not success:
                overall_success = False
                if category_info['required']:
                    logger.error(f"❌ Required category '{category}' failed - stopping execution")
                    break
                    
        # Show final results
        await self._show_final_results(overall_success)
        
        return overall_success
        
    async def _pre_flight_checks(self) -> bool:
        """Run pre-flight checks before main tests."""
        logger.info("\n🔍 Running pre-flight checks...")
        
        checks = [
            self._check_python_version,
            self._check_file_structure,
            self._check_virtual_environment,
            self._check_test_files_exist
        ]
        
        all_passed = True
        for check in checks:
            try:
                if not await check():
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ Pre-flight check {check.__name__} failed: {e}")
                all_passed = False
                
        if all_passed:
            logger.info("✅ All pre-flight checks passed")
        else:
            logger.error("❌ Some pre-flight checks failed")
            
        return all_passed
        
    async def _check_python_version(self) -> bool:
        """Check Python version."""
        version = sys.version_info
        if version < (3, 8):
            logger.error(f"❌ Python 3.8+ required, found {version.major}.{version.minor}")
            return False
        logger.info(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
        return True
        
    async def _check_file_structure(self) -> bool:
        """Check basic file structure."""
        required_files = [
            "main.py",
            "config.py", 
            "requirements.txt"
        ]
        
        required_dirs = [
            "cogs",
            "services",
            "utils",
            "tests"
        ]
        
        missing = []
        
        for file_path in required_files:
            if not Path(file_path).exists():
                missing.append(f"file: {file_path}")
                
        for dir_path in required_dirs:
            if not Path(dir_path).is_dir():
                missing.append(f"directory: {dir_path}")
                
        if missing:
            logger.error(f"❌ Missing: {', '.join(missing)}")
            return False
            
        logger.info("✅ File structure is correct")
        return True
        
    async def _check_virtual_environment(self) -> bool:
        """Check virtual environment."""
        venv_path = "/root/bot-env/"
        if Path(venv_path).exists():
            logger.info(f"✅ Virtual environment found at {venv_path}")
        else:
            logger.warning(f"⚠️  Expected virtual environment not found at {venv_path}")
            
        # Check if we're in a virtual environment
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            logger.info("✅ Running in virtual environment")
        else:
            logger.warning("⚠️  Not running in virtual environment")
            
        return True
        
    async def _check_test_files_exist(self) -> bool:
        """Check that all test files exist."""
        missing_tests = []
        
        for category_info in self.test_categories.values():
            for test_file, _, _ in category_info['tests']:
                test_path = Path("tests") / test_file
                if not test_path.exists():
                    missing_tests.append(test_file)
                    
        if missing_tests:
            logger.error(f"❌ Missing test files: {', '.join(missing_tests)}")
            return False
            
        logger.info("✅ All test files are present")
        return True
        
    async def _run_category_tests(self, category: str, category_info: Dict[str, Any], quick_mode: bool) -> bool:
        """Run tests for a specific category."""
        logger.info(f"\n{'='*60}")
        logger.info(f"📁 CATEGORY: {category_info['name']}")
        logger.info(f"📝 {category_info['description']}")
        logger.info(f"{'='*60}")
        
        category_success = True
        category_results = []
        
        for test_file, test_description, is_essential in category_info['tests']:
            # In quick mode, skip non-essential tests
            if quick_mode and not is_essential:
                logger.info(f"⏭️  Skipping {test_description} (non-essential)")
                self.skipped_tests += 1
                continue
                
            self.total_tests += 1
            
            logger.info(f"\n🧪 Running: {test_description}")
            logger.info(f"📄 File: {test_file}")
            
            start_time = datetime.now()
            
            try:
                # Run the test
                result = subprocess.run(
                    [sys.executable, f"tests/{test_file}"],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # Store results
                test_result = {
                    'success': result.returncode == 0,
                    'duration': duration,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'description': test_description
                }
                
                category_results.append(test_result)
                
                if result.returncode == 0:
                    logger.info(f"✅ PASSED: {test_description} ({duration:.1f}s)")
                    self.passed_tests += 1
                else:
                    logger.error(f"❌ FAILED: {test_description} ({duration:.1f}s)")
                    self.failed_tests += 1
                    category_success = False
                    
                    # Show error output
                    if result.stderr:
                        logger.error("STDERR:")
                        for line in result.stderr.split('\n')[-10:]:  # Last 10 lines
                            if line.strip():
                                logger.error(f"  {line}")
                                
                    if result.stdout:
                        # Show last few lines of stdout for context
                        stdout_lines = result.stdout.split('\n')
                        relevant_lines = [line for line in stdout_lines if '❌' in line or 'ERROR' in line.upper()][-5:]
                        if relevant_lines:
                            logger.error("Error details:")
                            for line in relevant_lines:
                                if line.strip():
                                    logger.error(f"  {line}")
                                    
            except subprocess.TimeoutExpired:
                logger.error(f"❌ TIMEOUT: {test_description} (>300s)")
                self.failed_tests += 1
                category_success = False
                
                test_result = {
                    'success': False,
                    'duration': 300,
                    'stdout': '',
                    'stderr': 'Test timed out after 300 seconds',
                    'description': test_description
                }
                category_results.append(test_result)
                
            except Exception as e:
                logger.error(f"❌ ERROR: {test_description} - {e}")
                self.failed_tests += 1
                category_success = False
                
                test_result = {
                    'success': False,
                    'duration': 0,
                    'stdout': '',
                    'stderr': str(e),
                    'description': test_description
                }
                category_results.append(test_result)
                
        # Store category results
        self.test_results[category] = {
            'info': category_info,
            'success': category_success,
            'results': category_results
        }
        
        # Show category summary
        passed = sum(1 for r in category_results if r['success'])
        total = len(category_results)
        
        if category_success:
            logger.info(f"\n✅ CATEGORY PASSED: {category_info['name']} ({passed}/{total} tests)")
        else:
            logger.error(f"\n❌ CATEGORY FAILED: {category_info['name']} ({passed}/{total} tests)")
            
        return category_success
        
    async def _show_final_results(self, overall_success: bool) -> None:
        """Show comprehensive final results."""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        logger.info("\n" + "=" * 80)
        logger.info("🏁 FINAL TEST RESULTS")
        logger.info("=" * 80)
        
        # Overall summary
        logger.info(f"⏰ Total time: {total_duration:.1f}s")
        logger.info(f"📊 Total tests: {self.total_tests}")
        logger.info(f"✅ Passed: {self.passed_tests}")
        logger.info(f"❌ Failed: {self.failed_tests}")
        logger.info(f"⏭️  Skipped: {self.skipped_tests}")
        
        # Category breakdown
        logger.info(f"\n📁 CATEGORY BREAKDOWN:")
        for category, results in self.test_results.items():
            category_info = results['info']
            category_results = results['results']
            
            passed = sum(1 for r in category_results if r['success'])
            total = len(category_results)
            status = "✅ PASS" if results['success'] else "❌ FAIL"
            
            logger.info(f"  {status} {category_info['name']}: {passed}/{total}")
            
            # Show failed tests
            failed_tests = [r for r in category_results if not r['success']]
            if failed_tests:
                for test in failed_tests:
                    logger.error(f"    ❌ {test['description']}")
                    
        # Recommendations
        logger.info(f"\n💡 RECOMMENDATIONS:")
        
        if overall_success:
            logger.info("🎉 All tests passed! Your bot is ready for deployment.")
            logger.info("📚 Next steps:")
            logger.info("   1. Start the bot: python main.py")
            logger.info("   2. Test bot commands in Discord")
            logger.info("   3. Monitor logs for any runtime issues")
        else:
            logger.error("❌ Some tests failed. Please address the issues above.")
            logger.info("🔧 Troubleshooting:")
            
            # Specific recommendations based on failed categories
            for category, results in self.test_results.items():
                if not results['success']:
                    category_info = results['info']
                    
                    if category == 'config':
                        logger.info("   • Configuration issues:")
                        logger.info("     - Check your .env file exists and has correct values")
                        logger.info("     - Verify all required API keys are set")
                        logger.info("     - Ensure database credentials are correct")
                        
                    elif category == 'database':
                        logger.info("   • Database issues:")
                        logger.info("     - Verify PostgreSQL is running")
                        logger.info("     - Check database connection parameters")
                        logger.info("     - Run database schema files if tables are missing")
                        logger.info("     - Ensure database user has correct permissions")
                        
                    elif category == 'services':
                        logger.info("   • Service issues:")
                        logger.info("     - Verify LLM API keys are valid and have credits")
                        logger.info("     - Check internet connectivity for API calls")
                        logger.info("     - Review API rate limits and quotas")
                        
                    elif category == 'cogs':
                        logger.info("   • Discord cog issues:")
                        logger.info("     - Check for Python syntax errors in cog files")
                        logger.info("     - Verify all imports are available")
                        logger.info("     - Review cog initialization and setup functions")
                        
                    elif category == 'integration':
                        logger.info("   • Integration issues:")
                        logger.info("     - Fix issues in earlier categories first")
                        logger.info("     - Check for missing dependencies")
                        logger.info("     - Review async/await usage in code")
                        
        # Test artifacts
        logger.info(f"\n📋 TEST ARTIFACTS:")
        logger.info(f"   • Individual test logs available in test output above")
        logger.info(f"   • Re-run specific categories: python tests/run_comprehensive_tests.py --category <name>")
        logger.info(f"   • Quick test mode: python tests/run_comprehensive_tests.py --quick")
        
        logger.info("=" * 80)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for Educational Quiz Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--category', '-c',
        choices=['config', 'database', 'services', 'cogs', 'integration', 'performance', 'all'],
        nargs='+',
        default=['all'],
        help='Test categories to run (default: all)'
    )
    
    parser.add_argument(
        '--quick', '-q',
        action='store_true',
        help='Run only essential tests for quick validation'
    )
    
    parser.add_argument(
        '--list-categories',
        action='store_true',
        help='List available test categories and exit'
    )
    
    args = parser.parse_args()
    
    # Handle list categories
    if args.list_categories:
        runner = ComprehensiveTestRunner()
        print("Available test categories:")
        for category, info in runner.test_categories.items():
            required = " (required)" if info['required'] else ""
            print(f"  {category}{required}: {info['description']}")
            for test_file, test_desc, essential in info['tests']:
                essential_marker = " [essential]" if essential else ""
                print(f"    - {test_desc}{essential_marker}")
        return 0
        
    # Run tests
    async def run_async():
        runner = ComprehensiveTestRunner()
        success = await runner.run_tests(
            categories=args.category,
            quick_mode=args.quick
        )
        return 0 if success else 1
        
    return asyncio.run(run_async())


if __name__ == "__main__":
    sys.exit(main())