import asyncio
import logging
import json
from urllib.parse import urlparse, urlunparse
from aiohttp import web, ClientSession, WSMsgType

# 設定
LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 9222
TARGET_HOST = 'localhost'
TARGET_PORT = 9223

TARGET_BASE_URL = f'http://{TARGET_HOST}:{TARGET_PORT}'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def proxy_http(request):
    """通常のHTTPリクエストをプロキシする"""
    original_host = request.headers.get('Host')
    target_url = f"{TARGET_BASE_URL}{request.path_qs}"

    # ターゲットへのリクエストヘッダーを準備
    forward_headers = dict(request.headers)
    forward_headers['Host'] = f'{TARGET_HOST}:{TARGET_PORT}'

    async with ClientSession() as session:
        try:
            async with session.request(
                request.method,
                target_url,
                headers=forward_headers,
                data=await request.read()
            ) as resp:
                content = await resp.read()
                # ヘッダーはミュータブルなdictにコピーする
                response_headers = dict(resp.headers)

                # /json/version, /json, /json/list の場合、レスポンスを書き換える
                if request.path in ('/json/version', '/json', '/json/list') and resp.status == 200 and original_host:
                    try:
                        data = json.loads(content)

                        # /json の場合はリスト内の各要素を処理
                        items = data if isinstance(data, list) else [data]

                        for item in items:
                            if 'webSocketDebuggerUrl' in item:
                                ws_url_parts = urlparse(item['webSocketDebuggerUrl'])
                                new_ws_url_parts = ws_url_parts._replace(netloc=original_host)
                                item['webSocketDebuggerUrl'] = urlunparse(new_ws_url_parts)
                                logging.info(f"Rewrote webSocketDebuggerUrl for host: {original_host}")

                        content = json.dumps(data).encode('utf-8')
                        response_headers['Content-Length'] = str(len(content))

                    except (json.JSONDecodeError, KeyError) as e:
                        logging.warning(f"Failed to modify {request.path} response: {e}")

                # aiohttpに再圧縮させないようにContent-Encodingを削除
                if 'Content-Encoding' in response_headers:
                    del response_headers['Content-Encoding']

                # Transfer-Encodingヘッダも削除
                if 'Transfer-Encoding' in response_headers:
                    del response_headers['Transfer-Encoding']

                response = web.Response(
                    body=content,
                    status=resp.status,
                    headers=response_headers
                )
                return response
        except Exception as e:
            logging.error(f"Error proxying HTTP request: {e}")
            return web.Response(status=502, text="Bad Gateway")


async def proxy_websocket(request):
    """WebSocket接続をプロキシする"""
    # クライアントからのWebSocket接続を準備
    ws_server = web.WebSocketResponse()
    await ws_server.prepare(request)

    # ターゲットへのWebSocket接続を準備
    target_url = f"ws://{TARGET_HOST}:{TARGET_PORT}{request.path_qs}"
    headers = dict(request.headers)
    headers['Host'] = f'{TARGET_HOST}:{TARGET_PORT}'

    async with ClientSession() as session:
        try:
            async with session.ws_connect(target_url, headers=headers) as ws_client:
                logging.info("WebSocket connection established.")

                # 接続状態を追跡するためのイベント
                shutdown_event = asyncio.Event()

                async def forward_to_client():
                    """ターゲット -> プロキシ -> クライアント"""
                    try:
                        async for msg in ws_client:
                            if shutdown_event.is_set():
                                break
                            if msg.type == WSMsgType.TEXT:
                                if not ws_server.closed:
                                    await ws_server.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                if not ws_server.closed:
                                    await ws_server.send_bytes(msg.data)
                            elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                                break
                    except Exception as e:
                        logging.debug(f"Forward to client error: {e}")
                    finally:
                        shutdown_event.set()
                        logging.info("Forward to client finished.")


                async def forward_to_target():
                    """クライアント -> プロキシ -> ターゲット"""
                    try:
                        async for msg in ws_server:
                            if shutdown_event.is_set():
                                break
                            if msg.type == WSMsgType.TEXT:
                                if not ws_client.closed:
                                    await ws_client.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                if not ws_client.closed:
                                    await ws_client.send_bytes(msg.data)
                            elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                                break
                    except Exception as e:
                        logging.debug(f"Forward to target error: {e}")
                    finally:
                        shutdown_event.set()
                        logging.info("Forward to target finished.")

                # 双方向のメッセージ転送を並行して実行
                # どちらかが終了したら両方を終了させる
                tasks = [
                    asyncio.create_task(forward_to_client()),
                    asyncio.create_task(forward_to_target())
                ]
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                # 残りのタスクをキャンセル
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        except Exception as e:
            logging.error(f"Error proxying WebSocket: {e}")
        finally:
            if not ws_server.closed:
                await ws_server.close()
            logging.info("WebSocket connection closed.")

    return ws_server


async def handle_request(request):
    """HTTPとWebSocketのリクエストを振り分ける"""
    # WebSocketへのアップグレードリクエストか判定
    if 'Upgrade' in request.headers and request.headers.get('Upgrade', '').lower() == 'websocket':
        return await proxy_websocket(request)
    else:
        return await proxy_http(request)

async def main():
    app = web.Application()
    app.router.add_route('*', '/{path:.*}', handle_request)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, LISTEN_HOST, LISTEN_PORT)
    await site.start()
    logging.info(f"CDP reverse proxy started on http://{LISTEN_HOST}:{LISTEN_PORT}")
    # サーバーを永続的に実行
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Proxy server shutting down.")
