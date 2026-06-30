"""
第二、三、四阶段：数据存储 → 数据清洗 → 特征分析
招聘数据转换与深度统计分析建模引擎。
完成数据清洗、薪酬正则标准化、分层编码与 Pearson 相关性矩阵计算。
输入：raw_recruitment_data.csv
输出：cleaned_recruitment_data.csv + 控制台统计报告
"""

import pandas as pd
import numpy as np
import re


class RecruitmentAnalysisEngine:
    """
    招聘数据转换与深度统计分析建模引擎。
    完成数据清洗、薪酬正则标准化、分层编码与 Pearson 相关性矩阵计算。
    """

    def __init__(self, file_path="./output/raw_recruitment_data.csv"):
        self.file_path = file_path
        self.df = None

    # ------------------------------------------------------------------
    # 薪酬正则解析辅助函数
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_salary(salary_str):
        """
        将原始文本薪酬解析并统一换算为 k/月（千元/月）的浮点数。
        支持多种格式：
          - 模式A："18k-30k" 或 "08-12K/月"（已为千元单位）
          - 模式B："2.5万-4.5万" 或 "2-4万" 或 "1-2万/月"（万元/月，需 ×10 换算）
          - 模式B2："40-80万/年"（万元/年，需 ×10/12 换算）
          - 模式B3："1-2万·15薪"（万元/月 × 薪资月数 / 12）
          - 模式C："150-200元/天"（日薪，需 ×21.75 / 1000 换算为 k/月）
          - 模式D："8000-12000元/月"（元/月，需 /1000 换算为 k/月）
          - 模式E："6-7千" 或 "8千-1.2万"（千/万混合格式）
        """
        salary_str = str(salary_str).lower().strip()

        # 过滤无效值
        if not salary_str or salary_str in ("暂无数据", "nan", "none", ""):
            return np.nan

        # 去除尾部多余描述（如 "·15薪"、"·13薪" 等，先提取月数）
        months_per_year = 12.0
        bonus_match = re.search(r"·(\d+)薪", salary_str)
        if bonus_match:
            months_per_year = float(bonus_match.group(1))
            salary_str = re.sub(r"·\d+薪", "", salary_str)

        # 模式D：匹配如 "8000-12000元/月" 或 "6000-10000"
        match_yuan_month = re.match(
            r"(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*元/月", salary_str
        )
        if match_yuan_month:
            low, high = float(match_yuan_month.group(1)), float(match_yuan_month.group(2))
            return (low + high) / 2.0 / 1000.0  # 元 → 千元

        # 模式C：匹配如 "150-200元/天" 或 "100-150/天"
        match_day = re.match(
            r"(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*元?/?天", salary_str
        )
        if match_day:
            low, high = float(match_day.group(1)), float(match_day.group(2))
            return (low + high) / 2.0 * 21.75 / 1000.0  # 日薪 → 月薪 → 千元

        # 模式B2：匹配如 "40-80万/年" 或 "20-40万/年"
        match_wan_year = re.match(
            r"([\d\.]+)\s*[-–—]\s*([\d\.]+)\s*万/年", salary_str
        )
        if match_wan_year:
            low, high = float(match_wan_year.group(1)), float(match_wan_year.group(2))
            return ((low + high) / 2.0) * 10.0 / 12.0  # 万元/年 → 千元/月

        # 模式E：匹配如 "8千-1.2万" 或 "6.5千-1万"（千/万混合格式）
        # 先统一转换为千（k）单位
        match_qian_wan = re.match(
            r"([\d\.]+)\s*千\s*[-–—]\s*([\d\.]+)\s*万", salary_str
        )
        if match_qian_wan:
            low_k = float(match_qian_wan.group(1))  # 已经是千单位
            high_k = float(match_qian_wan.group(2)) * 10.0  # 万 → 千
            base = (low_k + high_k) / 2.0
            if months_per_year > 12:
                base = base * months_per_year / 12.0
            return base

        # 模式E2：匹配如 "1.5万-2万" 或 "1.2-1.5万"（万-万格式）
        match_wan_wan = re.match(
            r"([\d\.]+)\s*万\s*[-–—]\s*([\d\.]+)\s*万", salary_str
        )
        if match_wan_wan:
            low, high = float(match_wan_wan.group(1)), float(match_wan_wan.group(2))
            base = ((low + high) / 2.0) * 10.0  # 万元折算为千元
            if months_per_year > 12:
                base = base * months_per_year / 12.0
            return base

        # 模式B：匹配如 "1.5-2.5万" 或 "2-4万" 或 "1-2万/月"
        match_wan = re.match(
            r"([\d\.]+)\s*[-–—]\s*([\d\.]+)\s*万", salary_str
        )
        if match_wan:
            low, high = float(match_wan.group(1)), float(match_wan.group(2))
            base = ((low + high) / 2.0) * 10.0  # 万元折算为千元
            if months_per_year > 12:
                base = base * months_per_year / 12.0
            return base

        # 模式E3：匹配如 "6-7千" 或 "8-10千"（千-千格式）
        match_qian = re.match(
            r"([\d\.]+)\s*[-–—]\s*([\d\.]+)\s*千", salary_str
        )
        if match_qian:
            low, high = float(match_qian.group(1)), float(match_qian.group(2))
            base = (low + high) / 2.0  # 已经是千单位
            if months_per_year > 12:
                base = base * months_per_year / 12.0
            return base

        # 模式A：匹配如 "18k-30k" 或 "08-12K/月" 或 "8K-12K"
        match_k = re.match(
            r"(\d+(?:\.\d+)?)\s*k?\s*[-–—]\s*(\d+(?:\.\d+)?)\s*k", salary_str
        )
        if match_k:
            low, high = float(match_k.group(1)), float(match_k.group(2))
            return (low + high) / 2.0

        # 模式A2：匹配如 "08-12K/月"（数字-数字K/月）
        match_k2 = re.match(
            r"(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*k/月", salary_str
        )
        if match_k2:
            low, high = float(match_k2.group(1)), float(match_k2.group(2))
            return (low + high) / 2.0

        return np.nan

    # ------------------------------------------------------------------
    # 清洗流水线
    # ------------------------------------------------------------------
    def execute_cleaning_pipeline(self):
        """
        执行标准数据清洗流水线，输出干净的结构化数据集。
        """
        self.df = pd.read_csv(self.file_path)

        # 1. 过滤缺失值与非标准异常值
        self.df = self.df[self.df["salary"] != "暂无数据"].dropna(subset=["salary"])

        # 过滤空字符串薪资
        self.df = self.df[self.df["salary"].astype(str).str.strip() != ""]

        # 2. 正则表达式解析薪酬，转换并统一量纲为 k/月
        self.df["salary_numeric"] = self.df["salary"].apply(self.normalize_salary)
        self.df = self.df.dropna(subset=["salary_numeric"])

        # 3. 清洗地区字段（提取城市名）
        if "location" in self.df.columns:
            self.df["location"] = self.df["location"].apply(self._clean_location)

        # 4. 清洗学历字段（标准化）
        if "education" in self.df.columns:
            self.df["education"] = self.df["education"].apply(self._clean_education)

        # 5. 清洗经验字段（标准化）
        if "experience" in self.df.columns:
            self.df["experience"] = self.df["experience"].apply(self._clean_experience)

        # 6. 对分类变量进行有序分类数值编码（Ordinal Encoding）
        edu_mapping = {"大专": 1, "本科": 2, "硕士": 3, "博士": 4}
        exp_mapping = {"不限": 1, "无经验": 1, "1-3年": 2, "3-5年": 3, "5-10年": 4}

        self.df["edu_code"] = self.df["education"].map(edu_mapping).fillna(2)
        self.df["exp_code"] = self.df["experience"].map(exp_mapping).fillna(1)

        # 7. 基于 IQR 准则过滤薪酬异常离群值
        if len(self.df) > 10:
            q1  = self.df["salary_numeric"].quantile(0.25)
            q3  = self.df["salary_numeric"].quantile(0.75)
            iqr = q3 - q1
            self.df = self.df[
                (self.df["salary_numeric"] >= (q1 - 1.5 * iqr)) &
                (self.df["salary_numeric"] <= (q3 + 1.5 * iqr))
            ]

        self.df.to_csv("./output/cleaned_recruitment_data.csv", index=False, encoding="utf-8-sig")
        return len(self.df)

    @staticmethod
    def _clean_location(location: str) -> str:
        """清洗地区字段，提取城市名。"""
        if not location or pd.isna(location):
            return ""
        location = str(location).strip()
        if "·" in location:
            return location.split("·")[0].strip()
        return location

    @staticmethod
    def _clean_education(education: str) -> str:
        """标准化学历字段。"""
        if not education or pd.isna(education):
            return ""
        edu = str(education).strip()
        # 映射 51job 的学历描述到标准格式
        edu_map = {
            "大专": "大专", "本科": "本科", "硕士": "硕士", "博士": "博士",
            "中专": "大专", "中技": "大专", "高中": "大专",
            "初中及以下": "大专", "MBA": "硕士", "EMBA": "硕士",
            "大专及以上": "大专", "本科及以上": "本科",
            "硕士及以上": "硕士", "博士及以上": "博士",
        }
        return edu_map.get(edu, edu)

    @staticmethod
    def _clean_experience(experience: str) -> str:
        """标准化经验字段。"""
        if not experience or pd.isna(experience):
            return ""
        exp = str(experience).strip()
        # 映射 51job 的经验描述到标准格式
        exp_map = {
            "无经验": "无经验", "不限": "不限",
            "1-3年": "1-3年", "3-5年": "3-5年", "5-10年": "5-10年",
            "1年以下": "无经验", "1年": "1-3年", "2年": "1-3年",
            "3-4年": "3-5年", "5-6年": "5-10年", "10年以上": "5-10年",
            "在校/应届": "无经验", "无需经验": "无经验",
        }
        if exp in exp_map:
            return exp_map[exp]

        # 处理 "X年及以上" 格式（51job 常见格式）
        m = re.match(r"(\d+)\s*年及以上", exp)
        if m:
            years = int(m.group(1))
            if years <= 1:
                return "1-3年"
            elif years <= 3:
                return "1-3年"
            elif years <= 5:
                return "3-5年"
            else:
                return "5-10年"

        # 处理 "X-X年" 格式
        m2 = re.match(r"(\d+)\s*[-–—]\s*(\d+)\s*年", exp)
        if m2:
            low, high = int(m2.group(1)), int(m2.group(2))
            if high <= 3:
                return "1-3年"
            elif high <= 5:
                return "3-5年"
            else:
                return "5-10年"

        return exp

    # ------------------------------------------------------------------
    # 统计分析报告
    # ------------------------------------------------------------------
    def generate_statistical_insights(self):
        """
        进行多维统计特征提取，输出分析结论。
        """
        print("=" * 55)
        print("  1. 薪资分布描述性统计指标（单位：k/月）")
        print("=" * 55)
        desc_stats = self.df["salary_numeric"].describe().round(2)
        print(desc_stats)

        print("\n" + "=" * 55)
        print("  2. 学历 × 工作经验交叉下的平均薪酬矩阵（k/月）")
        print("=" * 55)
        # 指定学历和经验的显示顺序
        edu_order = ["大专", "本科", "硕士", "博士"]
        exp_order = ["无经验", "不限", "1-3年", "3-5年", "5-10年"]

        # 仅保留数据中实际存在的类别，避免全 NaN 列/行
        edu_order = [e for e in edu_order if e in self.df["education"].unique()]
        exp_order = [e for e in exp_order if e in self.df["experience"].unique()]

        if edu_order and exp_order:
            pivot_table = self.df.pivot_table(
                values="salary_numeric",
                index="education",
                columns="experience",
                aggfunc="mean"
            ).reindex(index=edu_order, columns=exp_order).round(2)
            print(pivot_table.to_string())
        else:
            print("  （数据中学历或经验字段为空，无法生成交叉矩阵）")

        print("\n" + "=" * 55)
        print("  3. 学历、工作经验与薪酬的 Pearson 相关矩阵")
        print("=" * 55)
        corr_matrix = self.df[["salary_numeric", "edu_code", "exp_code"]].corr().round(4)
        print(corr_matrix)

        print("\n" + "=" * 55)
        print("  4. 城市招聘需求量 Top 10")
        print("=" * 55)
        if "location" in self.df.columns:
            city_counts = self.df["location"].value_counts().head(10)
            print(city_counts.to_string())
        else:
            print("  （数据中无城市字段）")

        return desc_stats, corr_matrix


# ── 入口 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    engine = RecruitmentAnalysisEngine()
    cleaned_size = engine.execute_cleaning_pipeline()
    print(f"[INFO] 数据清洗转换完毕，剩余高质量样本数: {cleaned_size} 条。")
    print()
    desc_stats, corr_matrix = engine.generate_statistical_insights()
