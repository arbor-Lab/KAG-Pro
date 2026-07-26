"""Batch generate textbooks from comprehensive outline.

Delegates all generation logic to TextbookGenerator so every file goes
through the P0 quality gates (completeness retry, science fact-check,
manifest traceability). Incomplete legacy files are auto-regenerated.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kag_pro.datasets.textbook_generator import TextbookGenerator, COMPREHENSIVE_OUTLINE


def main():
    output_dir = Path(__file__).resolve().parent.parent / "src" / "kag_pro" / "data" / "textbooks"
    total = sum(
        len(topics)
        for subjects in COMPREHENSIVE_OUTLINE.values()
        for topics in subjects.values()
    )
    gen = TextbookGenerator()
    count = gen.generate_from_outline(COMPREHENSIVE_OUTLINE, output_dir)
    print(f"\nDone: {count} generated/regenerated, {total} total topics")


if __name__ == "__main__":
    main()
