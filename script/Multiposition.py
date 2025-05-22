import os
import sys
sys.path.append('..')
import backtrader as bt
import pandas as pd
import matplotlib.pyplot as plt
import datetime

strategy_name = 'MA60_5accounts'
os.makedirs(f"record/{strategy_name}", exist_ok=True)

# === 資料 ===
dataframe = pd.read_csv(
    '/Users/coconut/Auto_trade/datas/BTCUSDT_futures_4h_from_20210101.csv',
    index_col=0, parse_dates=True
)

# === 策略 ===
class MA60Strategy(bt.Strategy):
    params = dict(
        limbars=36,
        limbars2=36,
        spread=0.001,
        name="Strategy"
    )

    def __init__(self):
        self.sma60 = bt.indicators.SMA(self.data.close, period=60)
        self.trade_records = []
        self.orefs = []

    def notify_trade(self, trade):
        if trade.isclosed:
            self.orefs = []
            self.trade_records.append({
                'datetime': self.data.datetime.datetime(0).isoformat(),
                'pnl': trade.pnl,
                'strategy': self.p.name
            })

    def next(self):
        if self.orefs:
            return
        close = self.data.close[0]
        if not self.position:
            if self.sma60[0] - self.sma60[-1] > 0 and self.sma60[-1] - self.sma60[-2] < 0:
                self._bracket_order(close, long=True)
            elif self.sma60[0] - self.sma60[-1] < 0 and self.sma60[-1] - self.sma60[-2] > 0:
                self._bracket_order(close, long=False)

    def _bracket_order(self, close, long=True):
        p1 = close
        p2 = p1 - self.p.spread * close if long else p1 + self.p.spread * close
        p3 = p1 + self.p.spread * close if long else p1 - self.p.spread * close
        valid1 = datetime.timedelta(self.p.limbars)
        valid2 = datetime.timedelta(self.p.limbars2)

        o1 = self.buy(price=round(p1, 2), exectype=bt.Order.Limit,
                      size=1, valid=valid1, transmit=False) if long else \
             self.sell(price=round(p1, 2), exectype=bt.Order.Limit,
                       size=1, valid=valid1, transmit=False)

        o2 = self.sell(price=round(p2, 2), exectype=bt.Order.Stop,
                       size=1, valid=valid2, parent=o1, transmit=False) if long else \
             self.buy(price=round(p2, 2), exectype=bt.Order.Stop,
                      size=1, valid=valid2, parent=o1, transmit=False)

        o3 = self.sell(price=round(p3, 2), exectype=bt.Order.Limit,
                       size=1, valid=valid2, parent=o1, transmit=True) if long else \
             self.buy(price=round(p3, 2), exectype=bt.Order.Limit,
                      size=1, valid=valid2, parent=o1, transmit=True)

        self.orefs = [o1.ref, o2.ref, o3.ref]

# === 策略參數 ===
strategy_params = [
    dict(limbars=36, limbars2=36, spread=0.001, name='S1'),
    dict(limbars=30, limbars2=30, spread=0.002, name='S2'),
    dict(limbars=40, limbars2=30, spread=0.003, name='S3'),
    dict(limbars=35, limbars2=28, spread=0.0015, name='S4'),
    dict(limbars=25, limbars2=25, spread=0.0025, name='S5'),
]

# === 回測所有策略，使用獨立 Cerebro（獨立資金池） ===
results = []
for i, params in enumerate(strategy_params):
    cerebro = bt.Cerebro(stdstats=False)
    data = bt.feeds.PandasData(dataname=dataframe.copy(), timeframe=bt.TimeFrame.Minutes, compression=5)
    cerebro.adddata(data)
    cerebro.addstrategy(MA60Strategy, **params)
    cerebro.broker.setcash(1000000)
    result = cerebro.run()
    results.append(result[0])

# === 收集所有交易紀錄 ===
all_trades = pd.concat([
    pd.DataFrame(r.trade_records) for r in results
], ignore_index=True)

all_trades['datetime'] = pd.to_datetime(all_trades['datetime'])
all_trades = all_trades.set_index('datetime').sort_index()

# === 累積 PnL 計算 ===
pnl_by_strategy = all_trades.pivot_table(
    index='datetime',
    columns='strategy',
    values='pnl',
    aggfunc='sum'
).fillna(0)

pnl_by_strategy['combined'] = pnl_by_strategy.sum(axis=1)/5
cumulative_pnl = pnl_by_strategy.cumsum()

# === 畫圖 ===
plt.figure(figsize=(12, 6))
for col in cumulative_pnl.columns:
    plt.plot(cumulative_pnl.index, cumulative_pnl[col], label=col)
plt.title("Multi-Account Cumulative PnL")
plt.xlabel("Date")
plt.ylabel("USD")
plt.grid()
plt.legend()
plt.tight_layout()
plt.savefig(f"record/{strategy_name}/multi_account_pnl.png")
plt.close()

# === 儲存 CSV ===
cumulative_pnl.to_csv(f"record/{strategy_name}/cumulative_pnl.csv")
all_trades.reset_index().to_csv(f"record/{strategy_name}/trades_all.csv", index=False)

print("✅ 完成多策略獨立資金池回測與圖表繪製")