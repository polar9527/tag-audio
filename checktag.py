import eyed3

def check_cleaned(audio_path):
    audio = eyed3.load(audio_path)
    if audio.tag:
        chap_frames = [f for f in audio.tag.frame_set if f.startswith(b'CHAP')]
        print(f"残留章节帧: {len(chap_frames)}")
    else:
        print("文件无标签")

check_cleaned("clean_01part.mp3")