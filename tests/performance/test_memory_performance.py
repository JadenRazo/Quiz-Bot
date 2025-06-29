"""
Performance tests for memory usage patterns and optimization opportunities.
Focuses on high-frequency operations like progress bars, content processing, and object creation.
"""

import time
import statistics
import gc
from typing import List, Dict, Any
import psutil
import tracemalloc
import asyncio

from utils.progress_bars import (
    create_progress_bar, 
    create_emoji_progress_bar,
    get_progress_emojis,
    create_xp_bar,
    create_accuracy_bar
)
from utils.content import truncate_content, normalize_quiz_content
from services.llm_service import Question


class MemoryPerformanceTest:
    """Test suite for measuring memory usage and allocation patterns."""
    
    def __init__(self):
        self.results = {}
        
    def measure_memory_operation(self, operation_name: str, operation_func, iterations: int = 1000):
        """Measure memory usage and allocation patterns of an operation."""
        # Start memory tracing
        tracemalloc.start()
        gc.collect()  # Clean up before measurement
        
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        times = []
        
        # Warm up
        for _ in range(10):
            operation_func()
        
        gc.collect()
        tracemalloc.clear_traces()
        
        # Actual measurement
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            iter_start = time.perf_counter()
            operation_func()
            iter_end = time.perf_counter()
            times.append(iter_end - iter_start)
        
        end_time = time.perf_counter()
        
        # Get memory statistics
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        memory_delta = final_memory - initial_memory
        
        # Calculate statistics
        self.results[operation_name] = {
            'avg_time': statistics.mean(times),
            'median_time': statistics.median(times),
            'total_time': end_time - start_time,
            'iterations': iterations,
            'operations_per_second': iterations / (end_time - start_time),
            'memory_delta_mb': memory_delta,
            'peak_memory_kb': peak / 1024,
            'current_memory_kb': current / 1024,
            'memory_per_operation_bytes': current / iterations if iterations > 0 else 0
        }
        
        gc.collect()  # Clean up after measurement
        return self.results[operation_name]
    
    def test_progress_bar_generation(self):
        """Test memory usage of progress bar generation."""
        
        # Test current implementation
        def current_progress_bar():
            return create_progress_bar(75, 100, length=10, use_emoji=False)
        
        self.measure_memory_operation("progress_bar_current", current_progress_bar, 1000)
        
        # Test emoji progress bar
        def emoji_progress_bar():
            return create_emoji_progress_bar(75, 100, length=10)
        
        self.measure_memory_operation("progress_bar_emoji", emoji_progress_bar, 1000)
        
        # Test get_progress_emojis overhead
        def emoji_config_lookup():
            return get_progress_emojis()
        
        self.measure_memory_operation("progress_emoji_lookup", emoji_config_lookup, 1000)
    
    def test_content_processing(self):
        """Test memory usage of content processing operations."""
        
        test_content = "This is a test string that needs to be processed multiple times for performance testing. " * 10
        
        # Test truncate_content
        def truncate_operation():
            return truncate_content(test_content, "question", max_length=100)
        
        self.measure_memory_operation("content_truncation", truncate_operation, 1000)
        
        # Test multiple content operations
        def multiple_content_ops():
            result1 = truncate_content(test_content, "question")
            result2 = truncate_content(test_content, "answer")
            result3 = truncate_content(test_content, "explanation")
            return [result1, result2, result3]
        
        self.measure_memory_operation("multiple_content_ops", multiple_content_ops, 500)
    
    def test_question_object_creation(self):
        """Test memory usage of Question object creation patterns."""
        
        # Test simple Question creation
        def create_simple_question():
            return Question(
                question_id=1,
                question="What is the capital of France?",
                answer="Paris",
                options=["Paris", "London", "Berlin", "Madrid"],
                category="geography",
                difficulty="easy"
            )
        
        self.measure_memory_operation("question_creation_simple", create_simple_question, 1000)
        
        # Test Question creation with content processing
        def create_processed_question():
            raw_question = "What is the capital of France?" * 10  # Longer content
            raw_options = [f"Option {i}: " + "Content " * 20 for i in range(4)]
            
            return Question(
                question_id=1,
                question=truncate_content(raw_question, "question"),
                answer=truncate_content(raw_options[0], "answer"),
                options=[truncate_content(opt, "choice") for opt in raw_options],
                category="geography",
                difficulty="easy"
            )
        
        self.measure_memory_operation("question_creation_processed", create_processed_question, 500)
    
    def test_list_comprehensions_vs_generators(self):
        """Test memory usage differences between list comprehensions and generators."""
        
        data = list(range(1000))
        
        # List comprehension
        def list_comprehension_op():
            return [x * 2 for x in data]
        
        self.measure_memory_operation("list_comprehension", list_comprehension_op, 100)
        
        # Generator expression (consumed immediately)
        def generator_expression_op():
            return list(x * 2 for x in data)
        
        self.measure_memory_operation("generator_expression", generator_expression_op, 100)
    
    def test_string_concatenation_patterns(self):
        """Test different string concatenation approaches."""
        
        base_strings = [f"String {i}" for i in range(100)]
        
        # String concatenation with +
        def string_concat_plus():
            result = ""
            for s in base_strings:
                result += s + " "
            return result
        
        self.measure_memory_operation("string_concat_plus", string_concat_plus, 100)
        
        # String join
        def string_join():
            return " ".join(base_strings)
        
        self.measure_memory_operation("string_join", string_join, 100)
        
        # f-string formatting
        def f_string_formatting():
            return " ".join(f"{s}_formatted" for s in base_strings)
        
        self.measure_memory_operation("f_string_formatting", f_string_formatting, 100)
    
    def test_dictionary_vs_object_access(self):
        """Test memory and performance differences between dict and object attribute access."""
        
        # Dictionary access
        test_dict = {'name': 'test', 'value': 42, 'description': 'test object'}
        
        def dict_access():
            name = test_dict['name']
            value = test_dict['value']
            desc = test_dict['description']
            return name, value, desc
        
        self.measure_memory_operation("dictionary_access", dict_access, 1000)
        
        # Object attribute access
        class TestObject:
            def __init__(self):
                self.name = 'test'
                self.value = 42
                self.description = 'test object'
        
        test_obj = TestObject()
        
        def object_access():
            name = test_obj.name
            value = test_obj.value
            desc = test_obj.description
            return name, value, desc
        
        self.measure_memory_operation("object_access", object_access, 1000)
    
    def print_results(self):
        """Print memory performance test results."""
        print("\n" + "="*80)
        print("MEMORY PERFORMANCE TEST RESULTS")
        print("="*80)
        
        for operation, metrics in self.results.items():
            print(f"\n{operation.upper()}:")
            print(f"  Avg Time/Op:    {metrics['avg_time']*1000000:.2f}μs")
            print(f"  Ops/Second:     {metrics['operations_per_second']:.0f}")
            print(f"  Memory/Op:      {metrics['memory_per_operation_bytes']:.2f} bytes")
            print(f"  Peak Memory:    {metrics['peak_memory_kb']:.2f}KB")
            print(f"  Memory Delta:   {metrics['memory_delta_mb']:.2f}MB")
    
    def get_baseline_metrics(self) -> Dict[str, Any]:
        """Return baseline metrics for comparison after optimization."""
        return {
            'progress_bar_memory_per_op': self.results.get('progress_bar_current', {}).get('memory_per_operation_bytes', 0),
            'progress_bar_ops_per_sec': self.results.get('progress_bar_current', {}).get('operations_per_second', 0),
            'emoji_lookup_memory_per_op': self.results.get('progress_emoji_lookup', {}).get('memory_per_operation_bytes', 0),
            'content_truncation_memory_per_op': self.results.get('content_truncation', {}).get('memory_per_operation_bytes', 0),
            'question_creation_memory_per_op': self.results.get('question_creation_simple', {}).get('memory_per_operation_bytes', 0),
            'string_join_vs_concat_ratio': (
                self.results.get('string_join', {}).get('operations_per_second', 1) /
                self.results.get('string_concat_plus', {}).get('operations_per_second', 1)
            ),
            'total_peak_memory_kb': sum(r.get('peak_memory_kb', 0) for r in self.results.values())
        }


def run_memory_performance_tests():
    """Run all memory performance tests."""
    test_suite = MemoryPerformanceTest()
    
    try:
        print("Running memory performance tests...")
        
        # Run all memory tests
        test_suite.test_progress_bar_generation()
        test_suite.test_content_processing()
        test_suite.test_question_object_creation()
        test_suite.test_list_comprehensions_vs_generators()
        test_suite.test_string_concatenation_patterns()
        test_suite.test_dictionary_vs_object_access()
        
        # Print results
        test_suite.print_results()
        
        return test_suite.get_baseline_metrics()
        
    except Exception as e:
        print(f"Memory performance tests failed: {e}")
        return None


if __name__ == "__main__":
    # Run the tests directly
    baseline_metrics = run_memory_performance_tests()
    if baseline_metrics:
        print(f"\nBaseline metrics saved: {baseline_metrics}")