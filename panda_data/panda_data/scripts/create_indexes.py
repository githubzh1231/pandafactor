#!/usr/bin/env python
"""
Script to create necessary indexes for the panda_data database
"""
import yaml
import argparse
from pymongo import MongoClient, ASCENDING, DESCENDING


def create_indexes(config_path='panda_data/config.yaml'):
    """Create indexes for MongoDB collections"""
    # Load configuration
    with open(config_path, 'r') as config_file:
        config = yaml.safe_load(config_file)

    # Connect to MongoDB
    mongo_uri = f'mongodb://{config["MONGO_USER"]}:{config["MONGO_PASSWORD"]}@{config["MONGO_URI"]}/{config["MONGO_AUTH_DB"]}'
    client = MongoClient(mongo_uri)

    # Get database
    db = client[config["MONGO_DB"]]

    # Create indexes for stock_market collection
    stock_market = db["stock_market"]

    # Create compound index on symbol and date (most common query pattern)
    print("Creating compound index on (symbol, date)...")
    stock_market.create_index([("symbol", ASCENDING), ("date", ASCENDING)])

    # Create index on date field (for date range queries)
    print("Creating index on date field...")
    stock_market.create_index([("date", ASCENDING)])

    # Create index on symbol field (for symbol-only queries)
    print("Creating index on symbol field...")
    stock_market.create_index([("symbol", ASCENDING)])

    # List all indexes
    print("\nCurrent indexes:")
    for index in stock_market.list_indexes():
        print(f"  - {index['name']}: {index['key']}")

    print("\nIndexes created successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create MongoDB indexes for panda_data')
    parser.add_argument('--config', type=str, default='panda_data/config.yaml',
                        help='Path to config file')
    args = parser.parse_args()

    create_indexes(args.config)