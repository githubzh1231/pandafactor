from pydantic import BaseModel


class FactorsRequest(BaseModel):
    symbols: list
    factors: list
    start_date: str
    end_date: str