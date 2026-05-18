#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目名称: GPS 时间序列环境负荷修正对比分析 (Nature 风格)
文件描述:
    本脚本用于读取 UNR (University of Nevada, Reno) 的 .tenv3 格式 GPS 时间序列数据。本模块提供了一个面向对象的解决方案，
    用于定量评估非潮汐大气负荷 (NATL) 和非潮汐海潮负荷 (NOTL) . 对 GPS 时间序列观测噪声的抑制效果。它集成了数据解析、线性去趋势、RMS 统计以及高级学术制图功能。
    主要功能包括：
    1. 提取原始位移(整数+小数部分)并进行线性去趋势(Detrend)处理。
    2. 计算去除 NOTL (非潮汐海潮负荷) 和 NATL (非潮汐大气负荷) 后的修正序列。
    3. 对比原始序列与负荷修正序列在 North, East, Up 三个方向上的波动差异。
    4. 统计 RMS 降低率，定量评估负荷修正对观测噪声的抑制效果（正值表示修正有效，负值表示修正后噪声反而增加）。
    5. 采用 Nature 期刊审美：时序散点图 + 30天移动平均趋势线 + 侧边残差分布直方图。
    6. 学术制图：
        - 散点背景代表逐日解。
        - 粗实线代表 31 天移动平均趋势。
        - 侧边直方图对比残差分布的收敛性。

注：30天移动平均趋势线是为了让趋势更明显，否则都是散点图感受不直观。

数据计算逻辑 (单位: mm):
    - 原始位移 = (Integer + Decimal) * 1000
    - 修正位移 = (原始位移 - NOTL - NATL) * 1000 加去趋势
    - 索引映射 (0-indexed):
        Year: 2 | E: 7+8 | N: 9+10 | U: 11+12 | NOTL: 23,24,25 | NATL: 26,27,28

原理：去趋势：去掉了由于地质构造引起的长期线性速度（最小二乘线性回归实现）。
     负荷修正：去掉了由于大气压力（NATL）和非潮汐海水压力（NOTL）引起的短期和季节性波动。
     最终结果：你在图上看到的修正后序列（先负荷修正后去趋势），是既没有长期速度，也没有大气/海洋负荷干扰的“干净”信号。

依赖库: pandas, matplotlib, numpy, scipy
作者: SingyuTang
日期: 2026-04-13
版本: v2.0
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from glob import glob
from scipy import stats


class GNSSLoadingAnalyzer:
    """
    GNSS 环境负荷修正对比分析类 (Nature 风格)
    功能：读取 tenv3 数据、去趋势处理、计算负荷修正效果及高级可视化。
    """

    def __init__(self, data_dir="BD_GNSS_TimeSeries", output_dir="GPS_Advanced_Comparison"):
        # 路径配置
        self.data_dir = data_dir
        self.output_dir = output_dir

        # 绘图审美配置
        self.style = {
            "font_family": "Arial",
            "dpi": 300,
            "color_orig": "#333333",  # 原始：深灰色
            "colors_corr": ["#D62728", "#1F77B4", "#2CA02C"],  # N, E, U 修正色
            "marker_size": 1.0,
            "line_width": 1.6,
            "smooth_window": 31,  # 移动平均窗长 (天)
        }

        # 数据列索引定义 (0-indexed)
        # Year:2 | E:7,8 | N:9,10 | U:11,12 | NOTL:23,24,25 | NATL:26,27,28
        self.use_cols = [2, 7, 8, 9, 10, 11, 12, 23, 24, 25, 26, 27, 28]
        self.col_names = [
            'year', 'E_int', 'E_dec', 'N_int', 'N_dec', 'U_int', 'U_dec',
            'E_notl', 'N_notl', 'U_notl', 'E_natl', 'N_natl', 'U_natl'
        ]

        self._setup_matplotlib()
        self._ensure_dir()

    def _ensure_dir(self):
        """确保输出目录存在"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _setup_matplotlib(self):
        """配置符合 Nature 规范的绘图参数"""
        plt.rcParams.update({
            'font.sans-serif': [self.style['font_family'], 'DejaVu Sans'],
            'axes.linewidth': 1.0,
            'xtick.direction': 'in',
            'ytick.direction': 'in',
            'xtick.major.size': 4,
            'ytick.major.size': 4,
            'axes.labelsize': 9,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'savefig.bbox': 'tight',
            'pdf.fonttype': 42
        })

    @staticmethod
    def detrend_signal(time, signal):
        """线性去趋势并计算 RMS"""
        mask = ~np.isnan(signal)
        if np.sum(mask) < 2:
            return signal, 0
        slope, intercept, r_val, p_val, std_err = stats.linregress(time[mask], signal[mask])
        detrended = signal - (slope * time + intercept)
        rms = np.sqrt(np.nanmean(detrended ** 2))
        return detrended, rms

    def process_file(self, file_path):
        """加载并处理单个站点的负荷修正数据"""
        try:
            df = pd.read_csv(file_path, sep=r'\s+', header=0, usecols=self.use_cols, names=self.col_names)
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna().reset_index(drop=True)

            factor = 1000.0  # m -> mm
            res = pd.DataFrame({'year': df['year']})
            rms_info = {}

            for k in ['N', 'E', 'U']:
                # 原始位移计算
                raw_val = (df[f'{k}_int'] + df[f'{k}_dec']) * factor
                # 环境负荷项 (NOTL + NATL)
                loading_val = (df[f'{k}_notl'] + df[f'{k}_natl']) * factor

                # 1. 原始序列去趋势
                res[f'd{k}_orig'], rms_o = self.detrend_signal(df['year'].values, raw_val.values)
                # 2. 修正后序列去趋势 (原始 - 负荷)
                res[f'd{k}_corr'], rms_c = self.detrend_signal(df['year'].values, (raw_val - loading_val).values)

                # 计算平滑趋势 (Rolling Mean)
                res[f'd{k}_orig_sm'] = res[f'd{k}_orig'].rolling(window=self.style['smooth_window'], center=True).mean()
                res[f'd{k}_corr_sm'] = res[f'd{k}_corr'].rolling(window=self.style['smooth_window'], center=True).mean()

                rms_info[k] = {'orig': rms_o, 'corr': rms_c}

            return res, rms_info
        except Exception as e:
            print(f"   [!] 无法处理文件 {os.path.basename(file_path)}: {e}")
            return None, None

    def plot_comparison(self, df, rms_info, station_name):
        """生成时序-趋势-分布三合一对比图"""
        fig = plt.figure(figsize=(10, 8), dpi=self.style['dpi'])
        gs = fig.add_gridspec(3, 4, hspace=0.25, wspace=0.1)

        components = [
            ('dN', 'North (mm)', self.style['colors_corr'][0], 'N', 0),
            ('dE', 'East (mm)', self.style['colors_corr'][1], 'E', 1),
            ('dU', 'Up (mm)', self.style['colors_corr'][2], 'U', 2)
        ]

        for col_pre, label, color, key, row in components:
            # A. 时序主图 (左侧 3/4)
            ax_ts = fig.add_subplot(gs[row, :3])

            # 原始点与修正点
            ax_ts.scatter(df['year'], df[f'{col_pre}_orig'], s=self.style['marker_size'],
                          c=self.style['color_orig'], alpha=0.1, edgecolors='none')
            ax_ts.scatter(df['year'], df[f'{col_pre}_corr'], s=self.style['marker_size'],
                          c=color, alpha=0.2, edgecolors='none')

            # 趋势线
            ax_ts.plot(df['year'], df[f'{col_pre}_orig_sm'], color='black',
                       linewidth=1.0, alpha=0.7, label='Original (31d avg)')
            ax_ts.plot(df['year'], df[f'{col_pre}_corr_sm'], color=color,
                       linewidth=self.style['line_width'], label='Corrected (31d avg)')

            # 样式调整
            ax_ts.set_ylabel(label, fontweight='bold')
            ax_ts.axhline(0, color='gray', linewidth=0.5, linestyle='--')
            ax_ts.spines['top'].set_visible(False)
            ax_ts.spines['right'].set_visible(False)

            # RMS 标注
            ro, rc = rms_info[key]['orig'], rms_info[key]['corr']
            reduction = (ro - rc) / ro * 100
            ax_ts.text(0.01, 0.96, f"RMS Reduction: {ro:.2f} → {rc:.2f} mm ({reduction:+.1f}%)",
                       transform=ax_ts.transAxes, va='top', fontsize=8,
                       fontweight='bold', color=color, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

            if row == 0: ax_ts.legend(loc='upper right', frameon=False, ncol=2, fontsize=7)
            if row == 2: ax_ts.set_xlabel('Time (Decimal Year)', fontweight='bold')

            # B. 分布直方图 (右侧 1/4)
            ax_hist = fig.add_subplot(gs[row, 3], sharey=ax_ts)
            ax_hist.hist(df[f'{col_pre}_orig'].dropna(), bins=60, orientation='horizontal',
                         color=self.style['color_orig'], alpha=0.2, density=True)
            ax_hist.hist(df[f'{col_pre}_corr'].dropna(), bins=60, orientation='horizontal',
                         color=color, alpha=0.4, density=True)
            ax_hist.axis('off')

        plt.suptitle(f"GNSS Environmental Loading Correction: {station_name}", fontsize=12, fontweight='bold', y=0.96)

        save_path = os.path.join(self.output_dir, f"{station_name}_correction_analysis.png")
        plt.savefig(save_path)
        plt.close()

    def run(self):
        """启动批量分析任务"""
        files = sorted(glob(os.path.join(self.data_dir, "*.tenv3")))
        if not files:
            print(f"[!] 在目录 {self.data_dir} 中未发现数据文件。")
            return

        print(f"[*] 开始分析任务，共检测到 {len(files)} 个站点...")

        for f in files:
            name = os.path.basename(f).split('.')[0]
            print(f"   > 正在处理: {name}")
            data, rms = self.process_file(f)
            if data is not None:
                self.plot_comparison(data, rms, name)

        print(f"\n[√] 任务已完成。所有图件保存在: {os.path.abspath(self.output_dir)}")


# ==========================================
# 3. 使用示例 (Usage)
# ==========================================
if __name__ == "__main__":
    # 实例化分析器
    # 参数：数据所在目录，图片保存目录
    analyzer = GNSSLoadingAnalyzer(
        data_dir="../../01_Data_Raw/tenv3",
        output_dir="s3_results"
    )

    # 运行
    analyzer.run()