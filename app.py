"""마케팅 캠페인 Streamlit 대시보드.

의사결정 단위로 구성한 3개 페이지:
  1. 판정 — 이 캠페인이 돈을 벌고 있나? (ROAS / CPA / 손익분기 구독가치)
  2. 낭비 — 전환 0건인 곳에 얼마를 쓰고 있나? (제외·중단 후보)
  3. 승자 — 무엇이 작동하고 있나? (예산 재배치 대상)

모든 페이지 상단에 효율 스트립(CVR·CPA·ROAS·낭비율)을 고정 노출한다.

일별 추이 라인차트는 제거했다. 원본 데이터상 비용이 30일 내내 36,000원으로 고정
(예산 상한, budget_exhausted 30/30일)이고 클릭 변동계수가 4.9%라 시간축에 신호가
거의 없기 때문. 대신 시간축에는 누적 CPA(효율 궤적)만 남기고, 실제 정보가 있는
세그먼트 축(기기·검색어 관련도·키워드)을 전면에 배치했다.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import data as d

# --- 팔레트 (dataviz 스킬 검증 팔레트, 흰 배경 대비 가독성 위주) ----------
CAT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
BLUE_SEQ = {450: "#2a78d6", 350: "#5598e7", 250: "#86b6ef", 150: "#b7d3f6"}
INK_MUTED = "#898781"
GRIDLINE = "#e5e4de"
SURFACE = "#ffffff"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}

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
LOW_RELEVANCE = ["느슨함", "무관"]

# 세그먼트 CSV(키워드/검색어/기기)에는 날짜 축이 없어 기간 필터가 적용되지 않는다.
SEGMENT_PERIOD_NOTE = "원본 CSV에 날짜 축이 없어 **전체 기간 집계**입니다 — 상단 기간 필터와 무관합니다."

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


def verdict_color(ok: bool) -> str:
    return STATUS["good"] if ok else STATUS["critical"]


def stat_card(label: str, value: str, note: str, note_color: str = INK_MUTED, value_color: str = "#0b0b0b") -> str:
    return f"""
    <div style="border:1px solid {GRIDLINE};border-radius:12px;padding:14px 16px;background:{SURFACE};height:100%;">
      <div style="color:{INK_MUTED};font-size:0.8rem;font-weight:600;">{label}</div>
      <div style="font-size:1.7rem;font-weight:800;color:{value_color};line-height:1.15;margin-top:4px;">{value}</div>
      <div style="color:{note_color};font-size:0.75rem;margin-top:5px;">{note}</div>
    </div>
    """


def banner(kind: str, title: str, body: str) -> str:
    """kind: 'critical' | 'good' | 'warning'"""
    color = STATUS[kind if kind != "critical" else "critical"]
    tint = {"critical": "#fdf2f2", "good": "#f1faf1", "warning": "#fff9ec"}[kind]
    return f"""
    <div style="border:1px solid {color};background:{tint};border-radius:12px;padding:16px 20px;">
      <div style="color:{color};font-size:0.8rem;font-weight:700;letter-spacing:0.02em;">{title}</div>
      <div style="font-size:1.35rem;font-weight:800;color:#0b0b0b;line-height:1.35;margin-top:6px;">{body}</div>
    </div>
    """


def base_layout(fig: go.Figure, y_title: str = "") -> go.Figure:
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        font=dict(color="#0b0b0b"),
        hovermode="closest",
    )
    fig.update_xaxes(showgrid=False, linecolor=GRIDLINE)
    fig.update_yaxes(showgrid=True, gridcolor=GRIDLINE, title=y_title, zeroline=False)
    return fig


def waste_bar_chart(labels, values, note_texts, title: str) -> go.Figure:
    """낭비 금액 랭킹 — 금액 크기순 가로 막대. 색은 심각도(상위 = 진한 적색)."""
    max_v = max(values) if len(values) else 1
    colors = [STATUS["critical"] if v >= max_v * 0.5 else STATUS["serious"] for v in values]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{v:,.0f}원" for v in values],
            textposition="outside",
            customdata=note_texts,
            hovertemplate="%{y}<br>%{x:,.0f}원<br>%{customdata}<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig = base_layout(fig)
    fig.update_layout(title=title, xaxis_title="비용 (원)", height=90 + 46 * len(labels))
    fig.update_xaxes(range=[0, max_v * 1.25])
    return fig


# --- 데이터 로드 -------------------------------------------------------
daily = get_campaign_daily()
ad_groups = get_ad_groups()
keywords = get_keywords()
search_terms = get_search_terms()
device_df, hour_df = get_device_hour()
placements = get_placements()

st.title("마케팅 캠페인 대시보드")

# =========================================================================
# 사이드바 — 기간 + 판정 기준(구독 가치 / 목표 CPA)
# =========================================================================
daily_wk = d.add_week_columns(daily)
min_date, max_date = daily["date"].min().date(), daily["date"].max().date()

st.sidebar.subheader("판정 기준")
value_per_conv = st.sidebar.number_input(
    "구독 1건당 가치 (원)",
    min_value=0,
    value=50_000,
    step=10_000,
    help="원본 CSV에 매출 컬럼이 없어 ROAS의 분자를 직접 입력받습니다. 구독 1건의 LTV 또는 예상 매출을 넣으세요.",
)
target_cpa = st.sidebar.number_input("목표 전환당비용 (원)", min_value=0, value=50_000, step=10_000)
target_cvr = st.sidebar.number_input("목표 클릭당 전환율 (%)", min_value=0.0, value=2.0, step=0.1)

st.sidebar.divider()
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
    start, end = (pd.Timestamp(min_date), sel_week_end) if cumulative else (sel_week_start, sel_week_end)

daily_f = daily[(daily["date"] >= start) & (daily["date"] <= end)]
daily_f_wk = daily_wk[(daily_wk["date"] >= start) & (daily_wk["date"] <= end)]
st.sidebar.caption(f"{len(daily_f)}일 선택 · {start:%Y-%m-%d} ~ {end:%Y-%m-%d}")

# --- 핵심 지표 계산 ------------------------------------------------------
impressions = daily_f["impressions"].sum()
clicks = daily_f["clicks"].sum()
cost = daily_f["cost"].sum()
conversions = daily_f["conversions"].sum()
ctr = d.weighted_ctr(daily_f)
cvr = d.weighted_conv_rate(daily_f)
cpa = d.cost_per_conversion(daily_f)
current_roas = d.roas(conversions, cost, value_per_conv)
breakeven = d.breakeven_value_per_conversion(cost, conversions)

# 낭비 = 관련도 낮은 검색어 중 전환 0건 (전체 기간 기준)
waste_terms = search_terms[search_terms["relevance"].isin(LOW_RELEVANCE) & (search_terms["conversions"] == 0)]
waste_cost = waste_terms["cost"].sum()
waste_ratio = waste_cost / search_terms["cost"].sum() * 100 if search_terms["cost"].sum() else 0.0

# =========================================================================
# 모든 페이지 상단 고정 — 효율 스트립
# =========================================================================
st.caption(f"조회 기간 {start:%Y-%m-%d} ~ {end:%Y-%m-%d} ({len(daily_f)}일) · 집행 {fmt_won(cost)} · 전환 {fmt_int(conversions)}건")

e1, e2, e3, e4 = st.columns(4)
with e1:
    cvr_ok = cvr >= target_cvr
    gap = f"목표 {target_cvr:.1f}% 대비 {((cvr - target_cvr) / target_cvr * 100):+.0f}%" if target_cvr else "목표 미설정"
    st.markdown(stat_card("클릭당 전환율 (CVR)", fmt_pct(cvr), gap, verdict_color(cvr_ok)), unsafe_allow_html=True)
with e2:
    cpa_ok = pd.notna(cpa) and cpa <= target_cpa
    if pd.isna(cpa):
        note, note_c = "전환 0건 — 산출 불가", STATUS["critical"]
    else:
        note, note_c = f"목표 {target_cpa:,.0f}원 대비 {cpa / target_cpa:.1f}배", verdict_color(cpa_ok)
    st.markdown(stat_card("전환당 비용 (CPA)", fmt_won(cpa), note, note_c), unsafe_allow_html=True)
with e3:
    roas_ok = pd.notna(current_roas) and current_roas >= 1
    if pd.isna(current_roas) or current_roas == 0:
        note, note_c = "전환 0건 — 매출 없음", STATUS["critical"]
    else:
        note, note_c = ("손익분기 1.0 " + ("달성" if roas_ok else "미달")), verdict_color(roas_ok)
    st.markdown(
        stat_card("ROAS", f"{current_roas:.2f}" if pd.notna(current_roas) else "-", note, note_c,
                  value_color=verdict_color(roas_ok)),
        unsafe_allow_html=True,
    )
with e4:
    st.markdown(
        stat_card("낭비 비중", f"{waste_ratio:.1f}%", f"{fmt_won(waste_cost)} · 전환 0건", STATUS["critical"]),
        unsafe_allow_html=True,
    )
st.caption("낭비 비중은 관련도가 낮고(무관·느슨함) 전환이 0건인 검색어 기준 · 전체 기간 집계")

st.divider()

tab_verdict, tab_waste, tab_winner = st.tabs(["① 돈 벌고 있나", "② 어디서 새나", "③ 뭘 키울까"])

# =========================================================================
# ① 판정
# =========================================================================
with tab_verdict:
    if conversions == 0:
        st.markdown(
            banner("critical", "판정", f"이 기간 전환 0건 — {fmt_won(cost)} 전액이 성과 없이 집행됐습니다"),
            unsafe_allow_html=True,
        )
    elif current_roas >= 1:
        st.markdown(
            banner("good", "판정", f"흑자 — ROAS {current_roas:.2f}, 구독 1건이 {fmt_won(breakeven)}보다 가치 있으면 이익"),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            banner("critical", "판정", f"적자 — 구독 1건 가치가 {fmt_won(breakeven)} 미만이면 손해입니다"),
            unsafe_allow_html=True,
        )

    st.write("")
    v1, v2, v3 = st.columns(3)
    with v1:
        st.markdown(
            stat_card("손익분기 구독가치", fmt_won(breakeven), f"현재 입력값 {value_per_conv:,.0f}원",
                      verdict_color(value_per_conv >= breakeven) if pd.notna(breakeven) else INK_MUTED),
            unsafe_allow_html=True,
        )
    with v2:
        revenue = conversions * value_per_conv
        profit = revenue - cost
        st.markdown(
            stat_card("추정 손익", fmt_won(profit), f"매출 {fmt_won(revenue)} − 비용 {fmt_won(cost)}",
                      verdict_color(profit >= 0)),
            unsafe_allow_html=True,
        )
    with v3:
        need_conv = cost / value_per_conv if value_per_conv else float("nan")
        short = need_conv - conversions if pd.notna(need_conv) else float("nan")
        st.markdown(
            stat_card("손익분기 필요 전환", f"{need_conv:,.1f}건" if pd.notna(need_conv) else "-",
                      f"현재 {fmt_int(conversions)}건 · {short:+,.1f}건" if pd.notna(short) else "구독 가치 입력 필요",
                      verdict_color(pd.notna(short) and short <= 0)),
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown("#### 효율 궤적 — 누적 전환당비용")
    st.caption("일별 추이 대신 누적 CPA를 본다. 비용이 매일 예산 상한(36,000원)에 고정돼 일별 라인은 정보가 없기 때문.")

    cum = daily_f.copy()
    cum["cum_cpa"] = d.cumulative_cpa(cum)
    fig_cpa = go.Figure()
    fig_cpa.add_trace(
        go.Scatter(
            x=cum["date"],
            y=cum["cum_cpa"],
            mode="lines+markers",
            line=dict(color=BLUE_SEQ[450], width=2),
            marker=dict(size=6),
            name="누적 CPA",
            hovertemplate="%{x|%Y-%m-%d}<br>누적 CPA: %{y:,.0f}원<extra></extra>",
        )
    )
    if target_cpa:
        fig_cpa.add_hline(
            y=target_cpa,
            line=dict(color=STATUS["good"], width=2, dash="dash"),
            annotation_text=f"목표 {target_cpa:,.0f}원",
            annotation_position="top left",
        )
    conv_days = cum[cum["conversions"] > 0]
    if not conv_days.empty:
        fig_cpa.add_trace(
            go.Scatter(
                x=conv_days["date"],
                y=conv_days["cum_cpa"],
                mode="markers",
                marker=dict(size=13, color=STATUS["good"], symbol="star"),
                name="전환 발생일",
                hovertemplate="%{x|%Y-%m-%d}<br>전환 발생<extra></extra>",
            )
        )
    fig_cpa = base_layout(fig_cpa, y_title="누적 CPA (원)")
    st.plotly_chart(fig_cpa, width="stretch")

    st.markdown("#### 요일 × 주차 히트맵")
    hm_labels = {"conversions": "구독 신청", "clicks": "클릭수", "impressions": "노출수", "cost": "비용 (원)", "ctr": "CTR (%)"}
    hm_key = st.radio("지표", list(hm_labels), format_func=lambda k: hm_labels[k], horizontal=True, key="hm_metric")
    pivot = daily_f_wk.pivot_table(index="weekday", columns="week_label", values=hm_key, aggfunc="sum").reindex(WEEKDAY_ORDER)
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
            hovertemplate="%{y} · %{x}<br>" + hm_labels[hm_key] + ": %{z:,.2f}<extra></extra>",
            colorbar=dict(title=hm_labels[hm_key], thickness=14),
        )
    )
    fig_heat.update_layout(margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font=dict(color="#0b0b0b"))
    fig_heat.update_xaxes(showgrid=False, side="top")
    fig_heat.update_yaxes(showgrid=False, autorange="reversed")
    st.plotly_chart(fig_heat, width="stretch")

    with st.expander("일별 원본 데이터"):
        st.dataframe(
            daily_f.assign(
                ctr=daily_f["ctr"].map(fmt_pct),
                conv_rate=daily_f["conv_rate"].map(fmt_pct),
                cost=daily_f["cost"].map(fmt_won),
                avg_cpc=daily_f["avg_cpc"].map(fmt_won),
                cost_per_conv=daily_f["cost_per_conv"].map(fmt_won),
            ),
            width="stretch",
            hide_index=True,
        )

# =========================================================================
# ② 낭비
# =========================================================================
with tab_waste:
    st.info(SEGMENT_PERIOD_NOTE)

    axis = st.radio(
        "낭비를 어느 축으로 볼까요?",
        ["검색어 관련도", "기기", "키워드", "시간대"],
        horizontal=True,
        key="waste_axis",
    )
    st.caption("축마다 같은 돈을 다르게 자른 것입니다 — 축 간 금액을 더하지 마세요.")

    if axis == "검색어 관련도":
        zero_terms = d.zero_conversion_segments(search_terms)
        low = zero_terms[zero_terms["relevance"].isin(LOW_RELEVANCE)]
        by_rel = low.groupby("relevance").agg(비용=("cost", "sum"), 검색어수=("search_term", "count"), 클릭=("clicks", "sum"))
        by_rel = by_rel.sort_values("비용", ascending=False)

        if by_rel.empty:
            st.success("관련도가 낮으면서 전환이 0건인 검색어가 없습니다.")
        else:
            st.markdown(
                banner("critical", "제외 키워드 후보",
                       f"{fmt_won(by_rel['비용'].sum())} 집행 · 전환 0건 · 검색어 {int(by_rel['검색어수'].sum())}개"),
                unsafe_allow_html=True,
            )
            st.write("")
            st.plotly_chart(
                waste_bar_chart(
                    list(by_rel.index),
                    list(by_rel["비용"]),
                    [f"검색어 {int(n)}개 · 클릭 {int(c)}" for n, c in zip(by_rel["검색어수"], by_rel["클릭"])],
                    "관련도별 낭비 금액",
                ),
                width="stretch",
            )
            st.markdown("**낭비 금액 상위 검색어**")
            st.dataframe(
                low.head(20).assign(ctr=low.head(20)["ctr"].map(fmt_pct), cost=low.head(20)["cost"].map(fmt_won))[
                    ["search_term", "relevance", "matched_keyword", "impressions", "clicks", "ctr", "cost"]
                ],
                width="stretch",
                hide_index=True,
            )

    elif axis == "기기":
        zero_dev = d.zero_conversion_segments(device_df)
        conv_dev = device_df[device_df["conversions"] > 0]
        if zero_dev.empty:
            st.success("모든 기기에서 전환이 발생하고 있습니다.")
        else:
            st.markdown(
                banner("critical", "입찰 조정 후보",
                       f"{fmt_won(zero_dev['cost'].sum())} 집행 · 전환 0건 · 기기 {len(zero_dev)}종"),
                unsafe_allow_html=True,
            )
            st.write("")
            st.plotly_chart(
                waste_bar_chart(
                    list(zero_dev["device"]),
                    list(zero_dev["cost"]),
                    [f"클릭 {int(c)} · CTR {t:.2f}%" for c, t in zip(zero_dev["clicks"], zero_dev["ctr"])],
                    "전환 0건 기기의 집행 금액",
                ),
                width="stretch",
            )
        if not conv_dev.empty:
            st.markdown("**전환이 발생하는 기기**")
            for _, r in conv_dev.iterrows():
                dev_cvr = r["conversions"] / r["clicks"] * 100 if r["clicks"] else 0
                st.markdown(
                    stat_card(r["device"], fmt_pct(dev_cvr),
                              f"클릭 {fmt_int(r['clicks'])} · 전환 {fmt_int(r['conversions'])} · {fmt_won(r['cost'])}",
                              STATUS["good"]),
                    unsafe_allow_html=True,
                )
        st.write("")
        st.dataframe(
            device_df.assign(ctr=device_df["ctr"].map(fmt_pct), cost=device_df["cost"].map(fmt_won)),
            width="stretch",
            hide_index=True,
        )

    elif axis == "키워드":
        kw = keywords.copy()
        kw["cvr"] = kw["conversions"] / kw["clicks"].replace(0, pd.NA) * 100
        zero_kw = d.zero_conversion_segments(kw)
        if zero_kw.empty:
            st.success("전환이 0건인 키워드가 없습니다.")
        else:
            st.markdown(
                banner("critical", "일시중지 · 입찰 조정 후보",
                       f"{fmt_won(zero_kw['cost'].sum())} 집행 · 전환 0건 · 키워드 {len(zero_kw)}개"),
                unsafe_allow_html=True,
            )
            st.write("")
            st.plotly_chart(
                waste_bar_chart(
                    list(zero_kw["keyword"]),
                    list(zero_kw["cost"]),
                    [f"CTR {t:.2f}% · 품질점수 {q:.0f}" for t, q in zip(zero_kw["ctr"], zero_kw["quality_score"])],
                    "전환 0건 키워드의 집행 금액",
                ),
                width="stretch",
            )
        st.markdown("**품질평가점수 vs CTR** (버블 크기 = 비용, 빨강 = 전환 0건)")
        fig_sc = go.Figure()
        for has_conv, label, color in [(True, "전환 있음", STATUS["good"]), (False, "전환 0건", STATUS["critical"])]:
            sub = kw[(kw["conversions"] > 0) == has_conv]
            if sub.empty:
                continue
            fig_sc.add_trace(
                go.Scatter(
                    x=sub["quality_score"],
                    y=sub["ctr"],
                    mode="markers+text",
                    name=label,
                    marker=dict(size=(sub["cost"] / kw["cost"].max() * 45 + 12), color=color, opacity=0.75),
                    text=sub["keyword"],
                    textposition="top center",
                    textfont=dict(size=10),
                    hovertemplate="%{text}<br>품질점수 %{x} · CTR %{y:.2f}%<extra>" + label + "</extra>",
                )
            )
        fig_sc = base_layout(fig_sc, y_title="CTR (%)")
        fig_sc.update_xaxes(title="품질평가점수")
        st.plotly_chart(fig_sc, width="stretch")
        st.dataframe(
            kw.sort_values("cost", ascending=False).assign(
                ctr=kw.sort_values("cost", ascending=False)["ctr"].map(fmt_pct),
                cost=kw.sort_values("cost", ascending=False)["cost"].map(fmt_won),
                avg_cpc=kw.sort_values("cost", ascending=False)["avg_cpc"].map(fmt_won),
            )[["keyword", "quality_score", "ad_relevance", "impressions", "clicks", "ctr", "cost", "conversions"]],
            width="stretch",
            hide_index=True,
        )

    else:  # 시간대
        zero_hours = hour_df[hour_df["conversions"] == 0]
        st.markdown(
            banner("warning", "전환 0건 시간대",
                   f"{fmt_won(zero_hours['cost'].sum())} 집행 · {len(zero_hours)}개 시간대"),
            unsafe_allow_html=True,
        )
        st.write("")
        st.markdown("**시간대별 비용 히트맵** — 짙을수록 많이 씀")
        fig_hr_cost = go.Figure(
            go.Heatmap(
                z=[hour_df["cost"].values],
                x=hour_df["hour"],
                y=["비용"],
                colorscale=HEATMAP_SCALE,
                xgap=2,
                ygap=2,
                hovertemplate="%{x}<br>비용: %{z:,.0f}원<extra></extra>",
                colorbar=dict(title="비용", thickness=14),
            )
        )
        fig_hr_cost.update_layout(margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                                  font=dict(color="#0b0b0b"), height=170)
        fig_hr_cost.update_xaxes(title="시간대", showgrid=False)
        fig_hr_cost.update_yaxes(showgrid=False, showticklabels=False)
        st.plotly_chart(fig_hr_cost, width="stretch")

        hour_cvr = hour_df.copy()
        hour_cvr["cvr"] = hour_cvr["conversions"] / hour_cvr["clicks"].replace(0, pd.NA) * 100
        st.markdown("**시간대별 클릭당 전환율 히트맵** — 짙을수록 잘 전환됨")
        fig_hr_cvr = go.Figure(
            go.Heatmap(
                z=[hour_cvr["cvr"].values],
                x=hour_cvr["hour"],
                y=["CVR"],
                colorscale=HEATMAP_SCALE,
                xgap=2,
                ygap=2,
                hovertemplate="%{x}<br>CVR: %{z:.2f}%<extra></extra>",
                colorbar=dict(title="CVR (%)", thickness=14),
            )
        )
        fig_hr_cvr.update_layout(margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                                 font=dict(color="#0b0b0b"), height=170)
        fig_hr_cvr.update_xaxes(title="시간대", showgrid=False)
        fig_hr_cvr.update_yaxes(showgrid=False, showticklabels=False)
        st.plotly_chart(fig_hr_cvr, width="stretch")
        st.caption("두 히트맵의 색이 어긋나는 구간(비용은 짙은데 CVR은 옅음)이 예산을 빼야 할 시간대입니다.")

# =========================================================================
# ③ 승자
# =========================================================================
with tab_winner:
    st.info(SEGMENT_PERIOD_NOTE)

    win_terms = search_terms[search_terms["conversions"] > 0].sort_values("cost_per_conv")
    win_kw = keywords[keywords["conversions"] > 0].sort_values("cost", ascending=False)
    win_dev = device_df[device_df["conversions"] > 0]

    if win_terms.empty and win_kw.empty:
        st.markdown(banner("critical", "승자 없음", "전환을 만든 검색어·키워드가 없습니다"), unsafe_allow_html=True)
    else:
        best = win_terms.iloc[0] if not win_terms.empty else None
        if best is not None:
            st.markdown(
                banner("good", "예산 재배치 1순위",
                       f"검색어 「{best['search_term']}」 — 전환 {fmt_int(best['conversions'])}건 · CPA {fmt_won(best['cost_per_conv'])}"),
                unsafe_allow_html=True,
            )

    st.write("")
    st.markdown("#### 전환을 만든 검색어")
    if win_terms.empty:
        st.warning("전환을 만든 검색어가 없습니다.")
    else:
        cols = st.columns(min(len(win_terms), 3))
        for col, (_, r) in zip(cols, win_terms.iterrows()):
            with col:
                better = pd.notna(cpa) and r["cost_per_conv"] < cpa
                st.markdown(
                    stat_card(
                        r["search_term"],
                        fmt_won(r["cost_per_conv"]),
                        f"전환 {fmt_int(r['conversions'])}건 · {r['relevance']} · 전체 CPA 대비 {'우수' if better else '열위'}",
                        verdict_color(better),
                    ),
                    unsafe_allow_html=True,
                )
        st.write("")
        st.dataframe(
            win_terms.assign(
                ctr=win_terms["ctr"].map(fmt_pct),
                cost=win_terms["cost"].map(fmt_won),
                cost_per_conv=win_terms["cost_per_conv"].map(fmt_won),
            )[["search_term", "relevance", "matched_keyword", "clicks", "ctr", "cost", "conversions", "cost_per_conv"]],
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### 전환을 만든 키워드 · 기기")
    w1, w2 = st.columns(2)
    with w1:
        if win_kw.empty:
            st.warning("전환을 만든 키워드가 없습니다.")
        else:
            for _, r in win_kw.iterrows():
                share = r["cost"] / keywords["cost"].sum() * 100
                st.markdown(
                    stat_card(f"키워드 {r['keyword']}", fmt_int(r["conversions"]) + "건",
                              f"비용 비중 {share:.0f}% · CTR {r['ctr']:.2f}% · 품질점수 {r['quality_score']:.0f}",
                              STATUS["good"]),
                    unsafe_allow_html=True,
                )
    with w2:
        if win_dev.empty:
            st.warning("전환을 만든 기기가 없습니다.")
        else:
            for _, r in win_dev.iterrows():
                dev_cvr = r["conversions"] / r["clicks"] * 100 if r["clicks"] else 0
                st.markdown(
                    stat_card(f"기기 {r['device']}", fmt_pct(dev_cvr),
                              f"전환 {fmt_int(r['conversions'])}건 · {fmt_won(r['cost'])}", STATUS["good"]),
                    unsafe_allow_html=True,
                )

    st.markdown("#### 광고그룹 요약")
    for _, row in ad_groups.iterrows():
        with st.container(border=True):
            gc = st.columns(6)
            gc[0].markdown(
                f"**{row['ad_group']}**<br><span style='color:{INK_MUTED};font-size:0.8rem;'>키워드 {fmt_int(row['keyword_count'])}개</span>",
                unsafe_allow_html=True,
            )
            gc[1].metric("품질점수", f"{row['avg_quality_score']:.1f}")
            gc[2].metric("CTR", fmt_pct(row["ctr"]))
            gc[3].metric("평균 CPC", fmt_won(row["avg_cpc"]))
            gc[4].metric("비용", fmt_won(row["cost"]))
            gc[5].metric("구독 신청", fmt_int(row["conversions"]))

    if placements.empty:
        st.caption("게재위치 데이터는 아직 비어 있습니다 (`raw/placements.csv`).")
