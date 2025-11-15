# Chromium with NoVNC

|[English](README.md)|日本語|

![screenshot](screenshot.png "screenshot")

- Dockerコンテナ内でChromiumブラウザを実行し、noVNCを使用してブラウザからコンテナ内のChromiumブラウザにリモートアクセスできます
- LLMを使用したWebスクレイピングや自動化タスクで使うブラウザを、サーバ上で動かすのに便利です


## 実行方法

```
docker compose up
```

http://localhost:9220 にアクセスしてください。


## 使用例: borwser-use から使用する

```python
browser_session = BrowserSession(
    headless=False,
    window_size={"width": 1280, "height": 1024},
    viewport={"width": 1248, "height": 895},
    cdp_url="http://localhost:9222",
    keep_alive=True
)
```
