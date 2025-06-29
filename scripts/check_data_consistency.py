#!/usr/bin/env python3
"""
Database consistency checker and repair tool for Quiz Bot.

This script identifies and optionally fixes data inconsistencies in the quiz bot database.
Run this script periodically to maintain data integrity.

Usage:
    python scripts/check_data_consistency.py --check-only
    python scripts/check_data_consistency.py --fix-issues
    python scripts/check_data_consistency.py --user-id 123456789
"""

import asyncio
import argparse
import sys
import os
from typing import List, Dict, Any

# Add the parent directory to the path to import bot modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import DatabaseService
from utils.data_validation import validate_database_consistency, calculate_accuracy
from config import load_config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def check_all_users_consistency(db_service: DatabaseService, fix_issues: bool = False) -> Dict[str, Any]:
    """
    Check data consistency for all users in the database.
    
    Args:
        db_service: Database service instance
        fix_issues: Whether to automatically fix found issues
    
    Returns:
        Summary of consistency check results
    """
    logger.info("Starting comprehensive consistency check...")
    
    inconsistent_users = []
    total_users_checked = 0
    total_issues_found = 0
    
    try:
        conn = await db_service.get_connection()
        try:
            # Get all users with quiz activity
            user_query = """
            SELECT DISTINCT user_id FROM user_quiz_sessions
            ORDER BY user_id
            """
            user_rows = await conn.fetch(user_query)
            
            for user_row in user_rows:
                user_id = user_row['user_id']
                total_users_checked += 1
                
                # Check consistency for this user
                consistency_result = await validate_database_consistency(db_service, user_id)
                
                if not consistency_result['consistent']:
                    inconsistent_users.append(consistency_result)
                    total_issues_found += len(consistency_result['issues'])
                    
                    logger.warning(f"User {user_id} has {len(consistency_result['issues'])} issues:")
                    for issue in consistency_result['issues']:
                        logger.warning(f"  - {issue}")
                    
                    if fix_issues:
                        await fix_user_data_issues(db_service, user_id)
                
                # Progress logging
                if total_users_checked % 100 == 0:
                    logger.info(f"Checked {total_users_checked} users so far...")
            
        finally:
            await db_service.release_connection(conn)
            
    except Exception as e:
        logger.error(f"Error during consistency check: {e}")
        return {'error': str(e)}
    
    logger.info(f"Consistency check complete: {total_users_checked} users checked, {len(inconsistent_users)} with issues")
    
    return {
        'total_users_checked': total_users_checked,
        'inconsistent_users_count': len(inconsistent_users),
        'total_issues_found': total_issues_found,
        'inconsistent_users': inconsistent_users,
        'fix_applied': fix_issues
    }


async def fix_user_data_issues(db_service: DatabaseService, user_id: int) -> bool:
    """
    Attempt to fix data consistency issues for a specific user.
    
    Args:
        db_service: Database service instance
        user_id: User ID to fix
    
    Returns:
        True if fixes were applied successfully
    """
    logger.info(f"Attempting to fix data issues for user {user_id}")
    
    try:
        conn = await db_service.get_connection()
        try:
            async with conn.transaction():
                # Get aggregated data from sessions table (source of truth)
                session_query = """
                SELECT 
                    COUNT(DISTINCT quiz_id) as session_count,
                    SUM(correct_answers) as session_correct,
                    SUM(wrong_answers) as session_wrong,
                    SUM(points) as session_points
                FROM user_quiz_sessions WHERE user_id = $1
                """
                session_stats = await conn.fetchrow(session_query, user_id)
                
                if session_stats:
                    session_data = dict(session_stats)
                    
                    # Update users table to match session aggregates
                    update_query = """
                    UPDATE users SET
                        quizzes_taken = $2,
                        correct_answers = $3,
                        wrong_answers = $4,
                        points = $5
                    WHERE user_id = $1
                    """
                    await conn.execute(
                        update_query,
                        user_id,
                        session_data['session_count'] or 0,
                        session_data['session_correct'] or 0,
                        session_data['session_wrong'] or 0,
                        session_data['session_points'] or 0
                    )
                    
                    logger.info(f"Fixed user {user_id} stats: quizzes={session_data['session_count']}, "
                              f"correct={session_data['session_correct']}, wrong={session_data['session_wrong']}, "
                              f"points={session_data['session_points']}")
                    
                    # Remove duplicate sessions if any exist
                    duplicate_query = """
                    DELETE FROM user_quiz_sessions 
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM user_quiz_sessions 
                        WHERE user_id = $1 
                        GROUP BY quiz_id
                    ) AND user_id = $1
                    """
                    deleted_rows = await conn.execute(duplicate_query, user_id)
                    if deleted_rows:
                        logger.info(f"Removed duplicate sessions for user {user_id}")
                    
                    return True
                    
        finally:
            await db_service.release_connection(conn)
            
    except Exception as e:
        logger.error(f"Error fixing data for user {user_id}: {e}")
        return False
    
    return False


async def check_and_fix_duplicate_sessions(db_service: DatabaseService) -> Dict[str, Any]:
    """
    Find and remove duplicate quiz sessions.
    
    Args:
        db_service: Database service instance
    
    Returns:
        Summary of duplicate removal
    """
    logger.info("Checking for duplicate quiz sessions...")
    
    try:
        conn = await db_service.get_connection()
        try:
            # Find duplicates
            duplicate_query = """
            SELECT user_id, quiz_id, COUNT(*) as count
            FROM user_quiz_sessions 
            GROUP BY user_id, quiz_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            """
            duplicates = await conn.fetch(duplicate_query)
            
            if not duplicates:
                logger.info("No duplicate sessions found")
                return {'duplicates_found': 0, 'duplicates_removed': 0}
            
            logger.warning(f"Found {len(duplicates)} sets of duplicate sessions")
            
            total_removed = 0
            for dup in duplicates:
                logger.warning(f"User {dup['user_id']}, Quiz {dup['quiz_id']}: {dup['count']} entries")
                
                # Remove duplicates, keeping the earliest one
                remove_query = """
                DELETE FROM user_quiz_sessions 
                WHERE user_id = $1 AND quiz_id = $2 AND id NOT IN (
                    SELECT MIN(id) 
                    FROM user_quiz_sessions 
                    WHERE user_id = $1 AND quiz_id = $2
                )
                """
                removed_count = await conn.execute(remove_query, dup['user_id'], dup['quiz_id'])
                total_removed += (dup['count'] - 1)  # Removed all but one
            
            logger.info(f"Removed {total_removed} duplicate sessions")
            
            return {
                'duplicates_found': len(duplicates),
                'duplicates_removed': total_removed
            }
            
        finally:
            await db_service.release_connection(conn)
            
    except Exception as e:
        logger.error(f"Error checking duplicates: {e}")
        return {'error': str(e)}


async def generate_consistency_report(db_service: DatabaseService) -> Dict[str, Any]:
    """
    Generate a comprehensive consistency report.
    
    Args:
        db_service: Database service instance
    
    Returns:
        Detailed consistency report
    """
    logger.info("Generating consistency report...")
    
    try:
        conn = await db_service.get_connection()
        try:
            report = {}
            
            # Total users and sessions
            user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            session_count = await conn.fetchval("SELECT COUNT(*) FROM user_quiz_sessions")
            
            report['overview'] = {
                'total_users': user_count,
                'total_sessions': session_count
            }
            
            # Users with missing sessions
            missing_sessions_query = """
            SELECT COUNT(*) FROM users u
            WHERE u.quizzes_taken > 0 
            AND NOT EXISTS (SELECT 1 FROM user_quiz_sessions s WHERE s.user_id = u.user_id)
            """
            missing_sessions = await conn.fetchval(missing_sessions_query)
            report['missing_sessions'] = missing_sessions
            
            # Sessions with missing users
            orphaned_sessions_query = """
            SELECT COUNT(*) FROM user_quiz_sessions s
            WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = s.user_id)
            """
            orphaned_sessions = await conn.fetchval(orphaned_sessions_query)
            report['orphaned_sessions'] = orphaned_sessions
            
            # Data range statistics
            stats_query = """
            SELECT 
                MIN(created_at) as earliest_session,
                MAX(created_at) as latest_session,
                MIN(points) as min_points,
                MAX(points) as max_points,
                AVG(points) as avg_points
            FROM user_quiz_sessions
            """
            stats = await conn.fetchrow(stats_query)
            if stats:
                report['statistics'] = dict(stats)
            
            logger.info(f"Report generated: {user_count} users, {session_count} sessions")
            
            return report
            
        finally:
            await db_service.release_connection(conn)
            
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return {'error': str(e)}


async def main():
    """Main function to run consistency checks and fixes."""
    parser = argparse.ArgumentParser(description='Quiz Bot Data Consistency Checker')
    parser.add_argument('--check-only', action='store_true', help='Only check for issues, do not fix')
    parser.add_argument('--fix-issues', action='store_true', help='Automatically fix found issues')
    parser.add_argument('--user-id', type=int, help='Check specific user only')
    parser.add_argument('--remove-duplicates', action='store_true', help='Remove duplicate sessions')
    parser.add_argument('--report', action='store_true', help='Generate detailed consistency report')
    
    args = parser.parse_args()
    
    if not any([args.check_only, args.fix_issues, args.user_id, args.remove_duplicates, args.report]):
        print("Please specify an action: --check-only, --fix-issues, --user-id, --remove-duplicates, or --report")
        return
    
    try:
        # Load configuration
        config = load_config()
        
        # Initialize database service
        db_service = DatabaseService(config.database)
        await db_service.initialize()
        
        # Run requested operations
        if args.report:
            report = await generate_consistency_report(db_service)
            print("\n=== CONSISTENCY REPORT ===")
            for key, value in report.items():
                print(f"{key}: {value}")
        
        if args.remove_duplicates:
            dup_result = await check_and_fix_duplicate_sessions(db_service)
            print(f"\nDuplicate removal: {dup_result}")
        
        if args.user_id:
            result = await validate_database_consistency(db_service, args.user_id)
            print(f"\nUser {args.user_id} consistency check:")
            print(f"  Consistent: {result['consistent']}")
            if result['issues']:
                print("  Issues found:")
                for issue in result['issues']:
                    print(f"    - {issue}")
            
            if args.fix_issues and not result['consistent']:
                fixed = await fix_user_data_issues(db_service, args.user_id)
                print(f"  Fix applied: {fixed}")
        
        elif args.check_only or args.fix_issues:
            result = await check_all_users_consistency(db_service, fix_issues=args.fix_issues)
            print(f"\n=== CONSISTENCY CHECK RESULTS ===")
            print(f"Users checked: {result.get('total_users_checked', 0)}")
            print(f"Users with issues: {result.get('inconsistent_users_count', 0)}")
            print(f"Total issues found: {result.get('total_issues_found', 0)}")
            if args.fix_issues:
                print(f"Fixes applied: {result.get('fix_applied', False)}")
        
        # Clean up
        await db_service.close()
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())