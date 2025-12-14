from pydantic import BaseModel, ConfigDict
from datetime import datetime
from .item import ItemBase


class Transaction(BaseModel):
    transaction_id: str
    item_id: str
    buyer_id: str
    price: int
    status: str
    shipped_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    item: ItemBase

    model_config = ConfigDict(from_attributes=True)
