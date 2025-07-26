# PandaFactor - PandaAI数据清洗

## 📌 数据源支持
| 数据商 | 文档链接 | 备注 |
|--------|----------|------|
| Tushare | [官方文档](https://www.tushare.pro/document/2) | - |
| 米筐(RiceQuant) | [官方文档](https://www.ricequant.com/doc/rqsdk/) | - |
| 迅投(ThinkTrader) | [官方文档](https://dict.thinktrader.net/dictionary/?id=q2AEDg) | 不支持macOS |

## 🏗 项目结构
```bash
panda_data_hub/
├── data/          # 股票数据清洗
├── factor/        # 因子数据计算
├── models/        # 数据交互DTO
├── routes/        # API接口层
├── services/      # 业务逻辑层
├── task/          # 定时任务管理
├── utils/         # 数据源工具包
├── _main_auto_    # 自动化任务入口
└── _main_clean_   # 手动清洗入口
```
## 下载最新数据库
因表结构更新，请在网盘下载最新的数据库
网盘链接： https://pan.baidu.com/s/1qnUFy7dw6O2yxa_0rE_2MQ?pwd=iayk 提取码: iayk

## 下载相关依赖包
迅投Quant不支持苹果系统
```bash
cd panda_data_hub/
pip install requirements.txt -r
```

## 修改配置文件
url: http://localhost:8080/factor/#/datahubsource
配置文件路径：
1. 股票清洗必须早于因子清洗（建议间隔≥5分钟）
2. 推荐清洗时段：交易日19:30后
3. 迅投用户需间隔≥30分钟（需先完成本地数据下载）
4. 修改配置文件后请重启项目以生效
![配置页面](https://zynf-test.oss-cn-shanghai.aliyuncs.com/github/WechatIMG67.jpg)
![配置页面](https://zynf-test.oss-cn-shanghai.aliyuncs.com/github/WechatIMG56.jpg)

## 数据列表
url: http://localhost:8080/factor/#/datahublist
1. 标注为非交易日的日期数据条数为0是正确的
2. 数据差异不为0，说明当日的因子数据清洗存在问题，请重新清洗
![数据列表页面](https://zynf-test.oss-cn-shanghai.aliyuncs.com/github/WechatIMG57.jpg)

## 股票及因子数据清洗
url: http://localhost:8080/factor/#/datahubdataclean
url: http://localhost:8080/factor/#/datahubFactorClean
1. 请先清洗股票数据再清洗因子数据
2. 迅投Quant需先下载数据到本地，所以先下载数据，再清洗数据
![数据清洗页面](https://zynf-test.oss-cn-shanghai.aliyuncs.com/github/WechatIMG69.jpg)

## ❓数据答疑
![微信](https://zynf-test.oss-cn-shanghai.aliyuncs.com/github/WechatIMG75.jpg)
## 🤝贡献

欢迎贡献代码、提出 Issue 或 PR：

Fork 本项目

新建功能分支 git checkout -b feature/AmazingFeature

提交更改 git commit -m 'Add some AmazingFeature'

推送分支 git push origin feature/AmazingFeature

发起 Pull Request

## 🙏 致谢
感谢量化李不白的粉丝们对我们的支持

感谢所有开源社区的贡献者

## 📜许可证

本项目采用 GPLV3 许可证
