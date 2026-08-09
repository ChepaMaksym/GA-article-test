function text = eu2612_fraction_decimal(numerator, denominator, places)
% Exact non-negative rational decimal with ties-to-even rounding and trimming.
values = [numerator, denominator, places];
if any(~isfinite(values)) || any(values ~= fix(values)) || numerator < 0 || denominator <= 0 || places < 0
    error('EU2612:FractionDomain', 'Fraction inputs must be valid non-negative integers.');
end
integer_part = floor(numerator / denominator);
remainder = mod(numerator, denominator);
digits = zeros(1, places + 1);
for index = 1:(places + 1)
    remainder = remainder * 10;
    digits(index) = floor(remainder / denominator);
    remainder = mod(remainder, denominator);
end
if places == 0
    retained_last = mod(integer_part, 10);
else
    retained_last = digits(places);
end
round_up = digits(places + 1) > 5 || ...
    (digits(places + 1) == 5 && (remainder > 0 || mod(retained_last, 2) == 1));
retained = digits(1:places);
if round_up
    carry = 1;
    for index = places:-1:1
        updated = retained(index) + carry;
        retained(index) = mod(updated, 10);
        carry = floor(updated / 10);
        if carry == 0
            break;
        end
    end
    integer_part = integer_part + carry;
end
if places == 0
    text = sprintf('%d', integer_part);
    return;
end
fraction = sprintf('%d', retained);
fraction = regexprep(fraction, '0+$', '');
if isempty(fraction)
    text = sprintf('%d', integer_part);
else
    text = sprintf('%d.%s', integer_part, fraction);
end
end
