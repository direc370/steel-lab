# -*- coding: utf-8 -*-
"""
steel-lab 领域数据层
数据来源：
  MAN0105601-CN 电弧炉模拟使用指南（MAN0003-CN.pdf）
  MAN0106601-CN 二次炼钢模拟使用指南 2.0（MAN0004-CN.pdf）
所有成分单位均为 wt%，价格单位 $/t，密度单位 t/m3。
"""

# ---------------------------------------------------------------- 元素
ELEMENTS = [
    "C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Cu", "N",
    "Nb", "Ti", "V", "Al", "B", "Ca", "O", "H", "As", "Pb", "Sn", "W", "Ce",
]
ELEMENT_CN = {
    "C": "碳", "Si": "硅", "Mn": "锰", "P": "磷", "S": "硫", "Cr": "铬",
    "Mo": "钼", "Ni": "镍", "Cu": "铜", "N": "氮", "Nb": "铌", "Ti": "钛",
    "V": "钒", "Al": "铝", "B": "硼", "Ca": "钙", "O": "氧", "H": "氢",
    "As": "砷", "Pb": "铅", "Sn": "锡", "W": "钨", "Ce": "铈", "Fe": "铁",
}

# ---------------------------------------------------------------- 废钢（EAF 手册 表2.3.1）
SCRAPS = [
    {
        "key": "no1_heavy", "name": "1号重废", "name_en": "No1 Heavy", "form": "CS",
        "density": 0.85, "price": 160,
        "comp": {"C": 0.5, "Si": 0.2, "Mn": 0.8, "P": 0.05, "S": 0.04,
                 "Cr": 0.15, "Ni": 0.15, "Mo": 0.06, "Cu": 0.25, "Sn": 0.015},
    },
    {
        "key": "no2_heavy", "name": "2号重废", "name_en": "No2 Heavy", "form": "CS",
        "density": 0.75, "price": 140,
        "comp": {"C": 0.35, "Si": 0.15, "Mn": 0.8, "P": 0.04, "S": 0.04,
                 "Cr": 0.25, "Mo": 0.06, "Ni": 0.18, "Cu": 0.5, "Sn": 0.025},
    },
    {
        "key": "internal_low_alloy", "name": "内部低合金废钢", "name_en": "Internal Low Alloyed",
        "form": "CS", "density": 3.00, "price": 240,
        "comp": {"C": 0.17, "Si": 0.04, "Mn": 0.31, "P": 0.013, "S": 0.001,
                 "Cr": 0.26, "Mo": 0.14, "Ni": 0.15, "Cu": 0.10, "Nb": 0.001,
                 "Ti": 0.015, "V": 0.005, "W": 0.009, "Ce": 0.003, "Sn": 0.001},
    },
    {
        "key": "plate_structural", "name": "板材与结构废钢", "name_en": "Plate & Structural",
        "form": "CS", "density": 2.0, "price": 290,
        "comp": {"C": 0.25, "Si": 0.25, "Mn": 6.5, "P": 0.03, "S": 0.035,
                 "Cr": 0.12, "Mo": 0.05, "Ni": 0.15, "Cu": 0.2, "Sn": 0.015},
    },
    {
        "key": "no1_bundle", "name": "1号捆包废钢", "name_en": "No1 Bundle", "form": "FS",
        "density": 1.2, "price": 180,
        "comp": {"C": 0.08, "Si": 0.11, "Mn": 0.7, "P": 0.01, "S": 0.01,
                 "Cr": 0.08, "Mo": 0.03, "Ni": 0.05, "Cu": 0.08, "Al": 0.02,
                 "Sn": 0.008, "Ti": 0.001},
    },
    {
        "key": "no2_bundle", "name": "2号捆包废钢", "name_en": "No2 Bundle", "form": "FS",
        "density": 1.1, "price": 170,
        "comp": {"C": 0.2, "Si": 0.18, "Mn": 0.12, "P": 0.03, "S": 0.03,
                 "Cr": 0.12, "Mo": 0.04, "Ni": 0.15, "Cu": 0.3, "Ti": 0.001},
    },
    {
        "key": "dri", "name": "直接还原铁 DRI", "name_en": "DRI", "form": "FS",
        "density": 1.65, "price": 220,
        "comp": {"C": 2.4, "P": 0.1, "S": 0.01, "Nb": 0.03, "Cu": 0.005,
                 "Ti": 0.02, "V": 0.02},
        # 脉石 SiO2：按 实炉校准 终渣（碱度 1.698 / MgO 8.186 / FeO 37.117）反算 4.8%
        "sio2": 4.8,
    },
    {
        "key": "shredded", "name": "碎废钢", "name_en": "Shredded", "form": "VFS",
        "density": 1.5, "price": 200,
        "comp": {"C": 0.3, "Si": 0.2, "Mn": 0.5, "P": 0.03, "S": 0.03,
                 "Cr": 0.15, "Mo": 0.05, "Ni": 0.18, "Cu": 0.2, "Sn": 0.015, "Al": 0.02},
    },
    {
        "key": "turnings", "name": "车屑", "name_en": "Turnings", "form": "VFS",
        "density": 1.0, "price": 110,
        "comp": {"C": 0.5, "Si": 0.6, "Mn": 0.6, "P": 0.035, "S": 0.8,
                 "Cr": 0.25, "Mo": 0.1, "Ni": 0.25, "Cu": 0.35, "Sn": 0.02, "Pb": 0.157},
    },
    {
        "key": "eaf_dust", "name": "电炉除尘灰", "name_en": "EAF Dust", "form": "PW",
        "density": 0.9, "price": -120,
        # 手册表 2.3.1 的标称成分（仅供追溯，不直接参与计算）：
        #   Si 0.91 / Mn 4.44 / Cr 20.03 / Ni 11.2
        # 但 2026-11-17 模拟器「步骤1」实测反推：粉末料只有约 20.6% 进入熔池，
        # 剩下约 80% 随烟气带走（既不贡献成分，也不计入成分基准的质量）。
        # 依据（84 t 炉次：29 一号重废 + 19 二号重废 + 30 一号捆包 + 2 DRI + 2 车屑 + 2 除尘灰）：
        #   若炉尘按标称全算，Ni 应为 0.383%、Cr 0.620%，而模拟器显示 0.174% / 0.245%；
        #   其余 9 个元素（C/Si/Mn/P/S/Mo/Cu）按手册纯加权完全吻合。
        #   取有效系数 0.206 后：Ni 0.1745、Cr 0.2455、C 0.3558、Mn 0.7567，与模拟器逐项吻合。
        "comp_scale": 0.206,
        "comp": {"Si": 0.91, "Mn": 4.44, "P": 0.019, "S": 0.001, "Cr": 20.03,
                 "Ni": 11.2, "Ca": 0.14, "Ti": 0.003},
    },
]
SCRAP_BY_KEY = {s["key"]: s for s in SCRAPS}

# ---------------------------------------------------------------- 钢种
# EAF 手册 表2.2.1：目标成分为“进入二次处理前”的要求
EAF_GRADES = {
    "structural": {
        "name": "结构钢 / 通用建筑钢", "short": "结构钢", "standard": "EAF 表2.2.1",
        "specs": {
            "C": [0.100, 0.120], "Si": [0.100, 0.300], "Mn": [1.000, 1.500],
            "P": [None, 0.020], "S": [None, 0.030], "Cr": [None, 0.100],
            "Mo": [None, 0.040], "Ni": [None, 0.150], "Cu": [None, 0.150],
            "N": [None, 0.005], "Nb": [None, 0.050], "Ti": [None, 0.010],
        },
        "note": "要求最低，主要工作是保证合金添加量正确。",
    },
    "tinb_ulc": {
        "name": "TiNb 超低碳钢", "short": "TiNb ULC", "standard": "EAF 表2.2.1",
        "specs": {
            "C": [None, 0.050], "Si": [None, 0.100], "Mn": [0.650, 0.850],
            "P": [None, 0.060], "S": [None, 0.020], "Cr": [None, 0.050],
            "Mo": [None, 0.010], "Ni": [None, 0.080], "Cu": [None, 0.080],
            "N": [None, 0.004], "Nb": [None, 0.030], "Ti": [None, 0.035],
        },
        "note": "汽车车身用钢。出钢后仍需 RH 脱碳至 <0.0035%C，废钢选择必须优先低碳。",
    },
    "pipeline": {
        "name": "管线钢", "short": "管线钢", "standard": "EAF 表2.2.1",
        "specs": {
            "C": [0.040, 0.080], "Si": [0.100, 0.300], "Mn": [0.900, 1.100],
            "P": [None, 0.007], "S": [None, 0.010], "Cr": [None, 0.060],
            "Mo": [None, 0.010], "Ni": [None, 0.050], "Cu": [None, 0.060],
            "N": [None, 0.005], "Nb": [None, 0.018], "Ti": [None, 0.010],
        },
        "note": "最苛刻钢种，S/P/H/O/N 与夹杂物要求极低。",
    },
    "sc21_engineering": {
        "name": "工程用钢（2026 赛题）", "short": "工程钢 2026", "standard": "赛题目标成分",
        "specs": {
            "C": [0.50, 0.56], "Si": [0.24, 0.32], "Mn": [0.85, 1.20],
            "P": [0.0, 0.035], "S": [0.0, 0.035], "Cr": [1.50, 1.60],
            "Mo": [0.0, 0.024], "Ni": [0.0, 0.10], "Nb": [0.0, 0.02],
            "Cu": [0.0, 0.15], "Ti": [0.0, 0.015], "Al": [0.0, 0.01],
            "V": [0.0, 0.015],
        },
        "note": "按你提供的 2026 赛题目标表建立；高铬、中高碳，Cr 需靠铬铁补加。",
        "process": {"temp": [1630, 1660], "time_max_min": 80, "weight": [80, 110],
                     "basicity": [1.5, 2.5], "mgo": [8, 12], "feo": [10, 50]},
    },
    "engineering": {
        "name": "冷镦钢 20MnB4（2026 赛题 · 学生级）", "short": "20MnB4",
        "standard": "第21届模拟炼钢挑战赛案例研究 v1.0 · 学生级",
        "specs": {
            "C": [0.420, 0.450], "Si": [0.100, 0.300], "Mn": [0.600, 0.800],
            "P": [0.0, 0.100], "S": [0.0, 0.050], "Cr": [0.200, 0.300],
            # Ni 官方上限 0.085；规划按 0.080 卡（留 0.005 余量）。
            # 依据：模拟器步骤1 面板 Ni 与废钢纯加权完全一致（实测 0.1740 vs 0.174），
            # 且 Ni 在熔化、吹氧、二次精炼全过程都不损失，进炉多少出钢就是多少，
            # 没有任何后续手段能降下来，所以只能靠配料卡死。
            "Mo": [0.0, 0.050], "Ni": [0.0, 0.080], "Nb": [0.0, 0.020],
            "Cu": [0.0, 0.250], "Ti": [0.0, 0.050], "Al": [0.0, 0.050],
            "V": [0.0, 0.015],
        },
        # 工厂情况（学生级）：1 号打包块压块机损坏，**每炉最多 30 t**
        "material_limits": {"no1_bundle": {"enabled": True, "min": 0, "max": 30}},
        # 入炉碳上限：Ni≤0.080 逼着必须掺约 22 t DRI（DRI 含碳 2.4%），
        # 入炉碳的结构性下限约 0.74（DRI 独占其中约八成），压不下去。
        # 不设上限时 LP 会为了省钱堆到 0.86；碳不是硬约束（可吹氧脱除），
        # 所以这里只是防止算法挑最便宜的碳、把吹氧时间拖长。
        "charge_c_max": 0.76,
        "note": ("1.5525 / 20MnB4 低碳锰硼冷镦钢。EAF 出钢 C 0.42–0.45、Cr 仅 0.20–0.30%，"
                 "脱碳与 Cr/Mn/Si/B 合金化全部在二次精炼完成；Mo/Ni/Cu 只能靠废钢控制，不可补加。"
                 "1 号打包块每炉限 30 t。官方 S 上限 0.1，但二次精炼要 ≤0.025，"
                 "这里把 EAF 目标收到的 0.04（压硫只多花约 $0.5/t，省下的脱硫时间和渣料远不止）。"),
        "process": {"temp": [1630, 1660], "time_max_min": 80, "co2_max_kg": 17000,
                     "basicity": [1.5, 2.5], "mgo": [8, 12], "feo": [10, 50],
                     "inclusion": "低"},
    },
}

# 二次炼钢手册 表6-1：最终目标成分（单点目标值）
SM_GRADES = {
    "structural": {
        "name": "通用建筑钢", "short": "通用钢", "standard": "SM 表6-1",
        "specs": {
            "C": [0.140, 0.150], "Si": [0.190, 0.210], "Mn": [1.350, 1.450],
            "P": [None, 0.025], "S": [None, 0.020], "Cr": [None, 0.100],
            "Al": [0.030, 0.040], "B": [None, 0.0005], "Ni": [None, 0.150],
            "Nb": [0.045, 0.055], "Ti": [None, 0.010], "V": [None, 0.010],
            "Mo": [None, 0.040], "N": [None, 0.005],
            "H": [None, 0.0005], "O": [None, 0.0010],
        },
        "note": "模拟中 C 0.1450 / Si 0.2000 / Mn 1.4000 为点名目标值。",
    },
    "tinb_ulc": {
        "name": "TiNb 汽车车身超低碳钢", "short": "TiNb ULC", "standard": "SM 表6-1",
        "specs": {
            "C": [0.0028, 0.0032], "Si": [0.200, 0.220], "Mn": [0.740, 0.760],
            "P": [None, 0.065], "S": [None, 0.012], "Cr": [None, 0.050],
            "Al": [0.040, 0.050], "B": [0.0025, 0.0035], "Ni": [None, 0.080],
            "Nb": [0.015, 0.025], "Ti": [0.025, 0.035], "Mo": [None, 0.010],
            "N": [None, 0.004], "H": [None, 0.0005], "O": [None, 0.0005],
        },
        "note": "碳 <0.0035%，须经 RH/罐式脱气深脱碳。",
    },
    "pipeline": {
        "name": "管线钢", "short": "管线钢", "standard": "SM 表6-1",
        "specs": {
            "C": [0.065, 0.075], "Si": [0.170, 0.190], "Mn": [1.040, 1.060],
            "P": [None, 0.012], "S": [None, 0.003], "Cr": [None, 0.060],
            "Al": [0.025, 0.035], "B": [None, 0.005], "Ni": [None, 0.050],
            "Nb": [0.010, 0.020], "Ti": [None, 0.010], "V": [None, 0.010],
            "Mo": [None, 0.010], "Ca": [None, 0.005], "N": [None, 0.0045],
            "H": [None, 0.0002], "O": [None, 0.0007],
        },
        "note": "杂质与夹杂物要求最严，需铝脱氧 + 钙处理 + 真空脱气。",
    },
    "sc21_refining": {
        "name": "工程钢（二次精炼目标）", "short": "工程钢 SM", "standard": "SM 目标成分",
        "specs": {
            "C": [0.35, 0.40], "Si": [0.24, 0.32], "Mn": [1.30, 1.60],
            "P": [0.0, 0.035], "S": [0.0, 0.035], "Cr": [1.80, 2.10],
            "Mo": [0.15, 0.25], "Ni": [0.0, 0.10], "B": [0.0, 0.005],
            "Al": [0.0, 0.004], "N": [0.0, 0.009], "H": [0.0, 0.0003],
            "O": [0.0, 0.002],
            # 二次精炼 17 元素：Nb/Ti/V/Cu 为与 EAF 共用的残余元素上限
            "Nb": [0.0, 0.020], "Ti": [0.0, 0.015], "V": [0.0, 0.015],
            "Cu": [0.0, 0.150],
        },
        "note": "按 #1552955 二次精炼目标表建立，共 17 元素；Mo 建议只做到 0.16 控制成本。",
    },
    "sc21_engineering": {
        "name": "工程用钢（2026 赛题）", "short": "工程钢 2026", "standard": "赛题目标成分",
        "specs": {
            "C": [0.50, 0.56], "Si": [0.24, 0.32], "Mn": [0.85, 1.20],
            "P": [0.0, 0.035], "S": [0.0, 0.035], "Cr": [1.50, 1.60],
            "Mo": [0.0, 0.024], "Ni": [0.0, 0.10], "Nb": [0.0, 0.02],
            "Cu": [0.0, 0.15], "Ti": [0.0, 0.015], "Al": [0.0, 0.01],
            "V": [0.0, 0.015],
        },
        "note": "与 EAF 赛题目标一致，用于合金补加页。",
    },
    "engineering": {
        "name": "冷镦钢 20MnB4（二次精炼 · 学生级）", "short": "20MnB4 精炼",
        "standard": "第21届模拟炼钢挑战赛案例研究 v1.0 · 学生级",
        "specs": {
            "C": [0.18, 0.23], "Si": [0.20, 0.30], "Mn": [0.90, 1.20],
            "P": [0.0, 0.025], "S": [0.0, 0.025], "Cr": [0.35, 0.45],
            "Mo": [0.0, 0.050], "Ni": [0.0, 0.10], "Cu": [0.0, 0.25],
            "Nb": [0.0, None], "Ti": [0.0, 0.050], "Al": [0.0, 0.050],
            "B": [0.0008, 0.005],
            "N": [None, 0.009], "H": [None, 0.00025], "O": [None, 0.002],
        },
        "note": ("关键：C 要从 EAF 的 0.42–0.45 脱到 0.18–0.23（CAS-OB 大脱碳）；"
                 "Mn/Si/Cr 上调，B 必须加（0.0008–0.005%）且加 Ti 固氮；"
                 "Mo/Ni/Cu 只是上限，绝对不能补加，只能靠废钢控制。V 无约束。"),
    },
}

# EAF 目标钢种 → 二次精炼目标钢种（两段是同一炉钢的前后工序，不能固定用 sc21_refining）
SM_GRADE_BY_EAF = {
    "structural": "structural",
    "tinb_ulc": "tinb_ulc",
    "pipeline": "pipeline",
    "sc21_engineering": "sc21_refining",
    "engineering": "engineering",
}

# 各 EAF 钢种的停氧碳默认值（%）。低 C 钢种不能套用 0.37% 的工程钢停氧点。
DEFAULT_PRE_C = {
    "structural": 0.10,
    "tinb_ulc": 0.03,
    "pipeline": 0.05,
    "sc21_engineering": 0.37,
    "engineering": 0.37,
}


def sm_grade_for(eaf_grade, fallback="sc21_refining"):
    """返回 EAF 钢种对应的二次精炼目标钢种 key。"""
    key = SM_GRADE_BY_EAF.get(eaf_grade)
    if key in SM_GRADES:
        return key
    if eaf_grade in SM_GRADES:
        return eaf_grade
    return fallback


def default_pre_c(grade_key, fallback=0.37):
    """返回 EAF 钢种的默认停氧目标 C（%）。"""
    return DEFAULT_PRE_C.get(grade_key, fallback)


# ---------------------------------------------------------------- 添加剂（EAF 手册 表3.7.1）
EAF_ADDITIVES = [
    {"key": "al", "name": "铝块", "comp": {"Al": 99.15, "Fe": 0.82, "Cu": 0.03},
     "density": 2.4, "price": 1400, "form": "鹅卵石"},
    {"key": "c", "name": "增碳剂", "comp": {"C": 99.9, "S": 0.011},
     "density": 1.0, "price": 280, "form": "粉"},
    {"key": "cr_ore", "name": "高碳铬铁", "comp": {"C": 7.82, "Si": 0.23, "P": 0.021, "S": 0.051, "Cr": 70.11, "Ti": 0.0092},
     "density": 3.5, "price": 590, "form": "鹅卵石"},
    {"key": "cr_ore_ls", "name": "高碳铬铁（低硫）", "comp": {"C": 8.12, "Si": 0.34, "P": 0.017, "S": 0.024, "Cr": 69.92},
     "density": 3.5, "price": 660, "form": "鹅卵石"},
    {"key": "femn_hc", "name": "高碳锰铁", "comp": {"Mn": 76.5, "C": 6.7, "Si": 1.0, "S": 0.03, "P": 0.3},
     "density": 4.0, "price": 350, "form": "鹅卵石"},
    {"key": "femn_lc", "name": "低碳锰铁", "comp": {"Mn": 81.5, "C": 0.85, "Si": 0.5, "S": 0.1, "P": 0.25},
     "density": 4.0, "price": 600, "form": "鹅卵石"},
    {"key": "femo", "name": "钼铁合金", "comp": {"C": 0.044, "Si": 0.14, "P": 0.044, "S": 0.092, "Mo": 62.02},
     "density": 6.0, "price": 1680, "form": "鹅卵石"},
    {"key": "fesi75", "name": "硅铁 75%", "comp": {"C": 0.08, "Si": 60.3, "P": 0.014, "S": 0.002, "Al": 1.23, "Ti": 0.05},
     "density": 2.5, "price": 770, "form": "鹅卵石"},
    {"key": "fesi75hp", "name": "硅铁 75% 高纯净度", "comp": {"C": 0.008, "Si": 75.6, "P": 0.003, "Al": 0.024, "Ti": 0.014},
     "density": 2.5, "price": 840, "form": "鹅卵石"},
    {"key": "fev", "name": "钒铁合金", "comp": {"C": 0.25, "Si": 0.72, "P": 0.031, "S": 0.081, "Al": 1.23, "V": 78.82},
     "density": 3.5, "price": 8400, "form": "鹅卵石"},
    {"key": "sic", "name": "硅碳合金", "comp": {"C": 30, "Si": 70},
     "density": 1.5, "price": 610, "form": "鹅卵石"},
    {"key": "sicr", "name": "硅铬合金", "comp": {"C": 1.82, "Si": 25.33, "P": 0.014, "S": 0.015, "Cr": 38.23},
     "density": 3.5, "price": 940, "form": "鹅卵石"},
    # 造渣剂单独归类
    {"key": "dolomite", "name": "白云石", "comp": {"MgO": 38.5, "SiO2": 2.0, "P": 0.005, "S": 0.15, "CaO": 59.345},
     "density": 1.0, "price": 120, "form": "粉", "flux": True},
    {"key": "fluorspar", "name": "萤石", "comp": {"CaO": 20.0, "MgO": 20.0, "SiO2": 20.0, "P": 0.001, "S": 0.06, "CaF2": 39.939},
     "density": 1.0, "price": 180, "form": "粉", "flux": True},
    {"key": "iron_oxide", "name": "氧化铁", "comp": {"Al2O3": 0.3, "CaO": 0.5, "MgO": 0.1, "P": 0.001, "FeO": 99.099},
     "density": 1.8, "price": 140, "form": "粉", "flux": True},
    {"key": "lime", "name": "石灰", "comp": {"Al2O3": 1.2, "MgO": 1.8, "SiO2": 2.1, "P": 0.01, "S": 0.01, "CaO": 94.88},
     "density": 1.0, "price": 120, "form": "粉", "flux": True},
]

# ---------------------------------------------------------------- 添加剂（二次炼钢手册 表7-2）
SM_ADDITIVES = [
    {"key": "recarb", "name": "增碳剂", "comp": {"C": 98}, "density": 1.0, "price": 280},
    {"key": "femn_hc_sm", "name": "高碳锰铁", "comp": {"Mn": 76.5, "C": 6.7, "Si": 1.0, "S": 0.03, "P": 0.3},
     "density": 4.0, "price": 490},
    {"key": "femn_lc_sm", "name": "低碳锰铁", "comp": {"Mn": 81.5, "C": 0.85, "Si": 0.5, "S": 0.1, "P": 0.25},
     "density": 4.0, "price": 840},
    {"key": "femn_hp", "name": "铁锰合金，高纯净度", "comp": {"Mn": 49.0}, "density": 4.0, "price": 1820},
    {"key": "simn", "name": "硅锰", "comp": {"Mn": 60, "Si": 30, "C": 0.5, "P": 0.08, "S": 0.08},
     "density": 3.5, "price": 560},
    {"key": "fesi75_sm", "name": "硅铁 75%", "comp": {"Si": 75, "Al": 1.5, "C": 0.15, "Mn": 0.5, "Ca": 0.2},
     "density": 2.5, "price": 770},
    {"key": "fesi75hp_sm", "name": "硅铁 75% 高纯净度", "comp": {"Si": 75, "Al": 0.06, "Mn": 0.2, "C": 0.02},
     "density": 2.5, "price": 840},
    {"key": "fesi45", "name": "硅铁 45", "comp": {"Si": 45, "Al": 2, "C": 0.2, "Mn": 1, "Cr": 0.5},
     "density": 2.5, "price": 630},
    {"key": "fecr", "name": "高碳铬铁", "comp": {"Cr": 66.5, "C": 6.4}, "density": 3.5, "price": 1260},
    {"key": "al_wire", "name": "铝线", "comp": {"Al": 98}, "density": 2.7, "price": 2100},
    {"key": "al_pebble", "name": "铝粒", "comp": {"Al": 98}, "density": 2.4, "price": 1400},
    {"key": "feb", "name": "硼铁合金", "comp": {"B": 20, "Si": 3, "P": 0.2}, "density": 6.0, "price": 3780},
    {"key": "femo_sm", "name": "钼铁合金", "comp": {"Mo": 70}, "density": 6.0, "price": 16800},
    {"key": "fenb", "name": "铌铁合金", "comp": {"Nb": 63, "Al": 2, "Si": 2, "Ti": 2, "C": 0.2, "S": 0.2, "P": 0.2},
     "density": 6.0, "price": 9800},
    {"key": "fev_sm", "name": "钒铁合金", "comp": {"V": 50}, "density": 3.5, "price": 8400},
    {"key": "fep", "name": "磷铁", "comp": {"P": 26, "Si": 1.5}, "density": 6.0, "price": 630},
    {"key": "ni", "name": "镍", "comp": {"Ni": 99}, "density": 8.9, "price": 7000},
    {"key": "ti", "name": "钛", "comp": {"Ti": 99}, "density": 4.5, "price": 2800},
    {"key": "sica_powder", "name": "硅钙粉", "comp": {"Ca": 50, "Si": 50}, "density": 2.5, "price": 1218},
    {"key": "sica_wire", "name": "硅钙线", "comp": {"Ca": 50, "Si": 50}, "density": 2.5, "price": 1540},
    {"key": "ca_ball", "name": "钙丸", "comp": {"Ca": 100}, "density": 1.5, "price": 5600},
]

EAF_ADDITIVE_BY_KEY = {a["key"]: a for a in EAF_ADDITIVES}
SM_ADDITIVE_BY_KEY = {a["key"]: a for a in SM_ADDITIVES}

# ---------------------------------------------------------------- 回收率（SM 手册 表7-3）
RECOVERY = {
    "ladle": {
        "label": "LF / RH / CAS-OB（保护气氛）",
        "C": 95, "Mn": 95, "Si": 98, "S": 80, "P": 98, "Cr": 99, "Al": 90,
        "B": 100, "Ni": 100, "Nb": 100, "Ti": 90, "V": 100, "Mo": 100,
        "As": 100, "Ca": 15, "O": 100, "N": 40, "H": 100, "Fe": 100,
    },
    "eaf_cal": {
        # Si：按实炉反算。目标 0.28%、加 340 kg 高纯硅铁（75.6% Si）实际到 0.33%，
        # 对应 Si 回收率约 95%（不是 82%）；82% 会把 SiFe 多算约 60–70 kg。
        "label": "EAF 模拟器实测（Cr/Mn≈98%，Si≈95%）",
        "C": 98, "Mn": 98, "Si": 95, "S": 80, "P": 80, "Cr": 98, "Al": 70,
        "B": 90, "Ni": 98, "Nb": 95, "Ti": 90, "V": 95, "Mo": 98,
        "As": 70, "Ca": 15, "O": 80, "N": 50, "H": 90, "Fe": 95,
    },
    "eaf_tap": {
        "label": "EAF 出钢（按实炉校准，约 90%）",
        "C": 90, "Mn": 90, "Si": 88, "S": 70, "P": 80, "Cr": 95, "Al": 80,
        "B": 90, "Ni": 95, "Nb": 90, "Ti": 80, "V": 90, "Mo": 95,
        "As": 90, "Ca": 20, "O": 80, "N": 40, "H": 80, "Fe": 90,
    },
}

# 二次炼钢目标钢种 与 EAF 钢种使用同一 grade key，便于联动。

# ---------------------------------------------------------------- 手册原文位置
MANUALS = {
    "eaf": {
        "title": "电弧炉模拟使用指南",
        "code": "MAN0105601-CN",
        "file": "MAN0003-CN.pdf",
        "pages": 52,
    },
    "sm": {
        "title": "二次炼钢模拟使用指南 2.0",
        "code": "MAN0106601-CN",
        "file": "MAN0004-CN.pdf",
        "pages": 68,
    },
}
