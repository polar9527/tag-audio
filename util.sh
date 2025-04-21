# 截取部分音频
ffmpeg -i 01full.mp3 -ss 00:00:00 -to 01:10:00 -c copy 01part.mp3

# 清理音频中的 所有标签
ffmpeg -i 01part.mp3 -map_metadata -1 -c:a copy clean_01part.mp3

# 清理音频中的 所有chapter标签
ffmpeg -i 01part.mp3 -map_metadata 0 -map_chapters -1 -c:a copy clean_01part.mp3



ffmpeg -i 01part.mp3 -f ffmetadata -

ffmpeg -i clean_01part.mp3 -f ffmetadata -