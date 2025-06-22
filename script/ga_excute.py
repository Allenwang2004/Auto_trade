import pygad
import numpy as np

import pandas as pd
import importlib
import datetime
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import backtrader as bt

# === 載入資料 ===
dataframe = pd.read_csv('/Users/coconut/Auto_trade/datas/BTCUSDT_futures_4h_from_20210101.csv', index_col=0, parse_dates=True)
split_date = '2024-01-01'
df_in = dataframe[dataframe.index < split_date]

# === 導入策略類別 ===
from strategy.RuleGA_Strategy import RuleGA_Strategy

# === 回測函數 ===
def run_backtest(mask):
    cerebro = bt.Cerebro(stdstats=False)
    data = bt.feeds.PandasData(dataname=df_in, timeframe=bt.TimeFrame.Minutes, compression=5)
    cerebro.adddata(data)
    cerebro.addstrategy(RuleGA_Strategy,
                        condition_mask=mask,
                        limbars=36,
                        limbars2=36,
                        spread=0.001,
                        trailing_stop_pct=0.03,
                        lookback=20)
    cerebro.broker.setcash(5000000)
    result = cerebro.run()
    strat = result[0]

    nav_df = pd.DataFrame(strat.nav_records)
    nav_df['datetime'] = pd.to_datetime(nav_df['datetime'])
    nav_df = nav_df.set_index('datetime').sort_index()
    nav_df['returns'] = nav_df['nav'].pct_change().fillna(0)
    final_nav = nav_df['nav'].iloc[-1]
    total_pnl = final_nav - 5000000
    return total_pnl

# === 適應度函數（符合 PyGAD 2.20.0 規格） ===
def fitness_func(ga_instance, solution, solution_idx):
    mask = [int(round(bit)) for bit in solution]
    if sum(mask) == 0:
        return -1e6  # 無條件時略過
    pnl = run_backtest(mask)
    return pnl

# === GA 設定 ===
gene_space = [0, 1]  # 每個基因是布林值（是否使用某條件）
num_generations = 20
num_parents_mating = 4
sol_per_pop = 10
num_genes = 5

# === 初始化 GA ===
ga_instance = pygad.GA(
    gene_space=gene_space,
    num_generations=num_generations,
    num_parents_mating=num_parents_mating,
    fitness_func=fitness_func,
    sol_per_pop=sol_per_pop,
    num_genes=num_genes,
    parent_selection_type="sss",
    keep_parents=2,
    crossover_type="single_point",
    mutation_type="random",
    mutation_percent_genes=20
)

# === 執行 GA ===
ga_instance.run()
ga_instance.plot_fitness()

# === 最佳解 ===
best_solution, best_solution_fitness, _ = ga_instance.best_solution()
best_mask = [int(round(x)) for x in best_solution]
print(f"Best mask: {best_mask}, Fitness: {best_solution_fitness:.2f}")

# === 儲存最佳結果 ===
os.makedirs('record/RuleGA_Strategy', exist_ok=True)
with open('record/RuleGA_Strategy/ga_best_mask.txt', 'w') as f:
    f.write(f"Best mask: {best_mask}\n")
    f.write(f"Fitness: {best_solution_fitness:.2f}\n")

