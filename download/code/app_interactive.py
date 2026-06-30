# ══════════════════════════════════════════════════════════════
# app_interactive.py — 进阶版交互式数据看板（Plotly + Streamlit）
# 运行方式：streamlit run app_interactive.py
# ══════════════════════════════════════════════════════════════
import os
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── 页面配置 ──────────────────────────────────────────────
st.set_page_config(
    page_title="招聘市场多维可视化看板",
    page_icon="📊",
    layout="wide",
)

# ── 数据预处理（复用你的逻辑） ────────────────────────────
@st.cache_data
def load_and_prepare(data_path: str) -> pd.DataFrame:
    df = pd.read_csv(data_path)
    exp_fix = {"3年": "1-3年", "5年": "3-5年"}
    df["experience"] = df["experience"].replace(exp_fix)
    df["education"] = df["education"].replace({"中技/中专": "大专"})
    df["industry_clean"] = df["industry"].str.split("丨").str[0].str.strip()

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

# ── 加载数据 ──────────────────────────────────────────────
data_path = st.sidebar.selectbox(
    "选择数据文件",
    ["./download/output/cleaned_recruitment_data.csv"],
    index=0,
)

if not os.path.exists(data_path):
    st.error(f"❌ 找不到数据文件: {data_path}")
    st.stop()

df = load_and_prepare(data_path)
total_records = len(df)

# ── 侧边栏筛选 ────────────────────────────────────────────
st.sidebar.markdown("## 数据筛选")

all_cities = sorted(df["city"].unique())
selected_cities = st.sidebar.multiselect("选择城市", all_cities, default=all_cities)

all_skills = sorted(df["skill_cat"].unique())
selected_skills = st.sidebar.multiselect("选择技能方向", all_skills, default=all_skills)

all_edu = [e for e in ["大专", "本科", "硕士", "博士"] if e in df["education"].unique()]
selected_edu = st.sidebar.multiselect("选择学历", all_edu, default=all_edu)

salary_min, salary_max = st.sidebar.slider(
    "薪资范围 (k/月)",
    float(df["salary_numeric"].min()),
    float(df["salary_numeric"].max()),
    (float(df["salary_numeric"].min()), float(df["salary_numeric"].max())),
)

# 应用筛选
mask = (
    df["city"].isin(selected_cities)
    & df["skill_cat"].isin(selected_skills)
    & df["education"].isin(selected_edu)
    & df["salary_numeric"].between(salary_min, salary_max)
)
df_filtered = df[mask].copy()

# ── 顶部指标卡片 ──────────────────────────────────────────
st.markdown("# 招聘市场多维可视化看板")
st.markdown("### 高等教育与培训体系改革支撑分析")
st.markdown("---")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("总岗位数", f"{total_records}", f"筛选后: {len(df_filtered)}")
with col2:
    st.metric("平均月薪", f"{df_filtered['salary_numeric'].mean():.1f}k")
with col3:
    st.metric("中位月薪", f"{df_filtered['salary_numeric'].median():.1f}k")
with col4:
    ai_pct = (df_filtered["skill_cat"] == "AI / 算法").mean() * 100
    st.metric("AI岗占比", f"{ai_pct:.1f}%")
with col5:
    entry_pct = (df_filtered["experience"] == "无经验").mean() * 100
    st.metric("无经验岗占比", f"{entry_pct:.1f}%")

st.markdown("---")

# ══════════════════════════════════════════════════════════
# Panel A：学历 - 薪资箱线图
# ══════════════════════════════════════════════════════════
st.markdown("## Panel A：学历门槛 × 薪资分布")
col_a1, col_a2 = st.columns([3, 1])
with col_a1:
    fig_a = px.box(
        df_filtered, x="education", y="salary_numeric",
        category_orders={"education": ["大专", "本科", "硕士", "博士"]},
        color="education",
        title="不同学历门槛下的岗位薪资分布",
        labels={"salary_numeric": "月薪 (k/月)", "education": "最低学历要求"},
    )
    fig_a.update_layout(showlegend=False, height=450)
    st.plotly_chart(fig_a, use_container_width=True)
with col_a2:
    st.markdown("#### 统计摘要")
    summary = df_filtered.groupby("education")["salary_numeric"].describe()[
        ["count", "mean", "50%", "min", "max"]
    ].round(1)
    summary.columns = ["样本量", "均值", "中位数", "最小值", "最大值"]
    st.dataframe(summary, use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════
# Panel B & D：城市需求量 + 平均薪资
# ══════════════════════════════════════════════════════════
col_b, col_d = st.columns(2)

with col_b:
    st.markdown("## Panel B：城市招聘需求量")
    city_count = df_filtered["city"].value_counts().head(15).reset_index()
    city_count.columns = ["city", "count"]
    fig_b = px.bar(
        city_count, x="city", y="count",
        title="各城市招聘需求规模",
        labels={"city": "城市", "count": "岗位数量"},
        color="count", color_continuous_scale="Blues",
    )
    fig_b.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_b, use_container_width=True)

with col_d:
    st.markdown("## Panel D：城市平均薪资")
    city_sal = df_filtered.groupby("city")["salary_numeric"].mean().reset_index()
    city_sal.columns = ["city", "avg_salary"]
    city_sal = city_sal.sort_values("avg_salary", ascending=False)
    fig_d = px.bar(
        city_sal, x="city", y="avg_salary",
        title="各城市平均月薪对比",
        labels={"city": "城市", "avg_salary": "平均月薪 (k)"},
        color="avg_salary", color_continuous_scale="RdYlGn_r",
    )
    fig_d.add_hline(y=df_filtered["salary_numeric"].mean(),
                    line_dash="dash", line_color="gray",
                    annotation_text=f"均值 {df_filtered['salary_numeric'].mean():.1f}k")
    fig_d.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_d, use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════
# Panel C：经验 - 均薪趋势
# ══════════════════════════════════════════════════════════
st.markdown("## Panel C：工作经验 - 平均月薪趋势")
exp_order_map = {"无经验": 0, "不限": 1, "1-3年": 2, "3-5年": 3, "5-10年": 4}
exp_df = df_filtered.groupby("experience")["salary_numeric"].mean().reset_index()
exp_df["rank"] = exp_df["experience"].map(exp_order_map)
exp_df = exp_df.dropna(subset=["rank"]).sort_values("rank")

fig_c = px.line(
    exp_df, x="experience", y="salary_numeric",
    markers=True, title="工作经验积累与平均月薪变动趋势",
    labels={"salary_numeric": "平均月薪 (k/月)", "experience": "工作年限要求"},
)
fig_c.update_traces(marker_size=12, line_width=3, line_color="#D9383A")
fig_c.update_layout(height=400)
st.plotly_chart(fig_c, use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════
# Panel E & F：技能薪资溢价 + 技术方向需求量
# ══════════════════════════════════════════════════════════
col_e, col_f = st.columns(2)

with col_e:
    st.markdown("## Panel E：技能方向薪资溢价率")
    baseline = df_filtered["salary_numeric"].mean()
    skill_stats = df_filtered.groupby("skill_cat")["salary_numeric"].agg(
        n="count", avg="mean"
    ).reset_index()
    skill_stats["premium"] = ((skill_stats["avg"] - baseline) / baseline * 100).round(1)
    skill_stats = skill_stats[skill_stats["n"] >= 5].sort_values("premium")
    skill_stats["color"] = skill_stats["premium"].apply(lambda v: "#e74c3c" if v >= 0 else "#3498db")

    fig_e = go.Figure()
    fig_e.add_trace(go.Bar(
        x=skill_stats["premium"], y=skill_stats["skill_cat"],
        orientation="h", marker_color=skill_stats["color"],
        text=skill_stats.apply(lambda r: f"{r['premium']:+.1f}% (n={int(r['n'])})", axis=1),
        textposition="outside",
    ))
    fig_e.add_vline(x=0, line_color="gray", line_width=1)
    fig_e.update_layout(
        title=f"不同技能方向薪资溢价率（基准: {baseline:.1f}k/月）",
        xaxis_title="溢价率 (%)", yaxis_title="技能方向",
        height=400, showlegend=False,
    )
    st.plotly_chart(fig_e, use_container_width=True)

with col_f:
    st.markdown("## Panel F：技术方向需求量排行")
    cat_df = df_filtered.groupby("skill_cat").agg(
        n=("job_title", "count"), avg_sal=("salary_numeric", "mean")
    ).reset_index().sort_values("n")
    cat_df["pct"] = (cat_df["n"] / len(df_filtered) * 100).round(1)

    fig_f = px.bar(
        cat_df, x="n", y="skill_cat", orientation="h",
        title="各技能方向招聘岗位数量",
        labels={"n": "岗位数量", "skill_cat": "技能方向"},
        color="avg_sal", color_continuous_scale="Viridis",
        text=cat_df.apply(lambda r: f"{int(r['n'])} ({r['pct']}%) 均{r['avg_sal']:.1f}k", axis=1),
    )
    fig_f.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_f, use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════
# Panel G：经验壁垒双轴图
# ══════════════════════════════════════════════════════════
st.markdown("## Panel G：经验壁垒与应届生困境")
exp_order = ["无经验", "1-3年", "3-5年", "5-10年"]
df_exp = df_filtered[df_filtered["experience"].isin(exp_order)].copy()
if not df_exp.empty:
    stats = df_exp.groupby("experience").agg(
        n=("salary_numeric", "count"), avg_sal=("salary_numeric", "mean")
    ).reindex(exp_order).reset_index()
    stats["pct"] = (stats["n"] / stats["n"].sum() * 100).round(1)

    fig_g = make_subplots(specs=[[{"secondary_y": True}]])
    fig_g.add_trace(
        go.Bar(x=stats["experience"], y=stats["pct"], name="岗位占比 (%)",
               marker_color=["#3498db" if e == "无经验" else "#e74c3c" for e in stats["experience"]],
               text=stats["pct"].apply(lambda v: f"{v:.1f}%"), textposition="outside"),
        secondary_y=False,
    )
    fig_g.add_trace(
        go.Scatter(x=stats["experience"], y=stats["avg_sal"], name="平均月薪 (k)",
                   mode="lines+markers", marker_size=12, line_color="#2ecc71",
                   text=stats["avg_sal"].apply(lambda v: f"{v:.1f}k"), textposition="top center"),
        secondary_y=True,
    )
    fig_g.update_xaxes(title_text="工作年限要求")
    fig_g.update_yaxes(title_text="岗位占比 (%)", secondary_y=False)
    fig_g.update_yaxes(title_text="平均月薪 (k/月)", secondary_y=True)
    fig_g.update_layout(title="招聘经验需求结构与薪资水平", height=450)
    st.plotly_chart(fig_g, use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════
# Panel H：学历 - 经验热力图
# ══════════════════════════════════════════════════════════
st.markdown("## Panel H：学历 - 工作经验联合薪资热力图")
edu_order = ["大专", "本科", "硕士", "博士"]
df_sub = df_filtered[df_filtered["education"].isin(edu_order) & df_filtered["experience"].isin(exp_order)].copy()
if not df_sub.empty:
    pivot = df_sub.pivot_table(values="salary_numeric", index="education",
                               columns="experience", aggfunc="mean").reindex(index=edu_order, columns=exp_order)
    count_pivot = df_sub.pivot_table(values="salary_numeric", index="education",
                                     columns="experience", aggfunc="count").reindex(index=edu_order, columns=exp_order)
    pivot_display = pivot.copy()
    for i in pivot.index:
        for j in pivot.columns:
            if not pd.isna(pivot.loc[i, j]):
                pivot_display.loc[i, j] = f"{pivot.loc[i, j]:.1f}k (n={int(count_pivot.loc[i, j])})"
            else:
                pivot_display.loc[i, j] = "—"

    fig_h = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="YlOrRd",
        text=pivot_display.values,
        texttemplate="%{text}",
        hovertemplate="学历: %{y}<br>经验: %{x}<br>%{text}<extra></extra>",
        colorbar=dict(title="月薪(k)"),
    ))
    fig_h.update_layout(
        title="学历 - 经验联合薪资热力图（单元格: 均薪/样本量）",
        xaxis_title="工作年限要求", yaxis_title="学历要求",
        height=400,
    )
    st.plotly_chart(fig_h, use_container_width=True)

st.markdown("---")
st.caption("📌 数据看板基于招聘平台公开数据 | 由 Streamlit + Plotly 驱动")
