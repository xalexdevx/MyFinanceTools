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
    page_title="ETF Portfolio Analyzer",
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
    .stButton button {
        background-color: #1E88E5;
        color: white;
        font-weight: bold;
        width: 100%;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        padding: 1.5rem;
        color: white;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

class ETFAnalyzer:
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
        if 'performance' not in st.session_state:
            st.session_state.performance = None
        if 'returns_data' not in st.session_state:
            st.session_state.returns_data = None
        if 'sp500_data' not in st.session_state:
            st.session_state.sp500_data = None

    def setup_sidebar(self):
        """Configure the sidebar with basic inputs"""
        st.sidebar.markdown("## 📋 Portfolio Configuration")
        
        # Date range selection
        st.sidebar.markdown("### 📅 Date Range")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime(2020, 1, 1),
                max_value=datetime.today() - timedelta(days=365),
                help="Select the start date for analysis"
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.today(),
                min_value=datetime(2020, 1, 2),
                help="Select the end date for analysis"
            )
        
        # S&P500 comparison option
        st.sidebar.markdown("### 📊 Benchmark Comparison")
        include_sp500 = st.sidebar.checkbox(
            "Compare to S&P 500 (^GSPC)",
            value=True,
            help="Include S&P 500 as a benchmark for comparison"
        )
        
        # Portfolio allocation
        st.sidebar.markdown("### 💼 Portfolio Allocation")
        st.sidebar.markdown("Adjust weights for each ETF (must sum to 100%):")
        
        etf_config = {}
        total_weight = 0
        
        # Create editable ETF configuration
        for region, config in self.default_etfs.items():
            col1, col2 = st.sidebar.columns([2, 1])
            
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
                    key=f"weight_{region}",
                    label_visibility="collapsed"
                )
            
            etf_config[region] = {
                'ticker': ticker,
                'weight': weight / 100,  # Convert to decimal
                'color': config['color']
            }
            total_weight += weight
        
        # Show weight validation
        if total_weight != 100:
            st.sidebar.error(f"⚠️ Total weights: {total_weight}% (must be 100%)")
            st.sidebar.info("Adjust the weights until they sum to 100%")
        else:
            st.sidebar.success(f"✓ Total weights: {total_weight}%")
        
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
            "🚀 Run Portfolio Analysis",
            type="primary",
            use_container_width=True
        )
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'etf_config': etf_config,
            'initial_capital': initial_capital,
            'run_analysis': run_analysis,
            'weights_valid': total_weight == 100,
            'include_sp500': include_sp500
        }

    def fetch_sp500_data(self, start_date, end_date):
        """Fetch S&P 500 data for comparison"""
        try:
            sp500 = yf.download('^GSPC', start=start_date, end=end_date, progress=False, timeout=10)
            if not sp500.empty:
                # Handle MultiIndex columns
                if sp500.columns.nlevels > 1:
                    sp500.columns = sp500.columns.droplevel(1)
                
                # Get price column
                price_col = 'Adj Close' if 'Adj Close' in sp500.columns else 'Close'
                
                prices = sp500[price_col]
                returns = prices.pct_change().dropna()
                
                return {
                    'ticker': '^GSPC',
                    'prices': prices,
                    'returns': returns,
                    'color': '#FF5722',
                    'weight': 0  # Not part of portfolio
                }
        except Exception as e:
            st.warning(f"Could not fetch S&P 500 data: {str(e)}")
        return None

    def fetch_etf_data(self, etf_config, start_date, end_date):
        """Fetch historical data for all ETFs"""
        data = {}
        progress_text = st.empty()
        
        with st.spinner("📥 Fetching ETF data..."):
            for region, config in etf_config.items():
                ticker = config['ticker']
                
                try:
                    # Download data
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
                            'weight': config['weight']
                        }
                        
                        progress_text.text(f"✓ {region}: {ticker} ({len(prices)} days)")
                    else:
                        st.warning(f"No data found for {ticker}")
                        
                except Exception as e:
                    st.error(f"Error fetching {ticker}: {str(e)}")
        
        return data

    def calculate_performance_metrics(self, data, sp500_data=None):
        """Calculate performance metrics for each ETF and S&P 500"""
        performance_data = {}
        
        # Calculate for ETFs
        for region, region_data in data.items():
            prices = region_data['prices']
            returns = region_data['returns'].dropna()
            
            if len(prices) == 0 or len(returns) == 0:
                continue
            
            performance_data[region] = self._calculate_single_asset_metrics(
                prices, returns, region_data
            )
        
        # Calculate for S&P 500 if available
        if sp500_data:
            prices = sp500_data['prices']
            returns = sp500_data['returns'].dropna()
            
            if len(prices) > 0 and len(returns) > 0:
                performance_data['S&P 500'] = self._calculate_single_asset_metrics(
                    prices, returns, sp500_data
                )
                performance_data['S&P 500']['Weight'] = 'N/A'
        
        return performance_data
    
    def _calculate_single_asset_metrics(self, prices, returns, asset_data):
        """Calculate metrics for a single asset"""
        # Basic metrics
        total_return = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
        days = len(prices)
        
        # Annualized metrics
        annual_return = ((1 + total_return/100) ** (252/days) - 1) * 100
        volatility = returns.std() * np.sqrt(252) * 100
        
        # Calculate maximum drawdown
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        # Sharpe ratio (assuming 0% risk-free rate)
        sharpe_ratio = (annual_return / volatility) if volatility != 0 else 0
        
        # Additional metrics
        positive_months = len(returns[returns > 0])
        total_months = len(returns)
        win_rate = (positive_months / total_months * 100) if total_months > 0 else 0
        
        return {
            'Ticker': asset_data['ticker'],
            'Weight': f"{asset_data['weight']*100:.1f}%" if asset_data['weight'] > 0 else 'N/A',
            'Total Return (%)': round(total_return, 2),
            'Annual Return (%)': round(annual_return, 2),
            'Volatility (%)': round(volatility, 2),
            'Max Drawdown (%)': round(max_drawdown, 2),
            'Sharpe Ratio': round(sharpe_ratio, 2),
            'Win Rate (%)': round(win_rate, 1),
            'Color': asset_data['color']
        }

    def calculate_portfolio_returns(self, data, initial_capital, sp500_data=None):
        """Calculate portfolio returns based on weights - FIXED VERSION"""
        # Combine all returns into a single DataFrame with proper alignment
        returns_list = []
        for region, region_data in data.items():
            returns_list.append(region_data['returns'])
        
        if not returns_list:
            return None, None, None, None
        
        # Align all return series by index
        returns_df = pd.concat(returns_list, axis=1)
        returns_df.columns = list(data.keys())
        
        # Drop rows with any NaN (start from first complete data point)
        returns_df = returns_df.dropna()
        
        if returns_df.empty:
            return None, None, None, None
        
        # Get weights
        weights = np.array([data[region]['weight'] for region in returns_df.columns])
        
        # Calculate weighted portfolio returns
        portfolio_returns = returns_df.dot(weights)
        
        # Calculate portfolio value over time starting from initial_capital
        portfolio_value = initial_capital * (1 + portfolio_returns).cumprod()
        
        # Calculate S&P 500 as benchmark if available
        benchmark_label = "S&P 500"
        if sp500_data is not None:
            # Align S&P 500 returns with portfolio returns index
            sp500_returns = sp500_data['returns'].reindex(portfolio_returns.index, method='ffill').fillna(0)
            benchmark_value = initial_capital * (1 + sp500_returns).cumprod()
        else:
            # Calculate equal weight benchmark as fallback
            equal_weight_returns = returns_df.mean(axis=1)
            benchmark_value = initial_capital * (1 + equal_weight_returns).cumprod()
            benchmark_label = 'Equal Weight Benchmark'
        
        return portfolio_returns, portfolio_value, benchmark_value, benchmark_label

    def create_portfolio_performance_chart(self, portfolio_value, benchmark_value, initial_capital, benchmark_label):
        """Create portfolio performance chart"""
        fig = go.Figure()
        
        # Add portfolio line
        fig.add_trace(go.Scatter(
            x=portfolio_value.index,
            y=portfolio_value,
            mode='lines',
            name='Your Portfolio',
            line=dict(color='#1E88E5', width=3),
            hovertemplate='Portfolio: $%{y:,.0f}<extra></extra>'
        ))
        
        # Add benchmark line
        fig.add_trace(go.Scatter(
            x=benchmark_value.index,
            y=benchmark_value,
            mode='lines',
            name=benchmark_label,
            line=dict(color='#FF5722', width=2, dash='dash'),
            hovertemplate=f'{benchmark_label}: $%{{y:,.0f}}<extra></extra>'
        ))
        
        # Add initial investment line
        fig.add_hline(
            y=initial_capital,
            line_dash="dot",
            line_color="gray",
            annotation_text=f"Initial: ${initial_capital:,.0f}",
            annotation_position="bottom right"
        )
        
        # Add final values annotation
        if not portfolio_value.empty:
            fig.add_annotation(
                x=portfolio_value.index[-1],
                y=portfolio_value.iloc[-1],
                text=f"${portfolio_value.iloc[-1]:,.0f}",
                showarrow=True,
                arrowhead=1,
                ax=40,
                ay=-40
            )
        
        if not benchmark_value.empty:
            fig.add_annotation(
                x=benchmark_value.index[-1],
                y=benchmark_value.iloc[-1],
                text=f"${benchmark_value.iloc[-1]:,.0f}",
                showarrow=True,
                arrowhead=1,
                ax=40,
                ay=40
            )
        
        fig.update_layout(
            title=f'Portfolio Performance vs {benchmark_label}',
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

    def create_normalized_price_chart(self, data, portfolio_value, sp500_data=None, initial_capital=10000):
        """Create normalized price performance chart for all assets"""
        fig = go.Figure()
        
        # Normalize all prices to starting value of 100
        for region, region_data in data.items():
            prices = region_data['prices']
            if len(prices) > 0:
                normalized = (prices / prices.iloc[0]) * 100
                fig.add_trace(go.Scatter(
                    x=normalized.index,
                    y=normalized,
                    mode='lines',
                    name=f"{region} ({region_data['ticker']})",
                    line=dict(color=region_data['color'], width=2),
                    hovertemplate=f"{region}: %{{y:.1f}}%<extra></extra>"
                ))
        
        # Add portfolio normalized to 100
        if portfolio_value is not None and len(portfolio_value) > 0:
            portfolio_normalized = (portfolio_value / portfolio_value.iloc[0]) * 100
            fig.add_trace(go.Scatter(
                x=portfolio_normalized.index,
                y=portfolio_normalized,
                mode='lines',
                name='Your Portfolio',
                line=dict(color='#1E88E5', width=3),
                hovertemplate='Portfolio: %{y:.1f}%<extra></extra>'
            ))
        
        # Add S&P 500 normalized to 100
        if sp500_data is not None:
            sp500_prices = sp500_data['prices']
            if len(sp500_prices) > 0:
                sp500_normalized = (sp500_prices / sp500_prices.iloc[0]) * 100
                fig.add_trace(go.Scatter(
                    x=sp500_normalized.index,
                    y=sp500_normalized,
                    mode='lines',
                    name='S&P 500',
                    line=dict(color='#FF5722', width=3, dash='dash'),
                    hovertemplate='S&P 500: %{y:.1f}%<extra></extra>'
                ))
        
        fig.update_layout(
            title='Normalized Price Performance (Base = 100)',
            xaxis_title='Date',
            yaxis_title='Normalized Price (%)',
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
        
        # Add a horizontal line at 100 for reference
        fig.add_hline(
            y=100,
            line_dash="dot",
            line_color="gray",
            annotation_text="Base = 100",
            annotation_position="bottom right"
        )
        
        return fig

    def create_returns_distribution_chart(self, data, sp500_data=None):
        """Create distribution of returns chart - FIXED VERSION"""
        fig = go.Figure()
        
        # Collect all returns data
        all_returns = []
        colors = []
        names = []
        
        for region, region_data in data.items():
            returns = region_data['returns'].dropna() * 100  # Convert to percentage
            if len(returns) > 0:
                all_returns.append(returns)
                colors.append(region_data['color'])
                names.append(region)
        
        # Add S&P 500 if available
        if sp500_data is not None:
            sp500_returns = sp500_data['returns'].dropna() * 100
            if len(sp500_returns) > 0:
                all_returns.append(sp500_returns)
                colors.append(sp500_data['color'])
                names.append('S&P 500')
        
        if not all_returns:
            return fig
        
        # Create histogram for each series
        for i, (returns, color, name) in enumerate(zip(all_returns, colors, names)):
            fig.add_trace(go.Histogram(
                x=returns,
                name=name,
                opacity=0.6,
                nbinsx=50,
                marker_color=color,
                histnorm='probability density'
            ))
        
        fig.update_layout(
            title='Distribution of Daily Returns',
            xaxis_title='Daily Return (%)',
            yaxis_title='Density',
            barmode='overlay',
            template='plotly_white',
            height=400,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )
        
        # Update bin size for better visualization
        fig.update_traces(xbins=dict(size=0.1))  # 0.1% bins
        
        return fig

    def create_risk_return_scatter(self, performance_data):
        """Create risk-return scatter plot"""
        fig = go.Figure()
        
        regions = list(performance_data.keys())
        returns = [performance_data[r]['Annual Return (%)'] for r in regions]
        volatilities = [performance_data[r]['Volatility (%)'] for r in regions]
        colors = [performance_data[r]['Color'] for r in regions]
        tickers = [performance_data[r]['Ticker'] for r in regions]
        
        # Separate portfolio ETFs from benchmark
        etf_indices = [i for i, r in enumerate(regions) if r != 'S&P 500']
        benchmark_indices = [i for i, r in enumerate(regions) if r == 'S&P 500']
        
        # Add ETF points
        if etf_indices:
            fig.add_trace(go.Scatter(
                x=[volatilities[i] for i in etf_indices],
                y=[returns[i] for i in etf_indices],
                mode='markers+text',
                marker=dict(
                    size=15,
                    color=[colors[i] for i in etf_indices],
                    line=dict(width=2, color='DarkSlateGrey')
                ),
                text=[regions[i] for i in etf_indices],
                textposition="top center",
                name='Portfolio ETFs',
                hovertemplate="<b>%{text}</b><br>" +
                            "Ticker: %{customdata}<br>" +
                            "Return: %{y:.2f}%<br>" +
                            "Volatility: %{x:.2f}%<extra></extra>",
                customdata=[tickers[i] for i in etf_indices]
            ))
        
        # Add S&P 500 point if present
        if benchmark_indices:
            fig.add_trace(go.Scatter(
                x=[volatilities[i] for i in benchmark_indices],
                y=[returns[i] for i in benchmark_indices],
                mode='markers',
                marker=dict(
                    size=20,
                    symbol='star',
                    color=[colors[i] for i in benchmark_indices],
                    line=dict(width=2, color='black')
                ),
                name='S&P 500',
                hovertemplate="<b>S&P 500</b><br>" +
                            "Return: %{y:.2f}%<br>" +
                            "Volatility: %{x:.2f}%<extra></extra>"
            ))
        
        # Add quadrant lines (average return and volatility)
        if returns:
            avg_return = np.mean(returns)
            avg_volatility = np.mean(volatilities)
            
            fig.add_hline(y=avg_return, line_dash="dot", line_color="gray", opacity=0.5)
            fig.add_vline(x=avg_volatility, line_dash="dot", line_color="gray", opacity=0.5)
        
        fig.update_layout(
            title='Risk-Return Profile',
            xaxis_title='Annual Volatility (%)',
            yaxis_title='Annual Return (%)',
            template='plotly_white',
            height=500,
            showlegend=True
        )
        
        return fig

    def create_correlation_matrix(self, data, sp500_data=None):
        """Create correlation matrix heatmap between ETFs (and S&P 500 if available)"""
        # Prepare returns data
        returns_df = pd.DataFrame()
        
        # Add all ETF returns
        for region, region_data in data.items():
            returns_df[region] = region_data['returns']
        
        # Add S&P 500 if available
        if sp500_data is not None:
            returns_df['S&P 500'] = sp500_data['returns']
        
        if returns_df.empty:
            return None
        
        # Drop NaN values and align dates
        returns_df = returns_df.dropna()
        
        if returns_df.empty:
            return None
        
        # Calculate correlation matrix
        correlation_matrix = returns_df.corr()
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=correlation_matrix.values,
            x=correlation_matrix.columns,
            y=correlation_matrix.index,
            colorscale='RdBu',
            zmin=-1,
            zmax=1,
            text=np.round(correlation_matrix.values, 2),
            texttemplate='%{text}',
            textfont={"size": 10},
            hoverongaps=False,
            hoverinfo='z+text'
        ))
        
        # Add title based on what's included
        title = 'Correlation Matrix'
        if sp500_data is not None:
            title += ' (with S&P 500)'
        
        fig.update_layout(
            title=title,
            xaxis_title='Asset',
            yaxis_title='Asset',
            template='plotly_white',
            height=500,
            width=600
        )
        
        # Add annotations for high/low correlations
        fig.update_traces(
            text=correlation_matrix.round(2).values,
            texttemplate='%{text}',
            textfont={"size": 10}
        )
        
        return fig

    def display_portfolio_summary(self, portfolio_value, benchmark_value, initial_capital, benchmark_label, portfolio_returns):
        """Display portfolio summary metrics - FIXED VERSION"""
        st.markdown('<h2 class="section-header">📊 Portfolio Summary</h2>', unsafe_allow_html=True)
        
        if portfolio_value is None or len(portfolio_value) == 0:
            st.warning("Unable to calculate portfolio metrics. Please check your data.")
            return
        
        # Calculate portfolio metrics
        final_value = portfolio_value.iloc[-1]
        total_return = (final_value / initial_capital - 1) * 100
        
        # Calculate annualized return properly
        if portfolio_returns is not None and len(portfolio_returns) > 0:
            annualized_return = ((1 + portfolio_returns).prod() ** (252/len(portfolio_returns)) - 1) * 100
            volatility = portfolio_returns.std() * np.sqrt(252) * 100
            sharpe_ratio = (annualized_return / volatility) if volatility != 0 else 0
            
            # Calculate maximum drawdown
            cumulative = (1 + portfolio_returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_dd = drawdown.min() * 100
        else:
            annualized_return = 0
            volatility = 0
            sharpe_ratio = 0
            max_dd = 0
        
        # Calculate benchmark metrics
        if benchmark_value is not None and len(benchmark_value) > 0:
            benchmark_final = benchmark_value.iloc[-1]
            benchmark_return = (benchmark_final / initial_capital - 1) * 100
            alpha = total_return - benchmark_return
            
            # Calculate benchmark volatility for comparison
            benchmark_returns = benchmark_value.pct_change().dropna()
            if len(benchmark_returns) > 0:
                benchmark_volatility = benchmark_returns.std() * np.sqrt(252) * 100
                excess_volatility = volatility - benchmark_volatility
            else:
                excess_volatility = 0
        else:
            benchmark_return = None
            alpha = None
            excess_volatility = None
        
        # Display metrics in columns with cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                "Final Portfolio Value",
                f"${final_value:,.0f}",
                f"{total_return:.1f}% total return"
            )
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                "Annualized Return",
                f"{annualized_return:.2f}%",
                f"{sharpe_ratio:.2f} Sharpe Ratio"
            )
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(
                "Risk Metrics",
                f"{volatility:.2f}% vol",
                f"Max DD: {max_dd:.2f}%"
            )
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            if benchmark_return is not None:
                delta_color = "normal" if alpha >= 0 else "inverse"
                st.metric(
                    f"vs {benchmark_label}",
                    f"{total_return:.1f}%",
                    f"Alpha: {alpha:+.1f}%",
                    delta_color=delta_color
                )
            else:
                st.metric("Benchmark", "N/A", "No benchmark data")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Additional comparison metrics
        if benchmark_return is not None:
            st.markdown("### 📈 Performance Comparison Details")
            comp_col1, comp_col2, comp_col3, comp_col4 = st.columns(4)
            
            with comp_col1:
                st.metric("Portfolio Return", f"{total_return:.2f}%")
            with comp_col2:
                st.metric(f"{benchmark_label} Return", f"{benchmark_return:.2f}%")
            with comp_col3:
                st.metric("Outperformance (Alpha)", f"{alpha:+.2f}%")
            with comp_col4:
                if excess_volatility is not None:
                    vol_text = f"{excess_volatility:+.2f}%"
                    st.metric("Excess Volatility", vol_text)

    def display_etf_details(self, performance_data):
        """Display detailed ETF performance metrics"""
        st.markdown('<h2 class="section-header">📈 Asset Performance Details</h2>', unsafe_allow_html=True)
        
        if not performance_data:
            st.warning("No performance data available.")
            return
        
        # Separate S&P 500 from ETFs for highlighting
        etf_data = {k: v for k, v in performance_data.items() if k != 'S&P 500'}
        sp500_data = performance_data.get('S&P 500')
        
        # Convert to DataFrame for display
        if etf_data:
            metrics_df = pd.DataFrame(etf_data).T
            
            # Reorder columns
            columns_order = ['Ticker', 'Weight', 'Total Return (%)', 'Annual Return (%)', 
                            'Volatility (%)', 'Max Drawdown (%)', 'Sharpe Ratio', 'Win Rate (%)']
            
            metrics_df = metrics_df[columns_order]
            
            # Style the DataFrame
            styled_df = metrics_df.style.format({
                'Total Return (%)': '{:.2f}%',
                'Annual Return (%)': '{:.2f}%',
                'Volatility (%)': '{:.2f}%',
                'Max Drawdown (%)': '{:.2f}%',
                'Win Rate (%)': '{:.1f}%'
            }).background_gradient(cmap='RdYlGn', subset=['Annual Return (%)', 'Sharpe Ratio'])
            
            # Display ETF table
            st.markdown("### Portfolio ETFs")
            st.dataframe(styled_df, use_container_width=True, height=300)
        
        # Display S&P 500 separately if available
        if sp500_data:
            st.markdown("### Benchmark")
            sp500_df = pd.DataFrame([sp500_data])
            sp500_styled = sp500_df.style.format({
                'Total Return (%)': '{:.2f}%',
                'Annual Return (%)': '{:.2f}%',
                'Volatility (%)': '{:.2f}%',
                'Max Drawdown (%)': '{:.2f}%',
                'Win Rate (%)': '{:.1f}%'
            }).apply(lambda x: ['background-color: #FFE5D9' for _ in x], axis=1)
            
            st.dataframe(sp500_styled, use_container_width=True, height=100)

    def run_analysis(self, config):
        """Run the complete analysis"""
        # Fetch ETF data
        data = self.fetch_etf_data(
            config['etf_config'], 
            config['start_date'], 
            config['end_date']
        )
        
        if not data:
            st.error("❌ No ETF data could be fetched. Please check your ticker symbols and internet connection.")
            return
        
        # Fetch S&P 500 data if requested
        sp500_data = None
        if config['include_sp500']:
            with st.spinner("📥 Fetching S&P 500 data..."):
                sp500_data = self.fetch_sp500_data(config['start_date'], config['end_date'])
                if sp500_data:
                    st.success(f"✓ S&P 500 data fetched ({len(sp500_data['prices'])} days)")
                else:
                    st.warning("⚠️ Could not fetch S&P 500 data. Using equal-weight benchmark instead.")
        
        # Calculate performance metrics
        performance_data = self.calculate_performance_metrics(data, sp500_data)
        
        # Calculate portfolio returns
        portfolio_returns, portfolio_value, benchmark_value, benchmark_label = self.calculate_portfolio_returns(
            data, config['initial_capital'], sp500_data
        )
        
        # Store in session state
        st.session_state.data = data
        st.session_state.performance = performance_data
        st.session_state.sp500_data = sp500_data
        
        # Display results
        self.display_portfolio_summary(portfolio_value, benchmark_value, config['initial_capital'], 
                                     benchmark_label, portfolio_returns)
        
        # Portfolio Performance Chart
        st.markdown('<h2 class="section-header">📊 Portfolio Performance</h2>', unsafe_allow_html=True)
        fig1 = self.create_portfolio_performance_chart(
            portfolio_value, benchmark_value, config['initial_capital'], benchmark_label
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        # Normalized Price Performance Chart
        st.markdown('<h2 class="section-header">📈 Normalized Price Performance</h2>', unsafe_allow_html=True)
        fig2 = self.create_normalized_price_chart(data, portfolio_value, sp500_data, config['initial_capital'])
        st.plotly_chart(fig2, use_container_width=True)
        
        # Risk-Return and Correlation Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<h3 class="section-header" style="font-size: 1.2rem;">⚖️ Risk-Return Profile</h3>', unsafe_allow_html=True)
            fig3 = self.create_risk_return_scatter(performance_data)
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            st.markdown('<h3 class="section-header" style="font-size: 1.2rem;">🔗 Correlation Matrix</h3>', unsafe_allow_html=True)
            fig4 = self.create_correlation_matrix(data, sp500_data)
            if fig4:
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("Not enough data to calculate correlations.")
        
        # Asset Details
        self.display_etf_details(performance_data)
        
        # Additional Charts
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown('<h3 class="section-header" style="font-size: 1.2rem;">📊 Returns Distribution</h3>', unsafe_allow_html=True)
            fig5 = self.create_returns_distribution_chart(data, sp500_data)
            st.plotly_chart(fig5, use_container_width=True)
        
        with col4:
            # Add key statistics table
            st.markdown('<h3 class="section-header" style="font-size: 1.2rem;">📋 Key Statistics</h3>', unsafe_allow_html=True)
            
            # Calculate key statistics
            stats_data = []
            
            if portfolio_value is not None and len(portfolio_value) > 0:
                # Portfolio stats
                final_value = portfolio_value.iloc[-1]
                total_return = (final_value / config['initial_capital'] - 1) * 100
                
                # Best and worst months
                if portfolio_returns is not None and len(portfolio_returns) > 0:
                    monthly_returns = portfolio_returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
                    best_month = monthly_returns.max() * 100
                    worst_month = monthly_returns.min() * 100
                    
                    stats_data.append({
                        'Metric': 'Portfolio Total Return',
                        'Value': f'{total_return:.2f}%'
                    })
                    stats_data.append({
                        'Metric': 'Best Month',
                        'Value': f'{best_month:.2f}%'
                    })
                    stats_data.append({
                        'Metric': 'Worst Month',
                        'Value': f'{worst_month:.2f}%'
                    })
            
            # Benchmark stats if available
            if benchmark_value is not None and len(benchmark_value) > 0:
                benchmark_final = benchmark_value.iloc[-1]
                benchmark_return = (benchmark_final / config['initial_capital'] - 1) * 100
                
                stats_data.append({
                    'Metric': f'{benchmark_label} Return',
                    'Value': f'{benchmark_return:.2f}%'
                })
            
            # Number of ETFs
            stats_data.append({
                'Metric': 'Number of ETFs',
                'Value': str(len(data))
            })
            
            # Display as table
            if stats_data:
                stats_df = pd.DataFrame(stats_data)
                st.table(stats_df.style.set_properties(**{'text-align': 'left'}))

        # Export Data Section
        st.markdown('<h2 class="section-header">💾 Export Data</h2>', unsafe_allow_html=True)
        
        col5, col6, col7 = st.columns(3)
        
        with col5:
            # Export portfolio values
            if portfolio_value is not None:
                portfolio_df = pd.DataFrame({
                    'Date': portfolio_value.index,
                    'Portfolio_Value': portfolio_value.values,
                    'Daily_Return': portfolio_returns if portfolio_returns is not None else 0,
                    'Benchmark_Value': benchmark_value.values if benchmark_value is not None else 0
                })
                csv = portfolio_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Portfolio History",
                    data=csv,
                    file_name="portfolio_history.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        with col6:
            # Export ETF prices
            if data:
                prices_df = pd.DataFrame()
                for region, region_data in data.items():
                    prices_df[region] = region_data['prices']
                
                if sp500_data:
                    prices_df['S&P_500'] = sp500_data['prices']
                
                csv = prices_df.to_csv()
                st.download_button(
                    label="📥 Download Asset Prices",
                    data=csv,
                    file_name="asset_prices.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        with col7:
            # Export performance metrics
            if performance_data:
                metrics_df = pd.DataFrame(performance_data).T
                csv = metrics_df.to_csv()
                st.download_button(
                    label="📥 Download Performance Metrics",
                    data=csv,
                    file_name="performance_metrics.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    def show_welcome_screen(self):
        """Display welcome screen with instructions"""
        st.markdown("""
        <div style="text-align: center; padding: 3rem 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin-bottom: 2rem;">
            <h1 style="font-size: 3rem; margin-bottom: 1rem;">📈 ETF Portfolio Analyzer</h1>
            <p style="font-size: 1.2rem; margin-bottom: 2rem;">
                Analyze and compare your global ETF portfolio to S&P 500
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Instructions
        st.markdown("""
        ## 🚀 How to Use This Tool
        
        1. **Configure Portfolio** (in sidebar):
           - Adjust date range for analysis
           - Set ETF tickers and weights (must sum to 100%)
           - Enable S&P 500 comparison
           - Choose initial investment amount
        
        2. **Click "Run Portfolio Analysis"** to see results
        
        3. **Analyze Results**:
           - View portfolio performance vs. S&P 500
           - Compare normalized price performance of all assets
           - Assess risk-return profiles
           - Check correlations between ETFs
        
        ## 📋 Default Portfolio (Example)
        
        The default portfolio shows a diversified global allocation:
        
        | Region | ETF | Weight | Purpose |
        |--------|-----|--------|---------|
        | US | SPY | 40% | S&P 500 exposure |
        | Europe | VGK | 25% | European stocks |
        | Asia | VPL | 20% | Pacific region excluding Japan |
        | Japan | EWJ | 15% | Japanese market exposure |
        
        ## 🆕 New Features
        
        - **Fixed S&P 500 Comparison**: Proper portfolio vs benchmark comparison from same start date
        - **Normalized Price Chart**: All assets normalized to 100 for easy comparison
        - **Correlation Matrix**: See how ETFs correlate with each other and S&P 500
        - **Enhanced Metrics**: Alpha calculation, excess volatility, and more
        
        ## 💡 Tips
        
        - Use any ETF ticker from Yahoo Finance (e.g., QQQ, VTI, EFA)
        - Weights must sum to 100% for proper analysis
        - Enable S&P 500 comparison to see how you're doing vs the market
        - Longer time periods provide more stable statistics
        - Monitor correlation to ensure proper diversification
        """)

    def run_dashboard(self):
        """Main function to run the dashboard"""
        # Display header
        st.markdown('<h1 class="main-header">ETF Portfolio Analyzer with S&P 500 Comparison</h1>', unsafe_allow_html=True)
        
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
        analyzer = ETFAnalyzer()
        analyzer.run_dashboard()
    except Exception as e:
        st.error(f"❌ An error occurred: {str(e)}")
        st.info("💡 Tips for troubleshooting:")
        st.info("1. Check your internet connection")
        st.info("2. Verify ETF ticker symbols are correct")
        st.info("3. Try a shorter date range")
        st.info("4. Make sure portfolio weights sum to 100%")