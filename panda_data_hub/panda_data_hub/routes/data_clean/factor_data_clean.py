from fastapi import APIRouter, BackgroundTasks
from panda_common.config import config
from typing import Dict

from panda_data_hub.services.rq_factor_clean_pro_service import FactorCleanerProService
from panda_data_hub.services.ts_factor_clean_pro_service import FactorCleanerTSProService
# from panda_data_hub.services.xt_factor_clean_pro_service import FactorCleanerXTProService

router = APIRouter()

@router.get('/upsert_factor_final')
async def upsert_factor(start_date: str, end_date: str, background_tasks: BackgroundTasks):
    global current_progress
    current_progress = 0  # 重置进度

    data_source = config['DATAHUBSOURCE']

    def progress_callback(progress: int):
        global current_progress
        current_progress = progress

    if data_source == 'ricequant':
        rice_quant_service = FactorCleanerProService(config)
        rice_quant_service.set_progress_callback(progress_callback)
        background_tasks.add_task(
            rice_quant_service.clean_history_data,
            start_date,
            end_date
        )
    elif data_source == 'tushare':
        tushare_service = FactorCleanerTSProService(config)
        tushare_service.set_progress_callback(progress_callback)
        background_tasks.add_task(
            tushare_service.clean_history_data,
           start_date,
            end_date)
    # elif data_source == 'xuntou':
    #     xt_quant_service = FactorCleanerXTProService(config)
    #     xt_quant_service.set_progress_callback(progress_callback)
    #     background_tasks.add_task(
    #         xt_quant_service.factor_history_clean,
    #         start_date,
    #         end_date
    #     )


    return {"message": "Factor data cleaning started by {data_source}"}

@router.get('/get_progress_factor_final')
async def get_progress() -> Dict[str, int]:
    """获取当前数据清洗进度"""
    return {"progress": current_progress}

