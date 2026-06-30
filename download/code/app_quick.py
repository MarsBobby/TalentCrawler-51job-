# ══════════════════════════════════════════════════════════════
# app_quick.py — 快速版数据看板（直接展示已生成的 PNG）
# 运行方式：streamlit run app_quick.py
# ══════════════════════════════════════════════════════════════
import streamlit as st
import os
from PIL import Image

st.set_page_config(
    page_title="招聘市场多维可视化看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 标题区 ──────────────────────────────────────────────────
st.markdown("# 📊 招聘市场多维可视化看板")
st.markdown("### 高等教育与培训体系改革支撑分析")
st.markdown("---")

# ── 侧边栏：项目背景 ──────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 政策核心论点")
    st.markdown("""
    ① **淘汰过时技术栈**，跟进前沿技术演进  
    ② **高校导入 ML/BI 实践课程**  
    ③ **缩短毕业生→企业转换时间**  
    ④ **提升毕业生初期人力资本存量**  
    ⑤ **减少结构性失业**
    """)
    st.markdown("---")
    st.markdown("### 🔧 操作说明")
    if st.button("🔄 刷新页面"):
        st.rerun()

# ── Panel 定义 ─────────────────────────────────────────────
PANELS = [
    ("Panel A", "./images/panel_a_education_salary_boxplot.png", "学历门槛 - 薪资分布箱线图", "展示不同学历要求下的薪资分布，中位数随学历提升而上升"),
    ("Panel B", "./images/panel_b_city_demand_barchart.png", "城市招聘需求量柱状图", "核心城市招聘规模对比，一线城市需求集中"),
    ("Panel C", "./images/panel_c_experience_salary_lineplot.png", "经验 - 均薪趋势折线", "工作经验积累与平均月薪变动趋势"),
    ("Panel D", "./images/panel_d_city_avg_salary.png", "城市平均薪资对比", "一线高薪虹吸效应，全样本均值参考线"),
    ("Panel E", "./images/panel_e_skill_salary_premium.png", "技能方向薪资溢价率", "AI/算法溢价显著，论证淘汰过时技术栈"),
    ("Panel F", "./images/panel_f_tech_job_demand.png", "技术方向需求量排行", "前沿技术岗需求主导市场"),
    ("Panel G", "./images/panel_g_experience_barrier.png", "经验壁垒双轴图", "应届生就业壁垒分析"),
    ("Panel H", "./images/panel_h_edu_exp_heatmap.png", "学历 - 经验热力图", "复合效应印证人力资本回报价值"),
]

# ── 检查 PNG 是否存在 ─────────────────────────────────────
missing = [p[1] for p in PANELS if not os.path.exists(p[1])]
if missing:
    st.warning(f"⚠️ 以下图片尚未生成，请先运行 `python step3_visualize.py`：\n" + "\n".join(f"- {f}" for f in missing))

# ── 两列布局展示图表 ──────────────────────────────────────
for i in range(0, len(PANELS), 2):
    cols = st.columns(2)
    for j, (panel_id, fname, title, desc) in enumerate(PANELS[i:i+2]):
        with cols[j]:
            st.markdown(f"### {panel_id}：{title}")
            st.caption(desc)
            if os.path.exists(fname):
                img = Image.open(fname)
                st.image(img, use_container_width=True)
            else:
                st.info(f"等待生成: {fname}")
            st.markdown("---")

