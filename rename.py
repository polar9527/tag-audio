import os
import re

def clean_brackets_in_names(root_dir="."):
    """移除当前目录下所有文件/文件夹名中的【】符号"""
    for name in os.listdir(root_dir):
        old_path = os.path.join(root_dir, name)
        
        # 使用正则替换【数字】→ 数字+空格
        new_name = re.sub(r'【(\d+)】', r'\1 ', name)
        
        if new_name != name:  # 只有当名称变化时才重命名
            new_path = os.path.join(root_dir, new_name)
            os.rename(old_path, new_path)
            print(f"重命名: {name} → {new_name}")

# 使用示例
clean_brackets_in_names(".")