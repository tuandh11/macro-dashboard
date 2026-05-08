import streamlit as st
from vnstock import *
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

# --- 1. CẤU HÌNH GIAO DIỆN DARK MODE TỰ ĐỘNG ---
st.set_page_config(page_title="Macro Watch", layout="wide", initial_sidebar_state="expanded")

# --- CẤU HÌNH FONT CHỮ KIỂU MACOS/IOS ---
st.markdown(
    """
    <style>
    html, body, [class*="st-"] {
        font-family: -apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Cấu hình Sidebar cho API Key
with st.sidebar:
    st.header("⚙️ Cấu hình Hệ thống")
    gemini_api_key = st.text_input("Nhập Gemini API Key:", type="password", help="Dùng để kích hoạt Trợ lý AI")
    st.markdown("[Lấy Key miễn phí tại Google AI Studio](https://aistudio.google.com/app/apikey)")

# Thiết kế Tiêu đề
st.markdown("<h1 style='text-align: center; color: #E5A93C;'> DEEP-DIVE TERMINAL - HOSE</h1>", unsafe_allow_html=True)
st.markdown("---")

# --- 2. XÂY DỰNG "BỘ NÃO" LẤY DỮ LIỆU ---
def calculate_rsi(data, period=14):
    """Hàm tính toán chỉ báo RSI tiêu chuẩn"""
    delta = data.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period-1, adjust=False).mean()
    ema_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

# Dùng cache để lưu dữ liệu trong 5 phút, tránh việc tải lại web bị chậm
@st.cache_data(ttl=300) 
def get_macro_indicators():
    try:
        # Sử dụng vnstock để lấy VNINDEX thay vì Yahoo Finance (tránh lỗi 404 Not Found / delisted)
        end_date = datetime.today().strftime('%Y-%m-%d')
        start_date = (datetime.today() - pd.Timedelta(days=7)).strftime('%Y-%m-%d')
        # Đổi sang nguồn KBS để đảm bảo tính ổn định cao và chống bị chặn
        vn_data = Quote(symbol="VNINDEX", source="KBS").history(start=start_date, end=end_date)
        vnindex = round(vn_data['close'].iloc[-1], 2)
        
        return vnindex
    except Exception as e:
        return "N/A"

@st.cache_data(ttl=300)
def get_stock_insight(symbol="FPT"):
    # Sử dụng sức mạnh của VnStock 4.0 để lấy dữ liệu chứng khoán Việt Nam
    try:
        quote = Quote(symbol=symbol, source='KBS')
        # Lấy lịch sử giá từ đầu năm đến nay để vẽ biểu đồ
        df = quote.history(start='2026-01-01', end=datetime.today().strftime('%Y-%m-%d'))
        return df
    except Exception as e:
        st.error(f"Lỗi truy xuất dữ liệu: {e}")
        return pd.DataFrame()

def generate_ai_analysis(symbol, df, api_key):
    """Sử dụng Gemini API để phân tích biến động giá cổ phiếu"""
    if df.empty or 'close' not in df.columns:
        return "Chưa đủ dữ liệu để hệ thống AI phân tích."
    
    if not api_key:
        return "⚠️ Vui lòng nhập **Gemini API Key** ở thanh bên trái (Sidebar) để kích hoạt trợ lý AI."
        
    start_price = df['close'].iloc[0]
    end_price = df['close'].iloc[-1]
    change = ((end_price - start_price) / start_price) * 100
    
    # Thu thập thêm các chỉ báo kỹ thuật vừa được tạo ở biểu đồ
    rsi = round(df['RSI'].iloc[-1], 2) if 'RSI' in df.columns else "Chưa có dữ liệu"
    vol = df['volume'].iloc[-1] if 'volume' in df.columns else "Chưa có dữ liệu"
    
    prompt = f"""
    Bạn là một chuyên gia phân tích chứng khoán chuyên nghiệp tại thị trường Việt Nam.
    Hãy phân tích ngắn gọn, súc tích (khoảng 3-4 câu) về cổ phiếu {symbol} dựa trên các dữ liệu kỹ thuật mới nhất sau:
    - Giá hiện tại: {end_price} (Biến động từ đầu năm: {change:.2f}%)
    - Chỉ báo RSI hiện tại: {rsi} (Nhắc lại: RSI > 70 là vùng quá mua, RSI < 30 là vùng quá bán)
    - Khối lượng giao dịch phiên gần nhất: {vol}
    
    Yêu cầu: Nhận định đánh giá rủi ro hiện tại và đưa ra khuyến nghị chiến lược (Mua/Bán/Nắm giữ) kèm lý do. Trình bày bằng Markdown, có sử dụng in đậm và emoji.
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Lỗi khi kết nối với Gemini API: {e}"

# --- 3. ĐƯA DỮ LIỆU LÊN GIAO DIỆN TRỰC QUAN ---
vnindex = get_macro_indicators()

# Thêm Dropdown chọn mã Bluechip (VN30)
blue_chips = ["FPT", "VCB", "HPG", "MWG", "TCB", "VIC", "VHM", "SSI", "VPB", "MBB", "GEX"]
selected_stock = st.selectbox("📌 Chọn mã cổ phiếu Blue-chip (VN30):", blue_chips)

# Lấy dữ liệu mã được chọn trước để trích xuất giá mới nhất cho thẻ điểm
df_stock = get_stock_insight(selected_stock)
stock_price = round(df_stock['close'].iloc[-1], 2) if not df_stock.empty and 'close' in df_stock.columns else "N/A"

# Tạo 2 cột thẻ điểm (Scorecards) nằm ngang
col1, col2 = st.columns(2)

with col1:
    st.metric(label="🇻🇳 VN-Index (HOSE)", value=vnindex)
with col2:
    st.metric(label=f"📈 Giá cổ phiếu {selected_stock}", value=stock_price)

st.markdown("<br>", unsafe_allow_html=True) # Tạo khoảng trống

# --- 4. DÒNG TIỀN & TÂM LÝ (MARKET BREADTH & FLOWS) ---
st.subheader("🌊 Dòng tiền & Tâm lý (Market Breadth & Flows)")
flow_col1, flow_col2, flow_col3 = st.columns(3)

with flow_col1:
    st.metric(label="💧 Thanh khoản thị trường", value="18,500 Tỷ VNĐ", delta="12% so với hôm qua (Mô phỏng)")
with flow_col2:
    st.metric(label="🌍 Khối ngoại & Tự doanh Net Flow", value="-250 Tỷ VNĐ", delta="Bán ròng (Mô phỏng)", delta_color="inverse")
with flow_col3:
    st.metric(label="⚖️ Độ rộng thị trường", value="210 Xanh / 150 Đỏ", delta="Tích cực (Mô phỏng)")

st.markdown("<br>", unsafe_allow_html=True)

# Khu vực biểu đồ chuyên sâu
st.subheader("💡 Phân tích Kỹ thuật Chuyên sâu & AI Nhận định")

# Tạo 2 cột: Cột trái vẽ biểu đồ, Cột phải hiện tin tức
chart_col, news_col = st.columns([2, 1])

with chart_col:
    st.markdown(f"**Biểu đồ Nến, Khối lượng & RSI ({selected_stock})**")
    if not df_stock.empty and 'close' in df_stock.columns and 'volume' in df_stock.columns:
        df_stock['RSI'] = calculate_rsi(df_stock['close'])
        
        # Khởi tạo khung biểu đồ Plotly gồm 3 phần
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
        
        # 1. Biểu đồ nến Nhật (Candlestick)
        fig.add_trace(go.Candlestick(x=df_stock['time'], open=df_stock['open'], high=df_stock['high'], 
                                     low=df_stock['low'], close=df_stock['close'], name='Giá'), row=1, col=1)
        
        # 2. Khối lượng giao dịch (Volume)
        colors = ['#26a69a' if row['close'] >= row['open'] else '#ef5350' for _, row in df_stock.iterrows()]
        fig.add_trace(go.Bar(x=df_stock['time'], y=df_stock['volume'], marker_color=colors, name='KLGD'), row=2, col=1)
        
        # 3. Chỉ báo RSI
        fig.add_trace(go.Scatter(x=df_stock['time'], y=df_stock['RSI'], name='RSI', line=dict(color='#ab47bc')), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
        
        fig.update_layout(height=650, xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Đang chờ cập nhật dữ liệu hoặc thiếu dữ liệu (open/high/low/volume)...")

with news_col:
    st.markdown(f"**🤖 Phân tích AI ({selected_stock})**")
    with st.spinner("AI đang phân tích dữ liệu..."):
        ai_text = generate_ai_analysis(selected_stock, df_stock, gemini_api_key)
    st.info(ai_text)