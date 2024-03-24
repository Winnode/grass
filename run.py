import asyncio
import aiohttp
import ssl
import json
import time
import uuid
import threading
from loguru import logger
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent

# Initialize logger
logger.add("output.log", rotation="10 MB")

# Initialize user agent
user_agent = UserAgent()
random_user_agent = user_agent.random

# Configuration
MAX_RETRIES = 3
RETRY_DELAY = 5
PING_INTERVAL = 20

async def send_ping(websocket):
    while True:
        try:
            send_message = json.dumps(
                {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
            logger.debug(send_message)
            await websocket.send(send_message)
            await asyncio.sleep(PING_INTERVAL)
        except aiohttp.ClientError as e:
            logger.error(f"Error sending ping: {e}")
            break

async def handle_auth(websocket, device_id, user_id, custom_headers):
    while True:
        try:
            response = await websocket.recv()
            message = json.loads(response)
            logger.info(message)
            if message.get("action") == "AUTH":
                auth_response = {
                    "id": message["id"],
                    "origin_action": "AUTH",
                    "result": {
                        "browser_id": device_id,
                        "user_id": user_id,
                        "user_agent": custom_headers['User-Agent'],
                        "timestamp": int(time.time()),
                        "device_type": "extension",
                        "version": "3.3.2"
                    }
                }
                logger.debug(auth_response)
                await websocket.send(json.dumps(auth_response))

            elif message.get("action") == "PONG":
                pong_response = {"id": message["id"], "origin_action": "PONG"}
                logger.debug(pong_response)
                await websocket.send(json.dumps(pong_response))
        except aiohttp.ClientError as e:
            logger.error(f"Error handling auth response: {e}")
            break

async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(f"Connecting to {socks5_proxy} with device ID: {device_id}")
    custom_headers = {
        "User-Agent": random_user_agent
    }
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    uri = "wss://proxy.wynd.network:4650/"
    server_hostname = "proxy.wynd.network"
    proxy = Proxy.from_url(socks5_proxy)

    retries = 0
    while retries < MAX_RETRIES:
        try:
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                await asyncio.gather(
                    send_ping(websocket),
                    handle_auth(websocket, device_id, user_id, custom_headers)
                )
        except asyncio.CancelledError:
            logger.info("Task was cancelled")
            break
        except (aiohttp.ClientError, websockets.exceptions.ConnectionClosedError) as e:
            logger.error(f"Failed to connect to {socks5_proxy}: {e}. Retrying...")
            await asyncio.sleep(RETRY_DELAY)
            retries += 1
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            break

async def main():
    _user_ids = input('Please Enter your user IDs (comma-separated): ').split(',')
    with open('proxy_list.txt', 'r') as file:
        socks5_proxy_list = file.read().splitlines()

    while True:
        tasks = []
        for user_id in _user_ids:
            for proxy in socks5_proxy_list:
                tasks.append(asyncio.create_task(connect_to_wss(proxy, user_id)))

        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Exiting...")
