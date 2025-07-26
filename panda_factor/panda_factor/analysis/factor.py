import math

from statsmodels.tsa.stattools import acf
from panda_factor.analysis.factor_func import *
from panda_common.models.chart_data import *
from scipy.stats import ttest_1samp

from panda_common.config import config
from panda_common.handlers.database_handler import DatabaseHandler
from datetime import datetime
import uuid
import logging
import traceback
from typing import List, Optional


class factor():
    def __init__(self, name: str, group_number: int = 10, factor_id: str = None) -> None:
        self.name: str = name  # 因子名称
        self.factor_id: str = factor_id if factor_id else str("unable get")  # 因子ID
        self.last_date_top_factor = pd.DataFrame()
        self.period: int = 1  # 因子回测周期
        self.predict_direction = 0  # 预测方向为反向,即因子值越小越好
        self.commission = 0.002  # 手续费+滑点默认为千2
        self.mode = 1  # 回测模式(0为只回测分层测试图,1为全面回测)
        self.group_cnt = group_number  # 分组数量

        self.df_pnl = pd.DataFrame()  # 储存不同分组超额和绝对收益矩阵
        self.df_stock = pd.DataFrame()  # 储存不同分组持仓股票矩阵
        self.df_turnover = pd.DataFrame()  # 储存计算过后的组内换手率
        self.df_ic = pd.DataFrame()  # 储存IC值、滞后N期-IC矩阵
        self.logger = logging.Logger
        self.df_group = pd.DataFrame()  # 储存多空分组不同周期平均收益率和标准差矩阵

        # 使用动态分组数量创建统计指标矩阵
        group_names = [f'分组{i}' for i in range(1, self.group_cnt + 1)]
        if self.group_cnt >= 4:
            self.df_info = pd.DataFrame(index=group_names + ['多空组合', '多空组合2'],
                                        columns=['年化收益率', '超额年化', '最大回撤', '超额最大回撤', '年化波动',
                                                 '超额年化波动', '换手率', '月度胜率', '超额月度胜率', '跟踪误差',
                                                 '夏普比率', '信息比率'])  # 储存多空分组年化、夏普等统计指标矩阵
        else:
            self.df_info = pd.DataFrame(index=group_names + ['多空组合'],
                                        columns=['年化收益率', '超额年化', '最大回撤', '超额最大回撤', '年化波动',
                                                 '超额年化波动', '换手率', '月度胜率', '超额月度胜率', '跟踪误差',
                                                 '夏普比率', '信息比率'])  # 储存多空分组年化、夏普等统计指标矩阵
        self.df_info2 = pd.DataFrame(index=[self.name],
                                     columns=['IC_mean', 'Rank_IC', 'IC_std', 'IC_IR', 'IR', 'P(IC<-0.02)',
                                              'P(IC>0.02)', 't统计量', 'p-value', '单调性']).T  # 储存因子IC各项评估信息

    def set_backtest_parameters(self, period: int, predict_direction: int = 0, commission: float = 0.002,
                                mode: int = 1) -> None:
        """
        # 设置因子回测的相关参数
        :param period:回测周期
        :param predict_direction:预测方向(0为因子值越小越好,IC为负/1为因子值越大越好,IC为正)
        :param commission:手续费+滑点(默认为千2)
        :param mode:0为简单回测,1为全面回测(默认为1)
        """
        self.period = period
        self.predict_direction = predict_direction
        self.commission = commission
        self.mode = mode

    def cal_turnover_rate(self) -> None:
        """
        #计算各个分组换手率,结果保存到self.df_turnover中
        """
        if self.df_stock.empty:
            return

        # 创建一个新的 DataFrame 用于存储换手率(储存不同组不同持仓周期下的换手率信息)
        column_list = []
        for n in range(1, self.group_cnt + 1):
            column_list.append(f'group{n}_day_turnover')
        self.df_turnover = pd.DataFrame(index=self.df_stock.index, columns=column_list)

        for i in range(0, self.df_stock.shape[0]):
            # 跳过前几天
            if i < self.period:
                continue

            for n in range(0, self.group_cnt):
                prev_stock = self.df_stock.iloc[i - self.period, n]
                today_stock = self.df_stock.iloc[i, n]

                # 检查数据是否有效
                if not prev_stock or not today_stock:
                    self.df_turnover.iloc[i, n] = np.nan
                    continue

                try:
                    # 确保 prev_stock 和 today_stock 是列表
                    if isinstance(prev_stock, (np.ndarray, pd.Series)):
                        prev_stock = prev_stock.tolist()
                    if isinstance(today_stock, (np.ndarray, pd.Series)):
                        today_stock = today_stock.tolist()

                    # 如果数据为空，设置为 NaN
                    if not prev_stock or not today_stock:
                        self.df_turnover.iloc[i, n] = np.nan
                        continue

                    # 确保是列表类型
                    if not isinstance(prev_stock, list):
                        prev_stock = [prev_stock]
                    if not isinstance(today_stock, list):
                        today_stock = [today_stock]

                    prev_stock_set = set(prev_stock)
                    today_stock_set = set(today_stock)

                    changed_stock_num = len(today_stock_set - prev_stock_set)
                    turnover_rate = changed_stock_num / len(prev_stock_set) if prev_stock_set else 0
                    self.df_turnover.iloc[i, n] = turnover_rate
                except Exception as e:
                    print(f"计算换手率时出错: {str(e)}")
                    self.df_turnover.iloc[i, n] = np.nan

    def cal_df_stock(self, df: pd.DataFrame) -> None:
        stock_dict = {}  # 储存组内持仓股票字典  {'日期':{'group1_code':[]}}
        for date, group in df.groupby('date'):
            stock_child_dict = {}
            for num, temp in group.groupby(f'{self.name}_group'):
                stock_child_dict[f'group{num}_code'] = temp['symbol'].tolist()  # 记录组内的股票代码,后续计算换手率

            stock_dict[date] = stock_child_dict

        # 创建不同分组的股票列表矩阵
        df_stock = pd.DataFrame(stock_dict)
        self.df_stock = df_stock

    # def cal_df_stock(self, df: pd.DataFrame) -> None:
    #     stock_dict = {}  # 储存组内持仓股票字典  {'日期':{'group1_code':[]}}
    #     for date, group in df.groupby('trade_date'):
    #         stock_child_dict = {}
    #         for num, temp in group.groupby(f'{self.name}_group'):
    #             stock_child_dict[f'group{num}_code'] = temp['ts_code'].tolist()  # 记录组内的股票代码,后续计算换手率
    #
    #         stock_dict[date] = stock_child_dict
    #
    #     # 创建不同分组的股票列表矩阵
    #     df_stock = pd.DataFrame(stock_dict).T
    #     self.df_stock = df_stock
    def show_df_info(self, types: int = 0) -> None:
        """
        # 显示多空分组、IC各类统计信息
        :param types:0为多空分组年化、夏普等统计指标矩阵,1为因子IC各项评估信息
        """
        if self.df_info.empty:
            print('统计指标数据缺失!')
            return

        if types == 0:
            display(self.df_info)
            return self.df_info
        else:
            display(self.df_info2)
            return self.df_info2

    def cal_df_info1(self) -> None:
        if self.group_cnt >= 4:
            _group_number = self.group_cnt + 3
        else:
            _group_number = self.group_cnt + 2
        for i in range(1, _group_number):
            if i <= self.group_cnt:
                group_return = self.df_pnl[f'group{i}_pnl']
                group_pro = self.df_pnl[f'group{i}_pro']
                self.df_info.iloc[i - 1]['换手率'] = str_round(self.df_turnover.iloc[:, i - 1].mean(), 4, True)
            elif i == self.group_cnt + 1:  # 多空组合1
                group_return = self.df_pnl['group_ls']
                group_pro = self.df_pnl['group_ls_pro']
                self.df_info.iloc[i - 1]['换手率'] = str_round(
                    (self.df_turnover.iloc[:, 0].mean() + self.df_turnover.iloc[:, self.group_cnt - 1].mean()) / 2, 4,
                    True)
            elif i == self.group_cnt + 2:  # 多空组合2
                group_return = self.df_pnl['group_ls_2']
                group_pro = self.df_pnl['group_ls_2_pro']
                self.df_info.iloc[i - 1]['换手率'] = str_round(
                    (self.df_turnover.iloc[:, 1].mean() + self.df_turnover.iloc[:, self.group_cnt - 2].mean()) / 2, 4,
                    True)

            annualized_return = np.mean(group_return) * (252 / self.period)
            self.df_info.iloc[i - 1]['年化收益率'] = str_round(annualized_return, 4, True)

            annualized_volatility = np.std(group_return) * np.sqrt(252 / self.period)
            self.df_info.iloc[i - 1]['年化波动'] = str_round(annualized_volatility, 4, True)

            annualized_pro_volatility = np.std(group_pro) * np.sqrt(252 / self.period)
            self.df_info.iloc[i - 1]['超额年化波动'] = str_round(annualized_pro_volatility, 4, True)

            cumulative_returns = np.cumsum(np.array(group_return.dropna()))
            max_drawdown = np.max(np.maximum.accumulate(cumulative_returns) - cumulative_returns)
            self.df_info.iloc[i - 1]['最大回撤'] = str_round(max_drawdown, 4, True)

            cumulative_pro_returns = np.cumsum(np.array(group_pro.dropna()))
            max_drawdown = np.max(np.maximum.accumulate(cumulative_pro_returns) - cumulative_pro_returns)
            self.df_info.iloc[i - 1]['超额最大回撤'] = str_round(max_drawdown, 4, True)

            sharpe_ratio = (annualized_return - 0.025) / annualized_volatility
            if not math.isfinite(sharpe_ratio):  # 如果是inf或nan
                sharpe_ratio = 0
            self.df_info.iloc[i - 1]['夏普比率'] = str_round(sharpe_ratio, 4)

            excess_annualized_return = group_pro.mean() * (252 / self.period)
            tracking_error = np.sqrt(np.sum(group_pro ** 2) / (len(group_pro) - 1))
            if not math.isfinite(tracking_error):  # 如果是inf或nan
                tracking_error = 0
            self.df_info.iloc[i - 1]['跟踪误差'] = str_round(tracking_error, 4)

            self.df_info.iloc[i - 1]['超额年化'] = str_round(excess_annualized_return, 4, True)

            monthly_return = group_return.groupby(pd.Grouper(freq='M')).sum()
            win_rate = monthly_return[monthly_return > 0].count() / len(monthly_return)
            self.df_info.iloc[i - 1]['月度胜率'] = str_round(win_rate, 4, True)

            monthly_pro_return = group_pro.groupby(pd.Grouper(freq='M')).sum()
            win_pro_rate = monthly_pro_return[monthly_pro_return > 0].count() / len(monthly_pro_return)
            self.df_info.iloc[i - 1]['超额月度胜率'] = str_round(win_pro_rate, 4, True)

            IR = excess_annualized_return / annualized_pro_volatility
            if not math.isfinite(IR):  # 如果是inf或nan
                IR = 0
            self.df_info.iloc[i - 1]['信息比率'] = str_round(IR, 4)

            # factor_path = 'D:\\quant\\project\\Backtesting\\single-factor\\factor_lib\\' + self.name
            # self.df_info.to_csv(factor_path + '\\多空分组统计指标.csv')

    def cal_df_info2(self) -> None:
        ic_value = self.df_ic['ic']
        ir_value = self.df_ic['ir']
        self.df_info2.loc['IC_mean', self.name] = str_round(ic_value.mean(), 4)
        self.df_info2.loc['Rank_IC', self.name] = str_round(self.df_ic['rank_ic'].mean(), 4)
        self.df_info2.loc['IC_std', self.name] = str_round(ic_value.std(), 4)
        self.df_info2.loc['IC_IR', self.name] = str_round(ic_value.mean() / ic_value.std(), 4)
        self.df_info2.loc['IR', self.name] = str_round(ir_value.mean(), 4)
        self.df_info2.loc['P(IC>0.02)', self.name] = str_round(np.sum((ic_value) > 0.02) / len(ic_value), 4, True)
        self.df_info2.loc['P(IC<-0.02)', self.name] = str_round(np.sum((ic_value) < -0.02) / len(ic_value), 4, True)
        ic_value = ic_value.fillna(0)
        # t_stat, p_value = ttest_ind(ic_value, np.zeros(len(ic_value)))

        t_stat, p_value = ttest_1samp(ic_value, popmean=0)
        self.df_info2.loc['t统计量', self.name] = str_round(t_stat, 4)
        self.df_info2.loc['p-value', self.name] = str_round(p_value, 4)

        # 根据动态分组获取年化收益率排名
        ann_return_rankings = self.df_info.iloc[0:self.group_cnt]['年化收益率'].str.replace('%', '').astype(
            float).reset_index(drop=True)
        self.df_info2.loc['单调性', self.name] = str_round(
            abs(ann_return_rankings.corr(pd.Series(np.arange(1, self.group_cnt + 1)))), 2)
        # factor_path = 'D:\\quant\\project\\Backtesting\\single-factor\\factor_lib\\' + self.name
        # self.df_info2.to_csv(factor_path + '\\IC统计指标.csv')

    def start_backtest(self, df: pd.DataFrame, df_benchmark_pct: pd.DataFrame) -> None:
        """
        # 参数设置好后就可以开始回测了
        :param df:整理好的因子和k线数据dataframe
        """
        if df.empty or self.name not in df.columns:
            print('回测数据缺失!')
            return

        self.cal_df_stock(df)
        self.cal_turnover_rate()

        pnl_dict = {}  # 储存超额和绝对收益 {'日期':{'group1_pro':...,'group1_pnl':...}}
        ic_dict = {}  # 储存IC字典 {'日期':{'ic':...,'rank_ic':...,'ic_lag1':...}}

        day_count = 0
        for date, group in df.groupby('date'):
            if group.empty:
                continue

            if group[self.name].dropna().nunique() < self.group_cnt:  # 检查去掉NaN后的唯一值数量是否小于设定的分组数
                print(f"因子{self.name},{date},分组小于{self.group_cnt},已跳过")
                continue

            # 每个周期统计的信息(观测周期不为1时,按照天数跳过)
            if day_count % self.period != 0:
                day_count += 1
                continue
            day_count += 1

            pnl_child_dict = {}
            ic_child_dict = {}

            ic_child_dict['ic'] = group[self.name].corr(group[f'{self.period}day_return'])
            ic_child_dict['rank_ic'] = group[self.name].rank().corr(group[f'{self.period}day_return'].rank())
            ic_child_dict['ir'] = ic_child_dict['ic'] * np.power(group.shape[0], 0.5)  # 信息比率=IC*根号下(样本宽度)
            for i in range(1, 21):
                ic_child_dict[f'rank_ic_lag{i}'] = group[self.name].rank().corr(group[f'returns_lag{i}'].rank())
                # ic
                ic_child_dict[f'ic_lag{i}'] = group[self.name].corr(group[f'returns_lag{i}'])

            ic_dict[date] = ic_child_dict

            # 使用动态分组数量
            for n in range(1, self.group_cnt + 1):
                return_mean = group[group[f'{self.name}_group'] == n][f'{self.period}day_return'].mean()
                pnl_child_dict[f'group{n}_pnl'] = return_mean

            return_benchmark = df_benchmark_pct.loc[date, f'{self.period}D_m']
            pnl_child_dict['return_benchmark'] = return_benchmark

            pnl_dict[date] = pnl_child_dict

        # 创建不同分组的绝对和超额收益率矩阵
        df_pnl = pd.DataFrame(pnl_dict).T

        # 使用动态分组数量计算超额收益
        for n in range(1, self.group_cnt + 3):
            if n <= self.group_cnt:
                df_pnl[f'group{n}_pro'] = df_pnl[f'group{n}_pnl'] - df_pnl['return_benchmark']
            elif n == self.group_cnt + 1:  # 多空组合1
                if self.predict_direction == 0:
                    df_pnl['group_ls'] = df_pnl[f'group1_pnl'] - df_pnl[f'group{self.group_cnt}_pnl']
                    df_pnl['group_ls_pro'] = df_pnl[f'group1_pro'] - df_pnl[f'group{self.group_cnt}_pro']
                else:
                    df_pnl['group_ls'] = df_pnl[f'group{self.group_cnt}_pnl'] - df_pnl[f'group1_pnl']
                    df_pnl['group_ls_pro'] = df_pnl[f'group{self.group_cnt}_pro'] - df_pnl[f'group1_pro']
            elif n == self.group_cnt + 2:  # 多空组合2
                if self.group_cnt >= 4:
                    if self.predict_direction == 0:
                        df_pnl['group_ls_2'] = df_pnl[f'group2_pnl'] - df_pnl[f'group{self.group_cnt - 1}_pnl']
                        df_pnl['group_ls_2_pro'] = df_pnl[f'group2_pro'] - df_pnl[f'group{self.group_cnt - 1}_pro']
                    else:
                        df_pnl['group_ls_2'] = df_pnl[f'group{self.group_cnt - 1}_pnl'] - df_pnl[f'group2_pnl']
                        df_pnl['group_ls_2_pro'] = df_pnl[f'group{self.group_cnt - 1}_pro'] - df_pnl[f'group2_pro']

        self.df_pnl = df_pnl

        # 创建IC值、滞后N期-IC矩阵
        df_ic = pd.DataFrame(ic_dict).T
        self.df_ic = df_ic

        # 初始化回测结果矩阵
        self.cal_df_info1()
        self.cal_df_info2()

    def draw_pct(self) -> None:
        """
        # 画多空分组绝对收益图和超额收益图
        """
        if self.df_pnl.empty:
            print('收益率数据缺失!')
            return

        colors = [plt.cm.coolwarm(i) for i in np.linspace(0, 1, self.group_cnt)]
        # 重新创建画布，这次确保两个子图在视觉上的宽长比为1.1:1，并设置更高的DPI
        fig, axes = plt.subplots(1, 2, figsize=(22, 10), dpi=200)

        # 调整子图的宽高比，确保两个子图的高度相同
        for ax in axes:
            ax.set_box_aspect(1 / 1.1)

        # 绘制每个组的累积收益率
        for i in range(1, self.group_cnt + 1):
            axes[0].plot(self.df_pnl.index, self.df_pnl[f'group{i}_pnl'].cumsum(), label=f'group {i}',
                         color=colors[i - 1], linewidth=1.5)

        if self.predict_direction == 0:
            axes[0].plot(self.df_pnl.index, self.df_pnl['group_ls'].cumsum(),
                         label=f'group 1-{self.group_cnt}', color='black',
                         linestyle='--', linewidth=1.5)
            if self.group_cnt >= 4:
                axes[0].plot(self.df_pnl.index, self.df_pnl['group_ls_2'].cumsum(),
                             label=f'group 2-{self.group_cnt - 1}', color='purple',
                             linestyle='--', linewidth=1.5)
        else:
            axes[0].plot(self.df_pnl.index, self.df_pnl['group_ls'].cumsum(),
                         label=f'group {self.group_cnt}-1', color='black',
                         linestyle='--', linewidth=1.5)
            if self.group_cnt >= 4:
                axes[0].plot(self.df_pnl.index, self.df_pnl['group_ls_2'].cumsum(),
                             label=f'group {self.group_cnt - 1}-2', color='purple',
                             linestyle='--', linewidth=1.5)

        axes[0].set_title(f'{self.name} {self.group_cnt} groups return')

        axes[0].legend(loc='upper left', prop={'size': 10}, ncol=2)
        axes[0].grid(True)

        # 绘制每个组的超额收益率
        for i in range(1, self.group_cnt + 1):
            axes[1].plot(self.df_pnl.index, self.df_pnl[f'group{i}_pro'].cumsum(), label=f'group {i}',
                         color=colors[i - 1], linewidth=1.5)

        if self.predict_direction == 0:
            axes[1].plot(self.df_pnl.index, self.df_pnl['group_ls_pro'].cumsum(),
                         label=f'group 1-{self.group_cnt}', color='black',
                         linestyle='--', linewidth=1.5)
            if self.group_cnt >= 4:
                axes[1].plot(self.df_pnl.index, self.df_pnl['group_ls_2_pro'].cumsum(),
                             label=f'group 2-{self.group_cnt - 1}', color='purple',
                             linestyle='--', linewidth=1.5)
        else:
            axes[1].plot(self.df_pnl.index, self.df_pnl['group_ls_pro'].cumsum(),
                         label=f'group {self.group_cnt}-1', color='black',
                         linestyle='--', linewidth=1.5)
            if self.group_cnt >= 4:
                axes[1].plot(self.df_pnl.index, self.df_pnl['group_ls_2_pro'].cumsum(),
                             label=f'group {self.group_cnt - 1}-2', color='purple',
                             linestyle='--', linewidth=1.5)

        axes[1].set_title(f'{self.name} {self.group_cnt} groups excess return')
        axes[1].legend(loc='upper left', prop={'size': 10}, ncol=2)
        axes[1].grid(True)

        axes[0].yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1, decimals=0))
        axes[1].yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1, decimals=0))
        # axes[0].xaxis.set_major_locator(plt.MaxNLocator(20))
        # axes[1].xaxis.set_major_locator(plt.MaxNLocator(20))
        plt.tight_layout()  # 调整子图参数，使之填充整个图像区域
        # axes[0].xaxis.set_major_locator(ticker.MultipleLocator(252))
        # axes[1].xaxis.set_major_locator(ticker.MultipleLocator(252))
        # plt.savefig(f'D:\\quant\\project\\Backtesting\\single-factor\\factor_lib\\{self.name}\\分组收益图.png', dpi=200)
        plt.show()

    def draw_ic(self, types: int = 0) -> None:
        """
        # 画IC时序图和IC密度图
        :param types:IC时序图类型(0为normal_IC,1为rank_IC)
        """
        if self.df_ic.empty:
            print('IC序列数据缺失!')
            return

        fig, axes = plt.subplots(1, 2, figsize=(22, 10), dpi=200)

        if types:
            ic_value = self.df_ic['rank_ic']
            mu = np.mean(ic_value)
            sigma = np.std(ic_value)
            axes[0].set_title(f'{self.name} Rank_IC={str_round(mu, 3)} IC_IR={str_round((mu / sigma), 4)}')
        else:
            ic_value = self.df_ic['ic']
            mu = np.mean(ic_value)
            sigma = np.std(ic_value)
            axes[0].set_title(f'{self.name} IC={str_round(mu, 3)} IC_IR={str_round((mu / sigma), 4)}')

        for date, value in ic_value.items():
            if value > 0:
                axes[0].bar(date, value, color='red')
            else:
                axes[0].bar(date, value, color=(31 / 255, 119 / 255, 180 / 255))
        axes[0].set_ylabel('IC')
        axes[0].set_xlabel('Date')
        axes[0].set_ylim([ic_value.min(), ic_value.max()])

        ax2 = axes[0].twinx()  # 创建共享同一个x轴的次轴
        ax2.plot(self.df_ic.index, self.df_ic['ic'].cumsum(), color='black')
        ax2.set_ylabel('cum_IC')

        axes[1].set_title(
            f'{self.name} IC distribution skew={str_round(ic_value.skew(), 3)} kurt={str_round(ic_value.kurt(), 3)}')
        n, bins, patches = axes[1].hist(x=ic_value, bins=60, density=True, color=(138 / 255, 188 / 255, 220 / 255),
                                        edgecolor='black')
        y = norm.pdf(bins, mu, sigma)
        axes[1].plot(bins, y, color=(61 / 255, 109 / 255, 141 / 255))
        axes[1].axvline(mu, color='black', linestyle='--')
        axes[1].set_ylabel('Density')
        axes[1].set_xlabel('IC')

        # 调整子图的宽高比，确保两个子图的高度相同
        for ax in axes:
            ax.set_box_aspect(1 / 1.1)

        axes[0].xaxis.set_major_locator(plt.MaxNLocator(10))
        plt.tight_layout()  # 调整子图参数，使之填充整个图像区域
        # plt.savefig(f'D:\\quant\\project\\Backtesting\\single-factor\\factor_lib\\{self.name}\\IC时序图.png', dpi=200)
        plt.show()

    def draw_ic_dacay(self) -> None:
        """
        # 画滞后N期-IC衰减图和IC自相关性图
        """
        if self.df_ic.empty:
            print('IC序列数据缺失!')
            return
        fig, axes = plt.subplots(1, 2, figsize=(22, 10), dpi=200)

        for ax in axes:
            ax.set_box_aspect(1 / 1.1)

        for i in range(0, 21):
            if i == 0:
                ic_mean = self.df_ic[f'rank_ic'].mean()
                axes[0].bar(i, ic_mean, color=(31 / 255, 119 / 255, 180 / 255), edgecolor='black')
                if ic_mean >= 0:
                    axes[0].text(i, ic_mean, str_round(ic_mean, 3), ha='center', va='bottom', fontsize=10)
                else:
                    axes[0].text(i, ic_mean, str_round(ic_mean, 3), ha='center', va='top', fontsize=10)
            else:
                ic_mean = self.df_ic[f'rank_ic_lag{i}'].mean()
                axes[0].bar(i, ic_mean, color=(31 / 255, 119 / 255, 180 / 255), edgecolor='black')
                if ic_mean >= 0:
                    axes[0].text(i, ic_mean, str_round(ic_mean, 3), ha='center', va='bottom', fontsize=10)
                else:
                    axes[0].text(i, ic_mean, str_round(ic_mean, 3), ha='center', va='top', fontsize=10)

        axes[0].set_title('rank_IC衰减图')
        axes[0].set_ylabel('Rank_IC')
        axes[0].set_xlabel('滞后期数')
        axes[0].set_xticks([i for i in range(0, 21)])

        sm.graphics.tsa.plot_acf(self.df_ic['rank_ic'], lags=40, alpha=0.05, ax=axes[1])
        axes[1].set_xlabel('滞后期数')
        axes[1].set_title("ACF with 95% Confidence Intervals")

        plt.tight_layout()  # 调整子图参数，使之填充整个图像区域
        # plt.savefig(f'D:\\quant\\project\\Backtesting\\single-factor\\factor_lib\\{self.name}\\IC衰减图.png', dpi=200)
        plt.show()

    def ic_sequential_to_chart_data(self, ic_type: int = 0) -> ChartData:
        """
        # IC|Rank_IC时序图
        :param ic_type: 时序图类型(0为normal_IC,1为rank_IC)
        :return: ChartData对象，包含IC时序图数据
        """
        # 将索引转换为日期列表
        dates = self.df_ic.index.tolist()
        date_strs = [str(date) if date is not None else "" for date in dates]

        def clean_float_list(values) -> List[Optional[float]]:
            """Helper function to clean float values for JSON serialization"""
            return [None if pd.isna(x) or np.isinf(x) else float(x) for x in values]

        if ic_type:
            # 使用Rank_IC
            ic_value = self.df_ic['rank_ic'].fillna(0)  # Replace NaN with 0 for statistics
            mu = float(ic_value.mean())
            sigma = max(float(ic_value.std()), 1e-10)  # Avoid division by zero
            title = f'{self.name} Rank_IC={str_round(mu, 3)} IC_IR={str_round(mu / sigma, 4)}'

            # 创建x轴和y轴数据
            x_data = [SeriesItem(name="date", data=date_strs)]
            y_data = [
                SeriesItem(name="Rank_IC", data=clean_float_list(self.df_ic['rank_ic'].fillna(0).values)),
                SeriesItem(name="Cum_Rank_IC", data=clean_float_list(self.df_ic['rank_ic'].fillna(0).cumsum().values))
            ]
        else:
            # 使用普通IC
            ic_value = self.df_ic['ic'].fillna(0)  # Replace NaN with 0 for statistics
            mu = float(ic_value.mean())
            sigma = max(float(ic_value.std()), 1e-10)  # Avoid division by zero
            title = f'{self.name} IC={str_round(mu, 3)} IC_IR={str_round(mu / sigma, 4)}'

            # 创建x轴和y轴数据
            x_data = [SeriesItem(name="date", data=date_strs)]
            y_data = [
                SeriesItem(name="IC", data=clean_float_list(self.df_ic['ic'].fillna(0).values)),
                SeriesItem(name="Cum_IC", data=clean_float_list(self.df_ic['ic'].fillna(0).cumsum().values))
            ]

        # 返回ChartData对象
        return ChartData(
            title=title,
            x=x_data,
            y=y_data
        )

    def ic_density_to_chart_data(self, ic_type: int = 0) -> ChartData:
        """
        # IC|Rank_IC密度图
        :param ic_type:图类型(0为normal_IC,1为rank_IC)
        """
        # 将索引转换为日期列表
        dates = self.df_ic.index.tolist()
        date_strs = [str(date) for date in dates]

        if ic_type:
            # 使用Rank_IC
            ic_value = self.df_ic['rank_ic']
            ic_value.fillna(0, inplace=True)
            mu = np.mean(ic_value)
            sigma = np.std(ic_value)
            n, bins = np.histogram(ic_value, bins=60, density=True)
            y = norm.pdf(bins, mu, sigma)
            title = f'{self.name} Rank_IC distribution skew={str_round(ic_value.skew(), 3)} kurt={str_round(ic_value.kurt(), 3)}'

            # 创建x轴和y轴数据
            x_data = [SeriesItem(name="Rank_IC", data=bins.tolist())]
            y_data = [
                SeriesItem(name="Density", data=n.tolist()),
                SeriesItem(name="Density", data=norm.pdf(bins, mu, sigma).tolist())
            ]
        else:
            # 使用普通IC
            ic_value = self.df_ic['ic']
            ic_value.fillna(0, inplace=True)
            mu = np.mean(ic_value)
            sigma = np.std(ic_value)
            n, bins = np.histogram(ic_value, bins=60, density=True)
            y = norm.pdf(bins, mu, sigma)
            title = f'{self.name} IC distribution skew={str_round(ic_value.skew(), 3)} kurt={str_round(ic_value.kurt(), 3)}'

            # 创建x轴和y轴数据
            x_data = [SeriesItem(name="IC", data=bins.tolist())]
            y_data = [
                SeriesItem(name="Density", data=n.tolist()),
                SeriesItem(name="Density", data=norm.pdf(bins, mu, sigma).tolist())
            ]

        # 返回ChartData对象
        return ChartData(
            title=title,
            x=x_data,
            y=y_data
        )

    def simple_return_chart(self) -> ChartData:
        dates = self.df_ic.index.tolist()
        date_strs = [str(date) for date in dates]
        x_data = [SeriesItem(name="date", data=date_strs)]
        if self.predict_direction:
            y_data = [SeriesItem(name=f"组{self.group_cnt}",
                                 data=self.df_pnl[f'group{self.group_cnt}_pnl'].fillna(0).cumsum().tolist())]
        else:
            y_data = [SeriesItem(name="组1", data=self.df_pnl[f'group1_pnl'].fillna(0).cumsum().tolist())]

        return ChartData(
            title=f'{self.name} one groups return',
            x=x_data,
            y=y_data
        )

    def return_to_chart_data(self) -> ChartData:
        # 将索引转换为日期列表
        dates = self.df_ic.index.tolist()
        date_strs = [str(date) for date in dates]
        x_data = [SeriesItem(name="date", data=date_strs)]
        y_data = []
        for group_idx in range(1, self.group_cnt + 1):
            y_data.append(SeriesItem(
                name=f'组{group_idx}',
                data=self.df_pnl[f'group{group_idx}_pnl'].fillna(0).cumsum().tolist()
            ))
        if self.predict_direction:
            # 添加多空组合数据
            y_data.append(SeriesItem(
                name=f'多空组合(组{self.group_cnt}-组1)',
                data=self.df_pnl['group_ls'].fillna(0).cumsum().tolist()
            ))
            if self.group_cnt >= 4:
                y_data.append(SeriesItem(
                    name=f'多空组合2(组{self.group_cnt - 1}-组2)',
                    data=self.df_pnl['group_ls_2'].fillna(0).cumsum().tolist()
                ))
        else:
            # 添加多空组合数据
            y_data.append(SeriesItem(
                name=f'多空组合(组1-组{self.group_cnt})',
                data=self.df_pnl['group_ls'].fillna(0).cumsum().tolist()
            ))
            if self.group_cnt >= 4:
                y_data.append(SeriesItem(
                    name=f'多空组合2(组2-组{self.group_cnt - 1})',
                    data=self.df_pnl['group_ls_2'].fillna(0).cumsum().tolist()
                ))
        return ChartData(
            title=f'{self.name} {self.group_cnt} groups return',
            x=x_data,
            y=y_data
        )

    def excess_return_to_chart_data(self) -> ChartData:
        # 将索引转换为日期列表
        dates = self.df_ic.index.tolist()
        date_strs = [str(date) for date in dates]
        x_data = [SeriesItem(name="date", data=date_strs)]
        y_data = []
        for group_idx in range(1, self.group_cnt + 1):
            y_data.append(SeriesItem(
                name=f'组{group_idx}',
                data=self.df_pnl[f'group{group_idx}_pro'].fillna(0).cumsum().tolist()
            ))
        # 添加多空组合数据
        if self.predict_direction:
            y_data.append(SeriesItem(
                name=f'多空组合(组{self.group_cnt}-组1)',
                data=self.df_pnl['group_ls'].fillna(0).cumsum().tolist()
            ))
            if self.group_cnt >= 4:
                y_data.append(SeriesItem(
                    name=f'多空组合2(组{self.group_cnt - 1}-组2)',
                    data=self.df_pnl['group_ls_2'].cumsum().fillna(0).tolist()
                ))
        else:
            y_data.append(SeriesItem(
                name=f'多空组合(组1-组{self.group_cnt})',
                data=self.df_pnl['group_ls'].fillna(0).cumsum().tolist()
            ))
            if self.group_cnt >= 4:
                y_data.append(SeriesItem(
                    name=f'多空组合2(组2-组{self.group_cnt - 1})',
                    data=self.df_pnl['group_ls_2'].fillna(0).cumsum().tolist()
                ))

        return ChartData(
            title=f'{self.name} {self.group_cnt} groups excess return',
            x=x_data,
            y=y_data
        )

    def ic_decay_to_chart_data(self, ic_type: int = 0) -> ChartData:
        """
        生成IC衰减图表数据

        参数:
        - ic_type: 0为普通IC，1为RankIC

        返回:
        - ChartData对象，包含IC衰减数据
        """
        # 确定要使用的IC数据列
        ic_col = 'rank_ic' if ic_type else 'ic'

        # 准备数据
        lags = [0]  # 初始包含当期
        ic_values = [float(self.df_ic[ic_col].mean())]

        # 添加滞后1-20期的IC值
        for i in range(1, 21):
            lag_column = f'{ic_col}_lag{i}'
            if lag_column in self.df_ic.columns:
                lags.append(i)
                ic_values.append(float(self.df_ic[lag_column].mean()))

        # 创建SeriesItem对象
        x_data = [SeriesItem(name="滞后期数", data=lags)]
        y_data = [SeriesItem(name="IC值", data=ic_values)]

        # 创建图表标题
        title = f'{self.name} Rank IC衰减图' if ic_type else f'{self.name} IC衰减图'

        return ChartData(
            title=title,
            x=x_data,
            y=y_data
        )

    def ic_self_correlation_to_chart_data(self, ic_type: int = 0) -> ChartData:
        """
        生成IC自相关图表数据

        参数:
        - ic_type: 0为普通IC，1为RankIC

        返回:
        - ChartData对象，包含IC自相关数据
        """
        # 确定要使用的IC数据列
        ic_col = 'rank_ic' if ic_type else 'ic'

        # 确保有足够的数据计算自相关
        if len(self.df_ic[ic_col].dropna()) <= 5:
            # 数据不足，返回空图表
            return ChartData(
                title=f'{self.name} {"Rank IC" if ic_type else "IC"}自相关图（数据不足）',
                x=[SeriesItem(name="滞后期数", data=[0])],
                y=[SeriesItem(name="自相关系数", data=[1.0])]
            )

        # 计算自相关系数
        nlags = min(40, len(self.df_ic[ic_col].dropna()) - 1)
        acf_values, confint = acf(self.df_ic[ic_col].dropna(), nlags=nlags, alpha=0.05, fft=False)

        # 提取数据
        lags = list(range(len(acf_values)))
        acf_data = acf_values.tolist()
        lower_bounds = [float(confint[i][0]) for i in range(len(confint))]
        upper_bounds = [float(confint[i][1]) for i in range(len(confint))]

        # 创建SeriesItem对象
        x_data = [SeriesItem(name="滞后期数", data=lags)]
        y_data = [
            SeriesItem(name="自相关系数", data=acf_data),
            SeriesItem(name="下限(95%置信区间)", data=lower_bounds),
            SeriesItem(name="上限(95%置信区间)", data=upper_bounds)
        ]

        # 创建图表标题
        title = f'{self.name} {"Rank IC" if ic_type else "IC"}自相关图'

        return ChartData(
            title=title,
            x=x_data,
            y=y_data
        )

    def calculate_performance_metrics(self, return_ratio):
        """
        计算收益率相关的性能指标

        参数:
        - returns_data: 收益率数据列表或序列

        返回:
        - dict: 包含收益率、夏普比率和最大回撤的字典
        """
        try:
            if self.predict_direction:
                df = self.df_info.iloc[self.group_cnt - 1]
            else:
                df = self.df_info.iloc[0]
            return {
                'return_ratio': f"{return_ratio:.2%}",  # 收益率
                'annualized_ratio': df.loc['年化收益率'],  # 年化收益率
                'sharpe_ratio': df.loc['夏普比率'],
                'maximum_drawdown': df.loc['最大回撤']
            }

        except Exception as e:
            print(f"计算性能指标时出错: {str(e)}")
            return {
                'return_ratio': 0.0,
                'annual_return': 0.0,
                'sharpe_ratio': 0.0,
                'maximum_drawdown': 0.0,
                'calmar_ratio': 0.0
            }

    def inset_to_database(self, factor_id: str = None, task_id=None) -> None:
        """
        将因子分析结果保存到数据库

        参数:
        - factor_id: 因子ID，用于日志记录
        """
        logger = self.logger
        try:
            from panda_common.handlers.database_handler import DatabaseHandler
            from panda_common.config import config

            # # 如果传入了factor_id，尝试查询相关任务信息
            # if factor_id:
            #     try:
            #         from panda_common.handlers.log_handler import get_factor_logger
            #
            #         # 查询任务信息和因子信息
            #         _temp_db = DatabaseHandler(config)
            #         tasks = _temp_db.mongo_find("panda", "tasks", {"task_id": task_id, "status": 1})
            #         if tasks and len(tasks) > 0:
            #             task = tasks[0]
            #             factors = _temp_db.mongo_find("panda", "user_factors", {"_id": factor_id})
            #             if factors and len(factors) > 0:
            #                 factor_info = factors[0]
            _db_handler = DatabaseHandler(config)

            # 添加数据预处理，确保所有数据都可以被序列化为JSON
            def preprocess_data(data):
                if isinstance(data, dict):
                    return {k: preprocess_data(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [preprocess_data(item) for item in data]
                elif isinstance(data, pd.DataFrame):
                    return data.to_dict(orient='records')
                elif isinstance(data, np.ndarray):
                    return data.tolist()
                elif pd.isna(data):
                    return None
                # 处理ChartData类型
                elif hasattr(data, 'dict') and callable(getattr(data, 'dict')):
                    return data.dict()
                else:
                    return data

            # 确保返回数据不为空
            if self.df_pnl.empty:
                logger.warning(f"factor {self.name}  df_pnl empty ，can't save to database")
                return

            # 准备文档数据
            try:
                # ========== 收益率图数据 ==========
                return_chart = self.return_to_chart_data()

                # ========== 超额收益率图数据 ==========
                excess_chart = self.excess_return_to_chart_data()

                # ========== IC时序图数据 ==========
                ic_seq_chart = self.ic_sequential_to_chart_data(0)

                # ========== RankIC时序图数据 ==========
                rank_ic_seq_chart = self.ic_sequential_to_chart_data(1)

                # ========== IC密度图数据 ==========
                ic_den_chart = self.ic_density_to_chart_data(0)

                # ========== RankIC密度图数据 ==========
                rank_ic_den_chart = self.ic_density_to_chart_data(1)

                # ========== IC衰减图数据 ==========
                ic_decay_chart = self.ic_decay_to_chart_data(0)

                # ========== RankIC衰减图数据 ==========
                rank_ic_decay_chart = self.ic_decay_to_chart_data(1)

                # ========== IC自相关性图数据 ==========
                ic_self_correlation_chart = self.ic_self_correlation_to_chart_data(0)

                # ========== RankIC自相关性图数据 ==========
                rank_ic_self_correlation_chart = self.ic_self_correlation_to_chart_data(1)

                # ========== 简单收益图数据 ==========
                simple_return_chart = self.simple_return_chart()

                # ========== 调用函数计算性能指标 ==========
                one_group_data = self.calculate_performance_metrics(round(simple_return_chart.y[0].data[-1], 4))

                # ========== 最新一天的因子值 TOP20 ==========
                try:
                    last_date_top_factor_dict = []
                    if not self.last_date_top_factor.empty:
                        # 复制数据，避免修改原始数据
                        top_20 = self.last_date_top_factor.copy()
                        # 对 value 列（假设是第3列，索引为2）保留4位小数
                        value_col = top_20.columns[2]  # 获取第3列的名称（可能是 'value'）
                        top_20[value_col] = top_20[value_col].round(4)

                        # 将所有数值列转换为字符串，避免序列化问题（排除 'date', 'symbol', 'name'）
                        for col in top_20.columns:
                            if col not in ['date', 'symbol', 'name']:  # 不转换非数值列
                                top_20[col] = top_20[col].astype(str)
                        # 转换成列表格式而不是字典格式
                        top_20 = top_20[['date', 'symbol', 'name', value_col]]
                        last_date_top_factor_dict = top_20.to_dict(orient='records')
                except Exception as e:
                    logger.error(f"处理最新一天因子值时出错: {str(e)}")
                    last_date_top_factor_dict = []

                # ========== 分组收益分析 ==========
                try:
                    group_return_analysis = []
                    if not self.df_info.empty:
                        # 复制数据并重置索引，使索引成为一个列
                        df_info_copy = self.df_info.copy().reset_index()
                        df_info_copy.rename(columns={'index': '分组'}, inplace=True)
                        # 将所有列转换为字符串
                        for col in df_info_copy.columns:
                            df_info_copy[col] = df_info_copy[col].astype(str)
                        # 转换为记录列表
                        group_return_analysis = df_info_copy.to_dict(orient='records')
                except Exception as e:
                    logger.error(f"处理分组收益分析时出错: {str(e)}")
                    group_return_analysis = []

                # ========== 因子数据分析 ==========
                try:
                    factor_data_analysis = []
                    if not self.df_info2.empty:
                        # 复制数据并重置索引，使索引成为一个列
                        df_info2_copy = self.df_info2.copy().reset_index()
                        df_info2_copy.rename(columns={'index': '指标'}, inplace=True)
                        # 将所有列转换为字符串
                        for col in df_info2_copy.columns:
                            df_info2_copy[col] = df_info2_copy[col].astype(str)
                        # 转换为记录列表
                        factor_data_analysis = df_info2_copy.to_dict(orient='records')
                except Exception as e:
                    logger.error(f"处理因子数据分析时出错: {str(e)}")
                    factor_data_analysis = []

                document = {
                    "task_id": str(task_id),
                    "factor_name": self.name,
                    "factor_id": factor_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "period": self.period,
                    "pred_direction": self.predict_direction,
                    "commission": self.commission,
                    "mode": self.mode,
                    "return_chart": return_chart.dict() if return_chart else {},
                    "excess_chart": excess_chart.dict() if excess_chart else {},
                    "ic_seq_chart": ic_seq_chart.dict() if ic_seq_chart else {},
                    "rank_ic_seq_chart": rank_ic_seq_chart.dict() if rank_ic_seq_chart else {},
                    "ic_den_chart": ic_den_chart.dict() if ic_den_chart else {},
                    "rank_ic_den_chart": rank_ic_den_chart.dict() if rank_ic_den_chart else {},
                    "ic_decay_chart": ic_decay_chart.dict() if ic_decay_chart else {},
                    "rank_ic_decay_chart": rank_ic_decay_chart.dict() if rank_ic_decay_chart else {},
                    "ic_self_correlation_chart": ic_self_correlation_chart.dict() if ic_self_correlation_chart else {},
                    "rank_ic_self_correlation_chart": rank_ic_self_correlation_chart.dict() if rank_ic_self_correlation_chart else {},
                    "simple_return_chart": simple_return_chart.dict() if simple_return_chart else {},
                    "one_group_data": one_group_data,
                    "last_date_top_factor": last_date_top_factor_dict,
                    "group_return_analysis": group_return_analysis,
                    "factor_data_analysis": factor_data_analysis
                }

                # 保存到数据库
                logger.debug(f"正在将因子分析结果保存到数据库: {self.name}")
                result = None

                collection = _db_handler.get_mongo_collection("panda", "factor_analysis_results")
                # TODO 线下课程
                result = collection.update_one(
                    {"factor_id": factor_id},
                    {"$set": document},
                    upsert=True
                )

                if result and (result.modified_count > 0 or result.upserted_id):

                    logger.debug(
                        f"因子分析结果已保存到数据库: {self.name}, 修改: {result.modified_count}, 插入: {result.upserted_id}")
                else:
                    logger.warning(f"未修改数据库中的因子记录: {self.name}")
            except Exception as doc_e:
                logger.error(f"准备文档数据时出错: {str(doc_e)}")
                traceback.print_exc()

        except Exception as e:
            logger.error(f"保存因子分析结果到数据库失败: {self.name}, 错误: {str(e)}")
            traceback.print_exc()

    def __str__(self) -> str:  # 重载print语句
        # self.draw_pct()
        # self.draw_ic()
        # self.draw_ic_dacay()

        # self.show_df_info(0)
        # self.show_df_info(1)
        return ''