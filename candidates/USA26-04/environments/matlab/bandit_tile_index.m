function paper_index = bandit_tile_index(x, left, offset, width)
%BANDIT_TILE_INDEX Paper-style one-based integer formula.

values = [x, left, offset, width];
if ~isnumeric(values) || ~isreal(values) || numel(values) ~= 4 ...
        || any(~isfinite(values))
    error('banditverify:InvalidTileInput', 'Tile inputs must be finite scalars.');
end
if width <= 0
    error('banditverify:InvalidTileWidth', 'Tile width must be positive.');
end
paper_index = floor((x - offset - left) / width) + 1;
end
