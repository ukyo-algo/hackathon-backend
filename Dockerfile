# 1. ベースイメージを推奨される「python:3.11-slim」に変更
FROM python:3.11-slim

# 2. ログのバッファリングを無効 (Cloud Loggingのために推奨)
ENV PYTHONUNBUFFERED=1

# 作業ディレクトリを設定
WORKDIR /src

# requirements.txt を先にコピー (レイヤーキャッシュのため)
COPY requirements.txt ./

# 3. 「--no-cache-dir」を追加 (イメージサイズ削減)
RUN pip install --no-cache-dir -r requirements.txt

# 4. アプリケーションコードをすべてコピー
# (このDockerfileはプロジェクトルートに置くことを想定)
# 4. アプリケーションコードをすべてコピー
COPY . .

# 5. 起動コマンドを「api.main」から「app.main」に修正
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT