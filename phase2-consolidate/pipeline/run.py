#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据清洗流水线脚本
读取 d04 目录下的原始数据文件，清洗后输出四类 JSON 及清洗报告
"""

import json
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple

# ==================== 配置 ====================
INPUT_DIR = Path("d:/camp-data/raw/generated/d04")
OUTPUT_DIR = Path("d:/camp-data/phase2-consolidate/output")
REPORT_PATH = Path("d:/camp-data/phase2-consolidate/output/report.md")

# 停顿词定义（中文口语填充词）
STOP_WORDS = {
    "嗯", "啊", "哦", "呃", "那个", "就是", "然后", "其实", "我想想",
    "稍等", "麻烦", "help", "<<<<", ">>>>", "[ASR]", "（口述）",
    "```", "<p>", "</p>", "<!--", "-->", "<!--done-->",
    "<!-- cached -->", "[draft]", "#todo", "cache=false", "ENDEND",
    "stdout:", "OK", "@@@", "……", "~", "😅",
}

# 停顿词正则（用于统计）
STOP_WORDS_PATTERN = re.compile(
    r"(嗯+|啊+|哦+|呃+|那个|就是|然后然后?|其实|我想想|稍等|麻烦|help:)",
    re.IGNORECASE
)

# 时间格式解析
TIME_PATTERNS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y年%m月%d日 %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d %H:%M",
]


# ==================== 工具函数 ====================
def ensure_dir(path: Path):
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)


def parse_time(ts_str: str) -> str:
    """解析多种时间格式为标准 ISO 格式"""
    if not ts_str or not ts_str.strip():
        return ""
    ts_str = ts_str.strip()
    for pattern in TIME_PATTERNS:
        try:
            dt = datetime.strptime(ts_str, pattern)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    # 尝试清理后解析
    cleaned = re.sub(r"\+\d{2}:\d{2}$", "", ts_str)
    cleaned = re.sub(r"T", " ", cleaned)
    for pattern in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(cleaned, pattern)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return ts_str  # 返回原始值


def clean_text(text: str) -> Tuple[str, Dict[str, int]]:
    """
    清洗文本：去除停顿词、多余空白、特殊标记
    返回: (清洗后文本, 停顿词统计)
    """
    if not text:
        return "", {}

    stop_word_counts = Counter()

    # 统计停顿词出现次数
    for match in STOP_WORDS_PATTERN.finditer(text):
        word = match.group(0).lower()
        stop_word_counts[word] += 1

    # 去除各种噪音标记
    cleaned = text
    # 去除 HTML 标签
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    # 去除 markdown 代码块标记
    cleaned = re.sub(r"```", "", cleaned)
    # 去除注释标记
    cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
    # 去除特定标记
    cleaned = re.sub(r"\[ASR\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[draft\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"#todo", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"cache=false", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"ENDEND", "", cleaned)
    cleaned = re.sub(r"<<<<.*?>>>>", "", cleaned)
    cleaned = re.sub(r"（口述）", "", cleaned)
    cleaned = re.sub(r"stdout:\s*OK", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"@@@", "", cleaned)
    cleaned = re.sub(r"😅", "", cleaned)
    cleaned = re.sub(r"~", "", cleaned)
    cleaned = re.sub(r"……", "", cleaned)

    # 去除停顿词
    for sw in sorted(STOP_WORDS, key=len, reverse=True):
        pattern = re.escape(sw)
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # 清理多余空白
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip()

    return cleaned, dict(stop_word_counts)


def read_jsonl(filepath: Path) -> List[Dict[str, Any]]:
    """读取 JSONL 文件"""
    records = []
    if not filepath.exists():
        return records
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def read_csv_file(filepath: Path) -> List[Dict[str, Any]]:
    """读取 CSV 文件"""
    records = []
    if not filepath.exists():
        return records
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(dict(row))
    return records


def read_txt_file(filepath: Path) -> List[Dict[str, Any]]:
    """读取 TXT 文件（按行解析为简单记录）"""
    records = []
    if not filepath.exists():
        return records
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            # 尝试解析为 JSON
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # 作为纯文本记录
                records.append({"line_no": i + 1, "text": line})
    return records


def read_file_auto(filepath: Path) -> List[Dict[str, Any]]:
    """自动根据扩展名读取文件"""
    suffix = filepath.suffix.lower()
    if suffix == ".jsonl" or suffix == ".json":
        return read_jsonl(filepath)
    elif suffix == ".csv":
        return read_csv_file(filepath)
    elif suffix == ".txt":
        return read_txt_file(filepath)
    else:
        # 默认尝试 JSONL
        return read_jsonl(filepath)


def write_json(records: List[Dict[str, Any]], filepath: Path):
    """写入 JSON 文件（美化格式）"""
    ensure_dir(filepath.parent)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ==================== 清洗处理器 ====================
class CleaningReport:
    """清洗报告收集器"""

    def __init__(self):
        self.input_stats = {}
        self.output_stats = {}
        self.anomaly_counts = Counter()
        self.stop_word_stats = Counter()
        self.cleaning_rules = []
        self.examples = []  # (原始, 清洗后) 对比样例
        self.rule_details = defaultdict(Counter)

    def add_rule(self, name: str, description: str, count: int = 0):
        self.cleaning_rules.append({
            "name": name,
            "description": description,
            "count": count
        })

    def add_example(self, original: str, cleaned: str, source: str = ""):
        if len(self.examples) < 10:  # 最多保留 10 个样例
            self.examples.append({
                "source": source,
                "original": original[:200] + "..." if len(original) > 200 else original,
                "cleaned": cleaned[:200] + "..." if len(cleaned) > 200 else cleaned
            })

    def generate_report(self) -> str:
        """生成 Markdown 格式的清洗报告"""
        lines = []
        lines.append("# 数据清洗报告")
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 输入统计
        lines.append("## 输入统计")
        lines.append("")
        for name, stats in self.input_stats.items():
            lines.append(f"- **{name}**: {stats.get('count', 0)} 条记录")
        lines.append("")

        # 输出统计
        lines.append("## 输出统计")
        lines.append("")
        for name, stats in self.output_stats.items():
            lines.append(f"- **{name}**: {stats.get('count', 0)} 条记录")
            if "dropped" in stats:
                lines.append(f"  - 丢弃: {stats['dropped']} 条")
            if "cleaned_fields" in stats:
                lines.append(f"  - 清洗字段数: {stats['cleaned_fields']}")
        lines.append("")

        # 清洗规则
        lines.append("## 清洗规则")
        lines.append("")
        for i, rule in enumerate(self.cleaning_rules, 1):
            lines.append(f"{i}. **{rule['name']}**: {rule['description']}")
            if rule['count'] > 0:
                lines.append(f"   - 触发次数: {rule['count']}")
        lines.append("")

        # 停顿词统计
        lines.append("## 停顿词统计")
        lines.append("")
        if self.stop_word_stats:
            lines.append("| 停顿词 | 出现次数 |")
            lines.append("|--------|----------|")
            for word, count in self.stop_word_stats.most_common():
                lines.append(f"| {word} | {count} |")
        else:
            lines.append("未发现明显停顿词。")
        lines.append("")

        # 异常计数
        lines.append("## 异常计数")
        lines.append("")
        if self.anomaly_counts:
            lines.append("| 异常类型 | 计数 |")
            lines.append("|----------|------|")
            for anomaly, count in self.anomaly_counts.most_common():
                lines.append(f"| {anomaly} | {count} |")
        else:
            lines.append("未发现异常。")
        lines.append("")

        # 样例对比
        lines.append("## 清洗样例对比")
        lines.append("")
        for i, ex in enumerate(self.examples[:5], 1):
            lines.append(f"### 样例 {i} ({ex['source']})")
            lines.append("")
            lines.append("**原始文本:**")
            lines.append(f"```\n{ex['original']}\n```")
            lines.append("")
            lines.append("**清洗后:**")
            lines.append(f"```\n{ex['cleaned']}\n```")
            lines.append("")

        return "\n".join(lines)


def process_chat_logs(records: List[Dict], report: CleaningReport) -> List[Dict]:
    """处理聊天日志 -> chat_turns.json"""
    results = []
    cleaned_count = 0
    dropped = 0
    stop_word_total = Counter()

    for rec in records:
        text = rec.get("text", "")
        if not text or not text.strip():
            dropped += 1
            report.anomaly_counts["空文本记录"] += 1
            continue

        cleaned_text, stop_counts = clean_text(text)
        stop_word_total.update(stop_counts)

        # 记录样例
        if stop_counts and len(report.examples) < 10:
            report.add_example(text, cleaned_text, "chat_logs")

        if not cleaned_text or not cleaned_text.strip():
            dropped += 1
            report.anomaly_counts["清洗后为空"] += 1
            continue

        # 标准化 UID（统一为小写）
        uid = str(rec.get("uid", "")).lower()

        # 解析时间
        ts = parse_time(rec.get("ts", ""))
        if not ts:
            report.anomaly_counts["时间解析失败"] += 1

        # 清洗角色字段
        role = rec.get("role", "").strip().lower()
        if role not in {"user", "assistant", "tool"}:
            report.anomaly_counts["未知角色"] += 1

        results.append({
            "session_id": rec.get("session", ""),
            "uid": uid,
            "role": role,
            "text": cleaned_text,
            "timestamp": ts,
        })
        cleaned_count += 1

    report.input_stats["chat_logs"] = {"count": len(records)}
    report.output_stats["chat_turns"] = {
        "count": len(results),
        "dropped": dropped,
        "cleaned_fields": cleaned_count
    }
    report.stop_word_stats.update(stop_word_total)
    report.add_rule("停顿词过滤", "去除 '嗯、啊、哦、那个' 等无意义口语词", sum(stop_word_total.values()))
    report.add_rule("时间格式标准化", "统一多种时间格式为 ISO 8601", len(results))
    report.add_rule("UID 标准化", "统一用户 ID 为小写格式", len(results))

    return results


def process_knowledge(records: List[Dict], report: CleaningReport) -> List[Dict]:
    """处理知识库记录 -> knowledge_items.json"""
    results = []
    dropped = 0
    stop_word_total = Counter()

    for rec in records:
        body = rec.get("body", "")
        title = rec.get("title", "")

        if not body or not body.strip():
            dropped += 1
            report.anomaly_counts["知识条目空内容"] += 1
            continue

        cleaned_body, stop_counts = clean_text(body)
        stop_word_total.update(stop_counts)

        cleaned_title, _ = clean_text(title)

        if stop_counts and len(report.examples) < 10:
            report.add_example(body, cleaned_body, "knowledge")

        if not cleaned_body or not cleaned_body.strip():
            dropped += 1
            report.anomaly_counts["知识清洗后为空"] += 1
            continue

        # 解析时间
        source_time = parse_time(rec.get("source_time", ""))
        if not source_time:
            report.anomaly_counts["知识时间解析失败"] += 1

        # 清洗 tags
        tags_str = rec.get("tags", "")
        tags = [t.strip() for t in tags_str.split("#") if t.strip()]

        results.append({
            "item_id": rec.get("item_id", ""),
            "title": cleaned_title,
            "tags": tags,
            "body": cleaned_body,
            "source_time": source_time,
        })

    report.input_stats["knowledge"] = {"count": len(records)}
    report.output_stats["knowledge_items"] = {
        "count": len(results),
        "dropped": dropped,
        "cleaned_fields": len(results)
    }
    report.stop_word_stats.update(stop_word_total)
    report.add_rule("知识内容清洗", "去除口语停顿词和噪音标记", sum(stop_word_total.values()))
    report.add_rule("标签解析", "将 #标签 字符串解析为数组", len(results))

    return results


def process_preferences(records: List[Dict], report: CleaningReport) -> List[Dict]:
    """处理偏好记录 -> preferences.json"""
    results = []
    dropped = 0
    stop_word_total = Counter()

    for rec in records:
        pref_value = rec.get("pref_value", "")
        if not pref_value or not pref_value.strip():
            dropped += 1
            report.anomaly_counts["偏好值为空"] += 1
            continue

        cleaned_value, stop_counts = clean_text(pref_value)
        stop_word_total.update(stop_counts)

        if stop_counts and len(report.examples) < 10:
            report.add_example(pref_value, cleaned_value, "preferences")

        if not cleaned_value or not cleaned_value.strip():
            dropped += 1
            report.anomaly_counts["偏好清洗后为空"] += 1
            continue

        # 标准化 note 字段
        note = rec.get("note", "").strip()
        note_mapping = {
            "仅本次例外": "temporary",
            "重复记录": "duplicate",
            "管理员导入旧偏好": "imported",
            "用户明确表达": "explicit",
            "用户纠正": "corrected",
        }
        note_category = note_mapping.get(note, "other")

        results.append({
            "pref_id": rec.get("pref_id", ""),
            "uid": str(rec.get("uid", "")).lower(),
            "pref_key": rec.get("pref_key", "").strip(),
            "pref_value": cleaned_value,
            "version": rec.get("version", ""),
            "note_category": note_category,
            "note_original": note,
        })

    report.input_stats["preferences"] = {"count": len(records)}
    report.output_stats["preferences"] = {
        "count": len(results),
        "dropped": dropped,
        "cleaned_fields": len(results)
    }
    report.stop_word_stats.update(stop_word_total)
    report.add_rule("偏好值清洗", "去除口语停顿词和格式标记", sum(stop_word_total.values()))
    report.add_rule("note 标准化", "将中文 note 映射为分类标签", len(results))

    return results


def process_tool_executions(records: List[Dict], report: CleaningReport) -> List[Dict]:
    """处理工具执行记录 -> tool_executions.json"""
    results = []
    dropped = 0
    stop_word_total = Counter()
    seen_traces = set()
    duplicates = 0

    for rec in records:
        raw_output = rec.get("raw_output", "")
        if not raw_output or not raw_output.strip():
            dropped += 1
            report.anomaly_counts["工具输出为空"] += 1
            continue

        cleaned_output, stop_counts = clean_text(raw_output)
        stop_word_total.update(stop_counts)

        if stop_counts and len(report.examples) < 10:
            report.add_example(raw_output, cleaned_output, "tool_executions")

        if not cleaned_output or not cleaned_output.strip():
            dropped += 1
            report.anomaly_counts["工具输出清洗后为空"] += 1
            continue

        trace = rec.get("trace", "")
        # 去重
        if trace in seen_traces:
            duplicates += 1
            report.anomaly_counts["重复 trace"] += 1
            continue
        seen_traces.add(trace)

        # 清洗 exec_ms（处理字符串数字）
        exec_ms = rec.get("exec_ms", 0)
        try:
            exec_ms = int(exec_ms)
        except (ValueError, TypeError):
            exec_ms = 0
            report.anomaly_counts["exec_ms 格式异常"] += 1

        # 标准化 status
        status = rec.get("status", "").strip().lower()
        if status not in {"ok", "fail", "error"}:
            report.anomaly_counts["未知状态码"] += 1

        results.append({
            "trace": trace,
            "tool": rec.get("tool", "").strip(),
            "status": status,
            "output": cleaned_output,
            "exec_ms": exec_ms,
        })

    report.input_stats["tool_executions"] = {"count": len(records)}
    report.output_stats["tool_executions"] = {
        "count": len(results),
        "dropped": dropped,
        "duplicates_removed": duplicates,
        "cleaned_fields": len(results)
    }
    report.stop_word_stats.update(stop_word_total)
    report.add_rule("工具输出清洗", "去除口语停顿词和噪音标记", sum(stop_word_total.values()))
    report.add_rule("trace 去重", "移除重复的工具调用记录", duplicates)
    report.add_rule("数值字段清洗", "将 exec_ms 统一为整数类型", len(results))

    return results


# ==================== 主流程 ====================
def main():
    print("=" * 50)
    print("数据清洗流水线启动")
    print("=" * 50)

    # 确保输出目录存在
    ensure_dir(OUTPUT_DIR)

    report = CleaningReport()

    # 发现输入文件
    input_files = list(INPUT_DIR.iterdir())
    print(f"\n发现输入文件 ({len(input_files)} 个):")
    for f in input_files:
        print(f"  - {f.name}")

    # 处理 chat_logs -> chat_turns.json
    chat_file = INPUT_DIR / "chat_logs_raw.jsonl"
    if chat_file.exists():
        print(f"\n[1/4] 处理聊天日志: {chat_file.name}")
        records = read_file_auto(chat_file)
        chat_turns = process_chat_logs(records, report)
        out_path = OUTPUT_DIR / "chat_turns.json"
        write_json(chat_turns, out_path)
        print(f"  输入: {len(records)} 条 -> 输出: {len(chat_turns)} 条 -> {out_path}")

    # 处理 knowledge -> knowledge_items.json
    knowledge_file = INPUT_DIR / "knowledge_raw.jsonl"
    if knowledge_file.exists():
        print(f"\n[2/4] 处理知识库记录: {knowledge_file.name}")
        records = read_file_auto(knowledge_file)
        knowledge_items = process_knowledge(records, report)
        out_path = OUTPUT_DIR / "knowledge_items.json"
        write_json(knowledge_items, out_path)
        print(f"  输入: {len(records)} 条 -> 输出: {len(knowledge_items)} 条 -> {out_path}")

    # 处理 preferences -> preferences.json
    pref_file = INPUT_DIR / "preferences_raw.csv"
    if pref_file.exists():
        print(f"\n[3/4] 处理偏好记录: {pref_file.name}")
        records = read_file_auto(pref_file)
        preferences = process_preferences(records, report)
        out_path = OUTPUT_DIR / "preferences.json"
        write_json(preferences, out_path)
        print(f"  输入: {len(records)} 条 -> 输出: {len(preferences)} 条 -> {out_path}")

    # 处理 tool_results -> tool_executions.json
    tool_file = INPUT_DIR / "tool_result_raw.jsonl"
    if tool_file.exists():
        print(f"\n[4/4] 处理工具执行记录: {tool_file.name}")
        records = read_file_auto(tool_file)
        tool_executions = process_tool_executions(records, report)
        out_path = OUTPUT_DIR / "tool_executions.json"
        write_json(tool_executions, out_path)
        print(f"  输入: {len(records)} 条 -> 输出: {len(tool_executions)} 条 -> {out_path}")

    # 生成报告
    print(f"\n[报告] 生成清洗报告: {REPORT_PATH}")
    report_md = report.generate_report()
    ensure_dir(REPORT_PATH.parent)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_md)

    print("\n" + "=" * 50)
    print("数据清洗流水线完成")
    print("=" * 50)
    print(f"\n输出文件:")
    for f in OUTPUT_DIR.iterdir():
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
