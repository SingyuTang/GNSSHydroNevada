function convertTenv3ToPos_bg(inputFileName, outDir, startDateStr, endDateStr, bgStartStr, bgEndStr)
% 输入参数:
% inputFileName: 原始文件路径
% outDir: 输出文件夹
% startDateStr/endDateStr: 输出数据的日期范围
% bgStartStr/bgEndStr: 计算背景均值的日期范围 (可选)

[~, name, ~] = fileparts(inputFileName);
outputFileName = fullfile(outDir, [name '.pos']);

% 转换日期为数值
outStart = str2double(startDateStr);
outEnd   = str2double(endDateStr);

fid = fopen(inputFileName, 'r');
if fid == -1, error('无法打开文件'); end

% 1. 读取原始数据 (读取全部行)
fgetl(fid); % 跳过表头
formatSpec = '%s %s %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %*[^\n]';
C = textscan(fid, formatSpec, 'MultipleDelimsAsOne', true);
fclose(fid);

% 2. 处理日期转换
dateStrRaw = C{2};
numRows = length(dateStrRaw);
allDates = zeros(numRows, 1);
for i = 1:numRows
    dt = datetime(dateStrRaw{i}, 'InputFormat', 'yyMMMd', 'Locale', 'en_US');
    allDates(i) = str2double(datestr(dt, 'yyyymmdd'));
end

% 3. 计算全序列的净位移 (单位：米)
% 先计算出文件里每一行的位移值
full_net_N = (C{10} + C{11}) - (C{25} + C{28}); % N_total - N_ntal - N_ntol
full_net_E = (C{8}  + C{9})  - (C{24} + C{27}); % E_total - E_ntal - E_ntol
full_net_U = (C{12} + C{13}) - (C{26} + C{29}); % U_total - U_ntal - U_ntol

% 4. 确定背景值 (均值)
if nargin < 5 || isempty(bgStartStr) || isempty(bgEndStr)
    % 如果没设置背景范围，默认使用全文件数据
    bgIdx = true(numRows, 1); 
else
    bgStart = str2double(bgStartStr);
    bgEnd   = str2double(bgEndStr);
    bgIdx   = (allDates >= bgStart & allDates <= bgEnd);
    
    % 安全检查：如果背景时段没数据，退而求其次使用全序列
    if ~any(bgIdx)
        warning('站点 %s 背景时段 [%s-%s] 无数据，改用全序列计算均值。', name, bgStartStr, bgEndStr);
        bgIdx = true(numRows, 1);
    end
end

meanN = mean(full_net_N(bgIdx), 'omitnan');
meanE = mean(full_net_E(bgIdx), 'omitnan');
meanU = mean(full_net_U(bgIdx), 'omitnan');

% 5. 筛选输出时段的数据
keepIdx = (allDates >= outStart & allDates <= outEnd);
if ~any(keepIdx)
    fprintf('警告: 站点 %s 在输出范围 [%s-%s] 内无数据，跳过。\n', name, startDateStr, endDateStr);
    return;
end

% 计算相对于背景均值的残差并转为毫米
final_N = (full_net_N(keepIdx) - meanN) * 1000;
final_E = (full_net_E(keepIdx) - meanE) * 1000;
final_U = (full_net_U(keepIdx) - meanU) * 1000;

% 提取误差项并转为毫米
final_sigN = C{16}(keepIdx) * 1000;
final_sigE = C{15}(keepIdx) * 1000;
final_sigU = C{17}(keepIdx) * 1000;
final_dates = allDates(keepIdx);

% 6. 写入文件
fileID = fopen(outputFileName, 'w');
for i = 1:length(final_dates)
    fprintf(fileID, '%8d %10.2f %10.2f %10.2f %8.2f %8.2f %8.2f\n', ...
        final_dates(i), final_N(i), final_E(i), final_U(i), ...
        final_sigN(i), final_sigE(i), final_sigU(i));
end
fclose(fileID);
end