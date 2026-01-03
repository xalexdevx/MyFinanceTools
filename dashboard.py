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
        
        # Initialize session state for persistent data
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
                max_value=datetime.today() - timedelta(days=365)
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.today(),
                min_value=datetime(2015, 1, 2)
            )
        
        # VIX threshold
        st.sidebar.markdown("### 📊 VIX Settings")
        vix_threshold = st.sidebar.slider(
            "VIX Threshold for Rotation Signal",
            min_value=10,
            max_value=40,
            value=20,
            step=1,
            help="When VIX exceeds this value, the strategy considers rotating out of US markets"
        )
        
        # Strategy parameters
        st.sidebar.markdown("### ⚙️ Strategy Parameters")
        rebalance_threshold = st.sidebar.slider(
            "Rebalance Threshold (%)",
            min_value=1,
            max_value=30,
            value=10,
            step=1,
            help="Minimum allocation change before triggering rebalance"
        )
        
        lookback_period = st.sidebar.slider(
            "Momentum Lookback Period (days)",
            min_value=30,
            max_value=252,
            value=126,
            step=21,
            help="Number of days to calculate momentum for rotation"
        )
        
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
                'weight': weight / 100,  # Convert to decimal
                'color': config['color']
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
            'vix_threshold': vix_threshold,
            'rebalance_threshold': rebalance_threshold / 100,  # Convert to decimal
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
                            'color': config['color']
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
                    data['VIX'] = vix_data[vix_col]
                
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
                    
                    # Sortino ratio (using downside deviation)
                    downside_returns = returns[returns < 0]
                    downside_dev = downside_returns.std() * np.sqrt(252) * 100 if len(downside_returns) > 0 else 0
                    sortino_ratio = (annual_return / downside_dev) if downside_dev != 0 else 0
                    
                    performance_data[region] = {
                        'Total Return (%)': round(total_return, 2),
                        'Annual Return (%)': round(annual_return, 2),
                        'Volatility (%)': round(volatility, 2),
                        'Sharpe Ratio': round(sharpe_ratio, 3),
                        'Max Drawdown (%)': round(max_drawdown, 2),
                        'Sortino Ratio': round(sortino_ratio, 3),
                        'Color': region_data['color']
                    }
        
        return performance_data

    def backtest_strategy(self, data, etf_config, initial_capital, rebalance_threshold, lookback_period):
        """Backtest the rotation strategy"""
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
            st.warning(f"Insufficient data for backtesting. Need at least {lookback_period} days.")
            return None, None, None
        
        # Initialize tracking variables
        portfolio_value = initial_capital
        portfolio_history = [portfolio_value]
        allocation_history = [weights_dict.copy()]
        current_allocation = weights_dict.copy()
        date_history = [portfolio_returns.index[lookback_period - 1]]
        
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
        
        return pd.Series(portfolio_history, index=date_history), allocation_history, benchmark_value

    def create_dashboard(self, config, data, performance_metrics, portfolio_history, allocations_history, benchmark_history):
        """Create the main dashboard visualizations"""
        
        # Header
        st.markdown('<h1 class="main-header">📈 ETF Global Rotation Strategy Dashboard</h1>', unsafe_allow_html=True)
        
        # Key Metrics Row
        st.markdown('<h2 class="section-header">📊 Key Performance Metrics</h2>', unsafe_allow_html=True)
        
        if portfolio_history is not None:
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
                    st.metric(
                        "Benchmark Return",
                        f"{benchmark_return:.2f}%",
                        f"Alpha: {total_return - benchmark_return:.2f}%"
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
                st.metric("Annual Volatility", f"{volatility:.2f}%")
        
        # Portfolio Performance Chart
        st.markdown('<h2 class="section-header">📈 Portfolio Performance</h2>', unsafe_allow_html=True)
        
        if portfolio_history is not None:
            fig = go.Figure()
            
            # Add strategy line
            fig.add_trace(go.Scatter(
                x=portfolio_history.index,
                y=portfolio_history,
                mode='lines',
                name='Rotation Strategy',
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
                title='Portfolio Value Over Time',
                xaxis_title='Date',
                yaxis_title='Portfolio Value ($)',
                hovermode='x unified',
                template='plotly_white',
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
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
                        mode='markers',
                        marker=dict(
                            size=[abs(s)*50 for s in sharpe_ratios],
                            color=colors,
                            showscale=True,
                            colorbar=dict(title="Sharpe Ratio")
                        ),
                        text=[f"{regions[i]}<br>Sharpe: {sharpe_ratios[i]:.2f}" for i in range(len(regions))],
                        hoverinfo='text'
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
        
        # Performance Metrics Table
        st.markdown('<h2 class="section-header">📋 Detailed Performance Metrics</h2>', unsafe_allow_html=True)
        
        if performance_metrics:
            metrics_df = pd.DataFrame(performance_metrics).T
            st.dataframe(
                metrics_df.style.format({
                    'Total Return (%)': '{:.2f}%',
                    'Annual Return (%)': '{:.2f}%',
                    'Volatility (%)': '{:.2f}%',
                    'Max Drawdown (%)': '{:.2f}%'
                }).background_gradient(cmap='Blues', subset=['Annual Return (%)', 'Sharpe Ratio']),
                use_container_width=True
            )
        
        # VIX Analysis
        if 'VIX' in data:
            st.markdown('<h2 class="section-header">📉 VIX Market Stress Indicator</h2>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # VIX time series
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=data['VIX'].index,
                    y=data['VIX'],
                    mode='lines',
                    name='VIX',
                    line=dict(color='#FF6B6B')
                ))
                
                # Add threshold line
                fig.add_hline(
                    y=config['vix_threshold'],
                    line_dash="dash",
                    line_color="orange",
                    annotation_text=f"Threshold: {config['vix_threshold']}",
                    annotation_position="top right"
                )
                
                fig.update_layout(
                    title='VIX Index Over Time',
                    xaxis_title='Date',
                    yaxis_title='VIX Level',
                    template='plotly_white',
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # VIX distribution
                fig = go.Figure(data=[
                    go.Histogram(
                        x=data['VIX'].dropna(),
                        nbinsx=50,
                        marker_color='#FF6B6B',
                        opacity=0.7
                    )
                ])
                
                fig.update_layout(
                    title='VIX Distribution',
                    xaxis_title='VIX Level',
                    yaxis_title='Frequency',
                    template='plotly_white',
                    height=400
                )
                
                # Add vertical line for threshold
                fig.add_vline(
                    x=config['vix_threshold'],
                    line_dash="dash",
                    line_color="orange"
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        # Correlation Matrix
        st.markdown('<h2 class="section-header">🔗 Correlation Analysis</h2>', unsafe_allow_html=True)
        
        # Prepare returns data for correlation
        returns_data = {}
        for region in config['etf_config']:
            if region in data and 'returns' in data[region]:
                returns_data[region] = data[region]['returns']
        
        if returns_data:
            returns_df = pd.DataFrame(returns_data).dropna()
            correlation_matrix = returns_df.corr()
            
            fig = px.imshow(
                correlation_matrix,
                text_auto='.2f',
                color_continuous_scale='RdBu',
                range_color=[-1, 1],
                aspect="auto"
            )
            
            fig.update_layout(
                title='Correlation Matrix Between ETFs',
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)

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
            
            # Backtest strategy
            portfolio_history, allocations_history, benchmark_history = self.backtest_strategy(
                data, 
                config['etf_config'], 
                config['initial_capital'],
                config['rebalance_threshold'],
                config['lookback_period']
            )
            
            # Store results in session state
            st.session_state.analysis_results = {
                'performance': performance_metrics,
                'portfolio_history': portfolio_history,
                'allocations_history': allocations_history,
                'benchmark_history': benchmark_history
            }
            
            # Create dashboard
            self.create_dashboard(
                config, 
                data, 
                performance_metrics, 
                portfolio_history, 
                allocations_history, 
                benchmark_history
            )
            
            # Export option
            st.markdown('<h2 class="section-header">💾 Export Results</h2>', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if portfolio_history is not None:
                    csv = portfolio_history.to_csv()
                    st.download_button(
                        label="📥 Download Portfolio History",
                        data=csv,
                        file_name="portfolio_history.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if performance_metrics:
                    metrics_df = pd.DataFrame(performance_metrics).T
                    csv = metrics_df.to_csv()
                    st.download_button(
                        label="📥 Download Performance Metrics",
                        data=csv,
                        file_name="performance_metrics.csv",
                        mime="text/csv"
                    )
            
            with col3:
                if allocations_history:
                    alloc_df = pd.DataFrame(allocations_history, index=portfolio_history.index)
                    csv = alloc_df.to_csv()
                    st.download_button(
                        label="📥 Download Allocation History",
                        data=csv,
                        file_name="allocation_history.csv",
                        mime="text/csv"
                    )
        
        elif config['run_analysis'] and not config['weights_valid']:
            st.error("⚠️ Portfolio weights must sum to 100%! Please adjust the weights in the sidebar.")
        
        else:
            # Show welcome message
            st.markdown("""
            <div style="text-align: center; padding: 5rem 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white;">
                <h1 style="font-size: 3rem; margin-bottom: 1rem;">🎯 ETF Rotation Strategy Analyzer</h1>
                <p style="font-size: 1.2rem; margin-bottom: 2rem;">
                    Configure your strategy in the sidebar and click "Run Analysis" to begin.
                </p>
                <div style="background: rgba(255,255,255,0.1); padding: 2rem; border-radius: 10px; margin-top: 2rem;">
                    <h3>🚀 Key Features:</h3>
                    <div style="display: flex; justify-content: center; gap: 2rem; margin-top: 1rem; flex-wrap: wrap;">
                        <div style="text-align: center;">
                            <div style="font-size: 2rem;">🌍</div>
                            <div>Global ETF Coverage</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 2rem;">⚖️</div>
                            <div>Dynamic Allocation</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 2rem;">📊</div>
                            <div>Interactive Charts</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 2rem;">📈</div>
                            <div>Real-time Backtesting</div>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Quick start guide
            st.markdown("""
            ## 📝 Quick Start Guide
            
            1. **Configure Portfolio** - Adjust ETF weights in the sidebar
            2. **Set Strategy Parameters** - Configure VIX threshold and rebalance rules
            3. **Choose Date Range** - Select analysis period
            4. **Click "Run Analysis"** - Generate strategy backtest
            
            ⚠️ **Note**: Portfolio weights must sum to 100% before running analysis.
            """)

# Run the dashboard
if __name__ == "__main__":
    try:
        dashboard = ETFGlobalRotationDashboard()
        dashboard.run_dashboard()
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please check your internet connection and try again.")