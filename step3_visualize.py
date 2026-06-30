"""
第五阶段：成果展示
招聘市场多维可视化看板 —— 高等教育与培训体系改革支撑分析

政策核心论点：
  ① 淘汰过时技术栈，跟进前沿技术演进（前沿技能薪资溢价 Panel E）
  ② 高校全面导入机器学习、BI 实践课程（技能需求量结构 Panel F）
  ③ 缩短毕业生从象牙塔向企业工程应用转换的时间间距（经验壁垒 Panel G）
  ④ 提升毕业生初期人力资本存量（学历×经验联合薪资热力图 Panel H）
  ⑤ 减少结构性失业、提升人力资源利用效率（学历分布 Panel I）


输入：cleaned_recruitment_data.csv
输出（8 张独立 PNG）：
  panel_a_education_salary_boxplot.png
  panel_b_city_demand_barchart.png
  panel_c_experience_salary_lineplot.png
  panel_d_city_avg_salary.png
  panel_e_skill_salary_premium.png
  panel_f_tech_job_demand.png
  panel_g_experience_barrier.png
  panel_h_edu_exp_heatmap.png
"""

import os
import re
import warnings

import matplotlib
matplotlib.use("Agg")

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns


# ══════════════════════════════════════════════════════════════════════════════
#  字体工具（跨平台中文渲染，使用 FontProperties(fname=...) 直接绑定文件路径）
# ══════════════════════════════════════════════════════════════════════════════

CANDIDATE_FONT_PATHS = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def _get_chinese_font() -> fm.FontProperties:
    for fpath in CANDIDATE_FONT_PATHS:
        if os.path.isfile(fpath):
            prop = fm.FontProperties(fname=fpath)
            font_name = prop.get_name()
            print(f"[字体] {fpath}  →  {font_name}")

            # 同时注册到 matplotlib 全局，使 seaborn 色条/内部元素也能渲染中文 
            # addfont() 让 fontManager 识别该文件；
            # 然后把字体名称写入 rcParams，作为 seaborn 内部渲染的兜底字体。
            fm.fontManager.addfont(fpath)
            plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            plt.rcParams["font.family"]     = "sans-serif"
            plt.rcParams["axes.unicode_minus"] = False

            return prop
    print("[字体][WARN] 未找到中文字体，标签可能乱码。")
    return fm.FontProperties()


def fp(base: fm.FontProperties, size: int = 11,
       weight: str = "normal") -> fm.FontProperties:
    """快捷克隆：从基础字体生成指定大小/粗细的副本。"""
    p = fm.FontProperties(fname=base.get_file())
    p.set_size(size)
    p.set_weight(weight)
    return p


def apply_ticks(ax, base: fm.FontProperties,
                size: int = 9, axis: str = "both") -> None:
    """对 ax 的刻度标签统一应用中文字体（零警告写法）。"""
    tfp = fp(base, size)
    if axis in ("x", "both"):
        for t in ax.get_xticklabels():
            t.set_fontproperties(tfp)
    if axis in ("y", "both"):
        for t in ax.get_yticklabels():
            t.set_fontproperties(tfp)


def save_fig(fig: plt.Figure, path: str, label: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        plt.tight_layout()
        fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[完成] {label} → {path}")


# ══════════════════════════════════════════════════════════════════════════════
#  数据预处理
# ══════════════════════════════════════════════════════════════════════════════

def prepare_data(data_path: str) -> pd.DataFrame:
    """加载并做轻量补充清洗，返回分析就绪的 DataFrame。"""
    df = pd.read_csv(data_path)

    # 标准化经验字段：统一 '3年'→'1-3年'，'5年'→'3-5年'
    exp_fix = {"3年": "1-3年", "5年": "3-5年"}
    df["experience"] = df["experience"].replace(exp_fix)

    # 清洗学历：去掉 '中技/中专'（样本量太少，归入大专）
    df["education"] = df["education"].replace({"中技/中专": "大专"})

    # 行业取第一个标签（去掉'丨'后缀）
    df["industry_clean"] = df["industry"].str.split("丨").str[0].str.strip()

    # 技能分类标签（用于溢价图 / 需求量图）
    def classify_skill(title: str) -> str:
        t = str(title).lower()
        if re.search(r"ai|算法|机器学习|深度学习|nlp|cv|大模型", t):
            return "AI / 算法"
        if re.search(r"大数据|数据工程|数据仓库|数据开发", t):
            return "大数据工程"
        if re.search(r"数据分析|bi|商业智能|数据挖掘", t):
            return "数据分析 / BI"
        if re.search(r"测试|运维|后端|前端|嵌入式|硬件", t):
            return "传统软硬件"
        return "其他"

    df["skill_cat"] = df["job_title"].apply(classify_skill)
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  Panel A：学历门槛 - 薪资分布箱线图
# ══════════════════════════════════════════════════════════════════════════════

def render_panel_a(df: pd.DataFrame, base_fp: fm.FontProperties,
                   out: str = "panel_a_education_salary_boxplot.png") -> None:
    edu_order = [e for e in ["大专", "本科", "硕士", "博士"]
                 if e in df["education"].unique()]
    if not edu_order:
        print("[SKIP] Panel A: 无有效学历数据")
        return

    fig, ax = plt.subplots(figsize=(9, 6))
    sns.boxplot(data=df, x="education", y="salary_numeric",
                order=edu_order, hue="education", hue_order=edu_order,
                palette="Blues_r", width=0.52, legend=False, ax=ax)

    # 在每个箱子上方标注中位数
    medians = df.groupby("education")["salary_numeric"].median()
    for i, edu in enumerate(edu_order):
        if edu in medians.index:
            ax.text(i, medians[edu] + 0.5, f"{medians[edu]:.1f}k",
                    ha="center", va="bottom", fontsize=9, color="#1a5276",
                    fontproperties=fp(base_fp, 9))

    ax.set_title("不同学历门槛下的岗位薪资分布",
                 fontproperties=fp(base_fp, 14, "bold"), pad=14)
    ax.set_xlabel("最低学历要求", fontproperties=fp(base_fp, 11), labelpad=8)
    ax.set_ylabel("月薪（k/月）", fontproperties=fp(base_fp, 11), labelpad=8)
    apply_ticks(ax, base_fp)
    save_fig(fig, out, "Panel A")


# ══════════════════════════════════════════════════════════════════════════════
#  Panel B：核心城市招聘需求量柱状图
# ══════════════════════════════════════════════════════════════════════════════

def render_panel_b(df: pd.DataFrame, base_fp: fm.FontProperties,
                   out: str = "panel_b_city_demand_barchart.png") -> None:
    city_df = (df["city"].value_counts()
               .reset_index()
               .rename(columns={"city": "city", "count": "cnt"}))
    city_df = city_df.sort_values("cnt", ascending=False).head(10)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = sns.barplot(data=city_df, x="city", y="cnt",
                       hue="city", palette="Set2",
                       width=0.62, legend=False, ax=ax)

    for bar in ax.patches:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 2,
                    f"{int(h)}", ha="center", va="bottom",
                    fontproperties=fp(base_fp, 9))

    ax.set_title("各城市招聘需求规模对比",
                 fontproperties=fp(base_fp, 14, "bold"), pad=14)
    ax.set_xlabel("城市", fontproperties=fp(base_fp, 11), labelpad=8)
    ax.set_ylabel("岗位数量（个）", fontproperties=fp(base_fp, 11), labelpad=8)
    ax.tick_params(axis="x", rotation=20)
    apply_ticks(ax, base_fp)
    save_fig(fig, out, "Panel B")


# ══════════════════════════════════════════════════════════════════════════════
#  Panel C：工作经验 × 平均月薪趋势折线图
# ══════════════════════════════════════════════════════════════════════════════

def render_panel_c(df: pd.DataFrame, base_fp: fm.FontProperties,
                   out: str = "panel_c_experience_salary_lineplot.png") -> None:
    exp_order_map = {"无经验": 0, "不限": 1, "1-3年": 2, "3-5年": 3, "5-10年": 4}
    exp_df = (df.groupby("experience")["salary_numeric"].mean()
              .reset_index())
    exp_df["rank"] = exp_df["experience"].map(exp_order_map)
    exp_df = exp_df.dropna(subset=["rank"]).sort_values("rank")
    if exp_df.empty:
        print("[SKIP] Panel C: 无有效经验数据")
        return

    fig, ax = plt.subplots(figsize=(9, 6))
    sns.lineplot(data=exp_df, x="experience", y="salary_numeric",
                 marker="o", markersize=9, linewidth=2.6,
                 color="#D9383A", ax=ax)
    for _, row in exp_df.iterrows():
        ax.annotate(f"{row['salary_numeric']:.1f}k",
                    xy=(row["experience"], row["salary_numeric"]),
                    xytext=(0, 11), textcoords="offset points",
                    ha="center", fontproperties=fp(base_fp, 9),
                    color="#D9383A")

    ax.set_title("工作经验积累与平均月薪变动趋势",
                 fontproperties=fp(base_fp, 14, "bold"), pad=14)
    ax.set_xlabel("工作年限要求", fontproperties=fp(base_fp, 11), labelpad=8)
    ax.set_ylabel("平均月薪（k/月）", fontproperties=fp(base_fp, 11), labelpad=8)
    apply_ticks(ax, base_fp)
    save_fig(fig, out, "Panel C")


# ══════════════════════════════════════════════════════════════════════════════
#  Panel D：各城市平均薪资对比柱状图
#  论点支撑：揭示一线城市高薪资的地理虹吸效应，强化课程改革的紧迫性
# ══════════════════════════════════════════════════════════════════════════════

def render_panel_d(df: pd.DataFrame, base_fp: fm.FontProperties,
                   out: str = "panel_d_city_avg_salary.png") -> None:
    city_sal = (df.groupby("city")["salary_numeric"].mean()
                .reset_index()
                .rename(columns={"salary_numeric": "avg_salary"})
                .sort_values("avg_salary", ascending=False))

    fig, ax = plt.subplots(figsize=(10, 6))

    palette = sns.color_palette("RdYlGn_r", len(city_sal))[::-1]
    bars = ax.bar(city_sal["city"], city_sal["avg_salary"],
                  color=palette, width=0.58, edgecolor="white", linewidth=0.8)

    # 全国均值参考线
    overall_mean = df["salary_numeric"].mean()
    ax.axhline(overall_mean, color="#555", linestyle="--",
               linewidth=1.4, label=f"全样本均值 {overall_mean:.1f}k")
    ax.legend(prop=fp(base_fp, 10))

    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3,
                f"{h:.1f}k", ha="center", va="bottom",
                fontproperties=fp(base_fp, 9, "bold"), color="#2c3e50")

    ax.set_title("各城市平均月薪对比（含全样本均值参考线）",
                 fontproperties=fp(base_fp, 14, "bold"), pad=14)
    ax.set_xlabel("城市", fontproperties=fp(base_fp, 11), labelpad=8)
    ax.set_ylabel("平均月薪（k/月）", fontproperties=fp(base_fp, 11), labelpad=8)
    ax.set_ylim(0, city_sal["avg_salary"].max() * 1.18)
    ax.tick_params(axis="x", rotation=15)
    apply_ticks(ax, base_fp)
    save_fig(fig, out, "Panel D")


# ══════════════════════════════════════════════════════════════════════════════
#  Panel E：前沿技能薪资溢价对比图（水平条形图）
#  论点支撑①：AI/算法技能溢价 +18.9%，论证"淘汰过时技术栈"的经济必要性
# ══════════════════════════════════════════════════════════════════════════════

def render_panel_e(df: pd.DataFrame, base_fp: fm.FontProperties,
                   out: str = "panel_e_skill_salary_premium.png") -> None:
    baseline = df["salary_numeric"].mean()

    skill_stats = (df.groupby("skill_cat")["salary_numeric"]
                   .agg(n="count", avg="mean")
                   .reset_index())
    skill_stats["premium"] = (
        (skill_stats["avg"] - baseline) / baseline * 100
    ).round(1)
    skill_stats = skill_stats.sort_values("premium", ascending=True)

    # 过滤样本量不足5条的类别
    skill_stats = skill_stats[skill_stats["n"] >= 5]

    fig, ax = plt.subplots(figsize=(10, 5))

    colors = ["#e74c3c" if v >= 0 else "#3498db"
              for v in skill_stats["premium"]]
    bars = ax.barh(skill_stats["skill_cat"], skill_stats["premium"],
                   color=colors, height=0.52, edgecolor="white")

    # 零基准线
    ax.axvline(0, color="#555", linewidth=1.2, linestyle="-")

    # 标注数值 + 样本量
    for bar, (_, row) in zip(bars, skill_stats.iterrows()):
        x = bar.get_width()
        offset = 0.6 if x >= 0 else -0.6
        ha = "left" if x >= 0 else "right"
        ax.text(x + offset,
                bar.get_y() + bar.get_height() / 2,
                f"{row['premium']:+.1f}%  (n={int(row['n'])})",
                va="center", ha=ha,
                fontproperties=fp(base_fp, 9, "bold"),
                color="#2c3e50")

    # 添加图例说明
    red_p = mpatches.Patch(color="#e74c3c", label="高于均值（薪资溢价）")
    blue_p = mpatches.Patch(color="#3498db", label="低于均值（薪资折价）")
    ax.legend(handles=[red_p, blue_p], prop=fp(base_fp, 9),
              loc="lower right")

    ax.set_title(f"不同技能方向的薪资溢价率对比\n（基准：全样本均薪 {baseline:.1f}k/月）",
                 fontproperties=fp(base_fp, 14, "bold"), pad=14)
    ax.set_xlabel("相对全样本均薪的溢价率（%）",
                  fontproperties=fp(base_fp, 11), labelpad=8)
    ax.set_ylabel("技能方向分类",
                  fontproperties=fp(base_fp, 11), labelpad=8)
    apply_ticks(ax, base_fp)
    save_fig(fig, out, "Panel E")


# ══════════════════════════════════════════════════════════════════════════════
#  Panel F：热门技术方向招聘需求量排行（水平条形图）
#  论点支撑②：AI/算法岗占样本 39%，论证"高校导入 ML/BI 课程"的市场需求依据
# ══════════════════════════════════════════════════════════════════════════════

def render_panel_f(df: pd.DataFrame, base_fp: fm.FontProperties,
                   out: str = "panel_f_tech_job_demand.png") -> None:
    # 统计各技能分类的岗位数量及占比
    cat_df = (df.groupby("skill_cat")
              .agg(n=("job_title", "count"),
                   avg_sal=("salary_numeric", "mean"))
              .reset_index()
              .sort_values("n", ascending=True))

    total = len(df)
    cat_df["pct"] = (cat_df["n"] / total * 100).round(1)

    palette = {"AI / 算法":      "#e74c3c",
               "大数据工程":      "#e67e22",
               "数据分析 / BI":   "#3498db",
               "传统软硬件":      "#95a5a6",
               "其他":           "#bdc3c7"}
    colors = [palette.get(c, "#aab7b8") for c in cat_df["skill_cat"]]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    bars = ax.barh(cat_df["skill_cat"], cat_df["n"],
                   color=colors, height=0.52, edgecolor="white")

    for bar, (_, row) in zip(bars, cat_df.iterrows()):
        ax.text(bar.get_width() + 5,
                bar.get_y() + bar.get_height() / 2,
                f"{int(row['n'])} 条 ({row['pct']}%)  均薪 {row['avg_sal']:.1f}k",
                va="center", fontproperties=fp(base_fp, 9), color="#2c3e50")

    ax.set_title("各技能方向招聘岗位数量及均薪分布\n"
                 "（数据佐证：前沿技术岗需求主导市场，传统方向相对饱和）",
                 fontproperties=fp(base_fp, 13, "bold"), pad=14)
    ax.set_xlabel("招聘岗位数量（条）",
                  fontproperties=fp(base_fp, 11), labelpad=8)
    ax.set_ylabel("技能方向分类",
                  fontproperties=fp(base_fp, 11), labelpad=8)
    ax.set_xlim(0, cat_df["n"].max() * 1.45)
    apply_ticks(ax, base_fp)
    save_fig(fig, out, "Panel F")


# ══════════════════════════════════════════════════════════════════════════════
#  Panel G：经验壁垒与应届生就业困境（双轴组合图）
#  论点支撑③：60.9% 岗位要求 1-3 年经验，仅 12.4% 接受无经验，
#             直观揭示应届生跨越"经验壁垒"的结构性障碍，论证缩短
#             学校→企业转换时间的政策必要性。
# ══════════════════════════════════════════════════════════════════════════════

def render_panel_g(df: pd.DataFrame, base_fp: fm.FontProperties,
                   out: str = "panel_g_experience_barrier.png") -> None:
    exp_order = ["无经验", "1-3年", "3-5年", "5-10年"]
    df_exp = df[df["experience"].isin(exp_order)].copy()

    stats = (df_exp.groupby("experience")
             .agg(n=("salary_numeric", "count"),
                  avg_sal=("salary_numeric", "mean"))
             .reindex(exp_order)
             .reset_index())
    stats["pct"] = (stats["n"] / stats["n"].sum() * 100).round(1)

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()

    colors = ["#3498db" if e == "无经验" else "#e74c3c"
              for e in stats["experience"]]
    bars = ax1.bar(stats["experience"], stats["pct"],
                   color=colors, width=0.5, alpha=0.82, label="岗位占比（%）")

    ax2.plot(stats["experience"], stats["avg_sal"],
             marker="D", markersize=9, linewidth=2.4,
             color="#2ecc71", label="平均月薪（k）", zorder=5)

    # 标注柱子上方的占比
    for bar, (_, row) in zip(bars, stats.iterrows()):
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.5,
                 f"{row['pct']:.1f}%",
                 ha="center", va="bottom",
                 fontproperties=fp(base_fp, 10, "bold"),
                 color="#2c3e50")

    # 标注折线上的薪资值
    for _, row in stats.iterrows():
        ax2.annotate(f"{row['avg_sal']:.1f}k",
                     xy=(row["experience"], row["avg_sal"]),
                     xytext=(0, 10), textcoords="offset points",
                     ha="center",
                     fontproperties=fp(base_fp, 9),
                     color="#27ae60")

    # 应届生困境注释框
    ax1.annotate("仅 12.4% 岗位接受无经验\n—— 应届生就业壁垒显著",
                 xy=(0, stats.loc[stats["experience"] == "无经验", "pct"].values[0]),
                 xytext=(0.5, 45),
                 arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.5),
                 fontproperties=fp(base_fp, 9),
                 color="#c0392b",
                 bbox=dict(boxstyle="round,pad=0.4",
                           facecolor="#fdecea", edgecolor="#c0392b", alpha=0.9))

    ax1.set_title("招聘经验需求结构与对应薪资水平\n"
                  "（应届生经验壁垒分析：60.9% 岗位要求 1~3 年工作经验）",
                  fontproperties=fp(base_fp, 13, "bold"), pad=14)
    ax1.set_xlabel("工作年限要求", fontproperties=fp(base_fp, 11), labelpad=8)
    ax1.set_ylabel("岗位占比（%）", fontproperties=fp(base_fp, 11), labelpad=8)
    ax2.set_ylabel("平均月薪（k/月）", fontproperties=fp(base_fp, 11), labelpad=8)

    apply_ticks(ax1, base_fp)
    apply_ticks(ax2, base_fp, axis="y")

    # 合并图例
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, prop=fp(base_fp, 10), loc="upper right")

    save_fig(fig, out, "Panel G")


# ══════════════════════════════════════════════════════════════════════════════
#  Panel H：学历 - 工作经验联合薪资热力图
#  论点支撑④：高学历 + 高经验呈现显著复合增益，论证提升毕业生初期
#             人力资本存量可有效降低企业帮带成本、加速回报周期。
# ══════════════════════════════════════════════════════════════════════════════

def render_panel_h(df: pd.DataFrame, base_fp: fm.FontProperties,
                   out: str = "panel_h_edu_exp_heatmap.png") -> None:
    edu_order = ["大专", "本科", "硕士", "博士"]
    exp_order = ["无经验", "1-3年", "3-5年", "5-10年"]

    df_sub = df[df["education"].isin(edu_order) &
                df["experience"].isin(exp_order)].copy()

    pivot = df_sub.pivot_table(
        values="salary_numeric",
        index="education",
        columns="experience",
        aggfunc="mean"
    ).reindex(index=edu_order, columns=exp_order)

    # 同时统计各单元格样本量（用于标注）
    count_pivot = df_sub.pivot_table(
        values="salary_numeric",
        index="education",
        columns="experience",
        aggfunc="count"
    ).reindex(index=edu_order, columns=exp_order)

    fig, ax = plt.subplots(figsize=(11, 6))

    im = sns.heatmap(pivot, annot=False, cmap="YlOrRd",
                     linewidths=0.6, linecolor="white",
                     ax=ax, vmin=8, vmax=40,
                     cbar_kws={"label": "平均月薪 (k/月)"})

    # 手动标注：薪资 + 样本量
    for i, edu in enumerate(edu_order):
        for j, exp in enumerate(exp_order):
            val = pivot.loc[edu, exp]
            cnt = count_pivot.loc[edu, exp]
            if not np.isnan(val):
                # 深色背景用白字，浅色背景用黑字
                text_color = "white" if val > 28 else "#2c3e50"
                ax.text(j + 0.5, i + 0.38,
                        f"{val:.1f}k",
                        ha="center", va="center",
                        fontproperties=fp(base_fp, 11, "bold"),
                        color=text_color)
                ax.text(j + 0.5, i + 0.68,
                        f"n={int(cnt)}",
                        ha="center", va="center",
                        fontproperties=fp(base_fp, 8),
                        color=text_color)
            else:
                ax.text(j + 0.5, i + 0.5, "—",
                        ha="center", va="center",
                        fontproperties=fp(base_fp, 11),
                        color="#aaa")

    ax.set_title("学历 × 工作经验联合薪资热力图\n"
                 "（单元格：均薪 / 样本量；复合效应印证提升初始人力资本的回报价值）",
                 fontproperties=fp(base_fp, 13, "bold"), pad=14)
    ax.set_xlabel("工作年限要求", fontproperties=fp(base_fp, 11), labelpad=8)
    ax.set_ylabel("学历要求", fontproperties=fp(base_fp, 11), labelpad=8)

    apply_ticks(ax, base_fp)

    # 色条字体
    cbar = ax.collections[0].colorbar
    cbar.set_label("平均月薪 (k/月)",
                   fontproperties=fp(base_fp, 10))
    for t in cbar.ax.get_yticklabels():
        t.set_fontproperties(fp(base_fp, 9))

    save_fig(fig, out, "Panel H")


# ══════════════════════════════════════════════════════════════════════════════
#  主入口：一键生成全部 8 张图表
# ══════════════════════════════════════════════════════════════════════════════

def render_recruitment_dashboard(
        data_path: str = "cleaned_recruitment_data.csv",
        output_dir: str = ".",
) -> None:
    """
    加载清洗数据，依次生成 8 张高清分析图，输出至 output_dir。

    图表列表：
      Panel A — 学历门槛 - 薪资箱线图
      Panel B — 城市招聘需求量柱状图
      Panel C — 工作经验 - 均薪折线图
      Panel D — 各城市平均薪资对比图          [新增]
      Panel E — 技能方向薪资溢价图            [新增，论点①]
      Panel F — 热门技术方向需求量排行         [新增，论点②]
      Panel G — 经验壁垒与应届生困境组合图     [新增，论点③]
      Panel H — 学历×经验联合薪资热力图        [新增，论点④]
    """
    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"找不到数据文件: '{data_path}'，"
            "请先运行 step2_clean_analyze.py"
        )

    print("=" * 60)
    print("  招聘市场多维可视化看板（教育改革版 v2）")
    print("=" * 60)

    base_fp = _get_chinese_font()
    plt.rcParams["axes.unicode_minus"] = False
    sns.set_theme(style="whitegrid")

    df = prepare_data(data_path)
    print(f"[数据] 加载完成：{len(df)} 条有效记录\n")

    os.makedirs(output_dir, exist_ok=True)

    def p(name: str) -> str:
        return os.path.join(output_dir, name)

    render_panel_a(df, base_fp, p("panel_a_education_salary_boxplot.png"))
    render_panel_b(df, base_fp, p("panel_b_city_demand_barchart.png"))
    render_panel_c(df, base_fp, p("panel_c_experience_salary_lineplot.png"))
    render_panel_d(df, base_fp, p("panel_d_city_avg_salary.png"))
    render_panel_e(df, base_fp, p("panel_e_skill_salary_premium.png"))
    render_panel_f(df, base_fp, p("panel_f_tech_job_demand.png"))
    render_panel_g(df, base_fp, p("panel_g_experience_barrier.png"))
    render_panel_h(df, base_fp, p("panel_h_edu_exp_heatmap.png"))

    print("\n" + "=" * 60)
    print("  全部图表已生成（8 张，300dpi PNG）")
    print("=" * 60)
    chart_info = [
        ("Panel A", "panel_a_education_salary_boxplot.png",  "学历 - 薪资箱线图"),
        ("Panel B", "panel_b_city_demand_barchart.png",      "城市招聘需求量"),
        ("Panel C", "panel_c_experience_salary_lineplot.png","经验 - 均薪折线"),
        ("Panel D", "panel_d_city_avg_salary.png",           "城市平均薪资对比"),
        ("Panel E", "panel_e_skill_salary_premium.png",      "技能薪资溢价率"),
        ("Panel F", "panel_f_tech_job_demand.png",           "技术方向需求量"),
        ("Panel G", "panel_g_experience_barrier.png",        "经验壁垒双轴图"),
        ("Panel H", "panel_h_edu_exp_heatmap.png",           "学历×经验热力图"),
    ]
    for panel, fname, desc in chart_info:
        print(f"  [{panel}] {fname}  ←  {desc}")


# ── 入口 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    render_recruitment_dashboard(
        data_path="./output/cleaned_recruitment_data.csv",
        output_dir="./images/",
    )
