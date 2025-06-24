import backtrader as bt
import datetime
from skopt.space import Categorical

class SSMAchange(bt.Strategy):
    params = dict(
        long_trailing_stop_pct=0.03,
        short_trailing_stop_pct=0.03,
        long_stop_loss_pct=0.01,
        short_stop_loss_pct=0.01,
        ssma_period=30
    )

    @classmethod
    def get_opt_space(cls):
        return [
            Categorical([0.01, 0.02, 0.03, 0.04, 0.05]),  # long_trailing_stop_pct
            Categorical([0.01, 0.02, 0.03, 0.04, 0.05]),  # short_trailing_stop_pct
            Categorical([0.005, 0.01, 0.015, 0.02]),      # long_stop_loss_pct
            Categorical([0.005, 0.01, 0.015, 0.02]),       # short_stop_loss_pct
            Categorical([10, 20, 30, 40, 50])            # ssma_period
        ]

    @classmethod
    def param_names(cls):
        return [
            'long_trailing_stop_pct',
            'short_trailing_stop_pct',
            'long_stop_loss_pct',
            'short_stop_loss_pct',
            'ssma_period'
        ]

    def __init__(self):
        self.ssma = bt.ind.SmoothedMovingAverage(self.data.close, period=self.p.ssma_period)
        self.trade_records = []
        self.nav_records = []
        self.highest_price = None
        self.lowest_price = None
        self.entry_price = None

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            if order.status == order.Completed:
                self.entry_price = order.executed.price

    def notify_trade(self, trade):
        if trade.isclosed:
            cost = 10  # 固定滑價+手續費成本
            self.trade_records.append({
                'datetime': self.data.datetime.datetime(0).isoformat(),
                'pnl': trade.pnl - cost,
                'entry_price': self.entry_price,
                'exit_price': trade.price,
                'return': (trade.pnl - cost) / self.entry_price if self.entry_price else 0
            })
            self.highest_price = None
            self.lowest_price = None
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

        # 訊號邏輯：使用 SSMA 斜率轉折判斷
        long_signal = self.ssma[0] - self.ssma[-1] > 0 and self.ssma[-1] - self.ssma[-2] < 0
        short_signal = self.ssma[0] - self.ssma[-1] < 0 and self.ssma[-1] - self.ssma[-2] > 0

        if self.position:
            if self.position.size > 0:
                self.highest_price = max(self.highest_price or close, close)
                if close < self.highest_price * (1 - self.p.long_trailing_stop_pct):
                    self.close()
                    return
                if self.entry_price and close < self.entry_price * (1 - self.p.long_stop_loss_pct):
                    self.close()
                    return
                if short_signal:
                    self.close()
                    self.sell(size=1)
                    self.lowest_price = close
                    return

            elif self.position.size < 0:
                self.lowest_price = min(self.lowest_price or close, close)
                if close > self.lowest_price * (1 + self.p.short_trailing_stop_pct):
                    self.close()
                    return
                if self.entry_price and close > self.entry_price * (1 + self.p.short_stop_loss_pct):
                    self.close()
                    return
                if long_signal:
                    self.close()
                    self.buy(size=1)
                    self.highest_price = close
                    return

        else:
            if long_signal:
                self.buy(size=1)
                self.highest_price = close
            elif short_signal:
                self.sell(size=1)
                self.lowest_price = close