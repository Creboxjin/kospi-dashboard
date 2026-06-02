import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="KOSPI 스마트머니 리스크 대시보드", layout="wide")
st.title("📈 KOSPI 이격도 + VIX(공포지수) 융합 방어 시스템")
st.markdown("단순 이격도 과열을 넘어, **옵션 시장의 공포지수(VIX)가 급등하는 다이버전스 현상**을 결합하여 진짜 폭락장을 걸러냅니다.")

# 2. 데이터 수집 및 연산 (KOSPI + VIX 융합)
@st.cache_data(ttl=3600)
def load_data():
    try:
        # [데이터 1] KOSPI 지수
        ks_raw = yf.download('^KS11', start="1996-12-11", progress=False)
        if ks_raw.empty: raise ValueError("yfinance KS11 empty")
        ks = pd.DataFrame({'Close': ks_raw['Close'].squeeze(), 'Low': ks_raw['Low'].squeeze()})
        
        # [데이터 2] 글로벌 공포지수 (VIX)
        vix_raw = yf.download('^VIX', start="1996-12-11", progress=False)
        if vix_raw.empty: raise ValueError("yfinance VIX empty")
        vix = pd.DataFrame({'VIX_Close': vix_raw['Close'].squeeze()})
        
    except Exception:
        # 우회 로직 (yfinance 에러 시 KOSPI만 fdr로 수집, VIX는 임시 처리)
        ks_raw = fdr.DataReader('KS11', '1996-12-11')
        ks = ks_raw[['Close', 'Low']].copy()
        vix = pd.DataFrame({'VIX_Close': [15] * len(ks)}, index=ks.index) # 임시 더미 데이터

    # 데이터 병합 (날짜 기준)
    df = ks.join(vix, how='inner')
    
    # KOSPI 이격도 계산
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['Disparity'] = (df['Close'] / df['MA50']) * 100
    
    # VIX 단기 추세(20일선) 계산
    df['VIX_MA20'] = df['VIX_Close'].rolling(window=20).mean()
    
    # T+10일 최대 낙폭(MAE) 계산
    future_lows = pd.concat([df['Low'].shift(-i) for i in range(1, 11)], axis=1)
    df['Min_Low_10d'] = future_lows.min(axis=1)
    df['MAE_10d(%)'] = ((df['Min_Low_10d'] / df['Close']) - 1) * 100
    
    return df.dropna(subset=['MA50', 'VIX_MA20'])

df = load_data()

# 3. 사이드바 컨트롤러
st.sidebar.header("⚙️ 팩터 설정")
threshold = st.sidebar.slider("1. KOSPI 과열 이격도 (%)", min_value=100, max_value=150, value=115, step=1)
st.sidebar.caption("※ 팩터 융합을 위해 기본 이격도를 115로 살짝 낮추어 표본을 확보합니다.")

st.sidebar.markdown("---")
st.sidebar.markdown("**2. 스마트 머니 팩터 (VIX)**")
st.sidebar.info("VIX 지수가 20일 이동평균선을 돌파하여 '상승 추세'에 진입했을 때만 진짜 위기로 판별합니다.")

st.sidebar.markdown("---")
mae_target = st.sidebar.slider("단기 하락(조정) 판단 기준 (%)", min_value=-15, max_value=-1, value=-5, step=1)
chart_period = st.sidebar.radio("차트 기간", ["최근 2년 (500일)", "최근 5년 (1250일)", "전체 기간 (1996년~)"])

# 4. 시그널 필터링 (비교 분석)
# [기존 로직] 이격도만 과열된 경우
base_signals = df[df['Disparity'] >= threshold].dropna(subset=['MAE_10d(%)'])
if len(base_signals) > 0:
    base_hit = len(base_signals[base_signals['MAE_10d(%)'] <= mae_target])
    base_win_rate = (base_hit / len(base_signals)) * 100
else:
    base_win_rate = 0

# [제인스트리트 로직] 이격도 과열 + VIX 상승 추세 동시 발생
smart_signals = df[(df['Disparity'] >= threshold) & (df['VIX_Close'] > df['VIX_MA20'])].dropna(subset=['MAE_10d(%)'])
if len(smart_signals) > 0:
    smart_hit = len(smart_signals[smart_signals['MAE_10d(%)'] <= mae_target])
    smart_win_rate = (smart_hit / len(smart_signals)) * 100
else:
    smart_win_rate = 0

# 5. 화면 레이아웃 상단 (알파 증명 성과 비교)
st.subheader("💡 팩터 융합에 따른 하락 적중률(승률) 개선 효과")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="1. 기존 로직 (이격도 단독)", value=f"{base_win_rate:.1f}%", help="이격도만 돌파했을 때의 하락 적중률")
with col2:
    # 승률이 얼마나 개선되었는지 델타(Delta) 값 표시
    improvement = smart_win_rate - base_win_rate
    st.metric(label="2. 스마트머니 로직 (이격도+VIX)", value=f"{smart_win_rate:.1f}%", delta=f"{improvement:.1f}%p 개선", delta_color="normal")
with col3:
    st.metric(label="걸러낸 '가짜 시그널' 횟수", value=f"{len(base_signals) - len(smart_signals)} 회", help="이격도는 높았으나 VIX가 안정적이어서 굳이 매도할 필요가 없었던 횟수")

st.markdown("---")

# 6. KOSPI 및 VIX 다이버전스 차트
st.subheader("📊 KOSPI 지수 및 VIX(공포지수) 다이버전스 추이")

if chart_period == "최근 2년 (500일)":
    chart_data = df.tail(500)
elif chart_period == "최근 5년 (1250일)":
    chart_data = df.tail(1250)
else:
    chart_data = df.resample('W').last()

# Plotly 이중축 차트 생성 (KOSPI와 VIX를 한 화면에)
from plotly.subplots import make_subplots
fig = make_subplots(specs=[[{"secondary_y": True}]])

fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['Close'], name="KOSPI", line=dict(color="#2E86C1")), secondary_y=False)
fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['VIX_Close'], name="VIX", line=dict(color="#E74C3C", dash="dot")), secondary_y=True)

fig.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
fig.update_yaxes(title_text="KOSPI Index", secondary_y=False)
fig.update_yaxes(title_text="VIX (Volatility)", secondary_y=True, showgrid=False)
st.plotly_chart(fig, use_container_width=True)

# 7. 스마트 시그널 상세 내역 표
st.subheader(f"📋 진짜 폭락 전조 증상 (이격도 {threshold}% + VIX 상승) 발생 내역")
if len(smart_signals) > 0:
    display_df = smart_signals[['Close', 'Disparity', 'VIX_Close', 'MAE_10d(%)']].copy().round(2)
    display_df.columns = ['당일 KOSPI 종가', 'KOSPI 이격도(%)', '당일 VIX 수치', '10일 내 최대 낙폭(%)']
    st.dataframe(display_df.sort_index(ascending=False), use_container_width=True)
else:
    st.info("조건에 부합하는 시그널이 없습니다.")