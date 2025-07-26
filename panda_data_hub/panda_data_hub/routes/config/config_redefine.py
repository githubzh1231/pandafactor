from fastapi import APIRouter
from panda_common.config import config
from panda_data_hub.models.config_request import ConfigRequest
from panda_data_hub.services.config.data_source_config_redefine_service import DataSourceConfigRedefine

router = APIRouter()

@router.post('/config_redefine_data_source')
async def config_redefine_data_source(requst:ConfigRequest):
    """ 修改配置文件 """
    service = DataSourceConfigRedefine(config)
    service.data_source_config_redefine(requst)
    return {"message": "配置文件修改成功"}


@router.get('/get_datahub_resource')
async def config_redefine_data_source():
    service = DataSourceConfigRedefine(config)
    return service.get_datahub_resource()


