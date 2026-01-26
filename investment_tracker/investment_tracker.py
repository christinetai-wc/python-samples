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
        st.session_state.df_plan = pd.DataFrame(columns=['時間', '投資類型', '預計投入(USD)', '匯率'])
    if 'df_allocation' not in st.session_state:
        st.session_state.df_allocation = pd.DataFrame(columns=['股票代碼', '比重', '公允值(USD)', '邊際1(%)', '邊際2(%)', '邊際3(%)', '邊際4(%)', '邊際5(%)'])
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
                st.session_state[state_key] = df
                loaded_files.append(filename)
            except Exception as e:
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
                            st.session_state[FILE_MAPPING[zip_filename]] = df
                            loaded_files.append(zip_filename)
        # 處理 CSV 檔案
        elif filename in FILE_MAPPING:
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
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
                fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else trade_amt * 0.001425
                total += trade_amt + fee

    return total

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
def check_monthly_conservative_plan(df_plan):
    """檢查從2026/1開始每個月是否有保守型投資計畫"""
    if df_plan.empty:
        return []

    # 轉換時間欄位
    df_plan['時間'] = pd.to_datetime(df_plan['時間'])

    # 篩選保守型
    conservative = df_plan[df_plan['投資類型'] == '保守型']

    if conservative.empty:
        return []

    # 取得已有的月份
    existing_months = conservative['時間'].dt.to_period('M').unique()

    # 檢查從2026/1到現在的每個月
    start_date = pd.Period('2026-01', 'M')
    current_date = pd.Period(datetime.now(), 'M')

    missing_months = []
    period = start_date
    while period <= current_date:
        if period not in existing_months:
            missing_months.append(period.strftime('%Y年%m月'))
        period += 1

    return missing_months

# 檢查保守型每月投資是否低於下限
def check_conservative_monthly_limit(df_plan, minimum=300):
    """檢查保守型每月投資是否低於下限"""
    if df_plan.empty:
        return []

    df_plan = df_plan.copy()
    df_plan['時間'] = pd.to_datetime(df_plan['時間'])

    conservative = df_plan[df_plan['投資類型'] == '保守型']
    if conservative.empty:
        return []

    # 按月份加總
    conservative['月份'] = conservative['時間'].dt.to_period('M')
    monthly_sum = conservative.groupby('月份')['預計投入(USD)'].sum()

    below_minimum = []
    for month, amount in monthly_sum.items():
        if amount < minimum:
            below_minimum.append({
                'month': month.strftime('%Y年%m月'),
                'amount': amount,
                'minimum': minimum
            })

    return below_minimum

# 檢查樂透型是否超過總投資比例
def check_lottery_ratio(df_plan, max_ratio=10):
    """檢查樂透型是否超過總投資金額的比例上限"""
    if df_plan.empty:
        return None

    total_investment = df_plan['預計投入(USD)'].sum()
    if total_investment == 0:
        return None

    lottery = df_plan[df_plan['投資類型'] == '樂透型']
    lottery_amount = lottery['預計投入(USD)'].sum() if not lottery.empty else 0

    lottery_ratio = (lottery_amount / total_investment) * 100

    if lottery_ratio > max_ratio:
        return {
            'ratio': lottery_ratio,
            'amount': lottery_amount,
            'total': total_investment,
            'max_ratio': max_ratio
        }

    return None
def get_planned_amount(df_plan, df_allocation, category, stock_code=None):
    if df_plan.empty:
        return 0
    if category == '進攻型' and stock_code:
        aggressive_row = df_plan[df_plan['投資類型'] == '進攻型']
        if aggressive_row.empty:
            return 0
        aggressive_total = float(aggressive_row.iloc[0]['預計投入(USD)'])
        if not df_allocation.empty:
            match = df_allocation[df_allocation['股票代碼'] == stock_code]
            if not match.empty:
                weight = float(match.iloc[0]['比重'])
                return aggressive_total * (weight / 100)
        return 0
    else:
        filtered = df_plan[df_plan['投資類型'] == category]
        return float(filtered['預計投入(USD)'].sum()) if not filtered.empty else 0

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
    st.info(f"💡 預計金額來自投資計畫CSV，實際金額來自交易記錄CSV | 即時匯率: USD 1 = TWD {rate_display:.2f}")
    
    # 準備圖表數據
    chart_data = []
    
    # 從 investment_plan.csv 讀取投資類型
    if not df_plan.empty:
        # 按投資類型分組,取最新的預計投入
        plan_summary = df_plan.groupby('投資類型').agg({
            '預計投入(USD)': 'sum',
            '匯率': 'last'
        }).reset_index()
        
        for _, row in plan_summary.iterrows():
            inv_type = row['投資類型']
            planned = row['預計投入(USD)']
            
            if inv_type == '進攻型':
                # 進攻型需要拆分成各股票
                if not df_allocation.empty:
                    for _, stock_row in df_allocation.iterrows():
                        stock_code = stock_row['股票代碼']
                        weight = float(stock_row['比重'])

                        # 預計金額 = 進攻型總額 × 比重
                        stock_planned = planned * (weight / 100)

                        # 實際金額從交易記錄計算（僅股票成本）
                        stock_actual = calculate_actual_investment(df_stock, '進攻型', stock_code)
                        # 選擇權保證金（資金來源為此股票）
                        stock_margin, margin_details = calculate_option_margin(df_option, stock_code, return_details=True)

                        chart_data.append({
                            'name': stock_code,
                            'type': '進攻型',
                            'planned': stock_planned,
                            'actual': stock_actual,
                            'margin': stock_margin,
                            'margin_details': margin_details
                        })
            elif inv_type == '保守型':
                # 保守型拆分成各股票
                if not df_conservative.empty:
                    for _, stock_row in df_conservative.iterrows():
                        stock_code = stock_row['股票代碼']
                        weight = float(stock_row['比重'])

                        stock_planned = planned * (weight / 100)
                        stock_actual = calculate_actual_investment(df_stock, '保守型', stock_code)

                        chart_data.append({
                            'name': stock_code,
                            'type': '保守型',
                            'planned': stock_planned,
                            'actual': stock_actual,
                            'margin': 0
                        })
                else:
                    # 沒有配置時顯示整體
                    actual = calculate_actual_investment(df_stock, inv_type)
                    chart_data.append({
                        'name': inv_type,
                        'type': inv_type,
                        'planned': planned,
                        'actual': actual,
                        'margin': 0
                    })
            elif inv_type == '樂透型':
                # 樂透型拆分成各股票
                if not df_lottery.empty:
                    for _, stock_row in df_lottery.iterrows():
                        stock_code = stock_row['股票代碼']
                        weight = float(stock_row['比重'])

                        stock_planned = planned * (weight / 100)
                        stock_actual = calculate_actual_investment(df_stock, '樂透型', stock_code)

                        chart_data.append({
                            'name': stock_code,
                            'type': '樂透型',
                            'planned': stock_planned,
                            'actual': stock_actual,
                            'margin': 0
                        })
                else:
                    # 沒有配置時顯示整體
                    actual = calculate_actual_investment(df_stock, inv_type)
                    chart_data.append({
                        'name': inv_type,
                        'type': inv_type,
                        'planned': planned,
                        'actual': actual,
                        'margin': 0
                    })

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

        # 準備圖表
        categories = [d['name'] for d in chart_data]
        planned_values = [d['planned'] for d in chart_data]
        actual_values = [d['actual'] for d in chart_data]

        # 計算每個項目的成本價、現價、持股數
        actual_hover_texts = []
        market_hover_texts = []

        for i, d in enumerate(chart_data):
            stock_code = d['name']
            category = d['type']

            # 計算成本價 (實際買入金額 / 持股數)
            # 如果 name 不等於 type，表示是個別股票
            is_individual_stock = (stock_code != category)
            holdings = calculate_holdings(df_stock, category, stock_code if is_individual_stock else None)
            total_shares = sum(holdings.values()) if holdings else 0
            cost_price = actual_values[i] / total_shares if total_shares > 0 else 0

            # 取得現價
            if is_individual_stock:
                current_price = get_current_price(stock_code) or 0
            else:
                # 未配置時可能有多檔股票，取最後一檔的價格
                current_price = 0
                if holdings:
                    for code in holdings:
                        p = get_current_price(code)
                        if p:
                            current_price = p

            # 實際買入 hover 文字
            if actual_values[i] > 0:
                actual_hover_texts.append(
                    f"<b>{stock_code}</b><br>"
                    f"成本價: ${cost_price:,.2f}<br>"
                    f"總成本: ${actual_values[i]:,.0f}"
                )
            else:
                actual_hover_texts.append(f"<b>{stock_code}</b><br>尚未買入")

            # 目前市值 hover 文字
            if market_values[i] > 0:
                market_hover_texts.append(
                    f"<b>{stock_code}</b><br>"
                    f"現在股價: ${current_price:,.2f}<br>"
                    f"目前市值: ${market_values[i]:,.0f}"
                )
            else:
                market_hover_texts.append(f"<b>{stock_code}</b><br>無持股")

        # 取得保證金數據
        margin_values = [d.get('margin', 0) for d in chart_data]

        # 建立選擇權保證金 hover 文字
        margin_hover_texts = []
        for d in chart_data:
            margin_details = d.get('margin_details', [])
            margin_total = d.get('margin', 0)
            if margin_total > 0 and margin_details:
                # 顯示標的股票和保證金
                hover_lines = [f"<b>選擇權保證金</b>"]
                for detail in margin_details:
                    hover_lines.append(f"{detail['ticker']}: ${detail['margin']:,.0f}")
                hover_lines.append(f"<b>合計: ${margin_total:,.0f}</b>")
                margin_hover_texts.append("<br>".join(hover_lines))
            elif margin_total > 0:
                margin_hover_texts.append(f"<b>選擇權保證金</b><br>${margin_total:,.0f}")
            else:
                margin_hover_texts.append("")

        # 使用 Plotly 建立圖表
        fig = go.Figure()

        # 預計投入
        fig.add_trace(go.Bar(
            name='預計投入',
            x=categories,
            y=planned_values,
            marker_color='#64748b',
            text=[f'${int(v):,}' if v > 0 else '' for v in planned_values],
            textposition='outside',
            textangle=-45,
            hovertemplate='<b>%{x}</b><br>預計投入: $%{y:,.0f}<extra></extra>',
            offsetgroup='planned'
        ))

        # 實際買入（股票成本）- 與保證金堆疊
        fig.add_trace(go.Bar(
            name='實際買入',
            x=categories,
            y=actual_values,
            marker_color='#3b82f6',
            text=[f'${int(v):,}' if v > 0 else '' for v in actual_values],
            textposition='inside',
            textangle=0,
            hovertemplate='%{customdata}<extra></extra>',
            customdata=actual_hover_texts,
            offsetgroup='actual'
        ))

        # 選擇權保證金（堆疊在實際買入上方）
        fig.add_trace(go.Bar(
            name='選擇權保證金',
            x=categories,
            y=margin_values,
            marker_color='#f59e0b',
            text=[f'${int(v):,}' if v > 0 else '' for v in margin_values],
            textposition='outside',
            textangle=-45,
            hovertemplate='%{customdata}<extra></extra>',
            customdata=margin_hover_texts,
            offsetgroup='actual',
            base=actual_values
        ))

        # 目前市值
        fig.add_trace(go.Bar(
            name='目前市值',
            x=categories,
            y=market_values,
            marker_color='#22c55e',
            text=[f'${int(v):,}' if v > 0 else '' for v in market_values],
            textposition='outside',
            textangle=-45,
            hovertemplate='%{customdata}<extra></extra>',
            customdata=market_hover_texts,
            offsetgroup='market'
        ))

        # 在進攻型股票的預計投入長條上加入安全邊際標記
        if not df_allocation.empty:
            for i, d in enumerate(chart_data):
                if d['type'] == '進攻型':
                    stock_code = d['name']
                    alloc_row = df_allocation[df_allocation['股票代碼'] == stock_code]
                    if not alloc_row.empty:
                        fair_value = alloc_row.iloc[0]['公允值(USD)']
                        planned_amt = d['planned']

                        if fair_value > 0 and planned_amt > 0:
                            cumulative_weight = 0

                            for j in range(1, 6):
                                margin_pct = alloc_row.iloc[0].get(f'邊際{j}(%)', 0) or 0
                                margin_weight = alloc_row.iloc[0].get(f'邊際{j}比重(%)', 0) or 0

                                if margin_pct > 0 and margin_weight > 0:
                                    cumulative_weight += margin_weight
                                    height_at_margin = planned_amt * (cumulative_weight / 100)
                                    margin_price = fair_value * margin_pct / 100

                                    fig.add_annotation(
                                        x=stock_code,
                                        y=height_at_margin,
                                        text=f'${margin_price:.0f}',
                                        showarrow=False,
                                        font=dict(size=10, color='#ff6a00', family='Arial Black'),
                                        bgcolor='rgba(255,255,255,0.8)',
                                        xshift=-40  # 往左偏移到預計投入長條上
                                    )

        # 計算 Y 軸最大值，加上 20% 空間顯示數字
        all_values = planned_values + actual_values + market_values + [a + m for a, m in zip(actual_values, margin_values)]
        max_value = max(all_values) if all_values else 0
        y_max = max_value * 1.25  # 增加 25% 空間

        fig.update_layout(
            title='預計投入 vs 實際買入 vs 目前市值',
            xaxis_title='投資類型/股票',
            yaxis_title='金額 (USD)',
            barmode='group',
            xaxis_tickangle=-45,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            height=500,
            margin=dict(t=80, b=80),
            yaxis=dict(range=[0, y_max])
        )

        fig.update_yaxes(gridcolor='rgba(0,0,0,0.1)')

        st.plotly_chart(fig, use_container_width=True)
        
        # 詳細數據表格
        st.subheader("📋 詳細數據")

        # 計算選擇權收入（提前計算用於佔比）
        if not df_option.empty:
            if '收支金額(USD)' in df_option.columns:
                opt_total = df_option['收支金額(USD)'].sum()
            elif '總成本(USD)' in df_option.columns:
                opt_total = df_option['總成本(USD)'].sum()
            else:
                opt_total = 0
        else:
            opt_total = 0

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
                total_agg_actual = sum([d['actual'] for d, _ in aggressive_data])
                total_agg_mv = sum([market_values[idx] for _, idx in aggressive_data])
                total_agg_planned = sum([d['planned'] for d, _ in aggressive_data])
                total_agg_profit = total_agg_mv - total_agg_actual
                total_agg_return = (total_agg_profit / total_agg_actual * 100) if total_agg_actual > 0 else 0
                total_agg_exec = (total_agg_actual / total_agg_planned * 100) if total_agg_planned > 0 else 0

                # 使用 st.metric 原生箭頭：正數綠色向上、負數紅色向下
                delta_str = f"{total_agg_return:+.1f}%"

                st.metric("總計", f"${total_agg_mv:,.0f}" if total_agg_mv > 0 else f"${total_agg_actual:,.0f}", delta=delta_str)
                st.caption(f"成本: ${total_agg_actual:,.0f} | 損益: ${total_agg_profit:,.0f}")
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

        # 計算被壓住的保證金（未到期的賣方部位）
        if not df_option.empty and '保證金(USD)' in df_option.columns:
            df_option_calc = df_option.copy()
            df_option_calc['到期日'] = pd.to_datetime(df_option_calc['到期日'])
            today = pd.Timestamp(datetime.now().date())
            active_sold = df_option_calc[
                (df_option_calc['到期日'] >= today) &
                (df_option_calc['買賣方向'] == '賣出')
            ]
            total_margin = active_sold['保證金(USD)'].sum() if not active_sold.empty else 0
        else:
            total_margin = 0

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

        col1, col2, col3 = st.columns(3)
        col1.metric("選擇權收支", f"${opt_total:,.2f}")
        if total_margin > 0:
            col2.metric("🔒 被壓住的保證金", f"${total_margin:,.0f}")
            col3.metric("報酬率", opt_return_str)

        # 總計
        st.divider()
        st.subheader("📊 投資組合總覽")

        total_actual = sum([d['actual'] for d in chart_data])
        total_market_value = sum(market_values)
        total_profit = total_market_value - total_actual
        total_return_rate = (total_profit / total_actual * 100) if total_actual > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💵 總成本", f"${total_actual:,.0f}")
        col2.metric("💰 總市值", f"${total_market_value:,.0f}" if total_market_value > 0 else "-")

        # 報酬率顯示
        if total_return_rate > 0:
            col3.metric("📈 總報酬率", f"+{total_return_rate:.1f}%", delta=f"${total_profit:,.0f}")
        elif total_return_rate < 0:
            col3.metric("📉 總報酬率", f"{total_return_rate:.1f}%", delta=f"${total_profit:,.0f}")
        else:
            col3.metric("📊 總報酬率", "0%", delta="$0")

        # 執行率
        overall_exec_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
        col4.metric("🎯 執行率", f"{overall_exec_rate:.1f}%", delta=f"預計: ${total_planned:,.0f}")
    
    else:
        st.warning("⚠️ 請先在「投資計畫管理」設定投資計畫")

# ==================== 投資計畫管理 ====================
elif page == "💵 投資計畫管理":
    st.header("投資計畫管理")
    df_plan = st.session_state.df_plan.copy()
    df_allocation = st.session_state.df_allocation.copy()

    st.subheader("📋 表格1: 投資計畫")
    if df_plan.empty:
        df_plan = pd.DataFrame({
            '時間': [datetime.now().date(), datetime.now().date(), datetime.now().date()],
            '投資類型': ['保守型', '進攻型', '樂透型'],
            '預計投入(USD)': [0.0, 0.0, 0.0],
            '匯率': [USD_RATE, USD_RATE, USD_RATE]
        })
    else:
        # 轉換時間欄位
        df_plan['時間'] = pd.to_datetime(df_plan['時間']).dt.date
        # 按時間排序
        df_plan = df_plan.sort_values('時間', ascending=True).reset_index(drop=True)

    edited_plan = st.data_editor(df_plan, num_rows="dynamic", use_container_width=True,
        column_config={
            "時間": st.column_config.DateColumn("時間", required=True),
            "投資類型": st.column_config.SelectboxColumn("投資類型",
                options=["保守型", "進攻型", "樂透型"], required=True),
            "預計投入(USD)": st.column_config.NumberColumn("預計投入(USD)",
                format="$%.2f", min_value=0, required=True),
            "匯率": st.column_config.NumberColumn("匯率(USD→TWD)",
                format="%.2f", min_value=0, help=f"即時匯率: {get_exchange_rate('USD', 'TWD') or USD_RATE:.2f}")
        })

    # 自動儲存到 session_state
    edited_plan['時間'] = edited_plan['時間'].astype(str)
    st.session_state.df_plan = edited_plan

    # 檢查保守型月度計畫
    missing_months = check_monthly_conservative_plan(edited_plan)
    if missing_months:
        st.warning(f"⚠️ **保守型投資提醒**: 以下月份尚未設定投資計畫")
        st.write("缺少的月份: " + ", ".join(missing_months))
        st.info("💡 建議: 保守型應該每月定期投入,請補充缺少月份的投資計畫")

    # 檢查保守型每月是否低於300元
    below_months = check_conservative_monthly_limit(edited_plan, minimum=300)
    if below_months:
        st.warning("⚠️ **保守型投資不足提醒**")
        for item in below_months:
            st.write(f"  • {item['month']}: ${item['amount']:.0f} (下限: ${item['minimum']})")

    # 檢查樂透型是否超過總投資10%
    lottery_warning = check_lottery_ratio(edited_plan, max_ratio=10)
    if lottery_warning:
        st.error(
            f"🚨 **樂透型投資超額提醒**: 目前佔比 {lottery_warning['ratio']:.1f}% "
            f"(上限: {lottery_warning['max_ratio']}%)\n\n"
            f"樂透型金額: ${lottery_warning['amount']:,.0f} / "
            f"總投資金額: ${lottery_warning['total']:,.0f}"
        )
    
    st.divider()
    st.subheader("🔵 表格2: 進攻型股票配置")
    st.info("💡 公允值=合理價格 | 邊際1-5=分批買入的價格比例 (例如: 公允值$300, 邊際80%→$240買入)")
    
    if df_allocation.empty:
        df_allocation = pd.DataFrame({
            '股票代碼': ['TSLA'],
            '比重': [100.0],
            '公允值(USD)': [300.0],
            '邊際1(%)': [100.0],
            '邊際2(%)': [93.0],
            '邊際3(%)': [80.0],
            '邊際4(%)': [70.0],
            '邊際5(%)': [50.0]
        })

    edited_alloc = st.data_editor(df_allocation, num_rows="dynamic", use_container_width=True,
        column_config={
            "股票代碼": st.column_config.TextColumn("代碼", required=True),
            "比重": st.column_config.NumberColumn("比重(%)", format="%.0f", required=True),
            "公允值(USD)": st.column_config.NumberColumn("公允值", format="$%.0f"),
            "邊際1(%)": st.column_config.NumberColumn("邊際1", format="%.0f%%"),
            "邊際2(%)": st.column_config.NumberColumn("邊際2", format="%.0f%%"),
            "邊際3(%)": st.column_config.NumberColumn("邊際3", format="%.0f%%"),
            "邊際4(%)": st.column_config.NumberColumn("邊際4", format="%.0f%%"),
            "邊際5(%)": st.column_config.NumberColumn("邊際5", format="%.0f%%")
        })

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

    st.info("💡 只需填寫: 日期、類型、分類、代碼、股數、價格 | 其他欄位可選填(空白則使用預設值)")
    
    if df_stock.empty:
        df_stock = pd.DataFrame([{
            '交易日期': datetime.now().date(),
            '交易類型': '買進',
            '所屬分類': '進攻型',
            '股票代碼': 'TSLA',
            '股數': 0.0,
            '成交價格(USD)': 0.0,
            '手續費(USD)': 0.0,
            '交易稅(USD)': 0.0,
            '用途說明': '',
            '備註': ''
        }])
    else:
        df_stock['交易日期'] = pd.to_datetime(df_stock['交易日期']).dt.date
        # 確保股數為浮點數
        df_stock['股數'] = df_stock['股數'].astype(float)
        # 填充空值
        df_stock['手續費(USD)'].fillna(0.0, inplace=True)
        df_stock['交易稅(USD)'].fillna(0.0, inplace=True)
        df_stock['用途說明'].fillna('', inplace=True)
        df_stock['備註'].fillna('', inplace=True)
        # 按交易日期排序
        df_stock = df_stock.sort_values('交易日期', ascending=True).reset_index(drop=True)

    edited_stock = st.data_editor(df_stock, num_rows="dynamic", use_container_width=True,
        column_config={
            "交易日期": st.column_config.DateColumn("日期", required=True),
            "交易類型": st.column_config.SelectboxColumn("類型", options=["買進", "賣出"], required=True),
            "所屬分類": st.column_config.SelectboxColumn("分類", options=["保守型", "進攻型", "樂透型"], required=True),
            "股票代碼": st.column_config.TextColumn("代碼", required=True),
            "股數": st.column_config.NumberColumn("股數", format="%.4f", required=True),
            "成交價格(USD)": st.column_config.NumberColumn("價格", format="$%.2f", required=True),
            "手續費(USD)": st.column_config.NumberColumn("手續費", format="$%.2f", 
                help="空白則自動計算(交易額×0.1425%)"),
            "交易稅(USD)": st.column_config.NumberColumn("稅", format="$%.2f",
                help="空白則自動計算(賣出時為交易額×0.3%)"),
            "用途說明": st.column_config.TextColumn("用途"),
            "備註": st.column_config.TextColumn("備註")
        }, key="stock_editor")
    
    # 顯示計算預覽
    if not edited_stock.empty and len(edited_stock) > 0:
        st.write("**💡 計算預覽 (實際儲存時會自動計算空白欄位)**")
        preview_data = []
        for idx, row in edited_stock.iterrows():
            shares = abs(row['股數'])
            price = row['成交價格(USD)']
            t_type = row['交易類型']
            
            trade_amt = shares * price
            
            # 手續費: 如果為0或空,使用預設
            fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else trade_amt * 0.001425
            
            # 交易稅: 如果為0或空且是賣出,使用預設
            if t_type == '賣出':
                tax = row['交易稅(USD)'] if pd.notna(row['交易稅(USD)']) and row['交易稅(USD)'] > 0 else trade_amt * 0.003
            else:
                tax = 0
            
            # 總成本/收入
            if t_type == '買進':
                total = trade_amt + fee
            else:
                total = trade_amt - fee - tax
            
            preview_data.append({
                '股票': row['股票代碼'],
                '交易額': f"${trade_amt:.2f}",
                '手續費': f"${fee:.2f}",
                '稅': f"${tax:.2f}",
                '總計': f"${total:.2f}"
            })
        
        if preview_data:
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)
    
    # 自動處理預設值並儲存到 session_state
    for idx, row in edited_stock.iterrows():
        # 填充用途說明和備註的空值
        if pd.isna(row['用途說明']) or row['用途說明'] == '':
            edited_stock.at[idx, '用途說明'] = ''
        if pd.isna(row['備註']) or row['備註'] == '':
            edited_stock.at[idx, '備註'] = ''

        # 計算交易金額
        shares = abs(row['股數'])
        price = row['成交價格(USD)']
        trade_amt = shares * price

        # 手續費預設值
        if pd.isna(row['手續費(USD)']) or row['手續費(USD)'] == 0:
            edited_stock.at[idx, '手續費(USD)'] = trade_amt * 0.001425

        # 交易稅預設值
        if row['交易類型'] == '賣出':
            if pd.isna(row['交易稅(USD)']) or row['交易稅(USD)'] == 0:
                edited_stock.at[idx, '交易稅(USD)'] = trade_amt * 0.003
        else:
            edited_stock.at[idx, '交易稅(USD)'] = 0

        # 股數正負號
        if row['交易類型'] == '買進':
            edited_stock.at[idx, '股數'] = abs(row['股數'])
        else:
            edited_stock.at[idx, '股數'] = -abs(row['股數'])

    edited_stock['交易日期'] = edited_stock['交易日期'].astype(str)
    st.session_state.df_stock = edited_stock

    # 統計
    if not df_stock.empty and len(df_stock) > 0:
        st.divider()
        st.subheader("📊 交易統計")
        
        # 計算統計
        total_buy = 0
        total_sell = 0
        for _, row in df_stock.iterrows():
            shares = abs(row['股數'])
            price = row['成交價格(USD)']
            trade_amt = shares * price
            fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else trade_amt * 0.001425
            
            if row['交易類型'] == '買進':
                total_buy += trade_amt + fee
            else:
                tax = row['交易稅(USD)'] if pd.notna(row['交易稅(USD)']) and row['交易稅(USD)'] > 0 else trade_amt * 0.003
                total_sell += trade_amt - fee - tax
        
        col1, col2 = st.columns(2)
        col1.metric("總買入金額", f"${total_buy:,.2f}")
        col2.metric("總賣出金額", f"${total_sell:,.2f}")

# ==================== 選擇權交易記錄 ====================
elif page == "🎯 選擇權交易記錄":
    st.header("選擇權交易記錄")
    df_option = st.session_state.df_option.copy()

    st.info("💡 直接在表格中編輯,自動計算金額")

    if df_option.empty:
        df_option = pd.DataFrame([{
            '交易日期': datetime.now().date(),
            '商品類型': '股票選擇權',
            '標的': 'TSLA',
            '履約價': 0.0,
            '到期日': datetime.now().date(),
            '買賣權': '買權(Call)',
            '買賣方向': '賣出',
            '口數': 0,
            '權利金': 0.0,
            '交易金額(USD)': 0.0,
            '手續費(USD)': 0.0,
            '保證金(USD)': 0.0,
            '總成本(USD)': 0.0,
            '資金來源': '',
            '策略說明': ''
        }])
    else:
        df_option['交易日期'] = pd.to_datetime(df_option['交易日期']).dt.date
        df_option['到期日'] = pd.to_datetime(df_option['到期日']).dt.date
        # 確保文字欄位為字串類型
        df_option['資金來源'] = df_option['資金來源'].fillna('').astype(str)
        df_option['策略說明'] = df_option['策略說明'].fillna('').astype(str)
        # 確保保證金欄位存在
        if '保證金(USD)' not in df_option.columns:
            df_option['保證金(USD)'] = 0.0
        if '買賣方向' not in df_option.columns:
            df_option['買賣方向'] = '賣出'
        # 按交易日期排序
        df_option = df_option.sort_values('交易日期', ascending=True).reset_index(drop=True)

    edited_option = st.data_editor(df_option, num_rows="dynamic", use_container_width=True,
        column_config={
            "交易日期": st.column_config.DateColumn("日期", required=True),
            "商品類型": st.column_config.SelectboxColumn("類型",
                options=["股票選擇權", "指數選擇權", "其他"], required=True),
            "標的": st.column_config.TextColumn("標的", required=True),
            "履約價": st.column_config.NumberColumn("履約價", format="$%.2f"),
            "到期日": st.column_config.DateColumn("到期日", required=True),
            "買賣權": st.column_config.SelectboxColumn("買賣權",
                options=["買權(Call)", "賣權(Put)"], required=True),
            "買賣方向": st.column_config.SelectboxColumn("買/賣",
                options=["買入", "賣出"], required=True),
            "口數": st.column_config.NumberColumn("口數", format="%d"),
            "權利金": st.column_config.NumberColumn("權利金", format="$%.2f"),
            "交易金額(USD)": st.column_config.NumberColumn("金額", format="$%.2f"),
            "手續費(USD)": st.column_config.NumberColumn("手續費", format="$%.2f"),
            "保證金(USD)": st.column_config.NumberColumn("保證金", format="$%.0f"),
            "總成本(USD)": st.column_config.NumberColumn("總額", format="$%.2f"),
            "資金來源": st.column_config.TextColumn("來源"),
            "策略說明": st.column_config.TextColumn("策略")
        }, key="option_editor")
    
    # 自動處理預設值並儲存到 session_state
    for idx, row in edited_option.iterrows():
        contracts = row['口數']
        premium = row['權利金']

        trade_amt = contracts * premium * 100
        edited_option.at[idx, '交易金額(USD)'] = trade_amt

        if row['手續費(USD)'] == 0:
            edited_option.at[idx, '手續費(USD)'] = 1.0

        fee = edited_option.at[idx, '手續費(USD)']
        edited_option.at[idx, '總成本(USD)'] = trade_amt + fee

    edited_option['交易日期'] = edited_option['交易日期'].astype(str)
    edited_option['到期日'] = edited_option['到期日'].astype(str)
    st.session_state.df_option = edited_option

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
            fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else trade_amt * 0.001425
            tax = 0
            
            if row['交易類型'] == '買進':
                total_buy_amt += trade_amt
            else:
                total_sell_amt += trade_amt
                tax = row['交易稅(USD)'] if pd.notna(row['交易稅(USD)']) and row['交易稅(USD)'] > 0 else trade_amt * 0.003
            
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
            fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else trade_amt * 0.001425
            
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