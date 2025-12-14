# hackathon-backend/app/api/v1/endpoints/transactions.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func

from app.db.database import get_db
from app.db import models
from app.schemas import transaction as transaction_schema
from app.api.v1.endpoints.users import get_current_user


router = APIRouter()


@router.post(
    "/{transaction_id}/ship",
    response_model=transaction_schema.Transaction,
    summary="発送しました（出品者用）",
)
def ship_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tx = (
        db.query(models.Transaction)
        .options(joinedload(models.Transaction.item))
        .filter(models.Transaction.transaction_id == transaction_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="取引が見つかりません")
    if not tx.item:
        raise HTTPException(status_code=400, detail="取引に紐づく商品が不明です")
    if tx.item.seller_id != current_user.firebase_uid:
        raise HTTPException(status_code=403, detail="出品者のみ操作できます")
    if tx.status != "pending_shipment":
        raise HTTPException(status_code=400, detail="現在の状態では発送にできません")

    tx.status = "in_transit"
    tx.shipped_at = func.now()

    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.post(
    "/{transaction_id}/complete",
    response_model=transaction_schema.Transaction,
    summary="受け取りました（購入者用）",
)
def complete_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tx = (
        db.query(models.Transaction)
        .options(joinedload(models.Transaction.item))
        .filter(models.Transaction.transaction_id == transaction_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="取引が見つかりません")
    if tx.buyer_id != current_user.firebase_uid:
        raise HTTPException(status_code=403, detail="購入者のみ操作できます")
    if tx.status != "in_transit":
        raise HTTPException(status_code=400, detail="配送中ではありません")

    tx.status = "completed"
    tx.completed_at = func.now()

    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx
