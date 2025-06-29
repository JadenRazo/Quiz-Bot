#!/usr/bin/env python3
"""
Quick health check script to diagnose bot connection issues.
Run this script to check if the bot is experiencing connection problems.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from config import load_config
from services.database_service import DatabaseService

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_database_health():
    """Check database connection health."""
    print("🔍 Checking database connection...")
    
    try:
        # Load configuration
        load_dotenv()
        config = load_config()
        
        # Initialize database service
        db_service = DatabaseService(config=config.database)
        await db_service.initialize()
        
        # Test basic connection
        start_time = datetime.now()
        async with db_service.acquire() as conn:
            result = await conn.fetchval("SELECT version()")
            
        connection_time = datetime.now() - start_time
        
        print(f"✅ Database connection successful!")
        print(f"   Connection time: {connection_time.total_seconds():.2f}s")
        print(f"   PostgreSQL version: {result}")
        
        # Test a more complex query
        start_time = datetime.now()
        async with db_service.acquire() as conn:
            user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            
        query_time = datetime.now() - start_time
        
        print(f"✅ Database query successful!")
        print(f"   Query time: {query_time.total_seconds():.2f}s")
        print(f"   Total users: {user_count}")
        
        # Check pool stats
        if hasattr(db_service, '_pool_stats'):
            stats = db_service._pool_stats
            print(f"📊 Connection pool stats:")
            print(f"   Queries executed: {stats['queries_executed']}")
            print(f"   Errors: {stats['errors']}")
        
        await db_service.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def check_environment():
    """Check environment variables and configuration."""
    print("🔍 Checking environment configuration...")
    
    required_vars = [
        'DISCORD_TOKEN',
        'POSTGRES_HOST',
        'POSTGRES_PORT', 
        'POSTGRES_DB',
        'POSTGRES_USER',
        'POSTGRES_PASSWORD'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        return False
    else:
        print("✅ All required environment variables present")
        
        # Show database config (without password)
        print(f"   Database host: {os.getenv('POSTGRES_HOST')}")
        print(f"   Database port: {os.getenv('POSTGRES_PORT')}")
        print(f"   Database name: {os.getenv('POSTGRES_DB')}")
        print(f"   Database user: {os.getenv('POSTGRES_USER')}")
        return True

def check_log_file():
    """Check recent log entries for connection issues."""
    print("🔍 Checking recent bot logs...")
    
    log_file = "/quiz_bot/discord_bot.log"
    
    if not os.path.exists(log_file):
        print("❌ Log file not found")
        return False
    
    try:
        # Read last 50 lines
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-50:] if len(lines) > 50 else lines
        
        # Look for connection issues
        session_invalidations = 0
        database_errors = 0
        
        for line in recent_lines:
            if "session has been invalidated" in line:
                session_invalidations += 1
            if "database" in line.lower() and ("error" in line.lower() or "timeout" in line.lower()):
                database_errors += 1
        
        print(f"📊 Recent log analysis (last {len(recent_lines)} lines):")
        print(f"   Session invalidations: {session_invalidations}")
        print(f"   Database errors: {database_errors}")
        
        if session_invalidations > 0:
            print("⚠️  Recent session invalidations detected - this may indicate network issues")
        
        if database_errors > 0:
            print("⚠️  Recent database errors detected - this may cause session invalidations")
        
        return session_invalidations == 0 and database_errors == 0
        
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        return False

async def main():
    """Run all health checks."""
    print("🤖 Quiz Bot Health Check")
    print("=" * 50)
    
    checks = [
        ("Environment Configuration", check_environment),
        ("Log File Analysis", check_log_file),
        ("Database Connection", check_database_health)
    ]
    
    results = []
    
    for name, check_func in checks:
        print(f"\n{name}:")
        print("-" * len(name))
        
        if asyncio.iscoroutinefunction(check_func):
            result = await check_func()
        else:
            result = check_func()
            
        results.append((name, result))
        
        if not result:
            print(f"⚠️  {name} check failed!")
    
    print("\n" + "=" * 50)
    print("📋 Summary:")
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All health checks passed! Bot should be stable.")
    else:
        print("\n⚠️  Some health checks failed. Bot may experience connection issues.")
        print("\n🔧 Recommended actions:")
        print("   1. Check database connection stability")
        print("   2. Monitor bot logs for connection timeouts")
        print("   3. Consider restarting the bot if issues persist")
        print("   4. Verify network connectivity to database server")

if __name__ == "__main__":
    asyncio.run(main())