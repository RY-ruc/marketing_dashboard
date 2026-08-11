"""마케팅 캠페인 Streamlit 대시보드."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import data as d

# --- 팔레트 (dataviz 스킬 검증 팔레트 참고, 흰 배경 대비 가독성 위주) -----
CAT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
BLUE_SEQ = {450: "#2a78d6", 350: "#5598e7", 250: "#86b6ef", 150: "#b7d3f6"}
INK_MUTED = "#898781"
GRIDLINE = "#e5e4de"
SURFACE = "#ffffff"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}

# 흰 바탕에서 "낮음=흰색에 수렴, 높음=진한 블루"로 읽히는 순차(sequential) 히트맵 스케일
HEATMAP_SCALE = [
    [0.0, "#ffffff"],
    [0.15, "#dbe9fb"],
    [0.35, "#9ec5f4"],
    [0.55, "#5598e7"],
    [0.78, "#2a78d6"],
    [1.0, "#0d366b"],
]

RELEVANCE_ORDER = ["정확 일치", "관련", "느슨함", "무관"]
RELEVANCE_COLOR = {"정확 일치": BLUE_SEQ[450], "관련": BLUE_SEQ[350], "느슨함": BLUE_SEQ[250], "무관": BLUE_SEQ[150]}
WEEKDAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]

st.set_page_config(page_title="마케팅 캠페인 대시보드", layout="wide")


# --- 캐시된 데이터 로더 (UI 캐싱은 여기서, 순수 파싱 로직은 src/data.py) ----
@st.cache_data
def get_campaign_daily() -> pd.DataFrame:
    return d.load_campaign_daily()


@st.cache_data
def get_ad_groups() -> pd.DataFrame:
    return d.load_ad_groups()


@st.cache_data
def get_keywords() -> pd.DataFrame:
    return d.load_keywords()


@st.cache_data
def get_search_terms() -> pd.DataFrame:
    return d.load_search_terms()


@st.cache_data
def get_device_hour() -> tuple[pd.DataFrame, pd.DataFrame]:
    return d.load_device_hour()


@st.cache_data
def get_placements() -> pd.DataFrame:
    return d.load_placements()


def fmt_int(x) -> str:
    return "-" if pd.isna(x) else f"{x:,.0f}"


def fmt_won(x) -> str:
    return "-" if pd.isna(x) else f"{x:,.0f}원"


def fmt_pct(x) -> str:
    return "-" if pd.isna(x) else f"{x:.2f}%"


def base_layout(fig: go.Figure, y_title: str = "") -> go.Figure:
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        font=dict(color="#0b0b0b"),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, linecolor=GRIDLINE)
    fig.update_yaxes(showgrid=True, gridcolor=GRIDLINE, title=y_title, zeroline=False)
    return fig


# --- 데이터 로드 -------------------------------------------------------
daily = get_campaign_daily()
ad_groups = get_ad_groups()
keywords = get_keywords()
search_terms = get_search_terms()
device_df, hour_df = get_device_hour()
placements = get_placements()

st.title("📊 마케팅 캠페인 대시보드")

# --- 사이드바: 기간 필터 ------------------------------------------------
daily_wk = d.add_week_columns(daily)  # week_start / week_no / week_label 부여
min_date, max_date = daily["date"].min().date(), daily["date"].max().date()

st.sidebar.subheader("기간 필터")
filter_mode = st.sidebar.radio("조회 방식", ["날짜 범위 직접 선택", "주 단위 선택"], index=0)

if filter_mode == "날짜 범위 직접 선택":
    date_range = st.sidebar.date_input(
        "기간 선택", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    else:
        start, end = pd.Timestamp(min_date), pd.Timestamp(max_date)
else:
    week_options = daily_wk[["week_no", "week_label", "week_start"]].drop_duplicates().sort_values("week_no")
    selected_label = st.sidebar.selectbox("주 선택", week_options["week_label"], index=len(week_options) - 1)
    cumulative = st.sidebar.checkbox("선택 주까지 누계로 보기 (QTD 방식)", value=True)
    sel_week_start = week_options.loc[week_options["week_label"] == selected_label, "week_start"].iloc[0]
    sel_week_end = sel_week_start + pd.Timedelta(days=6)
    if cumulative:
        start, end = pd.Timestamp(min_date), sel_week_end
    else:
        start, end = sel_week_start, sel_week_end

daily_f = daily[(daily["date"] >= start) & (daily["date"] <= end)]
daily_f_wk = daily_wk[(daily_wk["date"] >= start) & (daily_wk["date"] <= end)]
st.sidebar.caption(f"{len(daily_f)}일 데이터 선택됨 (전체 {len(daily)}일) · {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")

tab_overview, tab_adgroup, tab_search, tab_device = st.tabs(
    ["개요", "광고그룹 · 키워드", "검색어", "기기 · 시간대"]
)

# =========================================================================
# 1) 개요
# =========================================================================
with tab_overview:
    impressions = daily_f["impressions"].sum()
    clicks = daily_f["clicks"].sum()
    cost = daily_f["cost"].sum()
    conversions = daily_f["conversions"].sum()
    ctr = d.weighted_ctr(daily_f)
    conv_rate = d.weighted_conv_rate(daily_f)
    cpa = d.cost_per_conversion(daily_f)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("노출수", fmt_int(impressions))
    c2.metric("클릭수", fmt_int(clicks))
    c3.metric("CTR", fmt_pct(ctr))
    c4.metric("비용", fmt_won(cost))

    c5, c6, c7 = st.columns(3)
    c5.metric("구독 신청(전환)", fmt_int(conversions))
    c6.metric("전환율", fmt_pct(conv_rate))
    c7.metric("전환당 비용", fmt_won(cpa) if pd.notna(cpa) else "-")

    st.divider()

    metric_labels = {
        "impressions": "노출수",
        "clicks": "클릭수",
        "ctr": "CTR (%)",
        "cost": "비용 (원)",
        "conversions": "구독 신청",
        "conv_rate": "전환율 (%)",
    }
    metric_key = st.radio(
        "일별 추이 지표", list(metric_labels), format_func=lambda k: metric_labels[k], horizontal=True
    )

    fig = go.Figure(
        go.Scatter(
            x=daily_f["date"],
            y=daily_f[metric_key],
            mode="lines",
            line=dict(color=BLUE_SEQ[450], width=2, shape="spline", smoothing=0.3),
            fill="tozeroy",
            fillcolor="rgba(42,120,214,0.08)",
            hovertemplate="%{x|%Y-%m-%d}<br>" + metric_labels[metric_key] + ": %{y:,.2f}<extra></extra>",
        )
    )
    fig = base_layout(fig, y_title=metric_labels[metric_key])
    st.plotly_chart(fig, width='stretch')

    st.markdown(f"**요일 × 주차 히트맵** — {metric_labels[metric_key]}")
    pivot = (
        daily_f_wk.pivot_table(index="weekday", columns="week_label", values=metric_key, aggfunc="sum")
        .reindex(WEEKDAY_ORDER)
    )
    week_cols = daily_f_wk[["week_no", "week_label"]].drop_duplicates().sort_values("week_no")["week_label"]
    pivot = pivot.reindex(columns=week_cols)

    fig_heat = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale=HEATMAP_SCALE,
            xgap=3,
            ygap=3,
            hovertemplate="%{y} · %{x}<br>" + metric_labels[metric_key] + ": %{z:,.2f}<extra></extra>",
            colorbar=dict(title=metric_labels[metric_key], thickness=14),
        )
    )
    fig_heat.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        font=dict(color="#0b0b0b"),
    )
    fig_heat.update_xaxes(showgrid=False, side="top")
    fig_heat.update_yaxes(showgrid=False, autorange="reversed")
    st.plotly_chart(fig_heat, width='stretch')

    with st.expander("일별 원본 데이터 보기"):
        st.dataframe(
            daily_f.assign(
                ctr=daily_f["ctr"].map(fmt_pct),
                conv_rate=daily_f["conv_rate"].map(fmt_pct),
                cost=daily_f["cost"].map(fmt_won),
                avg_cpc=daily_f["avg_cpc"].map(fmt_won),
                cost_per_conv=daily_f["cost_per_conv"].map(fmt_won),
            ),
            width='stretch',
            hide_index=True,
        )

# =========================================================================
# 2) 광고그룹 · 키워드
# =========================================================================
with tab_adgroup:
    st.subheader("광고그룹 요약")
    st.dataframe(
        ad_groups.assign(
            ctr=ad_groups["ctr"].map(fmt_pct),
            avg_cpc=ad_groups["avg_cpc"].map(fmt_won),
            cost=ad_groups["cost"].map(fmt_won),
        ),
        width='stretch',
        hide_index=True,
    )

    st.subheader("키워드 성과")
    keywords_sorted = keywords.sort_values("cost", ascending=False)

    fig_kw = go.Figure(
        go.Bar(
            x=keywords_sorted["cost"],
            y=keywords_sorted["keyword"],
            orientation="h",
            marker_color=CAT[0],
            hovertemplate="%{y}<br>비용: %{x:,.0f}원<extra></extra>",
        )
    )
    fig_kw.update_yaxes(autorange="reversed")
    fig_kw = base_layout(fig_kw, y_title="")
    fig_kw.update_layout(title="키워드별 비용 순위")
    st.plotly_chart(fig_kw, width='stretch')

    st.markdown("**품질평가점수 vs CTR** (bubble 크기 = 비용)")
    relevance_order3 = ["평균 이상", "평균", "평균 미만"]
    color_map3 = {"평균 이상": BLUE_SEQ[450], "평균": BLUE_SEQ[250], "평균 미만": BLUE_SEQ[150]}
    fig_sc = go.Figure()
    for rel in relevance_order3:
        sub = keywords_sorted[keywords_sorted["ad_relevance"] == rel]
        if sub.empty:
            continue
        fig_sc.add_trace(
            go.Scatter(
                x=sub["quality_score"],
                y=sub["ctr"],
                mode="markers",
                name=rel,
                marker=dict(size=(sub["cost"] / sub["cost"].max() * 40 + 10), color=color_map3[rel]),
                text=sub["keyword"],
                hovertemplate="%{text}<br>품질평가점수: %{x}<br>CTR: %{y:.2f}%<extra>" + rel + "</extra>",
            )
        )
    fig_sc = base_layout(fig_sc, y_title="CTR (%)")
    fig_sc.update_xaxes(title="품질평가점수")
    fig_sc.update_layout(legend_title_text="광고 관련성")
    st.plotly_chart(fig_sc, width='stretch')

    with st.expander("키워드 원본 데이터 보기"):
        st.dataframe(
            keywords_sorted.assign(
                ctr=keywords_sorted["ctr"].map(fmt_pct),
                avg_cpc=keywords_sorted["avg_cpc"].map(fmt_won),
                cost=keywords_sorted["cost"].map(fmt_won),
                cost_per_conv=keywords_sorted["cost_per_conv"].map(fmt_won),
            ),
            width='stretch',
            hide_index=True,
        )

# =========================================================================
# 3) 검색어
# =========================================================================
with tab_search:
    st.subheader("검색어 관련도 분포")
    rel_summary = (
        search_terms.groupby("relevance")[["impressions", "clicks", "cost", "conversions"]]
        .sum()
        .reindex(RELEVANCE_ORDER)
        .dropna(how="all")
        .reset_index()
    )

    c1, c2 = st.columns(2)
    with c1:
        fig_cnt = go.Figure(
            go.Bar(
                x=rel_summary["relevance"],
                y=search_terms["relevance"].value_counts().reindex(rel_summary["relevance"]).values,
                marker_color=[RELEVANCE_COLOR[r] for r in rel_summary["relevance"]],
                hovertemplate="%{x}<br>검색어 수: %{y}<extra></extra>",
            )
        )
        fig_cnt = base_layout(fig_cnt, y_title="검색어 수")
        fig_cnt.update_layout(title="관련도별 검색어 수")
        st.plotly_chart(fig_cnt, width='stretch')

    with c2:
        fig_cost = go.Figure(
            go.Bar(
                x=rel_summary["relevance"],
                y=rel_summary["cost"],
                marker_color=[RELEVANCE_COLOR[r] for r in rel_summary["relevance"]],
                hovertemplate="%{x}<br>비용: %{y:,.0f}원<extra></extra>",
            )
        )
        fig_cost = base_layout(fig_cost, y_title="비용 (원)")
        fig_cost.update_layout(title="관련도별 비용")
        st.plotly_chart(fig_cost, width='stretch')

    st.subheader("저성과 검색어 (관련도 낮음 + 전환 없음)")
    underperforming = search_terms[
        search_terms["relevance"].isin(["느슨함", "무관"]) & (search_terms["conversions"] == 0)
    ].sort_values("cost", ascending=False)

    if underperforming.empty:
        st.success("조건에 해당하는 저성과 검색어가 없습니다.")
    else:
        st.warning(f"⚠️ 관련도가 낮고 전환이 없는 검색어 {len(underperforming)}건 — 제외 키워드 후보로 검토하세요.")
        st.dataframe(
            underperforming.assign(
                ctr=underperforming["ctr"].map(fmt_pct),
                cost=underperforming["cost"].map(fmt_won),
            )[["search_term", "relevance", "matched_keyword", "impressions", "clicks", "ctr", "cost"]],
            width='stretch',
            hide_index=True,
        )

    with st.expander("검색어 전체 데이터 보기 (비용 순)"):
        st.dataframe(
            search_terms.sort_values("cost", ascending=False).assign(
                ctr=search_terms["ctr"].map(fmt_pct),
                cost=search_terms["cost"].map(fmt_won),
                cost_per_conv=search_terms["cost_per_conv"].map(fmt_won),
            ),
            width='stretch',
            hide_index=True,
        )

# =========================================================================
# 4) 기기 · 시간대
# =========================================================================
with tab_device:
    metric_labels2 = {
        "impressions": "노출수",
        "clicks": "클릭수",
        "cost": "비용 (원)",
        "conversions": "구독 신청",
        "ctr": "CTR (%)",
    }
    metric_key2 = st.radio(
        "비교 지표", list(metric_labels2), format_func=lambda k: metric_labels2[k], horizontal=True, key="dev_metric"
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("기기별 성과")
        fig_dev = go.Figure(
            go.Bar(
                x=device_df["device"],
                y=device_df[metric_key2],
                marker_color=CAT[: len(device_df)],
                hovertemplate="%{x}<br>" + metric_labels2[metric_key2] + ": %{y:,.2f}<extra></extra>",
            )
        )
        fig_dev = base_layout(fig_dev, y_title=metric_labels2[metric_key2])
        st.plotly_chart(fig_dev, width='stretch')

    with c2:
        st.subheader("시간대별 성과 (히트맵)")
        fig_hr = go.Figure(
            go.Heatmap(
                z=[hour_df[metric_key2].values],
                x=hour_df["hour"],
                y=[metric_labels2[metric_key2]],
                colorscale=HEATMAP_SCALE,
                xgap=2,
                ygap=2,
                hovertemplate="%{x}<br>" + metric_labels2[metric_key2] + ": %{z:,.2f}<extra></extra>",
                colorbar=dict(title=metric_labels2[metric_key2], thickness=14),
            )
        )
        fig_hr.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            plot_bgcolor=SURFACE,
            paper_bgcolor=SURFACE,
            font=dict(color="#0b0b0b"),
            height=180,
        )
        fig_hr.update_xaxes(title="시간대", showgrid=False)
        fig_hr.update_yaxes(showgrid=False, showticklabels=False)
        st.plotly_chart(fig_hr, width='stretch')

    st.subheader("게재위치")
    if placements.empty:
        st.info("게재위치 데이터가 아직 없습니다 (`raw/placements.csv`가 비어 있음).")
    else:
        st.dataframe(
            placements.assign(
                ctr=placements["ctr"].map(fmt_pct),
                cost=placements["cost"].map(fmt_won),
            ),
            width='stretch',
            hide_index=True,
        )
