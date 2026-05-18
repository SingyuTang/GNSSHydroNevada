#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目名称: GNSS 时间序列子段提取与高级可视化工具 (Sub-period Extractor & Plotter)
文件描述:
    本模块提供了一个面向对象的解决方案，用于从内华达大学里诺分校 (UNR) 的 .tenv3 格式大地测量数据中
    提取指定时间段的位移子集。它集成了数据清洗、单位转换 (mm)、增量提取及符合 Nature 出版标准的学术制图功能。

主要功能特性:
    1. 时间维度转换：支持 YYYYMMDD 格式与 Decimal Year (十进制年份) 的双向转换。
    2. 位移量化：自动计算 North, East, Up 三分量位移，单位统一转换为毫米 (mm)。
    3. 自动化流水线：
        - 自动扫描指定目录下的所有 .tenv3 文件。
        - 仅处理在目标时间段内包含有效观测记录的站点。
        - 自动创建结果文件夹，分类存储 CSV 数据与可视化图像。
    4. 论文级绘图：采用 Nature 杂志风格，优化了线宽、颜色、字体及坐标轴排版。
    5. 数据统计：任务结束后自动返回并打印筛选后的站点名单。

依赖环境:
    - Python 3.x
    - pandas: 数据分析与处理
    - matplotlib: 核心制图引擎
    - numpy: 数值计算

作者: SingyuTang
日期: 2026-04-13
版本: v2.0
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
from glob import glob


class GNSSSubPeriodExtractor:
    """
    GNSS 指定日期范围数据提取与可视化类
    功能：从 .tenv3 文件中筛选子集、保存 CSV 并绘制三分量时序图
    """

    def __init__(self, input_dir, output_root="s2_results",
                 start_date="20200101", end_date="20210101"):
        # 路径配置
        self.input_dir = input_dir
        self.sub_data_dir = os.path.join(output_root, "data")
        self.sub_plot_dir = os.path.join(output_root, "figures")

        # 时间配置
        self.start_date_str = start_date
        self.end_date_str = end_date
        self.start_decimal = self._date_to_decimal(start_date)
        self.end_decimal = self._date_to_decimal(end_date)

        # 内部变量
        self.processed_stations = []  # 存放筛选后的站名列表

        # 绘图审美配置 (Nature 风格)
        self.style = {
            "font_family": "Arial",
            "dpi": 300,
            "colors": ["#E64B35", "#4DBBD5", "#00A087"],  # 分别对应 N, E, U
            "marker_size": 3.0,
            "alpha": 0.8,
            "fig_size": (8 / 2.54 * 2.5, 7 / 2.54 * 2.5),  # 适配单栏/双栏宽度
            "x_max_ticks": 6
        }

        self.use_cols = [2, 7, 8, 9, 10, 11, 12]
        self.col_names = ['decimal_year', 'E_int', 'E_dec', 'N_int', 'N_dec', 'U_int', 'U_dec']

        self._setup_directories()
        self._setup_matplotlib_style()

    def _setup_directories(self):
        """创建输出目录"""
        for d in [self.sub_data_dir, self.sub_plot_dir]:
            if not os.path.exists(d):
                os.makedirs(d)

    def _setup_matplotlib_style(self):
        """配置 Matplotlib 渲染参数"""
        plt.rcParams.update({
            'font.sans-serif': [self.style['font_family'], 'DejaVu Sans'],
            'axes.linewidth': 1.0,
            'xtick.direction': 'in',
            'ytick.direction': 'in',
            'axes.labelsize': 9,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'savefig.bbox': 'tight',
            'pdf.fonttype': 42
        })

    @staticmethod
    def _date_to_decimal(date_str):
        """YYYYMMDD 转换为 Decimal Year"""
        dt = datetime.strptime(str(date_str), "%Y%m%d")
        year = dt.year
        start_of_year = datetime(year, 1, 1)
        end_of_year = datetime(year + 1, 1, 1)
        return year + (dt - start_of_year).total_seconds() / (end_of_year - start_of_year).total_seconds()

    @staticmethod
    def _decimal_to_datetime(dec_year):
        """Decimal Year 转换为 datetime 对象"""
        year = int(dec_year)
        rem = dec_year - year
        base = datetime(year, 1, 1)
        total_seconds = (datetime(year + 1, 1, 1) - base).total_seconds()
        return base + timedelta(seconds=total_seconds * rem)

    def _process_single_file(self, file_path):
        """解析单个 .tenv3 文件并计算位移"""
        try:
            # 读取数据
            df = pd.read_csv(file_path, sep=r'\s+', header=0, usecols=self.use_cols, names=self.col_names)
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna()

            # 时间筛选
            mask = (df['decimal_year'] >= self.start_decimal) & (df['decimal_year'] <= self.end_decimal)
            sub_df = df[mask].copy()

            if sub_df.empty:
                return None

            # 转换单位为 mm 并对应日期
            res = pd.DataFrame()
            res['date_obj'] = sub_df['decimal_year'].apply(self._decimal_to_datetime)
            res['dN'] = (sub_df['N_int'] + sub_df['N_dec']) * 1000
            res['dE'] = (sub_df['E_int'] + sub_df['E_dec']) * 1000
            res['dU'] = (sub_df['U_int'] + sub_df['U_dec']) * 1000

            return res
        except Exception as e:
            print(f"   [!] Error reading {os.path.basename(file_path)}: {e}")
            return None

    def _plot_subperiod(self, df, station_name):
        """绘制三分量位移图"""
        n_points = len(df)
        fig, axes = plt.subplots(3, 1, figsize=self.style['fig_size'], sharex=True, dpi=self.style['dpi'])

        components = [('dN', 'North (mm)', self.style['colors'][0]),
                      ('dE', 'East (mm)', self.style['colors'][1]),
                      ('dU', 'Vertical (mm)', self.style['colors'][2])]

        for i, (col, label, color) in enumerate(components):
            ax = axes[i]
            ax.scatter(df['date_obj'], df[col], s=self.style['marker_size'],
                       c=color, alpha=self.style['alpha'], edgecolors='none')

            # 设置 Y 轴范围余量
            if not df[col].empty:
                y_min, y_max = df[col].min(), df[col].max()
                margin = (y_max - y_min) * 0.2 if y_max != y_min else 5.0
                ax.set_ylim(y_min - margin, y_max + margin)

            ax.set_ylabel(label, fontweight='bold')
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
            ax.grid(True, linestyle=':', alpha=0.3)

            # 日期格式化
            locator = mdates.AutoDateLocator(maxticks=self.style['x_max_ticks'])
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

        plt.suptitle(f"Station: {station_name} | {self.start_date_str}-{self.end_date_str} (N={n_points})",
                     fontsize=10, fontweight='bold', y=0.98)

        plt.tight_layout()
        save_path = os.path.join(self.sub_plot_dir, f"{station_name}_{self.start_date_str}_{self.end_date_str}.png")
        plt.savefig(save_path)
        plt.close()

    def run(self):
        """执行主循环"""
        all_files = sorted(glob(os.path.join(self.input_dir, "*.tenv3")))
        print(f"[*] Task Start: Range {self.start_date_str} to {self.end_date_str}")
        print(f"[*] Scanning {len(all_files)} files in {self.input_dir}...")

        self.processed_stations = []

        for file_path in all_files:
            station_name = os.path.basename(file_path).split('.')[0]
            data = self._process_single_file(file_path)

            if data is not None and len(data) > 0:
                self.processed_stations.append(station_name)
                print(f"   > Processing: {station_name} | Found {len(data)} epochs")

                # 保存结果 CSV
                csv_save = data.copy()
                csv_save['date_str'] = csv_save['date_obj'].dt.strftime('%Y%m%d')
                csv_save.to_csv(os.path.join(self.sub_data_dir, f"{station_name}_sub.csv"), index=False)

                # 绘图
                self._plot_subperiod(data, station_name)

        # 打印并总结
        print("\n" + "=" * 40)
        print(f"任务完成报告:")
        print(f" - 起始日期: {self.start_date_str}")
        print(f" - 结束日期: {self.end_date_str}")
        print(f" - 包含数据的站点总数: {len(self.processed_stations)}")
        print(f" - 站点列表: {', '.join(self.processed_stations)}")
        print("=" * 40 + "\n")

        return self.processed_stations


# ==========================================
# 3. 调用示例
# ==========================================
if __name__ == "__main__":
    # 实例化类
    extractor = GNSSSubPeriodExtractor(
        input_dir="../../01_Data_Raw/tenv3",  # 你的数据源目录
        output_root="s2_results",  # 输出根目录
        start_date="20200101",  # 开始日期
        end_date="20210101"  # 结束日期
    )

    # 运行并获取站名列表
    successful_list = extractor.run()

    # 你可以继续对这个列表进行后续处理
    print(f"主程序收到的站名列表: {successful_list}")