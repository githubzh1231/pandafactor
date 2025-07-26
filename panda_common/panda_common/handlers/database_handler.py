import pymongo
import urllib.parse
import os
import logging
from typing import Optional, Dict, List
# 设置日志
logger = logging.getLogger(__name__)
class DatabaseHandler:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DatabaseHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self, config):
        if not hasattr(self, 'initialized'):  # Prevent re-initialization

            # URL encode the password to avoid authentication issues with special characters
            encoded_password = urllib.parse.quote_plus(config["MONGO_PASSWORD"])

            # Build connection string
            MONGO_URI = f'mongodb://{config["MONGO_USER"]}:{encoded_password}@{config["MONGO_URI"]}/{config["MONGO_AUTH_DB"]}'
            if (config['MONGO_TYPE']=='single'):
                self.mongo_client = pymongo.MongoClient(
                    MONGO_URI,
                    readPreference='secondaryPreferred',  # Prefer reading from secondary nodes
                    w='majority',  # Write concern level
                    retryWrites=True,  # Automatically retry write operations
                    socketTimeoutMS=30000,  # Socket timeout
                    connectTimeoutMS=20000,  # Connection timeout
                    serverSelectionTimeoutMS=30000,  # Server selection timeout
                    authSource=config["MONGO_AUTH_DB"],  # Explicitly specify authentication database
                )
            elif (config['MONGO_TYPE']=='replica_set'):
                MONGO_URI += f'?replicaSet={config["MONGO_REPLICA_SET"]}'
                self.mongo_client = pymongo.MongoClient(
                    MONGO_URI,
                    readPreference='secondaryPreferred',  # Prefer reading from secondary nodes
                    w='majority',  # Write concern level
                    retryWrites=True,  # Automatically retry write operations
                    socketTimeoutMS=30000,  # Socket timeout
                    connectTimeoutMS=20000,  # Connection timeout
                    serverSelectionTimeoutMS=30000,  # Server selection timeout
                    authSource=config["MONGO_AUTH_DB"],  # Explicitly specify authentication database
                )

            # Print connection string with masked password
            masked_uri = MONGO_URI
            masked_uri = masked_uri.replace(urllib.parse.quote_plus(config["MONGO_PASSWORD"]), "****")
            # Test if connection is successful
            try:
                # Send ping command to database
                self.mongo_client.admin.command('ping')
                print(f"Connecting to MongoDB: {masked_uri}")
            except Exception as e:
                print(f"MongoDB connection failed: {e}")
                raise
            
            # Enable when needed
            # self.mysql_conn = mysql.connector.connect(
            #     host=config.MYSQL_HOST,
            #     user=config.MYSQL_USER,
            #     password=config.MYSQL_PASSWORD,
            #     database=config.MYSQL_DATABASE
            # )
            # self.redis_client = redis.StrictRedis(
            #     host=config.REDIS_HOST,
            #     port=config.REDIS_PORT,
            #     password=config.REDIS_PASSWORD,
            #     decode_responses=True
            # )
            self.initialized = True

    def mongo_insert(self, db_name, collection_name, document):
        collection = self.get_mongo_collection(db_name, collection_name)
        return collection.insert_one(document).inserted_id

    def mongo_find(self, db_name, collection_name, query, projection=None, hint=None, sort=None):
        """
        Find documents in MongoDB collection

        Args:
            db_name: Database name
            collection_name: Collection name
            query: Query dictionary
            projection: Fields to return (dict)
            hint: Optional index hint
            sort: Optional sort specification

        Returns:
            List of documents
        """
        collection = self.get_mongo_collection(db_name, collection_name)
        cursor = collection.find(query, projection)
        if hint:
            cursor = cursor.hint(hint)
        if sort:
            cursor = cursor.sort(sort)
        return list(cursor)

    def mongo_update(self, db_name, collection_name, query, update):
        collection = self.get_mongo_collection(db_name, collection_name)
        return collection.update_many(query, {'$set': update}).modified_count


    def mongo_delete(self, db_name, collection_name, query):
        collection = self.get_mongo_collection(db_name, collection_name)
        return collection.delete_many(query).deleted_count

    def get_mongo_collection(self, db_name, collection_name):
        return self.mongo_client[db_name][collection_name]

    # def mysql_query(self, query, params=None):
    #     cursor = self.mysql_conn.cursor()
    #     cursor.execute(query, params)
    #     return cursor.fetchall()

    # def redis_set(self, key, value):
    #     self.redis_client.set(key, value)

    # def redis_get(self, key):
    #     return self.redis_client.get(key)

    # def mysql_insert(self, table, data):
    #     cursor = self.mysql_conn.cursor()
    #     placeholders = ', '.join(['%s'] * len(data))
    #     columns = ', '.join(data.keys())
    #     sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    #     cursor.execute(sql, list(data.values()))
    #     self.mysql_conn.commit()
    #     return cursor.lastrowid

    # def mysql_update(self, table, data, condition):
    #     cursor = self.mysql_conn.cursor()
    #     set_clause = ', '.join([f"{key} = %s" for key in data.keys()])
    #     sql = f"UPDATE {table} SET {set_clause} WHERE {condition}"
    #     cursor.execute(sql, list(data.values()))
    #     self.mysql_conn.commit()
    #     return cursor.rowcount

    # def mysql_delete(self, table, condition):
    #     cursor = self.mysql_conn.cursor()
    #     sql = f"DELETE FROM {table} WHERE {condition}"
    #     cursor.execute(sql)
    #     self.mysql_conn.commit()
    #     return cursor.rowcount

    def mongo_insert_many(self, db_name, collection_name, documents):
        collection = self.get_mongo_collection(db_name, collection_name)
        return collection.insert_many(documents).inserted_ids

    def mongo_aggregate(self, db_name, collection_name, aggregation_pipeline):
        collection = self.get_mongo_collection(db_name, collection_name)
        return list(collection.aggregate(aggregation_pipeline)) 
    
    def get_distinct_values(self, db_name, collection_name, field):
        """Get distinct values for a field"""
        collection = self.get_mongo_collection(db_name, collection_name)
        return collection.distinct(field)

    def mongo_find_one(self, db_name, collection_name, query, hint=None):
        """
        Find a single document in MongoDB collection
        
        Args:
            db_name: Database name
            collection_name: Collection name
            query: Query dictionary
            hint: Optional index hint
            
        Returns:
            Single document or None if not found
        """
        collection = self.get_mongo_collection(db_name, collection_name)
        if hint:
            return collection.find_one(query, hint=hint)
        return collection.find_one(query)

    def find_documents(self,
                       db_name: str,
                       collection_name: str,
                       filter_dict: Optional[Dict] = None,
                       projection: Optional[Dict] = None,
                       limit: Optional[int] = None,
                       sort: Optional[List] = None) -> List[Dict]:
        """
        查询文档

        Args:
            db_name: 数据库名称
            collection_name: 集合名称
            filter_dict: 查询条件
            projection: 字段投影
            limit: 限制返回数量
            sort: 排序条件

        Returns:
            List[Dict]: 查询结果
        """
        try:
            collection = self.get_mongo_collection(db_name, collection_name)

            cursor = collection.find(
                filter_dict or {},
                projection
            )

            if sort:
                cursor = cursor.sort(sort)

            if limit:
                cursor = cursor.limit(limit)

            results = list(cursor)
            logger.info(f"从集合 {collection_name} 查询到 {len(results)} 条记录")
            return results

        except Exception as e:
            logger.error(f"查询集合 {collection_name} 失败: {e}")
            return []