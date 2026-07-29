function [errorValue, details] = c_index_error(riskScore, time, event)
riskScore = riskScore(:);
time = time(:);
event = event(:);

concordant = 0;
permissible = 0;
ties = 0;
n = numel(time);

for i = 1:n
    if event(i) == 0
        continue;
    end
    for j = 1:n
        if time(i) < time(j)
            permissible = permissible + 1;
            if riskScore(i) > riskScore(j)
                concordant = concordant + 1;
            elseif riskScore(i) == riskScore(j)
                ties = ties + 1;
            end
        end
    end
end

if permissible == 0
    cIndex = 0.5;
else
    cIndex = (concordant + 0.5 * ties) / permissible;
end

errorValue = 1 - cIndex;
details = struct();
details.c_index = cIndex;
details.c_index_error = errorValue;
details.permissible_pairs = permissible;
details.concordant_pairs = concordant;
details.tied_pairs = ties;
end
