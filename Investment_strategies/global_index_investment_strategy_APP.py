import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="ETF Global Rotation Strategy Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.5rem;
        color: #424242;
        border-bottom: 2px solid #1E88E5;
        padding-bottom: 0.5rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f5f5f5;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton button {
        background-color: #1E88E5;
        color: white;
        font-weight: bold;
    }
    .info-box {
        background-color: #E3F2FD;
        border-left: 4px solid #1E88E5;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

class ETFGlobalRotationDashboard:
    def __init__(self):
        """Initialize the dashboard"""
        # Default configuration
        self.default_etfs = {
            'US': {'ticker': 'SPY', 'weight': 40, 'color': '#2196F3'},
            'Europe': {'ticker': 'VGK', 'weight': 25, 'color': '#4CAF50'},
            'Asia': {'ticker': 'VPL', 'weight': 20, 'color': '#FF9800'},
            'Japan': {'ticker': 'EWJ', 'weight': 15, 'color': '#9C27B0'}
        }
        
        # Initialize session state
        if 'analysis_results' not in st.session_state:
            st.session_state.analysis_results = None
        if 'portfolio_history' not in st.session_state:
            st.session_state.portfolio_history = None
        if 'allocations_history' not in st.session_state:
            st.session_state.allocations_history = None

    def setup_sidebar(self):
        """Configure the sidebar with user inputs"""
        st.sidebar.markdown("## 📋 Strategy Configuration")
        
        # Date range selection
        st.sidebar.markdown("### 📅 Date Range")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime(2015, 1, 1),
                max_value=datetime.today() - timedelta(days=365),
                help="Select the start date for analysis"
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.today(),
                min_value=datetime(2015, 1, 2),
                help="Select the end date for analysis"
            )
        
        # Strategy Selection
        st.sidebar.markdown("### 🎯 Strategy Type")
        strategy_type = st.sidebar.selectbox(
            "Select Strategy",
            ["Momentum Rotation", "VIX Rotation", "Combined Strategy"],
            index=0,
            help="Choose between momentum-based rotation, VIX-based rotation, or combined approach"
        )
        
        # Strategy parameters
        st.sidebar.markdown("### ⚙️ Strategy Parameters")
        
        if strategy_type != "VIX Rotation Only":
            st.sidebar.markdown("#### Momentum Settings")
            
            # Momentum Lookback Period with better explanation
            lookback_period = st.sidebar.slider(
                "Momentum Lookback Period",
                min_value=21,
                max_value=252,
                value=126,
                step=21,
                help="""
                **How it works:** 
                - This determines how many past trading days to use when calculating momentum
                - Shorter periods (30-60 days) capture recent trends
                - Longer periods (180-252 days) provide smoother, more stable signals
                - 126 days ≈ 6 months of trading days
                
                **Example:**
                - If set to 126 days, the strategy calculates the 6-month return for each ETF
                - The top-performing ETF gets higher allocation
                """
            )
            
            # Rebalance Threshold with better explanation
            rebalance_threshold = st.sidebar.slider(
                "Rebalance Threshold",
                min_value=1,
                max_value=30,
                value=10,
                step=1,
                help="""
                **How it works:**
                - This is the minimum allocation change required to trigger a rebalance
                - Lower threshold = more frequent rebalancing (higher turnover)
                - Higher threshold = less frequent rebalancing (lower transaction costs)
                
                **Example:**
                - If set to 10% and an ETF's target allocation changes from 30% to 42% (12% change)
                - Since 12% > 10%, a rebalance will be triggered
                - If change was only 8%, no rebalance would occur
                """
            )
        else:
            lookback_period = 126
            rebalance_threshold = 10
        
        if strategy_type != "Momentum Rotation Only":
            st.sidebar.markdown("#### VIX Rotation Settings")
            
            # Monthly VIX Strategy Settings
            st.sidebar.markdown("**Monthly VIX Rebalancing**")
            
            col1, col2 = st.sidebar.columns(2)
            with col1:
                vix_high_threshold = st.slider(
                    "VIX Sell Threshold",
                    min_value=15,
                    max_value=40,
                    value=20,
                    step=1,
                    help="When VIX closes above this level at month-end, rotate out of US"
                )
            
            with col2:
                vix_low_threshold = st.slider(
                    "VIX Buy Threshold",
                    min_value=10,
                    max_value=30,
                    value=15,
                    step=1,
                    help="When VIX closes below this level at month-end, rotate back into US"
                )
            
            # Rotation percentages
            st.sidebar.markdown("**Rotation Amounts**")
            
            rotate_out_pct = st.slider(
                "Reduce US by (%) when VIX High",
                min_value=10,
                max_value=100,
                value=50,
                step=5,
                help="Percentage of US allocation to move to other regions when VIX is high"
            )
            
            rotate_back_pct = st.slider(
                "Increase US by (%) when VIX Low",
                min_value=10,
                max_value=100,
                value=100,
                step=5,
                help="Percentage to return to original US allocation when VIX is low"
            )
            
            # VIX calculation method
            vix_method = st.sidebar.radio(
                "VIX Calculation Method",
                ["Month-end close", "Monthly average"],
                index=0,
                help="Use VIX closing value at month-end or monthly average"
            )
        else:
            vix_high_threshold = 20
            vix_low_threshold = 15
            rotate_out_pct = 50
            rotate_back_pct = 100
            vix_method = "Month-end close"
        
        # Portfolio configuration
        st.sidebar.markdown("### 💼 Portfolio Allocation")
        st.sidebar.markdown("Adjust weights for each region (must sum to 100%):")
        
        etf_config = {}
        total_weight = 0
        
        for region, config in self.default_etfs.items():
            weight = st.sidebar.slider(
                f"{region} Weight (%)",
                min_value=0,
                max_value=100,
                value=config['weight'],
                step=1,
                key=f"weight_{region}"
            )
            etf_config[region] = {
                'ticker': config['ticker'],
                'weight': weight / 100,
                'color': config['color'],
                'target_weight': weight / 100  # Store target weight for VIX strategy
            }
            total_weight += weight
        
        # Validate weights
        if total_weight != 100:
            st.sidebar.warning(f"⚠️ Total weights sum to {total_weight}%. Must equal 100%.")
            st.sidebar.info("Adjust weights until they sum to 100%")
        
        # Custom ETF tickers
        st.sidebar.markdown("### 🔧 Custom ETF Tickers")
        use_custom_tickers = st.sidebar.checkbox("Use custom tickers")
        
        if use_custom_tickers:
            for region in etf_config:
                new_ticker = st.sidebar.text_input(
                    f"{region} Ticker",
                    value=etf_config[region]['ticker'],
                    key=f"ticker_{region}"
                )
                etf_config[region]['ticker'] = new_ticker
        
        # Initialize portfolio
        initial_capital = st.sidebar.number_input(
            "Initial Portfolio Value ($)",
            min_value=1000,
            max_value=1000000,
            value=10000,
            step=1000
        )
        
        # Run analysis button
        st.sidebar.markdown("---")
        run_analysis = st.sidebar.button(
            "🚀 Run Analysis",
            type="primary",
            use_container_width=True
        )
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'strategy_type': strategy_type,
            'vix_high_threshold': vix_high_threshold,
            'vix_low_threshold': vix_low_threshold,
            'rotate_out_pct': rotate_out_pct / 100,
            'rotate_back_pct': rotate_back_pct / 100,
            'vix_method': vix_method,
            'rebalance_threshold': rebalance_threshold / 100,
            'lookback_period': lookback_period,
            'etf_config': etf_config,
            'initial_capital': initial_capital,
            'run_analysis': run_analysis,
            'weights_valid': total_weight == 100
        }

    def fetch_data(self, etf_config, start_date, end_date):
        """Fetch historical data for all ETFs and indicators"""
        data = {}
        
        with st.spinner("📥 Fetching market data..."):
            progress_bar = st.progress(0)
            total_etfs = len(etf_config)
            
            for i, (region, config) in enumerate(etf_config.items()):
                ticker = config['ticker']
                try:
                    etf_data = yf.download(
                        ticker, 
                        start=start_date, 
                        end=end_date,
                        progress=False
                    )
                    
                    if not etf_data.empty:
                        # Handle MultiIndex columns
                        if etf_data.columns.nlevels > 1:
                            etf_data.columns = etf_data.columns.droplevel(1)
                        
                        # Get price column
                        price_col = 'Adj Close' if 'Adj Close' in etf_data.columns else 'Close'
                        
                        data[region] = {
                            'ticker': ticker,
                            'price': etf_data[price_col],
                            'returns': etf_data[price_col].pct_change(),
                            'color': config['color'],
                            'target_weight': config['target_weight']
                        }
                    
                    progress_bar.progress((i + 1) / (total_etfs + 1))
                    
                except Exception as e:
                    st.error(f"Error fetching {region} data ({ticker}): {e}")
            
            # Fetch VIX data
            try:
                vix_data = yf.download('^VIX', start=start_date, end=end_date, progress=False)
                if not vix_data.empty:
                    if vix_data.columns.nlevels > 1:
                        vix_data.columns = vix_data.columns.droplevel(1)
                    vix_col = 'Adj Close' if 'Adj Close' in vix_data.columns else 'Close'
                    data['VIX'] = {
                        'price': vix_data[vix_col],
                        'returns': vix_data[vix_col].pct_change()
                    }
                
                progress_bar.progress(1.0)
                
            except Exception as e:
                st.warning(f"Could not fetch VIX data: {e}")
        
        return data

    def calculate_performance_metrics(self, data):
        """Calculate performance metrics for each ETF"""
        performance_data = {}
        
        for region, region_data in data.items():
            if region != 'VIX' and 'price' in region_data:
                prices = region_data['price']
                returns = region_data['returns'].dropna()
                
                if len(prices) > 0 and len(returns) > 0:
                    # Calculate metrics
                    total_return = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
                    days = len(prices)
                    
                    # Annualized metrics
                    annual_return = ((1 + total_return/100) ** (252/days) - 1) * 100
                    volatility = returns.std() * np.sqrt(252) * 100
                    sharpe_ratio = (annual_return / volatility) if volatility != 0 else 0
                    
                    # Maximum drawdown
                    cumulative_returns = (1 + returns).cumprod()
                    running_max = cumulative_returns.expanding().max()
                    drawdown = (cumulative_returns - running_max) / running_max * 100
                    max_drawdown = drawdown.min()
                    
                    # Sortino ratio
                    downside_returns = returns[returns < 0]
                    downside_dev = downside_returns.std() * np.sqrt(252) * 100 if len(downside_returns) > 0 else 0
                    sortino_ratio = (annual_return / downside_dev) if downside_dev != 0 else 0
                    
                    # Calmar ratio
                    calmar_ratio = (annual_return / abs(max_drawdown)) if max_drawdown != 0 else 0
                    
                    performance_data[region] = {
                        'Total Return (%)': round(total_return, 2),
                        'Annual Return (%)': round(annual_return, 2),
                        'Volatility (%)': round(volatility, 2),
                        'Sharpe Ratio': round(sharpe_ratio, 3),
                        'Max Drawdown (%)': round(max_drawdown, 2),
                        'Sortino Ratio': round(sortino_ratio, 3),
                        'Calmar Ratio': round(calmar_ratio, 3),
                        'Color': region_data['color']
                    }
        
        return performance_data

    def backtest_momentum_strategy(self, data, etf_config, initial_capital, rebalance_threshold, lookback_period):
        """Backtest momentum-based rotation strategy"""
        # Prepare returns data
        portfolio_returns = pd.DataFrame()
        weights_dict = {region: config['weight'] for region, config in etf_config.items()}
        
        for region in weights_dict:
            if region in data and 'returns' in data[region]:
                portfolio_returns[region] = data[region]['returns']
        
        if portfolio_returns.empty:
            return None, None, None
        
        portfolio_returns = portfolio_returns.dropna()
        
        if len(portfolio_returns) < lookback_period:
            return None, None, None
        
        # Initialize tracking variables
        portfolio_value = initial_capital
        portfolio_history = [portfolio_value]
        allocation_history = [weights_dict.copy()]
        current_allocation = weights_dict.copy()
        date_history = [portfolio_returns.index[lookback_period - 1]]
        rebalance_dates = []
        
        # Main backtesting loop
        for i in range(lookback_period, len(portfolio_returns)):
            # Calculate momentum
            lookback_returns = portfolio_returns.iloc[i-lookback_period:i]
            momentum = (lookback_returns + 1).prod() - 1
            
            # Rank regions by momentum
            ranked_regions = momentum.sort_values(ascending=False)
            
            # Create new allocation based on momentum
            new_allocation = {}
            
            if len(ranked_regions) > 0:
                # Top performer gets 40%, others get proportional allocation
                new_allocation[ranked_regions.index[0]] = 0.4
                
                if len(ranked_regions) > 1:
                    remaining_regions = ranked_regions.iloc[1:]
                    total_momentum = remaining_regions.sum()
                    
                    if total_momentum > 0:
                        for j, region in enumerate(remaining_regions.index):
                            new_allocation[region] = 0.6 * (remaining_regions.iloc[j] / total_momentum)
                    else:
                        for region in remaining_regions.index:
                            new_allocation[region] = 0.6 / len(remaining_regions)
            else:
                new_allocation = current_allocation
            
            # Check if rebalance is needed
            rebalance_needed = False
            for region in set(list(current_allocation.keys()) + list(new_allocation.keys())):
                current_weight = current_allocation.get(region, 0)
                new_weight = new_allocation.get(region, 0)
                if abs(new_weight - current_weight) > rebalance_threshold:
                    rebalance_needed = True
                    break
            
            if rebalance_needed:
                current_allocation = new_allocation
                rebalance_dates.append(portfolio_returns.index[i])
            
            # Calculate daily return
            daily_return = 0
            for region, weight in current_allocation.items():
                if region in portfolio_returns.columns:
                    daily_return += weight * portfolio_returns.iloc[i][region]
            
            portfolio_value *= (1 + daily_return)
            portfolio_history.append(portfolio_value)
            allocation_history.append(current_allocation.copy())
            date_history.append(portfolio_returns.index[i])
        
        # Calculate benchmark (equal weight)
        equal_weight_returns = portfolio_returns.iloc[lookback_period:].mean(axis=1)
        benchmark_value = initial_capital * (1 + equal_weight_returns).cumprod()
        
        return pd.Series(portfolio_history, index=date_history), allocation_history, benchmark_value, rebalance_dates

    def backtest_vix_strategy(self, data, etf_config, initial_capital, vix_high_threshold, 
                             vix_low_threshold, rotate_out_pct, rotate_back_pct, vix_method):
        """Backtest monthly VIX-based rotation strategy"""
        # Prepare returns data
        portfolio_returns = pd.DataFrame()
        weights_dict = {region: config['weight'] for region, config in etf_config.items()}
        
        for region in weights_dict:
            if region in data and 'returns' in data[region]:
                portfolio_returns[region] = data[region]['returns']
        
        if portfolio_returns.empty or 'VIX' not in data:
            return None, None, None, None
        
        portfolio_returns = portfolio_returns.dropna()
        
        # Get VIX data
        vix_data = data['VIX']['price']
        
        # Resample to monthly frequency
        if vix_method == "Month-end close":
            # Use last trading day of month
            vix_monthly = vix_data.resample('M').last()
        else:  # Monthly average
            vix_monthly = vix_data.resample('M').mean()
        
        # Create monthly rebalance dates (first trading day of each month)
        monthly_dates = portfolio_returns.resample('MS').first().index
        
        # Initialize tracking variables
        portfolio_value = initial_capital
        portfolio_history = []
        allocation_history = []
        date_history = []
        current_allocation = weights_dict.copy()
        vix_signals = []
        rebalance_dates = []
        
        # Track original US allocation
        original_us_weight = etf_config['US']['weight'] if 'US' in etf_config else 0
        
        # Initialize with first date
        start_idx = portfolio_returns.index.get_loc(monthly_dates[0]) if monthly_dates[0] in portfolio_returns.index else 0
        portfolio_history.append(portfolio_value)
        allocation_history.append(current_allocation.copy())
        date_history.append(portfolio_returns.index[start_idx])
        
        # Backtest loop (monthly)
        for i in range(1, len(monthly_dates)):
            current_date = monthly_dates[i]
            if current_date not in portfolio_returns.index:
                continue
            
            # Get VIX value for previous month
            prev_month = current_date - pd.DateOffset(months=1)
            prev_month_key = prev_month.strftime('%Y-%m')
            vix_value = None
            
            # Find VIX value for previous month
            for date in vix_monthly.index:
                if date.strftime('%Y-%m') == prev_month_key:
                    vix_value = vix_monthly.loc[date]
                    break
            
            if vix_value is not None:
                # Determine VIX signal
                if vix_value > vix_high_threshold:
                    signal = "HIGH"
                    # Rotate out of US
                    us_weight = current_allocation.get('US', 0)
                    if us_weight > 0:
                        # Calculate reduction
                        reduction = us_weight * rotate_out_pct
                        new_us_weight = us_weight - reduction
                        
                        # Distribute reduction to other regions proportionally
                        non_us_regions = [r for r in current_allocation.keys() if r != 'US']
                        total_non_us = sum(current_allocation[r] for r in non_us_regions)
                        
                        if total_non_us > 0:
                            for region in non_us_regions:
                                proportion = current_allocation[region] / total_non_us
                                current_allocation[region] += reduction * proportion
                        
                        current_allocation['US'] = new_us_weight
                        rebalance_dates.append(current_date)
                
                elif vix_value < vix_low_threshold:
                    signal = "LOW"
                    # Rotate back into US
                    current_us_weight = current_allocation.get('US', 0)
                    target_us_weight = original_us_weight
                    
                    if current_us_weight < target_us_weight:
                        # Calculate amount to add back
                        add_back = min(target_us_weight - current_us_weight, 
                                     target_us_weight * rotate_back_pct)
                        
                        # Take from other regions proportionally
                        non_us_regions = [r for r in current_allocation.keys() if r != 'US']
                        total_non_us = sum(current_allocation[r] for r in non_us_regions)
                        
                        if total_non_us > 0:
                            for region in non_us_regions:
                                proportion = current_allocation[region] / total_non_us
                                current_allocation[region] -= add_back * proportion
                                current_allocation[region] = max(0, current_allocation[region])
                        
                        current_allocation['US'] += add_back
                        rebalance_dates.append(current_date)
                else:
                    signal = "NEUTRAL"
                
                vix_signals.append({
                    'date': current_date,
                    'vix': vix_value,
                    'signal': signal
                })
            
            # Get returns for the month
            month_start = current_date
            month_end = monthly_dates[i+1] if i+1 < len(monthly_dates) else portfolio_returns.index[-1]
            
            month_returns = portfolio_returns.loc[month_start:month_end]
            
            # Calculate portfolio value through the month
            for idx, daily_return in month_returns.iterrows():
                # Calculate weighted return
                daily_portfolio_return = 0
                for region, weight in current_allocation.items():
                    if region in daily_return.index:
                        daily_portfolio_return += weight * daily_return[region]
                
                portfolio_value *= (1 + daily_portfolio_return)
                portfolio_history.append(portfolio_value)
                allocation_history.append(current_allocation.copy())
                date_history.append(idx)
        
        # Convert to Series
        portfolio_series = pd.Series(portfolio_history, index=date_history)
        
        # Calculate benchmark (equal weight)
        equal_weight_returns = portfolio_returns.loc[date_history[0]:].mean(axis=1)
        benchmark_value = initial_capital * (1 + equal_weight_returns).cumprod()
        
        return portfolio_series, allocation_history, benchmark_value, pd.DataFrame(vix_signals)

    def backtest_combined_strategy(self, data, etf_config, initial_capital, config_params):
        """Backtest combined momentum and VIX strategy"""
        # Get momentum results
        momentum_results = self.backtest_momentum_strategy(
            data, etf_config, initial_capital,
            config_params['rebalance_threshold'],
            config_params['lookback_period']
        )
        
        # Get VIX results
        vix_results = self.backtest_vix_strategy(
            data, etf_config, initial_capital,
            config_params['vix_high_threshold'],
            config_params['vix_low_threshold'],
            config_params['rotate_out_pct'],
            config_params['rotate_back_pct'],
            config_params['vix_method']
        )
        
        if momentum_results[0] is None or vix_results[0] is None:
            return None, None, None, None
        
        # Combine strategies (equal weight between momentum and VIX signals)
        momentum_portfolio = momentum_results[0]
        vix_portfolio = vix_results[0]
        
        # Align dates
        common_dates = momentum_portfolio.index.intersection(vix_portfolio.index)
        if len(common_dates) == 0:
            return momentum_results  # Fallback to momentum
        
        # Combine portfolios (50% momentum, 50% VIX)
        combined_portfolio = (momentum_portfolio.loc[common_dates] * 0.5 + 
                             vix_portfolio.loc[common_dates] * 0.5)
        
        # For simplicity, use momentum allocations
        combined_allocations = momentum_results[1]
        
        # Calculate benchmark
        portfolio_returns = pd.DataFrame()
        for region in etf_config:
            if region in data and 'returns' in data[region]:
                portfolio_returns[region] = data[region]['returns']
        
        portfolio_returns = portfolio_returns.dropna()
        equal_weight_returns = portfolio_returns.loc[common_dates].mean(axis=1)
        benchmark_value = initial_capital * (1 + equal_weight_returns).cumprod()
        
        return combined_portfolio, combined_allocations, benchmark_value, None

    def create_dashboard(self, config, data, performance_metrics, backtest_results, vix_signals=None):
        """Create the main dashboard visualizations"""
        
        # Header
        st.markdown('<h1 class="main-header">📈 ETF Global Rotation Strategy Dashboard</h1>', unsafe_allow_html=True)
        
        # Strategy Info Box
        strategy_info = f"""
        <div class="info-box">
            <strong>Active Strategy:</strong> {config['strategy_type']}<br>
            <strong>Date Range:</strong> {config['start_date']} to {config['end_date']}<br>
            <strong>Initial Capital:</strong> ${config['initial_capital']:,.0f}
        </div>
        """
        st.markdown(strategy_info, unsafe_allow_html=True)
        
        if backtest_results[0] is None:
            st.error("Unable to backtest strategy with current parameters. Please adjust settings.")
            return
        
        portfolio_history, allocations_history, benchmark_history, _ = backtest_results
        
        # Key Metrics Row
        st.markdown('<h2 class="section-header">📊 Key Performance Metrics</h2>', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_return = (portfolio_history.iloc[-1] / config['initial_capital'] - 1) * 100
        annualized_return = ((1 + total_return/100) ** (252/len(portfolio_history)) - 1) * 100
        
        with col1:
            st.metric(
                "Total Return", 
                f"{total_return:.2f}%",
                f"{annualized_return:.2f}% annualized"
            )
        
        with col2:
            if benchmark_history is not None:
                benchmark_return = (benchmark_history.iloc[-1] / config['initial_capital'] - 1) * 100
                alpha = total_return - benchmark_return
                delta_color = "normal" if alpha >= 0 else "inverse"
                st.metric(
                    "Benchmark Return",
                    f"{benchmark_return:.2f}%",
                    f"Alpha: {alpha:+.2f}%",
                    delta_color=delta_color
                )
        
        with col3:
            # Calculate maximum drawdown
            returns = portfolio_history.pct_change()
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_dd = drawdown.min() * 100
            st.metric("Maximum Drawdown", f"{max_dd:.2f}%")
        
        with col4:
            volatility = returns.std() * np.sqrt(252) * 100
            sharpe = (annualized_return / volatility) if volatility != 0 else 0
            st.metric("Sharpe Ratio", f"{sharpe:.2f}")
        
        # Portfolio Performance Chart
        st.markdown('<h2 class="section-header">📈 Portfolio Performance</h2>', unsafe_allow_html=True)
        
        fig = go.Figure()
        
        # Add strategy line
        fig.add_trace(go.Scatter(
            x=portfolio_history.index,
            y=portfolio_history,
            mode='lines',
            name=f'{config["strategy_type"]}',
            line=dict(color='#1E88E5', width=3)
        ))
        
        # Add benchmark line
        if benchmark_history is not None:
            fig.add_trace(go.Scatter(
                x=benchmark_history.index,
                y=benchmark_history,
                mode='lines',
                name='Equal Weight Benchmark',
                line=dict(color='#FF5722', width=2, dash='dash')
            ))
        
        fig.update_layout(
            title=f'Portfolio Value Over Time - {config["strategy_type"]}',
            xaxis_title='Date',
            yaxis_title='Portfolio Value ($)',
            hovermode='x unified',
            template='plotly_white',
            height=500,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # VIX Signal Analysis (if applicable)
        if vix_signals is not None and not vix_signals.empty:
            st.markdown('<h2 class="section-header">📉 VIX Rotation Signals</h2>', unsafe_allow_html=True)
            
            # Create VIX signal chart
            fig = go.Figure()
            
            # Add VIX line
            if 'VIX' in data:
                vix_prices = data['VIX']['price']
                fig.add_trace(go.Scatter(
                    x=vix_prices.index,
                    y=vix_prices,
                    mode='lines',
                    name='VIX Index',
                    line=dict(color='#666', width=1)
                ))
            
            # Add signals
            high_signals = vix_signals[vix_signals['signal'] == 'HIGH']
            low_signals = vix_signals[vix_signals['signal'] == 'LOW']
            
            fig.add_trace(go.Scatter(
                x=high_signals['date'],
                y=high_signals['vix'],
                mode='markers',
                name='Sell Signal (VIX > {})'.format(config['vix_high_threshold']),
                marker=dict(
                    color='red',
                    size=10,
                    symbol='triangle-down'
                )
            ))
            
            fig.add_trace(go.Scatter(
                x=low_signals['date'],
                y=low_signals['vix'],
                mode='markers',
                name='Buy Signal (VIX < {})'.format(config['vix_low_threshold']),
                marker=dict(
                    color='green',
                    size=10,
                    symbol='triangle-up'
                )
            ))
            
            # Add threshold lines
            fig.add_hline(
                y=config['vix_high_threshold'],
                line_dash="dash",
                line_color="red",
                annotation_text=f"Sell Threshold: {config['vix_high_threshold']}",
                annotation_position="top right"
            )
            
            fig.add_hline(
                y=config['vix_low_threshold'],
                line_dash="dash",
                line_color="green",
                annotation_text=f"Buy Threshold: {config['vix_low_threshold']}",
                annotation_position="bottom right"
            )
            
            fig.update_layout(
                title='VIX Signals and Rotation Triggers',
                xaxis_title='Date',
                yaxis_title='VIX Level',
                hovermode='x unified',
                template='plotly_white',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Signal statistics
            col1, col2, col3, col4 = st.columns(4)
            
            total_signals = len(vix_signals)
            high_signals_count = len(high_signals)
            low_signals_count = len(low_signals)
            
            with col1:
                st.metric("Total Signals", total_signals)
            with col2:
                st.metric("Sell Signals", high_signals_count, 
                         f"{high_signals_count/total_signals*100:.1f}%")
            with col3:
                st.metric("Buy Signals", low_signals_count,
                         f"{low_signals_count/total_signals*100:.1f}%")
            with col4:
                avg_vix = vix_signals['vix'].mean()
                st.metric("Average VIX", f"{avg_vix:.1f}")
        
        # ETF Performance Comparison
        st.markdown('<h2 class="section-header">🌍 Regional ETF Performance</h2>', unsafe_allow_html=True)
        
        if performance_metrics:
            # Create comparison charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Returns comparison
                regions = list(performance_metrics.keys())
                returns = [performance_metrics[r]['Annual Return (%)'] for r in regions]
                colors = [performance_metrics[r]['Color'] for r in regions]
                
                fig1 = go.Figure(data=[
                    go.Bar(
                        x=regions,
                        y=returns,
                        marker_color=colors,
                        text=[f'{r}%' for r in returns],
                        textposition='auto'
                    )
                ])
                fig1.update_layout(
                    title='Annual Returns by Region',
                    xaxis_title='Region',
                    yaxis_title='Annual Return (%)',
                    template='plotly_white',
                    height=400
                )
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # Risk-Return scatter
                returns = [performance_metrics[r]['Annual Return (%)'] for r in regions]
                volatilities = [performance_metrics[r]['Volatility (%)'] for r in regions]
                sharpe_ratios = [performance_metrics[r]['Sharpe Ratio'] for r in regions]
                
                fig2 = go.Figure(data=[
                    go.Scatter(
                        x=volatilities,
                        y=returns,
                        mode='markers+text',
                        marker=dict(
                            size=[abs(s)*50 for s in sharpe_ratios],
                            color=colors,
                            showscale=True,
                            colorbar=dict(title="Sharpe Ratio")
                        ),
                        text=regions,
                        textposition="top center",
                        hovertemplate="<b>%{text}</b><br>" +
                                    "Return: %{y:.2f}%<br>" +
                                    "Volatility: %{x:.2f}%<br>" +
                                    "Sharpe: %{marker.size:.2f}<extra></extra>"
                    )
                ])
                
                fig2.update_layout(
                    title='Risk-Return Profile',
                    xaxis_title='Annual Volatility (%)',
                    yaxis_title='Annual Return (%)',
                    template='plotly_white',
                    height=400
                )
                st.plotly_chart(fig2, use_container_width=True)
        
        # Allocation History
        st.markdown('<h2 class="section-header">⚖️ Portfolio Allocation Over Time</h2>', unsafe_allow_html=True)
        
        if allocations_history:
            # Convert allocation history to DataFrame
            alloc_df = pd.DataFrame(allocations_history, index=portfolio_history.index)
            
            fig = go.Figure()
            for region in alloc_df.columns:
                fig.add_trace(go.Scatter(
                    x=alloc_df.index,
                    y=alloc_df[region] * 100,
                    mode='lines',
                    name=region,
                    stackgroup='one',
                    line=dict(width=0.5),
                    fillcolor=config['etf_config'][region]['color']
                ))
            
            fig.update_layout(
                title='Portfolio Allocation (%) Over Time',
                xaxis_title='Date',
                yaxis_title='Allocation (%)',
                hovermode='x unified',
                template='plotly_white',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Detailed Performance Table
        st.markdown('<h2 class="section-header">📋 Detailed Performance Metrics</h2>', unsafe_allow_html=True)
        
        if performance_metrics:
            # Create DataFrame with additional strategy metrics
            strategy_metrics = {
                'Total Return (%)': total_return,
                'Annual Return (%)': annualized_return,
                'Volatility (%)': returns.std() * np.sqrt(252) * 100,
                'Max Drawdown (%)': max_dd,
                'Sharpe Ratio': (annualized_return / (returns.std() * np.sqrt(252) * 100)) if returns.std() > 0 else 0
            }
            
            # Display strategy metrics
            st.markdown("#### Strategy Performance")
            strategy_df = pd.DataFrame([strategy_metrics]).T
            strategy_df.columns = ['Value']
            st.dataframe(strategy_df.style.format('{:.2f}'), use_container_width=True)
            
            # Display ETF metrics
            st.markdown("#### ETF Performance Metrics")
            metrics_df = pd.DataFrame(performance_metrics).T
            st.dataframe(
                metrics_df.style.format({
                    'Total Return (%)': '{:.2f}%',
                    'Annual Return (%)': '{:.2f}%',
                    'Volatility (%)': '{:.2f}%',
                    'Max Drawdown (%)': '{:.2f}%',
                    'Sharpe Ratio': '{:.2f}',
                    'Sortino Ratio': '{:.2f}',
                    'Calmar Ratio': '{:.2f}'
                }).background_gradient(cmap='Blues', subset=['Annual Return (%)', 'Sharpe Ratio']),
                use_container_width=True
            )
        
        # VIX Analysis
        if 'VIX' in data:
            st.markdown('<h2 class="section-header">📊 VIX Market Analysis</h2>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # VIX time series
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=data['VIX']['price'].index,
                    y=data['VIX']['price'],
                    mode='lines',
                    name='VIX',
                    line=dict(color='#FF6B6B')
                ))
                
                # Add threshold lines
                fig.add_hline(
                    y=config['vix_high_threshold'],
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Sell: {config['vix_high_threshold']}",
                    annotation_position="top right"
                )
                
                fig.add_hline(
                    y=config['vix_low_threshold'],
                    line_dash="dash",
                    line_color="green",
                    annotation_text=f"Buy: {config['vix_low_threshold']}",
                    annotation_position="bottom right"
                )
                
                fig.update_layout(
                    title='VIX Index with Rotation Thresholds',
                    xaxis_title='Date',
                    yaxis_title='VIX Level',
                    template='plotly_white',
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # VIX distribution with thresholds
                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=data['VIX']['price'].dropna(),
                    nbinsx=50,
                    marker_color='#FF6B6B',
                    opacity=0.7,
                    name='VIX Distribution'
                ))
                
                # Add vertical lines for thresholds
                fig.add_vline(
                    x=config['vix_high_threshold'],
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Sell Threshold",
                    annotation_position="top"
                )
                
                fig.add_vline(
                    x=config['vix_low_threshold'],
                    line_dash="dash",
                    line_color="green",
                    annotation_text=f"Buy Threshold",
                    annotation_position="top"
                )
                
                # Calculate statistics
                vix_data = data['VIX']['price'].dropna()
                below_low = (vix_data < config['vix_low_threshold']).sum() / len(vix_data) * 100
                between = ((vix_data >= config['vix_low_threshold']) & 
                          (vix_data <= config['vix_high_threshold'])).sum() / len(vix_data) * 100
                above_high = (vix_data > config['vix_high_threshold']).sum() / len(vix_data) * 100
                
                fig.add_annotation(
                    x=0.05,
                    y=0.95,
                    xref="paper",
                    yref="paper",
                    text=f"<b>Time in Regimes:</b><br>"
                         f"Buy Zone: {below_low:.1f}%<br>"
                         f"Neutral: {between:.1f}%<br>"
                         f"Sell Zone: {above_high:.1f}%",
                    showarrow=False,
                    bgcolor="white",
                    bordercolor="black",
                    borderwidth=1
                )
                
                fig.update_layout(
                    title='VIX Distribution with Regime Zones',
                    xaxis_title='VIX Level',
                    yaxis_title='Frequency',
                    template='plotly_white',
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        # Export option
        st.markdown('<h2 class="section-header">💾 Export Results</h2>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            csv = portfolio_history.to_csv()
            st.download_button(
                label="📥 Download Portfolio History",
                data=csv,
                file_name="portfolio_history.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            if performance_metrics:
                metrics_df = pd.DataFrame(performance_metrics).T
                csv = metrics_df.to_csv()
                st.download_button(
                    label="📥 Download Performance Metrics",
                    data=csv,
                    file_name="performance_metrics.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        with col3:
            if allocations_history:
                alloc_df = pd.DataFrame(allocations_history, index=portfolio_history.index)
                csv = alloc_df.to_csv()
                st.download_button(
                    label="📥 Download Allocation History",
                    data=csv,
                    file_name="allocation_history.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    def run_dashboard(self):
        """Main function to run the dashboard"""
        # Sidebar configuration
        config = self.setup_sidebar()
        
        # Main content area
        if config['run_analysis'] and config['weights_valid']:
            # Fetch data
            data = self.fetch_data(
                config['etf_config'], 
                config['start_date'], 
                config['end_date']
            )
            
            if not data or len(data) == 0:
                st.error("Failed to fetch data. Please check your tickers and internet connection.")
                return
            
            # Calculate performance metrics
            performance_metrics = self.calculate_performance_metrics(data)
            
            # Backtest selected strategy
            vix_signals = None
            
            if config['strategy_type'] == "Momentum Rotation":
                backtest_results = self.backtest_momentum_strategy(
                    data, 
                    config['etf_config'], 
                    config['initial_capital'],
                    config['rebalance_threshold'],
                    config['lookback_period']
                )
                
            elif config['strategy_type'] == "VIX Rotation":
                backtest_results = self.backtest_vix_strategy(
                    data,
                    config['etf_config'],
                    config['initial_capital'],
                    config['vix_high_threshold'],
                    config['vix_low_threshold'],
                    config['rotate_out_pct'],
                    config['rotate_back_pct'],
                    config['vix_method']
                )
                vix_signals = backtest_results[3] if len(backtest_results) > 3 else None
                
            else:  # Combined Strategy
                backtest_results = self.backtest_combined_strategy(
                    data,
                    config['etf_config'],
                    config['initial_capital'],
                    config
                )
            
            # Store results in session state
            st.session_state.analysis_results = {
                'performance': performance_metrics,
                'backtest_results': backtest_results,
                'vix_signals': vix_signals
            }
            
            # Create dashboard
            self.create_dashboard(
                config, 
                data, 
                performance_metrics, 
                backtest_results,
                vix_signals
            )
            
        elif config['run_analysis'] and not config['weights_valid']:
            st.error("⚠️ Portfolio weights must sum to 100%! Please adjust the weights in the sidebar.")
        
        else:
            # Show welcome message with explanations
            st.markdown("""
            <div style="text-align: center; padding: 3rem 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white;">
                <h1 style="font-size: 3rem; margin-bottom: 1rem;">🎯 ETF Rotation Strategy Analyzer</h1>
                <p style="font-size: 1.2rem; margin-bottom: 2rem;">
                    Configure your strategy in the sidebar and click "Run Analysis" to begin.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Strategy explanations
            st.markdown("""
            ## 📖 Strategy Explanations
            
            ### ⚙️ **Rebalance Threshold**
            This controls how frequently your portfolio is adjusted:
            - **Low threshold (1-5%)**: Frequent rebalancing, captures small changes but increases transaction costs
            - **Medium threshold (5-15%)**: Balanced approach, rebalances when significant changes occur
            - **High threshold (15-30%)**: Infrequent rebalancing, reduces costs but may miss optimization opportunities
            
            ### 📊 **Momentum Lookback Period**
            Determines the time period used to calculate momentum:
            - **Short-term (21-63 days)**: Captures recent trends, more responsive but more volatile
            - **Medium-term (84-126 days)**: Balanced approach, captures medium-term trends
            - **Long-term (189-252 days)**: Smooth signals, captures long-term trends but slower to respond
            
            ### 📉 **VIX Rotation Strategy**
            **How it works:**
            1. **Monthly Check**: At the end of each month, check VIX level
            2. **Sell Signal**: If VIX > High Threshold, reduce US allocation by specified percentage
            3. **Buy Signal**: If VIX < Low Threshold, increase US allocation back toward target
            4. **Distribution**: Rotated amounts are distributed to/from other regions proportionally
            
            **Example:**
            - US Target: 40%, Reduce by: 50% when VIX > 20
            - If VIX = 25: New US = 40% × (1 - 50%) = 20%
            - The 20% reduction is distributed to Europe, Asia, Japan proportionally
            """)
            
            # Quick start guide
            st.markdown("""
            ## 🚀 Quick Start Guide
            
            1. **Configure Portfolio** - Adjust ETF weights in sidebar (must sum to 100%)
            2. **Choose Strategy** - Select Momentum, VIX, or Combined approach
            3. **Set Parameters** - Configure thresholds and lookback periods
            4. **Click "Run Analysis"** - Generate strategy backtest
            5. **Analyze Results** - Review performance metrics and charts
            """)

# Run the dashboard
if __name__ == "__main__":
    try:
        dashboard = ETFGlobalRotationDashboard()
        dashboard.run_dashboard()
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please check your internet connection and try again.")