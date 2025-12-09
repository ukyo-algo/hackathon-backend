# 1. ベースイメージ
FROM python:3.11-slim

# 2. ログのバッファリングを無効
ENV PYTHONUNBUFFERED=1

# 3. 作業ディレクトリの設定
WORKDIR /app

# 4. 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. ★重要: Pythonにアプリケーションのルートを教える
ENV PYTHONPATH=/app

# 6. アプリケーションコードのコピー
# 現在のディレクトリ(.)を コンテナの /app にコピー
COPY . .

# 7. 起動コマンド
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}