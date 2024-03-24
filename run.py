import asyncio
import json
import ssl
import time
import uuid
import random
from loguru import logger
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent
import websockets.exceptions

user_agent = UserAgent()
random_user_agent = user_agent.random

async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(f"Connecting to {socks5_proxy} with device ID: {device_id}")

    try:
        await asyncio.sleep(random.uniform(0.1, 1))  # Introduce slight delay
        custom_headers = {"User-Agent": random_user_agent}
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        uri = "wss://proxy.wynd.network:4650/"
        server_hostname = "proxy.wynd.network"
        proxy = Proxy.from_url(socks5_proxy)

        async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                 extra_headers=custom_headers) as websocket:
            async def send_ping():
                try:
                    while True:
                        send_message = json.dumps(
                            {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                        logger.debug(send_message)
                        await websocket.send(send_message)
                        await asyncio.sleep(20)
                except websockets.exceptions.ConnectionClosedError:
                    pass

            await asyncio.sleep(1)  # Introduce slight delay before starting tasks
            asyncio.create_task(send_ping())

            while True:
                response = await websocket.recv()
                message = json.loads(response)
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
    except Exception as e:
        logger.error(f"Error connecting to {socks5_proxy}: {e}")

async def worker(user_ids, socks5_proxy_list):
    tasks = []
    for user_id in user_ids:
        for proxy in socks5_proxy_list:
            tasks.append(asyncio.create_task(connect_to_wss(proxy, user_id)))
    await asyncio.gather(*tasks)

async def main():
    user_ids = input('Please enter your user IDs (comma-separated): ').split(',')
    with open('proxy_list.txt', 'r') as file:
        socks5_proxy_list = file.read().splitlines()

    # Number of workers
    num_workers = 8
    
    # Adjust chunk size based on the length of user_ids
    chunk_size = max(len(user_ids) // num_workers, 1)
    
    # Split user_ids into chunks for each worker
    user_id_chunks = [user_ids[i:i + chunk_size] for i in range(0, len(user_ids), chunk_size)]
    
    # Start workers
    worker_tasks = [asyncio.create_task(worker(user_id_chunk, socks5_proxy_list)) for user_id_chunk in user_id_chunks]
    await asyncio.gather(*worker_tasks)

if __name__ == '__main__':
    asyncio.run(main())
