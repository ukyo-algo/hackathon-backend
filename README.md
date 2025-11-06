# Delivery Simulator (Python + React)

- 左: Three.js(R3F)で3D表示（建物・車・ドローン）
- 右: 配送需要レート(荷物/分)を操作するパネル
- Python(FastAPI)のローカルサーバでシミュレーションし、WebSocketでフロントに配信

## クイックスタート

### 1) バックエンド
```bash
cd backend
uv venv
.venv\Scripts\activate
# macOS/Linuxの場合） source .venv/bin/activate
uv sync
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 2) フロントエンド
別ターミナルで:
```bash
cd frontend
npm install
npm run dev
```
ブラウザで http://127.0.0.1:5173 を開きます。

## 使い方
- 右パネルの各建物のスライダーは「1分あたりの配送需要」を表します。
- 値を上げると、その建物の保留キューが増え、車/ドローンがDepotから往復します。
- 3D上では保留キューが多い建物ほどビルが高く、赤っぽく表示されます。
- 車は緑、ドローンは黄色で表示されます。
