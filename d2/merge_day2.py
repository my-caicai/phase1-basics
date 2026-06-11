import json
import csv
import os
from pathlib import Path

RAW_DIR = Path("camp-data/raw/d2")
OUTPUT_FILE = Path("merged.jsonl")

SESSION_ID_KEYS = {"trace_id", "uid", "user_id", "session_id", "id"}

def get_session_id(record):
    for key in SESSION_ID_KEYS:
        if key in record:
            val = record[key]
            if val != "" and val is not None:
                return val
    return None

def generate_record_id(record):
    """为没有 session ID 的记录生成唯一标识"""
    import hashlib
    content = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]

def read_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "items", "records", "sessions"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    return []

def read_csv_file(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(dict(row))
    return records

def load_all_records(raw_dir):
    all_records = []
    if not raw_dir.exists():
        raise FileNotFoundError(f"目录不存在: {raw_dir}")
    for file_path in raw_dir.iterdir():
        if file_path.is_dir():
            continue
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".json":
                records = read_json_file(file_path)
            elif suffix == ".csv":
                records = read_csv_file(file_path)
            else:
                continue
            all_records.extend(records)
        except Exception as e:
            print(f"读取文件失败 {file_path}: {e}")
    return all_records

def main():
    raw_dir = RAW_DIR
    output_file = OUTPUT_FILE

    records = load_all_records(raw_dir)
    print(f"共读取 {len(records)} 条记录")

    seen = set()
    merged = []
    for rec in records:
        sid = get_session_id(rec)
        if sid is None:
            sid = generate_record_id(rec)
        if sid not in seen:
            seen.add(sid)
            merged.append(rec)

    print(f"去重后共 {len(merged)} 条记录")

    if len(merged) < 8:
        raise ValueError(f"去重后的数据行数不足 8 行，实际为 {len(merged)}")

    with open(output_file, "w", encoding="utf-8") as f:
        for rec in merged:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"已输出到 {output_file}")

if __name__ == "__main__":
    main()
