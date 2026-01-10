import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="ETF Rotation Strategy Analyzer",
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
    .info-box {
        background-color: #E3F2FD;
        border-left: 4px solid #1E88E5;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .strategy-box {
        background-color: #f0f7ff;
        border: 1px solid #1E88E5;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .stButton button {
        background-color: #1E88E5;
        color: white;
        font-weight: bold;
        width: 100%;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

class ETFRotationAnalyzer:
    def __init__(self):
        """Initialize the analyzer with default settings"""
        # Default ETF configuration
        self.default_etfs = {
            'US': {'ticker': 'SPY', 'weight': 40, 'color': '#2196F3'},
            'Europe': {'ticker': 'VGK', 'weight': 25, 'color': '#4CAF50'},
            'Asia': {'ticker': 'VPL', 'weight': 20, 'color': '#FF9800'},
            'Japan': {'ticker': 'EWJ', 'weight': 15, 'color': '#9C27B0'}
        }
        
        # Initialize session state
        if 'data' not in st.session_state:
            st.session_state.data = None
        if 'strategy_history' not in st.session_state:
            st.session_state.strategy_history = None

    def setup_sidebar(self):
        """Configure the sidebar with strategy inputs"""
        st.sidebar.markdown("## 📋 Portfolio Configuration")
        
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
                "End Dateeee",
                value=datetime.today(),
                min_value=datetime(2015, 1, 2),
                help="Select the end date for analysis"
            )
        
        # Portfolio allocation
        st.sidebar.markdown("### 💼 Base Portfolio Allocation")
        st.sidebar.markdown("Set base weights for each ETF (must sum to 100%):")
        
        etf_config = {}
        total_weight = 0
        
        # Create editable ETF configuration
        for region, config in self.default_etfs.items():
            col1, col2 = st.sidebar.columns([3, 1])
            
            with col1:
                # Allow custom ticker input
                ticker = st.text_input(
                    f"{region} Ticker",
                    value=config['ticker'],
                    key=f"ticker_{region}",
                    label_visibility="collapsed"
                )
            
            with col2:
                # Weight slider
                weight = st.slider(
                    f"Weight (%)",
                    min_value=0,
                    max_value=100,
                    value=config['weight'],
                    key=f"base_weight_{region}",
                    label_visibility="collapsed"
                )
            
            etf_config[region] = {
                'ticker': ticker,
                'base_weight': weight / 100,  # Convert to decimal
                'color': config['color'],
                'original_weight': weight
            }
            total_weight += weight
        
        # Show weight validation
        if total_weight != 100:
            st.sidebar.error(f"⚠️ Total weights: {total_weight}% (must be 100%)")
            st.sidebar.info("Adjust the weights until they sum to 100%")
        else:
            st.sidebar.success(f"✓ Total weights: {total_weight}%")
        
        # Strategy Selection
        st.sidebar.markdown("## 🎯 Rotation Strategies")
        
        st.sidebar.markdown("### 🔄 Momentum Strategy")
        use_momentum = st.sidebar.checkbox("Enable Momentum Rotation", value=True)
        
        if use_momentum:
            col1, col2 = st.sidebar.columns(2)
            with col1:
                momentum_lookback = st.slider(
                    "Lookback Months",
                    min_value=1,
                    max_value=6,
                    value=3,
                    help="Number of months to analyze for momentum"
                )
            with col2:
                max_single_weight = st.slider(
                    "Max Weight (%)",
                    min_value=30,
                    max_value=70,
                    value=50,
                    help="Maximum allocation to any single ETF"
                )
            
            momentum_strength = st.slider(
                "Momentum Strength",
                min_value=10,
                max_value=100,
                value=50,
                help="How strongly to overweight top performers (0-100%)"
            )
        
        st.sidebar.markdown("### 📉 VIX Strategy")
        use_vix = st.sidebar.checkbox("Enable VIX Rotation", value=True)
        
        if use_vix:
            col1, col2 = st.sidebar.columns(2)
            with col1:
                vix_threshold = st.slider(
                    "VIX Threshold",
                    min_value=15,
                    max_value=35,
                    value=20,
                    help="VIX level to trigger rotation"
                )
            with col2:
                rotation_amount = st.slider(
                    "Rotation Amount (%)",
                    min_value=10,
                    max_value=50,
                    value=25,
                    help="Percentage to rotate between US and international"
                )
            
            st.sidebar.markdown("**When VIX > Threshold:**")
            vix_action = st.sidebar.radio(
                "Action",
                ["Reduce US exposure", "Increase International exposure"],
                index=0,
                label_visibility="collapsed"
            )
        
        # Risk Management
        st.sidebar.markdown("### ⚠️ Risk Management")
        min_single_weight = st.slider(
            "Minimum Weight per ETF (%)",
            min_value=5,
            max_value=30,
            value=10,
            help="Minimum allocation to any single ETF"
        )
        
        rebalancing_cost = st.slider(
            "Rebalancing Cost (%)",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.05,
            help="Transaction cost per rebalance (as percentage)"
        )
        
        # Initial investment
        st.sidebar.markdown("### 💰 Initial Investment")
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
            "🚀 Run Strategy Analysis",
            type="primary",
            use_container_width=True
        )
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'etf_config': etf_config,
            'initial_capital': initial_capital,
            'use_momentum': use_momentum if 'use_momentum' in locals() else False,
            'momentum_lookback': momentum_lookback if 'momentum_lookback' in locals() else 3,
            'max_single_weight': (max_single_weight / 100) if 'max_single_weight' in locals() else 0.5,
            'momentum_strength': (momentum_strength / 100) if 'momentum_strength' in locals() else 0.5,
            'use_vix': use_vix if 'use_vix' in locals() else False,
            'vix_threshold': vix_threshold if 'vix_threshold' in locals() else 20,
            'rotation_amount': (rotation_amount / 100) if 'rotation_amount' in locals() else 0.25,
            'vix_action': vix_action if 'vix_action' in locals() else "Reduce US exposure",
            'min_single_weight': (min_single_weight / 100),
            'rebalancing_cost': (rebalancing_cost / 100),
            'run_analysis': run_analysis,
            'weights_valid': total_weight == 100
        }

    def fetch_data(self, etf_config, start_date, end_date, use_vix):
        """Fetch historical data for ETFs and VIX"""
        data = {}
        
        with st.spinner("📥 Fetching market data..."):
            progress_bar = st.progress(0)
            total_items = len(etf_config) + (1 if use_vix else 0)
            
            # Fetch ETF data
            for i, (region, config) in enumerate(etf_config.items()):
                ticker = config['ticker']
                
                try:
                    etf_data = yf.download(
                        ticker, 
                        start=start_date, 
                        end=end_date,
                        progress=False,
                        timeout=10
                    )
                    
                    if not etf_data.empty:
                        # Handle MultiIndex columns
                        if etf_data.columns.nlevels > 1:
                            etf_data.columns = etf_data.columns.droplevel(1)
                        
                        # Get price column
                        price_col = 'Adj Close' if 'Adj Close' in etf_data.columns else 'Close'
                        
                        # Calculate returns
                        prices = etf_data[price_col]
                        returns = prices.pct_change()
                        
                        data[region] = {
                            'ticker': ticker,
                            'prices': prices,
                            'returns': returns,
                            'color': config['color'],
                            'base_weight': config['base_weight']
                        }
                    else:
                        st.warning(f"No data found for {ticker}")
                        
                except Exception as e:
                    st.error(f"Error fetching {ticker}: {str(e)}")
                
                progress_bar.progress((i + 1) / total_items)
            
            # Fetch VIX data if needed
            if use_vix:
                try:
                    vix_data = yf.download('^VIX', start=start_date, end=end_date, progress=False)
                    if not vix_data.empty:
                        if vix_data.columns.nlevels > 1:
                            vix_data.columns = vix_data.columns.droplevel(1)
                        vix_col = 'Adj Close' if 'Adj Close' in vix_data.columns else 'Close'
                        data['VIX'] = {
                            'prices': vix_data[vix_col],
                            'returns': vix_data[vix_col].pct_change()
                        }
                except Exception as e:
                    st.error(f"Error fetching VIX data: {str(e)}")
            
            progress_bar.progress(1.0)
        
        return data

    def calculate_momentum_scores(self, data, date, lookback_months):
        """Calculate momentum scores for each ETF based on past performance"""
        momentum_scores = {}
        
        for region, region_data in data.items():
            if region == 'VIX':
                continue
            
            prices = region_data['prices']
            
            # Find start date for lookback period
            lookback_date = date - pd.DateOffset(months=lookback_months)
            
            # Get prices in lookback period
            lookback_prices = prices[prices.index <= date]
            lookback_prices = lookback_prices[lookback_prices.index >= lookback_date]
            
            if len(lookback_prices) > 1:
                # Calculate return over lookback period
                lookback_return = (lookback_prices.iloc[-1] / lookback_prices.iloc[0] - 1) * 100
                
                # Calculate risk-adjusted momentum (using simple volatility)
                returns = region_data['returns'][lookback_prices.index].dropna()
                if len(returns) > 0:
                    volatility = returns.std() * np.sqrt(252) * 100
                    risk_adjusted_score = lookback_return / max(volatility, 1)  # Avoid division by zero
                else:
                    risk_adjusted_score = lookback_return
                
                momentum_scores[region] = {
                    'return': lookback_return,
                    'risk_adjusted': risk_adjusted_score
                }
            else:
                momentum_scores[region] = {
                    'return': 0,
                    'risk_adjusted': 0
                }
        
        return momentum_scores

    def apply_momentum_strategy(self, base_weights, momentum_scores, strength, max_weight, min_weight):
        """Adjust weights based on momentum scores"""
        # Normalize momentum scores
        regions = list(momentum_scores.keys())
        scores = [momentum_scores[r]['risk_adjusted'] for r in regions]
        
        # Handle negative scores
        min_score = min(scores)
        if min_score < 0:
            scores = [s - min_score for s in scores]  # Shift to positive
        
        total_score = sum(scores)
        if total_score == 0:
            return base_weights
        
        # Calculate momentum adjustments
        momentum_weights = {}
        for i, region in enumerate(regions):
            momentum_ratio = scores[i] / total_score
            # Blend base weight with momentum weight
            momentum_weight = base_weights[region] * (1 - strength) + momentum_ratio * strength
            momentum_weights[region] = momentum_weight
        
        # Apply weight constraints
        momentum_weights = self.apply_weight_constraints(momentum_weights, max_weight, min_weight)
        
        return momentum_weights

    def apply_vix_strategy(self, current_weights, vix_value, threshold, rotation_amount, action, max_weight, min_weight):
        """Adjust weights based on VIX level"""
        adjusted_weights = current_weights.copy()
        
        if 'US' not in adjusted_weights:
            return adjusted_weights
        
        # Identify US and international ETFs
        us_etf = 'US'
        intl_etfs = [r for r in adjusted_weights.keys() if r != 'US']
        
        if vix_value > threshold:
            # High VIX - risk-off signal
            if action == "Reduce US exposure":
                # Reduce US allocation
                reduction = adjusted_weights[us_etf] * rotation_amount
                adjusted_weights[us_etf] -= reduction
                
                # Distribute to international ETFs proportionally
                total_intl = sum(adjusted_weights[r] for r in intl_etfs)
                if total_intl > 0:
                    for etf in intl_etfs:
                        adjusted_weights[etf] += reduction * (adjusted_weights[etf] / total_intl)
            else:
                # Increase international allocation
                increase = rotation_amount
                for etf in intl_etfs:
                    adjusted_weights[etf] = min(
                        adjusted_weights[etf] * (1 + increase),
                        max_weight
                    )
                # Re-normalize
                total = sum(adjusted_weights.values())
                adjusted_weights = {k: v/total for k, v in adjusted_weights.items()}
        
        else:
            # Low VIX - risk-on signal
            if action == "Reduce US exposure":
                # Increase US allocation
                increase = rotation_amount
                adjusted_weights[us_etf] = min(
                    adjusted_weights[us_etf] * (1 + increase),
                    max_weight
                )
                # Re-normalize
                total = sum(adjusted_weights.values())
                adjusted_weights = {k: v/total for k, v in adjusted_weights.items()}
        
        # Apply weight constraints
        adjusted_weights = self.apply_weight_constraints(adjusted_weights, max_weight, min_weight)
        
        return adjusted_weights

    def apply_weight_constraints(self, weights, max_weight, min_weight):
        """Apply minimum and maximum weight constraints"""
        # First pass: apply maximum weight
        for region in list(weights.keys()):
            if weights[region] > max_weight:
                excess = weights[region] - max_weight
                weights[region] = max_weight
                
                # Distribute excess to other ETFs proportionally
                other_regions = [r for r in weights.keys() if r != region]
                total_other = sum(weights[r] for r in other_regions)
                if total_other > 0:
                    for r in other_regions:
                        weights[r] += excess * (weights[r] / total_other)
        
        # Second pass: apply minimum weight
        for region in list(weights.keys()):
            if weights[region] < min_weight:
                deficit = min_weight - weights[region]
                weights[region] = min_weight
                
                # Take from other ETFs proportionally
                other_regions = [r for r in weights.keys() if r != region and weights[r] > min_weight]
                if other_regions:
                    total_other = sum(weights[r] for r in other_regions)
                    if total_other > 0:
                        for r in other_regions:
                            reduction = deficit * (weights[r] / total_other)
                            weights[r] -= reduction
        
        # Normalize to sum to 1
        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}
        
        return weights

    def get_monthly_rebalancing_dates(self, all_dates):
        """Get first trading day of each month"""
        # Convert to DataFrame to use resample
        dates_df = pd.DataFrame(index=all_dates)
        # Resample to month start and get first date of each month
        monthly_dates = dates_df.resample('MS').first().index
        return monthly_dates

    def backtest_rotation_strategy(self, data, config):
        """Backtest the combined rotation strategy"""
        # Extract ETF data
        etf_regions = [r for r in data.keys() if r != 'VIX']
        
        if not etf_regions:
            return None, None, None, None
        
        # Get all trading dates
        all_dates = data[etf_regions[0]]['prices'].index
        
        # Get monthly rebalancing dates (first trading day of each month)
        monthly_dates = self.get_monthly_rebalancing_dates(all_dates)
        
        # Initialize tracking variables
        current_weights = {region: config['etf_config'][region]['base_weight'] for region in etf_regions}
        portfolio_value = config['initial_capital']
        portfolio_history = [portfolio_value]
        weight_history = [current_weights.copy()]
        strategy_signals = []
        date_history = [all_dates[0] if len(all_dates) > 0 else monthly_dates[0]]
        
        # Track monthly performance
        monthly_returns = {}
        monthly_vix = {}
        
        # Main backtesting loop
        for month_idx in range(1, len(monthly_dates)):
            current_date = monthly_dates[month_idx]
            
            # Get returns for previous month
            prev_date = monthly_dates[month_idx-1]
            month_returns = {}
            
            for region in etf_regions:
                prices = data[region]['prices']
                month_prices = prices[(prices.index >= prev_date) & (prices.index <= current_date)]
                if len(month_prices) > 1:
                    month_returns[region] = (month_prices.iloc[-1] / month_prices.iloc[0] - 1)
                else:
                    month_returns[region] = 0
            
            # Calculate VIX value for previous month
            vix_value = None
            if 'VIX' in data and config['use_vix']:
                vix_prices = data['VIX']['prices']
                month_vix = vix_prices[(vix_prices.index >= prev_date) & (vix_prices.index <= current_date)]
                if len(month_vix) > 0:
                    vix_value = month_vix.mean()
            
            # Store monthly data
            monthly_returns[current_date] = month_returns
            if vix_value is not None:
                monthly_vix[current_date] = vix_value
            
            # Apply momentum strategy
            if config['use_momentum']:
                momentum_scores = self.calculate_momentum_scores(
                    data, current_date, config['momentum_lookback']
                )
                current_weights = self.apply_momentum_strategy(
                    current_weights, 
                    momentum_scores, 
                    config['momentum_strength'],
                    config['max_single_weight'],
                    config['min_single_weight']
                )
            
            # Apply VIX strategy
            if config['use_vix'] and vix_value is not None:
                current_weights = self.apply_vix_strategy(
                    current_weights,
                    vix_value,
                    config['vix_threshold'],
                    config['rotation_amount'],
                    config['vix_action'],
                    config['max_single_weight'],
                    config['min_single_weight']
                )
            
            # Apply rebalancing cost
            if month_idx > 1:
                # Calculate weight changes
                prev_weights = weight_history[-1]
                weight_change = sum(abs(current_weights[r] - prev_weights.get(r, 0)) for r in etf_regions)
                if weight_change > 0:
                    cost = portfolio_value * weight_change * config['rebalancing_cost']
                    portfolio_value -= cost
            
            # Calculate portfolio performance from current_date to next rebalance date
            next_rebalance_date = monthly_dates[month_idx+1] if month_idx+1 < len(monthly_dates) else all_dates[-1]
            
            # Get trading days between current rebalance date and next
            trading_days = all_dates[(all_dates >= current_date) & (all_dates <= next_rebalance_date)]
            
            # Calculate daily portfolio value
            for i, date in enumerate(trading_days):
                daily_return = 0
                for region in etf_regions:
                    if region in data and date in data[region]['returns'].index:
                        daily_return += current_weights[region] * data[region]['returns'].loc[date]
                
                portfolio_value *= (1 + daily_return)
                portfolio_history.append(portfolio_value)
                weight_history.append(current_weights.copy())
                date_history.append(date)
            
            # Record strategy signal
            signal = {
                'date': current_date,
                'weights': current_weights.copy(),
                'vix': vix_value,
                'momentum_rank': None
            }
            
            if config['use_momentum'] and config['use_momentum']:
                momentum_rank = sorted(momentum_scores.items(), 
                                     key=lambda x: x[1]['risk_adjusted'], 
                                     reverse=True)
                if momentum_rank:
                    signal['momentum_rank'] = momentum_rank[0][0]
            
            strategy_signals.append(signal)
        
        # Calculate benchmark (static portfolio)
        static_weights = {region: config['etf_config'][region]['base_weight'] for region in etf_regions}
        benchmark_value = config['initial_capital']
        benchmark_history = [benchmark_value]
        benchmark_dates = []
        
        for i, date in enumerate(all_dates):
            if i == 0:
                benchmark_dates.append(date)
                continue
                
            daily_return = 0
            for region in etf_regions:
                if date in data[region]['returns'].index:
                    daily_return += static_weights[region] * data[region]['returns'].loc[date]
            
            benchmark_value *= (1 + daily_return)
            benchmark_history.append(benchmark_value)
            benchmark_dates.append(date)
        
        # Convert to Series
        portfolio_series = pd.Series(portfolio_history, index=date_history)
        benchmark_series = pd.Series(benchmark_history, index=benchmark_dates[:len(benchmark_history)])
        
        return portfolio_series, benchmark_series, weight_history, strategy_signals

    def create_strategy_performance_chart(self, portfolio_value, benchmark_value, initial_capital):
        """Create performance comparison chart"""
        fig = go.Figure()
        
        # Add strategy line
        fig.add_trace(go.Scatter(
            x=portfolio_value.index,
            y=portfolio_value,
            mode='lines',
            name='Rotation Strategy',
            line=dict(color='#1E88E5', width=3),
            hovertemplate='Date: %{x|%Y-%m-%d}<br>Value: $%{y:,.0f}<extra></extra>'
        ))
        
        # Add benchmark line
        fig.add_trace(go.Scatter(
            x=benchmark_value.index,
            y=benchmark_value,
            mode='lines',
            name='Static Portfolio',
            line=dict(color='#FF5722', width=2, dash='dash'),
            hovertemplate='Date: %{x|%Y-%m-%d}<br>Value: $%{y:,.0f}<extra></extra>'
        ))
        
        fig.update_layout(
            title='Strategy Performance vs Static Portfolio',
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
        
        return fig

    def create_weight_evolution_chart(self, strategy_signals, etf_colors):
        """Create chart showing weight evolution with strategy signals"""
        if not strategy_signals:
            return None
        
        # Extract data
        dates = [s['date'] for s in strategy_signals]
        if not dates:
            return None
            
        # Get regions from first signal
        first_signal = strategy_signals[0]
        regions = list(first_signal['weights'].keys())
        
        # Create DataFrame for weights
        weight_data = pd.DataFrame(index=dates, columns=regions)
        for signal in strategy_signals:
            for region in regions:
                weight_data.loc[signal['date'], region] = signal['weights'][region] * 100
        
        # Create figure
        fig = go.Figure()
        
        # Add stacked area for weights
        for region in regions:
            color = etf_colors.get(region, '#CCCCCC')
            fig.add_trace(go.Scatter(
                x=weight_data.index,
                y=weight_data[region],
                mode='lines',
                name=region,
                stackgroup='one',
                line=dict(width=0.5),
                fillcolor=color,
                hovertemplate=f"{region}: %{{y:.1f}}%<extra></extra>"
            ))
        
        # Add momentum signals
        momentum_dates = [s['date'] for s in strategy_signals if s.get('momentum_rank')]
        momentum_ranks = [s.get('momentum_rank') for s in strategy_signals if s.get('momentum_rank')]
        
        if momentum_dates:
            fig.add_trace(go.Scatter(
                x=momentum_dates,
                y=[95] * len(momentum_dates),  # Near top of chart
                mode='markers',
                name='Momentum Top Performer',
                marker=dict(
                    symbol='triangle-up',
                    size=10,
                    color='green'
                ),
                hovertemplate='Date: %{x|%Y-%m-%d}<br>Top Performer: %{text}<extra></extra>',
                text=momentum_ranks
            ))
        
        fig.update_layout(
            title='Portfolio Weight Evolution with Strategy Signals',
            xaxis_title='Date',
            yaxis_title='Portfolio Weight (%)',
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
        
        return fig

    def create_momentum_analysis_chart(self, strategy_signals, data):
        """Create momentum analysis visualization"""
        if not strategy_signals or not data:
            return None
        
        # Extract momentum information
        momentum_info = []
        for signal in strategy_signals:
            if signal.get('momentum_rank'):
                momentum_info.append({
                    'date': signal['date'],
                    'top_performer': signal['momentum_rank']
                })
        
        if not momentum_info:
            return None
        
        # Calculate performance of momentum strategy vs others
        top_performers = [m['top_performer'] for m in momentum_info]
        
        # Get unique ETFs
        etf_regions = list(data.keys())
        if 'VIX' in etf_regions:
            etf_regions.remove('VIX')
        
        # Calculate how often each ETF was top performer
        top_counts = {region: top_performers.count(region) for region in etf_regions}
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=list(top_counts.keys()),
                y=list(top_counts.values()),
                marker_color=['green' if count > 0 else 'gray' for count in top_counts.values()],
                text=[f"{count} times" for count in top_counts.values()],
                textposition='auto'
            )
        ])
        
        fig.update_layout(
            title='Momentum Strategy - Top Performer Frequency',
            xaxis_title='ETF',
            yaxis_title='Times as Top Performer',
            template='plotly_white',
            height=400
        )
        
        return fig

    def create_vix_analysis_chart(self, strategy_signals):
        """Create VIX strategy analysis visualization"""
        if not strategy_signals:
            return None
        
        # Extract VIX information
        vix_info = []
        for signal in strategy_signals:
            if signal.get('vix') is not None:
                us_weight = signal['weights'].get('US', 0)
                vix_info.append({
                    'date': signal['date'],
                    'vix': signal['vix'],
                    'us_weight': us_weight
                })
        
        if not vix_info:
            return None
        
        # Create DataFrame
        vix_df = pd.DataFrame(vix_info)
        
        # Create scatter plot
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=vix_df['vix'],
            y=vix_df['us_weight'] * 100,
            mode='markers',
            marker=dict(
                size=8,
                color=vix_df['vix'],
                colorscale='RdYlGn_r',  # Red for high VIX, green for low
                showscale=True,
                colorbar=dict(title="VIX Level")
            ),
            text=vix_df['date'].dt.strftime('%Y-%m-%d'),
            hovertemplate='Date: %{text}<br>VIX: %{x:.1f}<br>US Weight: %{y:.1f}%<extra></extra>'
        ))
        
        fig.update_layout(
            title='VIX Strategy Analysis',
            xaxis_title='VIX Level',
            yaxis_title='US Allocation (%)',
            template='plotly_white',
            height=400
        )
        
        return fig

    def display_strategy_summary(self, config, portfolio_value, benchmark_value, strategy_signals):
        """Display strategy performance summary"""
        st.markdown('<h2 class="section-header">📊 Strategy Performance Summary</h2>', unsafe_allow_html=True)
        
        if portfolio_value is None or len(portfolio_value) == 0:
            st.warning("Unable to calculate strategy metrics.")
            return
        
        # Calculate performance metrics
        strategy_return = (portfolio_value.iloc[-1] / config['initial_capital'] - 1) * 100
        strategy_returns = portfolio_value.pct_change().dropna()
        strategy_annual = ((1 + strategy_return/100) ** (252/len(strategy_returns)) - 1) * 100
        
        benchmark_return = (benchmark_value.iloc[-1] / config['initial_capital'] - 1) * 100
        benchmark_returns = benchmark_value.pct_change().dropna()
        benchmark_annual = ((1 + benchmark_return/100) ** (252/len(benchmark_returns)) - 1) * 100
        
        alpha = strategy_return - benchmark_return
        
        # Strategy statistics
        momentum_count = sum(1 for s in strategy_signals if s.get('momentum_rank'))
        vix_count = sum(1 for s in strategy_signals if s.get('vix') is not None)
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Strategy Return",
                f"{strategy_return:.1f}%",
                f"{strategy_annual:.1f}% annual"
            )
        
        with col2:
            delta_color = "normal" if alpha >= 0 else "inverse"
            st.metric(
                "vs. Static Portfolio",
                f"{strategy_return:.1f}%",
                f"Alpha: {alpha:+.1f}%",
                delta_color=delta_color
            )
        
        with col3:
            st.metric(
                "Momentum Signals",
                f"{momentum_count}",
                "Monthly rebalances"
            )
        
        with col4:
            st.metric(
                "VIX Signals",
                f"{vix_count}",
                "Monthly checks"
            )
        
        # Strategy configuration display
        st.markdown("### 🎯 Active Strategy Configuration")
        
        strategy_desc = f"""
        <div class="strategy-box">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <div><strong>Momentum Strategy:</strong> {config['use_momentum'] and '✅ Active' or '❌ Inactive'}</div>
                <div><strong>VIX Strategy:</strong> {config['use_vix'] and '✅ Active' or '❌ Inactive'}</div>
            </div>
        """
        
        if config['use_momentum']:
            strategy_desc += f"""
            <div style="margin-top: 0.5rem;">
                <strong>Momentum Settings:</strong><br>
                • Lookback: {config['momentum_lookback']} months<br>
                • Max single ETF: {config['max_single_weight']*100:.0f}%<br>
                • Strength: {config['momentum_strength']*100:.0f}%
            </div>
            """
        
        if config['use_vix']:
            strategy_desc += f"""
            <div style="margin-top: 0.5rem;">
                <strong>VIX Settings:</strong><br>
                • Threshold: {config['vix_threshold']}<br>
                • Rotation: {config['rotation_amount']*100:.0f}%<br>
                • Action: {config['vix_action']}
            </div>
            """
        
        strategy_desc += f"""
            <div style="margin-top: 0.5rem;">
                <strong>Risk Management:</strong><br>
                • Min single ETF: {config['min_single_weight']*100:.0f}%<br>
                • Rebalancing cost: {config['rebalancing_cost']*100:.1f}%
            </div>
        </div>
        """
        
        st.markdown(strategy_desc, unsafe_allow_html=True)

    def run_analysis(self, config):
        """Run the complete analysis"""
        # Fetch data
        data = self.fetch_data(
            config['etf_config'], 
            config['start_date'], 
            config['end_date'],
            config['use_vix']
        )
        
        if not data:
            st.error("❌ No data could be fetched. Please check your ticker symbols and internet connection.")
            return
        
        # Run backtest
        portfolio_value, benchmark_value, weight_history, strategy_signals = self.backtest_rotation_strategy(
            data, config
        )
        
        if portfolio_value is None:
            st.error("❌ Unable to run backtest. Please check your configuration.")
            return
        
        # Display results
        self.display_strategy_summary(config, portfolio_value, benchmark_value, strategy_signals)
        
        # Performance Chart
        st.markdown('<h2 class="section-header">📈 Performance Comparison</h2>', unsafe_allow_html=True)
        fig1 = self.create_strategy_performance_chart(portfolio_value, benchmark_value, config['initial_capital'])
        st.plotly_chart(fig1, use_container_width=True)
        
        # Weight Evolution with Signals
        st.markdown('<h2 class="section-header">⚖️ Weight Evolution & Strategy Signals</h2>', unsafe_allow_html=True)
        
        # Get ETF colors
        etf_colors = {}
        for region, config_data in config['etf_config'].items():
            etf_colors[region] = config_data['color']
        
        fig2 = self.create_weight_evolution_chart(strategy_signals, etf_colors)
        if fig2:
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("Unable to create weight evolution chart.")
        
        # Strategy Analysis Charts
        if config['use_momentum'] or config['use_vix']:
            col1, col2 = st.columns(2)
            
            with col1:
                if config['use_momentum']:
                    st.markdown('<h3 style="font-size: 1.2rem; margin-bottom: 1rem;">📊 Momentum Analysis</h3>', unsafe_allow_html=True)
                    fig3 = self.create_momentum_analysis_chart(strategy_signals, data)
                    if fig3:
                        st.plotly_chart(fig3, use_container_width=True)
                    else:
                        st.info("No momentum data available.")
            
            with col2:
                if config['use_vix']:
                    st.markdown('<h3 style="font-size: 1.2rem; margin-bottom: 1rem;">📉 VIX Strategy Analysis</h3>', unsafe_allow_html=True)
                    fig4 = self.create_vix_analysis_chart(strategy_signals)
                    if fig4:
                        st.plotly_chart(fig4, use_container_width=True)
                    else:
                        st.info("No VIX data available.")
        
        # Detailed Strategy Log
        st.markdown('<h2 class="section-header">📋 Strategy Decision Log (Last 12 Months)</h2>', unsafe_allow_html=True)
        
        if strategy_signals:
            # Create DataFrame for display
            log_data = []
            for signal in strategy_signals[-12:]:  # Show last 12 months
                log_entry = {
                    'Date': signal['date'].strftime('%Y-%m'),
                    'VIX': f"{signal.get('vix', 'N/A'):.1f}" if signal.get('vix') is not None else 'N/A'
                }
                
                # Add weights
                for region, weight in signal['weights'].items():
                    log_entry[f'{region} (%)'] = f"{weight*100:.1f}"
                
                # Add momentum signal
                if signal.get('momentum_rank'):
                    log_entry['Momentum Top'] = signal['momentum_rank']
                
                log_data.append(log_entry)
            
            if log_data:
                log_df = pd.DataFrame(log_data)
                st.dataframe(log_df, use_container_width=True, height=300)
            else:
                st.info("No strategy signals available.")
        
        # Export Data
        st.markdown('<h2 class="section-header">💾 Export Strategy Data</h2>', unsafe_allow_html=True)
        
        col3, col4, col5 = st.columns(3)
        
        with col3:
            # Export portfolio values
            portfolio_df = pd.DataFrame({
                'Date': portfolio_value.index,
                'Strategy_Value': portfolio_value.values,
                'Benchmark_Value': benchmark_value.reindex(portfolio_value.index, method='ffill').values
            })
            csv = portfolio_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Performance Data",
                data=csv,
                file_name="strategy_performance.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col4:
            # Export strategy signals
            if strategy_signals:
                signals_df = pd.DataFrame([
                    {
                        'Date': s['date'],
                        'VIX': s.get('vix'),
                        'Momentum_Top': s.get('momentum_rank'),
                        **{f'{r}_Weight': w*100 for r, w in s['weights'].items()}
                    }
                    for s in strategy_signals
                ])
                csv = signals_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Strategy Signals",
                    data=csv,
                    file_name="strategy_signals.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        with col5:
            # Export ETF data
            prices_df = pd.DataFrame()
            for region, region_data in data.items():
                if region != 'VIX':
                    prices_df[region] = region_data['prices']
            
            if not prices_df.empty:
                csv = prices_df.to_csv()
                st.download_button(
                    label="📥 Download ETF Prices",
                    data=csv,
                    file_name="etf_prices.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    def show_welcome_screen(self):
        """Display welcome screen with instructions"""
        st.markdown("""
        <div style="text-align: center; padding: 3rem 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin-bottom: 2rem;">
            <h1 style="font-size: 3rem; margin-bottom: 1rem;">🎯 ETF Rotation Strategy Analyzer</h1>
            <p style="font-size: 1.2rem; margin-bottom: 2rem;">
                Combine Momentum & VIX strategies for intelligent monthly rebalancing
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick features overview
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="metric-card">
                <div style="font-size: 2rem;">📈</div>
                <div style="font-weight: bold;">Momentum Strategy</div>
                <div style="font-size: 0.9rem;">Overweight best-performing ETFs (3-month lookback)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="metric-card">
                <div style="font-size: 2rem;">📊</div>
                <div style="font-weight: bold;">VIX Rotation</div>
                <div style="font-size: 0.9rem;">Adjust US/international based on market volatility</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card">
                <div style="font-size: 2rem;">⚖️</div>
                <div style="font-weight: bold;">Risk Management</div>
                <div style="font-size: 0.9rem;">No single ETF > 50%, minimum diversification</div>
            </div>
            """, unsafe_allow_html=True)

    def run_dashboard(self):
        """Main function to run the dashboard"""
        # Display header
        st.markdown('<h1 class="main-header">ETF Rotation Strategy Analyzer</h1>', unsafe_allow_html=True)
        
        # Get configuration from sidebar
        config = self.setup_sidebar()
        
        # Check if we should run analysis
        if config['run_analysis']:
            if config['weights_valid']:
                self.run_analysis(config)
            else:
                st.error("❌ Portfolio weights must sum to 100%. Please adjust the weights in the sidebar.")
        else:
            self.show_welcome_screen()

# Run the dashboard
if __name__ == "__main__":
    try:
        analyzer = ETFRotationAnalyzer()
        analyzer.run_dashboard()
    except Exception as e:
        st.error(f"❌ An error occurred: {str(e)}")
        st.info("💡 Tips for troubleshooting:")
        st.info("1. Check your internet connection")
        st.info("2. Verify ETF ticker symbols are correct")
        st.info("3. Try a shorter date range if data is unavailable")
        st.info("4. Make sure portfolio weights sum to 100%")
        
# To run: 
# streamlit run Investment_strategies/app_stage2.py