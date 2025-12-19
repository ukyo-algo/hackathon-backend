# hackathon-backend/app/api/v1/endpoints/transactions.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func

from app.db.database import get_db
from app.db import models
from app.schemas import transaction as transaction_schema
from app.api.v1.endpoints.users import get_current_user


router = APIRouter()


@router.get(
    "",
    response_model=list[transaction_schema.Transaction],
    summary="取引一覧（ロール・ステータスでフィルタ）",
)
def list_transactions(
    role: str,  # 'seller' | 'buyer'
    status: str | None = None,  # 'pending_shipment' | 'in_transit' | 'completed' | None
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Transaction).options(joinedload(models.Transaction.item))

    if role == "seller":
        q = q.join(
            models.Item, models.Transaction.item_id == models.Item.item_id
        ).filter(models.Item.seller_id == current_user.firebase_uid)
    elif role == "buyer":
        q = q.filter(models.Transaction.buyer_id == current_user.firebase_uid)
    else:
        raise HTTPException(
            status_code=400, detail="roleは'seller'または'buyer'を指定してください"
        )

    if status:
        q = q.filter(models.Transaction.status == status)

    txs = (
        q.order_by(models.Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return txs


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

    # 購入者に発送通知を送信
    buyer = db.query(models.User).filter(models.User.firebase_uid == tx.buyer_id).first()
    if buyer:
        notification = models.Notification(
            user_id=buyer.id,
            type="shipment",
            title="商品が発送されました！",
            message=f"「{tx.item.name}」が発送されました。お届けまでしばらくお待ちください。",
            link="/buyer",
        )
        db.add(notification)
        db.commit()

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

    # 出品者に取引完了通知を送信
    if tx.item and tx.item.seller:
        notification = models.Notification(
            user_id=tx.item.seller.id,
            type="transaction_complete",
            title="取引が完了しました！",
            message=f"「{tx.item.name}」の取引が完了しました。ありがとうございました！",
            link="/seller",
        )
        db.add(notification)
        db.commit()

    return tx
