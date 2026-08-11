"""raw/ CSV 로드 및 정제. Streamlit(st.*) 의존성 없는 순수 함수만 둔다."""

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"


def _read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / name, encoding="utf-8-sig")


def _to_percent(series: pd.Series) -> pd.Series:
    """'2.16%' -> 2.16 (float, percentage points 단위 유지)"""
    return pd.to_numeric(series.astype(str).str.rstrip("%"), errors="coerce")


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", ""), errors="coerce")


def _to_flag(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().eq("Y")


def load_campaign_daily() -> pd.DataFrame:
    df = _read_csv("campaign_daily.csv")
    df = df.rename(
        columns={
            "날짜": "date",
            "요일": "weekday",
            "노출수": "impressions",
            "클릭수": "clicks",
            "CTR": "ctr",
            "평균 CPC": "avg_cpc",
            "비용": "cost",
            "구독 신청": "conversions",
            "전환율": "conv_rate",
            "전환당비용": "cost_per_conv",
            "예산 소진": "budget_exhausted",
            "학습 기간": "learning_period",
        }
    )
    # 원본 마지막 행은 "합계"(총계) 행이라 날짜가 아님 -> 일별 시계열에서 제외
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()

    for col in ["impressions", "clicks", "avg_cpc", "cost", "conversions", "cost_per_conv"]:
        df[col] = _to_number(df[col])
    for col in ["ctr", "conv_rate"]:
        df[col] = _to_percent(df[col])
    for col in ["budget_exhausted", "learning_period"]:
        df[col] = _to_flag(df[col])

    return df.sort_values("date").reset_index(drop=True)


def load_ad_groups() -> pd.DataFrame:
    df = _read_csv("ad_groups.csv")
    df = df.rename(
        columns={
            "광고그룹": "ad_group",
            "키워드 수": "keyword_count",
            "평균 품질평가점수": "avg_quality_score",
            "노출수": "impressions",
            "클릭수": "clicks",
            "CTR": "ctr",
            "평균 CPC": "avg_cpc",
            "비용": "cost",
            "구독 신청": "conversions",
        }
    )
    for col in ["keyword_count", "avg_quality_score", "impressions", "clicks", "avg_cpc", "cost", "conversions"]:
        df[col] = _to_number(df[col])
    df["ctr"] = _to_percent(df["ctr"])
    return df


def load_keywords() -> pd.DataFrame:
    df = _read_csv("keywords.csv")
    df = df.rename(
        columns={
            "키워드": "keyword",
            "광고그룹": "ad_group",
            "검색유형": "match_type",
            "품질평가점수": "quality_score",
            "광고 관련성": "ad_relevance",
            "예상 CTR": "expected_ctr",
            "방문 페이지": "landing_page_exp",
            "노출수": "impressions",
            "클릭수": "clicks",
            "CTR": "ctr",
            "평균 CPC": "avg_cpc",
            "비용": "cost",
            "구독 신청": "conversions",
            "고객 아님": "not_customer",
        }
    )
    for col in ["quality_score", "impressions", "clicks", "avg_cpc", "cost", "conversions"]:
        df[col] = _to_number(df[col])
    df["ctr"] = _to_percent(df["ctr"])
    df["cost_per_conv"] = df["cost"] / df["conversions"].replace(0, pd.NA)
    return df


def load_search_terms() -> pd.DataFrame:
    df = _read_csv("search_terms.csv")
    df = df.rename(
        columns={
            "검색어": "search_term",
            "관련도": "relevance",
            "일치 키워드": "matched_keyword",
            "광고그룹": "ad_group",
            "검색유형": "match_type",
            "노출수": "impressions",
            "클릭수": "clicks",
            "CTR": "ctr",
            "비용": "cost",
            "구독 신청": "conversions",
            "전환당비용": "cost_per_conv",
        }
    )
    for col in ["impressions", "clicks", "cost", "conversions", "cost_per_conv"]:
        df[col] = _to_number(df[col])
    df["ctr"] = _to_percent(df["ctr"])
    return df


def load_device_hour() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(기기별 성과, 시간대별 성과) 튜플 반환. 원본은 한 파일에 두 그레인이 union되어 있음."""
    df = _read_csv("device_hour.csv")
    df = df.rename(
        columns={
            "구분": "category",
            "값": "value",
            "노출수": "impressions",
            "클릭수": "clicks",
            "CTR": "ctr",
            "비용": "cost",
            "구독 신청": "conversions",
        }
    )
    for col in ["impressions", "clicks", "cost", "conversions"]:
        df[col] = _to_number(df[col])
    df["ctr"] = _to_percent(df["ctr"])

    device_df = df[df["category"] == "기기"].drop(columns=["category"]).rename(columns={"value": "device"})
    hour_df = df[df["category"] == "시간대"].drop(columns=["category"]).rename(columns={"value": "hour"})
    device_df = device_df.reset_index(drop=True)
    hour_df = hour_df.sort_values("hour").reset_index(drop=True)
    return device_df, hour_df


def load_placements() -> pd.DataFrame:
    df = _read_csv("placements.csv")
    df = df.rename(
        columns={
            "게재위치": "placement",
            "관련도": "relevance",
            "노출수": "impressions",
            "클릭수": "clicks",
            "CTR": "ctr",
            "비용": "cost",
            "구독 신청": "conversions",
        }
    )
    if not df.empty:
        for col in ["impressions", "clicks", "cost", "conversions"]:
            df[col] = _to_number(df[col])
        df["ctr"] = _to_percent(df["ctr"])
    return df


def add_week_columns(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """date_col 기준으로 주(월~일) 단위 컬럼(week_start, week_no, week_label)을 추가."""
    df = df.copy()
    week_start = df[date_col] - pd.to_timedelta(df[date_col].dt.weekday, unit="D")
    first_week_start = week_start.min()
    week_no = ((week_start - first_week_start).dt.days // 7 + 1).astype(int)
    week_end = week_start + pd.Timedelta(days=6)
    df["week_start"] = week_start
    df["week_no"] = week_no
    df["week_label"] = (
        week_no.astype(str) + "주차 (" + week_start.dt.strftime("%m/%d") + "~" + week_end.dt.strftime("%m/%d") + ")"
    )
    return df


def weighted_ctr(df: pd.DataFrame) -> float:
    impressions = df["impressions"].sum()
    return (df["clicks"].sum() / impressions * 100) if impressions else 0.0


def weighted_conv_rate(df: pd.DataFrame) -> float:
    clicks = df["clicks"].sum()
    return (df["conversions"].sum() / clicks * 100) if clicks else 0.0


def cost_per_conversion(df: pd.DataFrame) -> float:
    conversions = df["conversions"].sum()
    return (df["cost"].sum() / conversions) if conversions else float("nan")
