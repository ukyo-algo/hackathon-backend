# hackathon-backend/app/services/recommend_service.py

from sqlalchemy.orm import Session
from app.db import models
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from janome.tokenizer import Tokenizer

# 日本語解析器 (Janome) の初期化
tokenizer = Tokenizer()


def japanese_tokenizer(text):
    """
    日本語の文章を単語に分割する関数
    例: "これはペンです" -> ["これ", "は", "ペン", "です"]
    """
    if not text:
        return []
    return [token.surface for token in tokenizer.tokenize(text)]


from app.core.config import settings

def get_recommendations(db: Session, item_id: str, limit: int = settings.RECOMMEND_ITEM_COUNT):
    """
    指定された商品(item_id)に似ている商品をDBから探して返す
    """
    # 1. 全商品のデータを取得 (販売中のものだけ)
    # ※ 本番では全件取得は重いので、最新100件や同じカテゴリ内で絞るなどの工夫が必要ですが、
    #    MVPなら全件でOKです。
    items = db.query(models.Item).filter(models.Item.status == "on_sale").all()

    # 商品が少なすぎる場合はレコメンドできないので空リストを返す
    if len(items) < 2:
        return []

    # 2. データフレームの作成
    # 商品IDと、特徴量に使うテキスト（タイトル + 説明文 + カテゴリ）を準備
    item_data = []
    target_index = -1

    for index, item in enumerate(items):
        # テキストを結合: 商品名を3回繰り返して重要度を上げる
        # "商品名 商品名 商品名 カテゴリ 状態 説明文"
        name_weight = f"{item.name} {item.name} {item.name}"
        condition = item.condition or ""
        text_feature = f"{name_weight} {item.category} {condition} {item.description or ''}"
        item_data.append(text_feature)

        if item.item_id == item_id:
            target_index = index

    # ターゲット商品が「販売中」リストになかった場合（売り切れなど）
    if target_index == -1:
        # 売り切れ商品も含めて再検索するか、空を返す。今回は空を返す。
        return []

    # 3. TF-IDF でテキストをベクトル化 (AIの計算用データに変換)
    # tokenizer=japanese_tokenizer を指定して日本語に対応させる
    vectorizer = TfidfVectorizer(tokenizer=japanese_tokenizer)
    tfidf_matrix = vectorizer.fit_transform(item_data)

    # 4. コサイン類似度を計算
    # 全商品 vs 全商品の類似度行列を作る
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

    # 5. ターゲット商品に似ている順にソート
    # target_index の商品の類似度スコアを取得
    sim_scores = list(enumerate(cosine_sim[target_index]))

    # スコアが高い順にソート (key=lambda x: x[1], reverse=True)
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # 6. 上位の商品を取得 (自分自身 [0] は除くので [1:limit+1])
    recommended_items = []
    for i, score in sim_scores[1 : limit + 1]:
        # 類似度が0（全く関係ない）商品は除外しても良いが、今回はそのまま出す
        recommended_items.append(items[i])

    return recommended_items
