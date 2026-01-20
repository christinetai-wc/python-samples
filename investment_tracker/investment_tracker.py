import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os

# 嘗試導入 yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    st.warning("⚠️ 未安裝 yfinance，無法查詢即時股價。請執行: pip install yfinance")

# 嘗試導入 fear_and_greed
try:
    import fear_and_greed
    FEAR_GREED_AVAILABLE = True
except ImportError:
    FEAR_GREED_AVAILABLE = False

st.set_page_config(page_title="投資理財追蹤系統", layout="wide")
st.title("💰 投資理財資金分配追蹤系統 (USD)")

# 檔案路徑
PLAN_FILE = 'investment_plan.csv'
ALLOCATION_FILE = 'aggressive_allocation.csv'
STOCK_FILE = 'stock_transactions.csv'
OPTION_FILE = 'options_transactions.csv'
USD_RATE = 31.5

# 初始化CSV檔案
def init_csv_files():
    if not os.path.exists(PLAN_FILE):
        pd.DataFrame(columns=['時間', '投資類型', '預計投入(USD)', '匯率']).to_csv(PLAN_FILE, index=False, encoding='utf-8-sig')
    if not os.path.exists(ALLOCATION_FILE):
        pd.DataFrame(columns=['股票代碼', '比重', '公允值(USD)', '邊際1(%)', '邊際2(%)', '邊際3(%)', '邊際4(%)', '邊際5(%)']).to_csv(ALLOCATION_FILE, index=False, encoding='utf-8-sig')
    if not os.path.exists(STOCK_FILE):
        pd.DataFrame(columns=['交易日期', '交易類型', '所屬分類', '股票代碼', '股數', '成交價格(USD)', 
                              '手續費(USD)', '交易稅(USD)', '用途說明', '備註']).to_csv(STOCK_FILE, index=False, encoding='utf-8-sig')
    if not os.path.exists(OPTION_FILE):
        pd.DataFrame(columns=['交易日期', '商品類型', '標的', '履約價', '到期日', '買賣權', '口數', 
                              '權利金', '交易金額(USD)', '手續費(USD)', '總成本(USD)', 
                              '資金來源', '策略說明']).to_csv(OPTION_FILE, index=False, encoding='utf-8-sig')

init_csv_files()

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

# 讀取CSV
def load_data(file_path):
    try:
        return pd.read_csv(file_path, encoding='utf-8-sig')
    except:
        return pd.DataFrame()

# 計算實際投入金額
def calculate_actual_investment(df_stock, category, stock_code=None):
    if df_stock.empty:
        return 0
    
    if category == '進攻型' and stock_code:
        filtered = df_stock[(df_stock['所屬分類'] == '進攻型') & 
                           (df_stock['股票代碼'] == stock_code) & 
                           (df_stock['交易類型'] == '買進')]
    else:
        filtered = df_stock[(df_stock['所屬分類'] == category) & (df_stock['交易類型'] == '買進')]
    
    if filtered.empty:
        return 0
    
    # 計算總成本 = 交易金額 + 手續費
    total = 0
    for _, row in filtered.iterrows():
        shares = abs(row['股數'])
        price = row['成交價格(USD)']
        trade_amt = shares * price
        fee = row['手續費(USD)'] if pd.notna(row['手續費(USD)']) and row['手續費(USD)'] > 0 else trade_amt * 0.001425
        total += trade_amt + fee
    
    return total

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
        info = stock.info
        # 優先使用 currentPrice，如果沒有則用 regularMarketPrice
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        return float(price) if price else None
    except:
        return None

# 計算持股數量
def calculate_holdings(df_stock, category, stock_code=None):
    """計算某分類或特定股票的持有股數"""
    if df_stock.empty:
        return {}

    if category == '進攻型' and stock_code:
        filtered = df_stock[(df_stock['所屬分類'] == '進攻型') &
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
page = st.sidebar.selectbox("選擇功能", 
    ["📊 投資總覽", "💵 投資計畫管理", "📈 股票交易記錄", "🎯 選擇權交易記錄", "📉 數據分析"])

# ==================== 投資總覽 ====================
if page == "📊 投資總覽":
    st.header("投資資金配置總覽")
    df_plan = load_data(PLAN_FILE)
    df_stock = load_data(STOCK_FILE)
    df_option = load_data(OPTION_FILE)
    df_allocation = load_data(ALLOCATION_FILE)

    # 顯示恐懼貪婪指數
    fgi = get_fear_greed_index()
    if fgi:
        # 根據數值決定顏色
        value = fgi['value']
        if value <= 25:
            color = '#e74c3c'  # 極度恐懼 - 紅色
            emoji = '😱'
        elif value <= 45:
            color = '#e67e22'  # 恐懼 - 橘色
            emoji = '😨'
        elif value <= 55:
            color = '#f1c40f'  # 中性 - 黃色
            emoji = '😐'
        elif value <= 75:
            color = '#2ecc71'  # 貪婪 - 綠色
            emoji = '😊'
        else:
            color = '#27ae60'  # 極度貪婪 - 深綠
            emoji = '🤑'

        st.markdown(
            f"""
            <div style="background: linear-gradient(90deg, {color}22, {color}44);
                        border-left: 4px solid {color}; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                <span style="font-size: 24px;">{emoji}</span>
                <strong style="font-size: 18px; margin-left: 10px;">恐懼貪婪指數: {value:.0f}</strong>
                <span style="color: {color}; font-weight: bold; margin-left: 10px;">{fgi['description']}</span>
                <span style="color: #888; font-size: 12px; margin-left: 15px;">更新: {fgi['last_update']}</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    elif FEAR_GREED_AVAILABLE:
        st.warning("⚠️ 無法取得恐懼貪婪指數")

    st.info(f"💡 預計金額來自投資計畫CSV，實際金額來自交易記錄CSV | 參考匯率: USD 1 = TWD {USD_RATE}")
    
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
                        
                        # 實際金額從交易記錄計算
                        stock_actual = calculate_actual_investment(df_stock, '進攻型', stock_code)
                        
                        chart_data.append({
                            'name': stock_code,
                            'type': '進攻型',
                            'planned': stock_planned,
                            'actual': stock_actual
                        })
            else:
                # 保守型和樂透型直接計算
                actual = calculate_actual_investment(df_stock, inv_type)
                chart_data.append({
                    'name': inv_type,
                    'type': inv_type,
                    'planned': planned,
                    'actual': actual
                })

    # 顯示長條圖
    if chart_data:
        st.subheader("📊 資金分配圖表")

        # 計算目前市值
        market_values = []
        for d in chart_data:
            if d['type'] == '進攻型':
                mv = calculate_market_value(df_stock, '進攻型', d['name'])
            else:
                mv = calculate_market_value(df_stock, d['type'])
            market_values.append(mv)

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
            holdings = calculate_holdings(df_stock, category, stock_code if category == '進攻型' else None)
            total_shares = sum(holdings.values()) if holdings else 0
            cost_price = actual_values[i] / total_shares if total_shares > 0 else 0

            # 取得現價
            if category == '進攻型':
                current_price = get_current_price(stock_code) or 0
            else:
                # 非進攻型可能有多檔股票，顯示總市值
                current_price = 0
                if holdings:
                    for code in holdings:
                        p = get_current_price(code)
                        if p:
                            current_price = p  # 簡化：取最後一檔的價格

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
            hovertemplate='<b>%{x}</b><br>預計投入: $%{y:,.0f}<extra></extra>'
        ))

        # 實際買入
        fig.add_trace(go.Bar(
            name='實際買入',
            x=categories,
            y=actual_values,
            marker_color='#3b82f6',
            text=[f'${int(v):,}' if v > 0 else '' for v in actual_values],
            textposition='outside',
            textangle=-45,
            hovertemplate='%{customdata}<extra></extra>',
            customdata=actual_hover_texts
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
            customdata=market_hover_texts
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

        fig.update_layout(
            title='預計投入 vs 實際買入 vs 目前市值',
            xaxis_title='投資類型/股票',
            yaxis_title='金額 (USD)',
            barmode='group',
            xaxis_tickangle=-45,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            height=500,
            margin=dict(t=80, b=80)
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

        # 按類型分組顯示
        col1, col2, col3 = st.columns(3)

        # 保守型
        conservative_data = [d for d in chart_data if d['type'] == '保守型']
        if conservative_data:
            with col1:
                st.write("**🟢 保守型**")
                for d in conservative_data:
                    st.metric(d['name'],
                             f"${d['actual']:,.2f}",
                             delta=f"預計: ${d['planned']:,.2f}")
                    exec_rate = (d['actual'] / d['planned'] * 100) if d['planned'] > 0 else 0
                    pct = (d['actual'] / grand_total * 100) if grand_total > 0 else 0
                    st.caption(f"執行率: {exec_rate:.1f}%")
                    st.caption(f"資金佔比: {pct:.1f}%")

        # 樂透型
        lottery_data = [d for d in chart_data if d['type'] == '樂透型']
        if lottery_data:
            with col2:
                st.write("**🟡 樂透型**")
                for d in lottery_data:
                    st.metric(d['name'],
                             f"${d['actual']:,.2f}",
                             delta=f"預計: ${d['planned']:,.2f}")
                    exec_rate = (d['actual'] / d['planned'] * 100) if d['planned'] > 0 else 0
                    pct = (d['actual'] / grand_total * 100) if grand_total > 0 else 0
                    st.caption(f"執行率: {exec_rate:.1f}%")
                    st.caption(f"資金佔比: {pct:.1f}%")

        # 進攻型統計
        aggressive_data = [d for d in chart_data if d['type'] == '進攻型']
        if aggressive_data:
            with col3:
                st.write("**🔵 進攻型**")
                total_agg_planned = sum([d['planned'] for d in aggressive_data])
                total_agg_actual = sum([d['actual'] for d in aggressive_data])
                st.metric("總計",
                         f"${total_agg_actual:,.2f}",
                         delta=f"預計: ${total_agg_planned:,.2f}")
                exec_rate = (total_agg_actual / total_agg_planned * 100) if total_agg_planned > 0 else 0
                pct = (total_agg_actual / grand_total * 100) if grand_total > 0 else 0
                st.caption(f"執行率: {exec_rate:.1f}%")
                st.caption(f"資金佔比: {pct:.1f}%")
        
        # 進攻型各股明細
        if aggressive_data:
            st.write("**進攻型各股明細**")
            cols = st.columns(min(len(aggressive_data), 5))
            for i, d in enumerate(aggressive_data):
                with cols[i % 5]:
                    st.write(f"**{d['name']}**")
                    st.metric("實際", f"${d['actual']:,.2f}")
                    st.caption(f"預計: ${d['planned']:,.2f}")
                    exec_rate = (d['actual'] / d['planned'] * 100) if d['planned'] > 0 else 0
                    st.caption(f"執行率: {exec_rate:.1f}%")
        
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

        col1, col2 = st.columns(2)
        col1.metric("選擇權收支", f"${opt_total:,.2f}")
        if total_margin > 0:
            col2.metric("🔒 被壓住的保證金", f"${total_margin:,.0f}")

        # 總計
        st.divider()
        total_actual = sum([d['actual'] for d in chart_data]) + opt_total

        col1, col2 = st.columns(2)
        col1.metric("📋 預計投入總額", f"${total_planned:,.2f}")
        col2.metric("💰 實際買入總額", f"${total_actual:,.2f}")

        overall_exec_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
        st.info(f"整體執行率: {overall_exec_rate:.1f}%")
    
    else:
        st.warning("⚠️ 請先在「投資計畫管理」設定投資計畫")

# ==================== 投資計畫管理 ====================
elif page == "💵 投資計畫管理":
    st.header("投資計畫管理")
    df_plan = load_data(PLAN_FILE)
    df_allocation = load_data(ALLOCATION_FILE)
    
    st.subheader("📋 表格1: 投資計畫")
    if df_plan.empty:
        df_plan = pd.DataFrame({
            '時間': [datetime.now().date(), datetime.now().date(), datetime.now().date()],
            '投資類型': ['保守型', '進攻型', '樂透型'], 
            '預計投入(USD)': [0.0, 0.0, 0.0],
            '匯率': [USD_RATE, USD_RATE, USD_RATE]
        })
        df_plan.to_csv(PLAN_FILE, index=False, encoding='utf-8-sig')
    else:
        # 轉換時間欄位
        df_plan['時間'] = pd.to_datetime(df_plan['時間']).dt.date
    
    edited_plan = st.data_editor(df_plan, num_rows="dynamic", use_container_width=True,
        column_config={
            "時間": st.column_config.DateColumn("時間", required=True),
            "投資類型": st.column_config.SelectboxColumn("投資類型", 
                options=["保守型", "進攻型", "樂透型"], required=True),
            "預計投入(USD)": st.column_config.NumberColumn("預計投入(USD)", 
                format="$%.2f", min_value=0, required=True),
            "匯率": st.column_config.NumberColumn("匯率(USD→TWD)", 
                format="%.2f", min_value=0, help=f"參考匯率: {USD_RATE}")
        })
    
    if st.button("💾 儲存投資計畫"):
        # 轉換日期為字串儲存
        edited_plan['時間'] = edited_plan['時間'].astype(str)
        edited_plan.to_csv(PLAN_FILE, index=False, encoding='utf-8-sig')
        st.success("✅ 已儲存!")
        st.rerun()
    
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
        df_allocation.to_csv(ALLOCATION_FILE, index=False, encoding='utf-8-sig')
    
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
    
    if st.button("💾 儲存股票配置"):
        edited_alloc.to_csv(ALLOCATION_FILE, index=False, encoding='utf-8-sig')
        st.success("✅ 已儲存!")
        st.rerun()
    
    # 顯示買入參考價格表
    if not edited_alloc.empty:
        st.write("**📋 五檔買入參考價格表**")
        price_table = []
        for _, row in edited_alloc.iterrows():
            code = row['股票代碼']
            fair = row['公允值(USD)']
            if fair > 0:
                prices = {'代碼': code, '公允值': f"${fair:.2f}"}
                for i in range(1, 6):
                    margin = row[f'邊際{i}(%)']
                    if margin > 0:
                        prices[f'第{i}檔'] = f"${fair * margin / 100:.2f}"
                    else:
                        prices[f'第{i}檔'] = "-"
                price_table.append(prices)
        
        if price_table:
            st.dataframe(pd.DataFrame(price_table), use_container_width=True, hide_index=True)

# ==================== 股票交易記錄 ====================
elif page == "📈 股票交易記錄":
    st.header("股票交易記錄")
    df_stock = load_data(STOCK_FILE)
    
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
    
    if st.button("💾 儲存股票交易記錄"):
        # 處理預設值
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
        edited_stock.to_csv(STOCK_FILE, index=False, encoding='utf-8-sig')
        st.success("✅ 已儲存! 空白欄位已自動填入預設值")
        st.rerun()
    
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
    df_option = load_data(OPTION_FILE)

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
    
    if st.button("💾 儲存選擇權交易記錄"):
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
        edited_option.to_csv(OPTION_FILE, index=False, encoding='utf-8-sig')
        st.success("✅ 已儲存!")
        st.rerun()

# ==================== 數據分析 ====================
elif page == "📉 數據分析":
    st.header("數據分析")
    df_stock = load_data(STOCK_FILE)
    
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

# 側邊欄
st.sidebar.divider()
st.sidebar.info(f"**匯率參考:** 1 USD = {USD_RATE} TWD")
st.sidebar.success("✅ 數據自動儲存")