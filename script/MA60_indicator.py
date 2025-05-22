import sys
sys.path.append('..')
import backtrader as bt
import pandas as pd
import quantstats as qs
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import datetime

strategy = 'MA60'
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
        trailing_stop_pct=0.03  # 新增：移動止盈比例
    )

    def __init__(self):
        self.sma30 = bt.indicators.SMA(self.data.close)
        self.sma60 = bt.indicators.SMA(self.data.close, period=60)
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.trade_records = []
        self.orefs = []

        self.highest_price = None  # for long trailing stop
        self.lowest_price = None   # for short trailing stop

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            if order.isbuy() and order.status != order.Canceled:
                print(f"{self.data.datetime.datetime(0).isoformat()} : [{strategy} ORDER BUY] {order.getstatusname()} @ {order.executed.price}")
            elif order.issell() and order.status != order.Canceled:
                print(f"{self.data.datetime.datetime(0).isoformat()} : [{strategy} ORDER SELL] {order.getstatusname()} @ {order.executed.price}")
            elif order.isbuy() and order.status == order.Canceled:
                print(f"{self.data.datetime.datetime(0).isoformat()} : [{strategy} ORDER BUY] {order.getstatusname()}")
                self.orefs = []
            elif order.issell() and order.status == order.Canceled:
                print(f"{self.data.datetime.datetime(0).isoformat()} : [{strategy} ORDER SELL] {order.getstatusname()})")
                self.orefs = []

    def notify_trade(self, trade):
        if trade.isopen:
            print(f"{self.data.datetime.datetime(0).isoformat()} : [{strategy} TRADE OPEN]")
        elif trade.isclosed:
            print(f"{self.data.datetime.datetime(0).isoformat()} : [{strategy} TRADE EXIT] , PnL: {trade.pnl:.2f}")
            self.trade_records.append({
                'datetime': self.data.datetime.datetime(0).isoformat(),
                'pnl': trade.pnl,
            })
            self.orefs = []
            self.highest_price = None
            self.lowest_price = None

    def next(self):
        dt = self.data.datetime.datetime(0).isoformat()
        close = self.data.close[0]

        # 處理移動止盈平倉邏輯
        if self.position:
            if self.position.size > 0:  # 多單
                if self.highest_price is None or close > self.highest_price:
                    self.highest_price = close
                if close < self.highest_price * (1 - self.p.trailing_stop_pct):
                    print(f"{dt} : [Trailing Stop Hit - LONG], close at {close}")
                    self.close()
                    return
            elif self.position.size < 0:  # 空單
                if self.lowest_price is None or close < self.lowest_price:
                    self.lowest_price = close
                if close > self.lowest_price * (1 + self.p.trailing_stop_pct):
                    print(f"{dt} : [Trailing Stop Hit - SHORT], close at {close}")
                    self.close()
                    return
            return  # 移動止盈後不再繼續開倉

        # 若尚未有持倉且沒掛單才嘗試開新倉
        if not self.orefs:
            if self.sma60[0] - self.sma60[-1] > 0 and self.sma60[-1] - self.sma60[-2] < 0:
                # 多單條件
                p1 = close
                p2 = p1 - self.p.spread * close

                valid1 = datetime.timedelta(self.p.limbars)
                valid2 = datetime.timedelta(self.p.limbars2)

                o1 = self.buy(exectype=bt.Order.Limit, price=round(p1, 2), size=1, valid=valid1, transmit=False)
                o2 = self.sell(exectype=bt.Order.Stop, price=round(p2, 2), size=1, valid=valid2, parent=o1, transmit=True)

                print(f"{dt} : [{strategy} LONG placed: Buy@{round(p1,2)} / SL@{round(p2,2)}]")
                self.highest_price = close
                self.orefs = [o1.ref, o2.ref]

            elif self.sma60[0] - self.sma60[-1] < 0 and self.sma60[-1] - self.sma60[-2] > 0:
                # 空單條件
                p1 = close
                p2 = p1 + self.p.spread * close

                valid1 = datetime.timedelta(self.p.limbars)
                valid2 = datetime.timedelta(self.p.limbars2)

                o1 = self.sell(exectype=bt.Order.Limit, price=round(p1, 2), size=1, valid=valid1, transmit=False)
                o2 = self.buy(exectype=bt.Order.Stop, price=round(p2, 2), size=1, valid=valid2, parent=o1, transmit=True)

                print(f"{dt} : [{strategy} SHORT placed: Sell@{round(p1,2)} / SL@{round(p2,2)}]")
                self.lowest_price = close
                self.orefs = [o1.ref, o2.ref]




dataframe = pd.read_csv('/Users/coconut/Auto_trade/datas/BTCUSDT_futures_4h_from_20210101.csv', index_col=0, parse_dates=True)
data = bt.feeds.PandasData(
    dataname=dataframe,
    timeframe=bt.TimeFrame.Minutes,
    compression=5,                  
)

cerebro = bt.Cerebro(stdstats=False)
cerebro.adddata(data)
cerebro.addstrategy(MA60Strategy)
cerebro.broker.setcash(5000000)
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
cerebro.addobserver(NetValue)


cerebro.broker.setcommission(
    commission=2.0,
    margin=10000,
    mult=10,
)

cerebro.broker.set_slippage_fixed(
    fixed=2.0,
    slip_open=True,
    slip_limit=True,
    slip_match=True,
    slip_out=False
)

results = cerebro.run()

trades_record = pd.DataFrame(results[0].trade_records)
trades_record.to_csv(f"record/{strategy}/trades.csv", index=False)

sum_return = trades_record['pnl'].sum(axis=0)

trades_record['datetime'] = pd.to_datetime(trades_record['datetime'])
trades_record = trades_record.set_index('datetime')
full_range = pd.date_range(start=trades_record.index.min(), end=trades_record.index.max(), freq='5T')

trades_record = trades_record.reindex(full_range)
trades_record = trades_record.fillna(0)

trades_record = trades_record.reset_index().rename(columns={'index': 'datetime'})

fig, axs = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={'height_ratios': [1, 2]})

# pnl 累積圖（上圖）
axs[0].plot(trades_record['datetime'], trades_record['pnl'].cumsum(), label='Cumulative PnL')
axs[0].set_title(f"{strategy} - PnL")
axs[0].set_ylabel("USD")
axs[0].legend()
axs[0].grid(True)

# 價格走勢圖（下圖）
axs[1].plot(dataframe.index, dataframe['close'], label='Price', color='black')
axs[1].set_title("Price Movement")
axs[1].set_ylabel("Price")
axs[1].set_xlabel("Date")
axs[1].legend()
axs[1].grid(True)

plt.tight_layout()
plt.savefig(f"record/{strategy}/pnl_price_comparison.png")
plt.close()

fig = cerebro.plot()[0][0]
fig.savefig(f"record/{strategy}/result.png")


# # all_trades = trades_macd
# # all_trades['datetime'] = pd.to_datetime(all_trades['datetime'])
# # all_trades.set_index('datetime', inplace=True)

# # daily_returns = all_trades.groupby(all_trades.index.date)['pnl'].sum()
# # daily_returns = pd.Series(daily_returns)
# # daily_returns.index = pd.to_datetime(daily_returns.index)
# # daily_returns = daily_returns.sort_index()
# # returns = daily_returns / 1_000_000
# # qs.extend_pandas()
# # returns = returns.asfreq('D').fillna(0)
# # print('--------------------------------')
# # qs.reports.basic(returns)
# # plt.show()

# #cerebro.plot(start=datetime.date(2024, 7, 1), end=datetime.date(2024, 8, 31))