#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目名称: GNSS 洪水载荷提取算法对比 (去趋势 vs 不去趋势)
文件描述:
    本脚本用于对比研究 2020 年夏季洪水期间，两种预处理方法对沉降信号提取的影响，定量分析构造速度对短期极端水文事件信号提取的影响。
    1. 计算逻辑 (mm):
       dE = (Col8 + Col9) - Col24 - Col27
       dN = (Col10 + Col11) - Col25 - Col28
       dU = (Col12 + Col13) - Col26 - Col29
       - 趋势计算: 使用站点【全部历史数据】进行线性拟合，提取长期构造速度。
       - 背景值对齐: 选取 2020-05 均值作为 0 电平。
       - 站点过滤: 仅处理 SELECTED_STATIONS 列表中的站点。
    2. 对比方案:
       - 方法 A (蓝色/红色点): 先执行全序列线性去趋势 (Detrend)，再减去 2020-05 的背景均值。
       - 方法 B (灰色虚线/点): 不执行去趋势，直接减去 2020-05 的原始均值。
    3. 目的: 观察长期构造速度如何“污染”短期的水文载荷信号。

作者: SingyuTang
日期: 2026-04-13
"""


import os
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from glob import glob
from scipy import stats
from datetime import datetime, timedelta

from s2_extract_and_plot_subperiod import GNSSSubPeriodExtractor


class GNSSDetrendComparisonAnalyzer:
    """GNSS 去趋势效果对比分析管理类"""

    def __init__(self, data_dir, output_dir, stations=None,
                 baseline=("20200501", "20200531"),
                 display=("20200501", "20200831")):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.selected_stations = stations

        # 时段参数
        self.baseline_range = baseline
        self.display_range = display

        # 绘图审美配置
        self.style = {
            "font_family": "Arial",
            "dpi": 300,
            "colors_dt": ["#E64B35", "#4DBBD5", "#00A087"],  # N(红), E(蓝), U(绿)
            "color_raw": "#999999",  # 不去趋势对比色：浅灰色
            "marker_size": 4,
            "line_width": 1.2,
            "matrix_cols": 4
        }

        # 统一量程
        self.y_limits = {'dN': (-12, 12), 'dE': (-12, 12), 'dU': (-55, 15)}

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

    def _load_and_compare_process(self, file_path):
        """核心逻辑：同时计算 Raw 和 Detrended 两种序列"""
        try:
            df = pd.read_csv(file_path, sep=r'\s+', header=0, usecols=self.use_cols, names=self.col_names)
            for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna(subset=['year', 'U_int', 'U_dec']).reset_index(drop=True)
            df.fillna(0, inplace=True)  # 容错：负荷项缺失填充0

            res = pd.DataFrame({'year_dec': df['year'], 'date_obj': df['year'].apply(self._dec_to_dt)})
            factor, slopes = 1000.0, {}

            for k in ['N', 'E', 'U']:
                # 1. 计算原始改正后的位移 (Raw Displacement)
                raw_val = ((df[f'{k}_int'] + df[f'{k}_dec']) - df[f'{k}_notl'] - df[f'{k}_natl']) * factor
                res[f'd{k}_raw'] = raw_val

                # 2. 计算去趋势后的序列 (Detrended)
                slope, intercept, _, _, _ = stats.linregress(res['year_dec'], raw_val)
                res[f'd{k}_dt'] = raw_val - (slope * res['year_dec'] + intercept)
                slopes[k] = slope

            # 3. 5月基准面归零对齐
            b_s, b_e = self._date_to_dec(self.baseline_range[0]), self._date_to_dec(self.baseline_range[1])
            base_df = res[(res['year_dec'] >= b_s) & (res['year_dec'] <= b_e)]

            if base_df.empty: return None, None

            for k in ['N', 'E', 'U']:
                # 方式A: 去趋势后的相对值
                res[f'd{k}_dt_rel'] = res[f'd{k}_dt'] - base_df[f'd{k}_dt'].mean()
                # 方式B: 不去趋势的相对值
                res[f'd{k}_raw_rel'] = res[f'd{k}_raw'] - base_df[f'd{k}_raw'].mean()

            return res, slopes
        except Exception as e:
            print(f"   [!] 错误: {os.path.basename(file_path)} -> {e}")
            return None, None

    def _draw_axis(self, ax, df, k, color, label, is_summary=False):
        """对比绘图函数：同时绘制两条线"""
        # 1. 绘制 Method B (Raw: 灰色虚线 + 方块)
        ax.plot(df['date_obj'], df[f'd{k}_raw_rel'], color=self.style['color_raw'],
                linestyle='--', linewidth=0.8, alpha=0.4, zorder=1)
        ax.scatter(df['date_obj'], df[f'd{k}_raw_rel'], s=self.style['marker_size'],
                   marker='s', facecolors='none', edgecolors=self.style['color_raw'],
                   alpha=0.5, zorder=2)

        # 2. 绘制 Method A (Detrended: 彩色实线 + 圆点)
        ax.plot(df['date_obj'], df[f'd{k}_dt_rel'], color=color,
                linestyle='-', linewidth=self.style['line_width'], alpha=0.8, zorder=3)
        ax.scatter(df['date_obj'], df[f'd{k}_dt_rel'], s=self.style['marker_size'] + 1,
                   marker='o', color=color, alpha=0.9, edgecolors='white',
                   linewidths=0.2, zorder=4)

        ax.axhline(0, color='black', lw=0.8, ls='-', zorder=0)
        ax.set_ylim(self.y_limits[f'd{k}'])

        if not is_summary or (ax.get_subplotspec().is_first_col()):
            ax.set_ylabel(label, fontsize=8, fontweight='bold')

        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.tick_params(labelsize=7)

    def run(self):
        """执行全自动流水线"""
        files = sorted(glob(os.path.join(self.data_dir, "*.tenv3")))
        summary_cache = []
        print(f"[*] 启动对比分析任务... 基准: {self.baseline_range}, 显示: {self.display_range}")

        for f in files:
            name = os.path.basename(f).split('.')[0]
            if self.selected_stations and (name not in self.selected_stations): continue

            df_full, slopes = self._load_and_compare_process(f)
            if df_full is None: continue

            d_s, d_e = self._date_to_dec(self.display_range[0]), self._date_to_dec(self.display_range[1])
            df_plot = df_full[(df_full['year_dec'] >= d_s) & (df_full['year_dec'] <= d_e)]

            if df_plot.empty: continue
            summary_cache.append((name, df_plot))
            self._plot_single(name, df_plot, slopes)
            print(f"   > 对比处理完成: {name} (V_U: {slopes['U']:.2f} mm/yr)")

        if summary_cache: self._plot_matrix(summary_cache)
        print(f"\n[√] 任务全部结束。结果见: {self.output_dir}")

    def _plot_single(self, name, df, slopes):
        fig, axes = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
        comps = [('N', 'North (mm)', self.style['colors_dt'][0]),
                 ('E', 'East (mm)', self.style['colors_dt'][1]),
                 ('U', 'Vertical (mm)', self.style['colors_dt'][2])]

        for i, (k, lbl, clr) in enumerate(comps):
            self._draw_axis(axes[i], df, k, clr, lbl)
            axes[i].text(0.02, 0.92, f"Plate Vel: {slopes[k]:.2f} mm/yr", transform=axes[i].transAxes, fontsize=7,
                         fontweight='bold')
            if i == 0:
                axes[i].legend(['Raw', '', 'Detrended', ''], loc='upper right', frameon=False, ncol=2, fontsize=7)

        axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        plt.suptitle(f"Algorithm Contrast: {name}", fontsize=12, fontweight='bold')
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, f"{name}_contrast.png"), dpi=self.style['dpi'])
        plt.close()

    def _plot_matrix(self, cache):
        print(f"[*] 正在生成全站对比矩阵图...")
        num, cols = len(cache), self.style['matrix_cols']
        rows = int(np.ceil(num / cols))
        fig = plt.figure(figsize=(cols * 3.5, rows * 5.5))
        for idx, (name, df) in enumerate(cache):
            for s_idx, (k, clr) in enumerate([('N', self.style['colors_dt'][0]),
                                              ('E', self.style['colors_dt'][1]),
                                              ('U', self.style['colors_dt'][2])]):
                pos = (idx // cols) * (cols * 3) + (idx % cols) + (s_idx * cols) + 1
                ax = fig.add_subplot(rows * 3, cols, pos)
                self._draw_axis(ax, df, k, clr, k, is_summary=True)
                if s_idx == 0: ax.set_title(name, fontsize=10, fontweight='bold')
                if (idx // cols) == (rows - 1) and s_idx == 2:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                else:
                    ax.set_xticklabels([])

        plt.subplots_adjust(wspace=0.18, hspace=0.3)
        plt.savefig(os.path.join(self.output_dir, "A_Contrast_Summary_Matrix.png"), dpi=self.style['dpi'],
                    bbox_inches='tight')
        plt.close()


def get_station_list_dynamic(mode="filtered", data_dir="", s_date="", e_date=""):
    if mode == "all":
        files = glob(os.path.join(data_dir, "*.tenv3"))
        return sorted([os.path.basename(f).split('.')[0] for f in files])
    elif mode == "filtered":
        tmp = "temp_contrast_check"
        try:
            extractor = GNSSSubPeriodExtractor(input_dir=data_dir, start_date=s_date, end_date=e_date, output_root=tmp)
            return extractor.run()
        finally:
            if os.path.exists(tmp): shutil.rmtree(tmp)
    return []


# ==========================================
# 主程序
# ==========================================
if __name__ == "__main__":
    RAW_PATH = "../../01_Data_Raw/tenv3"
    OUT_PATH = "s7_results"

    # 洪水窗口与基准期
    START, END = "20200501", "20200831"
    BASE_S, BASE_E = "20200501", "20200531"

    # 1. 获取在洪水期有有效观测的站点
    target_list = get_station_list_dynamic(
        mode="filtered", data_dir=RAW_PATH, s_date=START, e_date=END
    )

    # 2. 启动对比分析
    if target_list:
        contrast_analyzer = GNSSDetrendComparisonAnalyzer(
            data_dir=RAW_PATH,
            output_dir=OUT_PATH,
            stations=target_list,
            baseline=(BASE_S, BASE_E),
            display=(START, END)
        )
        contrast_analyzer.run()