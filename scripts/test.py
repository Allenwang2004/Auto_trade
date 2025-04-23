import sys
sys.path.append('..')
import backtrader as bt
import pandas as pd
import quantstats as qs
import matplotlib.pyplot as plt
import datetime

# === 策略一：支援多空方向的 MACD 策略（使用 bracket order） ===
class MACDStrategy(bt.Strategy):
    params = (
        ('limit', 0.01),        # 下單折扣
        ('limdays', 3),         # 主單有效天數
        ('limdays2', 3),        # 子單有效天數
    )

    def __init__(self):
        macd = bt.indicators.MACD(self.data.close)
        self.crossover = bt.indicators.CrossOver(macd.macd, macd.signal)
        self.trade_records = []
        self.orefs = []  # 記錄掛單參考

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            if order.isbuy():
                print(f"[ORDER BUY] {order.getstatusname()} @ {order.executed.price}")
            elif order.issell():
                print(f"[ORDER SELL] {order.getstatusname()} @ {order.executed.price}")

    def notify_trade(self, trade):
        if trade.isopen:
            print(f"[TRADE OPEN]")
        elif trade.isclosed:
            self.orefs = []  # 清空掛單參考
            print(f"[TRADE EXIT] , PnL: {trade.pnl:.2f}")
            self.trade_records.append({
                'datetime': self.data.datetime.date(0).isoformat(),
                'pnl': trade.pnl,
            })

    def next(self):
        if self.orefs:
            return  # 尚有掛單在等待成交，不再下單

        dt = self.data.datetime.date(0).isoformat()
        close = self.data.close[0]

        if not self.position:
            if self.crossover > 0:
                # === 金叉 → 做多 ===
                p1 = close
                p2 = p1 - 0.02 * close  # 停損
                p3 = p1 + 0.02 * close  # 止盈

                valid1 = datetime.timedelta(self.p.limdays)
                valid2 = valid3 = datetime.timedelta(self.p.limdays2)

                o1 = self.buy(exectype=bt.Order.Limit,
                            price=round(p1, 2),
                            valid=valid1,
                            size=1,
                            transmit=False)
                o2 = self.sell(exectype=bt.Order.Stop,
                            price=round(p2, 2),
                            valid=valid2,
                            size=1,
                            parent=o1,
                            transmit=False)
                o3 = self.sell(exectype=bt.Order.Limit,
                            price=round(p3, 2),
                            valid=valid3,
                            size=1,
                            parent=o1,
                            transmit=True)

                print(f"{dt}: Bracket LONG placed: Buy@{round(p1,2)} / SL@{round(p2,2)} / TP@{round(p3,2)}")
                self.orefs = [o1.ref, o2.ref, o3.ref]

            elif self.crossover < 0:
                # === 死叉 → 做空 ===
                p1 = close
                p2 = p1 + 0.02 * close  # 停損
                p3 = p1 - 0.02 * close  # 止盈

                valid1 = datetime.timedelta(self.p.limdays)
                valid2 = valid3 = datetime.timedelta(self.p.limdays2)

                o1 = self.sell(exectype=bt.Order.Limit,
                            price=round(p1, 2),
                            valid=valid1,
                            size=1,
                            transmit=False)
                o2 = self.buy(exectype=bt.Order.Stop,
                            price=round(p2, 2),
                            valid=valid2,
                            size=1,
                            parent=o1,
                            transmit=False)
                o3 = self.buy(exectype=bt.Order.Limit,
                            price=round(p3, 2),
                            valid=valid3,
                            size=1,
                            parent=o1,
                            transmit=True)

                print(f"{dt}: Bracket SHORT placed: Sell@{round(p1,2)} / SL@{round(p2,2)} / TP@{round(p3,2)}")
                self.orefs = [o1.ref, o2.ref, o3.ref]

# === 策略二：RSI過熱策略（使用 bracket order） ===
class RSIStrategy(bt.Strategy):
    params = (
        ('limdays', 3),
        ('limdays2', 3),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.trade_records = []
        self.orefs = []

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            if order.isbuy():
                print(f"[RSI ORDER BUY] {order.getstatusname()} @ {order.executed.price}")
            elif order.issell():
                print(f"[RSI ORDER SELL] {order.getstatusname()} @ {order.executed.price}")

    def notify_trade(self, trade):
        if trade.isopen:
            print(f"[RSI TRADE OPEN]")
        elif trade.isclosed:
            self.orefs = []
            print(f"[RSI TRADE EXIT] , PnL: {trade.pnl:.2f}")
            self.trade_records.append({
                'datetime': self.data.datetime.date(0).isoformat(),
                'pnl': trade.pnl,
            })

    def next(self):
        if self.orefs:
            return

        dt = self.data.datetime.date(0).isoformat()
        close = self.data.close[0]

        if not self.position:
            if self.rsi < 30:
                p1 = close
                p2 = p1 - 0.02 * close
                p3 = p1 + 0.02 * close

                valid1 = datetime.timedelta(self.p.limdays)
                valid2 = valid3 = datetime.timedelta(self.p.limdays2)

                o1 = self.buy(exectype=bt.Order.Limit,
                              price=round(p1, 2),
                              valid=valid1,
                              size=1,
                              transmit=False)
                o2 = self.sell(exectype=bt.Order.Stop,
                               price=round(p2, 2),
                               valid=valid2,
                               size=1,
                               parent=o1,
                               transmit=False)
                o3 = self.sell(exectype=bt.Order.Limit,
                               price=round(p3, 2),
                               valid=valid3,
                               size=1,
                               parent=o1,
                               transmit=True)

                print(f"{dt}: RSI Bracket order placed: Buy@{round(p1,2)} / SL@{round(p2,2)} / TP@{round(p3,2)}")
                self.orefs = [o1.ref, o2.ref, o3.ref]

# === 載入資料並篩選繪圖期間 ===
dataframe = pd.read_csv('/Users/coconut/Backtrade/datas/BTCUSDT_futures_4h_from_20210101.csv', index_col=0, parse_dates=True)
dataframe = dataframe[(dataframe.index >= '2021-01-01') & (dataframe.index <= '2025-01-31')]
data = bt.feeds.PandasData(dataname=dataframe)

# === 建立 Cerebro，加入兩個策略與分析器 ===
cerebro = bt.Cerebro()
cerebro.adddata(data)
cerebro.addstrategy(MACDStrategy)
cerebro.addstrategy(RSIStrategy)
cerebro.broker.setcash(1000000)
cerebro.broker.setcommission(commission=0.002)
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')

# === 執行回測 ===
results = cerebro.run()

# === 擷取每筆交易記錄為 DataFrame ===
trades_macd = pd.DataFrame(results[0].trade_records)
trades_rsi = pd.DataFrame(results[1].trade_records)

trades_macd.to_csv("macd_trades.csv", index=False)
trades_rsi.to_csv("rsi_trades.csv", index=False)

print("MACD 策略交易記錄：")
print(trades_macd)
print("\nRSI 策略交易記錄：")
print(trades_rsi)

# === 合併並計算每日報酬 ===
all_trades = pd.concat([trades_macd, trades_rsi])
all_trades['datetime'] = pd.to_datetime(all_trades['datetime'])
all_trades.set_index('datetime', inplace=True)

# 損益彙總 → 報酬率
daily_returns = all_trades.groupby(all_trades.index.date)['pnl'].sum()
daily_returns = pd.Series(daily_returns)
daily_returns.index = pd.to_datetime(daily_returns.index)
daily_returns = daily_returns.sort_index()
returns = daily_returns / 1_000_000

# QuantStats 報表
qs.extend_pandas()
returns = returns.asfreq('D').fillna(0)
qs.reports.basic(returns)
plt.show()

# 畫出指定範圍圖
cerebro.plot(start=datetime.date(2021, 1, 1), end=datetime.date(2021, 4, 11))
