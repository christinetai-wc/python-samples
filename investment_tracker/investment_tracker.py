import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os
import io
import zipfile

# 嘗試導入 yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

# 嘗試導入 fear_and_greed
try:
    import fear_and_greed
    FEAR_GREED_AVAILABLE = True
except ImportError:
    FEAR_GREED_AVAILABLE = False


st.set_page_config(page_title="投資理財追蹤系統", layout="wide")
st.title("💰 投資理財資金分配追蹤系統 (USD)")

# 檔案名稱對應
FILE_MAPPING = {
    'investment_plan.csv': 'df_plan',
    'aggressive_allocation.csv': 'df_allocation',
    'conservative_allocation.csv': 'df_conservative',
    'lottery_allocation.csv': 'df_lottery',
    'stock_transactions.csv': 'df_stock',
    'options_transactions.csv': 'df_option'
}
USD_RATE = 31.5

# 初始化 session_state
def init_session_state():
    if 'df_plan' not in st.session_state:
        st.session_state.df_plan = pd.DataFrame(columns=['時間', '預計投入(USD)', '匯率'])
    if 'horizontal_ratio' not in st.session_state:
        st.session_state.horizontal_ratio = {'保守型': 10.0, '樂透型': 10.0, '進攻型': 80.0}
    if 'df_allocation' not in st.session_state:
        st.session_state.df_allocation = pd.DataFrame(columns=['股票代碼', '比重', '公允值(USD)', '邊際1(%)', '邊際2(%)', '邊際3(%)', '邊際4(%)', '邊際5(%)', '邊際1比重(%)', '邊際2比重(%)', '邊際3比重(%)', '邊際4比重(%)', '邊際5比重(%)'])
    if 'df_conservative' not in st.session_state:
        st.session_state.df_conservative = pd.DataFrame({
            '股票代碼': ['VOO'],
            '比重': [100.0],
            '說明': ['S&P 500 ETF']
        })
    if 'df_lottery' not in st.session_state:
        st.session_state.df_lottery = pd.DataFrame({
            '股票代碼': ['BTC'],
            '比重': [100.0],
            '說明': ['比特幣']
        })
    if 'df_stock' not in st.session_state:
        st.session_state.df_stock = pd.DataFrame(columns=['交易日期', '交易類型', '所屬分類', '股票代碼', '股數', '成交價格(USD)', '手續費(USD)', '交易稅(USD)', '用途說明', '備註'])
    if 'df_option' not in st.session_state:
        st.session_state.df_option = pd.DataFrame(columns=['交易日期', '商品類型', '標的', '履約價', '到期日', '買賣權', '買賣方向', '口數', '權利金', '交易金額(USD)', '手續費(USD)', '保證金(USD)', '總成本(USD)', '資金來源', '策略說明'])
    if 'data_folder' not in st.session_state:
        # 預設為程式所在的資料夾
        st.session_state.data_folder = os.path.dirname(os.path.abspath(__file__))
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False

init_session_state()

# 從資料夾載入 CSV 檔案（本地模式）
def load_from_folder(folder_path):
    if not os.path.isdir(folder_path):
        return False, "資料夾不存在"

    loaded_files = []
    for filename, state_key in FILE_MAPPING.items():
        file_path = os.path.join(folder_path, filename)
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                # 向下相容：移除舊版 investment_plan.csv 的投資類型欄
                if state_key == 'df_plan' and '投資類型' in df.columns:
                    df = df.drop(columns=['投資類型'])
                st.session_state[state_key] = df
                loaded_files.append(filename)
            except Exception as e:
                pass

    # 載入水平配置比例
    settings_path = os.path.join(folder_path, 'settings.csv')
    if os.path.exists(settings_path):
        try:
            df_settings = pd.read_csv(settings_path, encoding='utf-8-sig')
            st.session_state.horizontal_ratio = dict(zip(df_settings['類型'], df_settings['比例']))
            loaded_files.append('settings.csv')
        except Exception:
            pass

    if loaded_files:
        st.session_state.data_loaded = True
        return True, f"已載入: {', '.join(loaded_files)}"
    return False, "找不到任何 CSV 檔案"

# 從上傳的檔案載入（雲端模式）
def load_from_uploaded_files(uploaded_files):
    loaded_files = []
    for uploaded_file in uploaded_files:
        filename = uploaded_file.name

        # 處理 ZIP 檔案
        if filename.endswith('.zip'):
            with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                for zip_filename in zip_ref.namelist():
                    if zip_filename in FILE_MAPPING:
                        with zip_ref.open(zip_filename) as f:
                            df = pd.read_csv(f, encoding='utf-8-sig')
                            if FILE_MAPPING[zip_filename] == 'df_plan' and '投資類型' in df.columns:
                                df = df.drop(columns=['投資類型'])
                            st.session_state[FILE_MAPPING[zip_filename]] = df
                            loaded_files.append(zip_filename)
                    elif zip_filename == 'settings.csv':
                        with zip_ref.open(zip_filename) as f:
                            df_settings = pd.read_csv(f, encoding='utf-8-sig')
                            st.session_state.horizontal_ratio = dict(zip(df_settings['類型'], df_settings['比例']))
                            loaded_files.append('settings.csv')
        # 處理 CSV 檔案
        elif filename in FILE_MAPPING:
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            if FILE_MAPPING[filename] == 'df_plan' and '投資類型' in df.columns:
                df = df.drop(columns=['投資類型'])
            st.session_state[FILE_MAPPING[filename]] = df
            loaded_files.append(filename)

    if loaded_files:
        st.session_state.data_loaded = True
        return True, f"已載入: {', '.join(loaded_files)}"
    return False, "找不到符合的 CSV 檔案"

# 匯出所有資料為 ZIP
def export_all_to_zip():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, state_key in FILE_MAPPING.items():
            if state_key in st.session_state and not st.session_state[state_key].empty:
                csv_buffer = io.StringIO()
                st.session_state[state_key].to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                zip_file.writestr(filename, csv_buffer.getvalue().encode('utf-8-sig'))
        # 匯出水平配置比例
        if 'horizontal_ratio' in st.session_state:
            h = st.session_state.horizontal_ratio
            df_settings = pd.DataFrame({'類型': h.keys(), '比例': h.values()})
            csv_buf = io.StringIO()
            df_settings.to_csv(csv_buf, index=False, encoding='utf-8-sig')
            zip_file.writestr('settings.csv', csv_buf.getvalue().encode('utf-8-sig'))
    zip_buffer.seek(0)
    return zip_buffer

# 儲存到本地資料夾
def save_to_folder(folder_path):
    if not os.path.isdir(folder_path):
        return False, "資料夾不存在"

    saved_files = []
    for filename, state_key in FILE_MAPPING.items():
        if state_key in st.session_state and not st.session_state[state_key].empty:
            file_path = os.path.join(folder_path, filename)
            st.session_state[state_key].to_csv(file_path, index=False, encoding='utf-8-sig')
            saved_files.append(filename)

    # 儲存水平配置比例
    if 'horizontal_ratio' in st.session_state:
        h = st.session_state.horizontal_ratio
        df_settings = pd.DataFrame({'類型': h.keys(), '比例': h.values()})
        settings_path = os.path.join(folder_path, 'settings.csv')
        df_settings.to_csv(settings_path, index=False, encoding='utf-8-sig')
        saved_files.append('settings.csv')

    if saved_files:
        return True, f"已儲存: {', '.join(saved_files)}"
    return False, "沒有資料可儲存"

# 取得恐懼貪婪指數
def get_fear_greed_index():
    """取得 CNN 恐懼貪婪指數"""
    if not FEAR_GREED_AVAILABLE:
        return None
    try:
        fgi = fear_and_greed.get()
        return {
            'value': fgi.value,
            'description': fgi.description,
            'last_update': fgi.last_update.strftime('%Y-%m-%d %H:%M') if fgi.last_update else ''
        }
    except:
        return None

# 計算實際投入金額（僅股票成本，不含保證金）
def calculate_actual_investment(df_stock, category, stock_code=None):
    total = 0

    # 計算股票買入成本
    if not df_stock.empty:
        if stock_code:
            # 有指定股票代碼時，篩選該分類下的特定股票
            filtered = df_stock[(df_stock['所屬分類'] == category) &
                               (df_stock['股票代碼'] == stock_code) &
                               (df_stock['交易類型'] == '買進')]
        else:
            filtered = df_stock[(df_stock['所屬分類'] == category) & (df_stock['交易類型'] == '買進')]

        if not filtered.empty:
            # 計算總成本 = 交易金額 + 手續費
            for _, row in filtered.iterrows():
                shares = abs(row['股數'])
                price = row['成交價格(USD)']
                trade_amt = shares * price
                fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else 0
                total += trade_amt + fee

    return total

def calculate_sell_proceeds(df_stock, category=None, stock_code=None):
    """計算賣出收入（賣出金額 - 手續費 - 交易稅）"""
    if df_stock.empty:
        return 0

    filtered = df_stock[df_stock['交易類型'] == '賣出']
    if category:
        filtered = filtered[filtered['所屬分類'] == category]
    if stock_code:
        filtered = filtered[filtered['股票代碼'] == stock_code]

    if filtered.empty:
        return 0

    total = 0
    for _, row in filtered.iterrows():
        shares = abs(row['股數'])
        price = row['成交價格(USD)']
        trade_amt = shares * price
        fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else 0
        tax = row['交易稅(USD)'] if pd.notna(row['交易稅(USD)']) and row['交易稅(USD)'] > 0 else 0
        total += trade_amt - fee - tax

    return total

# 計算選擇權買方成本（資金來源對應到特定股票的未到期買方部位權利金）
def calculate_option_buy_cost(df_option, stock_code, return_details=False):
    if df_option is None or df_option.empty:
        return (0, []) if return_details else 0
    if '資金來源' not in df_option.columns or '交易金額(USD)' not in df_option.columns:
        return (0, []) if return_details else 0

    df_opt_calc = df_option.copy()
    df_opt_calc['到期日'] = pd.to_datetime(df_opt_calc['到期日'])
    df_opt_calc['資金來源'] = df_opt_calc['資金來源'].fillna('').astype(str)
    today = pd.Timestamp(datetime.now().date())
    active_buy = df_opt_calc[
        (df_opt_calc['資金來源'].str.upper() == stock_code.upper()) &
        (df_opt_calc['到期日'] >= today) &
        (df_opt_calc['買賣方向'] == '買入')
    ]
    if not active_buy.empty:
        total = active_buy['交易金額(USD)'].sum()
        if return_details:
            details = []
            for _, row in active_buy.iterrows():
                details.append({
                    'ticker': row.get('標的', ''),
                    'cost': row['交易金額(USD)'],
                    'cp': row.get('買賣權', '')
                })
            return (total, details)
        return total
    return (0, []) if return_details else 0

# 計算選擇權被壓住的保證金（資金來源對應到特定股票的未到期賣方部位）
def calculate_option_margin(df_option, stock_code, return_details=False):
    if df_option is None or df_option.empty:
        return (0, []) if return_details else 0
    if '保證金(USD)' not in df_option.columns or '資金來源' not in df_option.columns:
        return (0, []) if return_details else 0

    df_opt_calc = df_option.copy()
    df_opt_calc['到期日'] = pd.to_datetime(df_opt_calc['到期日'])
    df_opt_calc['資金來源'] = df_opt_calc['資金來源'].fillna('').astype(str)
    today = pd.Timestamp(datetime.now().date())
    # 篩選: 資金來源為此股票、未到期、賣方部位
    active_margin = df_opt_calc[
        (df_opt_calc['資金來源'].str.upper() == stock_code.upper()) &
        (df_opt_calc['到期日'] >= today) &
        (df_opt_calc['買賣方向'] == '賣出')
    ]
    if not active_margin.empty:
        total = active_margin['保證金(USD)'].sum()
        if return_details:
            # 取得標的股票清單和對應保證金
            details = []
            if '標的' in active_margin.columns:
                for _, row in active_margin.iterrows():
                    details.append({
                        'ticker': row['標的'],
                        'margin': row['保證金(USD)']
                    })
            return (total, details)
        return total
    return (0, []) if return_details else 0

# 計算選擇權未實現損益
def calculate_options_unrealized_pnl(df_option):
    """計算未到期選擇權部位的未實現損益"""
    if df_option is None or df_option.empty:
        return 0, []

    df_calc = df_option.copy()
    if '到期日' not in df_calc.columns:
        return 0, []

    df_calc['到期日'] = pd.to_datetime(df_calc['到期日'])
    today = pd.Timestamp(datetime.now().date())
    active = df_calc[df_calc['到期日'] >= today]

    if active.empty:
        return 0, []

    total_unrealized = 0
    details = []

    for idx, row in active.iterrows():
        ticker = row.get('標的', '')
        strike = row.get('履約價', 0)
        expiry = row['到期日']
        cp = row.get('買賣權', '')
        direction = row.get('買賣方向', '')
        contracts = row.get('口數', 0)
        trade_amt = row.get('交易金額(USD)', 0)

        # 將買賣權轉為 yfinance 格式
        opt_type = 'Call' if 'Call' in str(cp) or 'call' in str(cp) or cp == '買權' else 'Put'
        expiry_str = expiry.strftime('%Y-%m-%d')

        current_price = get_option_price(ticker, expiry_str, strike, opt_type)

        unrealized = 0
        if current_price is not None:
            market_value = current_price * contracts * 100
            if direction == '賣出':
                # 賣方：收到的權利金 - 平倉成本
                unrealized = trade_amt - market_value
            else:
                # 買方：現在市值 - 付出的權利金
                unrealized = market_value - trade_amt
            total_unrealized += unrealized

        details.append({
            '標的': ticker,
            '買賣權': cp,
            '買賣方向': direction,
            '履約價': strike,
            '到期日': expiry_str,
            '口數': contracts,
            '交易金額': trade_amt,
            '現價': current_price,
            '未實現損益': unrealized,
        })

    return total_unrealized, details

# 取得股票現價
@st.cache_data(ttl=300)  # 快取5分鐘
def get_current_price(ticker):
    """使用 yfinance 取得股票/加密貨幣現價"""
    if not YFINANCE_AVAILABLE:
        return None
    try:
        # 加密貨幣代碼轉換 (BTC -> BTC-USD)
        crypto_map = {'BTC': 'BTC-USD', 'ETH': 'ETH-USD', 'SOL': 'SOL-USD',
                      'XRP': 'XRP-USD', 'ADA': 'ADA-USD', 'DOGE': 'DOGE-USD'}
        yf_ticker = crypto_map.get(ticker.upper(), ticker)

        stock = yf.Ticker(yf_ticker)

        # 方法1: 使用 fast_info (較不容易被限速)
        try:
            price = stock.fast_info.get('lastPrice') or stock.fast_info.get('previousClose')
            if price:
                return float(price)
        except:
            pass

        # 方法2: 使用 history 取得最近收盤價
        try:
            hist = stock.history(period='1d')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except:
            pass

        # 方法3: 使用 info (可能被限速)
        try:
            info = stock.info
            price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            if price:
                return float(price)
        except:
            pass

        return None
    except:
        return None

# 取得選擇權現價
@st.cache_data(ttl=300)
def get_option_price(ticker, expiry_str, strike, option_type):
    """使用 yfinance 取得選擇權現價"""
    if not YFINANCE_AVAILABLE:
        return None
    try:
        stock = yf.Ticker(ticker)
        chain = stock.option_chain(expiry_str)
        df = chain.calls if option_type == 'Call' else chain.puts
        if df.empty:
            return None
        match = df[abs(df['strike'] - strike) < 0.01]
        if match.empty:
            return None
        row = match.iloc[0]
        price = row.get('lastPrice')
        if price and price > 0:
            return float(price)
        bid = row.get('bid', 0) or 0
        ask = row.get('ask', 0) or 0
        if bid > 0 or ask > 0:
            return float((bid + ask) / 2)
        return None
    except:
        return None

# 取得即時匯率
@st.cache_data(ttl=300)  # 快取5分鐘
def get_exchange_rate(from_currency="USD", to_currency="TWD"):
    """使用 yfinance 取得匯率"""
    if not YFINANCE_AVAILABLE:
        return None
    try:
        ticker = yf.Ticker(f"{from_currency}{to_currency}=X")

        # 方法1: 使用 fast_info
        try:
            rate = ticker.fast_info.get('lastPrice') or ticker.fast_info.get('previousClose')
            if rate:
                return float(rate)
        except:
            pass

        # 方法2: 使用 history
        try:
            hist = ticker.history(period='1d')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except:
            pass

        return None
    except:
        return None

# 計算持股數量
def calculate_holdings(df_stock, category, stock_code=None):
    """計算某分類或特定股票的持有股數"""
    if df_stock.empty:
        return {}

    if stock_code:
        # 有指定股票代碼時，篩選該分類下的特定股票
        filtered = df_stock[(df_stock['所屬分類'] == category) &
                           (df_stock['股票代碼'] == stock_code)]
    else:
        filtered = df_stock[df_stock['所屬分類'] == category]

    if filtered.empty:
        return {}

    holdings = {}
    for _, row in filtered.iterrows():
        code = row['股票代碼']
        shares = row['股數']
        t_type = row['交易類型']

        if code not in holdings:
            holdings[code] = 0

        if t_type == '買進':
            holdings[code] += abs(shares)
        else:
            holdings[code] -= abs(shares)

    # 移除持股為0或負的
    return {k: v for k, v in holdings.items() if v > 0}

# 計算目前市值
def calculate_market_value(df_stock, category, stock_code=None):
    """計算某分類或特定股票的目前市值"""
    holdings = calculate_holdings(df_stock, category, stock_code)

    if not holdings:
        return 0

    total_value = 0
    for code, shares in holdings.items():
        current_price = get_current_price(code)
        if current_price:
            total_value += shares * current_price

    return total_value

# 檢查保守型月度投資計畫

def get_planned_amount(df_plan, df_allocation, category, stock_code=None):
    """根據總預算 × 水平比例計算各類型預算"""
    if df_plan.empty:
        return 0
    total = df_plan['預計投入(USD)'].sum()
    ratio = st.session_state.horizontal_ratio.get(category, 0) / 100
    type_budget = total * ratio

    if category == '進攻型' and stock_code and not df_allocation.empty:
        match = df_allocation[df_allocation['股票代碼'] == stock_code]
        if not match.empty:
            weight = float(match.iloc[0]['比重'])
            return type_budget * (weight / 100)
        return 0
    return type_budget

# 側邊欄選單
page = st.sidebar.radio("選擇功能",
    ["📊 投資總覽", "💵 投資計畫管理", "📈 股票交易記錄", "🎯 選擇權交易記錄", "📉 數據分析"])

# 側邊欄 - 資料載入/匯出
st.sidebar.divider()
st.sidebar.subheader("📁 資料管理")

# 本地模式：輸入資料夾路徑
folder_path = st.sidebar.text_input("本地資料夾路徑", value=st.session_state.data_folder,
    help="輸入包含 CSV 檔案的資料夾路徑")
st.sidebar.caption("💡 編輯表格後請先點頁面內的「儲存」按鈕，再點此處「儲存」到檔案")

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("📂 載入", use_container_width=True, key="sidebar_load_btn"):
        if folder_path:
            success, msg = load_from_folder(folder_path)
            if success:
                st.session_state.data_folder = folder_path
                st.sidebar.success(msg)
                st.rerun()
            else:
                st.sidebar.error(msg)
        else:
            st.sidebar.warning("請輸入資料夾路徑")

with col2:
    if st.button("💾 儲存", use_container_width=True, key="sidebar_save_btn"):
        if folder_path:
            success, msg = save_to_folder(folder_path)
            if success:
                st.sidebar.success(msg)
                st.rerun()  # 重新整理顯示成功訊息
            else:
                st.sidebar.error(msg)
        else:
            st.sidebar.warning("請輸入資料夾路徑")

# 雲端模式：上傳檔案
st.sidebar.markdown("---")
uploaded_files = st.sidebar.file_uploader(
    "上傳 CSV 或 ZIP 檔案",
    type=['csv', 'zip'],
    accept_multiple_files=True,
    help="可一次選取多個 CSV 檔案，或上傳包含所有 CSV 的 ZIP 檔"
)

if uploaded_files:
    if st.sidebar.button("📤 匯入上傳的檔案", use_container_width=True):
        success, msg = load_from_uploaded_files(uploaded_files)
        if success:
            st.sidebar.success(msg)
            st.rerun()
        else:
            st.sidebar.error(msg)

# 一鍵下載所有資料
st.sidebar.markdown("---")
zip_data = export_all_to_zip()
st.sidebar.download_button(
    label="📥 下載所有資料 (ZIP)",
    data=zip_data,
    file_name=f"investment_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
    mime="application/zip",
    use_container_width=True
)

# 顯示資料狀態
if st.session_state.data_loaded:
    st.sidebar.success("✅ 資料已載入")
else:
    st.sidebar.info("💡 請載入或上傳資料")

# ==================== 投資總覽 ====================
if page == "📊 投資總覽":
    st.header("投資資金配置總覽")

    df_plan = st.session_state.df_plan
    df_stock = st.session_state.df_stock
    df_option = st.session_state.df_option
    df_allocation = st.session_state.df_allocation
    df_conservative = st.session_state.df_conservative
    df_lottery = st.session_state.df_lottery

    # 顯示恐懼貪婪指數（儀表板樣式）
    fgi = get_fear_greed_index()
    if fgi:
        value = fgi['value']

        # 建立儀表板圖表
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            title={'text': f"恐懼貪婪指數<br><span style='font-size:14px;color:gray'>{fgi['description']}</span>"},
            gauge={
                'axis': {
                    'range': [0, 100],
                    'tickwidth': 1,
                    'tickmode': 'array',
                    'tickvals': [0, 25, 50, 75, 100],
                    'ticktext': ['0', '25', '50', '75', '100']
                },
                'bar': {'color': "darkblue"},
                'bgcolor': "white",
                'steps': [
                    {'range': [0, 25], 'color': '#e74c3c'},    # 極度恐懼 - 紅色
                    {'range': [25, 45], 'color': '#e67e22'},   # 恐懼 - 橘色
                    {'range': [45, 55], 'color': '#f1c40f'},   # 中性 - 黃色
                    {'range': [55, 75], 'color': '#2ecc71'},   # 貪婪 - 綠色
                    {'range': [75, 100], 'color': '#27ae60'}   # 極度貪婪 - 深綠
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': value
                }
            }
        ))

        fig_gauge.update_layout(
            height=300,
            margin=dict(l=30, r=30, t=60, b=30),
            annotations=[
                dict(
                    text=f"更新: {fgi['last_update']}",
                    x=0.5, y=-0.1,
                    showarrow=False,
                    font=dict(size=10, color='gray')
                )
            ]
        )

        # 使用較窄的欄位顯示
        col_gauge, col_empty = st.columns([1, 2])
        with col_gauge:
            st.plotly_chart(fig_gauge, use_container_width=True)

    elif FEAR_GREED_AVAILABLE:
        st.warning("⚠️ 無法取得恐懼貪婪指數")

    rate_display = get_exchange_rate("USD", "TWD") or USD_RATE
    st.info(f"💡 總預算 = 預計投入 + 已實現損益 | 按水平比例自動分配 | 即時匯率: USD 1 = TWD {rate_display:.2f}")
    
    # 準備圖表數據
    chart_data = []

    # 計算已實現損益（賣出收入 - 賣出股票的均價成本）
    sell_proceeds = calculate_sell_proceeds(df_stock)
    sold_cost = 0
    if not df_stock.empty:
        sell_txns = df_stock[df_stock['交易類型'] == '賣出']
        for cat in ['保守型', '樂透型', '進攻型']:
            cat_sells = sell_txns[sell_txns['所屬分類'] == cat]
            for code in cat_sells['股票代碼'].unique():
                buy_cost = calculate_actual_investment(df_stock, cat, code)
                buy_shares = df_stock[
                    (df_stock['所屬分類'] == cat) &
                    (df_stock['股票代碼'] == code) &
                    (df_stock['交易類型'] == '買進')
                ]['股數'].abs().sum()
                if buy_shares > 0:
                    avg_price = buy_cost / buy_shares
                    sell_shares = cat_sells[cat_sells['股票代碼'] == code]['股數'].abs().sum()
                    sold_cost += avg_price * sell_shares
    realized_profit = sell_proceeds - sold_cost

    # 總預算 = 預計投入 + 已實現損益（賣股賺的錢回到資金池）
    plan_total_raw = df_plan['預計投入(USD)'].sum() if not df_plan.empty else 0
    total_budget = plan_total_raw + realized_profit
    if not df_plan.empty:
        h_ratio = st.session_state.horizontal_ratio

        # 先收集所有股票及其剩餘預算，用於自動分配無資金來源的選擇權
        all_stocks_budget = []  # [(stock_code, type, planned, actual)]

        # 保守型
        conservative_budget = total_budget * h_ratio['保守型'] / 100
        if not df_conservative.empty:
            for _, stock_row in df_conservative.iterrows():
                stock_code = stock_row['股票代碼']
                weight = float(stock_row['比重'])
                stock_planned = conservative_budget * (weight / 100)
                stock_actual = calculate_actual_investment(df_stock, '保守型', stock_code)
                all_stocks_budget.append((stock_code, '保守型', stock_planned, stock_actual))

        # 樂透型
        lottery_budget = total_budget * h_ratio['樂透型'] / 100
        if not df_lottery.empty:
            for _, stock_row in df_lottery.iterrows():
                stock_code = stock_row['股票代碼']
                weight = float(stock_row['比重'])
                stock_planned = lottery_budget * (weight / 100)
                stock_actual = calculate_actual_investment(df_stock, '樂透型', stock_code)
                all_stocks_budget.append((stock_code, '樂透型', stock_planned, stock_actual))

        # 進攻型
        aggressive_budget = total_budget * h_ratio['進攻型'] / 100
        if not df_allocation.empty:
            for _, stock_row in df_allocation.iterrows():
                stock_code = stock_row['股票代碼']
                weight = float(stock_row['比重'])
                stock_planned = aggressive_budget * (weight / 100)
                stock_actual = calculate_actual_investment(df_stock, '進攻型', stock_code)
                all_stocks_budget.append((stock_code, '進攻型', stock_planned, stock_actual))

        # 計算無資金來源的選擇權，按剩餘預算比例分攤到各股票
        unassigned_options = []  # [(cost, direction, ticker, details_dict), ...]
        if not df_option.empty and '資金來源' in df_option.columns:
            df_opt_tmp = df_option.copy()
            df_opt_tmp['資金來源'] = df_opt_tmp['資金來源'].fillna('').astype(str).str.strip()
            df_opt_tmp['到期日'] = pd.to_datetime(df_opt_tmp['到期日'])
            today = pd.Timestamp(datetime.now().date())
            empty_active = df_opt_tmp[
                (df_opt_tmp['資金來源'] == '') &
                (df_opt_tmp['到期日'] >= today)
            ]
            for _, row in empty_active.iterrows():
                direction = row.get('買賣方向', '賣出')
                if direction == '買入':
                    cost = float(row.get('交易金額(USD)', 0))
                    unassigned_options.append(('buy', cost, str(row.get('標的', '')), row.get('買賣權', '')))
                else:
                    cost = float(row.get('保證金(USD)', 0))
                    unassigned_options.append(('sell', cost, str(row.get('標的', '')), row.get('買賣權', '')))

        # 建立 chart_data（所有類型都計算 margin 和 buy_cost）
        for code, stype, planned, actual in all_stocks_budget:
            holdings = calculate_holdings(df_stock, stype, code)
            if actual > 0 and not holdings:
                continue
            stock_margin, margin_details = calculate_option_margin(df_option, code, return_details=True)
            stock_buy_cost, buy_details = calculate_option_buy_cost(df_option, code, return_details=True)
            chart_data.append({
                'name': code, 'type': stype,
                'planned': planned, 'actual': actual,
                'margin': stock_margin, 'margin_details': margin_details,
                'buy_cost': stock_buy_cost, 'buy_details': buy_details
            })

        # 按剩餘預算比例分攤無資金來源的選擇權
        if unassigned_options and chart_data:
            # 計算每檔股票的剩餘預算
            remainders = []
            for d in chart_data:
                rem = d['planned'] - d['actual'] - d.get('margin', 0) - d.get('buy_cost', 0)
                remainders.append(max(rem, 0))
            total_remaining = sum(remainders)

            if total_remaining > 0:
                for opt_type, opt_cost, opt_ticker, opt_cp in unassigned_options:
                    for i, d in enumerate(chart_data):
                        ratio = remainders[i] / total_remaining
                        share = opt_cost * ratio
                        if share <= 0:
                            continue
                        detail = {'ticker': opt_ticker, 'cost': share, 'cp': opt_cp}
                        if opt_type == 'buy':
                            d['buy_cost'] = d.get('buy_cost', 0) + share
                            if 'buy_details' not in d:
                                d['buy_details'] = []
                            d['buy_details'].append(detail)
                        else:
                            d['margin'] = d.get('margin', 0) + share
                            if 'margin_details' not in d:
                                d['margin_details'] = []
                            d['margin_details'].append(detail)

    # 顯示長條圖
    if chart_data:
        # 標題和重新查詢按鈕放在同一行
        col_title, col_btn = st.columns([3, 1])
        with col_title:
            st.subheader("📊 資金分配圖表")
        with col_btn:
            if st.button("🔄 重新查詢現價"):
                st.cache_data.clear()
                st.rerun()

        # 計算目前市值
        market_values = []
        price_fetch_failed = False
        for d in chart_data:
            # 如果 name 不等於 type，表示是個別股票
            if d['name'] != d['type']:
                mv = calculate_market_value(df_stock, d['type'], d['name'])
            else:
                mv = calculate_market_value(df_stock, d['type'])
            market_values.append(mv)
            if mv == 0 and d['name'] != d['type']:
                # 檢查是否有持股但市值為0（可能是取價失敗）
                holdings = calculate_holdings(df_stock, d['type'], d['name'])
                if holdings and sum(holdings.values()) > 0:
                    price_fetch_failed = True

        if price_fetch_failed:
            st.warning("⚠️ 部分股票現價查詢失敗（Yahoo Finance 可能被限速），請稍後點擊「重新查詢現價」")

        # ===== 共用排序：保守型 → 樂透型 → 進攻型 =====
        type_order = {'保守型': 0, '樂透型': 1, '進攻型': 2}
        sorted_chart = sorted(enumerate(chart_data), key=lambda x: (type_order.get(x[1]['type'], 9), x[0]))

        # 按類型分組（保持排序順序）
        type_groups = {}
        for orig_idx, d in sorted_chart:
            t = d['type']
            if t not in type_groups:
                type_groups[t] = {'planned': 0, 'actual': 0, 'mv': 0, 'margin': 0, 'items': []}
            type_groups[t]['planned'] += d['planned']
            type_groups[t]['actual'] += d['actual']
            type_groups[t]['mv'] += market_values[orig_idx]
            type_groups[t]['margin'] += d.get('margin', 0)
            type_groups[t]['items'].append((d, orig_idx))

        total_planned_all = sum(tg['planned'] for tg in type_groups.values())

        type_color_map = {'保守型': '#2ecc71', '樂透型': '#f1c40f', '進攻型': '#3498db'}
        type_icons = {'保守型': '🟢', '樂透型': '🟡', '進攻型': '🔵'}

        # ===== 水平配置：資金分配總覽 (Treemap) =====
        st.markdown("#### 水平配置：資金分配總覽")

        tree_labels = []
        tree_parents = []
        tree_values = []
        tree_colors = []
        tree_hovers = []
        tree_texts = []

        for t in ['保守型', '樂透型', '進攻型']:
            if t not in type_groups:
                continue
            info = type_groups[t]
            pct = (info['planned'] / total_planned_all * 100) if total_planned_all > 0 else 0
            type_label = f"{type_icons.get(t, '')} {t} ({pct:.0f}%)"
            base_color = type_color_map.get(t, '#95a5a6')

            # 類型層：計算該類型整體損益
            type_pnl = info['mv'] - info['actual'] if info['actual'] > 0 and info['mv'] > 0 else 0
            type_pnl_pct = (type_pnl / info['actual'] * 100) if info['actual'] > 0 else 0

            tree_labels.append(type_label)
            tree_parents.append('')
            tree_values.append(0)
            tree_colors.append(base_color)
            type_hover = (
                f"<b>{t}</b><br>"
                f"預算: ${info['planned']:,.0f} ({pct:.0f}%)<br>"
                f"已投入: ${info['actual']:,.0f}<br>"
                f"市值: ${info['mv']:,.0f}"
            )
            if info['actual'] > 0 and info['mv'] > 0:
                type_hover += f"<br>損益: ${type_pnl:+,.0f} ({type_pnl_pct:+.1f}%)"
            tree_hovers.append(type_hover)
            tree_texts.append('')  # 類型層用預設 label

            for d, idx in info['items']:
                mv = market_values[idx]
                margin = d.get('margin', 0)
                buy_cost = d.get('buy_cost', 0)
                remaining = d['planned'] - d['actual'] - margin - buy_cost
                cost = d['actual']

                # 損益計算
                if cost > 0 and mv > 0:
                    item_pnl = mv - cost
                    item_pnl_pct = (item_pnl / cost) * 100
                    pnl_text = f"<br>${item_pnl:+,.0f} ({item_pnl_pct:+.1f}%)"
                else:
                    item_pnl = 0
                    item_pnl_pct = 0
                    pnl_text = ''

                tree_labels.append(d['name'])
                tree_parents.append(type_label)
                tree_values.append(max(d['planned'], 1))
                tree_colors.append(base_color)
                tree_texts.append(pnl_text)

                hover_lines = [f"<b>{d['name']}</b>"]
                hover_lines.append(f"預算: ${d['planned']:,.0f}")
                if cost > 0:
                    hover_lines.append(f"已買入: ${cost:,.0f}")
                if margin > 0:
                    hover_lines.append(f"賣方保證金: ${margin:,.0f}")
                if buy_cost > 0:
                    hover_lines.append(f"買方成本: ${buy_cost:,.0f}")
                hover_lines.append(f"待部署: ${max(remaining, 0):,.0f}")
                if mv > 0:
                    hover_lines.append(f"市值: ${mv:,.0f} ({item_pnl:+,.0f})")
                    hover_lines.append(f"報酬率: {item_pnl_pct:+.1f}%")
                tree_hovers.append("<br>".join(hover_lines))

        fig_tree = go.Figure(go.Treemap(
            labels=tree_labels,
            parents=tree_parents,
            values=tree_values,
            marker=dict(
                colors=tree_colors,
                line=dict(width=2, color='white')
            ),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=tree_hovers,
            textinfo='label+value+text',
            texttemplate='%{label}<br>$%{value:,.0f}%{text}',
            branchvalues='remainder',
            tiling=dict(packing='dice'),
            sort=False
        ))
        fig_tree.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_tree, use_container_width=True)

        # ===== 垂直配置：分批買入進度 =====
        if chart_data:
            st.markdown("#### 垂直配置：分批買入進度")
            st.caption("藍色=已買入 | 橘色=賣方保證金 | 紫色=買方成本 | 灰色=待部署 | ◆=市值 | 紅框=邊際買入價")

            bar_names = []
            bar_bought = []
            bar_sell_margin = []
            bar_buy_cost = []
            bar_remaining = []
            bar_tier_info = []
            bar_types = []
            bar_idx_map = []  # 原始 chart_data index

            for orig_idx, d in sorted_chart:
                stock_code = d['name']
                budget = d['planned']
                bought = d['actual']
                margin = d.get('margin', 0)
                buy_cost = d.get('buy_cost', 0)
                remaining = max(budget - bought - margin - buy_cost, 0)

                bar_names.append(stock_code)
                bar_bought.append(bought)
                bar_sell_margin.append(margin)
                bar_buy_cost.append(buy_cost)
                bar_remaining.append(remaining)
                bar_types.append(d['type'])
                bar_idx_map.append(orig_idx)

                # 進攻型才有邊際配置
                tiers = []
                if d['type'] == '進攻型' and not df_allocation.empty:
                    alloc_row = df_allocation[df_allocation['股票代碼'] == stock_code]
                    if not alloc_row.empty:
                        fair_value = alloc_row.iloc[0]['公允值(USD)']
                        cumulative = 0
                        for j in range(1, 6):
                            m_pct = alloc_row.iloc[0].get(f'邊際{j}(%)', 0) or 0
                            m_wt = alloc_row.iloc[0].get(f'邊際{j}比重(%)', 0) or 0
                            if m_pct > 0 and m_wt > 0:
                                cumulative += m_wt
                                tiers.append({
                                    'price': fair_value * m_pct / 100,
                                    'weight': m_wt,
                                    'cumulative': budget * cumulative / 100
                                })
                bar_tier_info.append(tiers)

            fig_vert = go.Figure()

            # 已買入
            bought_hovers = []
            for i, s in enumerate(bar_names):
                t = bar_types[i]
                orig_i = bar_idx_map[i]
                holdings = calculate_holdings(df_stock, t, s)
                shares = sum(holdings.values()) if holdings else 0
                cost_avg = bar_bought[i] / shares if shares > 0 else 0
                current_p = get_current_price(s) or 0
                mv = market_values[orig_i]
                lines = [f"<b>{s} 已買入</b>"]
                lines.append(f"成本: ${bar_bought[i]:,.0f}")
                if shares > 0:
                    lines.append(f"持股: {shares:.4f} 股" if shares < 1 else f"持股: {shares:.2f} 股")
                    lines.append(f"均價: ${cost_avg:,.2f}")
                if current_p > 0:
                    lines.append(f"現價: ${current_p:,.2f}")
                if mv > 0:
                    pnl = mv - bar_bought[i]
                    lines.append(f"市值: ${mv:,.0f} ({pnl:+,.0f})")
                bought_hovers.append("<br>".join(lines))

            fig_vert.add_trace(go.Bar(
                name='已買入', x=bar_names, y=bar_bought,
                marker_color='#3b82f6',
                text=[f'${int(v):,}' if v > 0 else '' for v in bar_bought],
                textposition='inside', textangle=0,
                hovertemplate='%{customdata}<extra></extra>',
                customdata=bought_hovers
            ))

            # 賣方保證金
            sell_hovers = []
            for i, s in enumerate(bar_names):
                d = chart_data[bar_idx_map[i]]
                margin_details = d.get('margin_details', [])
                lines = [f"<b>{s} 賣方保證金</b>"]
                for detail in margin_details:
                    lines.append(f"標的 {detail['ticker']}: ${detail['margin']:,.0f}")
                if bar_sell_margin[i] > 0:
                    lines.append(f"合計: ${bar_sell_margin[i]:,.0f}")
                sell_hovers.append("<br>".join(lines))

            fig_vert.add_trace(go.Bar(
                name='賣方保證金', x=bar_names, y=bar_sell_margin,
                marker_color='#f59e0b',
                text=[f'${int(v):,}' if v > 0 else '' for v in bar_sell_margin],
                textposition='inside', textangle=0,
                hovertemplate='%{customdata}<extra></extra>',
                customdata=sell_hovers
            ))

            # 買方成本
            buy_hovers = []
            for i, s in enumerate(bar_names):
                d = chart_data[bar_idx_map[i]]
                buy_details = d.get('buy_details', [])
                lines = [f"<b>{s} 買方成本</b>"]
                for detail in buy_details:
                    lines.append(f"{detail['cp']} {detail['ticker']}: ${detail['cost']:,.0f}")
                if bar_buy_cost[i] > 0:
                    lines.append(f"合計: ${bar_buy_cost[i]:,.0f}")
                buy_hovers.append("<br>".join(lines))

            fig_vert.add_trace(go.Bar(
                name='買方成本', x=bar_names, y=bar_buy_cost,
                marker_color='#8b5cf6',
                text=[f'${int(v):,}' if v > 0 else '' for v in bar_buy_cost],
                textposition='inside', textangle=0,
                hovertemplate='%{customdata}<extra></extra>',
                customdata=buy_hovers
            ))

            # 待部署
            remain_hovers = []
            for i, s in enumerate(bar_names):
                budget = chart_data[bar_idx_map[i]]['planned']
                remain_hovers.append(
                    f"<b>{s} 待部署</b><br>"
                    f"${bar_remaining[i]:,.0f} / ${budget:,.0f}"
                )

            fig_vert.add_trace(go.Bar(
                name='待部署', x=bar_names, y=bar_remaining,
                marker_color='#e2e8f0',
                text=[f'${int(v):,}' if v > 0 else '' for v in bar_remaining],
                textposition='inside', textangle=0,
                textfont=dict(color='#64748b'),
                hovertemplate='%{customdata}<extra></extra>',
                customdata=remain_hovers
            ))

            # 市值標記（未實現損益）
            mv_y = []
            mv_colors = []
            mv_hovers = []
            has_mv = False
            for i, s in enumerate(bar_names):
                orig_i = bar_idx_map[i]
                mv = market_values[orig_i]
                cost = bar_bought[i]
                if mv > 0 and cost > 0:
                    has_mv = True
                    mv_y.append(mv)
                    pnl = mv - cost
                    pnl_pct = (pnl / cost) * 100
                    color = '#10b981' if pnl >= 0 else '#ef4444'
                    mv_colors.append(color)
                    mv_hovers.append(
                        f"<b>{s} 市值</b><br>"
                        f"市值: ${mv:,.0f}<br>"
                        f"成本: ${cost:,.0f}<br>"
                        f"損益: ${pnl:+,.0f} ({pnl_pct:+.1f}%)"
                    )
                else:
                    mv_y.append(None)
                    mv_colors.append('#94a3b8')
                    mv_hovers.append('')

            if has_mv:
                fig_vert.add_trace(go.Scatter(
                    name='市值',
                    x=bar_names,
                    y=mv_y,
                    mode='markers',
                    marker=dict(
                        symbol='diamond',
                        size=12,
                        color=mv_colors,
                        line=dict(width=2, color='white')
                    ),
                    hovertemplate='%{customdata}<extra></extra>',
                    customdata=mv_hovers
                ))

            # 進攻型邊際價格標注
            for i, s in enumerate(bar_names):
                for tier in bar_tier_info[i]:
                    fig_vert.add_annotation(
                        x=s, y=tier['cumulative'],
                        text=f"${tier['price']:.0f} ({tier['weight']:.0f}%)",
                        showarrow=False,
                        font=dict(size=9, color='#dc2626'),
                        bgcolor='rgba(255,255,255,0.85)',
                        bordercolor='#dc2626', borderwidth=1, borderpad=2,
                        xshift=0, yshift=8
                    )

            max_mv = max([v for v in mv_y if v is not None], default=0) if has_mv else 0
            max_budget = max(max([d['planned'] for d in chart_data]) if chart_data else 0, max_mv)
            fig_vert.update_layout(
                barmode='stack',
                xaxis_title='股票',
                yaxis_title='金額 (USD)',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                height=500,
                margin=dict(t=60, b=60),
                yaxis=dict(range=[0, max_budget * 1.2])
            )
            fig_vert.update_yaxes(gridcolor='rgba(0,0,0,0.1)')
            st.plotly_chart(fig_vert, use_container_width=True)

            # 進攻型邊際價格文字摘要
            aggressive_items = [(d, i) for i, d in enumerate(chart_data) if d['type'] == '進攻型']
            if aggressive_items and not df_allocation.empty:
                st.caption("**邊際買入價一覽**")
                for d, idx in aggressive_items:
                    stock_code = d['name']
                    alloc_row = df_allocation[df_allocation['股票代碼'] == stock_code]
                    if not alloc_row.empty:
                        fair_value = alloc_row.iloc[0]['公允值(USD)']
                        current_p = get_current_price(stock_code) or 0
                        prices = []
                        for j in range(1, 6):
                            m_pct = alloc_row.iloc[0].get(f'邊際{j}(%)', 0) or 0
                            if m_pct > 0:
                                prices.append(f"{fair_value * m_pct / 100:.0f}")
                        price_str = " / ".join(prices)
                        current_str = f"現價 {current_p:,.2f}" if current_p > 0 else "現價 -"
                        st.text(f"{stock_code}: {current_str} | 邊際價: {price_str}")
        
        # 詳細數據表格
        st.subheader("📋 詳細數據")

        # 計算選擇權損益（區分已實現/未實現）
        opt_realized = 0
        opt_unrealized = 0
        opt_unrealized_details = []
        if not df_option.empty:
            df_opt_calc = df_option.copy()
            if '到期日' in df_opt_calc.columns and '收支金額(USD)' in df_opt_calc.columns:
                df_opt_calc['到期日'] = pd.to_datetime(df_opt_calc['到期日'])
                today = pd.Timestamp(datetime.now().date())
                expired = df_opt_calc[df_opt_calc['到期日'] < today]
                opt_realized = expired['收支金額(USD)'].sum() if not expired.empty else 0
                opt_unrealized, opt_unrealized_details = calculate_options_unrealized_pnl(df_option)
            elif '收支金額(USD)' in df_opt_calc.columns:
                opt_realized = df_opt_calc['收支金額(USD)'].sum()
            elif '總成本(USD)' in df_opt_calc.columns:
                opt_realized = df_opt_calc['總成本(USD)'].sum()
        opt_total = opt_realized + opt_unrealized

        # 計算全部資金（預計投入 + 選擇權收入）用於佔比計算
        total_planned = sum([d['planned'] for d in chart_data])
        grand_total = total_planned + opt_total

        # 計算每個項目的報酬率
        def get_return_info(d, idx):
            """計算報酬率資訊"""
            actual = d['actual']
            mv = market_values[idx]
            if actual > 0 and mv > 0:
                profit = mv - actual
                return_rate = (profit / actual) * 100
                return profit, return_rate
            return 0, 0

        # 按類型分組顯示
        col1, col2, col3 = st.columns(3)

        # 保守型
        conservative_data = [(d, i) for i, d in enumerate(chart_data) if d['type'] == '保守型']
        if conservative_data:
            with col1:
                st.write("**🟢 保守型**")
                for d, idx in conservative_data:
                    profit, return_rate = get_return_info(d, idx)
                    mv = market_values[idx]
                    exec_rate = (d['actual'] / d['planned'] * 100) if d['planned'] > 0 else 0

                    # 使用 st.metric 原生箭頭：正數綠色向上、負數紅色向下
                    delta_str = f"{return_rate:+.1f}%"

                    st.metric(d['name'], f"${mv:,.0f}" if mv > 0 else f"${d['actual']:,.0f}", delta=delta_str)
                    st.caption(f"成本: ${d['actual']:,.0f} | 損益: ${profit:,.0f}")
                    st.progress(min(exec_rate / 100, 1.0), text=f"完成率: {exec_rate:.0f}%")

        # 樂透型
        lottery_data = [(d, i) for i, d in enumerate(chart_data) if d['type'] == '樂透型']
        if lottery_data:
            with col2:
                st.write("**🟡 樂透型**")
                for d, idx in lottery_data:
                    profit, return_rate = get_return_info(d, idx)
                    mv = market_values[idx]
                    exec_rate = (d['actual'] / d['planned'] * 100) if d['planned'] > 0 else 0

                    # 使用 st.metric 原生箭頭：正數綠色向上、負數紅色向下
                    delta_str = f"{return_rate:+.1f}%"

                    st.metric(d['name'], f"${mv:,.0f}" if mv > 0 else f"${d['actual']:,.0f}", delta=delta_str)
                    st.caption(f"成本: ${d['actual']:,.0f} | 損益: ${profit:,.0f}")
                    st.progress(min(exec_rate / 100, 1.0), text=f"完成率: {exec_rate:.0f}%")

        # 進攻型統計
        aggressive_data = [(d, i) for i, d in enumerate(chart_data) if d['type'] == '進攻型']
        if aggressive_data:
            with col3:
                st.write("**🔵 進攻型**")
                total_agg_held = sum([d['actual'] for d, _ in aggressive_data])
                total_agg_all_buy = calculate_actual_investment(df_stock, '進攻型')
                total_agg_mv = sum([market_values[idx] for _, idx in aggressive_data])
                total_agg_sell = calculate_sell_proceeds(df_stock, '進攻型')
                total_agg_planned = sum([d['planned'] for d, _ in aggressive_data])
                agg_unrealized = total_agg_mv - total_agg_held
                agg_realized = total_agg_sell - (total_agg_all_buy - total_agg_held)
                total_agg_profit = agg_unrealized + agg_realized
                total_agg_return = (total_agg_profit / total_agg_held * 100) if total_agg_held > 0 else 0
                total_agg_exec = (total_agg_held / total_agg_planned * 100) if total_agg_planned > 0 else 0

                # 使用 st.metric 原生箭頭：正數綠色向上、負數紅色向下
                delta_str = f"{total_agg_return:+.1f}%"

                st.metric("總計", f"${total_agg_mv:,.0f}" if total_agg_mv > 0 else f"${total_agg_held:,.0f}", delta=delta_str)
                st.caption(f"成本: ${total_agg_held:,.0f} | 損益: ${total_agg_profit:,.0f}")
                st.progress(min(total_agg_exec / 100, 1.0), text=f"完成率: {total_agg_exec:.0f}%")

        # 進攻型各股明細
        if aggressive_data:
            st.write("**進攻型各股明細**")
            cols = st.columns(min(len(aggressive_data), 5))
            for i, (d, idx) in enumerate(aggressive_data):
                with cols[i % 5]:
                    profit, return_rate = get_return_info(d, idx)
                    mv = market_values[idx]

                    # 使用 st.metric 原生箭頭：正數綠色向上、負數紅色向下
                    delta_str = f"{return_rate:+.1f}%"

                    st.metric(d['name'], f"${mv:,.0f}" if mv > 0 else "-", delta=delta_str)
                    st.caption(f"成本: ${d['actual']:,.0f} | 損益: ${profit:,.0f}")

        # 選擇權
        st.divider()
        st.subheader("🟣 選擇權投資")

        # 篩選未到期的選擇權部位
        total_margin = 0
        active_options = pd.DataFrame()
        if not df_option.empty:
            df_option_calc = df_option.copy()
            df_option_calc['到期日'] = pd.to_datetime(df_option_calc['到期日'])
            today = pd.Timestamp(datetime.now().date())
            active_options = df_option_calc[df_option_calc['到期日'] >= today]

            # 被壓住的保證金（僅賣方部位）
            if '保證金(USD)' in df_option_calc.columns:
                active_sold = active_options[active_options['買賣方向'] == '賣出']
                total_margin = active_sold['保證金(USD)'].sum() if not active_sold.empty else 0

        # 買方部位成本（buy call / buy put 的權利金支出）
        buy_cost = 0
        if not active_options.empty:
            active_bought = active_options[active_options['買賣方向'] == '買入']
            if not active_bought.empty and '交易金額(USD)' in active_bought.columns:
                buy_cost = active_bought['交易金額(USD)'].sum()

        # 計算選擇權報酬率
        if total_margin > 0:
            opt_return_rate = (opt_total / total_margin) * 100
            if opt_return_rate > 0:
                opt_return_str = f"📈 +{opt_return_rate:.1f}%"
            elif opt_return_rate < 0:
                opt_return_str = f"📉 {opt_return_rate:.1f}%"
            else:
                opt_return_str = "0%"
        else:
            opt_return_rate = 0
            opt_return_str = "-"

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("已實現損益", f"${opt_realized:,.2f}")
        opt_unrealized_delta = f"{opt_unrealized:+,.2f}" if opt_unrealized != 0 else None
        col2.metric("未實現損益", f"${opt_unrealized:,.2f}", delta=opt_unrealized_delta)
        if total_margin > 0:
            col3.metric("🔒 賣方保證金", f"${total_margin:,.0f}")
        if buy_cost > 0:
            col4.metric("🔵 買方成本", f"${buy_cost:,.0f}")
        if total_margin > 0:
            col5.metric("報酬率", opt_return_str)

        # 未到期部位明細
        if not active_options.empty:
            st.caption("**未到期部位**")
            display_cols = ['標的', '買賣權', '買賣方向', '履約價', '到期日', '口數', '權利金', '保證金(USD)', '資金來源']
            display_active = active_options[[c for c in display_cols if c in active_options.columns]].copy()
            display_active['到期日'] = display_active['到期日'].dt.strftime('%Y-%m-%d')
            # 加入現價和未實現損益欄位
            if opt_unrealized_details:
                details_map = {}
                for d in opt_unrealized_details:
                    key = (d['標的'], d['履約價'], d['到期日'], d['買賣方向'])
                    details_map[key] = d
                current_prices = []
                unrealized_pnls = []
                for _, row in display_active.iterrows():
                    key = (row.get('標的', ''), row.get('履約價', 0), row.get('到期日', ''), row.get('買賣方向', ''))
                    detail = details_map.get(key)
                    if detail and detail['現價'] is not None:
                        current_prices.append(f"${detail['現價']:.2f}")
                        unrealized_pnls.append(f"${detail['未實現損益']:,.2f}")
                    else:
                        current_prices.append('-')
                        unrealized_pnls.append('-')
                display_active['現價'] = current_prices
                display_active['未實現損益'] = unrealized_pnls
            st.dataframe(display_active, use_container_width=True, hide_index=True)

        # 總計
        st.divider()
        st.subheader("📊 投資組合總覽")

        # 持有中成本（不含已賣出）
        total_held_cost = sum([d['actual'] for d in chart_data])
        # 持有中的市值
        total_market_value = sum(market_values)
        # 未實現損益 = 市值 - 持有成本
        unrealized_profit = total_market_value - total_held_cost
        # 已實現損益（前面已計算: realized_profit = sell_proceeds - sold_cost）
        # 股票損益 = 未實現 + 已實現
        stock_profit = unrealized_profit + realized_profit
        total_profit = stock_profit + opt_total  # 股票報酬 + 選擇權收支
        total_return_rate = (total_profit / total_held_cost * 100) if total_held_cost > 0 else 0

        # 執行率 = (持有成本 + 被壓住保證金) / 總預算
        overall_exec_rate = ((total_held_cost + total_margin) / total_planned * 100) if total_planned > 0 else 0

        col1, col2, col3, col4, col5 = st.columns(5)
        budget_detail = f"投入 ${plan_total_raw:,.0f}" if realized_profit != 0 else ""
        if realized_profit != 0:
            budget_detail += f" + 已實現 ${realized_profit:,.0f}"
        col1.metric("📋 總預算", f"${total_planned:,.0f}")
        if budget_detail:
            st.caption(budget_detail)
        col2.metric("💵 總成本", f"${total_held_cost:,.0f}")
        col3.metric("💰 總市值", f"${total_market_value:,.0f}" if total_market_value > 0 else "-")

        # 總報酬率：股票報酬 + 選擇權收支
        delta_str = f"{total_return_rate:+.1f}%"
        col4.metric("📈 總報酬率", f"${total_profit:,.0f}", delta=delta_str)
        stock_unrealized_str = f"${unrealized_profit:,.0f}"
        opt_unrealized_str = f"${opt_unrealized:,.0f}"
        stock_realized_str = f"${realized_profit:,.0f}"
        opt_realized_str = f"${opt_realized:,.0f}"
        st.caption(f"未實現: 股票 {stock_unrealized_str} + 選擇權 {opt_unrealized_str} | 已實現: 股票 {stock_realized_str} + 選擇權 {opt_realized_str}")

        # 執行率
        col5.metric("🎯 執行率", f"{overall_exec_rate:.1f}%")
        st.progress(min(overall_exec_rate / 100, 1.0), text=f"執行率: {overall_exec_rate:.0f}% (成本 ${total_held_cost:,.0f} + 保證金 ${total_margin:,.0f}) / 預算 ${total_planned:,.0f}")
    
    else:
        st.warning("⚠️ 請先在「投資計畫管理」設定投資計畫")

# ==================== 投資計畫管理 ====================
elif page == "💵 投資計畫管理":
    st.header("投資計畫管理")
    df_plan = st.session_state.df_plan.copy()
    df_allocation = st.session_state.df_allocation.copy()

    # ===== 水平配置比例 =====
    st.subheader("📐 水平配置比例")
    st.caption("設定各投資類型的資金佔比，總和須為 100%")
    h_ratio = st.session_state.horizontal_ratio
    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        r_conservative = st.number_input("🟢 保守型 (%)", value=h_ratio['保守型'], min_value=0.0, max_value=100.0, step=5.0, key="ratio_conservative")
    with col_r2:
        r_lottery = st.number_input("🟡 樂透型 (%)", value=h_ratio['樂透型'], min_value=0.0, max_value=100.0, step=5.0, key="ratio_lottery")
    with col_r3:
        r_aggressive = st.number_input("🔵 進攻型 (%)", value=h_ratio['進攻型'], min_value=0.0, max_value=100.0, step=5.0, key="ratio_aggressive")

    ratio_sum = r_conservative + r_lottery + r_aggressive
    if abs(ratio_sum - 100) > 0.01:
        st.error(f"⚠️ 比例總和 {ratio_sum:.0f}%，須為 100%")
    else:
        st.success(f"✅ 比例總和: {ratio_sum:.0f}%")
    st.session_state.horizontal_ratio = {'保守型': r_conservative, '樂透型': r_lottery, '進攻型': r_aggressive}

    # ===== 投入金額 =====
    st.divider()
    st.subheader("📋 表格1: 投入金額")
    st.caption("記錄每次投入的總金額，系統會自動按水平比例分配")

    # 向下相容：載入舊格式時移除投資類型欄
    if '投資類型' in df_plan.columns:
        df_plan = df_plan.drop(columns=['投資類型'])

    if df_plan.empty:
        df_plan = pd.DataFrame({
            '時間': [datetime.now().date()],
            '預計投入(USD)': [0.0],
            '匯率': [USD_RATE]
        })
    else:
        df_plan['時間'] = pd.to_datetime(df_plan['時間']).dt.date

    edited_plan = st.data_editor(df_plan, num_rows="dynamic", use_container_width=True,
        column_config={
            "時間": st.column_config.DateColumn("時間", required=True),
            "預計投入(USD)": st.column_config.NumberColumn("預計投入(USD)",
                format="$%.2f", min_value=0, required=True),
            "匯率": st.column_config.NumberColumn("匯率(USD→TWD)",
                format="%.2f", min_value=0, help=f"即時匯率: {get_exchange_rate('USD', 'TWD') or USD_RATE:.2f}")
        }, key="plan_editor")

    # 自動儲存到 session_state
    edited_plan['時間'] = edited_plan['時間'].astype(str)
    st.session_state.df_plan = edited_plan

    # 顯示各類型預算分配
    plan_total = edited_plan['預計投入(USD)'].sum()
    if plan_total > 0:
        h = st.session_state.horizontal_ratio
        st.info(
            f"💡 總預算 ${plan_total:,.0f} → "
            f"保守型 ${plan_total * h['保守型'] / 100:,.0f} ({h['保守型']:.0f}%) | "
            f"樂透型 ${plan_total * h['樂透型'] / 100:,.0f} ({h['樂透型']:.0f}%) | "
            f"進攻型 ${plan_total * h['進攻型'] / 100:,.0f} ({h['進攻型']:.0f}%)"
        )

    
    st.divider()
    st.subheader("🔵 表格2: 進攻型股票配置")
    st.info("💡 公允值=合理價格 | 邊際1-5=分批買入的價格比例 (例如: 公允值$300, 邊際80%→$240買入) | 比重1-5=每檔買入的資金比重")
    
    if df_allocation.empty:
        df_allocation = pd.DataFrame({
            '股票代碼': ['TSLA'],
            '比重': [100.0],
            '公允值(USD)': [300.0],
            '邊際1(%)': [100.0],
            '邊際2(%)': [93.0],
            '邊際3(%)': [80.0],
            '邊際4(%)': [70.0],
            '邊際5(%)': [50.0],
            '邊際1比重(%)': [30.0],
            '邊際2比重(%)': [30.0],
            '邊際3比重(%)': [10.0],
            '邊際4比重(%)': [10.0],
            '邊際5比重(%)': [20.0]
        })

    edited_alloc = st.data_editor(df_allocation, num_rows="dynamic", use_container_width=True,
        column_config={
            "股票代碼": st.column_config.TextColumn("代碼", required=True),
            "比重": st.column_config.NumberColumn("比重(%)", format="%.0f", required=True, default=0.0),
            "公允值(USD)": st.column_config.NumberColumn("公允值", format="$%.0f", default=0.0),
            "邊際1(%)": st.column_config.NumberColumn("邊際1", format="%.0f%%", default=100.0),
            "邊際2(%)": st.column_config.NumberColumn("邊際2", format="%.0f%%", default=93.0),
            "邊際3(%)": st.column_config.NumberColumn("邊際3", format="%.0f%%", default=80.0),
            "邊際4(%)": st.column_config.NumberColumn("邊際4", format="%.0f%%", default=70.0),
            "邊際5(%)": st.column_config.NumberColumn("邊際5", format="%.0f%%", default=50.0),
            "邊際1比重(%)": st.column_config.NumberColumn("比重1", format="%.0f%%", default=30.0),
            "邊際2比重(%)": st.column_config.NumberColumn("比重2", format="%.0f%%", default=30.0),
            "邊際3比重(%)": st.column_config.NumberColumn("比重3", format="%.0f%%", default=10.0),
            "邊際4比重(%)": st.column_config.NumberColumn("比重4", format="%.0f%%", default=10.0),
            "邊際5比重(%)": st.column_config.NumberColumn("比重5", format="%.0f%%", default=20.0)
        }, key="allocation_editor")

    total_weight = edited_alloc['比重'].sum()
    if total_weight != 100:
        st.warning(f"⚠️ 總比重: {total_weight}%")
    else:
        st.success(f"✅ 總比重: {total_weight}%")

    # 自動儲存到 session_state
    st.session_state.df_allocation = edited_alloc

    # 顯示買入參考價格表
    # 顯示邊際價格（文字格式）
    if not edited_alloc.empty:
        st.write("**📋 五檔買入參考價格**")
        for _, row in edited_alloc.iterrows():
            code = row['股票代碼']
            fair = row['公允值(USD)']
            if fair > 0:
                # 取得現價
                current_price = get_current_price(code)
                # 計算邊際價格
                margin_prices = []
                for i in range(1, 6):
                    margin = row[f'邊際{i}(%)']
                    if margin > 0:
                        margin_prices.append(f"{fair * margin / 100:.2f}")
                if margin_prices:
                    price_str = " / ".join(margin_prices)
                    st.write(f"**{code}**: 現價 {current_price:.2f} | 邊際價: {price_str}")

    # ==================== 保守型股票配置 ====================
    st.divider()
    st.subheader("🟢 表格3: 保守型股票配置")
    st.info("💡 保守型通常配置 ETF 或穩定型股票，如 VOO、VTI、BND 等")

    df_conservative = st.session_state.df_conservative.copy()
    if df_conservative.empty:
        df_conservative = pd.DataFrame({
            '股票代碼': ['VOO'],
            '比重': [100.0],
            '說明': ['S&P 500 ETF']
        })

    edited_conservative = st.data_editor(df_conservative, num_rows="dynamic", use_container_width=True,
        column_config={
            "股票代碼": st.column_config.TextColumn("代碼", required=True),
            "比重": st.column_config.NumberColumn("比重(%)", format="%.0f", required=True),
            "說明": st.column_config.TextColumn("說明")
        }, key="conservative_editor")

    conservative_weight = edited_conservative['比重'].sum()
    if conservative_weight != 100:
        st.warning(f"⚠️ 保守型總比重: {conservative_weight}%")
    else:
        st.success(f"✅ 保守型總比重: {conservative_weight}%")

    # 自動儲存到 session_state
    st.session_state.df_conservative = edited_conservative

    # ==================== 樂透型股票配置 ====================
    st.divider()
    st.subheader("🟡 表格4: 樂透型股票配置")
    st.info("💡 樂透型可配置高風險高報酬的標的，如小型成長股、加密貨幣等")

    df_lottery = st.session_state.df_lottery.copy()
    if df_lottery.empty:
        df_lottery = pd.DataFrame({
            '股票代碼': ['BTC'],
            '比重': [100.0],
            '說明': ['比特幣']
        })

    edited_lottery = st.data_editor(df_lottery, num_rows="dynamic", use_container_width=True,
        column_config={
            "股票代碼": st.column_config.TextColumn("代碼", required=True),
            "比重": st.column_config.NumberColumn("比重(%)", format="%.0f", required=True),
            "說明": st.column_config.TextColumn("說明")
        }, key="lottery_editor")

    lottery_weight = edited_lottery['比重'].sum()
    if lottery_weight != 100:
        st.warning(f"⚠️ 樂透型總比重: {lottery_weight}%")
    else:
        st.success(f"✅ 樂透型總比重: {lottery_weight}%")

    # 自動儲存到 session_state
    st.session_state.df_lottery = edited_lottery

# ==================== 股票交易記錄 ====================
elif page == "📈 股票交易記錄":
    st.header("股票交易記錄")
    df_stock = st.session_state.df_stock.copy()

    if not df_stock.empty:
        df_stock['交易日期'] = pd.to_datetime(df_stock['交易日期']).dt.date
        df_stock['股數'] = df_stock['股數'].astype(float)
        df_stock['手續費(USD)'] = df_stock['手續費(USD)'].fillna(0.0)
        df_stock['交易稅(USD)'] = df_stock['交易稅(USD)'].fillna(0.0)
        df_stock['用途說明'] = df_stock['用途說明'].fillna('')
        df_stock['備註'] = df_stock['備註'].fillna('')

    # === 編輯狀態 ===
    edit_idx = st.session_state.get('stock_edit_idx', None)
    is_editing = edit_idx is not None and not df_stock.empty and edit_idx < len(df_stock)

    if is_editing:
        r = df_stock.iloc[edit_idx]
        st.subheader(f"✏️ 編輯紀錄 #{edit_idx + 1} ({r['股票代碼']})")
        d = {
            'date': r['交易日期'], 'type': r['交易類型'], 'cat': r['所屬分類'],
            'code': str(r['股票代碼']), 'shares': abs(float(r['股數'])),
            'price': float(r['成交價格(USD)']),
            'fee': float(r['手續費(USD)']), 'tax': float(r['交易稅(USD)']),
            'note': str(r['用途說明']), 'memo': str(r['備註'])
        }
    else:
        st.subheader("📝 新增交易")
        d = {
            'date': datetime.now().date(), 'type': '買進', 'cat': '進攻型',
            'code': '', 'shares': 0.0, 'price': 0.0,
            'fee': 0.0, 'tax': 0.0, 'note': '', 'memo': ''
        }

    with st.form(f"stock_form_{edit_idx}", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns(4)
        f_date = c1.date_input("交易日期", value=d['date'])
        f_type = c2.selectbox("交易類型", ["買進", "賣出"], index=["買進", "賣出"].index(d['type']))
        f_cat = c3.selectbox("所屬分類", ["保守型", "進攻型", "樂透型"],
                             index=["保守型", "進攻型", "樂透型"].index(d['cat']))
        f_code = c4.text_input("股票代碼", value=d['code'])

        c5, c6, c7, c8 = st.columns(4)
        f_shares = c5.number_input("股數", value=d['shares'], min_value=0.0, format="%.4f")
        f_price = c6.number_input("成交價格(USD)", value=d['price'], min_value=0.0, format="%.2f")
        f_fee = c7.number_input("手續費", value=d['fee'], min_value=0.0, format="%.2f",
                                help="Firstrade 免手續費")
        f_tax = c8.number_input("交易稅", value=d['tax'], min_value=0.0, format="%.2f",
                                help="Firstrade 免交易稅")

        c9, c10 = st.columns(2)
        f_note = c9.text_input("用途說明", value=d['note'])
        f_memo = c10.text_input("備註", value=d['memo'])

        trade_amt = f_shares * f_price
        st.caption(f"交易金額: ${trade_amt:,.2f}")

        cb1, cb2, cb3, cb4 = st.columns(4)
        btn_add = cb1.form_submit_button("➕ 新增", type="primary" if not is_editing else "secondary")
        btn_update = cb2.form_submit_button("✏️ 更新", type="primary" if is_editing else "secondary")
        btn_delete = cb3.form_submit_button("🗑️ 刪除")
        btn_clear = cb4.form_submit_button("🔄 清除")

    def _build_stock_row():
        return {
            '交易日期': str(f_date),
            '交易類型': f_type,
            '所屬分類': f_cat,
            '股票代碼': f_code.upper().strip(),
            '股數': f_shares if f_type == '買進' else -f_shares,
            '成交價格(USD)': f_price,
            '手續費(USD)': f_fee,
            '交易稅(USD)': f_tax if f_type == '賣出' else 0.0,
            '用途說明': f_note,
            '備註': f_memo
        }

    if btn_add and f_code.strip() and f_shares > 0:
        new_row = _build_stock_row()
        df = st.session_state.df_stock
        st.session_state.df_stock = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.stock_edit_idx = None
        st.rerun()

    if btn_update and is_editing:
        row_data = _build_stock_row()
        df = st.session_state.df_stock
        for k, v in row_data.items():
            df.at[edit_idx, k] = v
        st.session_state.df_stock = df
        st.session_state.stock_edit_idx = None
        st.rerun()

    if btn_delete and is_editing:
        df = st.session_state.df_stock
        st.session_state.df_stock = df.drop(index=edit_idx).reset_index(drop=True)
        st.session_state.stock_edit_idx = None
        st.rerun()

    if btn_clear:
        st.session_state.stock_edit_idx = None
        st.rerun()

    # === 已有紀錄 ===
    st.divider()
    st.subheader("📋 交易紀錄")
    st.caption("點選紀錄可帶入上方表單編輯")

    if not df_stock.empty:
        display_df = df_stock[['交易日期', '交易類型', '所屬分類', '股票代碼', '股數', '成交價格(USD)']].copy()
        display_df['股數'] = display_df['股數'].abs()

        event = st.dataframe(
            display_df, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row",
            key="stock_table_select"
        )

        if event.selection.rows:
            sel = event.selection.rows[0]
            if st.session_state.get('stock_edit_idx') != sel:
                st.session_state.stock_edit_idx = sel
                st.rerun()

        # 統計
        st.divider()
        total_buy = 0
        total_sell = 0
        for _, row in df_stock.iterrows():
            shares = abs(row['股數'])
            price = row['成交價格(USD)']
            amt = shares * price
            fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else 0
            if row['交易類型'] == '買進':
                total_buy += amt + fee
            else:
                tax = row['交易稅(USD)'] if pd.notna(row['交易稅(USD)']) and row['交易稅(USD)'] > 0 else 0
                total_sell += amt - fee - tax

        col1, col2 = st.columns(2)
        col1.metric("總買入金額", f"${total_buy:,.2f}")
        col2.metric("總賣出金額", f"${total_sell:,.2f}")
    else:
        st.info("尚無交易紀錄，請使用上方表單新增")

# ==================== 選擇權交易記錄 ====================
elif page == "🎯 選擇權交易記錄":
    st.header("選擇權交易記錄")
    df_option = st.session_state.df_option.copy()

    if not df_option.empty:
        df_option['交易日期'] = pd.to_datetime(df_option['交易日期']).dt.date
        df_option['到期日'] = pd.to_datetime(df_option['到期日']).dt.date
        df_option['資金來源'] = df_option['資金來源'].fillna('').astype(str)
        df_option['策略說明'] = df_option['策略說明'].fillna('').astype(str)
        if '保證金(USD)' not in df_option.columns:
            df_option['保證金(USD)'] = 0.0
        if '買賣方向' not in df_option.columns:
            df_option['買賣方向'] = '賣出'

    # === 編輯狀態 ===
    opt_edit_idx = st.session_state.get('option_edit_idx', None)
    opt_is_editing = opt_edit_idx is not None and not df_option.empty and opt_edit_idx < len(df_option)

    if opt_is_editing:
        r = df_option.iloc[opt_edit_idx]
        st.subheader(f"✏️ 編輯紀錄 #{opt_edit_idx + 1} ({r['標的']})")
        od = {
            'date': r['交易日期'], 'prod': r['商品類型'], 'ticker': str(r['標的']),
            'strike': float(r['履約價']), 'expiry': r['到期日'],
            'cp': r['買賣權'], 'bs': r['買賣方向'],
            'contracts': int(r['口數']), 'premium': float(r['權利金']),
            'fee': float(r['手續費(USD)']), 'margin': float(r['保證金(USD)']),
            'source': str(r['資金來源']), 'strategy': str(r['策略說明'])
        }
    else:
        st.subheader("📝 新增選擇權交易")
        od = {
            'date': datetime.now().date(), 'prod': '股票選擇權', 'ticker': '',
            'strike': 0.0, 'expiry': datetime.now().date(),
            'cp': '賣權(Put)', 'bs': '賣出',
            'contracts': 1, 'premium': 0.0,
            'fee': 0.0, 'margin': 0.0,
            'source': '', 'strategy': ''
        }

    with st.form(f"option_form_{opt_edit_idx}", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns(4)
        fo_date = c1.date_input("交易日期", value=od['date'])
        fo_prod = c2.selectbox("商品類型", ["股票選擇權", "指數選擇權", "其他"],
                               index=["股票選擇權", "指數選擇權", "其他"].index(od['prod']))
        fo_ticker = c3.text_input("標的", value=od['ticker'])
        fo_cp = c4.selectbox("買賣權", ["買權(Call)", "賣權(Put)"],
                             index=["買權(Call)", "賣權(Put)"].index(od['cp']))

        c5, c6, c7, c8 = st.columns(4)
        fo_strike = c5.number_input("履約價", value=od['strike'], min_value=0.0, format="%.2f")
        fo_expiry = c6.date_input("到期日", value=od['expiry'])
        fo_bs = c7.selectbox("買賣方向", ["買入", "賣出"],
                             index=["買入", "賣出"].index(od['bs']))
        fo_contracts = c8.number_input("口數", value=od['contracts'], min_value=0, step=1)

        c9, c10, c11, c12 = st.columns(4)
        fo_premium = c9.number_input("權利金", value=od['premium'], min_value=0.0, format="%.2f")
        fo_fee = c10.number_input("手續費", value=od['fee'], min_value=0.0, format="%.2f",
                                  help="Firstrade 選擇權手續費 $0.65/口")
        fo_margin = c11.number_input("保證金", value=od['margin'], min_value=0.0, format="%.0f")
        fo_source = c12.text_input("資金來源", value=od['source'], help="此保證金佔用哪檔股票的資金")

        fo_strategy = st.text_input("策略說明", value=od['strategy'])

        opt_trade_amt = fo_contracts * fo_premium * 100
        opt_income = opt_trade_amt if fo_bs == '賣出' else -opt_trade_amt
        st.caption(f"交易金額: ${opt_trade_amt:,.2f} | 收支: ${opt_income:+,.2f}")

        cb1, cb2, cb3, cb4 = st.columns(4)
        ob_add = cb1.form_submit_button("➕ 新增", type="primary" if not opt_is_editing else "secondary")
        ob_update = cb2.form_submit_button("✏️ 更新", type="primary" if opt_is_editing else "secondary")
        ob_delete = cb3.form_submit_button("🗑️ 刪除")
        ob_clear = cb4.form_submit_button("🔄 清除")

    def _build_option_row():
        t_amt = fo_contracts * fo_premium * 100
        income = t_amt if fo_bs == '賣出' else -t_amt
        return {
            '交易日期': str(fo_date), '商品類型': fo_prod,
            '標的': fo_ticker.upper().strip(), '履約價': fo_strike,
            '到期日': str(fo_expiry), '買賣權': fo_cp, '買賣方向': fo_bs,
            '口數': fo_contracts, '權利金': fo_premium,
            '交易金額(USD)': t_amt, '手續費(USD)': fo_fee,
            '保證金(USD)': fo_margin, '總成本(USD)': t_amt + fo_fee,
            '收支金額(USD)': income,
            '資金來源': fo_source.upper().strip(), '策略說明': fo_strategy
        }

    if ob_add and fo_ticker.strip() and fo_contracts > 0:
        new_row = _build_option_row()
        df = st.session_state.df_option
        st.session_state.df_option = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.option_edit_idx = None
        st.rerun()

    if ob_update and opt_is_editing:
        row_data = _build_option_row()
        df = st.session_state.df_option
        for k, v in row_data.items():
            df.at[opt_edit_idx, k] = v
        st.session_state.df_option = df
        st.session_state.option_edit_idx = None
        st.rerun()

    if ob_delete and opt_is_editing:
        df = st.session_state.df_option
        st.session_state.df_option = df.drop(index=opt_edit_idx).reset_index(drop=True)
        st.session_state.option_edit_idx = None
        st.rerun()

    if ob_clear:
        st.session_state.option_edit_idx = None
        st.rerun()

    # === 已有紀錄 ===
    st.divider()
    st.subheader("📋 選擇權紀錄")
    st.caption("點選紀錄可帶入上方表單編輯")

    if not df_option.empty:
        display_opt = df_option[['交易日期', '標的', '履約價', '到期日', '買賣權',
                                 '買賣方向', '口數', '權利金', '保證金(USD)', '資金來源']].copy()

        opt_event = st.dataframe(
            display_opt, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row",
            key="option_table_select"
        )

        if opt_event.selection.rows:
            sel = opt_event.selection.rows[0]
            if st.session_state.get('option_edit_idx') != sel:
                st.session_state.option_edit_idx = sel
                st.rerun()
    else:
        st.info("尚無選擇權紀錄，請使用上方表單新增")

# ==================== 數據分析 ====================
elif page == "📉 數據分析":
    st.header("數據分析")
    df_stock = st.session_state.df_stock

    if df_stock.empty:
        st.warning("尚無數據")
    else:
        col1, col2, col3, col4 = st.columns(4)
        
        # 計算統計
        total_buy_amt = 0
        total_sell_amt = 0
        total_fee = 0
        total_tax = 0
        
        for _, row in df_stock.iterrows():
            shares = abs(row['股數'])
            price = row['成交價格(USD)']
            trade_amt = shares * price
            fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else 0
            tax = 0
            
            if row['交易類型'] == '買進':
                total_buy_amt += trade_amt
            else:
                total_sell_amt += trade_amt
                tax = row['交易稅(USD)'] if pd.notna(row['交易稅(USD)']) and row['交易稅(USD)'] > 0 else 0
            
            total_fee += fee
            total_tax += tax
        
        col1.metric("總買入", f"${total_buy_amt:,.2f}")
        col2.metric("總賣出", f"${total_sell_amt:,.2f}")
        col3.metric("總手續費", f"${total_fee:,.2f}")
        col4.metric("總稅", f"${total_tax:,.2f}")
        
        st.subheader("持倉")
        # 計算持倉
        holdings_dict = {}
        for _, row in df_stock.iterrows():
            code = row['股票代碼']
            shares = row['股數']
            price = row['成交價格(USD)']
            t_type = row['交易類型']
            
            if code not in holdings_dict:
                holdings_dict[code] = {'股數': 0, '總成本': 0}
            
            trade_amt = abs(shares) * price
            fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else 0
            
            if t_type == '買進':
                holdings_dict[code]['股數'] += abs(shares)
                holdings_dict[code]['總成本'] += trade_amt + fee
            else:
                holdings_dict[code]['股數'] -= abs(shares)
        
        holdings_list = []
        for code, data in holdings_dict.items():
            if data['股數'] > 0:
                holdings_list.append({
                    '股票代碼': code,
                    '持有股數': data['股數'],
                    '總成本(USD)': data['總成本'],
                    '平均成本(USD)': data['總成本'] / data['股數']
                })
        
        if holdings_list:
            st.dataframe(pd.DataFrame(holdings_list), use_container_width=True, hide_index=True)
        else:
            st.info("無持倉")

# 側邊欄底部資訊
st.sidebar.divider()
live_rate = get_exchange_rate("USD", "TWD")
if live_rate:
    st.sidebar.info(f"**即時匯率:** 1 USD = {live_rate:.2f} TWD")
else:
    st.sidebar.info(f"**匯率參考:** 1 USD = {USD_RATE} TWD")