#!/usr/bin/env python3
"""
Test Runner for Educational Quiz Bot

This script provides an easy way to run various tests to ensure your bot is properly configured.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py database     # Run only database tests
    python run_tests.py multi-guild  # Run multi-guild tests
"""

import sys
import subprocess
import os
from typing import List

def run_database_test() -> bool:
    """Run the database setup test."""
    print("=" * 60)
    print("Running Database Setup Test...")
    print("=" * 60)
    
    # Get the directory where this script is located
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    result = subprocess.run(
        [sys.executable, os.path.join(test_dir, "test_database_setup.py")],
        capture_output=False
    )
    
    return result.returncode == 0

def run_multi_guild_test() -> bool:
    """Run the multi-guild functionality test."""
    print("=" * 60)
    print("Running Multi-Guild Functionality Test...")
    print("=" * 60)
    
    # Get the directory where this script is located
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    result = subprocess.run(
        [sys.executable, os.path.join(test_dir, "run_multi_guild_tests.py")],
        capture_output=False
    )
    
    return result.returncode == 0

def main() -> None:
    """Main test runner."""
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == "database":
            success = run_database_test()
        elif test_type == "multi-guild":
            success = run_multi_guild_test()
        else:
            print(f"Unknown test type: {test_type}")
            print("Available tests: database, multi-guild")
            sys.exit(1)
    else:
        # Run all tests
        print("Running all tests...\n")
        
        db_success = run_database_test()
        print("\n")
        
        guild_success = run_multi_guild_test()
        
        success = db_success and guild_success
        
        print("\n" + "=" * 60)
        if success:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed. Please check the output above.")
        print("=" * 60)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()