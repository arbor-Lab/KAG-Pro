"""Knowledge graph builder for high school education domain."""

from kag_pro.kg.graph import KnowledgeGraph


class EntityExtractor:
    """Build a predefined knowledge graph for high school subjects."""

    @staticmethod
    def build_default_kg() -> KnowledgeGraph:
        """Build a KG covering high school math/physics/chemistry and elementary math."""
        kg = KnowledgeGraph()

        # === Math entities ===
        for eid, name, etype in [
            ("math_function", "函数", "concept"),
            ("math_derivative", "导数", "concept"),
            ("math_limit", "极限", "concept"),
            ("math_monotonicity", "单调性", "concept"),
            ("math_extreme", "极值与最值", "concept"),
            ("math_integral", "定积分", "concept"),
            ("math_probability", "概率", "concept"),
            ("math_permutation", "排列组合", "concept"),
            ("math_statistics", "统计", "concept"),
            ("math_quadratic", "二次函数", "concept"),
            ("math_chain_rule", "链式法则", "method"),
            ("math_derivative_zero_error", "导数零点≠极值点", "common_mistake"),
        ]:
            kg.add_entity(eid, name, etype)

        # Math relations
        kg.add_relation("math_function", "prerequisite", "math_derivative")
        kg.add_relation("math_limit", "prerequisite", "math_derivative")
        kg.add_relation("math_derivative", "contains", "math_monotonicity")
        kg.add_relation("math_derivative", "contains", "math_extreme")
        kg.add_relation("math_derivative", "contains", "math_chain_rule")
        kg.add_relation("math_derivative", "common_mistake", "math_derivative_zero_error")
        kg.add_relation("math_quadratic", "related_to", "math_extreme")
        kg.add_relation("math_function", "contains", "math_quadratic")
        kg.add_relation("math_derivative", "prerequisite", "math_integral")
        kg.add_relation("math_permutation", "prerequisite", "math_probability")

        # === Physics entities ===
        for eid, name, etype in [
            ("phys_electric_field", "电场", "concept"),
            ("phys_potential", "电势与电势差", "concept"),
            ("phys_capacitor", "电容器", "concept"),
            ("phys_ohm_law", "欧姆定律", "law"),
            ("phys_electric_power", "电功率", "concept"),
            ("phys_magnetic_field", "磁场", "concept"),
            ("phys_ampere_force", "安培力", "concept"),
            ("phys_lorentz_force", "洛伦兹力", "concept"),
            ("phys_left_hand_rule", "左手定则", "method"),
            ("phys_right_hand_rule", "右手定则", "method"),
            ("phys_hand_rule_confusion", "左右手定则混淆", "common_mistake"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("phys_electric_field", "contains", "phys_potential")
        kg.add_relation("phys_electric_field", "related_to", "phys_capacitor")
        kg.add_relation("phys_potential", "prerequisite", "phys_ohm_law")
        kg.add_relation("phys_ohm_law", "contains", "phys_electric_power")
        kg.add_relation("phys_magnetic_field", "contains", "phys_ampere_force")
        kg.add_relation("phys_magnetic_field", "contains", "phys_lorentz_force")
        kg.add_relation("phys_ampere_force", "related_to", "phys_left_hand_rule")
        kg.add_relation("phys_lorentz_force", "related_to", "phys_right_hand_rule")
        kg.add_relation("phys_left_hand_rule", "common_mistake", "phys_hand_rule_confusion")
        kg.add_relation("phys_right_hand_rule", "common_mistake", "phys_hand_rule_confusion")

        # === Chemistry entities ===
        for eid, name, etype in [
            ("chem_equilibrium", "化学平衡", "concept"),
            ("chem_eq_constant", "平衡常数", "concept"),
            ("chem_le_chatelier", "勒夏特列原理", "principle"),
            ("chem_ionization", "电离平衡", "concept"),
            ("chem_ph", "pH值", "concept"),
            ("chem_hydrolysis", "盐类水解", "concept"),
            ("chem_catalyst_error", "催化剂不改变平衡", "common_mistake"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("chem_equilibrium", "contains", "chem_eq_constant")
        kg.add_relation("chem_equilibrium", "contains", "chem_le_chatelier")
        kg.add_relation("chem_le_chatelier", "common_mistake", "chem_catalyst_error")
        kg.add_relation("chem_equilibrium", "related_to", "chem_ionization")
        kg.add_relation("chem_ionization", "contains", "chem_ph")
        kg.add_relation("chem_ionization", "contains", "chem_hydrolysis")


        # === Additional high school entities ===
        for eid, name, etype in [
            ("phys_newton_laws", "牛顿运动定律", "law"),
            ("phys_mechanics", "力学", "concept"),
            ("phys_energy", "能量与功", "concept"),
            ("phys_circular_motion", "圆周运动", "concept"),
            ("phys_em_induction", "电磁感应", "concept"),
            ("chem_reaction_rate", "化学反应速率", "concept"),
            ("chem_organic", "有机化学", "concept"),
            ("chem_electrochemistry", "电化学", "concept"),
            ("math_trigonometry", "三角函数", "concept"),
            ("math_analytic_geometry", "解析几何", "concept"),
            ("math_sequence", "数列", "concept"),
            ("math_probability_adv", "概率统计进阶", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("phys_mechanics", "contains", "phys_newton_laws")
        kg.add_relation("phys_mechanics", "contains", "phys_circular_motion")
        kg.add_relation("phys_mechanics", "contains", "phys_energy")
        kg.add_relation("phys_newton_laws", "related_to", "phys_ampere_force")
        kg.add_relation("phys_magnetic_field", "contains", "phys_em_induction")
        kg.add_relation("chem_reaction_rate", "related_to", "chem_equilibrium")
        kg.add_relation("chem_equilibrium", "related_to", "chem_electrochemistry")
        kg.add_relation("math_trigonometry", "prerequisite", "math_analytic_geometry")
        kg.add_relation("math_sequence", "related_to", "math_derivative")
        kg.add_relation("math_permutation", "prerequisite", "math_probability_adv")
        kg.add_relation("math_probability_adv", "contains", "math_statistics")

        # === Elementary math entities ===
        for eid, name, etype in [
            ("elem_arithmetic", "四则运算", "concept"),
            ("elem_fraction", "分数", "concept"),
            ("elem_decimal", "小数", "concept"),
            ("elem_simple_equation", "简易方程", "concept"),
            ("elem_chicken_rabbit", "鸡兔同笼", "concept"),
            ("elem_sum_multiple", "和倍问题", "concept"),
            ("elem_diff_multiple", "差倍问题", "concept"),
            ("elem_pursuit", "追及问题", "concept"),
            ("elem_meeting", "相遇问题", "concept"),
            ("elem_profit_loss", "盈亏问题", "concept"),
            ("elem_tree_planting", "植树问题", "concept"),
            ("elem_grazing", "牛吃草问题", "concept"),
            ("elem_work", "工程问题", "concept"),
            ("elem_concentration", "浓度问题", "concept"),
            ("elem_assumption_method", "假设法", "method"),
            ("elem_equation_method", "方程法", "method"),
            ("elem_drawing_method", "画图法", "method"),
            ("elem_line_diagram", "线段图法", "method"),
            ("elem_tree_planting_error", "植树问题忽略两端情况", "common_mistake"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("elem_arithmetic", "prerequisite", "elem_chicken_rabbit")
        kg.add_relation("elem_arithmetic", "prerequisite", "elem_sum_multiple")
        kg.add_relation("elem_arithmetic", "prerequisite", "elem_diff_multiple")
        kg.add_relation("elem_arithmetic", "prerequisite", "elem_profit_loss")
        kg.add_relation("elem_arithmetic", "prerequisite", "elem_tree_planting")
        kg.add_relation("elem_arithmetic", "prerequisite", "elem_pursuit")
        kg.add_relation("elem_decimal", "related_to", "elem_fraction")
        kg.add_relation("elem_fraction", "prerequisite", "elem_work")
        kg.add_relation("elem_fraction", "prerequisite", "elem_concentration")
        kg.add_relation("elem_simple_equation", "prerequisite", "elem_chicken_rabbit")
        kg.add_relation("elem_simple_equation", "prerequisite", "elem_grazing")
        kg.add_relation("elem_pursuit", "related_to", "elem_meeting")
        kg.add_relation("elem_chicken_rabbit", "contains", "elem_assumption_method")
        kg.add_relation("elem_chicken_rabbit", "contains", "elem_equation_method")
        kg.add_relation("elem_grazing", "contains", "elem_assumption_method")
        kg.add_relation("elem_sum_multiple", "contains", "elem_line_diagram")
        kg.add_relation("elem_diff_multiple", "contains", "elem_line_diagram")
        kg.add_relation("elem_profit_loss", "contains", "elem_drawing_method")
        kg.add_relation("elem_tree_planting", "common_mistake", "elem_tree_planting_error")

        # === Middle school math entities ===
        for eid, name, etype in [
            ("mid_rational_numbers", "有理数", "concept"),
            ("mid_algebraic_expressions", "整式", "concept"),
            ("mid_linear_equations", "一元一次方程", "concept"),
            ("mid_systems_equations", "二元一次方程组", "concept"),
            ("mid_inequalities", "不等式", "concept"),
            ("mid_quadratic_functions", "二次函数", "concept"),
            ("mid_congruent_triangles", "全等三角形", "concept"),
            ("mid_pythagorean_theorem", "勾股定理", "concept"),
            ("mid_parallelograms", "平行四边形", "concept"),
            ("mid_probability", "概率初步", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("mid_rational_numbers", "prerequisite", "mid_algebraic_expressions")
        kg.add_relation("mid_algebraic_expressions", "prerequisite", "mid_linear_equations")
        kg.add_relation("mid_linear_equations", "prerequisite", "mid_systems_equations")
        kg.add_relation("mid_algebraic_expressions", "prerequisite", "mid_quadratic_functions")
        kg.add_relation("mid_congruent_triangles", "prerequisite", "mid_parallelograms")
        kg.add_relation("mid_pythagorean_theorem", "related_to", "mid_congruent_triangles")

        # === Middle school physics entities ===
        for eid, name, etype in [
            ("mid_force", "力", "concept"),
            ("mid_pressure", "压强", "concept"),
            ("mid_buoyancy", "浮力", "concept"),
            ("mid_simple_machines", "简单机械", "concept"),
            ("mid_work_power", "功与功率", "concept"),
            ("mid_internal_energy", "内能", "concept"),
            ("mid_ohm_law", "欧姆定律", "law"),
            ("mid_electric_power", "电功率", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("mid_force", "prerequisite", "mid_pressure")
        kg.add_relation("mid_pressure", "prerequisite", "mid_buoyancy")
        kg.add_relation("mid_force", "prerequisite", "mid_simple_machines")
        kg.add_relation("mid_simple_machines", "prerequisite", "mid_work_power")
        kg.add_relation("mid_internal_energy", "related_to", "mid_work_power")
        kg.add_relation("mid_ohm_law", "contains", "mid_electric_power")

        # === Middle school chemistry entities ===
        for eid, name, etype in [
            ("mid_chemical_change", "化学变化", "concept"),
            ("mid_oxygen", "氧气", "concept"),
            ("mid_water", "水", "concept"),
            ("mid_carbon", "碳", "concept"),
            ("mid_metals", "金属", "concept"),
            ("mid_acids_bases_salts", "酸碱盐", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("mid_chemical_change", "prerequisite", "mid_oxygen")
        kg.add_relation("mid_chemical_change", "prerequisite", "mid_water")
        kg.add_relation("mid_carbon", "related_to", "mid_oxygen")
        kg.add_relation("mid_metals", "related_to", "mid_acids_bases_salts")

        # === Middle school biology entities ===
        for eid, name, etype in [
            ("mid_cells", "细胞", "concept"),
            ("mid_photosynthesis", "光合作用", "concept"),
            ("mid_respiration", "呼吸作用", "concept"),
            ("mid_digestion", "消化", "concept"),
            ("mid_circulation", "血液循环", "concept"),
            ("mid_nervous_regulation", "神经调节", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("mid_cells", "prerequisite", "mid_photosynthesis")
        kg.add_relation("mid_cells", "prerequisite", "mid_respiration")
        kg.add_relation("mid_digestion", "related_to", "mid_circulation")
        kg.add_relation("mid_nervous_regulation", "related_to", "mid_circulation")

        # === Middle school geography entities ===
        for eid, name, etype in [
            ("mid_earth", "地球", "concept"),
            ("mid_climate", "气候", "concept"),
            ("mid_china_topography", "中国地形", "concept"),
            ("mid_china_climate", "中国气候", "concept"),
            ("mid_china_agriculture", "中国农业", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("mid_earth", "prerequisite", "mid_climate")
        kg.add_relation("mid_china_topography", "related_to", "mid_china_climate")
        kg.add_relation("mid_china_climate", "prerequisite", "mid_china_agriculture")

        # === Middle school history entities ===
        for eid, name, etype in [
            ("mid_xia_shang_zhou", "夏商周", "concept"),
            ("mid_qin_han", "秦汉", "concept"),
            ("mid_sui_tang", "隋唐", "concept"),
            ("mid_song_yuan", "宋元", "concept"),
            ("mid_ming_qing", "明清", "concept"),
            ("mid_modern_history", "近代史", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("mid_xia_shang_zhou", "prerequisite", "mid_qin_han")
        kg.add_relation("mid_qin_han", "prerequisite", "mid_sui_tang")
        kg.add_relation("mid_sui_tang", "prerequisite", "mid_song_yuan")
        kg.add_relation("mid_song_yuan", "prerequisite", "mid_ming_qing")
        kg.add_relation("mid_ming_qing", "prerequisite", "mid_modern_history")

        # === Middle school politics entities ===
        for eid, name, etype in [
            ("mid_morality", "道德", "concept"),
            ("mid_rule_of_law", "法治", "concept"),
            ("mid_national_conditions", "国情", "concept"),
            ("mid_reform_opening", "改革开放", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("mid_morality", "related_to", "mid_rule_of_law")
        kg.add_relation("mid_national_conditions", "prerequisite", "mid_reform_opening")

        # === Elementary Chinese entities ===
        for eid, name, etype in [
            ("elem_pinyin", "拼音", "concept"),
            ("elem_literacy", "识字", "concept"),
            ("elem_reading", "阅读", "concept"),
            ("elem_writing", "写作", "concept"),
            ("elem_ancient_poetry", "古诗词", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("elem_pinyin", "prerequisite", "elem_literacy")
        kg.add_relation("elem_literacy", "prerequisite", "elem_reading")
        kg.add_relation("elem_reading", "prerequisite", "elem_writing")
        kg.add_relation("elem_ancient_poetry", "related_to", "elem_reading")

        # === Elementary English entities ===
        for eid, name, etype in [
            ("elem_alphabet", "字母", "concept"),
            ("elem_vocabulary", "单词", "concept"),
            ("elem_dialogue", "对话", "concept"),
            ("elem_english_reading", "阅读", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("elem_alphabet", "prerequisite", "elem_vocabulary")
        kg.add_relation("elem_vocabulary", "prerequisite", "elem_dialogue")
        kg.add_relation("elem_dialogue", "prerequisite", "elem_english_reading")

        # === Elementary science entities ===
        for eid, name, etype in [
            ("elem_biology", "生物", "concept"),
            ("elem_physics", "物理", "concept"),
            ("elem_chemistry", "化学", "concept"),
            ("elem_geography", "地理", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        # === High school politics entities ===
        for eid, name, etype in [
            ("high_economy", "经济生活", "concept"),
            ("high_politics", "政治生活", "concept"),
            ("high_culture", "文化生活", "concept"),
            ("high_philosophy", "生活与哲学", "concept"),
        ]:
            kg.add_entity(eid, name, etype)

        kg.add_relation("high_economy", "related_to", "high_politics")
        kg.add_relation("high_culture", "related_to", "high_philosophy")

        return kg
