#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目名称: GNSS 时间序列分量分析与可视化 (Nature 风格)
文件描述:
    本脚本用于批量处理 UNR 格式的 .tenv3 文件，生成高质量的 GPS 位移时间序列图。
    主要功能包括：
    1. 自动读取指定目录下的所有 .tenv3 站点文件。
    2. 物理量转换：将原始观测(Raw)与负载预测(Load)相加，并从米(m)转换为毫米(mm)。
    3. 单站分析：为每个站点生成包含 北(N)、东(E)、垂直(U) 三个分量的独立时序图。
    4. 区域汇总：生成全区域所有站点的 North、East、Vertical 三张汇总矩阵大图。
    5. 出版级审美：采用 Nature 常用配色、自适应刻度控制及简洁布局。

数据计算逻辑 (单位: mm):
    - 位移 = (整数部分 + 小数部分) * 1000
    - 具体的列映射 (0-indexed):
        Year: 2 | E: 7+8 | N: 9+10 | U: 11+12

依赖库: pandas, matplotlib, numpy, glob
作者: SingyuTang
日期: 2026-01-14
版本: v1.0
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from glob import glob

# ==========================================
# 1. 参数配置区
# ==========================================
DATA_DIR = "../../01_Data_Raw/tenv3"
FIGURE_OUTPUT = "s1_results"

STYLE = {
    "font_family": "Arial",
    "dpi": 300,
    # 颜色顺序：北(N)-红，东(E)-蓝，垂直(U)-绿
    "colors": ["#E64B35", "#4DBBD5", "#00A087"],
    "marker_size": 1.5,
    "alpha": 0.6,
    "fig_size_single": (7, 6),
    "fig_size_summary": (16, 20),  # 增加宽度以适应 5 列布局
    "x_max_ticks": 6,
    "y_max_ticks": 5
}

# 列索引 (0-indexed)
# 年份:2, E:7+8, N:9+10, U:11+12
USE_COLS = [2, 7, 8, 9, 10, 11, 12]
COL_NAMES = ['decimal_year', 'E_raw', 'E_load', 'N_raw', 'N_load', 'U_raw', 'U_load']


# ==========================================

# ==========================================
# 2. 功能实现区
# ==========================================

def setup_style():
    """设置 Nature 出版级样式"""
    plt.rcParams.update({
        'font.sans-serif': [STYLE['font_family'], 'DejaVu Sans'],
        'axes.unicode_minus': False,
        'axes.linewidth': 1.0,
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.size': 5,
        'ytick.major.size': 5,
        'axes.labelsize': 10,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'savefig.bbox': 'tight'
    })


def load_and_calculate_data(file_path):
    """读取并计算位移 (raw + load) * 1000"""
    try:
        df = pd.read_csv(file_path, sep=r'\s+', header=0, usecols=USE_COLS, names=COL_NAMES)
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()

        final_df = pd.DataFrame()
        final_df['year'] = df['decimal_year']
        final_df['dE'] = (df['E_raw'] + df['E_load']) * 1000
        final_df['dN'] = (df['N_raw'] + df['N_load']) * 1000
        final_df['dU'] = (df['U_raw'] + df['U_load']) * 1000
        return final_df
    except Exception as e:
        print(f"处理文件 {file_path} 出错: {e}")
        return None


def apply_adaptive_ticks(ax, is_x=False):
    """防止坐标轴标签重叠"""
    if is_x:
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=STYLE['x_max_ticks']))
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f'))
    else:
        ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=STYLE['y_max_ticks']))


def plot_single_station(df, station_name, output_dir):
    """绘制单站 N, E, U 三轴图"""
    if df.empty: return
    fig, axes = plt.subplots(3, 1, figsize=STYLE['fig_size_single'], sharex=True)
    # 按 N, E, U 顺序
    components = [('dN', 'North (mm)', STYLE['colors'][0]),
                  ('dE', 'East (mm)', STYLE['colors'][1]),
                  ('dU', 'Vertical (mm)', STYLE['colors'][2])]

    for i, (col, label, color) in enumerate(components):
        ax = axes[i]
        ax.scatter(df['year'], df[col], s=STYLE['marker_size'], c=color, alpha=STYLE['alpha'], edgecolors='none')
        ax.set_ylabel(label, fontweight='bold')
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.grid(True, linestyle=':', alpha=0.3)
        apply_adaptive_ticks(ax, is_x=False)
        if i == 2:
            apply_adaptive_ticks(ax, is_x=True)
            ax.set_xlabel('Time (year)', fontweight='bold')

    plt.suptitle(f"Station: {station_name}", fontsize=12, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{station_name}.png"), dpi=STYLE['dpi'])
    plt.close()


def plot_component_summary(valid_stations, component, label, color, output_dir):
    """通用汇总大图绘制函数"""
    num_stations = len(valid_stations)
    cols = 5
    rows = int(np.ceil(num_stations / cols))

    fig, axes = plt.subplots(rows, cols, figsize=STYLE['fig_size_summary'])
    axes_flat = axes.flatten()

    print(f"[*] 正在生成总览大图: {label} ...")
    for i, (name, df) in enumerate(valid_stations):
        ax = axes_flat[i]
        ax.scatter(df['year'], df[component], s=0.5, c=color, alpha=0.4)
        ax.set_title(name, fontsize=10, fontweight='bold')

        # 极大简化矩阵图刻度以保整洁
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=3))
        ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=3))
        ax.tick_params(labelsize=8)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)

    # 隐藏多余格子
    for j in range(i + 1, len(axes_flat)):
        axes_flat[j].axis('off')

    plt.tight_layout(pad=2.5)
    file_name = f"A_Summary_{label.split(' ')[0]}.png"
    plt.savefig(os.path.join(output_dir, file_name), dpi=STYLE['dpi'])
    plt.close()


def main():
    setup_style()
    if not os.path.exists(FIGURE_OUTPUT): os.makedirs(FIGURE_OUTPUT)

    all_files = sorted(glob(os.path.join(DATA_DIR, "*.tenv3")))
    if not all_files:
        print("未找到数据。")
        return

    valid_stations = []
    # 1. 绘制单站图并收集有效数据
    for file_path in all_files:
        name = os.path.basename(file_path).split('.')[0]
        df = load_and_calculate_data(file_path)
        if df is not None and not df.empty:
            print(f"正在处理单站: {name}")
            plot_single_station(df, name, FIGURE_OUTPUT)
            valid_stations.append((name, df))

    # 2. 分别绘制三个分量的总览大图
    if valid_stations:
        # 北向总览 (North)
        plot_component_summary(valid_stations, 'dN', 'North (mm)', STYLE['colors'][0], FIGURE_OUTPUT)
        # 东向总览 (East)
        plot_component_summary(valid_stations, 'dE', 'East (mm)', STYLE['colors'][1], FIGURE_OUTPUT)
        # 垂直总览 (Vertical)
        plot_component_summary(valid_stations, 'dU', 'Vertical (mm)', STYLE['colors'][2], FIGURE_OUTPUT)

    print(f"\n[√] 任务完成！")
    print(f"单站图及 3 张总览图已保存至: {os.path.abspath(FIGURE_OUTPUT)}")


if __name__ == "__main__":
    main()