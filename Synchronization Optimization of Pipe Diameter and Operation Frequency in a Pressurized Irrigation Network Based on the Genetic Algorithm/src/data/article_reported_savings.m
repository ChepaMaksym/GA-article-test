function data = article_reported_savings()
data = struct();
data.total_irrigation_cost_saving_pct = struct('OFM', 1.4, 'PDM', 10.6, 'SOM', 19.3);
data.OFM_percent = 1.4;
data.PDM_percent = 10.6;
data.SOM_percent = 19.3;
data.energy_saving_pct = struct('OFM', 9.3);
data.energy_cost_increase_pct = struct('PDM', 31.7, 'SOM', 21.9);
data.network_cost_reduction_pct = struct('PDM', 18.1, 'SOM', 19.3);
data.network_cost_share_text = 'about 5/6 of annual total cost';
data.energy_cost_share_text = 'about 1/6 of annual total cost';
end
