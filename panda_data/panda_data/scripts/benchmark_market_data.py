#!/usr/bin/env python
"""
Script to benchmark the performance of get_market_data function
"""
import time
import argparse
import yaml
import pandas as pd
from panda_data import init, get_market_data


def benchmark_market_data(config_path='panda_data/config.yaml',
                          start_date='20220101',
                          end_date='20221231',
                          symbols=None,
                          fields=None,
                          iterations=3):
    """Benchmark the performance of get_market_data function"""
    # Initialize panda_data
    init(config_path)

    # Define test cases
    test_cases = [
        {
            'name': 'Small date range, few symbols',
            'start_date': start_date,
            'end_date': pd.to_datetime(start_date).strftime('%Y%m%d'),  # Same day
            'symbols': symbols[:5] if symbols and len(symbols) > 5 else symbols,
            'fields': fields
        },
        {
            'name': 'Medium date range, few symbols',
            'start_date': start_date,
            'end_date': pd.to_datetime(start_date).replace(month=pd.to_datetime(start_date).month + 1).strftime(
                '%Y%m%d'),
            'symbols': symbols[:5] if symbols and len(symbols) > 5 else symbols,
            'fields': fields
        },
        {
            'name': 'Large date range, few symbols',
            'start_date': start_date,
            'end_date': end_date,
            'symbols': symbols[:5] if symbols and len(symbols) > 5 else symbols,
            'fields': fields
        },
        {
            'name': 'Small date range, all symbols',
            'start_date': start_date,
            'end_date': pd.to_datetime(start_date).strftime('%Y%m%d'),  # Same day
            'symbols': None,
            'fields': fields
        }
    ]

    # Run benchmarks
    results = []

    for test_case in test_cases:
        print(f"\nRunning benchmark: {test_case['name']}")
        print(f"Parameters: start_date={test_case['start_date']}, end_date={test_case['end_date']}, "
              f"symbols={test_case['symbols']}, fields={test_case['fields']}")

        # Run multiple iterations and calculate average
        times = []
        data_size = 0

        for i in range(iterations):
            print(f"  Iteration {i + 1}/{iterations}...")

            # Clear cache between iterations (first iteration)
            if i == 0:
                # Force a new query by adding a dummy parameter
                _ = get_market_data(
                    start_date=test_case['start_date'],
                    end_date=test_case['end_date'],
                    symbols=test_case['symbols'],
                    fields=['_dummy_field_to_clear_cache'] if test_case['fields'] else None
                )

            # Measure time
            start_time = time.time()
            data = get_market_data(
                start_date=test_case['start_date'],
                end_date=test_case['end_date'],
                symbols=test_case['symbols'],
                fields=test_case['fields']
            )
            end_time = time.time()

            elapsed = end_time - start_time
            times.append(elapsed)

            if data is not None and i == 0:
                data_size = len(data)
                print(f"  Retrieved {data_size} records")

            print(f"  Time: {elapsed:.4f} seconds")

        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        # Store results
        results.append({
            'test_case': test_case['name'],
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time,
            'data_size': data_size
        })

        print(f"  Average time: {avg_time:.4f} seconds")
        print(f"  Min time: {min_time:.4f} seconds")
        print(f"  Max time: {max_time:.4f} seconds")

    # Print summary
    print("\n=== BENCHMARK SUMMARY ===")
    for result in results:
        print(f"{result['test_case']}:")
        print(f"  Data size: {result['data_size']} records")
        print(f"  Average time: {result['avg_time']:.4f} seconds")
        print(f"  Min time: {result['min_time']:.4f} seconds")
        print(f"  Max time: {result['max_time']:.4f} seconds")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Benchmark get_market_data performance')
    parser.add_argument('--config', type=str, default='panda_data/config.yaml',
                        help='Path to config file')
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

    benchmark_market_data(
        config_path=args.config,
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=args.symbols,
        fields=args.fields,
        iterations=args.iterations
    )