import eyed3
import subprocess
import os
from glob import glob
import argparse
import logging
logger = logging.getLogger(__name__)

# 根据音频文件的id3 章节标签 分割 音频文件
def split_mp3_with_ffmpeg(input_file, output_dir="output"):
    audio = eyed3.load(input_file)
    
    if not audio.tag or not audio.tag.chapters:
        print("错误：未找到章节信息！")
        return
    
    os.makedirs(output_dir, exist_ok=True)
    
    for i, chapter in enumerate(audio.tag.chapters):
        start_ms = chapter.times[0]  # 开始时间（毫秒）
        end_ms = chapter.times[1]    # 结束时间（毫秒）
        
        # 转换为 FFmpeg 时间格式 (HH:MM:SS.ms)
        start_time = f"{int(start_ms//3600000):02d}:{int((start_ms%3600000)//60000):02d}:{int((start_ms%60000)//1000):02d}.{int(start_ms%1000):03d}"
        end_time = f"{int(end_ms//3600000):02d}:{int((end_ms%3600000)//60000):02d}:{int((end_ms%60000)//1000):02d}.{int(end_ms%1000):03d}"
        print(chapter.title)
        # FFmpeg 无损切割
        if chapter.title != None:
            output_file = os.path.join(output_dir, f"{chapter.title}.mp3")
        else:
            if i == 0:   
                output_file = os.path.join(output_dir, f"chapter_{i} prologue.mp3")
            else:
                output_file = os.path.join(output_dir, f"chapter_{i}.mp3")
            
        cmd = [
            "ffmpeg", "-i", input_file,
            "-ss", start_time, "-to", end_time,
            "-c", "copy",  # 直接复制流（不重新编码）
            output_file
        ]
        subprocess.run(cmd, check=True)
        print(f"已保存: {output_file}")

# 使用示例
# split_mp3_with_ffmpeg("02 Fire and Ice.mp3", "02 Fire and Ice")

def process_all_mp3s(input_dir=".", output_parent_dir="."):
    """处理当前目录下所有MP3文件"""
    mp3_files = glob(os.path.join(input_dir, "*.mp3"))
    
    if not mp3_files:
        print("未找到MP3文件！")
        return
    
    for mp3_file in mp3_files:
        # 为每个MP3文件创建单独的输出目录
        base_name = os.path.splitext(os.path.basename(mp3_file))[0]
        output_dir = os.path.join(output_parent_dir, base_name)
        if os.path.isdir(output_dir):
            print(f"{output_dir} 已经存在， Pass!")
        else:
            print(f"\n正在处理: {mp3_file}")
            split_mp3_with_ffmpeg(mp3_file, output_dir)


# 使用示例：处理当前目录所有MP3，输出到 ./output/[原文件名]/ 下
# process_all_mp3s()


def main():
    logging.basicConfig(level=logging.INFO)
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(
        description="根据ID3标签自动分割音频章节",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "audio_file",
        help="要处理的音频文件路径 (支持MP3/WAV等格式)"
    )
    parser.add_argument(
        "--outputdir", "-o",
        help="输出文件路径 (默认覆盖原文件)",
        default=None
    )
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.audio_file):
        logging.error(f"文件不存在: {args.audio_file}")
        return
    logging.info(f"文件存在: {args.audio_file}")
    split_mp3_with_ffmpeg(args.audio_file, args.outputdir)
    
if __name__ == "__main__":
    main()