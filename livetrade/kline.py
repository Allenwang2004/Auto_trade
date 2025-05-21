import asyncio
import websockets
import json
import datetime
import threading
import nest_asyncio
import time
import queue
import sys
sys.path.append("..")

nest_asyncio.apply()

kline_queue = queue.Queue()

KLINE_STREAM_URL = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"

async def listen_kline():
    async with websockets.connect(KLINE_STREAM_URL) as websocket:
        print("Connected to Binance SPOT 1m Kline stream...")
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                k = data['k']
                is_closed = k['x']
                kline_data = {
                        'datetime': datetime.datetime.fromtimestamp(k['t'] / 1000),
                        'open': float(k['o']),
                        'high': float(k['h']),
                        'low': float(k['l']),
                        'close': float(k['c']),
                        'volume': float(k['v']),
                    }
                if is_closed:
                    kline_queue.put(kline_data)

            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

def start_ws_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(listen_kline())

if __name__ == '__main__':
    threading.Thread(target=start_ws_thread, daemon=True).start()
    while True:
        try:
            kline_data = kline_queue.get(timeout=1)
            print(f"Received Kline data: {kline_data}")
        except queue.Empty:
            continue
        except KeyboardInterrupt:
            break