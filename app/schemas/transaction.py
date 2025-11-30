from pydantic import BaseModel, ConfigDict
from datetime import datetime
from .item import ItemBase


class Transaction(BaseModel):
    transaction_id: str
    item_id: str
    buyer_id: str
    price: int
    created_at: datetime
    item: ItemBase

    model_config = ConfigDict(from_attributes=True)
