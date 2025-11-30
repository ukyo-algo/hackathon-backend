from pydantic import BaseModel, ConfigDict
from datetime import datetime


class Transaction(BaseModel):
    transaction_id: str
    item_id: str
    buyer_id: str
    price: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
