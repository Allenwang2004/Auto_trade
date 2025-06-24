import backtrader as bt
from skopt.space import Categorical, Integer

class SSMAchangeLongOnly(bt.Strategy):
    params = dict(
        trailing_stop_pct=0.03,
        stop_loss_pct=0.01,
        ssma_period=30
    )

    @classmethod
    def get_opt_space(cls):
        return [
            Categorical([0.01, 0.02, 0.03, 0.04, 0.05]),     # trailing_stop_pct
            Categorical([0.005, 0.01, 0.015, 0.02]),         # stop_loss_pct
            Categorical([10, 20, 30, 40, 50])                                 # ssma_period
        ]

    @classmethod
    def param_names(cls):
        return ['trailing_stop_pct', 'stop_loss_pct', 'ssma_period']

    def __init__(self):
        self.ssma = bt.ind.SmoothedMovingAverage(self.data.close, period=self.p.ssma_period)
        self.trade_records = []
        self.nav_records = []
        self.highest_price = None
        self.entry_price = None

    def notify_order(self, order):
        if order.status == order.Completed:
            self.entry_price = order.executed.price

    def notify_trade(self, trade):
        if trade.isclosed:
            cost = 10
            self.trade_records.append({
                'datetime': self.data.datetime.datetime(0).isoformat(),
                'pnl': trade.pnl - cost,
                'entry_price': self.entry_price,
                'exit_price': trade.price,
                'return': (trade.pnl - cost) / self.entry_price if self.entry_price else 0
            })
            self.highest_price = None
            self.entry_price = None

    def next(self):
        close = self.data.close[0]
        self.nav_records.append({
            'datetime': self.data.datetime.datetime(0).isoformat(),
            'nav': self.broker.getvalue(),
            'cash': self.broker.get_cash(),
            'position_value': self.position.size * close,
            'position_size': self.position.size
        })

        if len(self) < self.p.ssma_period + 2:
            return

        long_signal = self.ssma[0] - self.ssma[-1] > 0 and self.ssma[-1] - self.ssma[-2] < 0

        if self.position:
            self.highest_price = max(self.highest_price or close, close)
            if close < self.highest_price * (1 - self.p.trailing_stop_pct):
                self.close()
                return
            if self.entry_price and close < self.entry_price * (1 - self.p.stop_loss_pct):
                self.close()
                return
        else:
            if long_signal:
                self.buy(size=1)
                self.highest_price = close