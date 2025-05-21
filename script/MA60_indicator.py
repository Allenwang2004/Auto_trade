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

    def __init__(self):
        self.sma30 = bt.indicators.SMA(self.data.close)
        self.sma60 = bt.indicators.SMA(self.data.close,period=60)
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.trade_records = []
        self.orefs = []
    
    # 這裡放參數
    params = dict(
        limbars=36,        
        limbars2=36,
        spread=0.001
    )

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
            self.orefs = []  
            print(f"{self.data.datetime.datetime(0).isoformat()} : [{strategy} TRADE EXIT] , PnL: {trade.pnl:.2f}")
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

                print(f"{dt} : [{strategy} Bracket LONG placed: Buy@{round(p1,2)} / SL@{round(p2,2)} / TP@{round(p3,2)}]")
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

                print(f"{dt} : [{strategy} Bracket SHORT placed: Sell@{round(p1,2)} / SL@{round(p2,2)} / TP@{round(p3,2)}]")
                self.orefs = [o1.ref, o2.ref, o3.ref]




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
plt.plot(trades_record['datetime'],trades_record['pnl'].cumsum(axis=0),label='pnl')
plt.title(f"{strategy}")
plt.ylabel("USD", fontsize=15)
plt.savefig(f"record/{strategy}/pnl.png")
plt.legend()
plt.close

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