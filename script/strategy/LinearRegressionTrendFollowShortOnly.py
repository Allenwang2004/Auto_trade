import backtrader as bt
import datetime
import numpy as np
from skopt.space import Categorical

class LinearRegressionTrendFollowShortOnly(bt.Strategy):
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
        self.lowest_price = None
        self.entry_price = None

    def notify_order(self, order):
        if order.status == order.Completed:
            self.entry_price = order.executed.price

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_records.append({
                'datetime': self.data.datetime.datetime(0).isoformat(),
                'pnl': trade.pnl,
            })
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

        # === 不足資料長度，略過 ===
        if len(self) < self.p.lookback:
            return

        # === 計算回歸線預測 ===
        y = np.array([self.data.close[-i] for i in range(self.p.lookback)][::-1])
        x = np.arange(self.p.lookback)
        slope, intercept = np.polyfit(x, y, 1)
        reg_value = slope * (self.p.lookback - 1) + intercept

        short_signal = close < reg_value

        if self.position:
            # === 持有空單 ===
            self.lowest_price = min(self.lowest_price or close, close)
            # 移動止盈
            if close > self.lowest_price * (1 + self.p.trailing_stop_pct):
                self.close()
                return
            # 固定止損
            if self.entry_price and close > self.entry_price * (1 + self.p.stop_loss_pct):
                self.close()
                return

        else:
            # === 無持倉，且出現做空訊號 ===
            if short_signal:
                self.sell(size=1)
                self.lowest_price = close