import json
import logging
from pathlib import Path

# 配置日志：记录到 clean.log
logging.basicConfig(
    filename="clean.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


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


def validate_record(record, filepath, line_no):
    """校验单条记录，发现问题记录日志。返回 (是否有效, 问题列表)"""
    issues = []

    # 1. 检查是否为空记录
    if not record:
        issues.append("空记录")

    # 2. 检查关键字段缺失
    has_id = any(k in record for k in ("uid", "user_id", "trace_id"))
    if not has_id:
        issues.append("缺少ID字段(uid/user_id/trace_id)")

    # 3. 检查内容字段缺失或为空
    content_fields = ["content", "text", "output"]
    has_content = any(record.get(f) for f in content_fields if f in record)
    if not has_content:
        issues.append("内容字段为空(content/text/output)")

    # 4. 检查字段值异常（None 或空字符串）
    for k, v in record.items():
        if v is None:
            issues.append(f"字段 '{k}' 值为 None")
        elif isinstance(v, str) and not v.strip():
            issues.append(f"字段 '{k}' 值为空字符串")

    # 5. 检查时间字段缺失或为空（仅对含 time/timestamp 的记录）
    time_fields = ["time", "timestamp"]
    has_time_field = any(k in record for k in time_fields)
    if has_time_field:
        has_time_value = any(record.get(f) for f in time_fields)
        if not has_time_value:
            issues.append("时间字段值为空(time/timestamp)")

    # 6. 检查 status 字段有效性（tool_result 类记录）
    if "status" in record:
        valid_statuses = {"success", "fail", "pending", "error"}
        if record["status"] not in valid_statuses:
            issues.append(f"status 值异常: {record['status']}")

    # 7. 检查 latency_ms 是否为数字
    if "latency_ms" in record:
        try:
            float(record["latency_ms"])
        except (ValueError, TypeError):
            issues.append(f"latency_ms 非数字: {record['latency_ms']}")

    if issues:
        logger.warning(
            f"[校验问题] 文件={filepath.name}, 序号={line_no}, 问题={' | '.join(issues)}, 记录={record}"
        )
        return False, issues
    return True, []


def main():
    input_dir = Path("camp-data-new/raw/d2")
    output_file = Path("merged.json")

    all_records = []
    seen_keys = set()
    issue_count = 0
    dup_count = 0

    logger.info("=== 合并任务开始 ===")

    for filepath in sorted(input_dir.glob("*.json")):
        logger.info(f"读取文件: {filepath}")
        print(f"读取: {filepath}")
        records = load_json_file(filepath)

        for idx, rec in enumerate(records, start=1):
            # 校验记录（发现问题记录日志，但不过滤，继续处理）
            valid, issues = validate_record(rec, filepath, idx)
            if not valid:
                issue_count += 1

            # 去重
            key = record_key(rec)
            if key in seen_keys:
                dup_count += 1
                logger.info(f"[去重] 文件={filepath.name}, 序号={idx}, 记录={rec}")
                print(f"  去重: {rec}")
                continue
            seen_keys.add(key)
            all_records.append(rec)

    # 写入 JSONL
    with open(output_file, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 验证行数
    with open(output_file, "r", encoding="utf-8") as f:
        line_count = sum(1 for _ in f)

    # 汇总日志
    logger.info(
        f"合并完成: 有效记录={len(all_records)}, 发现问题记录={issue_count}, "
        f"重复记录={dup_count}, 输出行数={line_count}"
    )

    print(f"\n合并完成，共 {len(all_records)} 条唯一记录 → {output_file}")
    print(f"  发现问题记录: {issue_count}（已记录到 clean.log）")
    print(f"  重复记录: {dup_count}")
    print(f"文件行数: {line_count}")

    if line_count < 8:
        logger.error(f"行数不足: {line_count} < 8")
        raise AssertionError(f"行数不足: {line_count} < 8")

    logger.info("✓ 行数验证通过 (>= 8)")
    print("✓ 行数验证通过 (>= 8)")
    logger.info("=== 合并任务结束 ===")


if __name__ == "__main__":
    main()
