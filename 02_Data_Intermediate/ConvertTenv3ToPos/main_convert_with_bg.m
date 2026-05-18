%% GNSS 数据日期筛选批处理转换脚本 (增强版：支持自定义背景值时段)
clear; clc;

% --- 用户设置区域 ---
inputDir = '..\..\01_Data_Raw\tenv3';           % 原始数据存放地
outputDir = '..\..\02_Data_Intermediate\pos_files';      % 转换后数据存放地

% 1. 设定输出数据的日期范围 (YYYYMMDD)
startDate = '20050101';      
endDate   = '20251231';

% 2. 设定计算背景值(均值)的日期范围 (YYYYMMDD)
% 如果留空 ''，则默认使用文件内【所有日期】的数据计算均值
bgStartDate = '';
bgEndDate   = '';    
% --------------------

if ~exist(outputDir, 'dir'), mkdir(outputDir); end

fileList = dir(fullfile(inputDir, '*.tenv3')); 
if isempty(fileList), error('没有找到文件！'); end

fprintf('开始批处理转换...\n');
fprintf('输出时段: %s 至 %s\n', startDate, endDate);
if isempty(bgStartDate) || isempty(bgEndDate)
    fprintf('背景参考: 全序列均值\n');
else
    fprintf('背景参考时段: %s 至 %s\n', bgStartDate, bgEndDate);
end
fprintf('--------------------------------------\n');

tic;
successCount = 0;
for i = 1:length(fileList)
    fileName = fileList(i).name;
    fullInputPath = fullfile(inputDir, fileName);
    
    try
        % 调用增强后的函数
        convertTenv3ToPos_bg(fullInputPath, outputDir, startDate, endDate, bgStartDate, bgEndDate);
        
        [~, nameOnly] = fileparts(fileName);
        if exist(fullfile(outputDir, [nameOnly '.pos']), 'file')
            successCount = successCount + 1;
            fprintf('[%d/%d] 成功处理: %s\n', i, length(fileList), fileName);
        end
    catch ME
        fprintf('[%d/%d] 出错: %s, 原因: %s\n', i, length(fileList), fileName, ME.message);
    end
end

fprintf('--------------------------------------\n');
fprintf('处理完成！有效站点数: %d\n总耗时: %.2f 秒\n', successCount, toc);