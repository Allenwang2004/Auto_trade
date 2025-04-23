import sys
sys.path.append('..')
import backtrader as bt
import pandas as pd
import quantstats as qs
import matplotlib.pyplot as plt

# === 策略一：支援多空方向的 MACD 策略 ===
class MACDStrategy(bt.Strategy):
    def __init__(self):
        macd = bt.indicators.MACD(self.data.close)
        self.crossover = bt.indicators.CrossOver(macd.macd, macd.signal)
        self.trade_records = []
        self.long_order = None
        self.short_order = None

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            if order.isbuy():
                self.long_order = None
            elif order.issell():
                self.short_order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_records.append({
                'datetime': self.data.datetime.date(0).isoformat(),
                'entry_price': trade.price,
                'exit_price': self.data.close[0],
                'size': trade.size,
                'pnl': trade.pnl,
                'pnl_comm': trade.pnlcomm,
                'commission': trade.commission,
                'barlen': trade.barlen,
                'gross_pnl': trade.pnl,
                'net_pnl': trade.pnlcomm,
                'direction': 'Long' if trade.size > 0 else 'Short'
            })

    def next(self):
        dt = self.data.datetime.date(0).isoformat()
        price = self.data.close[0]

        if self.crossover > 0 and self.long_order is None:
            self.long_order = self.buy()
            print(f"[LONG ENTRY] Buy at {price} on {dt}")

        if self.crossover < 0 and self.short_order is None:
            self.short_order = self.sell()
            print(f"[SHORT ENTRY] Sell at {price} on {dt}")

# === 策略二：RSI過熱策略 ===
class RSIStrategy(bt.Strategy):
    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.trade_records = []

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_records.append({
                'datetime': self.data.datetime.date(0).isoformat(),
                'entry_price': trade.price,
                'exit_price': self.data.close[0],
                'size': trade.size,
                'pnl': trade.pnl,
                'pnl_comm': trade.pnlcomm,
                'commission': trade.commission,
                'barlen': trade.barlen,
                'gross_pnl': trade.pnl,
                'net_pnl': trade.pnlcomm,
                'direction': 'Long' if trade.size > 0 else 'Short'
            })

    def next(self):
        if not self.position:
            if self.rsi < 30:
                self.buy()
        elif self.rsi > 70:
            self.close()

# === 載入資料並篩選繪圖期間 ===
dataframe = pd.read_csv('/Users/coconut/Backtrade/datas/BTCUSDT_futures_4h_from_20210101.csv', index_col=0, parse_dates=True)
dataframe = dataframe[(dataframe.index >= '2022-01-01') & (dataframe.index <= '2022-12-31')]
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
daily_returns = all_trades.groupby(all_trades.index.date)['net_pnl'].sum()
daily_returns = pd.Series(daily_returns)
daily_returns.index = pd.to_datetime(daily_returns.index)
daily_returns = daily_returns.sort_index()
returns = daily_returns / 1_000_000

# QuantStats 報表
qs.extend_pandas()
returns = returns.asfreq('D').fillna(0)
qs.reports.basic(returns)
plt.savefig('quantstats_report.png', dpi=300)

# 畫出指定範圍圖
cerebro.plot()

