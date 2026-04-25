function export_appendix_a_xml(xmlPath, outputPath)
% Extract the raw Appendix A block from the XML article.
xmlText = fileread(xmlPath);

startToken = '<app id="app1-information-14-00286">';
endToken = '</app>';

startIdx = strfind(xmlText, startToken);
if isempty(startIdx)
    error('Appendix A start token not found in XML.');
end

searchText = xmlText(startIdx(1):end);
endIdxRel = strfind(searchText, endToken);
if isempty(endIdxRel)
    error('Appendix A end token not found in XML.');
end

appendixText = searchText(1:endIdxRel(1) + length(endToken) - 1);

fid = fopen(outputPath, 'w');
if fid == -1
    error('Cannot open output file for writing: %s', outputPath);
end

cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s', appendixText);
end
