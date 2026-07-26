"""KnowledgeTreeExtractor 解析逻辑回归测试。

修复背景：curriculum_standards.txt 中"数与代数:"等分类头行曾被误收为知识点，
导致出题功能的知识点标签出现多余冒号。
"""

from pathlib import Path

from kag_pro.core.paper_generator import KnowledgeTreeExtractor

_STANDARDS_FIXTURE = """# 课程标准测试夹具（与真实文件结构一致：注释行 + ==== 分隔）
================================================================================
一、小学阶段 (1-6年级)
================================================================================

[数学]
数与代数:
  数的认识 (自然数/整数/小数/分数)
  数的运算 (加减乘除/四则混合运算)
图形与几何:
  图形的认识 (点线面角/三角形)
数学常见错误类型:
  计算粗心(进退位/小数点)
  单位换算混淆(长度/面积)

[语文]
识字与写字 (拼音/笔画)
阅读 (记叙文/说明文)
"""


def _make_extractor(tmp_path: Path, text: str = _STANDARDS_FIXTURE) -> KnowledgeTreeExtractor:
    p = tmp_path / "standards.txt"
    p.write_text(text, encoding="utf-8")
    return KnowledgeTreeExtractor(str(p))


def test_category_headers_not_treated_as_topics(tmp_path):
    """以冒号结尾的分类头（数与代数:/图形与几何:）不得进入知识点列表。"""
    tree = _make_extractor(tmp_path)
    topics = tree.get_topics("小学", "数学")
    assert topics, "应解析出数学知识点"
    assert all(not t.endswith((":", "：")) for t in topics)
    assert "数与代数:" not in topics
    assert "图形与几何:" not in topics


def test_real_topics_preserved(tmp_path):
    """分类头下的真实知识点（含括号说明行）必须保留。"""
    tree = _make_extractor(tmp_path)
    topics = tree.get_topics("小学", "数学")
    assert "数的认识 (自然数/整数/小数/分数)" in topics
    assert "图形的认识 (点线面角/三角形)" in topics


def test_error_block_content_excluded(tmp_path):
    """常见错误类型块的内容行不得混入知识点。"""
    tree = _make_extractor(tmp_path)
    topics = tree.get_topics("小学", "数学")
    assert not any("粗心" in t or "混淆" in t for t in topics)


def test_no_topic_contains_colon_in_real_standards():
    """真实课程标准文件：全部学段学科的知识点标签均不含冒号。"""
    tree = KnowledgeTreeExtractor().get_tree()
    bad = [
        (stage, subject, t)
        for stage, subjects in tree.items()
        for subject, topics in subjects.items()
        for t in topics
        if ":" in t or "：" in t
    ]
    assert bad == [], f"仍存在带冒号知识点: {bad}"
