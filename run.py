import asyncio
import json
import ssl
import time
import uuid
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent
from loguru import logger

user_agent = UserAgent()
random_user_agent = user_agent.random


async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(device_id)

    while True:
        try:
            await asyncio.sleep(1)  

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
                    while True:
                        send_message = json.dumps(
                            {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                        try:
                            await websocket.send(send_message)
                            logger.debug(send_message)
                        except Exception as e:
                            pass
                        await asyncio.sleep(2)

                asyncio.create_task(send_ping())

                while True:
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
                        try:
                            await websocket.send(json.dumps(auth_response))
                            logger.debug(auth_response)
                        except Exception as e:
                            pass

                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        try:
                            await websocket.send(json.dumps(pong_response))
                            logger.debug(pong_response)
                        except Exception as e:
                            pass

        except Exception as e:
            pass


async def main():

    user_ids = input('Please Enter your user IDs separated by comma: ').split(',')

    with open('proxy_list.txt', 'r') as file:
        socks5_proxy_list = file.read().splitlines()


    tasks = [asyncio.ensure_future(connect_to_wss(proxy, user_id.strip())) for user_id in user_ids for proxy in
             socks5_proxy_list]
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
