function network = ieee33_synthetic_network()
branches = [ ...
    1 2; 2 3; 3 4; 4 5; 5 6; 6 7; 7 8; 8 9; 9 10; 10 11; 11 12; 12 13; ...
    13 14; 14 15; 15 16; 16 17; 17 18; 2 19; 19 20; 20 21; 21 22; ...
    3 23; 23 24; 24 25; 6 26; 26 27; 27 28; 28 29; 29 30; 30 31; ...
    31 32; 32 33];

network = struct();
network.name = 'synthetic_ieee33_radial';
network.data_type = 'synthetic_reproduction';
network.node_count = 33;
network.section_count = size(branches, 1);
network.branches = branches;
network.sensor_nodes = 2:33;
network.note = 'Standard IEEE33-style radial branch list used for synthetic FTU signature reproduction.';
end
