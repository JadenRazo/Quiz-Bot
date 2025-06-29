"""
Performance tests for database operations.
Measures current performance to establish baselines before optimization.
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
import psutil
import os
from unittest.mock import AsyncMock

# Import the database service
from services.database import DatabaseService
from config import load_config


class DatabasePerformanceTest:
    """Test suite for measuring database operation performance."""
    
    def __init__(self):
        self.results = {}
        self.config = load_config()
        
    async def setup_test_db(self) -> DatabaseService:
        """Set up a test database service."""
        # Use a test database configuration
        test_config = self.config.database
        db_service = DatabaseService(config=test_config)
        await db_service.initialize()
        return db_service
    
    async def measure_operation(self, operation_name: str, operation_func, iterations: int = 100):
        """Measure the performance of a database operation."""
        times = []
        memory_before = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        for i in range(iterations):
            start_time = time.perf_counter()
            try:
                await operation_func()
                end_time = time.perf_counter()
                times.append(end_time - start_time)
            except Exception as e:
                print(f"Operation failed on iteration {i}: {e}")
                continue
        
        memory_after = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        memory_delta = memory_after - memory_before
        
        if times:
            self.results[operation_name] = {
                'avg_time': statistics.mean(times),
                'median_time': statistics.median(times),
                'min_time': min(times),
                'max_time': max(times),
                'std_dev': statistics.stdev(times) if len(times) > 1 else 0,
                'total_operations': len(times),
                'failed_operations': iterations - len(times),
                'memory_delta_mb': memory_delta,
                'ops_per_second': len(times) / sum(times) if sum(times) > 0 else 0
            }
        
        return self.results.get(operation_name, {})
    
    async def test_individual_user_operations(self, db_service: DatabaseService):
        """Test performance of individual user operations (current implementation)."""
        user_id = 123456789
        username = "test_user"
        
        # Test update_user_stats
        async def update_user_stats_op():
            await db_service.update_user_stats(user_id, username, correct=5, wrong=2, points=10)
        
        await self.measure_operation("update_user_stats_individual", update_user_stats_op, 50)
        
        # Test increment_quizzes_taken
        async def increment_quizzes_op():
            await db_service.increment_quizzes_taken(user_id, username)
        
        await self.measure_operation("increment_quizzes_individual", increment_quizzes_op, 50)
        
        # Test get_basic_user_stats
        async def get_user_stats_op():
            await db_service.get_basic_user_stats(user_id)
        
        await self.measure_operation("get_user_stats", get_user_stats_op, 100)
    
    async def test_batch_operations(self, db_service: DatabaseService):
        """Test performance of batch operations."""
        # Create test data for batch operations
        batch_size = 20
        user_updates = [
            {
                'user_id': 100000 + i,
                'username': f'batch_user_{i}',
                'correct': 5,
                'wrong': 2,
                'points': 10
            }
            for i in range(batch_size)
        ]
        
        # Test batch_update_user_stats
        async def batch_update_op():
            await db_service.batch_update_user_stats(user_updates)
        
        await self.measure_operation("batch_update_user_stats", batch_update_op, 10)
        
        # Test batch_increment_quizzes_taken
        async def batch_increment_op():
            await db_service.batch_increment_quizzes_taken(user_updates)
        
        await self.measure_operation("batch_increment_quizzes", batch_increment_op, 10)
    
    async def test_connection_pool_performance(self, db_service: DatabaseService):
        """Test connection pool acquisition performance."""
        async def acquire_connection_op():
            async with db_service.acquire() as conn:
                await conn.fetchval('SELECT 1')
        
        await self.measure_operation("connection_acquisition", acquire_connection_op, 200)
    
    async def test_concurrent_operations(self, db_service: DatabaseService):
        """Test concurrent database operations."""
        async def concurrent_updates():
            tasks = []
            for i in range(10):
                user_id = 200000 + i
                task = db_service.update_user_stats(user_id, f"concurrent_user_{i}", correct=1, wrong=0, points=5)
                tasks.append(task)
            
            await asyncio.gather(*tasks)
        
        await self.measure_operation("concurrent_user_updates", concurrent_updates, 20)
    
    async def test_column_detection_overhead(self, db_service: DatabaseService):
        """Test the overhead of column name detection."""
        async def column_detection_op():
            await db_service._get_column_names("users")
        
        await self.measure_operation("column_name_detection", column_detection_op, 100)
    
    def print_results(self):
        """Print performance test results."""
        print("\n" + "="*80)
        print("DATABASE PERFORMANCE TEST RESULTS")
        print("="*80)
        
        for operation, metrics in self.results.items():
            print(f"\n{operation.upper()}:")
            print(f"  Average Time: {metrics['avg_time']*1000:.2f}ms")
            print(f"  Median Time:  {metrics['median_time']*1000:.2f}ms")
            print(f"  Min Time:     {metrics['min_time']*1000:.2f}ms")
            print(f"  Max Time:     {metrics['max_time']*1000:.2f}ms")
            print(f"  Std Dev:      {metrics['std_dev']*1000:.2f}ms")
            print(f"  Ops/Second:   {metrics['ops_per_second']:.2f}")
            print(f"  Memory Delta: {metrics['memory_delta_mb']:.2f}MB")
            if metrics['failed_operations'] > 0:
                print(f"  Failed Ops:   {metrics['failed_operations']}")
    
    def get_baseline_metrics(self) -> Dict[str, Any]:
        """Return baseline metrics for comparison after optimization."""
        return {
            'individual_ops_avg': self.results.get('update_user_stats_individual', {}).get('avg_time', 0),
            'batch_ops_avg': self.results.get('batch_update_user_stats', {}).get('avg_time', 0),
            'connection_acq_avg': self.results.get('connection_acquisition', {}).get('avg_time', 0),
            'concurrent_ops_avg': self.results.get('concurrent_user_updates', {}).get('avg_time', 0),
            'column_detection_avg': self.results.get('column_name_detection', {}).get('avg_time', 0),
            'total_memory_usage': sum(r.get('memory_delta_mb', 0) for r in self.results.values())
        }


async def run_database_performance_tests():
    """Run all database performance tests."""
    test_suite = DatabasePerformanceTest()
    
    try:
        # Skip if no database available (CI/test environment)
        if not os.getenv('POSTGRES_HOST'):
            print("Skipping database performance tests - no database configured")
            return None
            
        db_service = await test_suite.setup_test_db()
        
        print("Running database performance tests...")
        
        # Run all performance tests
        await test_suite.test_individual_user_operations(db_service)
        await test_suite.test_batch_operations(db_service)
        await test_suite.test_connection_pool_performance(db_service)
        await test_suite.test_concurrent_operations(db_service)
        await test_suite.test_column_detection_overhead(db_service)
        
        # Print results
        test_suite.print_results()
        
        # Close database connection
        await db_service.close()
        
        return test_suite.get_baseline_metrics()
        
    except Exception as e:
        print(f"Database performance tests failed: {e}")
        return None


if __name__ == "__main__":
    # Run the tests directly
    baseline_metrics = asyncio.run(run_database_performance_tests())
    if baseline_metrics:
        print(f"\nBaseline metrics saved: {baseline_metrics}")