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

        return kg
