import backtrader as bt
import datetime

class MA60change(bt.Strategy):
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
        close = self.data.close[0]
        position_value = self.position.size * close
        nav = self.broker.get_cash() + position_value
        self.nav_records.append({
            'datetime': self.data.datetime.datetime(0).isoformat(),
            'nav': nav
        })

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

        if self.sma60[0] - self.sma60[-1] > 0 and self.sma60[-1] - self.sma60[-2] < 0:
            p1 = close
            p2 = p1 - self.p.spread * close
            o1 = self.buy(price=round(p1, 2), exectype=bt.Order.Limit, size=1,
                          valid=datetime.timedelta(days=int(self.p.limbars)), transmit=False)
            o2 = self.sell(price=round(p2, 2), exectype=bt.Order.Stop, size=1,
                           valid=datetime.timedelta(days=int(self.p.limbars2)), parent=o1, transmit=True)
            self.highest_price = close
            self.orefs = [o1.ref, o2.ref]

        elif self.sma60[0] - self.sma60[-1] < 0 and self.sma60[-1] - self.sma60[-2] > 0:
            p1 = close
            p2 = p1 + self.p.spread * close
            o1 = self.sell(price=round(p1, 2), exectype=bt.Order.Limit, size=1,
                           valid=datetime.timedelta(days=int(self.p.limbars)), transmit=False)
            o2 = self.buy(price=round(p2, 2), exectype=bt.Order.Stop, size=1,
                          valid=datetime.timedelta(days=int(self.p.limbars2)), parent=o1, transmit=True)
            self.lowest_price = close
            self.orefs = [o1.ref, o2.ref]