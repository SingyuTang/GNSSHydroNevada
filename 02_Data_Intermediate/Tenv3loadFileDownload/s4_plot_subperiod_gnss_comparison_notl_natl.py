#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目名称: GNSS 指定时段环境负荷修正对比分析工具 (Advanced Class Version)

文件描述:
    本模块实现了对指定时间窗口内 GNSS 数据的环境负荷 (NATL+NOTL) 修正效果评估。集成了子时段数据切片、线性去趋势、RMS 降低率计算、以及 Nature 风格的高级可视化。
    1. 遍历指定目录下的 .tenv3 文件，筛选出包含用户定义时间范围内的数据。
    2. 对筛选出的子时段数据进行线性去趋势（Detrending）处理。
    3. 计算原始(Original)与修正后(-NOTL-NATL)的残差序列。
    4. 采用 Nature 风格布局：散点背景 + 30天移动平均趋势线 + 右侧残差分布直方图。
    5. 对比原始序列与修正序列（的残差分布，计算 RMS 改善百分比。
    6. 学术制图：
        - 散点背景代表逐日解。
        - 粗实线代表 31 天移动平均趋势。
        - 侧边直方图对比残差分布的收敛性。
注：去趋势和负荷修正都是基于截取时间范围内的数据进行处理。30天移动平均趋势线是为了让趋势更明显，否则都是散点图感受不直观。

数据计算逻辑:
    - 原始 = (Integer + Decimal) * 1000 (mm)
    - 修正 = (原始 - NOTL - NATL) * 1000 (mm) 加去趋势

作者: SingyuTang
日期: 2026-04-13
版本: v2.0
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates
import numpy as np
from glob import glob
from scipy import stats
from datetime import datetime, timedelta


class GNSSSubPeriodLoadingAnalyzer:
    """GNSS 指定时段负荷修正分析类"""

    def __init__(self, data_dir, output_root="Analysis_Results",
                 start_date="20200101", end_date="20210101"):
        # 路径初始化
        self.data_dir = data_dir
        self.output_data_dir = os.path.join(output_root, "data")
        self.output_plot_dir = os.path.join(output_root, "figures")

        # 时间参数设置
        self.start_date_str = start_date
        self.end_date_str = end_date
        self.start_dec = self._date_to_decimal(start_date)
        self.end_dec = self._date_to_decimal(end_date)

        # 绘图审美配置
        self.style = {
            "font_family": "Arial",
            "dpi": 300,
            "color_orig": "#333333",
            "colors_corr": ["#D62728", "#1F77B4", "#2CA02C"],  # N, E, U
            "marker_size": 1.2,
            "line_width": 2.0,
            "smooth_window": 31,
            "x_max_ticks": 6
        }

        # 内部数据定义
        self.use_cols = [2, 7, 8, 9, 10, 11, 12, 23, 24, 25, 26, 27, 28]
        self.col_names = ['year', 'E_int', 'E_dec', 'N_int', 'N_dec', 'U_int', 'U_dec',
                          'E_notl', 'N_notl', 'U_notl', 'E_natl', 'N_natl', 'U_natl']

        self._setup_env()

    def _setup_env(self):
        """准备文件夹与绘图风格"""
        for d in [self.output_data_dir, self.output_plot_dir]:
            if not os.path.exists(d): os.makedirs(d)

        plt.rcParams.update({
            'font.sans-serif': [self.style['font_family'], 'DejaVu Sans'],
            'axes.linewidth': 1.0,
            'xtick.direction': 'in', 'ytick.direction': 'in',
            'axes.labelsize': 9, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
            'savefig.bbox': 'tight', 'pdf.fonttype': 42
        })

    @staticmethod
    def _date_to_decimal(date_str):
        dt = datetime.strptime(str(date_str), "%Y%m%d")
        year = dt.year
        s, e = datetime(year, 1, 1), datetime(year + 1, 1, 1)
        return year + (dt - s).total_seconds() / (e - s).total_seconds()

    @staticmethod
    def _decimal_to_datetime(dec_year):
        year = int(dec_year)
        rem = dec_year - year
        base = datetime(year, 1, 1)
        total_sec = (datetime(year + 1, 1, 1) - base).total_seconds()
        return base + timedelta(seconds=total_sec * rem)

    @staticmethod
    def _detrend_signal(time, signal):
        """线性去趋势并返回 RMS"""
        mask = ~np.isnan(signal)
        if np.sum(mask) < 2: return signal, 0
        slope, intercept, _, _, _ = stats.linregress(time[mask], signal[mask])
        detrended = signal - (slope * time + intercept)
        rms = np.sqrt(np.nanmean(detrended ** 2))
        return detrended, rms

    def _process_file(self, file_path):
        """核心计算：读取、切片、去趋势、平滑"""
        try:
            df = pd.read_csv(file_path, sep=r'\s+', header=0, usecols=self.use_cols, names=self.col_names)
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 1. 筛选时段
            df = df[(df['year'] >= self.start_dec) & (df['year'] <= self.end_dec)].dropna().reset_index(drop=True)
            if df.empty: return None, None

            # 2. 计算单位转换与修正
            factor = 1000.0  # m -> mm
            res = pd.DataFrame({'year_dec': df['year'], 'date_obj': df['year'].apply(self._decimal_to_datetime)})
            rms_info = {}

            for k in ['N', 'E', 'U']:
                raw = (df[f'{k}_int'] + df[f'{k}_dec']) * factor
                load = (df[f'{k}_notl'] + df[f'{k}_natl']) * factor

                # 去趋势
                res[f'd{k}_orig'], rms_o = self._detrend_signal(df['year'].values, raw.values)
                res[f'd{k}_corr'], rms_c = self._detrend_signal(df['year'].values, (raw - load).values)

                # 移动平均平滑
                res[f'd{k}_orig_sm'] = res[f'd{k}_orig'].rolling(window=self.style['smooth_window'], center=True).mean()
                res[f'd{k}_corr_sm'] = res[f'd{k}_corr'].rolling(window=self.style['smooth_window'], center=True).mean()

                rms_info[k] = (rms_o, rms_c)

            return res, rms_info
        except Exception as e:
            print(f"   [!] Error: {os.path.basename(file_path)} -> {e}")
            return None, None

    def _plot_advanced(self, df, rms_info, station_name):
        """绘制高级学术图表"""
        fig = plt.figure(figsize=(11, 9), dpi=self.style['dpi'])
        gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.1)

        components = [('dN', 'North (mm)', self.style['colors_corr'][0], 'N', 0),
                      ('dE', 'East (mm)', self.style['colors_corr'][1], 'E', 1),
                      ('dU', 'Vertical (mm)', self.style['colors_corr'][2], 'U', 2)]

        for col_pre, ylabel, color, key, row in components:
            # A. 时序趋势轴
            ax_ts = fig.add_subplot(gs[row, :3])
            ax_ts.scatter(df['date_obj'], df[f'{col_pre}_orig'], s=self.style['marker_size'],
                          c=self.style['color_orig'], alpha=0.15, edgecolors='none')
            ax_ts.scatter(df['date_obj'], df[f'{col_pre}_corr'], s=self.style['marker_size'], c=color, alpha=0.25,
                          edgecolors='none')

            ax_ts.plot(df['date_obj'], df[f'{col_pre}_orig_sm'], color='black', linewidth=1.0, alpha=0.7)
            ax_ts.plot(df['date_obj'], df[f'{col_pre}_corr_sm'], color=color, linewidth=self.style['line_width'])

            # RMS 统计展示
            ro, rc = rms_info[key]
            improve = (ro - rc) / ro * 100
            ax_ts.text(0.01, 0.96, f"RMS: {ro:.2f}→{rc:.2f} mm ({improve:+.1f}%)", transform=ax_ts.transAxes,
                       va='top', fontsize=8, fontweight='bold', color=color,
                       bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

            ax_ts.set_ylabel(ylabel, fontweight='bold')
            ax_ts.axhline(0, color='gray', linewidth=0.5, linestyle='--')
            ax_ts.spines['top'].set_visible(False)
            ax_ts.spines['right'].set_visible(False)
            ax_ts.xaxis.set_major_formatter(mdates.DateFormatter('%Y%m%d'))
            ax_ts.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=self.style['x_max_ticks']))

            if row == 2: ax_ts.set_xlabel('Date (YYYYMMDD)', fontweight='bold')

            # B. 残差分布直方图
            ax_hist = fig.add_subplot(gs[row, 3], sharey=ax_ts)
            ax_hist.hist(df[f'{col_pre}_orig'].dropna(), bins=50, orientation='horizontal',
                         color=self.style['color_orig'], alpha=0.2, density=True)
            ax_hist.hist(df[f'{col_pre}_corr'].dropna(), bins=50, orientation='horizontal', color=color, alpha=0.4,
                         density=True)
            ax_hist.axis('off')

        plt.suptitle(f"GNSS Correction: {station_name} | Period: {self.start_date_str}-{self.end_date_str}",
                     fontsize=12, fontweight='bold', y=0.97)

        save_path = os.path.join(self.output_plot_dir,
                                 f"{station_name}_contrast_{self.start_date_str}_{self.end_date_str}.png")
        plt.savefig(save_path)
        plt.close()

    def run(self):
        """执行主程序逻辑"""
        all_files = sorted(glob(os.path.join(self.data_dir, "*.tenv3")))
        print(f"[*] Task Start: {self.start_date_str} to {self.end_date_str}")

        success_list = []
        for f in all_files:
            name = os.path.basename(f).split('.')[0]
            data, rms = self._process_file(f)
            if data is not None:
                success_list.append(name)
                print(f"   > Processing: {name} (N={len(data)})")
                data.to_csv(os.path.join(self.output_data_dir, f"{name}_sub.csv"), index=False)
                self._plot_advanced(data, rms, name)

        print("\n" + "=" * 40)
        print(f"DONE! Total Processed: {len(success_list)}")
        print(f"Station List: {', '.join(success_list)}")
        print("=" * 40)
        return success_list


# ==========================================
# 3. 调用示例
# ==========================================
if __name__ == "__main__":
    analyzer = GNSSSubPeriodLoadingAnalyzer(
        data_dir="../../01_Data_Raw/tenv3",  # 原始 tenv3 文件夹
        output_root="s4_results",  # 结果总文件夹
        start_date="20200101",  # 开始日期
        end_date="20220101"  # 结束日期
    )

    # 启动任务
    site_list = analyzer.run()