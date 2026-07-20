"""Knowledge graph builder for high school education domain."""

from kag_pro.kg.graph import KnowledgeGraph


class EntityExtractor:
    """Build a predefined knowledge graph for high school subjects."""

    @staticmethod
    def build_default_kg() -> KnowledgeGraph:
        """Build a KG covering high school math, physics, and chemistry."""
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

        return kg
