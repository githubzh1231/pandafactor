#!/usr/bin/env python
"""
Script to optimize MongoDB for market data queries
"""
import yaml
import argparse
import time
import os
from pymongo import MongoClient, ASCENDING, DESCENDING, IndexModel
from pymongo.errors import OperationFailure
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger


def load_config(config_path=None):
    """Load configuration from yaml file"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'panda_common',
                                   'config.yaml')

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def optimize_mongodb(config_path=None,
                     rebuild_indexes=False,
                     create_date_partitions=False,
                     start_year=2020,
                     end_year=2023):
    """Optimize MongoDB for market data queries"""
    print("Starting MongoDB optimization...")

    # Load configuration
    config = load_config(config_path)

    # Initialize DatabaseHandler with config
    db_handler = DatabaseHandler(config)

    # Get database and collection
    db = db_handler.mongo_client[config["MONGO_DB"]]
    collection = db["stock_market"]

    # Get collection stats before optimization
    print("\n=== COLLECTION STATISTICS BEFORE OPTIMIZATION ===")
    stats_before = db.command("collStats", "stock_market")

    print(f"Collection size: {stats_before['size'] / (1024 * 1024):.2f} MB")
    print(f"Storage size: {stats_before['storageSize'] / (1024 * 1024):.2f} MB")
    print(f"Total index size: {stats_before['totalIndexSize'] / (1024 * 1024):.2f} MB")
    print(f"Document count: {stats_before['count']}")

    # Print existing indexes
    print("\n=== EXISTING INDEXES ===")
    existing_indexes = list(collection.list_indexes())
    for idx in existing_indexes:
        print(f"- {idx['name']}: {idx['key']}")

    # Optimize indexes
    if rebuild_indexes:
        print("\n=== REBUILDING INDEXES ===")

        # Drop all non-_id indexes
        print("Dropping existing indexes...")
        for idx in existing_indexes:
            if idx['name'] != '_id_':
                try:
                    collection.drop_index(idx['name'])
                    print(f"Dropped index: {idx['name']}")
                except OperationFailure as e:
                    print(f"Failed to drop index {idx['name']}: {str(e)}")

        # Create optimized indexes
        print("Creating optimized indexes...")

        # Create compound index for symbol and date (most common query pattern)
        print("Creating compound index on (symbol, date)...")
        collection.create_index([("symbol", ASCENDING), ("date", ASCENDING)],
                                name="symbol_date_idx",
                                background=True)

        # Create index on date field (for date range queries)
        print("Creating index on date field...")
        collection.create_index([("date", ASCENDING)],
                                name="date_idx",
                                background=True)

        # Create index on symbol field (for symbol-only queries)
        print("Creating index on symbol field...")
        collection.create_index([("symbol", ASCENDING)],
                                name="symbol_idx",
                                background=True)

        # Create partial indexes for frequently queried date ranges
        print("Creating partial indexes for recent data...")

        # Get current year
        import datetime
        current_year = datetime.datetime.now().year

        # Create partial index for current year data
        current_year_start = f"{current_year}0101"
        collection.create_index(
            [("symbol", ASCENDING), ("date", ASCENDING)],
            name=f"symbol_date_{current_year}_idx",
            partialFilterExpression={"date": {"$gte": current_year_start}},
            background=True
        )

        # Create partial index for previous year data
        prev_year = current_year - 1
        prev_year_start = f"{prev_year}0101"
        prev_year_end = f"{prev_year}1231"
        collection.create_index(
            [("symbol", ASCENDING), ("date", ASCENDING)],
            name=f"symbol_date_{prev_year}_idx",
            partialFilterExpression={
                "date": {"$gte": prev_year_start, "$lte": prev_year_end}
            },
            background=True
        )

    # Create date-partitioned collections if requested
    if create_date_partitions:
        print("\n=== CREATING DATE-PARTITIONED COLLECTIONS ===")

        # Create collections for each year
        for year in range(start_year, end_year + 1):
            year_start = f"{year}0101"
            year_end = f"{year}1231"

            # Collection name for this year
            year_collection_name = f"stock_market_{year}"

            # Check if collection already exists
            if year_collection_name in db.list_collection_names():
                print(f"Collection {year_collection_name} already exists, skipping...")
                continue

            print(f"Creating collection for year {year}...")

            # Create the collection
            db.create_collection(year_collection_name)
            year_collection = db[year_collection_name]

            # Create indexes on the new collection
            year_collection.create_index([("symbol", ASCENDING), ("date", ASCENDING)])
            year_collection.create_index([("date", ASCENDING)])
            year_collection.create_index([("symbol", ASCENDING)])

            # Copy data for this year to the new collection
            print(f"Copying data for year {year}...")

            # Find documents for this year
            cursor = collection.find({
                "date": {"$gte": year_start, "$lte": year_end}
            })

            # Process in batches
            batch_size = 10000
            batch = []
            count = 0

            for doc in cursor:
                batch.append(doc)
                count += 1

                if len(batch) >= batch_size:
                    if batch:
                        year_collection.insert_many(batch)
                    batch = []
                    print(f"Copied {count} documents...")

            # Insert remaining documents
            if batch:
                year_collection.insert_many(batch)

            print(f"Copied {count} documents to {year_collection_name}")

    # Run compact on the collection to reclaim space
    print("\n=== COMPACTING COLLECTION ===")
    try:
        db.command("compact", "stock_market")
        print("Collection compacted successfully")
    except Exception as e:
        print(f"Failed to compact collection: {str(e)}")

    # Get collection stats after optimization
    print("\n=== COLLECTION STATISTICS AFTER OPTIMIZATION ===")
    stats_after = db.command("collStats", "stock_market")

    print(f"Collection size: {stats_after['size'] / (1024 * 1024):.2f} MB")
    print(f"Storage size: {stats_after['storageSize'] / (1024 * 1024):.2f} MB")
    print(f"Total index size: {stats_after['totalIndexSize'] / (1024 * 1024):.2f} MB")
    print(f"Document count: {stats_after['count']}")

    # Print new indexes
    print("\n=== NEW INDEXES ===")
    new_indexes = list(collection.list_indexes())
    for idx in new_indexes:
        print(f"- {idx['name']}: {idx['key']}")

    # Print optimization summary
    print("\n=== OPTIMIZATION SUMMARY ===")

    size_diff = stats_before['size'] - stats_after['size']
    size_diff_mb = size_diff / (1024 * 1024)
    size_diff_percent = (size_diff / stats_before['size']) * 100 if stats_before['size'] > 0 else 0

    index_size_diff = stats_before['totalIndexSize'] - stats_after['totalIndexSize']
    index_size_diff_mb = index_size_diff / (1024 * 1024)
    index_size_diff_percent = (index_size_diff / stats_before['totalIndexSize']) * 100 if stats_before[
                                                                                              'totalIndexSize'] > 0 else 0

    print(f"Collection size change: {size_diff_mb:.2f} MB ({size_diff_percent:.2f}%)")
    print(f"Index size change: {index_size_diff_mb:.2f} MB ({index_size_diff_percent:.2f}%)")

    if create_date_partitions:
        print("\nCreated date-partitioned collections:")
        for year in range(start_year, end_year + 1):
            year_collection_name = f"stock_market_{year}"
            if year_collection_name in db.list_collection_names():
                year_stats = db.command("collStats", year_collection_name)
                print(f"- {year_collection_name}: {year_stats['count']} documents, "
                      f"{year_stats['size'] / (1024 * 1024):.2f} MB")

    print("\nOptimization complete!")


def optimize_factor_collections(config):
    """Optimize MongoDB indexes for factor collections"""
    db_handler = DatabaseHandler(config)
    db = db_handler.mongo_client[config["MONGO_DB"]]

    # Get all factor collections
    collections = [name for name in db.list_collection_names() if name.startswith('factor_')]

    print(f"\nOptimizing {len(collections)} factor collections...")

    for collection_name in collections:
        print(f"\nOptimizing collection: {collection_name}")
        collection = db[collection_name]

        # Get existing indexes
        existing_indexes = list(collection.list_indexes())
        print("Existing indexes:")
        for idx in existing_indexes:
            print(f"- {idx['name']}: {idx['key']}")

        # Drop existing indexes except _id
        print("\nDropping existing indexes...")
        for idx in existing_indexes:
            if idx['name'] != '_id_':
                try:
                    collection.drop_index(idx['name'])
                    print(f"Dropped index: {idx['name']}")
                except Exception as e:
                    print(f"Failed to drop index {idx['name']}: {str(e)}")

        # Create compound index on date and symbol
        print("\nCreating compound index on (date, symbol)...")
        try:
            collection.create_index([("date", ASCENDING), ("symbol", ASCENDING)],
                                    name="date_symbol_idx",
                                    background=True)
            print("Created compound index successfully")
        except Exception as e:
            print(f"Failed to create compound index: {str(e)}")

        # Create index on date field
        print("\nCreating index on date field...")
        try:
            collection.create_index([("date", ASCENDING)],
                                    name="date_idx",
                                    background=True)
            print("Created date index successfully")
        except Exception as e:
            print(f"Failed to create date index: {str(e)}")

        # Create index on symbol field
        print("\nCreating index on symbol field...")
        try:
            collection.create_index([("symbol", ASCENDING)],
                                    name="symbol_idx",
                                    background=True)
            print("Created symbol index successfully")
        except Exception as e:
            print(f"Failed to create symbol index: {str(e)}")

        # Print collection stats
        try:
            stats = db.command("collStats", collection_name)
            print(f"\nCollection statistics:")
            print(f"Collection size: {stats['size'] / (1024 * 1024):.2f} MB")
            print(f"Total index size: {stats['totalIndexSize'] / (1024 * 1024):.2f} MB")
            print(f"Document count: {stats['count']}")
        except Exception as e:
            print(f"Failed to get collection statistics: {str(e)}")

        # Print new indexes
        print("\nNew indexes:")
        new_indexes = list(collection.list_indexes())
        for idx in new_indexes:
            print(f"- {idx['name']}: {idx['key']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Optimize MongoDB for market data queries')
    parser.add_argument('--config', type=str, help='Path to config file')
    parser.add_argument('--rebuild-indexes', action='store_true', help='Rebuild indexes')
    parser.add_argument('--create-partitions', action='store_true', help='Create date-partitioned collections')
    parser.add_argument('--start-year', type=int, default=2020, help='Start year for partitioning')
    parser.add_argument('--end-year', type=int, default=2023, help='End year for partitioning')
    args = parser.parse_args()

    config = load_config(args.config)

    # Optimize stock market collection
    optimize_mongodb(
        config_path=args.config,
        rebuild_indexes=args.rebuild_indexes,
        create_date_partitions=args.create_partitions,
        start_year=args.start_year,
        end_year=args.end_year
    )

    # Optimize factor collections
    optimize_factor_collections(config)