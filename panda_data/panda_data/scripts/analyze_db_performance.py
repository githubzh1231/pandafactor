#!/usr/bin/env python
"""
Script to analyze MongoDB query performance for market data
"""
import yaml
import argparse
import time
import pandas as pd
from pymongo import MongoClient
from tabulate import tabulate
from panda_data import init


def analyze_db_performance(config_path='panda_data/config.yaml',
                           start_date='20220101',
                           end_date='20221231',
                           symbols=None,
                           verbose=False):
    """Analyze MongoDB query performance for market data"""
    # Load configuration
    with open(config_path, 'r') as config_file:
        config = yaml.safe_load(config_file)

    # Connect to MongoDB
    mongo_uri = f'mongodb://{config["MONGO_USER"]}:{config["MONGO_PASSWORD"]}@{config["MONGO_URI"]}/{config["MONGO_AUTH_DB"]}'
    client = MongoClient(mongo_uri)

    # Get database and collection
    db = client[config["MONGO_DB"]]
    collection = db["stock_market"]

    # Get all symbols if not provided
    if symbols is None or len(symbols) == 0:
        symbols = collection.distinct("symbol")
        if len(symbols) > 10:
            symbols = symbols[:10]  # Limit to 10 symbols for testing

    # Convert to list if string
    if isinstance(symbols, str):
        symbols = [symbols]

    print(f"Analyzing query performance for {len(symbols)} symbols from {start_date} to {end_date}")

    # Define test queries
    test_queries = [
        {
            'name': 'Single symbol, small date range',
            'query': {
                'symbol': symbols[0],
                'date': {'$gte': start_date, '$lte': start_date}
            }
        },
        {
            'name': 'Single symbol, full date range',
            'query': {
                'symbol': symbols[0],
                'date': {'$gte': start_date, '$lte': end_date}
            }
        },
        {
            'name': 'Multiple symbols, small date range',
            'query': {
                'symbol': {'$in': symbols},
                'date': {'$gte': start_date, '$lte': start_date}
            }
        },
        {
            'name': 'Multiple symbols, full date range',
            'query': {
                'symbol': {'$in': symbols},
                'date': {'$gte': start_date, '$lte': end_date}
            }
        }
    ]

    # Run tests
    results = []

    for test in test_queries:
        print(f"\nRunning test: {test['name']}")

        # Count documents
        count_start = time.time()
        doc_count = collection.count_documents(test['query'])
        count_time = time.time() - count_start

        print(f"Document count: {doc_count}")
        print(f"Count time: {count_time:.4f} seconds")

        # Get explain plan
        explain_start = time.time()
        explain_plan = collection.find(test['query']).explain()
        explain_time = time.time() - explain_start

        # Extract key information from explain plan
        index_used = "No index used"
        execution_time_ms = None
        docs_examined = None

        if 'queryPlanner' in explain_plan:
            winning_plan = explain_plan['queryPlanner'].get('winningPlan', {})
            if 'inputStage' in winning_plan:
                input_stage = winning_plan['inputStage']
                if 'indexName' in input_stage:
                    index_used = input_stage['indexName']

        if 'executionStats' in explain_plan:
            execution_stats = explain_plan['executionStats']
            execution_time_ms = execution_stats.get('executionTimeMillis')
            docs_examined = execution_stats.get('totalDocsExamined')

        print(f"Index used: {index_used}")
        if execution_time_ms:
            print(f"Execution time: {execution_time_ms} ms")
        if docs_examined:
            print(f"Documents examined: {docs_examined}")

        # Run actual query
        query_start = time.time()
        cursor = collection.find(test['query'])
        data = list(cursor)
        query_time = time.time() - query_start

        print(f"Query time: {query_time:.4f} seconds")
        print(f"Retrieved {len(data)} documents")

        # Store results
        results.append({
            'test_name': test['name'],
            'doc_count': doc_count,
            'count_time': count_time,
            'index_used': index_used,
            'execution_time_ms': execution_time_ms,
            'docs_examined': docs_examined,
            'query_time': query_time,
            'docs_retrieved': len(data)
        })

        # Print explain plan if verbose
        if verbose:
            print("\nExplain Plan:")
            print(explain_plan)

    # Print summary table
    print("\n=== PERFORMANCE SUMMARY ===")

    summary_data = []
    for result in results:
        summary_data.append([
            result['test_name'],
            result['doc_count'],
            f"{result['count_time']:.4f}s",
            result['index_used'],
            f"{result['execution_time_ms']}ms" if result['execution_time_ms'] else "N/A",
            result['docs_examined'],
            f"{result['query_time']:.4f}s",
            result['docs_retrieved']
        ])

    headers = [
        "Test", "Doc Count", "Count Time", "Index Used",
        "Execution Time", "Docs Examined", "Query Time", "Docs Retrieved"
    ]

    print(tabulate(summary_data, headers=headers, tablefmt="grid"))

    # Check for collection stats
    print("\n=== COLLECTION STATISTICS ===")
    stats = db.command("collStats", "stock_market")

    print(f"Collection size: {stats['size'] / (1024 * 1024):.2f} MB")
    print(f"Storage size: {stats['storageSize'] / (1024 * 1024):.2f} MB")
    print(f"Total index size: {stats['totalIndexSize'] / (1024 * 1024):.2f} MB")
    print(f"Average document size: {stats['avgObjSize']} bytes")
    print(f"Document count: {stats['count']}")

    # Print index information
    print("\n=== INDEX INFORMATION ===")
    indexes = list(collection.list_indexes())

    index_data = []
    for idx in indexes:
        index_data.append([
            idx['name'],
            str(idx['key']),
            idx.get('size', 'N/A'),
            "Yes" if idx.get('unique', False) else "No"
        ])

    index_headers = ["Name", "Key", "Size", "Unique"]
    print(tabulate(index_data, headers=index_headers, tablefmt="grid"))

    # Recommendations
    print("\n=== RECOMMENDATIONS ===")

    # Check if compound index is being used
    compound_index_used = any(result['index_used'] == 'symbol_1_date_1' for result in results)
    if not compound_index_used:
        print("- The compound index (symbol, date) is not being used effectively.")
        print("  Consider rebuilding this index or checking query patterns.")

    # Check for slow queries
    slow_queries = [result for result in results if result['query_time'] > 1.0]
    if slow_queries:
        print("- The following queries are slow (>1s):")
        for query in slow_queries:
            print(f"  * {query['test_name']}: {query['query_time']:.4f}s")

    # Check for collection size issues
    if stats['size'] > 1024 * 1024 * 1000:  # 1 GB
        print("- The collection is large (>1GB). Consider:")
        print("  * Implementing data partitioning (e.g., by date ranges)")
        print("  * Adding more specific indexes for common query patterns")
        print("  * Using MongoDB sharding for horizontal scaling")

    # Check for index size issues
    if stats['totalIndexSize'] > stats['size'] * 0.5:
        print("- Index size is more than 50% of data size. Consider:")
        print("  * Removing unused indexes")
        print("  * Using more selective indexes")

    print("\nAnalysis complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze MongoDB query performance')
    parser.add_argument('--config', type=str, default='panda_data/config.yaml',
                        help='Path to config file')
    parser.add_argument('--start-date', type=str, default='20220101',
                        help='Start date in YYYYMMDD format')
    parser.add_argument('--end-date', type=str, default='20221231',
                        help='End date in YYYYMMDD format')
    parser.add_argument('--symbols', type=str, nargs='+',
                        help='List of symbols to query')
    parser.add_argument('--verbose', action='store_true',
                        help='Print detailed explain plans')

    args = parser.parse_args()

    analyze_db_performance(
        config_path=args.config,
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=args.symbols,
        verbose=args.verbose
    )