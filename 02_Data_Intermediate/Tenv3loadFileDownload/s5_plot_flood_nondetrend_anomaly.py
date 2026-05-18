#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目名称: GNSS 洪水载荷演变分析系统 (脚本中功能：时序数据没有去趋势+包含去除背景值)
文件描述:
    本模块是一个集成化的科研工具，专门用于提取、处理并可视化 2020 年夏季洪水期间
    GNSS 站点在垂直 (Up) 和水平 (North, East) 方向上的非构造性位移演变。

主要功能特性:
    1. 动态站点筛选：
       - 集成 GNSSSubPeriodExtractor 类，支持“全量处理”与“有效数据预检”两种模式。
       - 自动剔除在目标洪水时段内无观测记录的站点，确保输出结果的有效性。
    2. 高容错数据引擎：
       - 针对环境负荷修正项 (NOTL/NATL) 缺失的常见问题，采用“零值填充”策略，
         有效防止因模型数据滞后导致的观测散点稀疏或整行剔除。
    3. 核心计算逻辑：
       - 单位：毫米 (mm)。
       - 位移公式：Disp = (Observation) - (NATL) - (NOTL)。
       - 零基准对齐 (Baseline Alignment)：以洪水发生前夕 (如 2020-05) 的均值为 0 电平，
         直观反映洪水引发的额外地表沉降及水平运动。
       - 注：本脚本聚焦于极端事件的物理演变，未进行长期线性去趋势 (Detrend) 处理。
    4. 论文级制图标准 (Nature Style)：
       - 散点展示原始日解噪声，7天滑动平均线 (Rolling Mean) 勾勒物理形变骨架。
       - 强制统一 Y 轴量程，增强不同站点间沉降强度的空间对比性。
       - 自动生成 4 列排版的大型矩阵总览图 (Summary Matrix)，展示区域一致性。

注：时序只进行了负荷修正和扣除基准，并未进行去趋势处理。

列索引映射 (0-indexed):
    Year: 2 | E: 7+8 | N: 9+10 | U: 11+12 | NOTL: 23-25 | NATL: 26-28

依赖环境: Python 3.x, pandas, matplotlib, numpy
作者: SingyuTang
日期: 2026-04-13
版本: v2.0
"""


import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from glob import glob
import shutil
from datetime import datetime, timedelta

from s2_extract_and_plot_subperiod import GNSSSubPeriodExtractor

class GNSSFloodAnalyzer:
    """GNSS 洪水位移分析与可视化管理类"""

    def __init__(self, data_dir, output_dir, stations=None):
        # 路径配置
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.selected_stations = stations  # 如果为 None 则处理目录下所有文件

        # 时段配置 (默认 2020 洪水期)
        self.baseline_range = ("20200501", "20200531")
        self.display_range = ("20200501", "20200831")

        # 绘图审美配置
        self.style = {
            "font_family": "Arial",
            "dpi": 300,
            "colors": ["#D62728", "#1F77B4", "#2CA02C"],  # N, E, U
            "alpha_scatter": 0.35,
            "line_width": 2.5,
            "smooth_window": 7,
            "fig_size_single": (6, 7),
            "matrix_cols": 4
        }

        # 统一 Y 轴量程 (mm)
        self.y_limits = {
            'dN': (-10, 15),
            'dE': (-10, 15),
            'dU': (-70, 20)
        }

        # UNR .tenv3 数据定义
        self.use_cols = [2, 7, 8, 9, 10, 11, 12, 23, 24, 25, 26, 27, 28]
        self.col_names = ['year', 'E_int', 'E_dec', 'N_int', 'N_dec', 'U_int', 'U_dec',
                          'E_notl', 'N_notl', 'U_notl', 'E_natl', 'N_natl', 'U_natl']

        self._setup_style()
        if not os.path.exists(self.output_dir): os.makedirs(self.output_dir)

    def _setup_style(self):
        """设置绘图引擎"""
        plt.rcParams.update({
            'font.sans-serif': [self.style['font_family'], 'DejaVu Sans'],
            'axes.linewidth': 1.0,
            'xtick.direction': 'in',
            'ytick.direction': 'in',
            'savefig.bbox': 'tight',
            'pdf.fonttype': 42
        })

    @staticmethod
    def _date_to_dec(date_str):
        """日期转十进制年份"""
        dt = datetime.strptime(str(date_str), "%Y%m%d")
        s, e = datetime(dt.year, 1, 1), datetime(dt.year + 1, 1, 1)
        return dt.year + (dt - s).total_seconds() / (e - s).total_seconds()

    @staticmethod
    def _dec_to_dt(dec_year):
        """十进制年份转日期对象"""
        year = int(dec_year)
        base = datetime(year, 1, 1)
        total_sec = (datetime(year + 1, 1, 1) - base).total_seconds()
        return base + timedelta(seconds=total_sec * (dec_year - year))

    def _load_station_data(self, file_path):
        """稳健加载数据：处理负荷列缺失"""
        try:
            df = pd.read_csv(file_path, sep=r'\s+', header=0, usecols=self.use_cols, names=self.col_names)
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 仅在关键坐标列缺失时剔除行
            essential = ['year', 'E_int', 'E_dec', 'N_int', 'N_dec', 'U_int', 'U_dec']
            df = df.dropna(subset=essential).reset_index(drop=True)

            # 负荷模型列缺失则填0，保留观测散点
            load_cols = ['E_notl', 'N_notl', 'U_notl', 'E_natl', 'N_natl', 'U_natl']
            df[load_cols] = df[load_cols].fillna(0)

            res = pd.DataFrame({'year_dec': df['year'], 'date_obj': df['year'].apply(self._dec_to_dt)})
            factor = 1000.0

            # 计算位移 (毫米)
            for k in ['N', 'E', 'U']:
                res[f'd{k}_raw'] = ((df[f'{k}_int'] + df[f'{k}_dec']) - df[f'{k}_notl'] - df[f'{k}_natl']) * factor

            # 基准面对齐 (Baseline Correction)
            b_s, b_e = self._date_to_dec(self.baseline_range[0]), self._date_to_dec(self.baseline_range[1])
            base_df = res[(res['year_dec'] >= b_s) & (res['year_dec'] <= b_e)]

            if base_df.empty: return None

            for k in ['N', 'E', 'U']:
                res[f'd{k}_rel'] = res[f'd{k}_raw'] - base_df[f'd{k}_raw'].mean()

            return res
        except Exception as e:
            print(f"   [!] 无法读取 {os.path.basename(file_path)}: {e}")
            return None

    def _draw_axis(self, ax, df, component, color, label, is_summary=False):
        """统一的绘图逻辑"""
        # 滑动平均
        sm_val = df[f'd{component}_rel'].rolling(window=self.style['smooth_window'], center=True, min_periods=3).mean()

        # 散点
        ax.scatter(df['date_obj'], df[f'd{component}_rel'],
                   s=8 if not is_summary else 4,
                   c=color, alpha=self.style['alpha_scatter'], edgecolors='none', zorder=2)

        # 趋势线
        ax.plot(df['date_obj'], sm_val, color=color,
                linewidth=self.style['line_width'] if not is_summary else 1.8,
                alpha=1.0, zorder=10)

        ax.axhline(0, color='black', lw=0.8, ls='-', zorder=1)
        ax.set_ylim(self.y_limits[f'd{component}'])
        ax.set_ylabel(label, fontsize=8, fontweight='bold')
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.tick_params(labelsize=7)

    def run(self):
        """执行主处理流程"""
        all_files = sorted(glob(os.path.join(self.data_dir, "*.tenv3")))
        summary_cache = []

        print(f"[*] 开始洪水载荷演变分析任务...")

        for f in all_files:
            name = os.path.basename(f).split('.')[0]
            if self.selected_stations and (name not in self.selected_stations):
                continue

            # 加载
            df_full = self._load_station_data(f)
            if df_full is None: continue

            # 裁剪显示时段
            d_s, d_e = self._date_to_dec(self.display_range[0]), self._date_to_dec(self.display_range[1])
            df_plot = df_full[(df_full['year_dec'] >= d_s) & (df_full['year_dec'] <= d_e)]

            if df_plot.empty: continue
            summary_cache.append((name, df_plot))

            # 绘图：单站
            self._plot_single(name, df_plot)
            print(f"   > 处理完成: {name}")

        # 绘图：矩阵总览
        if summary_cache:
            self._plot_summary_matrix(summary_cache)

        print(f"\n[√] 所有任务完成。结果存放在: {self.output_dir}")

    def _plot_single(self, name, df_plot):
        """生成单站垂直对比图"""
        fig, axes = plt.subplots(3, 1, figsize=self.style['fig_size_single'], sharex=True)
        comps = [('N', 'North (mm)', self.style['colors'][0]),
                 ('E', 'East (mm)', self.style['colors'][1]),
                 ('U', 'Vertical (mm)', self.style['colors'][2])]

        for i, (k, lbl, clr) in enumerate(comps):
            self._draw_axis(axes[i], df_plot, k, clr, lbl)

        axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        plt.suptitle(f"Flood Displacement: {name}", fontsize=12, fontweight='bold', y=0.98)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, f"{name}_flood_evolution.png"), dpi=self.style['dpi'])
        plt.close()

    def _plot_summary_matrix(self, cache):
        """生成全站矩阵大图"""
        print(f"[*] 正在生成总览矩阵...")
        num_stations = len(cache)
        cols = self.style['matrix_cols']
        rows = int(np.ceil(num_stations / cols))

        fig = plt.figure(figsize=(cols * 3.5, rows * 5))

        for idx, (name, df_plot) in enumerate(cache):
            # 分别绘制 N, E, U 三行
            for s_idx, (k, clr) in enumerate([('N', self.style['colors'][0]),
                                              ('E', self.style['colors'][1]),
                                              ('U', self.style['colors'][2])]):
                # 计算子图位置
                pos = (idx // cols) * (cols * 3) + (idx % cols) + (s_idx * cols) + 1
                ax = fig.add_subplot(rows * 3, cols, pos)

                # 只有最左边显示标签
                label = k if idx % cols == 0 else ""
                self._draw_axis(ax, df_plot, k, clr, label, is_summary=True)

                # 标题仅在第一行
                if s_idx == 0: ax.set_title(name, fontsize=10, fontweight='bold')

                # 时间轴处理
                if (idx // cols) == (rows - 1) and s_idx == 2:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                    ax.xaxis.set_major_locator(mdates.DayLocator(interval=30))
                else:
                    ax.set_xticklabels([])

        plt.subplots_adjust(wspace=0.2, hspace=0.3)
        plt.savefig(os.path.join(self.output_dir, "A_Flood_Matrix_Full_Summary.png"), dpi=self.style['dpi'],
                    bbox_inches='tight')
        plt.close()


def get_station_list(mode="filtered", input_dir="", start_date="", end_date=""):
    """
    获取站名列表的工厂函数
    mode: "all" - 全部站点; "filtered" - 仅包含时段内有数据的站点
    """
    if mode == "all":
        print(f"[*] 模式: 获取目录下所有站点...")
        files = glob(os.path.join(input_dir, "*.tenv3"))
        return sorted([os.path.basename(f).split('.')[0] for f in files])

    elif mode == "filtered":
        TEMP_DIR = "temp_check"  # 定义临时目录名称
        print(f"[*] 模式: 仅获取在 {start_date}-{end_date} 期间有数据的站点...")

        try:
            extractor = GNSSSubPeriodExtractor(
                input_dir=input_dir,
                start_date=start_date,
                end_date=end_date,
                output_root=TEMP_DIR
            )

            # 获取有效列表
            valid_stations = extractor.run()
            return valid_stations

        except Exception as e:
            print(f"[-] 筛选过程中出现错误: {e}")
            return []

        finally:
            if os.path.exists(TEMP_DIR):
                shutil.rmtree(TEMP_DIR)
                print(f"[清理] 临时目录 '{TEMP_DIR}' 已被成功自动删除。")
    else:
        return []


# ==========================================
# 主程序入口 (Usage)
# ==========================================
if __name__ == "__main__":
    # --- 配置参数 ---
    RAW_DATA_PATH = "../../01_Data_Raw/tenv3"
    RESULT_PATH = "s5_results"

    # 洪水分析的时间范围
    FLOOD_START = "20200501"
    FLOOD_END = "20200831"

    # --- 第一步：确定站点列表 (两种方式切换) ---

    # 【方式一】：下载的所有站 (解除下面注释即可)
    # target_list = get_station_list(mode="all", input_dir=RAW_DATA_PATH)

    # 【方式二】：仅在洪水期间有观测数据的站 (更推荐，防止空图)
    target_list = get_station_list(
        mode="filtered",
        input_dir=RAW_DATA_PATH,
        start_date=FLOOD_START,
        end_date=FLOOD_END
    )

    print(f"\n[任务准备] 最终确定的待分析站点数量: {len(target_list)}")
    print(f"站点预览: {target_list[:10]}...")

    # --- 第二步：启动洪水演变分析器 ---
    if len(target_list) > 0:
        # 实例化之前的洪水分析类
        analyzer = GNSSFloodAnalyzer(
            data_dir=RAW_DATA_PATH,
            output_dir=RESULT_PATH,
            stations=target_list
        )

        # 配置分析器的时段 (确保与筛选时段一致)
        analyzer.baseline_range = ("20200501", "20200531")
        analyzer.display_range = (FLOOD_START, FLOOD_END)

        # 运行全自动分析和矩阵绘图
        analyzer.run()

        print(f"\n[√] 洪水演变分析圆满完成，结果见目录: {RESULT_PATH}")
    else:
        print("[!] 警告: 没有符合条件的站点可供分析。")