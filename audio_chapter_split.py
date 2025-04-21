import os
import numpy as np
from pydub import AudioSegment, silence
from mutagen.id3 import ID3, CHAP, CTOC, TIT2, TPE1, TRCK
import speech_recognition as sr
from rich.progress import Progress
import tempfile
import math
import multiprocessing as mp

import json
from pathlib import Path
from datetime import datetime
import logging
import argparse

# 配置日志
logger = logging.getLogger(__name__)

def find_optimal_split(audio, keyword_pos, silence_thresh=-45, look_back=5000):
    """
    在关键词位置前寻找最佳静音分割点
    参数:
        audio: 音频段
        keyword_pos: 关键词位置(ms)
        silence_thresh: 静音阈值(dBFS)
        look_back: 向前搜索范围(ms)
    """
    # 提取关键词前的音频段
    start_pos = max(0, keyword_pos - look_back)
    search_segment = audio[start_pos:keyword_pos]
    
    # 检测静音段
    silent_ranges = silence.detect_nonsilent(
        search_segment, 
        min_silence_len=4000,
        silence_thresh=silence_thresh
    )
    
    # 如果没有检测到静音，在关键词前500ms分割
    if not silent_ranges:
        return max(0, keyword_pos - 500)
    
    # 取最后一个静音段的中间位置
    last_silent_start = silent_ranges[-1][0] + start_pos
    last_silent_end = silent_ranges[-1][1] + start_pos
    optimal_pos = (last_silent_start + last_silent_end) // 2  # 计算中间点
    return optimal_pos

def process_audio_chunk(args):
    """处理音频片段的多进程函数"""
    chunk_path, chunk_start, chunk_duration, silence_thresh = args
    recognizer = sr.Recognizer()
    markers = []
    
    try:
        with sr.AudioFile(chunk_path) as source:
            audio = recognizer.record(source, duration=chunk_duration)
            text = recognizer.recognize_google(audio, language="en-US")
            
            if "chapter" in text.lower() or "prologue" in text.lower():
                # 计算关键词在原始音频中的大致位置
                keyword_pos = chunk_start + (chunk_duration * 1000 / 2)
                markers.append(keyword_pos)
    except Exception as e:
        pass
    
    logger.info(f"删除临时音频文件: {chunk_path}")
    os.remove(chunk_path)
    return markers

def detect_chapters_with_silence(audio_path, progress):
    """主检测函数：结合语音识别和静音分析"""
    # 准备音频
    audio = AudioSegment.from_file(audio_path)
    temp_dir = tempfile.mkdtemp()
    cpu_count = os.cpu_count()
    chunk_size = 5  # 每个进程处理5秒
    
    # 分割音频为临时文件
    task_prepare = progress.add_task("[cyan]准备音频...", total=math.ceil(len(audio)/(chunk_size*1000)))
    chunks = []
    for i in range(0, len(audio), chunk_size * 1000):
        chunk = audio[i:i + chunk_size * 1000]
        chunk_path = os.path.join(temp_dir, f"chunk_{i}.wav")
        chunk.export(chunk_path, format="wav")
        chunks.append((chunk_path, i, chunk_size, -40))  # 静音阈值-40dB
        progress.update(task_prepare, advance=1)
    
    # 并行处理
    task_detect = progress.add_task("[green]检测关键词...", total=len(chunks))
    keyword_positions = []
    with mp.Pool(cpu_count) as pool:
        for result in pool.imap_unordered(process_audio_chunk, chunks):
            keyword_positions.extend(result)
            progress.update(task_detect, advance=1)
    
    # 在关键词前寻找静音分割点
    task_split = progress.add_task("[yellow]寻找静音分割...", total=len(keyword_positions))
    split_points = [0]
    for pos in sorted(keyword_positions):
        split_at = find_optimal_split(audio, pos)
        if split_at - split_points[-1] > 5000:  # 最小章节长度5秒
            split_points.append(split_at)
            progress.print(f"在 {pos/1000:.1f}s 前 {split_at/1000:.1f}s 处分割")
        progress.update(task_split, advance=1)
    
    split_points.append(len(audio))
    
    logger.info(f"删除临时音频文件目录: {temp_dir}")
    os.rmdir(temp_dir)
    return split_points

def create_chapters(audio_path, split_points):
    """根据分割点创建章节"""
    chapters = []
    for i in range(len(split_points)-1):
        start = split_points[i]
        end = split_points[i+1]
        if i == 0:
            title = "Opening"
        elif i == 1:
            title = f"Chapter {i-1} Prologue"
        else:
            title = f"Chapter {i-1}"
        chapters.append((start, end, title))
    return chapters

def save_id3_tags(audio_path, chapters, output_path=None):
    """保存章节信息到ID3标签（兼容播放器显示）"""
    try:
        # 加载或创建ID3标签
        try:
            id3 = ID3(audio_path)
        except:
            id3 = ID3()
        
        # 清除现有章节
        id3.delall('CHAP')
        id3.delall('CTOC')
        
        
        # 添加章节（确保时间单位是毫秒）
        chap_ids = []
        for i, (start_ms, end_ms, title) in enumerate(chapters):
            chap_id = f"chp{i}"
            chap_ids.append(chap_id)
            
            id3.add(CHAP(
                element_id=chap_id,
                start_time=int(start_ms),  # 必须为毫秒
                end_time=int(end_ms),
                sub_frames=[
                    TIT2(encoding=3, text=[title]),  # UTF-8编码
                ]
            ))
        
        # 添加目录表（关键！flags必须设为0x03）
        id3.add(CTOC(
            element_id="toc1",
            flags=0x03,  # 0x03表示这是顶级目录
            child_element_ids=chap_ids,
            sub_frames=[
                TIT2(encoding=3, text=["Chapters"]),
            ]
        ))
        
        # 强制保存为ID3v2.3格式（兼容性最好）
        output_path = output_path or audio_path
        id3.save(output_path, v2_version=3)
        
        print(f"成功写入 {len(chapters)} 个章节")
        return True
        
    except Exception as e:
        print(f"失败: {str(e)}")
        return False


def save_progress_to_json(data: dict, filename: str = "progress.json") -> bool:
    """
    将中间结果保存为JSON文件
    参数:
        data: 包含split_points和chapters的字典
        filename: 保存路径
    返回:
        bool: 是否保存成功
    """
    try:
        # 准备可序列化数据
        serializable_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            },
            "split_points": [int(x) for x in data["split_points"]],
            "chapters": [
                (int(start), int(end), str(title))
                for start, end, title in data["chapters"]
            ],
            "audio_info": {
                "path": str(data.get("audio_path", "")),
                "duration_ms": int(data.get("duration_ms", 0))
            }
        }
        
        # 写入文件（原子操作模式）
        temp_path = Path(filename).with_suffix(".tmp")
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)
        
        # 替换原文件
        temp_path.replace(filename)
        logger.info(f"进度已保存到 {filename}")
        return True
        
    except Exception as e:
        logger.error(f"保存进度失败: {str(e)}", exc_info=True)
        return False

def load_progress_from_json(filename: str = "progress.json") -> dict:
    """
    从JSON文件加载中间结果
    返回:
        dict: 包含split_points和chapters的字典，结构为:
            {
                "split_points": List[int],
                "chapters": List[Tuple[int, int, str]],
                "audio_info": dict,
                "metadata": dict
            }
        或空字典（如果加载失败）
    """
    try:
        path = Path(filename)
        if not path.exists():
            logger.warning(f"进度文件不存在: {path}")
            return {}
            
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 验证数据结构
        if not all(key in data for key in ["split_points", "chapters"]):
            raise ValueError("无效的进度文件格式")
            
        # 转换回原始格式
        return {
            "split_points": data["split_points"],
            "chapters": [tuple(chap) for chap in data["chapters"]],
            "audio_info": data.get("audio_info", {}),
            "metadata": data.get("metadata", {})
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误: {str(e)}")
    except Exception as e:
        logger.error(f"加载进度失败: {str(e)}", exc_info=True)
    return {}

def process_audio_with_persistence(audio_path: str, progress_file: str = "progress.json", output_path: str = None):
    """带持久化支持的音频处理主流程"""
    # 尝试加载已有进度
    progress_data = load_progress_from_json(progress_file)
    if progress_data and progress_data["audio_info"].get("path") == audio_path:
        split_points = progress_data["split_points"]
        chapters = progress_data["chapters"]
        logger.info(f"恢复进度: 已加载 {len(chapters)} 个章节")
    else:
        split_points = []
        chapters = []
    
    try:
        with Progress() as progress:
            # 如果split_points为空，重新检测
            if not split_points:
                split_points = detect_chapters_with_silence(audio_path, progress)
                
                # 立即保存检测结果
                save_progress_to_json({
                    "split_points": split_points,
                    "chapters": chapters,
                    "audio_path": audio_path,
                    "duration_ms": len(AudioSegment.from_file(audio_path))
                }, progress_file)
            
            # 生成章节
            if split_points and not chapters:
                chapters = create_chapters(audio_path, split_points)
                save_progress_to_json({
                    "split_points": split_points,
                    "chapters": chapters,
                    "audio_path": audio_path
                }, progress_file)
            
            # 保存ID3标签
            if chapters:
                # safe_save_with_eyed3(audio_path, chapters)

                # save_id3_tags(audio_path, chapters, output_path)
                save_id3_tags(audio_path, chapters)

                
                # 处理完成后删除进度文件
                # try:
                #     os.remove(progress_file)
                # except:
                #     pass
                
            return chapters
            
    except Exception as e:
        logger.error(f"处理中断，进度已保存: {str(e)}", exc_info=True)
        raise
    
        
def main():
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(
        description="根据语音识别自动分割音频章节",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "audio_file",
        help="要处理的音频文件路径 (支持MP3/WAV等格式)"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件路径 (默认覆盖原文件)",
        default=None
    )
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.audio_file):
        logging.error(f"文件不存在: {args.audio_file}")
        return
    
    if args.output:
        output_path = args.output
    else:
        output_path = args.audio_file
    
    # 配置参数
    logging.info(f"开始处理文件：{args.audio_file}")
    progress_file = f"{Path(args.audio_file).stem}_progress.json"
    
    try:
        chapters = process_audio_with_persistence(args.audio_file, progress_file, output_path)
        if chapters:
            print("\n最终章节划分:")
            for chap in chapters:
                print(f"{chap[2]}: {chap[0]/1000:.1f}s - {chap[1]/1000:.1f}s")
    except Exception as e:
        print(f"\n处理中断，可以从以下文件恢复进度: {progress_file}")
        print("错误详情:", str(e))
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.WARN)
    mp.freeze_support()
    main()
    
# python audio_chapter_split.py clean_01part.mp3