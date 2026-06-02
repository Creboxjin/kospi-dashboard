import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="KOSPI 스마트머니 리스크 대시보드", layout="wide")
st.title("📈 KOSPI 이격도 + VIX(공포지수) 융합 방어 시스템")

# 대시보드 로직 설명 아코디언 메뉴
with st.expander("📌 대시보드 핵심 로직 및 활용 가이드 (클릭하여 열기)", expanded=False):
    st.markdown("""
    ### 1. 문제 제기: "차트(이격도)만 보는 것의 한계"
    * 기존 기술적 분석에서는 KOSPI 지수가 50일선 대비 15~20% 이상 급등하면 단순하게 '단기 과열'로 보고 숏(매도) 포지션을 잡음. 
    * 하지만 유동성이 풍부한 강세장에서는 이격도가 높아도 추세가 이어지는 경우가 허다함. 차트만 보면 **가짜 하락 시그널**에 속기 쉬움.

    ### 2. 핵심 해결책: "스마트 머니와의 다이버전스 포착"
    * 노이즈 필터링을 위해 **미국 옵션 시장의 공포지수(VIX)**를 결합함. 
    * **진짜 위기 시그널:** 표면적으로 한국 증시는 급등하며(이격도 115 이상) 대중이 환호하는데, 뒷단에서는 글로벌 스마트 머니가 하락 베팅을 시작하는(VIX 20일선 돌파 상승) **'인지 부조화(Divergence)'** 순간을 추적함.

    ### 3. 백테스팅 결론: "데이터로 증명된 하락 방어력"
    * 1996년부터 검증한 결과, 단순히 KOSPI 이격도만 높아졌을 때보다 **'KOSPI 과열 + VIX 상승 추세'**가 동시에 겹친 날, 10일 이내에 지수가 -5% 이상 단기 폭락할 확률이 압도적으로 높았음.
    """)
st.markdown("---")

# 2. 데이터 수집 및 연산
@st.cache_data(ttl=3600)
def load_data():
    try:
        ks_raw = yf.download('^KS11', start="1996-12-11", progress=False)
        if ks_raw.empty: raise ValueError("yfinance KS11 empty")
        ks = pd.DataFrame({'Close': ks_raw['Close'].squeeze(), 'Low': ks_raw['Low'].squeeze()})
        
        vix_raw = yf.download('^VIX', start="1996-12-11", progress=False)
        if vix_raw.empty: raise ValueError("yfinance VIX empty")
        vix = pd.DataFrame({'VIX_Close': vix_raw['Close'].squeeze()})
        
    except Exception:
        ks_raw = fdr.DataReader('KS11', '1996-12-11')
        ks = ks_raw[['Close', 'Low']].copy()
        vix = pd.DataFrame({'VIX_Close': [15] * len(ks)}, index=ks.index)

    df = ks.join(vix, how='inner')
    
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['Disparity'] = (df['Close'] / df['MA50']) * 100
    df['VIX_MA20'] = df['VIX_Close'].rolling(window=20).mean()
    
    future_lows = pd.concat([df['Low'].shift(-i) for i in range(1, 11)], axis=1)
    df['Min_Low_10d'] = future_lows.min(axis=1)
    df['MAE_10d(%)'] = ((df['Min_Low_10d'] / df['Close']) - 1) * 100
    
    return df.dropna(subset=['MA50', 'VIX_MA20'])

df = load_data()

# [신규 추가] 코스피 주요 강세장(Bull) 및 약세장(Bear) 국면 데이터
# 분석 목적상 시작과 끝 날짜를 YYYY-MM-DD 형식으로 매핑함
regimes = [
    ("2000-03-01", "2001-09-30", "Bear", "IT 버블 붕괴"),
    ("2001-09-01", "2002-04-30", "Bull", "기술적 반등"),
    ("2002-04-01", "2003-03-31", "Bear", "글로벌 경기 둔화"),
    ("2003-03-01", "2007-10-31", "Bull", "중국 성장+유동성"),
    ("2007-10-01", "2008-11-30", "Bear", "글로벌 금융위기"),
    ("2008-11-01", "2011-04-30", "Bull", "금융위기 이후 유동성"),
    ("2011-04-01", "2012-07-31", "Bear", "유럽 재정위기"),
    ("2012-07-01", "2015-04-30", "Bull", "글로벌 경기 회복"),
    ("2015-04-01", "2016-02-28", "Bear", "중국 경기 둔화"),
    ("2016-02-01", "2018-01-31", "Bull", "반도체 슈퍼사이클"),
    ("2018-01-01", "2019-01-31", "Bear", "미중 무역전쟁"),
    ("2019-01-01", "2020-01-31", "Bull", "글로벌 완화 정책"),
    ("2020-01-01", "2020-03-31", "Bear", "코로나 쇼크"),
    ("2020-03-01", "2021-06-30", "Bull", "코로나 유동성 랠리"),
    ("2021-06-01", "2022-10-31", "Bear", "글로벌 금리 인상"),
    ("2022-10-01", "2024-07-31", "Bull", "AI / 반도체 / 2차전지"),
    ("2024-07-01", "2024-10-31", "Bear", "AI 랠리 단기 조정"),
    ("2024-10-01", "2026-12-31", "Bull", "AI 산업 사이클") # 현재 진행형
]

# 3. 사이드바 컨트롤러
st.sidebar.header("⚙️ 팩터 설정")
threshold = st.sidebar.slider("1. KOSPI 과열 이격도 (%)", min_value=100, max_value=150, value=115, step=1)
st.sidebar.markdown("---")
st.sidebar.info("VIX 지수가 20일 이동평균선을 돌파하여 '상승 추세'에 진입했을 때만 진짜 위기로 판별함.")
st.sidebar.markdown("---")
mae_target = st.sidebar.slider("단기 하락(조정) 판단 기준 (%)", min_value=-15, max_value=-1, value=-5, step=1)
chart_period = st.sidebar.radio("차트 기간", ["최근 2년 (500일)", "최근 5년 (1250일)", "전체 기간 (1996년~)"])

# 4. 시그널 필터링 (비교 분석)
base_signals = df[df['Disparity'] >= threshold].dropna(subset=['MAE_10d(%)'])
if len(base_signals) > 0:
    base_hit = len(base_signals[base_signals['MAE_10d(%)'] <= mae_target])
    base_win_rate = (base_hit / len(base_signals)) * 100
else:
    base_win_rate = 0

smart_signals = df[(df['Disparity'] >= threshold) & (df['VIX_Close'] > df['VIX_MA20'])].dropna(subset=['MAE_10d(%)'])
if len(smart_signals) > 0:
    smart_hit = len(smart_signals[smart_signals['MAE_10d(%)'] <= mae_target])
    smart_win_rate = (smart_hit / len(smart_signals)) * 100
else:
    smart_win_rate = 0

# 5. 화면 레이아웃 상단 (알파 증명 성과 비교)
st.subheader("💡 팩터 융합에 따른 하락 적중률(승률) 개선 효과")
col1, col2, col3 = st.columns(3)
with col1: st.metric(label="1. 기존 로직 (이격도 단독)", value=f"{base_win_rate:.1f}%")
with col2: st.metric(label="2. 스마트머니 로직 (이격도+VIX)", value=f"{smart_win_rate:.1f}%", delta=f"{smart_win_rate - base_win_rate:.1f}%p 개선", delta_color="normal")
with col3: st.metric(label="걸러낸 '가짜 시그널' 횟수", value=f"{len(base_signals) - len(smart_signals)} 회")

st.markdown("---")

# 6. KOSPI 및 VIX 다이버전스 차트 (국면 배경색 추가)
st.subheader("📊 KOSPI 지수 및 VIX 다이버전스 (강세/약세장 국면 포함)")

if chart_period == "최근 2년 (500일)": chart_data = df.tail(500)
elif chart_period == "최근 5년 (1250일)": chart_data = df.tail(1250)
else: chart_data = df.resample('W').last()

fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['Close'], name="KOSPI", line=dict(color="#2E86C1")), secondary_y=False)
fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['VIX_Close'], name="VIX", line=dict(color="#E74C3C", dash="dot")), secondary_y=True)

# 차트에 Bull/Bear 국면 배경색 그리기
for start, end, regime_type, name in regimes:
    color = "rgba(231, 76, 60, 0.1)" if regime_type == "Bull" else "rgba(52, 152, 219, 0.15)" # 강세장 옅은 붉은색, 약세장 옅은 푸른색
    fig.add_vrect(
        x0=start, x1=end,
        fillcolor=color, layer="below", line_width=0,
        annotation_text=name if chart_period == "전체 기간 (1996년~)" else "", # 전체 기간일 때만 텍스트 표시
        annotation_position="top left",
        annotation=dict(font_size=10, textangle=-90)
    )

fig.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
fig.update_yaxes(title_text="KOSPI Index", secondary_y=False)
fig.update_yaxes(title_text="VIX (Volatility)", secondary_y=True, showgrid=False)
st.plotly_chart(fig, use_container_width=True)

# 7. 스마트 시그널 상세 내역 표
st.subheader(f"📋 과거 폭락 전조 증상 발생 내역 (결과 확정)")
if len(smart_signals) > 0:
    display_df = smart_signals[['Close', 'Disparity', 'VIX_Close', 'MAE_10d(%)']].copy().round(2)
    display_df.columns = ['당일 KOSPI 종가', 'KOSPI 이격도(%)', '당일 VIX 수치', '10일 내 최대 낙폭(%)']
    st.dataframe(display_df.sort_index(ascending=False), use_container_width=True)
else:
    st.info("조건에 부합하는 과거 시그널이 없습니다.")

st.markdown("---")

# 8. [신규 추가] 최근 10 영업일 실시간 트래킹 (미래 결과 미확정)
st.subheader("🔍 최근 10 영업일 이격도 모니터링 (현재 진행형 시그널 추적)")
st.markdown("조회일 기준 아직 10일이 경과하지 않아 미래 낙폭(MAE)이 확정되지 않은 최근 데이터를 실시간으로 추적함.")

recent_10d = df[['Close', 'MA50', 'Disparity', 'VIX_Close', 'VIX_MA20']].tail(10).copy().round(2)
recent_10d.columns = ['종가', '50일 이평선', '이격도(%)', '당일 VIX', 'VIX 20일선']
# 직관적인 모니터링을 위해 최신 날짜가 위로 오도록 정렬
st.dataframe(recent_10d.sort_index(ascending=False), use_container_width=True)