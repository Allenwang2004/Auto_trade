import os
import sys
sys.path.append('..')
import backtrader as bt
import pandas as pd
import matplotlib.pyplot as plt
from skopt import gp_minimize
from skopt.space import Categorical
import datetime

# === 基本設定 ===
strategy = 'MA60'
split_date = '2024-01-01'
os.makedirs(f"record/{strategy}", exist_ok=True)

class NetValue(bt.Observer):
    lines = ('netvalue',)
    plotinfo = dict(plot=True, subplot=True, plotname='NetValue', color='blue')

    def __init__(self):
        self.start_value = self._owner.broker.get_value()

    def next(self):
        current_value = self._owner.broker.get_value()
        self.lines.netvalue[0] = current_value - self.start_value

class MA60Strategy(bt.Strategy):
    params = dict(
        limbars=36,
        limbars2=36,
        spread=0.001,
        trailing_stop_pct=0.03
    )

    def __init__(self):
        self.sma60 = bt.indicators.SMA(self.data.close, period=60)
        self.orefs = []
        self.trade_records = []
        self.highest_price = None
        self.lowest_price = None

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            if order.status == order.Canceled:
                self.orefs = []

    def notify_trade(self, trade):
        if trade.isclosed:
            self.orefs = []
            self.trade_records.append({
                'datetime': self.data.datetime.datetime(0).isoformat(),
                'pnl': trade.pnl,
            })
            self.highest_price = None
            self.lowest_price = None

    def next(self):
        dt = self.data.datetime.datetime(0).isoformat()
        close = self.data.close[0]

        if self.position:
            if self.position.size > 0:
                if self.highest_price is None or close > self.highest_price:
                    self.highest_price = close
                if close < self.highest_price * (1 - self.p.trailing_stop_pct):
                    self.close()
                    return
            elif self.position.size < 0:
                if self.lowest_price is None or close < self.lowest_price:
                    self.lowest_price = close
                if close > self.lowest_price * (1 + self.p.trailing_stop_pct):
                    self.close()
                    return
            return

        if self.orefs:
            return

        if self.sma60[0]-self.sma60[-1]>0 and self.sma60[-1]-self.sma60[-2]<0:
            p1 = close
            p2 = p1 - self.p.spread * close
            valid1 = datetime.timedelta(days=int(self.p.limbars))
            valid2 = datetime.timedelta(days=int(self.p.limbars2))

            o1 = self.buy(exectype=bt.Order.Limit, price=round(p1, 2), size=1, valid=valid1, transmit=False)
            o2 = self.sell(exectype=bt.Order.Stop, price=round(p2, 2), size=1, valid=valid2, parent=o1, transmit=True)
            self.highest_price = close
            self.orefs = [o1.ref, o2.ref]

        elif self.sma60[0]-self.sma60[-1]<0 and self.sma60[-1]-self.sma60[-2]>0:
            p1 = close
            p2 = p1 + self.p.spread * close
            valid1 = datetime.timedelta(days=int(self.p.limbars))
            valid2 = datetime.timedelta(days=int(self.p.limbars2))

            o1 = self.sell(exectype=bt.Order.Limit, price=round(p1, 2), size=1, valid=valid1, transmit=False)
            o2 = self.buy(exectype=bt.Order.Stop, price=round(p2, 2), size=1, valid=valid2, parent=o1, transmit=True)
            self.lowest_price = close
            self.orefs = [o1.ref, o2.ref]

# === 資料讀取與切分 ===
dataframe = pd.read_csv('/Users/coconut/Auto_trade/datas/BTCUSDT_futures_4h_from_20210101.csv', index_col=0, parse_dates=True)
df_in = dataframe[dataframe.index < split_date]
df_out = dataframe[dataframe.index >= split_date]

# === 回測函數 ===
def run_backtest(params, df, plot_path=None):
    cerebro = bt.Cerebro(stdstats=False)
    data = bt.feeds.PandasData(dataname=df, timeframe=bt.TimeFrame.Minutes, compression=5)
    cerebro.adddata(data)
    cerebro.addstrategy(MA60Strategy, **params)
    cerebro.broker.setcash(5000000)
    cerebro.addobserver(NetValue)
    result = cerebro.run(runonce=True)
    trades = pd.DataFrame(result[0].trade_records)
    if trades.empty:
        trades = pd.DataFrame(columns=['datetime', 'pnl'])
    if plot_path:
        fig = cerebro.plot(style='candlestick')[0][0]
        fig.savefig(plot_path)
    return trades, trades['pnl'].sum() if not trades.empty else 0

# === 優化階段 ===
history = []
def objective(x):
    params = {
        'limbars': x[0],
        'limbars2': x[1],
        'spread': x[2],
        'trailing_stop_pct': x[3]
    }
    trades, score = run_backtest(params, df_in)
    history.append({**params, 'final_value': score})
    return -score

res = gp_minimize(
    func=objective,
    dimensions=[
        Categorical(list(range(10, 41, 5))),      # limbars
        Categorical(list(range(10, 41, 5))),      # limbars2
        Categorical([0.001, 0.002, 0.003, 0.004, 0.005]),  # spread
        Categorical([0.01, 0.02, 0.03, 0.04, 0.05])         # trailing stop pct
    ],
    n_calls=30,
    random_state=42
)

# 儲存優化紀錄
pd.DataFrame(history).to_csv(f'record/{strategy}/gp_optimize_results.csv', index=False)

# 最佳參數測試
best_params = {
    'limbars': res.x[0],
    'limbars2': res.x[1],
    'spread': res.x[2],
    'trailing_stop_pct': res.x[3]
}

trades_in, pnl_in = run_backtest(best_params, df_in)
trades_out, pnl_out = run_backtest(best_params, df_out, plot_path=f"record/{strategy}/op_result.png")

trades_in['in_sample'] = True
trades_out['in_sample'] = False
all_trades = pd.concat([trades_in, trades_out])
all_trades['datetime'] = pd.to_datetime(all_trades['datetime'])
all_trades = all_trades.set_index('datetime').sort_index()
all_trades['cumpnl'] = all_trades['pnl'].cumsum()
all_trades.reset_index().to_csv(f"record/{strategy}/best_params_trades.csv", index=False)

# 畫圖
fig, axs = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={'height_ratios': [1, 2]})

# PnL 累積圖（上）
axs[0].plot(all_trades.index, all_trades['cumpnl'], label='Cumulative PnL')
axs[0].set_title(f"{strategy} - PnL")
axs[0].set_ylabel("USD")
axs[0].legend()
axs[0].grid(True)

# 價格走勢圖（下）
axs[1].plot(dataframe.index, dataframe['close'], label='Price', color='black')
axs[1].axvline(pd.to_datetime(split_date), color='red', linestyle='--', label='Split Date')
axs[1].set_title("Price Movement")
axs[1].set_ylabel("Price")
axs[1].set_xlabel("Date")
axs[1].legend()
axs[1].grid(True)

plt.tight_layout()
plt.savefig(f"record/{strategy}/cumulative_pnl_split.png")
plt.close()


# === 統計指標計算 ===
nav = all_trades['pnl'].cumsum() + 5000000
returns = nav.pct_change().fillna(0)

# Sharpe Ratio
sharpe_ratio = (returns.mean() / returns.std()) * (365 * 24 * 12) ** 0.5 if returns.std() > 0 else 0

# Max Drawdown
running_max = nav.cummax()
drawdown = (nav - running_max) / running_max
max_drawdown = drawdown.min()

# Win Rate
num_win = (all_trades['pnl'] > 0).sum()
num_total = (all_trades['pnl'] != 0).sum()
win_rate = num_win / num_total if num_total > 0 else 0

# 輸出統計結果
with open(f"record/{strategy}/summary.txt", "w") as f:
    f.write(f"最佳參數: {best_params}")
    f.write(f"In-sample PnL: {pnl_in:.2f}")
    f.write(f"Out-of-sample PnL: {pnl_out:.2f}")
    f.write(f"Sharpe Ratio: {sharpe_ratio:.4f}")
    f.write(f"Max Drawdown: {max_drawdown:.2%}")
    f.write(f"Win Rate: {win_rate:.2%}")

print(f"Sharpe Ratio: {sharpe_ratio:.4f}")
print(f"Max Drawdown: {max_drawdown:.2%}")
print(f"Win Rate: {win_rate:.2%}")

print(f"\n最佳參數:")
print(best_params)
print(f"In-sample PnL: {pnl_in:.2f}, Out-of-sample PnL: {pnl_out:.2f}")

