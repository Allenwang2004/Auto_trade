import asyncio
import websockets
import json
import datetime
import queue
import threading
import nest_asyncio
import time
import sys
sys.path.append("..")
import backtrader as bt

nest_asyncio.apply()

# 全域 Queue 給 backtrader 使用
kline_queue = queue.Queue()

# Binance 現貨 WebSocket (1 分鐘 K 線)
KLINE_STREAM_URL = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"

# WebSocket 接收函數
async def listen_kline():
    async with websockets.connect(KLINE_STREAM_URL) as websocket:
        print("Connected to Binance 1m Kline stream...")
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                print(f"Received message: {message}")
                k = data['k']
                if k['x']:  # 收盤時才推入
                    kline_data = {
                        'datetime': datetime.datetime.fromtimestamp(k['t'] / 1000),
                        'open': float(k['o']),
                        'high': float(k['h']),
                        'low': float(k['l']),
                        'close': float(k['c']),
                        'volume': float(k['v']),
                    }
                    kline_queue.put(kline_data)
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

# 開一個 thread 給 WebSocket
def start_ws_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(listen_kline())

# 自定資料來源：從 queue 餵給 backtrader
class BinanceLiveKlineFeed(bt.feeds.DataBase):
    lines = ('open', 'high', 'low', 'close', 'volume')

    def _load(self):
        try:
            data = kline_queue.get_nowait()
            self.lines.datetime[0] = bt.date2num(data['datetime'])
            self.lines.open[0] = data['open']
            self.lines.high[0] = data['high']
            self.lines.low[0] = data['low']
            self.lines.close[0] = data['close']
            self.lines.volume[0] = data['volume']
            return True
        except queue.Empty:
            return None  # 馬上交還控制權給 Backtrader

# 簡單策略：每根收盤輸出一次價格
class PrintStrategy(bt.Strategy):
    def next(self):
        dt = self.data.datetime.datetime(0)
        close = self.data.close[0]
        print(f"[{dt}] 🔔 Close: {close}")

# 主程式
if __name__ == '__main__':
    threading.Thread(target=start_ws_thread, daemon=True).start()

    cerebro = bt.Cerebro()
    cerebro.addstrategy(PrintStrategy)
    cerebro.adddata(BinanceLiveKlineFeed())
    print("Starting Backtrader...")
    cerebro.run()

