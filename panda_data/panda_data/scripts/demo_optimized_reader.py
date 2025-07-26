#!/usr/bin/env python
"""
Demo script to show how to use the optimized market data reader
and compare performance with the original reader
"""
import argparse
import time
import pandas as pd
import panda_data
from tabulate import tabulate


def run_performance_test(
        start_date='20220101',
        end_date='20221231',
        symbols=None,
        fields=None,
        iterations=3
):
    """Run performance tests comparing original and optimized readers"""
    print("=== MARKET DATA READER PERFORMANCE COMPARISON ===\n")

    # Define test cases
    test_cases = [
        {
            'name': 'Small date range (1 day)',
            'start_date': start_date,
            'end_date': start_date,  # Same day
            'symbols': symbols,
            'fields': fields
        },
        {
            'name': 'Medium date range (1 month)',
            'start_date': start_date,
            'end_date': pd.to_datetime(start_date).replace(month=pd.to_datetime(start_date).month + 1).strftime(
                '%Y%m%d'),
            'symbols': symbols,
            'fields': fields
        },
        {
            'name': 'Large date range (full period)',
            'start_date': start_date,
            'end_date': end_date,
            'symbols': symbols,
            'fields': fields
        }
    ]

    results = []

    # Initialize with standard reader first
    print("Initializing with standard reader...")
    panda_data.init(use_partitioned=False)

    # Run tests with standard reader
    for test_case in test_cases:
        print(f"\nRunning test: {test_case['name']} with standard reader")
        standard_times = []
        data_size = 0

        for i in range(iterations):
            print(f"  Iteration {i + 1}/{iterations}...")

            # Clear cache between iterations (first iteration)
            if i == 0:
                try:
                    panda_data.clear_market_data_cache()
                except:
                    pass

            # Measure time
            start_time = time.time()
            data = panda_data.get_market_data(
                start_date=test_case['start_date'],
                end_date=test_case['end_date'],
                symbols=test_case['symbols'],
                fields=test_case['fields']
            )
            end_time = time.time()

            elapsed = end_time - start_time
            standard_times.append(elapsed)

            if data is not None and i == 0:
                data_size = len(data)
                print(f"  Retrieved {data_size} records")

            print(f"  Time: {elapsed:.4f} seconds")

        # Calculate statistics
        avg_standard_time = sum(standard_times) / len(standard_times)

        # Store partial results
        result = {
            'test_case': test_case['name'],
            'data_size': data_size,
            'standard_avg_time': avg_standard_time,
            'standard_min_time': min(standard_times),
            'standard_max_time': max(standard_times)
        }

        results.append(result)

    # Switch to partitioned reader
    print("\nSwitching to partitioned reader...")
    panda_data.switch_to_partitioned_reader()

    # Run tests with partitioned reader
    for i, test_case in enumerate(test_cases):
        print(f"\nRunning test: {test_case['name']} with partitioned reader")
        partitioned_times = []

        for j in range(iterations):
            print(f"  Iteration {j + 1}/{iterations}...")

            # Clear cache between iterations (first iteration)
            if j == 0:
                try:
                    panda_data.clear_market_data_cache()
                except:
                    pass

            # Measure time
            start_time = time.time()
            data = panda_data.get_market_data(
                start_date=test_case['start_date'],
                end_date=test_case['end_date'],
                symbols=test_case['symbols'],
                fields=test_case['fields']
            )
            end_time = time.time()

            elapsed = end_time - start_time
            partitioned_times.append(elapsed)

            print(f"  Time: {elapsed:.4f} seconds")

        # Calculate statistics
        avg_partitioned_time = sum(partitioned_times) / len(partitioned_times)

        # Update results
        results[i]['partitioned_avg_time'] = avg_partitioned_time
        results[i]['partitioned_min_time'] = min(partitioned_times)
        results[i]['partitioned_max_time'] = max(partitioned_times)

        # Calculate improvement
        improvement = (results[i]['standard_avg_time'] - avg_partitioned_time) / results[i]['standard_avg_time'] * 100
        results[i]['improvement'] = improvement

    # Print summary
    print("\n=== PERFORMANCE SUMMARY ===")

    summary_data = []
    for result in results:
        summary_data.append([
            result['test_case'],
            result['data_size'],
            f"{result['standard_avg_time']:.4f}s",
            f"{result['partitioned_avg_time']:.4f}s",
            f"{result['improvement']:.2f}%"
        ])

    headers = [
        "Test Case", "Records", "Standard Reader", "Partitioned Reader", "Improvement"
    ]

    print(tabulate(summary_data, headers=headers, tablefmt="grid"))

    # Print detailed results
    print("\n=== DETAILED RESULTS ===")

    detailed_data = []
    for result in results:
        detailed_data.append([
            result['test_case'],
            result['data_size'],
            f"{result['standard_avg_time']:.4f}s",
            f"{result['standard_min_time']:.4f}s",
            f"{result['standard_max_time']:.4f}s",
            f"{result['partitioned_avg_time']:.4f}s",
            f"{result['partitioned_min_time']:.4f}s",
            f"{result['partitioned_max_time']:.4f}s",
            f"{result['improvement']:.2f}%"
        ])

    detailed_headers = [
        "Test Case", "Records",
        "Std Avg", "Std Min", "Std Max",
        "Part Avg", "Part Min", "Part Max",
        "Improvement"
    ]

    print(tabulate(detailed_data, headers=detailed_headers, tablefmt="grid"))

    # Print recommendations
    print("\n=== RECOMMENDATIONS ===")

    avg_improvement = sum(result['improvement'] for result in results) / len(results)

    if avg_improvement > 20:
        print("✅ The partitioned reader shows significant performance improvements.")
        print("   Recommendation: Use the partitioned reader for all queries.")
        print("\n   To use the partitioned reader in your code:")
        print("   ```python")
        print("   import panda_data")
        print("   panda_data.init(use_partitioned=True)")
        print("   # or")
        print("   panda_data.init()")
        print("   panda_data.switch_to_partitioned_reader()")
        print("   ```")
    elif avg_improvement > 5:
        print("✅ The partitioned reader shows moderate performance improvements.")
        print("   Recommendation: Use the partitioned reader for large queries.")
        print("   For small queries, the standard reader may be sufficient.")
    else:
        print("ℹ️ The partitioned reader shows minimal performance improvements.")
        print("   Recommendation: Consider further optimizing the database:")
        print("   1. Run the optimize_mongodb.py script to rebuild indexes")
        print("   2. Create date-partitioned collections for better performance")
        print("   3. Check MongoDB server configuration and resources")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Demo optimized market data reader')
    parser.add_argument('--start-date', type=str, default='20220101',
                        help='Start date in YYYYMMDD format')
    parser.add_argument('--end-date', type=str, default='20221231',
                        help='End date in YYYYMMDD format')
    parser.add_argument('--symbols', type=str, nargs='+',
                        help='List of symbols to query')
    parser.add_argument('--fields', type=str, nargs='+',
                        help='List of fields to retrieve')
    parser.add_argument('--iterations', type=int, default=3,
                        help='Number of iterations for each test case')

    args = parser.parse_args()

    run_performance_test(
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=args.symbols,
        fields=args.fields,
        iterations=args.iterations
    )