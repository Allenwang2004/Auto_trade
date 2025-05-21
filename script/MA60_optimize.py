import os
import sys
sys.path.append('..')
import backtrader as bt
import pandas as pd
import matplotlib.pyplot as plt
from skopt import gp_minimize
import datetime

# === 基本設定 ===
strategy = 'MA60'
split_date = '2022-01-01'  # 訓練 / 測試資料切割點
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

    def __init__(self):
        self.sma30 = bt.indicators.SMA(self.data.close)
        self.sma60 = bt.indicators.SMA(self.data.close,period=60)
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.trade_records = []
        self.orefs = []
    
    params = dict(
        limbars=36,        
        limbars2=36,
        spread=0.001
    )

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            if order.isbuy() and order.status == order.Canceled:
                self.orefs = []
            elif order.issell() and order.status == order.Canceled:
                self.orefs = []

    def notify_trade(self, trade):
        if trade.isclosed:
            self.orefs = []  
            self.trade_records.append({
                'datetime': self.data.datetime.datetime(0).isoformat(),
                'pnl': trade.pnl,
            })

    def next(self):
        if self.orefs:
            return  

        dt = self.data.datetime.datetime(0).isoformat()
        close = self.data.close[0]

        if not self.position:
            if self.sma60[0]-self.sma60[-1]>0 and self.sma60[-1]-self.sma60[-2]<0 :

                p1 = close
                p2 = p1 - self.p.spread * close 
                p3 = p1 + self.p.spread * close 

                valid1 = datetime.timedelta(self.p.limbars)
                valid2 = valid3 = datetime.timedelta(self.p.limbars2)

                o1 = self.buy(exectype=bt.Order.Limit,
                            price=round(p1, 2),
                            size=1,
                            valid=valid1,
                            transmit=False)
                o2 = self.sell(exectype=bt.Order.Stop,
                            price=round(p2, 2),
                            size=1,
                            valid=valid2,
                            parent=o1,
                            transmit=False)
                o3 = self.sell(exectype=bt.Order.Limit,
                            price=round(p3, 2),
                            size=1,
                            valid=valid3,
                            parent=o1,
                            transmit=True)

                self.orefs = [o1.ref, o2.ref, o3.ref]
            
            elif self.sma60[0]-self.sma60[-1]<0 and self.sma60[-1]-self.sma60[-2]>0 :

                p1 = close
                p2 = p1 + self.p.spread * close  
                p3 = p1 - self.p.spread * close  

                valid1 = datetime.timedelta(self.p.limbars)
                valid2 = valid3 = datetime.timedelta(self.p.limbars2)
                
                o1 = self.sell(exectype=bt.Order.Limit,
                            price=round(p1, 2),
                            size=1,
                            valid=valid1,
                            transmit=False)
                o2 = self.buy(exectype=bt.Order.Stop,
                            price=round(p2, 2),
                            size=1,
                            valid=valid2,
                            parent=o1,
                            transmit=False)
                o3 = self.buy(exectype=bt.Order.Limit,
                            price=round(p3, 2),
                            size=1,
                            valid=valid3,
                            parent=o1,
                            transmit=True)

                self.orefs = [o1.ref, o2.ref, o3.ref]


# === 資料讀取與切分 ===
dataframe = pd.read_csv(
    '/Users/coconut/Auto_trade/datas/BTCUSDT_futures_4h_from_20210101.csv',
    index_col=0, parse_dates=True
)
df_in = dataframe[dataframe.index < split_date]
df_out = dataframe[dataframe.index >= split_date]


# === 回測函數 ===
def run_backtest(limbars, limbars2, spread, df, plot_path=None):
    cerebro = bt.Cerebro(stdstats=False)
    data = bt.feeds.PandasData(dataname=df, timeframe=bt.TimeFrame.Minutes, compression=5)
    cerebro.adddata(data)
    cerebro.addstrategy(MA60Strategy, limbars=limbars, limbars2=limbars2, spread=spread)
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
    limbars, limbars2, spread = int(x[0]), int(x[1]), x[2]
    trades, score = run_backtest(limbars, limbars2, spread, df_in)
    history.append({'limbars': limbars, 'limbars2': limbars2, 'spread': spread, 'final_value': score})
    return -score

res = gp_minimize(
    func=objective,
    dimensions=[
        (10, 40), (10, 40), (0.001, 0.005)
    ],
    n_calls=20,
    random_state=42
)

# 儲存優化紀錄
pd.DataFrame(history).to_csv(f'record/{strategy}/gp_optimize_results.csv', index=False)

# === 最佳參數測試 on full data ===
#best_limbars, best_limbars2, best_spread = int(res.x[0]), int(res.x[1]), res.x[2]
best_limbars, best_limbars2, best_spread = 36, 36, 0.001
trades_in, pnl_in = run_backtest(best_limbars, best_limbars2, best_spread, df_in)
trades_out, pnl_out = run_backtest(best_limbars, best_limbars2, best_spread, df_out, plot_path=f"record/{strategy}/op_result.png")

# 標記樣本內 / 外
trades_in['in_sample'] = True
trades_out['in_sample'] = False
all_trades = pd.concat([trades_in, trades_out])
all_trades['datetime'] = pd.to_datetime(all_trades['datetime'])
all_trades = all_trades.set_index('datetime').sort_index()
all_trades['cumpnl'] = all_trades['pnl'].cumsum()
all_trades.reset_index().to_csv(f"record/{strategy}/best_params_trades.csv", index=False)

# === 畫圖 ===
plt.figure(figsize=(12, 6))
plt.plot(all_trades.index, all_trades['cumpnl'], label='Cumulative PnL')
plt.axvline(pd.to_datetime(split_date), color='red', linestyle='--', label='Split Date')
plt.title(f"{strategy} | In-sample PnL: {pnl_in:.2f}, Out-of-sample PnL: {pnl_out:.2f}")
plt.xlabel("Date")
plt.ylabel("Cumulative PnL")
plt.legend()
plt.grid()
plt.tight_layout()
plt.savefig(f"record/{strategy}/cumulative_pnl_split.png")
plt.close()

print(f"優化完成！最佳參數: limbars={best_limbars}, limbars2={best_limbars2}, spread={best_spread:.4f}")
print(f"In-sample PnL: {pnl_in:.2f}, Out-of-sample PnL: {pnl_out:.2f}")