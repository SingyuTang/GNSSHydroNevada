clear; clc;

% ===================== 1. 用户配置区 =====================
udir = './pbo';       % POS文件目录
form = '*.pos';       % 文件格式

% ★ 修改点 1: 将单方向改为多方向元胞数组 ★
components = {'N', 'E', 'U'}; % 需要处理的分量，可以自由增减，如 {'E', 'U'}

periods = [1; 0.5];   % 估计年周期、半年周期
ebars = 0;            % 误差棒: 0=不画, 1=1-sigma, 2=2-sigma
outlier = 4;          % 异常值 IQR 剔除倍数
% =========================================================

% 获取文件列表与台站名
files = GetFiles(udir, form); 
[n, p] = size(files);
sites = files(:, p-7:p-4);

fprintf('🚀 开始批量处理 GNSS 时间序列...\n');
fprintf('共找到 %d 个文件，将处理方向: %s\n', n, strjoin(components, ', '));
fprintf('----------------------------------------\n');

% 遍历每个台站文件
for i = 1:n
    % 去除字符矩阵可能自带的尾随空格
    filepath = strtrim(files(i, :));
    staname = strtrim(sites(i, :));
    
    fprintf('[%d/%d] 正在处理台站: %s\n', i, n, upper(staname));
    
    % 读取该台站的先验物理信息 (阶跃、速率、震后松弛等)
    [breaks, rates, explog] = ReadBreaks(filepath);
    
    % ★ 修改点 2: 遍历所需处理的多个方向 ★
    for c = 1:length(components)
        comp = components{c};
        
        try
            % 调用处理函数
            plot_pbo_ts_custom(filepath, fullfile(udir, staname), ...
                               periods, breaks, rates, explog, ebars, outlier, comp);
            fprintf('  ├─ %s 方向 -> 成功\n', comp);
        catch ME
            % ★ 修改点 3: 增加容错机制 ★
            % 如果某个方向因为数据太少或其他原因报错，跳过并提示，不影响后续运行
            warning('  ├─ ⚠️ %s 方向处理失败: %s', comp, ME.message);
        end
    end
    fprintf('  └─ 台站 %s 处理完毕。\n\n', upper(staname));
end

fprintf('🎉 所有台站的指定方向均已处理完成！\n');