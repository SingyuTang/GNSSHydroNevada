"""
项目名称: GNSS 站点空间筛选与专业制图
文件名称: GNSSStationManager.py
文件描述:
    本模块通过解析内华达大学里诺分校 (UNR) 大地测量实验室的 DataHoldings 元数据，
    实现基于国家边界及自定义缓冲区的站点筛选，并提供学术风格的地图绘制功能。

主要功能:
    1. 元数据解析：高效读取并转换 NGL 格式的站点信息。
    2. 空间分析：自动获取 Natural Earth 高精度国家边界，并生成自定义度数 (Degree) 的缓冲区。
    3. 学术制图：绘制符合 Nature 期刊要求的地图（Arial 字体、高分辨率、多图层叠加、柔和缓冲区展示）。
    4. 多格式输出：支持 PDF (矢量)、PNG (高分位图)、SVG 等多种格式导出。

依赖环境:
    - pandas, geopandas: 数据处理与空间运算
    - matplotlib: 基础绘图
    - cartopy: 专业地理投影与要素加载
    - shapely: 几何体操作

使用说明:
    1. 确保已安装上述依赖：pip install pandas geopandas matplotlib cartopy shapely
    2. 初始化类：mgr = GNSSStationManager(file_path, target_country, buffer_val)
    3. 调用 load_data() 加载数据。
    4. 调用 process_selection() 进行筛选。
    5. 调用 export_maps() 生成地图。

作者: [SingyuTang]
日期: 2026-04-13
版本: v2.0
"""

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from shapely.geometry import Point
import matplotlib as mpl
import os

# --- Nature 出版规范全局设置 ---
mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica']
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['font.size'] = 7
mpl.rcParams['axes.linewidth'] = 0.5


class GNSSStationManager:
    """GNSS 站点筛选与专业绘图管理类"""

    def __init__(self, file_path, target_country, buffer_val=1.0):
        self.file_path = file_path
        self.target_country = target_country
        self.buffer_val = buffer_val
        self.gdf_all = None
        self.filtered_sites = None
        self.country_geom = None
        self.buffer_geom = None
        self.station_list = []

    def load_data(self):
        """稳健读取NGL格式数据"""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"找不到数据文件: {os.path.abspath(self.file_path)}")

        data = []
        with open(self.file_path, 'r', encoding='utf-8') as f:
            headers = f.readline().split()
            cols = headers[:11]
            for line in f:
                parts = line.split()
                if len(parts) >= 11:
                    data.append(parts[:11])

        df = pd.DataFrame(data, columns=cols)
        for c in ['Lat(deg)', 'Long(deg)']:
            df[c] = pd.to_numeric(df[c], errors='coerce')

        self.gdf_all = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df['Long(deg)'], df['Lat(deg)']),
            crs="EPSG:4326"
        )
        print(f"成功读取全球站点: {len(self.gdf_all)} 个")

    def _fetch_country_geometry(self):
        """从 Natural Earth 提取国家几何体 (模糊匹配)"""
        try:
            shpfilename = shpreader.natural_earth(resolution='50m', category='cultural', name='admin_0_countries')
            reader = shpreader.Reader(shpfilename)

            for record in reader.records():
                attrs = record.attributes
                # 检查多个可能的名称字段
                possible_names = [str(attrs.get(key, '')).lower() for key in
                                  ['NAME', 'NAME_EN', 'NAME_LONG', 'SOVEREIGNT', 'ADMIN']]

                if any(self.target_country.lower() in name for name in possible_names):
                    return record.geometry
            return None
        except Exception as e:
            print(f"提取地理边界出错: {e}")
            return None

    def process_selection(self):
        """执行空间筛选逻辑"""
        self.country_geom = self._fetch_country_geometry()
        if self.country_geom is None:
            print(f"错误: 无法在数据库中匹配到国家 '{self.target_country}'")
            return False

        # 创建缓冲区
        self.buffer_geom = self.country_geom.buffer(self.buffer_val)
        # 空间筛选
        self.filtered_sites = self.gdf_all[self.gdf_all.geometry.within(self.buffer_geom)]
        self.station_list = self.filtered_sites['Sta'].tolist()

        print("\n" + "=" * 40)
        print(f"筛选完成！国家: {self.target_country}")
        print(f"范围: {self.buffer_val}度 缓冲区 (约 {self.buffer_val * 111}km)")
        print(f"找到站点数量: {len(self.station_list)}")
        print("-" * 40)
        for i in range(0, len(self.station_list), 10):
            print(", ".join(self.station_list[i:i + 10]))
        print("=" * 40 + "\n")
        return True

    def export_maps(self, formats=['pdf', 'png'], show_buffer=True):
        """
        绘制并导出多种格式的地图
        :param formats: 格式列表，如 ['pdf', 'png', 'svg', 'jpg', 'tif']
        :param show_buffer: 是否在图上显示缓冲区
        """
        if self.filtered_sites is None:
            print("请先执行 process_selection()")
            return

        fig = plt.figure(figsize=(88 / 25.4, 100 / 25.4), dpi=300)
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

        # 设定显示范围
        minx, miny, maxx, maxy = self.buffer_geom.bounds
        ax.set_extent([minx - 0.6, maxx + 0.6, miny - 0.6, maxy + 0.6], crs=ccrs.PlateCarree())

        # --- 地理底图层 ---
        ax.add_feature(cfeature.OCEAN.with_scale('50m'), facecolor='#EBF4FB', zorder=0)
        ax.add_feature(cfeature.LAND.with_scale('50m'), facecolor='#F8F9F9', zorder=0)
        ax.add_feature(cfeature.LAKES.with_scale('50m'), facecolor='#EBF4FB', edgecolor='none', zorder=1)
        ax.add_feature(cfeature.RIVERS.with_scale('50m'), linewidth=0.3, edgecolor='#D0E2F2', zorder=1)

        # 邻国边界
        countries_shp = shpreader.natural_earth(resolution='50m', category='cultural', name='admin_0_countries')
        ax.add_geometries(shpreader.Reader(countries_shp).geometries(), ccrs.PlateCarree(),
                          facecolor='none', edgecolor='#E0E0E0', linewidth=0.2, zorder=2)

        # --- 缓冲区层 ---
        if show_buffer:
            ax.add_geometries([self.buffer_geom], crs=ccrs.PlateCarree(),
                              facecolor='#FF9800', alpha=0.06, edgecolor='none', zorder=2)
            ax.add_geometries([self.buffer_geom], crs=ccrs.PlateCarree(),
                              facecolor='none', edgecolor='#FF9800', linewidth=0.5,
                              linestyle=':', alpha=0.3, zorder=3)
            ax.plot([], [], color='#FF9800', linestyle=':', linewidth=0.8, alpha=0.6, label='Buffer area')

        # --- 目标国家层 ---
        ax.add_geometries([self.country_geom], crs=ccrs.PlateCarree(),
                          facecolor='#FFFFFF', edgecolor='#444444', linewidth=0.5, zorder=4)

        # --- 站点数据层 ---
        ax.scatter(self.gdf_all['Long(deg)'], self.gdf_all['Lat(deg)'],
                   color='#CCCCCC', s=0.1, alpha=0.2, transform=ccrs.PlateCarree(),
                   label='Global context', zorder=5)

        ax.scatter(self.filtered_sites['Long(deg)'], self.filtered_sites['Lat(deg)'],
                   color='#0072B2', s=8, edgecolor='white', linewidth=0.25,
                   transform=ccrs.PlateCarree(), zorder=10, label='Selected sites')

        # --- 装饰 ---
        gl = ax.gridlines(draw_labels=True, linewidth=0.2, color='#D1D1D1', linestyle='--', zorder=1)
        gl.top_labels, gl.right_labels = False, False
        gl.xlabel_style = {'size': 6, 'color': '#777777'}
        gl.ylabel_style = {'size': 6, 'color': '#777777'}

        plt.title(f"GNSS Stations: {self.target_country}", fontsize=8, pad=10, fontweight='bold')
        ax.legend(loc='lower right', frameon=True, fontsize=5.5, edgecolor='none', facecolor='white', framealpha=0.8)

        plt.tight_layout()

        # 批量导出多种格式
        base_name = f"{self.target_country}_Stations_Map"
        for fmt in formats:
            save_path = f"{base_name}.{fmt}"
            plt.savefig(save_path, bbox_inches='tight', format=fmt, dpi=300)
            print(f"已保存: {save_path}")

        plt.show()

    def save_station_list(self, output_path):
        """将筛选出的站名保存到 txt 文件，供 MATLAB 或其他程序读取"""
        if not self.station_list:
            print("[!] 警告：站名列表为空，未生成文件。")
            return

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for sta in self.station_list:
                    f.write(f"{sta}\n")
            print(f"[✔] 站名列表已导出至: {os.path.abspath(output_path)}")
        except Exception as e:
            print(f"[✘] 导出站名列表失败: {e}")


# ================= 使用示例 =================

if __name__ == "__main__":
    # 参数: 数据路径, 目标国家, 缓冲区度数
    target_country = "Bangladesh"
    buffer_degrees = 10
    stations_txt_path = f"../../01_Data_Raw/Selected_Stations_{target_country}.txt"

    gnss_manager = GNSSStationManager(
        file_path=r"../station_metadata/DataHoldings.txt",
        target_country=target_country,
        buffer_val=buffer_degrees
    )

    try:
        # 1. 加载数据
        gnss_manager.load_data()

        # 2. 处理筛选
        if gnss_manager.process_selection():
            # 3. 导出png格式的地图
            gnss_manager.export_maps(formats=['png'], show_buffer=True)

            # 4. 获取筛选出的站名列表 (extract_sites_lonlat.m脚本需要)
            my_list = gnss_manager.station_list
            # 保存站名列表供 MATLAB 使用
            gnss_manager.save_station_list(stations_txt_path)
    except Exception as e:
        print(f"运行过程中出错: {e}")