"""Batch generate textbooks from comprehensive outline."""

import sys, time, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kag_pro.datasets.textbook_generator import TextbookGenerator, COMPREHENSIVE_OUTLINE
from kag_pro.core.generator import Generator


def main():
    gen = Generator()
    output_dir = Path(__file__).resolve().parent.parent / "src" / "kag_pro" / "data" / "textbooks"
    output_dir.mkdir(parents=True, exist_ok=True)

    total = sum(len(topics) for topics in COMPREHENSIVE_OUTLINE.values())
    done = 0
    failed = 0

    # Short name mapping for filenames
    name_map = {
        "初中物理": ("mid", "phy"), "初中化学": ("mid", "che"), "初中数学": ("mid", "mat"),
        "初中生物": ("mid", "bio"), "初中地理": ("mid", "geo"), "初中历史": ("mid", "his"),
        "高中物理": ("hig", "phy"), "高中化学": ("hig", "che"), "高中数学": ("hig", "mat"),
        "高中生物": ("hig", "bio"), "高中地理": ("hig", "geo"), "高中历史": ("hig", "his"),
        "小学数学": ("ele", "mat"), "小学奥数": ("ele", "oly"),
    }

    for subject, topics in COMPREHENSIVE_OUTLINE.items():
        stage_code, subj_code = name_map.get(subject, ("gen", "gen"))
        for i, topic in enumerate(topics):
            fname = f"gen_{stage_code}_{subj_code}_{i+1:02d}.txt"
            fpath = output_dir / fname

            if fpath.exists():
                done += 1
                continue

            print(f"[{done+failed+1}/{total}] {subject}: {topic}")

            prompt = f"""你是一位中国{subject}教师。请编写关于"{topic}"的教材内容。

要求：
1. 知识点定义清晰准确，公式正确无误
2. 包含至少2个例题或示例
3. 标注1-2个学生常见的错误理解及纠正方法
4. 用初高中学生能理解的语言
5. 控制在200-400字
6. 分小节组织，用"一、二、三"格式

直接输出教材内容，不要加前言结语。"""

            try:
                text = gen.call(
                    system="你是一位中国教育教师。", user=prompt, temperature=0.2, max_tokens=600
                )
                if text:
                    header = f"{subject} - {topic}\n\n"
                    fpath.write_text(header + text, encoding="utf-8")
                    done += 1
                else:
                    failed += 1
                    print(f"  FAILED: empty response")
            except Exception as e:
                failed += 1
                print(f"  ERROR: {e}")
                time.sleep(2)

            time.sleep(0.3)  # Rate limit

    print(f"\nDone: {done} generated, {failed} failed, {done+failed}/{total}")

if __name__ == "__main__":
    main()
