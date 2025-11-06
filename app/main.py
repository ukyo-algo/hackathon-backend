from fastapi import FastAPI

app = FastAPI()


@app.get("/api/v1/ping")
def ping():
    """
    疎通確認用のエンドポイント.
    """
    return {"status": "success"}
