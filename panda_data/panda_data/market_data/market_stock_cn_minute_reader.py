import pandas as pd
import time
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
import concurrent.futures
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

"""
分钟亿级数据查询接口：
"mongodb://admin:1q2w3e4R%40@192.168.31.247:27017/?authSource=admin"
2025的数据查询 panda.stock_market_ticket_zstd 大概有 3 亿条数据
2025年之后的数据查询 panda.stock_market_ticket_by_golang 大概有 10亿条数据

{
  "_id": {
    "$oid": "6823049ff422760de9a7337c"
  },
  "datetime": {
    "$date": "2017-01-03T09:31:00.000Z"
  },
  "high": 9.11,
  "close": 9.1,
  "total_turnover": 8581815,
  "low": 9.1,
  "num_trades": 241,
  "open": 9.11,
  "volume": 942360,
  "date": "201701030931",
  "symbol": "000001.SZ"
}
2025年之后的数据查询 panda.stock_market_ticket_by_golang 大概有 10亿条数据
{
  "_id": {
    "$oid": "68248741f5518c413839ee64"
  },
  "open": 5.61,
  "high": 5.61,
  "close": 5.61,
  "volume": 51350,
  "symbol": "000488.SZ",
  "date": "201901021752",
  "low": 5.6,
  "total_turnover": 288046,
  "num_trades": 0,
  "datetime": {
    "$date": "2019-01-02T09:52:00.000Z"
  }
}
这两张表理论上 基于 datetime+symbol是唯一键，但在数据同步时存在重启现象，导致部分异常
date是字符串，无法做范围查询，范围查询只能依赖生成 date范围序列按天生成任务并发查询然后合并任务生成 dataframe
"""
import pandas as pd
import time
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
import concurrent.futures
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any


class MarketStockCnMinReaderV3:
    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        # self.all_symbols = self.get_all_symbols()
        self.zstd_cutoff = datetime(2024, 12, 31)  # 使用datetime类型便于比较
        self.golang_cutoff = datetime(2025, 1, 1)

    def _gen_date_sequence(self, start_date: str, end_date: str) -> List[str]:
        """生成YYYYMMDD格式的日期序列"""
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        delta = end - start

        return [
            (start + timedelta(days=i)).strftime("%Y%m%d")
            for i in range(delta.days + 1)
        ]

    def _get_collection_name(self, date_str: str) -> str:
        """根据日期选择对应存储表"""
        dt = datetime.strptime(date_str, "%Y%m%d")
        return "stock_market_ticket_by_golang" if dt <= self.golang_cutoff else "stock_market_ticket_zstd"

    def _build_daily_query(self, date_str: str, query_params: Dict) -> Dict:
        """优化后的查询条件构建"""
        # 时区处理（根据实际数据时区调整）
        start_time = datetime.strptime(date_str, "%Y%m%d")
        end_time = start_time + timedelta(days=1)

        query = {
            "datetime": {
                "$gte": start_time,
                "$lt": end_time
            }
        }
        if query_params.get("symbol") is not None:
            query['symbol'] = query_params['symbol']

        return query

    def _fetch_single_day(self, date_str: str, query_params: Dict) -> Optional[pd.DataFrame]:
        """获取单日数据"""
        start_time = time.time()
        try:
            # 确定目标集合
            collection_name = self._get_collection_name(date_str)

            # 构建查询
            query = self._build_daily_query(date_str, query_params)
            fields = query_params['fields']

            # 构建投影
            projection = {'_id': 0}
            if fields:
                projection.update({f: 1 for f in fields})
                # 投影中至少包含 symbol+datetime,这两个字段构建一个业务 key
                if 'symbol' not in fields:
                    projection['symbol'] = 1
                if 'datetime' not in fields:
                    projection['datetime'] = 1

            # 获取集合句柄
            collection = self.db_handler.get_mongo_collection(
                self.config["MONGO_DB"],
                collection_name
            )
            # 智能批处理策略
            batch_size = 5000 if len(projection) > 10 else 10000

            # 执行查询
            cursor = collection.find(query, projection).batch_size(batch_size)
            df = pd.DataFrame(list(cursor))

            if df.empty:
                return None
            # 添加处理日期用于后续合并
            df['_proc_date'] = date_str
            return df

        except Exception as e:
            logger.error(f"日期 {date_str} 查询失败: {str(e)}")
            return None
        finally:
            logger.debug(f"日期 {date_str} 查询耗时: {time.time() - start_time:.2f}s")

    def get_data(self, symbol=None, start_date=None, end_date=None,fields=None):
        """新版数据接口-基于日期分片策略"""
        total_start = time.time()

        # 参数校验与转换
        if not all([start_date, end_date]):
            logger.error("必须提供start_date和end_date")
            return None

        # 生成日期序列
        date_sequence = self._gen_date_sequence(start_date, end_date)
        logger.debug(f"生成{len(date_sequence)}个日期任务，时间范围: {start_date}~{end_date}")
        # 准备查询参数
        query_params = {
            'fields': fields or [],
        }
        if symbol is not None:
            query_params['symbol'] = symbol
        # 并发执行每日查询
        dfs = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = {
                executor.submit(self._fetch_single_day, date_str, query_params): date_str
                for date_str in date_sequence
            }

            for future in concurrent.futures.as_completed(futures):
                date_str = futures[future]
                try:
                    day_df = future.result()
                    if day_df is not None:
                        dfs.append(day_df)
                        logger.debug(f"日期 {date_str} 获取到 {len(day_df)} 条记录")
                except Exception as e:
                    logger.error(f"日期 {date_str} 处理异常: {str(e)}")
        if not dfs:
            logger.warning("未查询到有效数据")
            return None

        # 合并数据
        final_df = pd.concat(dfs, ignore_index=True).drop(columns=['_proc_date'])

        # 精确去重（保留最新记录）
        final_df['timestamp'] = pd.to_datetime(final_df['datetime']).astype('int64')
        final_df = final_df.sort_values('timestamp', ascending=False)
        final_df = final_df.drop_duplicates(subset=['datetime', 'symbol'], keep='first')
        final_df = final_df.sort_values('timestamp').drop(columns=['timestamp'])

        logger.debug(
            f"总耗时 {time.time() - total_start:.2f}秒 | 最终数据量 {len(final_df)}条 | 去重前 {sum(len(df) for df in dfs)}条")
        return final_df


    """
     {
            "_id": {
                "$oid": "68280a3ca054d61a469b67b7"
            },
            "order_book_id": "000001.XSHE",
            "industry_code": "J66",
            "market_tplus": 1,
            "symbol": "平安银行",
            "special_type": "Normal",
            "exchange": "XSHE",
            "status": "Active",
            "type": "CS",
            "de_listed_date": "0000-00-00",
            "listed_date": {
                "$date": "1991-04-03T00:00:00.000Z"
            },
            "sector_code_name": "金融",
            "abbrev_symbol": "PAYH",
            "sector_code": "Financials",
            "round_lot": 100,
            "trading_hours": "09:31-11:30,13:01-15:00",
            "board_type": "MainBoard",
            "industry_name": "货币金融服务",
            "issue_price": 40,
            "trading_code": 1,
            "office_address": "中国广东省深圳市深南东路5047号;中国广东省深圳市福田区益田路5023号平安金融中心B座",
            "province": "广东省"
        }
    """
    def get_stock_instruments(self):
        """获取全量股票代码"""
        collectionName = "stock_instruments"
        collection = self.db_handler.get_mongo_collection(
            self.config["MONGO_DB"],
            collectionName
        )
        return pd.DataFrame(list(collection.find({},{"_id": 0})))

    """获取所有的股票代码"""
    def get_all_symbols(self):
        """Get all unique symbols using distinct command"""
        collection = self.db_handler.get_mongo_collection(
            self.config["MONGO_DB"],
            "stocks"
        )
        return pd.DataFrame(collection.distinct("symbol"))

