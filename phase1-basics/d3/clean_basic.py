#主分支测试注释
import argparse
import csv
import re
from pathlib import Path
from datetime import datetime


def clean_text(text):
    """清洗文本：去除首尾空格、去除HTML标签，并做基础敏感信息遮罩。"""
    if text is None:
        return ""

    text = str(text).strip()
    text = re.sub(r'<[^>]+>', '', text)  # 去HTML标签
    text = re.sub(r'\s+', ' ', text)     # 压缩连续空白
    text = re.sub(r'\b(?:\d{11})\b', '***********', text)  # 遮罩手机号
    return text


def parse_time(time_str):
    """将多种时间格式统一为 ISO 格式"""
    if not time_str or not str(time_str).strip():
        return ""
    time_str = str(time_str).strip()

    formats = [
        "%Y-%m-%dT%H:%M:%S",      # 2026-06-03T09:00:00
        "%Y-%m-%d %H:%M:%S",      # 2026-06-03 09:00:00
        "%Y/%m/%d %H:%M",          # 2026/6/3 08:00
        "%Y年%m月%d日 %H:%M",       # 2026年6月3日 11:00
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue

    # 如果都解析失败，原样返回
    return time_str


def parse_args():
    parser = argparse.ArgumentParser(description="清洗基础聊天会话 CSV")
    parser.add_argument("--input", default="camp-data/raw/d3/chat_sessions_dirty.csv", help="输入 CSV 路径")
    parser.add_argument("--output", default="chat_sessions_cleaned.csv", help="输出 CSV 路径")
    return parser.parse_args()


def main():
    args = parse_args()
    input_file = Path(args.input)
    output_file = Path(args.output)

    seen = set()          # 用于去重
    cleaned_rows = []     # 清洗后的行
    removed_count = 0     # 移除的行数

    if not input_file.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_file}")

    with open(input_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("输入 CSV 为空或缺少表头")
        fieldnames = reader.fieldnames

        for row in reader:
            # 1. 清洗 message 字段（去空格、去HTML标签）
            row["message"] = clean_text(row.get("message", ""))

            # 2. 清洗 user_id（去空格）
            row["user_id"] = clean_text(row.get("user_id", ""))

            # 3. 清洗 role（去空格）
            row["role"] = clean_text(row.get("role", ""))

            # 4. 清洗 session_id（去空格）
            row["session_id"] = clean_text(row.get("session_id", ""))

            # 5. 统一时间格式
            row["created_at"] = parse_time(row.get("created_at", ""))

            # 6. 过滤：message 为空 或 user_id 为空
            if not row.get("message", "") or not row.get("user_id", ""):
                removed_count += 1
                continue

            # 7. 去重：基于整行内容
            row_tuple = tuple(sorted(row.items()))
            if row_tuple in seen:
                removed_count += 1
                continue
            seen.add(row_tuple)

            cleaned_rows.append(row)

    # 写入清洗后的文件
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print(f"清洗完成！")
    print(f"  原始行数: {len(cleaned_rows) + removed_count}")
    print(f"  移除行数: {removed_count}")
    print(f"  保留行数: {len(cleaned_rows)}")
    print(f"  输出文件: {output_file}")


if __name__ == "__main__":
    main()
