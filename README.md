# GNSSHydroNevada：GNSS高精度地壳形变解算与处理系统

## 1. 项目简介 (Project Overview)

**GNSSHydroNevada** 是一个面向卫星大地测量学及水文地球物理学研究的综合性科研开源项目。该项目旨在高效处理由内华达大学里诺分校（UNR）内华达地学实验室（NGL）提供的 GNSS 高时间分辨率（日解）三维坐标时间序列。

系统集成了**自动化数据检索与空间筛选、地壳构造速度去趋势、多源地球物理环境负荷改正（非潮汐大气负荷 NTAL、非潮汐海洋负荷 NTOL、局地地表水文负荷 HYDL/MASC）、最小二乘时间序列线性与周期性拟合（LSF）及鲁棒性阶跃探测**等多项核心算法。项目最终服务于极端水文事件（如南亚/孟加拉国夏季洪水）引发的瞬时弹性地表形变反演工作。

------

## 2. 系统架构与目录结构 (Directory Structure)

整个项目采用模块化设计，区分原始数据、中间层处理与可视化、高阶拟合建模以及科研文档：

```text
GNSSHydroNevada/
├── 01_Data_Raw/                                 # 原始数据层
│   ├── tenv3/                                   # 存放下载的全球站点原始 *.tenv3/ *.tenv3load 文件
│   ├── Selected_Stations_Bangladesh.txt         # 经空间范围筛选出的目标区域（如孟加拉国）站点列表
│   └── sites.all                                # NGL 全球 GNSS 站点元数据索引
├── 02_Data_Intermediate/                        # 中间层处理与论文级可视化
│   ├── ConvertTenv3ToPos/                       # 坐标格式转换与背景对齐模块（MATLAB）
│   │   ├── convertTenv3ToPos_bg.m               # 核心转换函数：支持自定义背景参考时段去均值
│   │   └── main_convert_with_bg.m               # 批处理转换脚本（生成标准 *.pos 格式）
│   ├── GenSitesallFile/                         # 空间地理筛选算法引擎
│   │   ├── GNSSStationManager.py                # 站点元数据解析、国家/缓冲区边界空间筛选算法
│   │   └── generate_sites_all_file.py           # 自动化筛选执行脚本
│   ├── station_metadata/                        # 站点历史数据 holdings
│   └── Tenv3loadFileDownload/                   # 增强型负荷时序批量下载、洪水演变分析与高级算法对比（Python）
│       ├── GNSSDataDownloader.py                # 具备健壮 HTTP 重试与流式断点续传的批量下载引擎
│       ├── s2_extract_and_plot_subperiod.py     # 目标洪水期有效数据自动化预检与裁剪脚本
│       ├── s5_plot_flood_nondetrend_anomaly.py  # 洪水引发非构造瞬时形变演变分析（未去长期趋势）
│       ├── s7_plot_flood_detrend_comparison.py  # 核心研究算法：长期板块构造速度对短期瞬时信号污染的定量对比
		└── ...
├── 03_LSF_Processing/                           # 最小二乘拟合与时序分析建模层
│   └── 2lsf/                                    # MATLAB 鲁棒解算引擎
│       ├── lsf_main.m                           # 时序回归主程序（多站点、多历元循环）
│       ├── LeastSquare.m                        # 核心算子：趋势项、周年/半周年项、突变阶跃联合估计
│       ├── iqr_outlier.m / sigma_outlier.m      # 异常值剔除：基于四分位距（IQR）与 N-Sigma 的双重准则
│       ├── break_neu.m / ReadBreaks.m           # 硬件更换与地震引发的非连续突变阶跃项（Jump）配置与自动切分
│       └── plot_pbo_ts.m                        # 论文级多组分拟合残差可视化
└──README.md                                     # 用户指南
```

------

## 3. 系统全景架构与数据流向

整个科研工作流横跨 **Python 空间地学分析与高并发数据检索架构** 与 **MATLAB 大地测量学高阶矩阵反演解算引擎**，形成互补的数据流闭环：

```
【阶段一：空间筛选与元数据重构】
   DataHoldings.txt + 边界缓冲区边界 (Python: GNSSStationManager)
                     │
                     ▼ 产出目标站点列表 (*.txt)
   生成固定列宽元数据索引文件 (Python: generate_sites_all_file) ──► 产出 sites.all

【阶段二：鲁棒型时序批量下载】
   高可用流式增量下载引擎 (Python: GNSSDataDownloader) ──► 获取 NGL 增强型 *.tenv3/tenv3load 原始时序

【阶段三：负荷解耦、基准平移与格式转换】
   (MATLAB: main_convert_with_bg & convertTenv3ToPos_bg)
   解析原始时序 ──► 扣除 NTAL/NTOL 负荷模型 ──► 指定时段零电平对齐 ──► 导出标准 7 列 *.pos 矩阵
                     │
                     ▼ (可选同步运行：Python s1-s7 洪水期高频非线性异常诊断工具链)

【阶段四：多组分联合最小二乘建模与鲁棒解算】
   (MATLAB LSF 引擎: lsf_main)
   读取 *.pos + 阶跃事件流 (*_break.neu) ──► 联合最小二乘反演 (LeastSquare) 
                     │
                     ├─► 嵌套式双准则粗差过滤 (iqr_outlier & sigma_outlier)
                     │
                     ▼ 滤波归一化收敛
   产出参数回归报告 (*_report.txt) 与 纯净非线性地学残差分量 (*.north / *.east / *.up)
```

------

## 4. 运行指南：全流程五大核心阶段

### 阶段一：空间边界收敛与元数据重构 (Python)

该阶段解决在全球高密度GNSS网络中，如何精准、高效地抽离出特定地球物理研究区域（如孟加拉湾、北美流域）的目标观测群落，并重构兼容传统解算框架的基础索引。

#### Step 1: 边界收敛与空间缓冲区裁剪

运行 `GNSSStationManager.py`，系统将自动检索内置的全球日解站点元数据，通过 `cartopy` 空间库获取高精度国家边界，并以自定义度数（Degree）向外构建几何缓冲区。

```
python GNSSStationManager.py
```

- **核心机制**：利用 `geopandas` 建立 `EPSG:4326` 地理坐标系空间点要素，执行 `.within(buffer_geom)` 空间拓扑包络线判定。自动剔除大洋、无关陆块的离群点，生成目标区域精简站点清单（如 `Selected_Stations_Bangladesh.txt`），并同步导出可直接用于学术论文发表的高分辨率地理空间分布图。

#### Step 2: 面向 legacy 软件的固定列宽元数据重构

运行 `generate_sites_all_file.py`，将精简的站点清单转化为地球物理高阶解算框架（如 Fortran I/O 标准）所需的严苛空间网格索引。

```
python generate_sites_all_file.py
```

- **核心机制**：利用 Python 字符流格式化方法（`f-string`），丢弃常规的分隔符，强制约束各数据列的空间物理跨度：站名占1-4字符（左对齐），第5位为空格，经度占6-14字符（右对齐，强制保留4位小数），第15位为空格，纬度占16-23字符（右对齐，强制保留4位小数）。

------

### 阶段二：鲁棒型高丰度负荷时序批量检索 (Python)

该阶段通过网络引擎，从内华达大学里诺分校（UNR）实验室的高并发服务器上抓取包含多源地球物理改正项的增强型数据集。

#### Step 3: 执行带断点续传的流式检索

运行 `GNSSDataDownloader.py`，批量异步抓取增强型 `.tenv3load` 负荷预测序列。

```
python GNSSDataDownloader.py
```

- **核心机制**：内置由 `urllib3` 支持的**指数退避（Backoff Factor）重试策略**，能智能拦截并缓冲因高频抓取导致的 `429` 访问限制或 `500/502` 网络瞬时抖动。
- **增量安全保护**：采用流式传输分块单块写入技术（`chunk_size=65536`），防止单文件大吞吐导致内存溢出。激活增量逻辑（`skip_existing=True`），自动对比本地文件大小与完整性，支持完全断点续传，防止重复下载。

------

### 阶段三：基准归零、负荷解耦与标准 `.pos` 格式转换 (MATLAB)

原始下载的 `.tenv3load` 数据无法直接输入回归引擎，必须在 MATLAB 下完成单位缩放、多源负荷剥离与零电平基准对齐。

#### Step 4: 运行批处理标准化转换

在 MATLAB 命令窗口或总控制台中配置研究时段与背景时段参数，运行 `main_convert_with_bg.m`。它将循环调用底层高吞吐量解析算子 `convertTenv3ToPos_bg.m`。

```
run('main_convert_with_bg.m')
```

- **核心解耦算法**：利用 `textscan` 级联抓取原始观测值与地球物理改正预测项。系统读取原始单日解三维坐标的分数项与整数项，将其还原为以米为单位的总位移，随后在三维物理轴线上精确解耦并扣除由德国地学中心（GFZ）LSDM 模型计算的非潮汐大气负荷（NTAL）与非潮汐海洋负荷（NTOL）高频气象干扰：  \text{Net}_U(t) = \left[ U_{int}(t) + U_{dec}(t) \right] - U_{ntal}(t) - U_{ntol}(t)  
- **零基准面平移校正（Zero-leveling Offset）**：为精确捕捉局部突发载荷事件的相对变化量，用户可自定义平稳的背景范围（如突发大洪水爆发前的 5 月份）。系统将计算该参考窗口内的净位移均值（自动执行 `omitnan` 规避硬件丢包污染）：  \text{Mean}_U = \langle \text{Net}_U(t) \rangle_{t \in \text{Baseline}}  全时序统一减去该背景静态偏移量，并全量放大 1000 倍，将物理尺度由米（m）标准化转化为毫米（mm），最终导出规范的 7 列 `.pos` 大地测量日解序列矩阵。

> 💡 **科研诊断工具链（Python 脚本 s1-s7 系列）**：
>
> 在此阶段，系统提供了并行的 Python 可视化分析套件（`s1` 至 `s7` 脚本）。其中 `s5_plot_flood_nondetrend_anomaly.py` 和 `s6_plot_flood_hasdetrend_anomaly.py` 分别代表了“不去长期趋势”与“全局去趋势”下瞬时地表弹性形变的响应状态。而核心科研对比脚本 `s7_plot_flood_detrend_comparison.py` 则通过**双算法同轴并联对撞可视化**，直观揭示并论证了在提取短期高频地表载荷（如极端洪涝）时，扣除长期构造板块运动速率趋势（Plate Tectonic Velocity）的科学迫切性，防止短期瞬时水文信号受到构造漂移的“信号污染”。

------

### 阶段四：多组分联合最小二乘建模与鲁棒阶跃解算 (MATLAB LSF)

这是整个系统最具确定性的核心回归引擎。它读取标准 `.pos` 时序与已知阶跃事件流（`*_break.neu`），全面解决长期板块运移速度、季节性周期震荡以及非连续性突变阶跃量的联合估计。

#### Step 5: 启动高阶参数反演回归

在 MATLAB 中配置输入数据路径，运行回归主控程序 `lsf_main.m`（或定制版 `lsf_main_custom.m`，`lsf_main.m`的高阶版，除计算up方向外，还可计算east和north方向数据）。

```
run('lsf_main.m')
```

#### ① 数学物理建模算子 (`LeastSquare.m`)

回归引擎构建的广义大地测量学时间序列非线性联合回归方程为：

y(t) = a + b \cdot t + \sum_{i=1}^{N_j} \Delta j_i \cdot H(t - t_i) + \sum_{k=1}^{2} \left[ C_k \cdot \cos(\omega_k t) + S_k \cdot \sin(\omega_k t) \right] + \varepsilon(t)

- 各组分物理涵义

  ：

  - a: 历元截距（静态标称参考位置）。
  - b: **长期构造速度（Linear Tectonic Velocity）**，代表地壳构造运动的长期线性趋势。
  - \Delta j_i: 第 i 个**突变阶跃项量值（Jump Magnitude）**。当硬件设备更换（如接收机、天线升级）或大地震突发导致坐标非连续性跳跃时，通过 `ReadBreaks.m` 自动检索阶跃历元 t_i，通过赫维赛德阶跃函数（Heaviside Step Function）H(t - t_i) 进行整体平移估计与修正。
  - C_k, S_k: 周期震荡系数。k=1 对应周年项（\omega_1 = 2\pi），k=2 对应半周年项（\omega_2 = 4\pi），用于吸收由宏观大尺度地表流体（如常规季节性气压、季节性地下水运移）引起的简谐地壳弹性摆动。

- **反演解算**：系统自动构建长达数千行的观测方程设计矩阵 A 及权矩阵 P，执行基于非线性约束的最小二乘参数反演：  X = (A^T P A)^{-1} A^T P L  从而在一次矩阵求逆中，实现所有未知参数（截距、速度、各个阶跃量、周期项振幅与相位）的无偏联合估计。

#### ② 嵌套式双准则粗差剥离引擎 (`iqr_outlier.m` & `sigma_outlier.m`)

由于GNSS日解序列易受到高频多路径效应、对流流体延迟残余以及硬件周跳等随机噪声污染，回归引擎内嵌了高鲁棒性的双重数据清洗机制，进行多轮迭代解算：

- **第一层：全球粗差剥离 (`iqr_outlier.m`)**  计算拟合残差的统计四分位距（Interquartile Range, IQR），定义上四分位数为 Q_3，下四分位数为 Q_1。构建强约束判定边界：  [\text{Threshold}] = [Q_1 - 1.5 \times \text{IQR}, \ Q_3 + 1.5 \times \text{IQR}]  凡超出该边界的残差离群点将被标记为粗差并予以剔除。该方法对未知分布的随机噪声具有极佳的稳健性。
- **第二层：局域高斯滤波 (`sigma_outlier.m`)**  在第一层清洗的基础上，启动移窗高斯 N\sigma 准则（通常设为 3\sigma）。计算局部序列的标准差 \sigma，若残差 \left| \varepsilon(t) \right| > 3\sigma，则将该历元从权重矩阵中剥离。通过双准则交尾迭代，确保回归系数的鲁棒性。

#### ③ 滤波输出与科研成图 (`WrtResult.m` & `plot_pbo_ts.m`)

- **统计报告归档**：解算收敛后，调用 `WrtResult.m` 算子，按照严格的学术规范将解算得到的板块线性速度（mm/yr）、周年/半周年项的精确物理振幅（Amplitude）与相位（Phase）、以及阶跃修复量写入最终生成的成果报告（如 `BNTL_up_report.txt`）。
- **论文级残差导出**：将原始序列彻底扣除长期速度项、确定性突变阶跃项以及季节性周期简谐项后，提取出高纯度的非线性地学形变残差，分类导出为独立的形变分量文件（`*.north`, `*.east`, `*.up`）。
- **成图渲染**：调用 `plot_pbo_ts.m`，自动生成包含“原始散点、联合拟合曲线、去异常后纯净残差序列”的三层联动学术成图，满足国际高水平期刊的直接投递标准。

------

## 5. 全流程核心字段与格式转换规范

为了确保多语言（Python/MATLAB）在全生命周期内无缝对接，系统严格遵循以下底层列索引映射与数据格式标准：

### 5.1 原始数据读取映射（0-Indexed，Python 规范）

在 Python 引擎（`s1-s7`、`GNSSDataDownloader`）中，对日解增强序列的列抓取规范如下：

- `col 2` : 十进制年份（`decimal_year`）
- `col 7`, `col 8` : 东向格网坐标整数部分（`E_int`）与分数项部分（`E_dec`）
- `col 9`, `col 10` : 北向格网坐标整数部分（`N_int`）与分数项部分（`N_dec`）
- `col 11`, `col 12` : 垂直方向坐标整数部分（`U_int`）与分数项部分（`U_dec`）
- `col 23, 24, 25` : 德国地学中心 ESMGFZ 非潮汐海潮负荷（NTOL）三维位移预测分量
- `col 26, 27, 28` : 德国地学中心 ESMGFZ 非潮汐大气负荷（NTAL）三维位移预测分量

### 5.2 中间层标准化输出格式（MATLAB 导出，`.pos` 标准）

经阶段三处理后，导出的标准 `.pos` 时间序列矩阵，采用标准 ASCII 码存储，每行固定为 **7 列**。各列定义及物理单位严格限定如下：

\begin{bmatrix} \text{Column 1} & \text{Column 2} & \text{Column 3} & \text{Column 4} & \text{Column 5} & \text{Column 6} & \text{Column 7} \\ \text{Date (yyyymmdd)} & \text{N (mm)} & \text{E (mm)} & \text{U (mm)} & \sigma_N \text{ (mm)} & \sigma_E \text{ (mm)} & \sigma_U \text{ (mm)} \end{bmatrix}

- **列 1**：8位连续标量数值型日期（如 `20200715`）。
- **列 2, 3, 4**：已解耦扣除大尺度 NTAL/NTOL 环境负荷、且经过指定时段零基准对齐后的北（North）、东（East）、垂直（Up）三维**净形变残差相对位移**（单位：**mm**）。
- **列 5, 6, 7**：单日解对应的北、东、垂直三方向标称标准差中误差（单位：**mm**），用于作为最小二乘解算矩阵中随机权矩阵 P 的定权依据（通常权倒数与标准差平方成正比）。

### 5.3 （附）基础 `.tenv3` 格式规范

`.tenv3`（UNR Graticule distance coordinates）是 Blewitt 等（2024）提出的高精度格网化时序格式，相比传统 UTM 系统避免了越带投影变形，北方向精确至 1 微米级。

- **第 1-6 列**：站名（4字节大写）、日期、十进制年份、简化儒略日（MJD）、GPS 周、周内天数。
- **第 7-13 列**：格网纵横坐标。采用**整数部分 + 小数部分**的级联存储设计（如 `E_int` 与 `E_dec`）。**重要特性**：在常规形变下（<10米），整数部分严格保持锁死不动，小数部分允许超出 `[-1, 1]` 边界。
- **核心制图逻辑**：**在处理局地日常形变序列时，可直接提取并分析其分数项（Fractional portion），有效避免传统浮点数高阶位截断带来的精度损失！** 仅当序列发生跨大洲级别的超大 jump（>10米）时，整数部分才会重新初始化。
- **第 21-23 列**：名义名义纬度、经度、高程（Nominal Coordinates）。

### 5.4（附） 增强型 `.tenv3load` 负荷改正格式规范

NGL 官方提供的负荷预测文件在常规 23 列的基础上，在其后追加了由德国地学中心（GFZ）基于 0.5° 格网陆地表面水文模型（LSDM，强迫场为 ECMWF 运营气象数据）计算并通过双三次样条拟合（Spline Interpolation）提取到 GNSS 站点的位移改正三维数组（单位：m）：

- **第 24-26 列 (NTAL)**：非潮汐大气负荷（Non-Tidal Atmospheric Loading）东、北、垂直三方向位移预测值。
- **第 27-29 列 (NTOL)**：非潮汐海洋负荷（Non-Tidal Ocean Loading）预测位移三方向。
- **第 30-32 列 (HYDL)**：LSDM 全球地表水文负荷（Terrestrial Water Storage Hydrological Loading）预测形变。
- **第 33-35 列 (MASC)**：基于 GRACE 空间卫星 Mascon 解决方案推演得到的宏观全球水文水体形变预测（注：2002年 GRACE 卫星发射前数据采用长期均值与季节震荡外推）。
- **第 36-41 列**：全球及北美典型大型湖泊/水库水体载荷引起的局地弹性位移预测。

------

## 6. 学术可视化规范

系统内所有绘图模块均内嵌了高学术标准的渲染参数。若要微调图件，须严格遵循以下审美约束：

1. **多组分空间矩阵大图排版**：采用统一量程约束（Y 轴垂直方向强制锁定在 `[-55, 15] mm` 区域内），禁止各站点子图自适应缩放，以便直接进行宏观形变强度的空间物理对比。
2. **物理演变骨架抽离**：图件背景散点（代表原始单日解噪声）通过降低透明度（`alpha=0.3` 或 `0.35`）进行弱化，而上层覆盖经过 7 天（洪水期短窗口高频提取）或 31 天（长期环境负荷评估趋势展示）的**中心对称滑动移窗平均线（Rolling Mean, Center=True）**，用粗实线勾勒出深层弹性质量动力学演化的物理骨架。
3. **字体与图形输出标准**：系统底层全面锁死 `Arial` 或 `Helvetica` 现代无衬线字体。所有图形在导出时均执行 `bbox_inches='tight'` 自动剪裁边缘白边，PDF 矢量图全面配置 `pdf.fonttype=42`（即 TrueType 字体嵌入），防止后期导入 Adobe Illustrator 等专业排版软件时发生字体缺失或解析变形，完全对接国际顶尖期刊的出版审稿要求。

## 7.文件下载链接指南

NGL 增强型 `.tenv3load` 时间序列数据：https://geodesy.unr.edu/gps_timeseries/tenv3_loadpredictions/

站点历史数据文件-DataHoldings.txt：https://geodesy.unr.edu/NGLStationPages/DataHoldings.txt

出故障的站点列表-step.txt：https://geodesy.unr.edu/NGLStationPages/steps.txt

NGL 官方格式规范指南：[基础格式文档README_tenv3.txt](https://geodesy.unr.edu/gps_timeseries/README_tenv3.txt) ，[增强版格式文档README_tenv3load.txt](https://geodesy.unr.edu/gps_timeseries/README_tenv3load.txt)

可能使用的数据：[GIA 冰期后回弹地球物理效应改正数据](https://www.atmosp.physics.utoronto.ca/~peltier/data.php) ，[Natural Earth 矢量边界数据集](https://www.naturalearthdata.com/)

> *特别感谢本项目的核心代码延用了姜中山老师的[lsf项目]([GitHub - jzshhh/lsf: lsf is designed for extracting hydrological loading displacement form GNSS vertical position time series analysis based on the least squares fitting method. · GitHub](https://github.com/jzshhh/lsf))。*