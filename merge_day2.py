import json
from pathlib import Path


def load_json_file(filepath):
    """加载单个 JSON 文件，支持对象（含 results 数组）或数组根节点"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    if isinstance(data, list):
        return data
    return [data]


def record_key(record):
    """将记录序列化为排序后的元组，用作去重键"""
    return tuple(sorted((k, str(v)) for k, v in record.items()))


def main():
    input_dir = Path("raw/d2")
    output_file = Path("merged.json")

    all_records = []
    seen_keys = set()

    for filepath in sorted(input_dir.glob("*.json")):
        print(f"读取: {filepath}")
        records = load_json_file(filepath)
        for rec in records:
            key = record_key(rec)
            if key not in seen_keys:
                seen_keys.add(key)
                all_records.append(rec)
            else:
                print(f"  去重: {rec}")

    # 写入 JSONL 格式（每行一个 JSON 对象）
    with open(output_file, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\n合并完成，共 {len(all_records)} 条唯一记录 → {output_file}")

    # 验证行数
    with open(output_file, "r", encoding="utf-8") as f:
        line_count = sum(1 for _ in f)
    print(f"文件行数: {line_count}")
    assert line_count >= 8, f"行数不足: {line_count} < 8"
    print("✓ 行数验证通过 (>= 8)")


if __name__ == "__main__":
    main()
