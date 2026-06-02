import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr  # 플랜 B 우회 라이브러리 추가
import pandas as pd
import plotly.express as px

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="KOSPI 과열 분석 대시보드", layout="wide")
st.title("📈 KOSPI 이격도 단기 조정(폭락) 리스크 대시보드")
st.markdown("이격도 과열 시그널 발생 후, **10영업일 이내에 발생하는 단기 최대 낙폭(MAE)**을 추적하여 하락장 진입 확률을 계산합니다.")

# 2. 데이터 수집 및 연산 (클라우드 IP 차단 우회 로직 적용)
@st.cache_data(ttl=3600) # 한 번 가져온 데이터는 1시간 동안 보관 (서버 차단 방지용)
def load_data():
    try:
        # [플랜 A] yfinance로 먼저 시도
        df_raw = yf.download('^KS11', start="1996-12-11", progress=False)
        
        # 클라우드 IP가 차단당해서 데이터가 비어있다면 에러 발생시킴
        if df_raw.empty:
            raise ValueError("yfinance empty data")
            
        if isinstance(df_raw.columns, pd.MultiIndex):
            df = pd.DataFrame({
                'Close': df_raw['Close'].squeeze(),
                'Low': df_raw['Low'].squeeze()
            })
        else:
            df = df_raw[['Close', 'Low']].copy()
            
    except Exception:
        # [플랜 B] 에러 발생 시 FinanceDataReader로 데이터 우회 수집
        df_raw = fdr.DataReader('KS11', '1996-12-11')
        df = df_raw[['Close', 'Low']].copy()

    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['Disparity'] = (df['Close'] / df['MA50']) * 100
    
    # 시그널 발생 후 10일(T+1 ~ T+10) 동안의 장중 최저가(Low) 찾기
    future_lows = pd.concat([df['Low'].shift(-i) for i in range(1, 11)], axis=1)
    df['Min_Low_10d'] = future_lows.min(axis=1)
    
    # 단기 최대 낙폭(MAE) 수익률 계산
    df['MAE_10d(%)'] = ((df['Min_Low_10d'] / df['Close']) - 1) * 100
    
    df = df.dropna(subset=['MA50'])
    return df

df = load_data()

# 3. 사이드바 컨트롤러
st.sidebar.header("⚙️ 대시보드 설정")
threshold = st.sidebar.slider("과열 이격도 기준 (%)", min_value=100, max_value=150, value=120, step=1)

st.sidebar.markdown("---")
mae_target = st.sidebar.slider("단기 하락(조정) 판단 기준 (%)", min_value=-15, max_value=-1, value=-5, step=1)
st.sidebar.caption("시그널 이후 10일 내에 해당 수치 이상 주가가 하락하면 '적중'으로 간주함.")

st.sidebar.markdown("---")
chart_period = st.sidebar.radio("상단 차트 기간", ["최근 2년 (500일)", "최근 5년 (1250일)", "전체 기간 (1996년~)"])

# 4. 시그널 필터링
signals = df[df['Disparity'] >= threshold].copy()
valid_signals = signals.dropna(subset=['MAE_10d(%)'])

# 5. 화면 레이아웃 상단 (지수 차트 및 통계)
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("KOSPI 지수 및 50일선 추이")
    if chart_period == "최근 2년 (500일)":
        chart_data = df[['Close', 'MA50']].tail(500)
    elif chart_period == "최근 5년 (1250일)":
        chart_data = df[['Close', 'MA50']].tail(1250)
    else:
        chart_data = df[['Close', 'MA50']].resample('W').last()
        
    fig1 = px.line(chart_data, y=['Close', 'MA50'], color_discrete_map={'Close': '#2E86C1', 'MA50': '#F39C12'})
    fig1.update_layout(xaxis_title="Date", yaxis_title="Index (pt)", hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader(f"시그널 발생 요약 (이격도 {threshold} 이상)")
    
    if len(valid_signals) > 0:
        hit_count = len(valid_signals[valid_signals['MAE_10d(%)'] <= mae_target])
        win_rate = (hit_count / len(valid_signals)) * 100
    else:
        win_rate = 0.0
        hit_count = 0
        
    st.metric(label="총 시그널 발생 횟수", value=f"{len(signals)} 회")
    st.metric(label=f"단기 폭락 적중률 ({mae_target}% 이상 하락)", value=f"{win_rate:.1f} %")
    st.caption(f"{len(valid_signals)}번 중 {hit_count}번 하락 적중")

# 6. 화면 레이아웃 하단 (텍스트 표 형태의 상세 내역)
st.markdown("---")
st.subheader("📋 시그널 발생 후 10일 내 단기 낙폭 상세 내역")

if len(valid_signals) > 0:
    display_df = valid_signals[['Close', 'Disparity', 'Min_Low_10d', 'MAE_10d(%)']].copy()
    display_df = display_df.round(2)
    display_df.columns = ['당일 종가', '이격도(%)', '10일 내 최저가', '최대 낙폭(%)']
    st.dataframe(display_df.sort_index(ascending=False), use_container_width=True)
else:
    st.info("조건에 부합하는 시그널이 없습니다.")