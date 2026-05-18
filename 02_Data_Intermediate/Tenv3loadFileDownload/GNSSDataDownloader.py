"""
项目名称: GNSS 时间序列数据批量下载工具 (集成筛选版)
文件名称: GNSSDownloader.py
文件描述:
    本脚本作为下载执行端，通过调用父级目录下 GenSitesallFile 文件夹中的 GNSSStationManager 类，
    实现“自动筛选 -> 确认地图 -> 批量下载”的一键式工作流。

主要功能:
    1. 跨目录调用：动态添加系统路径，实现对不同文件夹下筛选类的无缝引用。
    2. 自动下载：自动从 UNR 服务器抓取筛选后站点的 .tenv3 时间序列文件。
    3. 健壮性保障：
        - 内置 HTTP 重试策略 (Retry Strategy)，应对网络波动。
        - 采用流式下载 (Stream Download)，防止内存溢出。
        - 增量下载逻辑 (Skip Existing)，支持断点续传。
    4. 安全机制：模拟浏览器 User-Agent，设置下载间隔延迟 (Delay)，防止 IP 被封禁。

目录结构要求:
    Project_Root/
    ├── GenSitesallFile/
    │   └── GNSSStationManager.py      # 被调用的筛选类
    └── Tenv3loadFileDownload/
        └── GNSSDownloader.py           # 当前脚本

依赖环境:
    - requests: 网络请求
    - urllib3: 重试逻辑配置
    - 及其它 GNSSStationManager 所需的环境

使用说明:
    1. 确保 metadata 元数据文件路径正确。
    2. 设置 TARGET_COUNTRY (如 "Bangladesh", "China")。
    3. 设置 BUFFER_VAL (1度约等于111km)。
    4. 运行脚本：程序将先显示筛选地图，关闭地图后自动开始下载数据。

作者: [SingyuTang]
日期: 2026-04-13
版本: v2.0 (跨目录集成版)
"""

import sys
import os
from pathlib import Path
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from GenSitesallFile.GNSSStationManager import GNSSStationManager
    print("成功从其他子文件夹导入 GNSSStationManager")
except ImportError as e:
    print(f"导入失败: {e}")

class GNSSDataDownloader:
    """
    GNSS 数据下载类：
    负责接收站点列表并从 UNR 实验室批量抓取 .tenv3 时间序列数据
    """

    def __init__(self, save_dir="BD_GNSS_TimeSeries"):
        self.save_dir = save_dir
        self.base_url_template = "https://geodesy.unr.edu/gps_timeseries/tenv3_loadpredictions/{}.tenv3"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        self.delay = 1.0  # 下载间隔(秒)
        self.timeout = 20  # 超时时间
        self.skip_existing = True

    def _get_robust_session(self):
        """配置带重试机制的请求会话"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def run_download(self, station_list):
        """执行下载任务"""
        if not station_list:
            print("[-] 下载取消: 传入的站点列表为空。")
            return

        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        session = self._get_robust_session()
        print(f"\n[*] 任务启动：目标目录 '{self.save_dir}'")
        print(f"[*] 计划下载数量: {len(station_list)}")

        log_stats = {"success": 0, "missing": 0, "fail": 0}

        for i, station in enumerate(station_list):
            station = station.strip().upper()
            file_name = f"{station}.tenv3"
            local_path = os.path.join(self.save_dir, file_name)
            url = self.base_url_template.format(station)

            # 断点续传检查
            if self.skip_existing and os.path.exists(local_path):
                print(f"[{i + 1}/{len(station_list)}] 跳过: {station} (文件已存在)")
                continue

            try:
                print(f"[{i + 1}/{len(station_list)}] 正在下载: {station} ... ", end="", flush=True)
                response = session.get(url, headers=self.headers, timeout=self.timeout, stream=True)

                if response.status_code == 200:
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=65536):
                            f.write(chunk)
                    print("成功 ✅")
                    log_stats["success"] += 1
                elif response.status_code == 404:
                    print("未找到 ❌")
                    log_stats["missing"] += 1
                else:
                    print(f"失败 ⚠️ (HTTP {response.status_code})")
                    log_stats["fail"] += 1

            except Exception as e:
                print(f"错误: {e}")
                log_stats["fail"] += 1

            # 防封延迟
            time.sleep(self.delay)

        # 打印报告
        print("\n" + "=" * 40)
        print("批量下载总结报告：")
        print(f"  - 成功下载: {log_stats['success']}")
        print(f"  - 站点缺失: {log_stats['missing']} (404)")
        print(f"  - 下载失败: {log_stats['fail']}")
        print("=" * 40)


# ==========================================
# 主程序逻辑：连接两个类
# ==========================================
if __name__ == "__main__":

    # --- 1. 使用筛选类获取站名 (调用 GNSSStationManager.py) ---
    # 这里的参数根据你的原始类定义来设置
    filter_manager = GNSSStationManager(
        file_path=r"../station_metadata/DataHoldings.txt",
        target_country="Bangladesh",
        buffer_val=10
    )

    # 加载并处理筛选
    filter_manager.load_data()
    if filter_manager.process_selection():

        # 绘图 (支持多格式)
        filter_manager.export_maps(formats=['png'], show_buffer=True)

        # 获取筛选出的列表
        target_list = filter_manager.station_list

        # --- 2. 使用下载类执行下载 ---
        downloader = GNSSDataDownloader(save_dir="../../01_Data_Raw/tenv3")
        downloader.run_download(target_list)
    else:
        print("筛选失败，请检查国家名称或元数据文件。")