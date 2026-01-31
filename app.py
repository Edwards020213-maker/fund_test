import streamlit as st
import pandas as pd
import requests
import akshare as ak
import datetime
import time
import math
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ==========================================
# 🔐 商家后台配置区
# ==========================================
VALID_VIP_CODES = [
    "LIHWQY","GO75ON","DXPIOA","SAMRUO","SGUGKB","K88CTV","I354RX", "K9IJMS","4ZF59V","27DP9A","U0CALN","1XVK1D","G6AW46","Q9TXDU","HH4FDG",
    "LGYUB6", "2S55MK","82GJKA","7RI4IN","YE9SEZ","VLBGKG","4VKIWT","Q7SL9J","6QEBLO","P1OHJR","59L0A3","L1OTDE","8LH0D3","BMTQSN","F7NKNF",
    "0MJ0RD","TFLKK3","AKBODE","SC87DP","G3WJAG","N3XX4X","AN09RU", "I1A2Z3", "RH1C5B", "Y6RMG9", "ZH3G5O", "GTCAPG", "PZE1LX", "WT7Z8O", "EO6LXU", 
    "BYK569", "84IDLA","ETCTZG","P6YI7G","QZGDLB"
]
UNLOCK_HINT = "请输入您的专属 VIP 兑换码"
BUY_GUIDE = "如需获取，请在购买平台（闲鱼/小红书）私信联系发货"
CONTACT_TIP = "💡 有功能改进建议？欢迎在 闲鱼/小红书 私信留言，采纳有奖！"
# ==========================================

# --- 0. 核心配置 ---
PROXY_MAP = {
    "黄金": "518880", "上海金": "518600", "豆粕": "159985",
    "有色": "512400", "化工": "516020", "石化": "516020",
    "石油": "561360", "油气": "513350", "煤炭": "515220",
    "沪深300": "510300", "上证50": "510050", "中证500": "510500",
    "科创50": "588000", "创业板": "159915", "微盘": "563300",
    "半导体": "512480", "芯片": "159995", "人工智能": "159819",
    "游戏": "159869", "传媒": "512980", "光伏": "515790",
    "新能源": "515030", "白酒": "161725", "医疗": "512170",
    "医药": "512010", "证券": "512000", "银行": "512800",
    "纳斯达克": "513100", "纳指": "513100", "标普500": "513500",
    "恒生科技": "513180", "恒生互联网": "513330", "中概互联": "513050",
    "恒生指数": "159920", "日经": "513520", "港股通互联网": "159792",
}

# --- 1. 基础数据获取 ---
def get_tencent_code(symbol):
    s = str(symbol).strip().upper()
    if s.isalpha(): return f"us{s}"
    if len(s) == 5 and s.isdigit(): return f"hk{s}"
    if len(s) == 6 and s.isdigit():
        if s.startswith(('5','6','9')): return f"sh{s}"
        if s.startswith(('0','1','2','3')): return f"sz{s}"
    return None

def fetch_quotes_universal(code_list):
    if not code_list: return {}, 0.0
    unique_codes = list(set(code_list))
    t_codes = []
    map_ref = {}
    need_fx = False
    for c in unique_codes:
        tc = get_tencent_code(c)
        if tc:
            key = f"s_{tc}"
            t_codes.append(key)
            map_ref[key] = c
            if "us" in tc: need_fx = True
    if need_fx: t_codes.append("s_usUSDCNH")
    res_dict = {}
    fx_change = 0.0
    try:
        rand_param = int(time.time() * 1000)
        url = f"http://qt.gtimg.cn/q={','.join(t_codes)}&_={rand_param}"
        r = requests.get(url, timeout=3)
        r.encoding = 'gbk'
        for line in r.text.split(';'):
            if '=' not in line: continue
            k, v = line.split('=', 1)
            data = v.strip('"').split('~')
            if len(data) < 6: continue
            if "s_usUSDCNH" in k:
                try: fx_change = float(data[5])
                except: pass
            else:
                key_clean = k.split('v_')[-1]
                raw = map_ref.get(key_clean)
                if raw:
                    try: res_dict[raw] = float(data[5])
                    except: pass
    except: pass
    return res_dict, fx_change

def get_fund_base_info_robust(fund_code):
    name = f"基金{fund_code}"
    nav = 0.0
    try:
        ts = int(time.time() * 1000)
        url = f"http://qt.gtimg.cn/q=jj{fund_code}&t={ts}"
        r = requests.get(url, timeout=2)
        r.encoding = 'gbk'
        if '="' in r.text:
            data = r.text.split('="')[1].split('~')
            if len(data) > 3:
                name = data[1]
                try: nav = float(data[3])
                except: nav = 0.0
    except: pass
    return name, nav

@st.cache_data(ttl=3600)
def get_fund_history_data(fund_code):
    dates = []
    navs = []
    try:
        ts = int(time.time() * 1000)
        url = f"http://api.fund.eastmoney.com/f10/lsjz?fundCode={fund_code}&pageIndex=1&pageSize=10&startDate=&endDate=&_={ts}"
        headers = {"Referer": "http://fundf10.eastmoney.com/"}
        res = requests.get(url, headers=headers, timeout=3).json()
        
        if "Data" in res and "LSJZList" in res["Data"]:
            data_list = res["Data"]["LSJZList"]
            for item in data_list[:7]: 
                raw_date = item["FSRQ"]
                short_date = raw_date[5:] 
                dates.append(short_date)
                navs.append(float(item["DWJZ"]))
            dates.reverse()
            navs.reverse()
    except: pass
    if not dates: return pd.DataFrame()
    return pd.DataFrame({"Date": dates, "NAV": navs})

# --- 2. 绘图函数 ---
def plot_mini_trend(df, color_code):
    if df.empty: return None
    fig, ax = plt.subplots(figsize=(5, 1.5))
    x = df["Date"]
    y = df["NAV"]
    line_color = "#d62728" if color_code == "red" else "#2ca02c"
    ax.plot(x, y, color=line_color, linewidth=2, marker='o', markersize=3)
    ax.fill_between(x, y, y.min(), color=line_color, alpha=0.1)
    
    y_min, y_max = y.min(), y.max()
    margin = (y_max - y_min) * 0.1 if y_max != y_min else y_min * 0.01
    ax.set_ylim(y_min - margin, y_max + margin)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    ax.tick_params(axis='both', which='major', labelsize=8)
    plt.xticks(rotation=0) 
    plt.tight_layout()
    return fig

# --- 3. 核心分析逻辑 ---
def analyze_fund_full(fund_code, holding_amount):
    fund_name, last_nav = get_fund_base_info_robust(fund_code)
    
    hist_df = get_fund_history_data(fund_code)
    if last_nav <= 0 and not hist_df.empty:
        try: last_nav = float(hist_df["NAV"].iloc[-1])
        except: pass
    
    today_idx = datetime.datetime.now().weekday()
    is_weekend = today_idx >= 5 
    
    est_change = 0.0
    method = "❌ 未知"
    
    if "债" in fund_name and "可转债" not in fund_name:
        est_change = 0.0
        method = "🛡️ 债券基金"
    
    elif not method.startswith("🛡️"):
        found_proxy = False
        for kw, proxy in PROXY_MAP.items():
            if kw in fund_name:
                q, _ = fetch_quotes_universal([proxy])
                est_change = q.get(proxy, 0.0)
                method = "⚡ 行业锚定"
                found_proxy = True
                break
        
        if not found_proxy:
            holdings_df = pd.DataFrame()
            try:
                cur_year = datetime.datetime.now().year
                for y in [cur_year, cur_year-1]:
                    df = ak.fund_portfolio_hold_em(symbol=fund_code, date=str(y))
                    if not df.empty:
                        holdings_df = df[df['季度'] == df['季度'].max()].copy()
                        break
            except: pass
            
            if not holdings_df.empty:
                stocks = holdings_df['股票代码'].astype(str).tolist()
                weights = pd.to_numeric(holdings_df['占净值比例'], errors='coerce') / 100
                quotes, fx = fetch_quotes_universal(stocks)
                total_w = 0; total_c = 0; us_count = 0
                for i, s in enumerate(stocks):
                    if s in quotes:
                        w = weights.iloc[i]
                        c = quotes[s]
                        if s.isalpha(): c += fx; us_count += 1
                        total_c += w * c; total_w += w
                if total_w > 0.05:
                    est_change = total_c / total_w
                    if us_count > 3: method = "🇺🇸 美股穿透"
                    else: method = "📈 持仓穿透"
    
    try:
        safe_amount = float(holding_amount)
        if math.isnan(safe_amount): safe_amount = 0.0
    except: safe_amount = 0.0

    if is_weekend:
        est_nav = last_nav
        profit = 0.0 
    else:
        profit = safe_amount * (est_change / 100)
        est_nav = last_nav * (1 + est_change / 100) if last_nav > 0 else 0.0
    
    return {
        "code": fund_code, "name": fund_name, "change_pct": est_change, 
        "profit": profit, "amount": safe_amount, "method": method,
        "last_nav": last_nav, "est_nav": est_nav,
        "is_weekend": is_weekend
    }

# --- 4. Streamlit 界面 ---
st.set_page_config(page_title="基金估值Pro", page_icon="💰", layout="wide")

# ==================== 📢 弹窗逻辑 ====================
@st.dialog("🚀 服务升级 & 调价预告")
def show_announcement():
    st.markdown("""
    **感谢支持！新版本核心功能（智能净值修复、走势图、节假日休市检测）已上线。**
    
    **⚠️ 关于下周一调价的说明：**
    由于定价门槛较低，近期出现大量恶意退款及差评，严重影响了开发热情。为了保障服务质量，我们将于 **下周一（开盘后）正式上调价格，并取消免费版本**。
    
    **✅ 对您的影响：**
    1. **已购买用户（含Pro）：** 永久不受影响，无需补差价，享受后续所有更新。
    2. **还在犹豫的朋友：** 建议趁调价前锁定当前权益。
    
    *我们希望筛选出真正认可价值的朋友。感谢您的理解与支持！*
    """)
    if st.button("我知道了", type="primary", use_container_width=True):
        st.session_state.announcement_shown = True
        st.rerun()

# 控制弹窗只显示一次
if "announcement_shown" not in st.session_state:
    show_announcement()
# ====================================================

if "fund_data" not in st.session_state:
    st.session_state.fund_data = pd.DataFrame([
        {"代码": "013403", "持仓金额": 10000.50, "备注": "演示持仓"},
        {"代码": "005827", "持仓金额": 0.00, "备注": "演示观察"},
    ])
if "vip_unlocked" not in st.session_state:
    st.session_state.vip_unlocked = False

today_idx = datetime.datetime.now().weekday()
title_suffix = "(☕ 休市中)" if today_idx >= 5 else "(🚀 交易中)"

st.markdown(f"### 💰 基金实盘估值 {title_suffix}")

# === 侧边栏反馈入口 ===
with st.sidebar:
    st.info(CONTACT_TIP, icon="📩")
# =====================

with st.expander("📝 编辑持仓 (支持粘贴Excel)", expanded=True):
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🗑️ 清空表格"):
            st.session_state.fund_data = pd.DataFrame([{"代码": "", "持仓金额": 0.00, "备注": ""}])
            st.rerun()

    edited_df = st.data_editor(
        st.session_state.fund_data,
        num_rows="dynamic",
        column_config={
            "代码": st.column_config.TextColumn(help="6位代码"),
            "持仓金额": st.column_config.NumberColumn(min_value=0.0, format="%.2f", step=0.01),
            "备注": st.column_config.TextColumn(),
        },
        use_container_width=True
    )

start_calc = st.button("🚀 开始估值", type="primary", use_container_width=True)

if start_calc or st.session_state.get('show_results', False):
    st.session_state.show_results = True
    
    mask_has_code = edited_df["代码"].astype(str).str.strip() != ""
    valid_rows = edited_df[mask_has_code].copy()
    valid_rows["持仓金额"] = pd.to_numeric(valid_rows["持仓金额"], errors='coerce').fillna(0.0)
    
    if valid_rows.empty:
        st.warning("请至少输入一行基金代码")
        st.stop()

    if not st.session_state.vip_unlocked:
        st.divider()
        with st.container():
            st.warning("🔒 正在计算收益... (高级功能已锁定)")
            c1, c2 = st.columns([3, 1])
            with c1:
                pwd_input = st.text_input(UNLOCK_HINT, key="pwd_try", placeholder="请输入闲鱼/小红书获取的卡密").strip()
            with c2:
                st.write("") 
                st.write("") 
                if st.button("🔓 立即验证"):
                    if pwd_input in VALID_VIP_CODES:
                        st.session_state.vip_unlocked = True
                        st.success("✅ 验证成功！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 无效的兑换码")
            st.caption(f"💡 {BUY_GUIDE}")
            
        st.markdown("---")
        st.subheader("📊 基础估值 (预览)")
        for index, row in valid_rows.iterrows():
            code = str(row["代码"]).strip()
            res = analyze_fund_full(code, 0.0)
            val = res['change_pct']
            color_hex = "red" if val > 0 else "green"
            
            with st.container():
                st.markdown(f"#### {res['name']}")
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("参考涨跌", f"{val:+.2f}%")
                with c2: st.metric("最新净值", f"{res['last_nav']:.4f}")
                with c3: 
                    if res['is_weekend']:
                        st.metric("今日估值", f"{res['est_nav']:.4f}", help="周末休市，显示最新已更新净值")
                    else:
                        st.metric("今日估值", f"{res['est_nav']:.4f}")
                
                hist_df = get_fund_history_data(res['code'])
                if not hist_df.empty:
                    fig = plot_mini_trend(hist_df, color_hex)
                    st.pyplot(fig, use_container_width=True)
                st.divider()
    else:
        st.markdown("---")
        total_profit = 0.0
        results = []
        progress_bar = st.progress(0)
        
        for index, row in valid_rows.iterrows():
            code = str(row["代码"]).strip()
            amount = float(row["持仓金额"])
            res = analyze_fund_full(code, amount)
            results.append(res)
            if not math.isnan(res['profit']):
                total_profit += res['profit']
            progress_bar.progress((index + 1) / len(valid_rows))
        
        progress_bar.empty()
        
        if math.isnan(total_profit): total_profit = 0.0
        bg_color = "#ffebee" if total_profit > 0 else "#e8f5e9"
        border_color = "red" if total_profit > 0 else "green"
        sign = "+" if total_profit > 0 else ""
        
        if results[0]['is_weekend']:
            st.info("☕ 周末休市中，下方显示已更新的最新净值 (今日无新增变动)")
        else:
            st.markdown(
                f"""
                <div style="background-color:{bg_color}; padding:15px; border-radius:10px; border-left: 5px solid {border_color}; text-align:center; margin-bottom: 20px;">
                    <h4 style="margin:0; color:#666;">今日预估总盈亏 (Pro)</h4>
                    <h2 style="margin:5px 0; color:{border_color};">{sign}{total_profit:,.2f} 元</h2>
                </div>
                """, unsafe_allow_html=True)
        
        for res in results:
            val = res['change_pct']
            profit = res['profit']
            color_hex = "red" if val > 0 else "green"
            
            with st.container():
                st.markdown(f"#### {res['name']}")
                st.caption(f"{res['code']} | {res['method']}")
                
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("参考涨跌", f"{val:+.2f}%")
                with c2: st.metric("最新净值", f"{res['last_nav']:.4f}")
                with c3: st.metric("今日估值", f"{res['est_nav']:.4f}")
                
                if res['amount'] > 0 and not res['is_weekend']:
                    st.info(f"💰 今日持仓盈亏: {profit:+.2f} 元 (本金: {res['amount']})")
                
                hist_df = get_fund_history_data(res['code'])
                if not hist_df.empty:
                    fig = plot_mini_trend(hist_df, color_hex)
                    st.pyplot(fig, use_container_width=True)
                else:
                    st.caption("暂无历史数据")
                st.divider()

# === 底部反馈提示 (补充) ===
st.markdown("---")
st.caption(CONTACT_TIP)