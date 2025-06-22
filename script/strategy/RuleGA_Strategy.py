import backtrader as bt
import datetime
import numpy as np

class RuleGA_Strategy(bt.Strategy):
    params = dict(
        condition_mask=[1, 1, 0, 0, 0],
        limbars=36,
        limbars2=36,
        spread=0.001,
        trailing_stop_pct=0.03,
        lookback=20
    )

    def __init__(self):
        self.sma60 = bt.indicators.SMA(self.data.close, period=60)
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.orefs = []
        self.trade_records = []
        self.nav_records = []
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
        if len(self.data) < self.p.lookback:
            return

        close = self.data.close[0]
        open_ = self.data.open[0]
        dt = self.data.datetime.datetime(0)

        # 計算回歸線
        y = np.array([self.data.close[-i] for i in range(self.p.lookback)][::-1])
        x = np.arange(self.p.lookback)
        slope, intercept = np.polyfit(x, y, 1)
        reg_value = slope * (self.p.lookback - 1) + intercept

        # === NAV 紀錄 ===
        position_value = self.position.size * close
        nav = self.broker.get_cash() + position_value
        self.nav_records.append({
            'datetime': dt.isoformat(),
            'nav': nav
        })

        # === 持倉中移動止損 ===
        if self.position:
            if self.position.size > 0:
                self.highest_price = max(self.highest_price or close, close)
                if close < self.highest_price * (1 - self.p.trailing_stop_pct):
                    self.close()
                    return
            elif self.position.size < 0:
                self.lowest_price = min(self.lowest_price or close, close)
                if close > self.lowest_price * (1 + self.p.trailing_stop_pct):
                    self.close()
                    return
            return

        if self.orefs:
            return

        # === 條件定義 ===
        conditions = [
            self.sma60[0] > self.sma60[-1],                      # C0
            close > reg_value,                                   # C1
            self.data.volume[0] > self.data.volume[-1],          # C2
            self.rsi[0] < 30,                                    # C3
            close > open_                                        # C4
        ]

        # === 挑選條件 ===
        selected = [cond for cond, flag in zip(conditions, self.p.condition_mask) if flag]
        if not selected:
            return

        if all(selected):
            p1 = close
            p2 = p1 - self.p.spread * close
            o1 = self.buy(price=round(p1, 2), exectype=bt.Order.Limit, size=1,
                          valid=datetime.timedelta(days=self.p.limbars), transmit=False)
            o2 = self.sell(price=round(p2, 2), exectype=bt.Order.Stop, size=1,
                           valid=datetime.timedelta(days=self.p.limbars2), parent=o1, transmit=True)
            self.highest_price = close
            self.orefs = [o1.ref, o2.ref]

        elif all([not c for c in selected]):
            p1 = close
            p2 = p1 + self.p.spread * close
            o1 = self.sell(price=round(p1, 2), exectype=bt.Order.Limit, size=1,
                           valid=datetime.timedelta(days=self.p.limbars), transmit=False)
            o2 = self.buy(price=round(p2, 2), exectype=bt.Order.Stop, size=1,
                          valid=datetime.timedelta(days=self.p.limbars2), parent=o1, transmit=True)
            self.lowest_price = close
            self.orefs = [o1.ref, o2.ref]
