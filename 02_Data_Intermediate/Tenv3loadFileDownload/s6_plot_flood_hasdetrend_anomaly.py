#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目名称: GNSS 洪水载荷沉降异常分析系统 (全局去趋势 + 基准对齐版)
文件描述:
    本脚本用于提取并分析 2020 年夏季洪水期间，GNSS 站点发生的非线性地表形变。
    与原始序列分析不同，本版本引入了“全局去趋势”逻辑，以剥离长期构造运动对短期水文信号的干扰。

    核心功能与算法特性：
    1. 动态筛选：自动识别指定时段内有观测值的站点。
    2. 全局去趋势 (Global Detrending): 利用站点全历元观测数据进行线性回归，计算长期板块速度 (Tectonic Velocity)，
       并从 2020 年研究窗口中扣除线性项，确保提取的是纯粹的非线性水文载荷异常信号。
    3. 鲁棒性数据加载: 针对环境负荷修正项（NOTL/NATL）可能存在的空值，采用填充 0 的策略，
       确保位置信息点位不因修正项缺失而被整行剔除，保留了最完整的日解散点。
    4. 基准平移 (Zero-leveling): 以 2020 年 5 月（洪水发生前）的残差均值为零基准。
    5. 出版级可视化 (Nature Style):
       - 散点底层: 展示原始日解观测值及其噪声水平。
       - 趋势实线: 采用 7 天移动平均 (Rolling Mean) 拟合，解决数据“太淡、看不清”的痛点。
       - 矩阵总图: 自动生成全站点对比大图，并统一 Y 轴量程，使全区域站点洪水响应强度具备物理可比性。

数据映射逻辑 (0-indexed):
    Year: 2 | E: 7,8 | N: 9,10 | U: 11,12 | NOTL: 23-25 | NATL: 26-28
    计算公式 (mm): dU = [(U_int + U_dec) - U_notl - U_natl] * 1000

依赖环境: Python 3.x, pandas, matplotlib, numpy, scipy
作者: SingyuTang
日期: 2026-04-13
版本: v2.0 (Detrended + Publication Quality)
"""

import os
import sys
import time
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from glob import glob
from scipy import stats
from datetime import datetime, timedelta

from s2_extract_and_plot_subperiod import GNSSSubPeriodExtractor


class GNSSFloodDetrendAnalyzer:
    """GNSS 全局去趋势洪水分析管理类"""

    def __init__(self, data_dir, output_dir, stations=None):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.selected_stations = stations

        # 时段参数
        self.baseline_range = ("20200501", "20200531")
        self.display_range = ("20200501", "20200831")

        # 绘图配置
        self.style = {
            "font_family": "Arial",
            "dpi": 300,
            "colors": ["#D62728", "#1F77B4", "#2CA02C"],  # N, E, U
            "alpha_scatter": 0.3,
            "line_width": 2.5,
            "smooth_window": 7,
            "matrix_cols": 4
        }

        # 统一量程 (针对去趋势后的残差)
        self.y_limits = {
            'dN': (-12, 12),
            'dE': (-12, 12),
            'dU': (-50, 15)
        }

        self.use_cols = [2, 7, 8, 9, 10, 11, 12, 23, 24, 25, 26, 27, 28]
        self.col_names = ['year', 'E_int', 'E_dec', 'N_int', 'N_dec', 'U_int', 'U_dec',
                          'E_notl', 'N_notl', 'U_notl', 'E_natl', 'N_natl', 'U_natl']

        self._setup_style()
        if not os.path.exists(self.output_dir): os.makedirs(self.output_dir)

    def _setup_style(self):
        plt.rcParams.update({
            'font.sans-serif': [self.style['font_family'], 'DejaVu Sans'],
            'axes.linewidth': 1.0,
            'xtick.direction': 'in', 'ytick.direction': 'in',
            'savefig.bbox': 'tight', 'pdf.fonttype': 42
        })

    @staticmethod
    def _date_to_dec(date_str):
        dt = datetime.strptime(str(date_str), "%Y%m%d")
        s, e = datetime(dt.year, 1, 1), datetime(dt.year + 1, 1, 1)
        return dt.year + (dt - s).total_seconds() / (e - s).total_seconds()

    @staticmethod
    def _dec_to_dt(dec_year):
        year = int(dec_year)
        base = datetime(year, 1, 1)
        total_sec = (datetime(year + 1, 1, 1) - base).total_seconds()
        return base + timedelta(seconds=total_sec * (dec_year - year))

    def _load_and_detrend(self, file_path):
        """核心逻辑：加载数据、全局去趋势、计算基准"""
        try:
            df = pd.read_csv(file_path, sep=r'\s+', header=0, usecols=self.use_cols, names=self.col_names)
            for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')

            # 剔除坐标缺失行，填充负荷缺失值
            df = df.dropna(subset=['year', 'U_int', 'U_dec']).reset_index(drop=True)
            df.fillna(0, inplace=True)

            res = pd.DataFrame({'year_dec': df['year'], 'date_obj': df['year'].apply(self._dec_to_dt)})
            factor = 1000.0
            slopes = {}

            for k in ['N', 'E', 'U']:
                # 1. 计算原始改正后的位移
                raw_val = ((df[f'{k}_int'] + df[f'{k}_dec']) - df[f'{k}_notl'] - df[f'{k}_natl']) * factor
                # 2. 全局线性去趋势 (针对文件内所有数据点)
                slope, intercept, _, _, _ = stats.linregress(res['year_dec'], raw_val)
                res[f'd{k}_dt'] = raw_val - (slope * res['year_dec'] + intercept)
                slopes[k] = slope

            # 3. 基准面对齐 (以2020-05残差均值为准)
            b_s, b_e = self._date_to_dec(self.baseline_range[0]), self._date_to_dec(self.baseline_range[1])
            base_df = res[(res['year_dec'] >= b_s) & (res['year_dec'] <= b_e)]

            if base_df.empty: return None, None

            for k in ['N', 'E', 'U']:
                res[f'd{k}_rel'] = res[f'd{k}_dt'] - base_df[f'd{k}_dt'].mean()

            return res, slopes
        except Exception as e:
            print(f"   [!] 错误: {os.path.basename(file_path)} -> {e}")
            return None, None

    def _draw_axis(self, ax, df, k, color, label, is_summary=False):
        """通用绘图函数"""
        col = f'd{k}_rel'
        sm_val = df[col].rolling(window=self.style['smooth_window'], center=True, min_periods=1).mean()

        ax.scatter(df['date_obj'], df[col], s=10 if not is_summary else 4,
                   c=color, alpha=self.style['alpha_scatter'], edgecolors='none', zorder=2)
        ax.plot(df['date_obj'], sm_val, color=color, linewidth=self.style['line_width'] if not is_summary else 1.8,
                zorder=10)

        ax.axhline(0, color='black', lw=1.0, ls='-', zorder=1)
        ax.set_ylim(self.y_limits[f'd{k}'])
        ax.set_ylabel(label if not is_summary or (ax.get_subplotspec().is_first_col()) else "", fontsize=8,
                      fontweight='bold')
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.tick_params(labelsize=7)

    def run(self):
        """启动流水线"""
        files = sorted(glob(os.path.join(self.data_dir, "*.tenv3")))
        summary_cache = []

        print(f"[*] 启动去趋势分析任务... (基准: {self.baseline_range[0]})")

        for f in files:
            name = os.path.basename(f).split('.')[0]
            if self.selected_stations and (name not in self.selected_stations): continue

            # 加载、全局去趋势、对齐
            df_full, slopes = self._load_and_detrend(f)
            if df_full is None: continue

            # 截取显示时段
            d_s, d_e = self._date_to_dec(self.display_range[0]), self._date_to_dec(self.display_range[1])
            df_plot = df_full[(df_full['year_dec'] >= d_s) & (df_full['year_dec'] <= d_e)]

            if df_plot.empty: continue
            summary_cache.append((name, df_plot, slopes))

            # 绘图：单站
            self._plot_single_station(name, df_plot, slopes)
            print(f"   > 处理完成: {name} (Vel_U: {slopes['U']:.2f} mm/yr)")

        # 绘图：全站总览
        if summary_cache:
            self._plot_matrix(summary_cache)

        print(f"\n[√] 任务结束。结果保存在: {self.output_dir}")

    def _plot_single_station(self, name, df, slopes):
        fig, axes = plt.subplots(3, 1, figsize=(7, 8), sharex=True)
        comps = [('N', 'North (mm)', self.style['colors'][0]),
                 ('E', 'East (mm)', self.style['colors'][1]),
                 ('U', 'Vertical (mm)', self.style['colors'][2])]
        for i, (k, lbl, clr) in enumerate(comps):
            self._draw_axis(axes[i], df, k, clr, lbl)
            axes[i].text(0.02, 0.92, f"V_{k}: {slopes[k]:.2f} mm/yr", transform=axes[i].transAxes, fontsize=7,
                         fontweight='bold')

        axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        plt.suptitle(f"Detrended Flood Signal: {name}", fontsize=12, fontweight='bold')
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, f"{name}_detrend_flood.png"), dpi=self.style['dpi'])
        plt.close()

    def _plot_matrix(self, cache):
        print(f"[*] 正在生成全站矩阵总览图...")
        num = len(cache)
        cols = self.style['matrix_cols']
        rows = int(np.ceil(num / cols))
        fig = plt.figure(figsize=(cols * 3.5, rows * 5))

        for idx, (name, df, slopes) in enumerate(cache):
            for s_idx, (k, clr) in enumerate(
                    [('N', self.style['colors'][0]), ('E', self.style['colors'][1]), ('U', self.style['colors'][2])]):
                pos = (idx // cols) * (cols * 3) + (idx % cols) + (s_idx * cols) + 1
                ax = fig.add_subplot(rows * 3, cols, pos)
                lbl = k if idx % cols == 0 else ""
                self._draw_axis(ax, df, k, clr, lbl, is_summary=True)
                if s_idx == 0: ax.set_title(name, fontsize=10, fontweight='bold')
                if (idx // cols) == (rows - 1) and s_idx == 2:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                else:
                    ax.set_xticklabels([])

        plt.subplots_adjust(wspace=0.15, hspace=0.3)
        plt.savefig(os.path.join(self.output_dir, "A_Total_Detrended_Matrix.png"), dpi=self.style['dpi'],
                    bbox_inches='tight')
        plt.close()


def get_processed_station_list(mode="filtered", data_dir="", s_date="", e_date=""):
    """
    动态获取站点列表
    mode: "all" (全部文件) or "filtered" (时段内有有效数据的站点)
    """
    if mode == "all":
        files = glob(os.path.join(data_dir, "*.tenv3"))
        return sorted([os.path.basename(f).split('.')[0] for f in files])

    elif mode == "filtered":
        TEMP_DIR = "temp_check_detrend"
        print(f"[*] 正在预检时段 {s_date}-{e_date} 内的有效站点...")
        try:
            extractor = GNSSSubPeriodExtractor(
                input_dir=data_dir, start_date=s_date, end_date=e_date, output_root=TEMP_DIR
            )
            valid_list = extractor.run()
            return valid_list
        finally:
            if os.path.exists(TEMP_DIR): shutil.rmtree(TEMP_DIR)
    return []


# ==========================================
# 主程序入口 (Usage)
# ==========================================
if __name__ == "__main__":
    RAW_PATH = "../../01_Data_Raw/tenv3"
    OUT_PATH = "s6_results"

    # 洪水研究窗口
    START, END = "20200501", "20200831"

    # 1. 动态筛选站点
    target_sites = get_processed_station_list(
        mode="filtered",  # 如果想处理所有站请改为 "all"
        data_dir=RAW_PATH,
        s_date=START,
        e_date=END
    )

    # 2. 启动去趋势分析
    if target_sites:
        analyzer = GNSSFloodDetrendAnalyzer(
            data_dir=RAW_PATH,
            output_dir=OUT_PATH,
            stations=target_sites
        )
        # 可选：修改默认配置
        analyzer.baseline_range = ("20200501", "20200531")
        analyzer.display_range = (START, END)

        analyzer.run()