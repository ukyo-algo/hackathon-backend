# hackathon-backend/app/api/v1/endpoints/items.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.db.database import get_db
from app.db import models
from app.schemas import item as item_schema
from app.schemas import transaction as transaction_schema
from app.schemas import comment as comment_schema

from app.api.v1.endpoints.users import get_current_user
from app.services import recommend_service


router = APIRouter()


@router.get(
    "",  # /api/v1/items のルート
    response_model=List[item_schema.Item],  # [Item, Item, ...] のリストで返る
    summary="商品一覧取得",
)
def get_items(db: Session = Depends(get_db)):  # DBセッションを取得
    """
    全商品一覧（販売中）を新着順で取得します。

    N+1問題を回避するため、出品者情報(seller)もJOINして取得します。
    """
    items = (
        db.query(
            models.Item
        )  # Itemクラス内のtablename変数を元に，参照したいdbを指定(今回はitemsテーブルを参照することになる)
        .options(joinedload(models.Item.seller))  # relationship("seller") をJOIN
        .filter(models.Item.status == "on_sale")
        .order_by(models.Item.created_at.desc())
        .all()
    )

    return items


@router.get("/{item_id}", response_model=item_schema.Item)
def get_item(item_id: str, db: Session = Depends(get_db)):
    item = (
        db.query(models.Item)
        .options(
            joinedload(models.Item.seller),
            joinedload(models.Item.comments).joinedload(
                models.Comment.user
            ),  # コメントと投稿者
        )
        .filter(models.Item.item_id == item_id)
        .first()
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    item.like_count = len(item.likes)  # models.Itemにlikesリレーションがあれば動作

    return item


@router.post(
    "",  # /api/v1/items のルート
    response_model=item_schema.Item,
    summary="新規商品出品",
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    item_in: item_schema.ItemCreate,  # 入力データ
    db: Session = Depends(get_db),
    # ダミー認証関数で出品者情報を取得
    current_user: models.User = Depends(get_current_user),
):
    """
    ログイン中のユーザーとして新しい商品を出品します。
    """
    # ItemCreateスキーマのデータと、current_userから取得したseller_idを使って、Itemモデルのインスタンスを作成
    new_item = models.Item(
        **item_in.model_dump(),  # ItemCreateの全フィールド（name, category, brand, priceなど）を展開して渡す
        seller_id=current_user.firebase_uid,  # 認証済みユーザーのIDを出品者として設定
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    # フロントエンドのスキーマ(Item)に合うように、User情報もロードする
    # ※ Item.seller リレーションを通じて自動的にロードされるはずですが、明示的にリロードすることで確実にする
    db.refresh(new_item, attribute_names=["seller"])

    return new_item


@router.post(
    "/{item_id}/buy",
    response_model=transaction_schema.Transaction,
    summary="商品の購入（取引成立）",
    status_code=status.HTTP_201_CREATED,
)
def buy_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),  # 購入者
):
    """
    指定された商品を購入します。
    - 商品のステータスを 'sold' に変更
    - Transaction レコードを作成
    """
    # 1. 商品を取得（排他制御は今回は省略）
    item = db.query(models.Item).filter(models.Item.item_id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="商品が見つかりません")

    # 2. バリデーション
    if item.status != "on_sale":
        raise HTTPException(status_code=400, detail="この商品は既に売り切れています")

    if item.seller_id == current_user.firebase_uid:
        raise HTTPException(status_code=400, detail="自分の商品は購入できません")

    # 3. ステータス更新
    item.status = "sold"

    # 4. トランザクション作成
    transaction = models.Transaction(
        item_id=item.item_id, buyer_id=current_user.firebase_uid, price=item.price
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction


@router.get(
    "/{item_id}/recommend",
    response_model=List[item_schema.Item],
    summary="おすすめ商品の取得（レコメンド）",
)
def get_recommend_items(item_id: str, db: Session = Depends(get_db)):
    """
    指定された商品に類似したおすすめ商品を取得します。
    商品説明文やカテゴリの類似度（TF-IDF + Cosine Similarity）に基づきます。
    """
    # レコメンドサービスを呼び出す
    recommended_items = recommend_service.get_recommendations(db, item_id, limit=3)

    return recommended_items


@router.post("/{item_id}/like", summary="いいね！のトグル（登録/解除）")
def toggle_like(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 既にいいねしているか確認
    existing_like = (
        db.query(models.Like)
        .filter(
            models.Like.item_id == item_id,
            models.Like.user_id == current_user.firebase_uid,
        )
        .first()
    )

    if existing_like:
        # あれば削除（いいね解除）
        db.delete(existing_like)
        db.commit()
        return {"status": "unliked"}
    else:
        # なければ作成（いいね登録）
        new_like = models.Like(item_id=item_id, user_id=current_user.firebase_uid)
        db.add(new_like)
        db.commit()
        return {"status": "liked"}


@router.post(
    "/{item_id}/comments", response_model=comment_schema.Comment, summary="コメント投稿"
)
def create_comment(
    item_id: str,
    comment_in: comment_schema.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = db.query(models.Item).filter(models.Item.item_id == item_id).first()
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")

    new_comment = models.Comment(
        item_id=item_id, user_id=current_user.firebase_uid, content=comment_in.content
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return new_comment
