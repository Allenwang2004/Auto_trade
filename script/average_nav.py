import pandas as pd
import matplotlib.pyplot as plt
import argparse
import os
from datetime import datetime

# === 解析 CLI 參數 ===
parser = argparse.ArgumentParser(description="Plot average NAV from multiple strategies")
parser.add_argument('--files', nargs='+', required=True, help="List of nav_records.csv files")
parser.add_argument('--price', type=str, required=True, help="Price CSV file path")
parser.add_argument('--split', type=str, default="2024-01-01", help="Split date for marking training/test")
parser.add_argument('--initial_cash', type=float, default=5000000, help="Initial cash value")
parser.add_argument('--output', type=str, default="average_nav_plot.png", help="Output image filename")
args = parser.parse_args()

# === 讀取價格資料 ===
price_df = pd.read_csv(args.price, index_col=0, parse_dates=True)
price_df = price_df[['close']].rename(columns={'close': 'price'})

# === 讀取 nav_records 檔案 ===
nav_dfs = []
sharpe_info = []

for file in args.files:
    strategy_name = os.path.basename(os.path.dirname(file))
    df = pd.read_csv(file, parse_dates=['datetime']).set_index('datetime')
    df = df[['nav']].rename(columns={'nav': strategy_name})
    
    # 計算日報酬與 Sharpe ratio
    returns = df[strategy_name].pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * (365 * 24 * 12) ** 0.5 if returns.std() > 0 else 0
    sharpe_info.append((strategy_name, sharpe))

    nav_dfs.append(df)

# === 合併 NAV 並取平均 ===
merged_nav = pd.concat(nav_dfs, axis=1).sort_index().ffill()
merged_nav['avg_nav'] = merged_nav.mean(axis=1)

# === 計算平均策略 Sharpe ratio ===
avg_returns = merged_nav['avg_nav'].pct_change().dropna()
avg_sharpe = (avg_returns.mean() / avg_returns.std()) * (365 * 24 * 12) ** 0.5 if avg_returns.std() > 0 else 0

# === 整合價格（價格也縮放到初始資金等級）===
plot_df = merged_nav.merge(price_df, left_index=True, right_index=True, how='inner')
plot_df['price_scaled'] = plot_df['price'] / plot_df['price'].iloc[0] * args.initial_cash

# === 繪圖（上下兩個子圖）===
fig, axs = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

# === 上圖：策略 NAV ===
for col in merged_nav.columns:
    if col != 'avg_nav':
        axs[0].plot(plot_df.index, plot_df[col] - args.initial_cash, label=col, color='gray', alpha=0.3)

axs[0].plot(plot_df.index, plot_df['avg_nav'] - args.initial_cash, label='Average NAV', color='blue', linewidth=2)
axs[0].axvline(pd.to_datetime(args.split), color='red', linestyle='--', label='Split Date')
axs[0].set_title("NAV Comparison (Cumulative PnL)")
axs[0].set_ylabel("Cumulative PnL")
axs[0].legend()
axs[0].grid()

# === 下圖：價格 ===
axs[1].plot(plot_df.index, plot_df['price_scaled'] - args.initial_cash, label='Price (scaled)', color='black', linestyle='--', alpha=0.7)
axs[1].axvline(pd.to_datetime(args.split), color='red', linestyle='--', label='Split Date')
axs[1].set_title("Price (Scaled)")
axs[1].set_xlabel("Date")
axs[1].set_ylabel("Scaled Price - Initial Cash")
axs[1].legend()
axs[1].grid()

# === 儲存圖表 ===
plt.tight_layout()
plt.savefig(args.output)
plt.show()

# === 輸出 Sharpe ratio ===
print("\nSharpe Ratios:")
for name, sharpe in sharpe_info:
    print(f" - {name}: {sharpe:.4f}")
print(f" - Average NAV: {avg_sharpe:.4f}")