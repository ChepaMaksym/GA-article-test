function cost = annualized_network_cost(branch_diameter_mm)
% Approximate annualized pipe network cost for a branch-level design.
prices = article_table3_pipe_prices();
original = article_table2_original_branch_diameters();
basic = article_basic_information();

segmentLength_m = basic.hydrant_interval_m;
branch_diameter_mm = branch_diameter_mm(:).';
if numel(branch_diameter_mm) ~= numel(original.branch_number)
    error('Expected one diameter per branch pipe.');
end

capitalRecovery = capital_recovery_factor(basic.annual_interest_rate_pct / 100, basic.depreciation_period_year);
maintenance = basic.annual_maintenance_rate_pct / 100;

investment = 0;
for branch = 1:numel(branch_diameter_mm)
    segmentCount = sum(~isnan(original.diameter_mm(branch, :)));
    unitPrice = unit_price_for_diameter(branch_diameter_mm(branch), prices);
    investment = investment + unitPrice * segmentLength_m * segmentCount;
end

cost = (capitalRecovery + maintenance) * investment;
end

function factor = capital_recovery_factor(rate, years)
factor = rate * (1 + rate)^years / ((1 + rate)^years - 1);
end

function unitPrice = unit_price_for_diameter(diameter, prices)
[isKnown, idx] = ismember(diameter, prices.outside_diameter_mm);
if ~isKnown
    error('Unsupported pipe diameter: %.3f mm', diameter);
end
unitPrice = prices.unit_price_yuan_per_m(idx);
end
