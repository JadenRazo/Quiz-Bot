"""
Performance tests for LLM service operations.
Measures response times, caching effectiveness, and provider failover performance.
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any, Optional
import psutil
from unittest.mock import AsyncMock, patch

from services.llm_service import LLMService, TokenOptimizer
from config import load_config


class LLMPerformanceTest:
    """Test suite for measuring LLM service performance."""
    
    def __init__(self):
        self.results = {}
        self.config = load_config()
        
    def setup_test_service(self) -> LLMService:
        """Set up a test LLM service with mocked providers for consistent testing."""
        # Create a service with mock API keys for testing
        test_api_keys = {
            'openai': 'test-key',
            'anthropic': 'test-key', 
            'google': 'test-key'
        }
        return LLMService(api_keys=test_api_keys, config=self.config.llm)
    
    async def measure_operation(self, operation_name: str, operation_func, iterations: int = 10):
        """Measure the performance of an LLM operation."""
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
                'requests_per_second': len(times) / sum(times) if sum(times) > 0 else 0
            }
        
        return self.results.get(operation_name, {})
    
    async def test_provider_initialization_time(self, llm_service: LLMService):
        """Test how long it takes to initialize providers."""
        async def init_provider_op():
            provider = llm_service.get_provider("openai")
            return provider
        
        await self.measure_operation("provider_initialization", init_provider_op, 50)
    
    async def test_provider_availability_check(self, llm_service: LLMService):
        """Test provider availability checking performance."""
        async def check_availability_op():
            available = llm_service.get_available_providers()
            return available
        
        await self.measure_operation("provider_availability_check", check_availability_op, 100)
    
    async def test_mock_text_generation(self, llm_service: LLMService):
        """Test text generation with mocked responses for consistent timing."""
        
        # Mock the LLM responses to test service overhead without network delays
        mock_response = "This is a test response from the LLM service."
        
        with patch.object(llm_service, 'generate_raw_text', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response
            
            async def generate_text_op():
                response = await llm_service.generate_raw_text(
                    "Test prompt for performance measurement",
                    provider="openai"
                )
                return response
            
            await self.measure_operation("mock_text_generation", generate_text_op, 50)
    
    async def test_token_optimization_overhead(self):
        """Test the overhead of token optimization."""
        test_prompt = "This is a test prompt that needs to be optimized for token usage. " * 100
        
        async def token_optimize_op():
            optimized = TokenOptimizer.optimize_prompt(test_prompt, max_tokens=1000)
            return optimized
        
        await self.measure_operation("token_optimization", token_optimize_op, 100)
    
    async def test_concurrent_requests(self, llm_service: LLMService):
        """Test concurrent LLM request handling."""
        
        with patch.object(llm_service, 'generate_raw_text', new_callable=AsyncMock) as mock_generate:
            # Simulate variable response times
            async def mock_with_delay(*args, **kwargs):
                await asyncio.sleep(0.1)  # 100ms simulated network delay
                return "Mock response"
            
            mock_generate.side_effect = mock_with_delay
            
            async def concurrent_requests_op():
                tasks = []
                for i in range(5):
                    task = llm_service.generate_raw_text(f"Prompt {i}", provider="openai")
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                return results
            
            await self.measure_operation("concurrent_requests", concurrent_requests_op, 10)
    
    async def test_provider_failover_simulation(self, llm_service: LLMService):
        """Test provider failover performance."""
        
        call_count = 0
        
        async def failing_provider(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First two calls fail
                raise Exception("Simulated provider failure")
            return "Success after failover"
        
        with patch.object(llm_service, 'generate_raw_text', side_effect=failing_provider):
            async def failover_test_op():
                try:
                    response = await llm_service.generate_raw_text("Test prompt", provider="openai")
                    return response
                except Exception:
                    return "Failed"
            
            await self.measure_operation("provider_failover", failover_test_op, 5)
    
    async def test_cache_effectiveness(self, llm_service: LLMService):
        """Test caching effectiveness with repeated requests."""
        
        # First test: Cold cache (cache miss)
        with patch.object(llm_service, 'generate_raw_text', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "Cached response"
            
            async def cold_cache_op():
                response = await llm_service.generate_raw_text("Cache test prompt", provider="openai")
                return response
            
            await self.measure_operation("cache_miss", cold_cache_op, 20)
        
        # Second test: Warm cache (cache hit) - if caching is implemented
        # Note: The current implementation doesn't show explicit caching in generate_raw_text
        # This test would need to be adapted based on actual caching implementation
    
    def print_results(self):
        """Print LLM performance test results."""
        print("\n" + "="*80)
        print("LLM SERVICE PERFORMANCE TEST RESULTS")
        print("="*80)
        
        for operation, metrics in self.results.items():
            print(f"\n{operation.upper()}:")
            print(f"  Average Time: {metrics['avg_time']*1000:.2f}ms")
            print(f"  Median Time:  {metrics['median_time']*1000:.2f}ms")
            print(f"  Min Time:     {metrics['min_time']*1000:.2f}ms")
            print(f"  Max Time:     {metrics['max_time']*1000:.2f}ms")
            print(f"  Std Dev:      {metrics['std_dev']*1000:.2f}ms")
            print(f"  Req/Second:   {metrics['requests_per_second']:.2f}")
            print(f"  Memory Delta: {metrics['memory_delta_mb']:.2f}MB")
            if metrics['failed_operations'] > 0:
                print(f"  Failed Ops:   {metrics['failed_operations']}")
    
    def get_baseline_metrics(self) -> Dict[str, Any]:
        """Return baseline metrics for comparison after optimization."""
        return {
            'provider_init_avg': self.results.get('provider_initialization', {}).get('avg_time', 0),
            'availability_check_avg': self.results.get('provider_availability_check', {}).get('avg_time', 0),
            'text_generation_avg': self.results.get('mock_text_generation', {}).get('avg_time', 0),
            'token_optimization_avg': self.results.get('token_optimization', {}).get('avg_time', 0),
            'concurrent_requests_avg': self.results.get('concurrent_requests', {}).get('avg_time', 0),
            'failover_avg': self.results.get('provider_failover', {}).get('avg_time', 0),
            'total_memory_usage': sum(r.get('memory_delta_mb', 0) for r in self.results.values())
        }


async def run_llm_performance_tests():
    """Run all LLM performance tests."""
    test_suite = LLMPerformanceTest()
    
    try:
        llm_service = test_suite.setup_test_service()
        
        print("Running LLM service performance tests...")
        
        # Run all performance tests
        await test_suite.test_provider_initialization_time(llm_service)
        await test_suite.test_provider_availability_check(llm_service)
        await test_suite.test_mock_text_generation(llm_service)
        await test_suite.test_token_optimization_overhead()
        await test_suite.test_concurrent_requests(llm_service)
        await test_suite.test_provider_failover_simulation(llm_service)
        await test_suite.test_cache_effectiveness(llm_service)
        
        # Print results
        test_suite.print_results()
        
        return test_suite.get_baseline_metrics()
        
    except Exception as e:
        print(f"LLM performance tests failed: {e}")
        return None


if __name__ == "__main__":
    # Run the tests directly
    baseline_metrics = asyncio.run(run_llm_performance_tests())
    if baseline_metrics:
        print(f"\nBaseline metrics saved: {baseline_metrics}")