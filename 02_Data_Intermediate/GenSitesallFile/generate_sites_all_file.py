import pandas as pd
import os


def generate_sites_all_fixed_width(metadata_path, station_list_file, output_path):
    """
    生成固定宽度的 sites.all 文件
    格式要求：
    - 第一列 (Sta): 占1-4字符 (左对齐)
    - 空格: 第5位
    - 第二列 (Lon): 占6-14字符 (9位宽度，右对齐)
    - 空格: 第15位
    - 第三列 (Lat): 占16-23字符 (8位宽度，右对齐)
    """
    print("\n" + "=" * 50)
    print("[*] 正在生成固定宽度格式的 sites.all...")

    # 1. 读取站名列表
    if not os.path.exists(station_list_file):
        print(f"[✘] 错误：找不到文件 {station_list_file}")
        return

    with open(station_list_file, 'r') as f:
        target_stations = [line.strip().upper() for line in f if line.strip()]

    # 2. 读取原始 UNR 元数据
    try:
        # 只读取 Sta, Lat, Lon 三列
        df_meta = pd.read_csv(metadata_path, sep=r'\s+', usecols=[0, 1, 2],
                              names=['Sta', 'Lat', 'Lon'], header=0)
        df_meta['Sta'] = df_meta['Sta'].astype(str).str.upper()
    except Exception as e:
        print(f"[✘] 读取元数据失败: {e}")
        return

    # 3. 筛选数据
    df_selected = df_meta[df_meta['Sta'].isin(target_stations)].copy()

    # 4. 写入文件 (使用 f-string 强制固定宽度和对齐)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for _, row in df_selected.iterrows():
                # 格式解析：
                # {row['Sta']:<4}  : 左对齐，占4个字符
                # " "              : 第5位（空格）
                # {row['Lon']:>9.4f} : 右对齐，占9个字符，保留4位小数 (对应 6-14位)
                # " "              : 第15位（空格）
                # {row['Lat']:>8.4f} : 右对齐，占8个字符，保留4位小数 (对应 16-23位)

                line = f"{row['Sta']:<4} {row['Lon']:>9.4f} {row['Lat']:>8.4f}\n"
                f.write(line)

        print(f"[✔] 处理完成！共生成 {len(df_selected)} 个站点。")
        print(f"[✔] 目标文件: {os.path.abspath(output_path)}")

        # 打印比例尺辅助检查
        print("\n[*] 格式校验 (字符位置索引):")
        print("    12345678901234567890123")
        if len(df_selected) > 0:
            first_row = df_selected.iloc[0]
            preview = f"{first_row['Sta']:<4} {first_row['Lon']:>9.4f} {first_row['Lat']:>8.4f}"
            print(f"    {preview}")

    except Exception as e:
        print(f"[✘] 写入文件失败: {e}")


# =================================================================
# 执行
# =================================================================
if __name__ == "__main__":
    BASE_DIR = r"..\.."

    generate_sites_all_fixed_width(
        metadata_path=os.path.join(BASE_DIR, r"02_Data_Intermediate\station_metadata\DataHoldings.txt"),
        station_list_file=os.path.join(BASE_DIR, r"01_Data_Raw\Selected_Stations_Bangladesh.txt"),
        output_path=os.path.join(BASE_DIR, r"01_Data_Raw\sites.all")
    )