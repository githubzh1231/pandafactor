from abc import ABC
from datetime import timedelta
import pandas as pd
from chinese_calendar import is_holiday
from chinese_calendar import is_workday
from datetime import datetime
from panda_common.handlers.database_handler import DatabaseHandler



class StockStatisticQuery(ABC):
    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)

    def get_stock_statistic(self, tables_name, start_date, end_date, page, page_size,
                            sort_field, sort_order):
        """
        获取多个表中每天的记录数，并计算其他表与stock_market表的差值
        :param tables_name: 逗号分隔的表名（第一个必须是stock_market）
        :param start_date: 开始日期(YYYYMMDD)
        :param end_date: 结束日期(YYYYMMDD)
        :param page: 当前页码
        :param page_size: 每页大小
        :param sort_field: 排序字段（date、{table}_count或{table}_difference）
        :param sort_order: 排序方式，asc升序，desc降序
        :return: 包含统计数据和分页信息的字典
        """
        # 解析表名
        table_list = [name.strip() for name in tables_name.split(",")]
        if not table_list:
            raise ValueError("至少需要提供一个表名")

        # 验证第一个表是stock_market
        if table_list[0] != "stock_market":
            raise ValueError("第一个表必须是stock_market")

        # 验证排序方式
        if sort_order.lower() not in ["asc", "desc"]:
            raise ValueError("排序方式必须是asc或desc")

        # 计算日期范围
        start_dt = datetime.strptime(start_date, "%Y%m%d")
        end_dt = datetime.strptime(end_date, "%Y%m%d")

        # 计算总天数
        total_days = (end_dt - start_dt).days + 1

        # 计算分页信息
        total_pages = (total_days + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_days)

        # 获取当前页的日期列表
        date_list = []
        current_date = start_dt
        for i in range(total_days):
            if start_index <= i < end_index:
                date_list.append(current_date.strftime("%Y%m%d"))
            current_date += timedelta(days=1)

        # 初始化集合连接
        collections = {
            table: self.db_handler.mongo_client[self.config["MONGO_DB"]][table]
            for table in table_list
        }

        # 查询所有表的记录数
        result = []
        for date in date_list:
            date_stats = {"date": date}
            stock_market_count = None

            # 查询每个表的记录数
            for i, table in enumerate(table_list):
                count = collections[table].count_documents({"date": date})
                date_stats[f"{table}_count"] = count

                # 保存stock_market的count
                if i == 0:
                    stock_market_count = count
                # 计算其他表与stock_market的差值
                elif stock_market_count is not None:
                    date_stats[f"{table}_difference"] = stock_market_count - count

            result.append(date_stats)

        # 排序功能实现
        if sort_field:
            reverse = sort_order.lower() == "desc"

            if sort_field == "date":
                # 日期按字符串排序（YYYYMMDD格式可以直接比较）
                result.sort(key=lambda x: x["date"], reverse=reverse)
            else:
                # 其他字段按数值排序
                result.sort(key=lambda x: x.get(sort_field, 0), reverse=reverse)

        return {
            "data": result,
            "pagination": {
                "total": total_days,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        }

    def get_trading_days(self, start_date, end_date):
        """
        完全基于中国日历的实现
        """
        # 转换日期格式
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')

        # 获取所有日期
        all_days = pd.date_range(start, end)

        trading_days = []

        for day in all_days:
            day_date = day.to_pydatetime()

            # 基本过滤条件
            if day_date.weekday() >= 5:  # 周六周日
                # 特别处理调休日：虽然是周末但是工作日
                if is_workday(day_date):
                    continue  # 股市周末休市，即使调休
                else:
                    continue  # 正常周末
            else:  # 周一至周五
                if is_holiday(day_date):
                    continue  # 法定节假日

            trading_days.append(day_date.strftime('%Y%m%d'))

        return trading_days