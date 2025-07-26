from fastapi import APIRouter, Query
from server.services.user_factor_service import *

_db_handler = DatabaseHandler(config)

router = APIRouter()


@router.get("/hello")
async def hello_route():
    return hello()

@router.get("/user_factor_list")
async def user_factor_list_route(
    user_id: str,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    sort_field: str = Query(default="created_at", description="排序字段，支持updated_at、created_at、return_ratio、sharpe_ratio、maximum_drawdown、IC、IR"),
    sort_order: str = Query(default="desc", description="排序方式，asc升序，desc降序")
):
    """
    获取用户因子列表
    :param user_id: 用户ID
    :param page: 页码，从1开始
    :param page_size: 每页数量，默认10，最大100
    :param sort_field: 排序字段
    :param sort_order: 排序方式，asc或desc
    :return: 因子列表，包含基本信息和性能指标
    """
    return get_user_factor_list(user_id, page, page_size, sort_field, sort_order)

@router.post("/create_factor")
async def create_factor_route(factor: CreateFactorRequest):
    return create_factor(factor)

@router.get("/delete_factor")
async def delete_user_factor_route(factor_id: str):
    return delete_factor(factor_id)

@router.post("/update_factor")
async def update_factor_route(factor: CreateFactorRequest, factor_id: str):
    return update_factor(factor, factor_id)

@router.get("/query_factor")
async def query_factor_route(factor_id: str):
    return query_factor(factor_id)
@router.get("/query_factor_status")
async def query_factor_status_route(factor_id: str):
    return query_factor_status(factor_id)

@router.get("/run_factor")
async def run_factor_route(factor_id: str):

    return run_factor(factor_id,is_thread=True)

@router.get("/query_task_status")
async def query_task_status_route(task_id: str):
    return query_task_status(task_id)

@router.get("/query_factor_excess_chart")
async def query_factor_excess_chart_route(task_id: str):
    return query_factor_excess_chart(task_id)

@router.get("/query_factor_analysis_data")
async def query_factor_analysis_data_route(task_id: str):
    return query_factor_analysis_data(task_id)

@router.get("/query_group_return_analysis")
async def query_group_return_analysis_route(task_id: str):
    return query_group_return_analysis(task_id)

@router.get("/query_ic_decay_chart")
async def query_ic_decay_chart_route(task_id: str):
    return query_ic_decay_chart(task_id)

@router.get("/query_ic_density_chart")
async def query_ic_density_chart_route(task_id: str):
    return query_ic_density_chart(task_id)

@router.get("/query_ic_self_correlation_chart")
async def query_ic_self_correlation_chart_route(task_id: str):
    return query_ic_self_correlation_chart(task_id)

@router.get("/query_ic_sequence_chart")
async def query_ic_sequence_chart_route(task_id: str):
    return query_ic_sequence_chart(task_id)

@router.get("/query_last_date_top_factor")
async def query_last_date_top_factor_route(task_id: str):
 return query_last_date_top_factor(task_id)

@router.get("/query_one_group_data")
async def query_one_group_data_route(task_id: str):
    return query_one_group_data(task_id)

@router.get("/query_rank_ic_decay_chart")
async def query_rank_ic_decay_chart_route(task_id: str):
    return query_rank_ic_decay_chart(task_id)

@router.get("/query_rank_ic_density_chart")
async def query_rank_ic_density_chart_route(task_id: str):
    return query_rank_ic_density_chart(task_id)

@router.get("/query_rank_ic_self_correlation_chart")
async def query_rank_ic_self_correlation_chart_route(task_id: str):
    return query_rank_ic_self_correlation_chart(task_id)

@router.get("/query_rank_ic_sequence_chart")
async def query_rank_ic_sequence_chart_route(task_id: str):
    return query_rank_ic_sequence_chart(task_id)

@router.get("/query_return_chart")
async def query_return_chart_route(task_id: str):
    return query_return_chart(task_id)

@router.get("/query_simple_return_chart")
async def query_simple_return_chart_route(task_id: str):
    return query_simple_return_chart(task_id)

@router.get("/task_logs")
async def get_task_logs_route(task_id: str, last_log_id: str = None):
    return get_task_logs(task_id, last_log_id=last_log_id)
