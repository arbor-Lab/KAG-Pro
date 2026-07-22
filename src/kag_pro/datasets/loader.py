"""Loaders for external educational datasets: SC-Ques, Math23K, Smart Learning Companion.

SC-Ques:   289K English sentence completion questions (ai4ed/SC-Ques)
           Format: JSON lines with {question, choices, answer, difficulty}
           Source: https://github.com/ai4ed/SC-Ques

Math23K:   23K Chinese math word problems with equations
           Format: JSON with {id, original_text, equation, ans}
           Source: https://github.com/SCNU203/Math23K

智慧学伴:   K-12 multi-disciplinary assessment data from BNU
           Format: CSV with {student_id, question, answer, score, knowledge_point}
           Source: Beijing Normal University Smart Learning Companion
"""

import csv
import json
from pathlib import Path


class DatasetLoader:
    """Base class for dataset loading."""

    @staticmethod
    def from_jsonl(path: str) -> list[dict]:
        items = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        return items

    @staticmethod
    def from_json(path: str) -> list[dict]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def from_csv(path: str) -> list[dict]:
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))


class Math23KLoader:
    """Loader for Math23K Chinese math word problem dataset.

    Actual format (concatenated JSON objects):
    {"id":"1","original_text":"...","segmented_text":"...","equation":"...","ans":"..."}
    {"id":"2",...}
    ...

    Train: 22,162 questions | Test: ~1,000 questions
    """

    @staticmethod
    def load(path: str) -> list[dict]:
        import json
        import re
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        parts = re.split(r'\}\n\{', raw)
        if parts[0].startswith('{'):
            parts[0] = parts[0][1:]
        if parts[-1].endswith('}'):
            parts[-1] = parts[-1][:-1]
        items = []
        for part in parts:
            try:
                items.append(json.loads('{' + part + '}'))
            except json.JSONDecodeError:
                pass
        return items

    @staticmethod
    def to_qa_pairs(data: list[dict]) -> list[dict]:
        """Convert Math23K items to QA format for our system."""
        return [
            {
                "question": item.get("original_text", ""),
                "answer": f"答案: {item.get('ans', '')}。方程: {item.get('equation', '')}",
                "subject": "math",
                "stage": "primary",
            }
            for item in data
        ]


class SCQuesLoader:
    """Loader for SC-Ques English sentence completion dataset.

    Actual format (JSONL, 289K total):
    {"stem": "The plane is scheduled to arrive ___ .",
     "choice": {"A": "A.latest", "B": "B.later", "C": "C.late", "D": "D.lately"},
     "answer": "C",
     "choice_dict": {"A": "...A.latest", "B": "...B.later", "C": "...C.late", "D": "...D.lately"}}

    Use for: English grammar/sentence completion practice, cross-lingual RAG testing.
    """

    @staticmethod
    def load(path: str) -> list[dict]:
        return DatasetLoader.from_jsonl(path)

    @staticmethod
    def to_qa_pairs(data: list[dict]) -> list[dict]:
        """Convert SC-Ques items to fill-in-the-blank QA format."""
        pairs = []
        for item in data:
            stem = item.get("stem", "")
            choices = item.get("choice", {})
            correct = item.get("answer", "")
            choices_text = "; ".join(f"{k}. {v}" for k, v in sorted(choices.items()))
            question = f"Fill in the blank: {stem.strip()} Options: {choices_text}"
            answer = f"The correct answer is {correct}: {choices.get(correct, '')}"
            pairs.append({
                "question": question,
                "answer": answer,
                "subject": "english",
                "stage": "middle",
                "difficulty": item.get("difficulty", "unknown"),
            })
        return pairs

    @staticmethod
    def to_textbook_chunks(data: list[dict], chunk_size: int = 20) -> list[str]:
        """Group SC-Ques items into textbook-style chunks for indexing."""
        chunks = []
        for i in range(0, len(data), chunk_size):
            batch = data[i:i + chunk_size]
            text = "SC-Ques English Sentence Completion\\n\\n"
            for item in batch:
                stem = item.get("stem", "")
                choices = item.get("choice", {})
                correct = item.get("answer", "")
                text += f"Q: {stem.strip()}\\n"
                text += f"Choices: {' | '.join(f'{k}) {v}' for k, v in sorted(choices.items()))}\\n"
                text += f"A: {correct}\\n\\n"
            chunks.append(text)
        return chunks


class SmartLearningLoader:
    """Loader for Smart Learning Companion K-12 assessment data.

    Actual format (micro-assessment CSV):
    student_id,subject_abbr,exam_id,question_id,concept,score
    abc123,MATH,uuid-1,q-001,一元二次方程,1.0

    Note: No question text or student answers available.
    Use for: knowledge point mastery analysis, difficulty estimation.
    """

    SUBJECT_MAP = {
        "MATH": "math", "PHY": "physics", "CHEM": "chemistry",
        "BIO": "biology", "CHI": "chinese", "ENG": "english",
        "GEO": "geography", "HIST": "history",
    }

    @staticmethod
    def load(path: str) -> list[dict]:
        return DatasetLoader.from_csv(path)

    @staticmethod
    def load_all(data_dir: str) -> dict:
        """Load all subject CSVs from a directory."""
        import csv
        import os
        all_data = {}
        for fname in sorted(os.listdir(data_dir)):
            if fname.startswith("unit-") and fname.endswith(".csv"):
                subject_key = fname.replace("unit-", "").replace(".csv", "")
                fpath = os.path.join(data_dir, fname)
                with open(fpath, encoding="utf-8-sig") as f:
                    all_data[subject_key] = list(csv.DictReader(f))
        return all_data

    @staticmethod
    def to_knowledge_mastery(data: list[dict]) -> dict:
        """Aggregate by concept: {concept: {avg_score, total_attempts, error_rate}}"""
        from collections import defaultdict
        concepts = defaultdict(lambda: {"scores": [], "count": 0})
        for item in data:
            concept = item.get("concept", "unknown")
            score = float(item.get("score", 0))
            concepts[concept]["scores"].append(score)
            concepts[concept]["count"] += 1
        result = {}
        for concept, info in concepts.items():
            scores = info["scores"]
            result[concept] = {
                "avg_score": round(sum(scores) / len(scores), 3),
                "attempts": len(scores),
                "error_rate": round(sum(1 for s in scores if s == 0) / len(scores), 3),
            }
        return result

    @staticmethod
    def to_question_difficulty(data: list[dict]) -> dict:
        """Estimate question difficulty: {question_id: {avg_score, attempts}}"""
        from collections import defaultdict
        questions = defaultdict(lambda: {"scores": []})
        for item in data:
            qid = item.get("question_id", "unknown")
            score = float(item.get("score", 0))
            questions[qid]["scores"].append(score)
        result = {}
        for qid, info in questions.items():
            scores = info["scores"]
            result[qid] = {
                "avg_score": round(sum(scores) / len(scores), 3),
                "attempts": len(scores),
                "difficulty": round(1.0 - sum(scores) / len(scores), 3),
            }
        return result

    @staticmethod
    def to_student_profiles(data: list[dict]) -> dict:
        """Group by student: {student_id: {concept: avg_score}}"""
        from collections import defaultdict
        students = defaultdict(lambda: defaultdict(list))
        for item in data:
            sid = item.get("student_id", "unknown")
            concept = item.get("concept", "unknown")
            score = float(item.get("score", 0))
            students[sid][concept].append(score)
        result = {}
        for sid, concepts in students.items():
            result[sid] = {
                c: round(sum(s) / len(s), 3)
                for c, s in concepts.items()
            }
        return result


class DatasetIntegrator:
    """Integrate external datasets into KAG-Pro pipeline."""

    @staticmethod
    def integrate_math23k(data: list[dict], output_dir: str) -> int:
        """Convert Math23K problems into textbook chunks."""

        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        # Group by topic (simple heuristic based on keywords)
        topics = {"arithmetic": [], "fraction": [], "geometry": [], "application": []}
        for item in data:
            text = item.get("original_text", "")
            if any(kw in text for kw in ["分数", "百分数", "比"]):
                topics["fraction"].append(item)
            elif any(kw in text for kw in ["面积", "周长", "体积", "角"]):
                topics["geometry"].append(item)
            elif any(kw in text for kw in ["一共", "剩下", "多少", "买"]):
                topics["application"].append(item)
            else:
                topics["arithmetic"].append(item)

        count = 0
        for topic, items in topics.items():
            if not items:
                continue
            chunk_size = 10
            for i in range(0, len(items), chunk_size):
                batch = items[i:i + chunk_size]
                text = f"Math23K - {topic}\n\n" + "\n".join(
                    f"Q: {item.get('original_text', '')}\nA: {item.get('ans', '')} ({item.get('equation', '')})"
                    for item in batch
                )
                fpath = output / f"math23k_{topic}_{i // chunk_size}.txt"
                fpath.write_text(text, encoding="utf-8")
                count += 1

        return count

    @staticmethod
    def integrate_errors(data: list[dict], output_path: str) -> int:
        """Save error pairs for diagnosis testing."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# 智慧学伴错题数据\n")
            for item in data:
                f.write(f"{item['question']} || {item['student_answer']} || {item['correct_answer']} || concept_confusion\n")
        return len(data)
