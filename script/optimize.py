import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import argparse
import importlib
import backtrader as bt
import pandas as pd
import matplotlib.pyplot as plt
from skopt import gp_minimize
from skopt.space import Categorical
import datetime

# === Argument Parser ===
parser = argparse.ArgumentParser()
parser.add_argument('--strategy', required=True, help='策略類別名稱（需對應 strategy 資料夾下的 Python 檔）')
args = parser.parse_args()

strategy_name = args.strategy
strategy_path = f"strategy.{strategy_name}"
StrategyClass = getattr(importlib.import_module(strategy_path), strategy_name)

# === Constants ===
split_date = '2024-01-01'
os.makedirs(f"record/{strategy_name}", exist_ok=True)
initial_cash = 5000000
contract_multiplier = 1000

# === Load Data ===
dataframe = pd.read_csv('/Users/coconut/Auto_trade/datas/BTCUSDT_futures_4h_from_20210101.csv', index_col=0, parse_dates=True)
df_in = dataframe[dataframe.index < split_date]
df_out = dataframe[dataframe.index >= split_date]

# === Run Backtest ===
def run_backtest(params, df, plot_path=None):
    cerebro = bt.Cerebro(stdstats=False)
    data = bt.feeds.PandasData(dataname=df, timeframe=bt.TimeFrame.Minutes, compression=240)
    cerebro.adddata(data)
    cerebro.addstrategy(StrategyClass, **params)
    cerebro.broker.setcash(initial_cash)

    result = cerebro.run()
    strat = result[0]

    nav_df = pd.DataFrame(strat.nav_records)
    nav_df['datetime'] = pd.to_datetime(nav_df['datetime'])
    nav_df = nav_df.set_index('datetime').sort_index()
    nav_df['returns'] = nav_df['nav'].pct_change().fillna(0)

    realized_df = pd.DataFrame(getattr(strat, 'trade_records', []))
    if not realized_df.empty:
        realized_df['datetime'] = pd.to_datetime(realized_df['datetime'])
        realized_df = realized_df.set_index('datetime').sort_index()

    if plot_path:
        fig = cerebro.plot(style='candlestick')[0][0]
        fig.savefig(plot_path)

    final_nav = nav_df['nav'].iloc[-1]
    total_pnl = final_nav - initial_cash
    return nav_df.reset_index(), realized_df.reset_index(), total_pnl

# === Optimization Objective ===
history = []
def objective(x):
    params = {
        'limbars': x[0],
        'limbars2': x[1],
        'spread': x[2],
        'trailing_stop_pct': x[3]
    }
    nav_df, realized_df, score = run_backtest(params, df_in)
    history.append({**params, 'final_value': score})
    return -score

# === Run Optimization ===
res = gp_minimize(
    func=objective,
    dimensions=[
        Categorical(list(range(10, 41, 5))),
        Categorical(list(range(10, 41, 5))),
        Categorical([0.001, 0.002, 0.003, 0.004, 0.005]),
        Categorical([0.01, 0.02, 0.03, 0.04, 0.05])
    ],
    n_calls=30,
    random_state=42
)

pd.DataFrame(history).to_csv(f'record/{strategy_name}/gp_optimize_results.csv', index=False)

# === Evaluate Best Params ===
best_params = {
    'limbars': res.x[0],
    'limbars2': res.x[1],
    'spread': res.x[2],
    'trailing_stop_pct': res.x[3]
}

nav_in, realized_in, pnl_in = run_backtest(best_params, df_in)
nav_out, realized_out, pnl_out = run_backtest(best_params, df_out, plot_path=f"record/{strategy_name}/op_result.png")

# === Save all results ===
nav_all = pd.concat([nav_in.assign(in_sample=True), nav_out.assign(in_sample=False)]).set_index('datetime').sort_index()
nav_all['cumpnl'] = nav_all['nav'] - initial_cash

realized_all = pd.concat([realized_in.assign(in_sample=True), realized_out.assign(in_sample=False)])
realized_all = realized_all.sort_values('datetime')

nav_all.to_csv(f"record/{strategy_name}/nav_records.csv")
realized_all.to_csv(f"record/{strategy_name}/realized_records.csv", index=False)

returns = nav_all['returns']
sharpe_ratio = (returns.mean() / returns.std()) * (365 * 24 * 12) ** 0.5 if returns.std() > 0 else 0
max_drawdown = ((nav_all['nav'] - nav_all['nav'].cummax()) / nav_all['nav'].cummax()).min()

with open(f"record/{strategy_name}/summary.txt", "w") as f:
    f.write(f"最佳參數: {best_params}\n")
    f.write(f"In-sample PnL: {pnl_in:.2f}\n")
    f.write(f"Out-of-sample PnL: {pnl_out:.2f}\n")
    f.write(f"Sharpe Ratio: {sharpe_ratio:.4f}\n")
    f.write(f"Max Drawdown: {max_drawdown:.2%}\n")

# === Plot NAV ===
fig, axs = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
axs[0].plot(nav_all.index, nav_all['nav'], label='Net Asset Value')
axs[0].set_title(f"{strategy_name} - Net Asset Value")
axs[0].legend(); axs[0].grid()

axs[1].plot(dataframe.index, dataframe['close'], label='Price', color='black')
axs[1].axvline(pd.to_datetime(split_date), color='red', linestyle='--', label='Split Date')
axs[1].set_title("Price Movement")
axs[1].legend(); axs[1].grid()

plt.tight_layout()
plt.savefig(f"record/{strategy_name}/net_value_split.png")
plt.close()
