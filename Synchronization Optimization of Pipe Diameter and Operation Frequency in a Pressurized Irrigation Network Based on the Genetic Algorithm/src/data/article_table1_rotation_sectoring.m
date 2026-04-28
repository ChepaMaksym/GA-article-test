function data = article_table1_rotation_sectoring()
% Table 1. Rotation irrigation sectoring.
data.sectoring_number = 1:5;
data.branch_pipe_pairs = [1 2; 3 4; 5 6; 7 8; 9 10];
data.main_segments_between_branch_and_pump = [1 1 2 2 3];
data.general_main_segment_formula = 'floor((N - 1) / 4) + 1';
end
