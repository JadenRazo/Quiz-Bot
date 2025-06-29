"""
Comprehensive performance test runner.
Executes all performance tests and collects baseline metrics for optimization comparison.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Add the parent directory to the path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from test_database_performance import run_database_performance_tests
from test_llm_performance import run_llm_performance_tests
from test_memory_performance import run_memory_performance_tests


class PerformanceTestRunner:
    """Orchestrates all performance tests and collects comprehensive metrics."""
    
    def __init__(self):
        self.results = {}
        self.baseline_file = "performance_baseline.json"
        
    async def run_all_tests(self):
        """Run all performance test suites."""
        print("="*80)
        print("QUIZ BOT PERFORMANCE BASELINE MEASUREMENT")
        print(f"Started at: {datetime.now().isoformat()}")
        print("="*80)
        
        # Run database performance tests
        print("\n1. Running Database Performance Tests...")
        try:
            db_metrics = await run_database_performance_tests()
            self.results['database'] = db_metrics
            print("✅ Database tests completed")
        except Exception as e:
            print(f"❌ Database tests failed: {e}")
            self.results['database'] = None
        
        # Run LLM service performance tests
        print("\n2. Running LLM Service Performance Tests...")
        try:
            llm_metrics = await run_llm_performance_tests()
            self.results['llm_service'] = llm_metrics
            print("✅ LLM service tests completed")
        except Exception as e:
            print(f"❌ LLM service tests failed: {e}")
            self.results['llm_service'] = None
        
        # Run memory performance tests
        print("\n3. Running Memory Performance Tests...")
        try:
            memory_metrics = run_memory_performance_tests()
            self.results['memory'] = memory_metrics
            print("✅ Memory tests completed")
        except Exception as e:
            print(f"❌ Memory tests failed: {e}")
            self.results['memory'] = None
    
    def calculate_performance_score(self) -> Dict[str, float]:
        """Calculate overall performance scores for comparison."""
        scores = {}
        
        # Database performance score (lower time = better)
        if self.results.get('database'):
            db_metrics = self.results['database']
            # Combine key metrics into a composite score
            individual_ops = db_metrics.get('individual_ops_avg', 0) * 1000  # Convert to ms
            batch_ops = db_metrics.get('batch_ops_avg', 0) * 1000
            connection_acq = db_metrics.get('connection_acq_avg', 0) * 1000
            
            # Lower is better, so invert for scoring
            scores['database_performance'] = 1000 / (individual_ops + batch_ops + connection_acq + 1)
        
        # LLM service performance score
        if self.results.get('llm_service'):
            llm_metrics = self.results['llm_service']
            provider_init = llm_metrics.get('provider_init_avg', 0) * 1000
            text_gen = llm_metrics.get('text_generation_avg', 0) * 1000
            
            scores['llm_performance'] = 1000 / (provider_init + text_gen + 1)
        
        # Memory efficiency score (lower memory usage = better)
        if self.results.get('memory'):
            memory_metrics = self.results['memory']
            progress_bar_mem = memory_metrics.get('progress_bar_memory_per_op', 0)
            question_creation_mem = memory_metrics.get('question_creation_memory_per_op', 0)
            
            scores['memory_efficiency'] = 10000 / (progress_bar_mem + question_creation_mem + 1)
        
        return scores
    
    def save_baseline(self):
        """Save baseline metrics to a JSON file."""
        baseline_data = {
            'timestamp': datetime.now().isoformat(),
            'version': 'baseline',
            'results': self.results,
            'performance_scores': self.calculate_performance_score()
        }
        
        try:
            with open(self.baseline_file, 'w') as f:
                json.dump(baseline_data, f, indent=2)
            print(f"\n✅ Baseline metrics saved to {self.baseline_file}")
        except Exception as e:
            print(f"❌ Failed to save baseline: {e}")
    
    def load_previous_baseline(self) -> Optional[Dict[str, Any]]:
        """Load previous baseline for comparison."""
        try:
            if os.path.exists(self.baseline_file):
                with open(self.baseline_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load previous baseline: {e}")
        return None
    
    def compare_with_previous(self, previous: Dict[str, Any]):
        """Compare current results with previous baseline."""
        print("\n" + "="*80)
        print("COMPARISON WITH PREVIOUS BASELINE")
        print("="*80)
        
        current_scores = self.calculate_performance_score()
        previous_scores = previous.get('performance_scores', {})
        
        for metric, current_score in current_scores.items():
            previous_score = previous_scores.get(metric, 0)
            if previous_score > 0:
                improvement = ((current_score - previous_score) / previous_score) * 100
                status = "🚀" if improvement > 0 else "📉"
                print(f"{status} {metric}: {improvement:+.1f}% change")
            else:
                print(f"🆕 {metric}: {current_score:.2f} (new metric)")
    
    def print_summary(self):
        """Print a comprehensive summary of all test results."""
        print("\n" + "="*80)
        print("PERFORMANCE TEST SUMMARY")
        print("="*80)
        
        # Print key metrics
        if self.results.get('database'):
            print("\n📊 Database Performance:")
            db = self.results['database']
            print(f"  Individual ops avg: {db.get('individual_ops_avg', 0)*1000:.2f}ms")
            print(f"  Batch ops avg:      {db.get('batch_ops_avg', 0)*1000:.2f}ms")
            print(f"  Connection acq avg: {db.get('connection_acq_avg', 0)*1000:.2f}ms")
        
        if self.results.get('llm_service'):
            print("\n🤖 LLM Service Performance:")
            llm = self.results['llm_service']
            print(f"  Provider init avg:  {llm.get('provider_init_avg', 0)*1000:.2f}ms")
            print(f"  Text generation:    {llm.get('text_generation_avg', 0)*1000:.2f}ms")
            print(f"  Concurrent requests: {llm.get('concurrent_requests_avg', 0)*1000:.2f}ms")
        
        if self.results.get('memory'):
            print("\n💾 Memory Performance:")
            mem = self.results['memory']
            print(f"  Progress bar mem/op: {mem.get('progress_bar_memory_per_op', 0):.0f} bytes")
            print(f"  Progress bar ops/sec: {mem.get('progress_bar_ops_per_sec', 0):.0f}")
            print(f"  Question creation mem/op: {mem.get('question_creation_memory_per_op', 0):.0f} bytes")
        
        # Print performance scores
        scores = self.calculate_performance_score()
        print("\n🏆 Performance Scores:")
        for metric, score in scores.items():
            print(f"  {metric}: {score:.2f}")
        
        print("\n💡 Optimization Opportunities Identified:")
        print("  1. Database: Implement transactional batching for user operations")
        print("  2. LLM Service: Add circuit breaker pattern for provider failover")
        print("  3. Memory: Pre-compute progress bar emoji configurations")
        print("  4. Caching: Implement column name caching for database operations")


async def main():
    """Main entry point for performance testing."""
    runner = PerformanceTestRunner()
    
    # Load previous baseline for comparison
    previous_baseline = runner.load_previous_baseline()
    
    # Run all tests
    await runner.run_all_tests()
    
    # Print summary
    runner.print_summary()
    
    # Compare with previous if available
    if previous_baseline:
        runner.compare_with_previous(previous_baseline)
    
    # Save new baseline
    runner.save_baseline()
    
    print(f"\n✅ Performance testing completed at {datetime.now().isoformat()}")
    print("📝 Next steps: Implement optimizations and re-run tests to measure improvements")


if __name__ == "__main__":
    asyncio.run(main())