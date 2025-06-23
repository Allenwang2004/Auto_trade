import backtrader as bt
import datetime
from skopt.space import Categorical

class MA60changelongonly(bt.Strategy):
    params = dict(
        long_trailing_stop_pct=0.03,
        long_stop_loss_pct=0.01
    )

    @classmethod
    def get_opt_space(cls):
        return [
            Categorical([0.01, 0.02, 0.03, 0.04, 0.05]),  # trailing stop
            Categorical([0.005, 0.01, 0.015, 0.02])       # stop loss
        ]

    @classmethod
    def param_names(cls):
        return [
            'long_trailing_stop_pct',
            'long_stop_loss_pct'
        ]

    def __init__(self):
        self.sma60 = bt.indicators.SMA(self.data.close, period=60)
        self.trade_records = []
        self.nav_records = []
        self.highest_price = None
        self.entry_price = None

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            if order.status == order.Completed and order.isbuy():
                self.entry_price = order.executed.price

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_records.append({
                'datetime': self.data.datetime.datetime(0).isoformat(),
                'pnl': trade.pnl,
            })
            self.highest_price = None
            self.entry_price = None

    def next(self):
        close = self.data.close[0]
        nav = self.broker.getvalue()
        position_value = self.position.size * close
        self.nav_records.append({
            'datetime': self.data.datetime.datetime(0).isoformat(),
            'nav': nav,
            'cash': self.broker.get_cash(),
            'position_value': position_value,
            'position_size': self.position.size if self.position else 0,
        })

        long_signal = self.sma60[0] - self.sma60[-1] > 0 and self.sma60[-1] - self.sma60[-2] < 0

        if self.position:
            if self.position.size > 0:
                self.highest_price = max(self.highest_price or close, close)

                if close < self.highest_price * (1 - self.p.long_trailing_stop_pct):
                    self.close()
                    return

                if self.entry_price and close < self.entry_price * (1 - self.p.long_stop_loss_pct):
                    self.close()
                    return

        else:
            if long_signal:
                self.buy(size=1)
                self.highest_price = close