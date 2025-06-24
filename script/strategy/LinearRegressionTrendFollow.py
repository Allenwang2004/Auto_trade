import backtrader as bt
import datetime
import numpy as np
from skopt.space import Categorical

class LinearRegressionTrendFollow(bt.Strategy):
    params = dict(
        lookback=20,
        trailing_stop_pct=0.03,
        stop_loss_pct=0.01
    )

    @classmethod
    def get_opt_space(cls):
        return [
            Categorical([10, 15, 20, 25, 30]),          # lookback
            Categorical([0.01, 0.02, 0.03, 0.04]),      # trailing stop
            Categorical([0.005, 0.01, 0.015, 0.02])     # stop loss
        ]

    @classmethod
    def param_names(cls):
        return ['lookback', 'trailing_stop_pct', 'stop_loss_pct']

    def __init__(self):
        self.trade_records = []
        self.nav_records = []
        self.highest_price = None
        self.lowest_price = None
        self.entry_price = None

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.entry_price = order.executed.price

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_records.append({
                'datetime': self.data.datetime.datetime(0).isoformat(),
                'pnl': (trade.pnl-10),
                'entry_price': self.entry_price,
                'exit_price': trade.price,
                'return': (trade.pnl-10) / self.entry_price if self.entry_price else 0
            })
            self.highest_price = None
            self.lowest_price = None
            self.entry_price = None

    def next(self):
        close = self.data.close[0]
        dt = self.data.datetime.datetime(0)

        # === 資產紀錄 ===
        position_value = self.position.size * close
        nav = self.broker.get_cash() + position_value
        self.nav_records.append({
            'datetime': dt.isoformat(),
            'nav': nav
        })

        if len(self) < self.p.lookback:
            return

        # === 回歸線：最高價與最低價 ===
        high_prices = np.array([self.data.high[-i] for i in range(self.p.lookback)][::-1])
        low_prices = np.array([self.data.low[-i] for i in range(self.p.lookback)][::-1])
        x = np.arange(self.p.lookback)

        high_slope, high_intercept = np.polyfit(x, high_prices, 1)
        low_slope, low_intercept = np.polyfit(x, low_prices, 1)

        high_line = high_slope * (self.p.lookback - 1) + high_intercept
        low_line = low_slope * (self.p.lookback - 1) + low_intercept

        # === 開倉訊號 ===
        long_signal = close > high_line
        short_signal = close < low_line

        # === 有持倉 ===
        if self.position:
            if self.position.size > 0:
                self.highest_price = max(self.highest_price or close, close)
                if close < self.highest_price * (1 - self.p.trailing_stop_pct):
                    self.close()
                    return
                if self.entry_price and close < self.entry_price * (1 - self.p.stop_loss_pct):
                    self.close()
                    return
                # 多單時出現做空訊號（向下突破最低價回歸線）
                if short_signal:
                    self.close()
                    self.sell(size=1)
                    self.lowest_price = close
                    return

            elif self.position.size < 0:
                self.lowest_price = min(self.lowest_price or close, close)
                if close > self.lowest_price * (1 + self.p.trailing_stop_pct):
                    self.close()
                    return
                if self.entry_price and close > self.entry_price * (1 + self.p.stop_loss_pct):
                    self.close()
                    return
                # 空單時出現做多訊號（突破最高價回歸線）
                if long_signal:
                    self.close()
                    self.buy(size=1)
                    self.highest_price = close
                    return

        # === 無持倉 ===
        else:
            if long_signal:
                self.buy(size=1)
                self.highest_price = close
            elif short_signal:
                self.sell(size=1)
                self.lowest_price = close