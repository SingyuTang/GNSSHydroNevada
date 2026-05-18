function plot_pbo_ts_custom(inp_pos, out_ps, periods, breaks, rates, explog, ebars, outlier, comp)
% 增加参数 comp: 代表要处理的分量 ('N', 'E' 或 'U')
% 如果未提供 comp 参数，默认按 'U' 处理，保持向下兼容
if nargin < 9
    comp = 'U'; 
end

% 鲁棒地提取台站名，替代原有的 inp_pos(1,7:10)
[~, sta_name, ~] = fileparts(inp_pos);
sta_name = lower(sta_name);

% 根据传入的方向，动态配置：数据列号、误差列号、粗差剔除阈值和图表显示范围
switch upper(comp)
    case 'N'
        col_disp = 2; col_err = 5;
        comp_str = 'North'; ext = 'north';
        thres_outlier = 20; thres_plot = 40; ylims = [-20 20];
    case 'E'
        col_disp = 3; col_err = 6;
        comp_str = 'East'; ext = 'east';
        thres_outlier = 20; thres_plot = 40; ylims = [-20 20];
    case 'U'
        col_disp = 4; col_err = 7;
        comp_str = 'Up'; ext = 'up';
        thres_outlier = 40; thres_plot = 80; ylims = [-40 40];
    otherwise
        error('未知的方向分量。请使用 ''N'', ''E'', 或 ''U''。');
end

data = load(inp_pos);
time = data(:,1);
year = date2yr(datevec(num2str(time),'yyyymmdd'));

% 提取对应分量的数据: [时间(年), 位移, 误差]
dataC = [year, data(:,col_disp), data(:,col_err)];

% Look for outliers, deltaN < 20 mm, deltaE < 20mm, deltaU < 40mm
ok = sigma_outlier(dataC, thres_outlier);
dataC = dataC(ok,:); time = time(ok,:);

% 原有的环境负荷扣除注释保留
% ntal=load(['ntal/' sta_name '.ntal']);
% ntol=load(['ntol/' sta_name '.ntol']);
% % temp=load(['temp/' sta_name '.temp']);
% gia=load(['gia/' sta_name '.gia']);
% [~,ok1,ok2]=intersect(ntal(:,1),time);
% 
% dataC(ok2,2) = dataC(ok2,2)-ntal(ok1,4)-ntol(ok1,4)-gia(ok1,2);
% dataC = dataC(ok2,:); time=time(ok2,:);

% least square calculation, (iteration needed for editing the outlier data)
iter = 1; cnt = 0;
while iter == 1
    cnt = cnt + 1 ; % iteration number
    [Cx, Cstdx, Cres, Cnrms, Cwrms, CA, Ct] = LeastSquare(dataC, periods, breaks, rates, explog, [], []);
    ok = iqr_outlier(dataC, Cres, Cnrms, outlier);
    dataC = dataC(ok,:); time = time(ok,:);
    
    % if iteration exceed 30, stop
    if (length(ok) == length(Cres))
        iter = 0; 
    end
    if ( cnt > 30 ), iter = 0; end
end

% Write out the solution (增加方向后缀防止互相覆盖)
fid = fopen(sprintf('%s_%s_report.txt', out_ps, ext), 'w');
out = WrtResult(out_ps, comp_str, Cx, Cstdx, Cwrms, Cnrms, length(dataC(:,1)), length(year), periods, breaks, rates, explog, Ct);
fprintf(fid, '%s \n', out);
fclose(fid);
 
% Generate the model and model error bars
Cmod = CA(:,3:6) * Cx(3:6);
m = mean(Cmod);
Cmod = Cmod - m;
Cdata = Cmod + Cres;    % Cdata = 周期项 + 残差 (即去除了线性趋势和跳变后的信号)

% 剔除极端残差用于画图
ok3 = find(abs(Cdata) < thres_plot);
dataC = dataC(ok3,:); time = time(ok3,:); 
Cdata = Cdata(ok3,:); Cmod = Cmod(ok3,:);

figure(1)
plot(dataC(:,1), Cdata, 'bo', 'MarkerFaceColor', 'b', 'MarkerSize', 2.0);
hold on;
errorbar(dataC(:,1), Cdata, ebars*dataC(:,3), 'o', 'MarkerFaceColor', 'b', 'MarkerSize', 2.0, 'Color', [0.8 0.8 0.8]);
plot(dataC(:,1), Cmod, 'Color', 'r', 'LineWidth', 2);
hold off;

ylabel(sprintf('%s (mm)', comp_str));
xlabel('year');
title(sprintf('%s - %s', upper(sta_name), comp_str));
set(gcf, 'Position', [200 200 800 200]);
set(gca, 'YLim', ylims);

% export_fig(['neu/' sta_name '.pdf']);
% delete(figure(1));
if ~exist('neu', 'dir'), mkdir('neu'); end
% PDF文件名增加方向后缀
saveas(gcf, sprintf('neu/%s_%s.pdf', sta_name, ext));
delete(figure(1));

% 输出文件后缀名变为 .up, .north, .east
fid = fopen(sprintf('neu/%s.%s', sta_name, ext), 'wt');
fprintf(fid, '%8d %10.3f %10.3f\n', [time Cdata dataC(:,3)]');        % 输出单位为mm
fclose(fid);

end