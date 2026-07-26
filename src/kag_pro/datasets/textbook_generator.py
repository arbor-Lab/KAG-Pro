"""Auto-generate textbook entries from curriculum standards using LLM.

P0 quality gates (added after audit found 71% of legacy files truncated):
- max_tokens raised 800 -> 2000, then 4000 for broad humanities topics
- completeness gate (body length + ending punctuation) with retries
- no-Markdown prompt aligned with the QA pipeline's system prompt
- one LLM fact-check pass for science subjects (formula/theorem risk);
  verdict must START with "有误" (substring match would false-positive
  on "经检查无误")
- DashScope (Qwen) fallback channel for topics the primary provider
  repeatedly fails (e.g. politics content refusals)
- existing files are re-validated: incomplete ones are regenerated
- generation_manifest.json records model/time per file for traceability
"""

import json
import time
from datetime import datetime
from pathlib import Path

from kag_pro.core.generator import Generator
from kag_pro.utils.config import get_config

# Quality gate thresholds.
_MIN_BODY_CHARS = 300
_END_PUNCT = (
    "。", "！", "？", "；", "：", "）", "】", "”", "’", ".", "…", "$",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
)
_MAX_RETRIES = 2

# Science subjects get an extra LLM fact-check pass (formula/theorem risk).
_FACT_CHECK_SUBJECTS = {"数学", "物理", "化学", "生物", "奥数", "科学"}

# Filename code mappings (kept in sync with loader's gen_* contract).
_STAGE_CODES = {"小学": "ele", "初中": "mid", "高中": "hig"}
_SUBJECT_CODES = {
    "数学": "mat", "语文": "chi", "英语": "eng", "科学": "sci",
    "物理": "phy", "化学": "che", "生物": "bio", "地理": "geo",
    "历史": "his", "政治": "pol", "奥数": "oly",
}


class _DashScopeChannel:
    """Minimal OpenAI-compatible channel to DashScope (Qwen).

    Used as fallback for topics the primary provider repeatedly fails on
    (e.g. politics content refusals, persistent truncation).
    """

    model = "qwen-plus"

    def __init__(self, api_key: str):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def call(self, system: str, user: str, temperature: float = 0.3,
             max_tokens: int = 800) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


class TextbookGenerator:
    """Generate textbook content from curriculum topic outlines."""

    def __init__(self, generator: Generator | None = None, fallback="auto"):
        self._gen = generator or Generator()
        self._model = get_config()["llm_model"]
        # fallback="auto" (default): lazily build a DashScope channel from
        # DASHSCOPE_API_KEY the first time the primary channel exhausts its
        # retries. Pass fallback=None to disable (e.g. in tests).
        self._fallback_auto = fallback == "auto"
        self._fallback = None if self._fallback_auto else fallback

    def _get_fallback(self):
        if self._fallback is None and self._fallback_auto:
            key = get_config()["dashscope_api_key"]
            if key and len(key) > 20:  # skip placeholders like "sk-xxx"
                try:
                    self._fallback = _DashScopeChannel(key)
                except Exception as exc:
                    print(f"  fallback channel init failed: {exc}")
                    self._fallback_auto = False  # do not retry init
            else:
                self._fallback_auto = False  # no usable key configured
        return self._fallback

    def generate_topic(self, stage, subject, topic):
        return self._generate_with(self._gen, self._build_prompt(stage, subject, topic))

    @staticmethod
    def _build_prompt(stage, subject, topic) -> str:
        return f"""你是一位中国{stage}{subject}教师。请为“{topic}”这个知识点编写教材内容。

要求：
1. 知识点定义清晰准确，公式正确无误
2. 包含至少3个例题或示例
3. 标注1-2个学生常见的错误理解及纠正方法
4. 用{stage}学生能理解的语言
5. 正文400-700字，用“一、二、三”分小节
6. 严禁使用Markdown符号（不要用**加粗**、不要用-列表、不要用`代码块`）；数学公式用LaTeX格式，行内公式用 $...$ 包裹，独立成行的公式用 $$...$$ 包裹

直接输出教材内容，不要加前言结语。"""

    @staticmethod
    def _generate_with(channel, prompt: str) -> str:
        return channel.call(
            system="你是一位中国教育教师。", user=prompt, temperature=0.3, max_tokens=4000
        )

    @staticmethod
    def is_complete(text: str) -> bool:
        """Return True if content looks finished (not cut off by max_tokens)."""
        body = text.strip()
        if len(body) < _MIN_BODY_CHARS:
            return False
        return body.endswith(_END_PUNCT)

    def fact_check(self, stage, subject, topic, text: str) -> bool:
        """One LLM self-review pass for science content. Returns True if clean."""
        return self._fact_check_with(self._gen, stage, subject, topic, text)

    @staticmethod
    def _fact_check_with(channel, stage, subject, topic, text: str) -> bool:
        review = channel.call(
            system="你是严谨的学科审校员。只输出“通过”，或“有误：”加一句原因。",
            user=(
                f"检查以下{stage}{subject}“{topic}”教材内容是否有事实性错误"
                f"（定义、公式、定理、单位、例题答案）：\n\n{text}"
            ),
            temperature=0.0,
            max_tokens=100,
        )
        # Verdict must START with "有误": a substring check would
        # false-positive on reviewer outputs like "经检查无误".
        verdict = review.strip()
        passed = not verdict.startswith("有误")
        if not passed:
            print(f"  fact-check REJECTED {stage}{subject}/{topic}: {verdict[:80]}")
        return passed

    def _generate_gated(self, stage, subject, topic) -> tuple[str, bool, str]:
        """Generate with quality gates: completeness retry + science fact-check.

        API/network errors (e.g. transient proxy or TLS failures) are caught
        and retried with linear backoff so one dropped connection cannot kill
        a multi-hour batch run. When the primary channel exhausts its
        retries, a DashScope (Qwen) fallback channel gets one full retry
        round — this rescues topics the primary provider refuses or
        persistently truncates.

        Returns (text, fact_checked, model). Empty text means all failed.
        """
        need_check = subject in _FACT_CHECK_SUBJECTS
        channels: list = [self._gen]
        fallback = self._get_fallback()
        if fallback is not None:
            channels.append(fallback)
        for channel in channels:
            text = self._try_channel(channel, stage, subject, topic, need_check)
            if text:
                model = getattr(channel, "model", None) or getattr(
                    channel, "_model", self._model
                )
                return text, need_check, model
        return "", need_check, self._model

    def _try_channel(self, channel, stage, subject, topic, need_check) -> str:
        prompt = self._build_prompt(stage, subject, topic)
        for attempt in range(_MAX_RETRIES + 1):
            try:
                text = self._generate_with(channel, prompt)
            except Exception as exc:
                print(f"  API error on {stage}{subject}/{topic} (attempt {attempt+1}): {exc}")
                time.sleep(5 * (attempt + 1))
                continue
            if not text or not self.is_complete(text):
                continue
            if need_check:
                try:
                    if not self._fact_check_with(channel, stage, subject, topic, text):
                        continue
                except Exception as exc:
                    print(f"  fact-check API error on {topic} (attempt {attempt+1}): {exc}")
                    time.sleep(5 * (attempt + 1))
                    continue
            return text
        return ""

    def generate_from_outline(self, outline, output_dir):
        """Generate textbooks from nested outline structure.

        Existing files are re-validated: incomplete ones (e.g. truncated by a
        previous low-max_tokens run) are regenerated instead of skipped.

        Args:
            outline: Nested dict {stage: {subject: [topics]}}
            output_dir: Output directory path

        Returns:
            Number of files generated or regenerated
        """
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        manifest_path = output / "generation_manifest.json"
        manifest: dict = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                manifest = {}
        count = 0

        for stage, subjects in outline.items():
            stage_code = _STAGE_CODES.get(stage, "gen")
            for subject, topics in subjects.items():
                subj_code = _SUBJECT_CODES.get(subject, "gen")
                for i, topic in enumerate(topics):
                    fname = f"gen_{stage_code}_{subj_code}_{i+1:02d}.txt"
                    fpath = output / fname
                    if fpath.exists():
                        parts = fpath.read_text(encoding="utf-8").split("\n\n", 1)
                        if len(parts) == 2 and self.is_complete(parts[1]):
                            continue
                        print(f"  REGENERATE (incomplete): {fname}")
                    text, fact_checked, model = self._generate_gated(
                        stage, subject, topic
                    )
                    if text:
                        header = f"{stage}{subject} - {topic}\n\n"
                        fpath.write_text(header + text, encoding="utf-8")
                        manifest[fname] = {
                            "stage": stage,
                            "subject": subject,
                            "topic": topic,
                            "model": model,
                            "generated_at": datetime.now().isoformat(timespec="seconds"),
                            "fact_checked": fact_checked,
                        }
                        count += 1

        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return count


COMPREHENSIVE_OUTLINE = {
    "小学": {
        "数学": [
            "20以内数的认识与加减法","100以内数的认识与加减法","万以内数的认识","大数的认识",
            "多位数乘一位数","除数是两位数的除法","四则混合运算","运算定律与简便运算",
            "小数的意义和性质","小数加减法","小数乘除法","分数的意义和性质",
            "分数加减法","分数乘除法","百分数的认识与应用","负数的初步认识",
            "因数与倍数","质数与合数","最大公因数与最小公倍数","比和比例",
            "简易方程","常见的量与单位换算","年月日与24时计时法","认识图形（长方形和正方形）",
            "角的度量","三角形的认识与分类","平行四边形和梯形","圆的认识",
            "长方形和正方形的周长与面积","多边形的面积","圆的周长与面积","长方体和正方体",
            "圆柱与圆锥","体积与容积单位","观察物体","图形的运动（平移旋转轴对称）",
            "位置与方向","比例尺","分类与整理","条形统计图",
            "折线统计图","扇形统计图","平均数","可能性",
            "数学广角搭配问题","数学广角集合初步","数学广角优化问题","数学广角找规律"
        ],
        "语文": [
            "声母与韵母","整体认读音节","声调与轻声","查字典的方法",
            "常用汉字笔画笔顺","偏旁部首与间架结构","多音字辨析","形近字辨析",
            "同音字辨析","词语的理解与运用","近义词与反义词","成语的积累与运用",
            "句子的类型与变换","扩句与缩句","修辞手法（比喻拟人排比）",
            "病句修改","标点符号的使用","记叙文阅读","说明文阅读",
            "古诗词诵读与理解","文言文启蒙","看图写话","日记的写作",
            "记叙文写作","应用文写作（书信通知）","口语交际：听说训练","口语交际：演讲与辩论",
            "综合性学习","课外阅读指导"
        ],
        "英语": [
            "26个英文字母","字母的发音与书写","日常问候用语","自我介绍用语",
            "颜色词汇","数字1-100","家庭成员词汇","动物词汇",
            "食物与饮料词汇","学校用品词汇","身体部位词汇","天气与季节词汇",
            "be动词的用法","名词的单复数","一般现在时","现在进行时",
            "情态动词can的用法","there be句型","特殊疑问句","阅读理解：简单短文",
            "阅读理解：小故事","英语歌曲与童谣","英语书写规范","英语文化常识"
        ],
        "科学": [
            "植物的生长与繁殖","动物的特征与分类","人体的结构与功能","微生物与卫生",
            "声音的产生与传播","光的传播与反射","电与电路基础","磁现象与磁铁",
            "简单机械（杠杆滑轮）","物质的状态与变化","溶解与溶液","常见的酸碱物质",
            "地球的结构与运动","天气与气候观测","四季变化与成因","环境保护与可持续发展"
        ],
        "奥数": [
            "鸡兔同笼","和倍问题","差倍问题","和差问题","追及问题","相遇问题",
            "盈亏问题","植树问题","年龄问题","牛吃草问题","归一问题","还原问题",
            "工程问题","流水行船问题","火车过桥问题","浓度问题","经济利润问题","平均数问题",
            "周期问题","方阵问题","抽屉原理","容斥原理","加法原理与乘法原理","等差数列与高斯求和",
            "数字谜","幻方与数阵图","逻辑推理","统筹与最优化","定义新运算"
        ]
    },
    "初中": {
        "数学": [
            "有理数的混合运算","整式的加减","一元一次方程的应用","二元一次方程组",
            "不等式与不等式组","整式的乘法与因式分解","分式与分式方程","实数与二次根式",
            "平面直角坐标系","正比例函数与一次函数","反比例函数","二次函数的图像与性质",
            "全等三角形的判定","勾股定理及其应用","平行四边形与特殊四边形","圆的性质",
            "相似三角形","锐角三角函数","数据的集中趋势","数据的波动程度","概率初步"
        ],
        "物理": [
            "机械运动与参照物","速度与匀速直线运动","质量与密度","力的作用效果与重力弹力摩擦力",
            "二力平衡与牛顿第一定律","固体压强与液体压强","大气压强与流体压强","浮力与阿基米德原理",
            "浮沉条件与应用","杠杆与滑轮","功与功率","机械效率","动能与势能",
            "分子热运动与内能","比热容与热量计算","热机与热机效率","电荷与电路","电流与电压",
            "电阻与变阻器","欧姆定律及其应用","电功与电功率","焦耳定律与电热","家庭电路与安全用电",
            "磁现象与磁场","电生磁与电磁铁","电动机与发电机","电磁波与信息传递"
        ],
        "化学": [
            "物理变化与化学变化","空气的组成与性质","氧气的性质与制备","水的组成与净化",
            "碳的单质与二氧化碳","一氧化碳的性质","金属材料与合金","金属的化学性质",
            "金属资源的利用与保护","溶液的形成与溶解度","溶质的质量分数","常见的酸及其性质",
            "常见的碱及其性质","中和反应与pH","盐与复分解反应","化学肥料"
        ],
        "生物": [
            "生物的特征与环境","生态系统的组成","细胞的结构与功能","细胞分裂与分化",
            "光合作用","呼吸作用","人体的消化与吸收","人体的呼吸","血液循环",
            "尿的形成与排出","神经调节","激素调节","动物的运动","细菌与真菌",
            "病毒","传染病与免疫"
        ],
        "地理": [
            "地球与地球仪","地球的运动","地图的阅读","海陆分布","天气与气候",
            "气温与降水","世界气候类型","人口与人种","语言与宗教","亚洲",
            "东南亚","中东","欧洲西部","中国的疆域","中国的地形","中国的气候",
            "中国的河流","自然资源","农业与工业","交通"
        ],
        "历史": [
            "中国早期人类","夏商周","百家争鸣","秦统一中国","汉武帝","丝绸之路",
            "三国鼎立","隋唐繁荣","宋元经济","明朝统治","清朝前期","鸦片战争",
            "洋务运动","甲午战争","戊戌变法","辛亥革命","新文化运动","五四运动",
            "中共成立","红军长征","抗日战争","解放战争","新中国成立","改革开放"
        ],
        "政治": [
            "个人品德与修养","家庭美德与亲情","社会公德与规则","法律基础知识",
            "宪法与公民权利","公民的权利与义务","基本国情与国策","改革开放与成就",
            "中国特色社会主义","共同富裕与共享发展","民族团结与祖国统一","国际视野与全球观念"
        ]
    },
    "高中": {
        "数学": [
            "集合的概念与运算","充分条件与必要条件","基本不等式","二次函数与不等式",
            "函数的单调性与奇偶性","指数函数与对数函数","幂函数","任意角与弧度制",
            "三角函数定义与诱导公式","三角函数图像与性质","三角恒等变换","解三角形",
            "平面向量","复数","等差数列","等比数列","导数的概念与运算","导数与单调性",
            "导数与极值最值","空间几何体","点线面位置关系","空间向量","直线方程","圆的方程",
            "椭圆","双曲线","抛物线","排列与组合","二项式定理","随机事件与概率",
            "离散型随机变量","二项分布与正态分布","统计与回归分析"
        ],
        "物理": [
            "匀变速直线运动","自由落体","力的合成与分解","牛顿第二定律","超重与失重",
            "平抛运动","圆周运动","万有引力","动能定理","机械能守恒","动量守恒",
            "简谐运动","机械波","库仑定律","电场强度","电势与电势能","带电粒子在电场中",
            "闭合电路欧姆定律","安培力与洛伦兹力","电磁感应","交变电流","光的折射与全反射",
            "光的干涉与衍射","光电效应","原子结构"
        ],
        "化学": [
            "物质的量","离子反应","氧化还原反应","钠及其化合物","铝及其化合物",
            "铁及其化合物","氯及其化合物","硫及其化合物","氮及其化合物","原子结构与周期律",
            "化学键与分子结构","化学反应与能量","原电池","电解池","醇与酚","醛与酮",
            "羧酸与酯","糖类","油脂与蛋白质","合成高分子"
        ],
        "生物": [
            "细胞的分子组成","细胞的结构与功能","细胞代谢与酶","细胞呼吸","光合作用",
            "细胞的生命历程","孟德尔遗传实验","减数分裂","基因在染色体上","DNA的结构与复制",
            "基因的表达","基因突变","染色体变异","人类遗传病","杂交育种","基因工程",
            "现代生物进化理论","内环境与稳态","神经调节","体液调节","免疫调节","植物激素",
            "种群的特征","群落的结构","生态系统的结构","能量流动","物质循环","生态系统稳定性"
        ],
        "地理": [
            "地球的宇宙环境","地球的运动","大气的组成与分层","大气的受热过程","气压带与风带",
            "常见天气系统","水循环","地表形态的塑造","自然地理整体性与差异性","人口的数量变化",
            "城市化","农业区位因素","工业区位因素","交通运输布局","人地关系与可持续发展",
            "区域生态环境","区域自然资源","区域经济发展","地理信息技术"
        ],
        "历史": [
            "夏商周政治制度","秦中央集权","汉至元政治演变","明清君主专制","古代希腊罗马",
            "英国君主立宪制","美国联邦政府","资本主义制度扩展","两次鸦片战争","太平天国与洋务运动",
            "甲午战争与八国联军","辛亥革命","新民主主义革命","国共对峙","抗日战争","解放战争",
            "新中国民主政治","社会主义建设","改革开放","祖国统一大业","新中国外交","两极世界",
            "世界多极化","经济全球化"
        ],
        "政治": [
            "商品与货币","价格与价值规律","消费与消费观","企业与劳动者","投资与理财",
            "财政与税收","社会主义市场经济","经济全球化与对外开放","我国的政党制度","民族区域自治制度",
            "基层群众自治制度","依法治国与法治国家","文化与社会","文化对人的影响","文化的多样性与传播",
            "文化的继承与发展","中华文化与民族精神","哲学与时代精神","世界的物质性","意识的能动作用",
            "实践与认识","真理与价值","唯物辩证法","历史唯物主义"
        ]
    }
}
