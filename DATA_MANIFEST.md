# KAG-Pro 外部数据集清单 (External Data Manifest)

## 数据集来源与许可

本项目使用了三个外部公开数据集。数据集文件未包含在仓库中，
需从原始来源下载后放置到对应路径。

---

### 1. Math23K — 中文数学应用题

| 项目 | 内容 |
|---|---|
| 名称 | Math23K |
| 来源 | https://github.com/SCNU203/Math23k |
| 许可 | 开源 (见仓库 LICENSE 文件) |
| 数量 | 22,161 题 (训练集) |
| 格式 | 多行 JSON: {id, original_text, segmented_text, equation, ans} |
| 放置路径 | `src/kag_pro/data/external/math23k_train.json` |
| 用途 | RAG 问答检索、数学推理评测 |
| 引用 | Wang Y, Liu X, Shi S. "Deep Neural Solver for Math Word Problems". EMNLP 2017. |

```
git clone https://github.com/SCNU203/Math23k.git
cp Math23k/math23k_train.json src/kag_pro/data/external/
```

---

### 2. SC-Ques — 英语句子补全

| 项目 | 内容 |
|---|---|
| 名称 | SC-Ques (Sentence Completion Questions) |
| 来源 | https://github.com/ai4ed/SC-Ques |
| 下载 | https://www.dropbox.com/s/lzznin2hxt6rmft/SC-Ques.tar.gz |
| 许可 | 开源 (见仓库 LICENSE 文件) |
| 数量 | 289,148 题 (C1-C4 四个难度) |
| 格式 | JSONL: {stem, choice, answer, choice_dict} |
| 放置路径 | `src/kag_pro/data/external/SC-Ques-main/datasets/SC-Ques/` |
| 用途 | 英语句子补全、跨语言 RAG 测试 |
| 引用 | "SC-Ques: A Sentence Completion Question Dataset for ESL Learners" |

```bash
# 下载并解压
wget https://www.dropbox.com/s/lzznin2hxt6rmft/SC-Ques.tar.gz
tar -xzf SC-Ques.tar.gz -C src/kag_pro/data/external/SC-Ques-main/datasets/
```

---

### 3. 智慧学伴 K-12 — 微测评数据

| 项目 | 内容 |
|---|---|
| 名称 | Smart Learning Companion (智慧学伴) |
| 来源 | 北京师范大学未来教育高精尖创新中心 |
| 许可 | 研究用途 (需向数据提供方申请) |
| 数量 | 314,520 条 (7 科: 数学/物理/生物/语文/英语/地理/历史) |
| 格式 | CSV: student_id, subject_abbr, exam_id, question_id, concept, score |
| 放置路径 | `src/kag_pro/data/external/unit-*.csv` |
| 用途 | 知识追踪、知识点掌握度分析、题目难度估计 |
| 注意 | 数据仅包含学生ID/知识点/得分，不含题目文本和学生答案 |
| 缺科 | 化学 (unit-che.csv) 因网页丢失未下载 |

---

## 数据统计

| 数据集 | 数量 | 语言 | 学科 | 已集成 |
|---|---|---|---|---|
| Math23K | 22,161 | 中文 | 数学 | ✅ |
| SC-Ques | 289,148 | 英语 | 英语 | ✅ |
| 智慧学伴-生物 | 84,037 | 中文 | 生物 | ✅ |
| 智慧学伴-历史 | 68,279 | 中文 | 历史 | ✅ |
| 智慧学伴-数学 | 57,244 | 中文 | 数学 | ✅ |
| 智慧学伴-物理 | 38,416 | 中文 | 物理 | ✅ |
| 智慧学伴-地理 | 31,414 | 中文 | 地理 | ✅ |
| 智慧学伴-语文 | 30,056 | 中文 | 语文 | ✅ |
| 智慧学伴-英语 | 5,074 | 中文 | 英语 | ✅ |
| **总计** | **625,829** | | | |

---

## 自建数据

以下为项目自行编写的数据，不涉及外部版权：

| 数据 | 内容 |
|---|---|
| 18 个教材专题 | 基于中国课程标准自行编写，覆盖小/初/高/大学 |
| curriculum_standards.txt | 学科分类标准参考，整理自公开课程标准 |
| test_errors_middle.txt | 初中错题测试集，自行设计 |
