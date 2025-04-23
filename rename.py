import os
import re

def clean_brackets_in_names(root_dir="."):
    """
    递归移除目录及子目录下所有文件/文件夹名中的【】符号
    格式转换示例：
    【1】文件名.txt → 1 文件名.txt
    【23】文件夹 → 23 文件夹
    """
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        print(root_dir)
        # 处理当前目录的文件
        for name in filenames + dirnames:
            print(name)
            old_path = os.path.join(dirpath, name)
            
            # 使用正则替换【数字】→ 数字+空格
            new_name = re.sub(r'【(\d+)】', r'\1 ', name)
            
            if new_name != name:  # 只有当名称变化时才重命名
                new_path = os.path.join(dirpath, new_name)
                print(new_path)
                try:
                    os.rename(old_path, new_path)
                    print(f"重命名: {os.path.relpath(old_path)} → {os.path.relpath(new_path)}")
                except OSError as e:
                    print(f"无法重命名 {old_path}: {e}")

# 使用示例
if __name__ == "__main__":
    # target_dir = input("请输入要处理的目录路径（留空则使用当前目录）: ").strip() or "."
    # clean_brackets_in_names(target_dir)
    # print("处理完成！")
    dirs = [
        "D:\path\to\bookdir1",
        "D:\path\to\bookdir2",
    ]
    for d in dirs:
        print(d)
        clean_brackets_in_names(d)
