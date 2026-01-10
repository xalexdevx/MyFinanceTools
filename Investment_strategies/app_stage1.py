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
            'weights_valid': total_weight == 100
        }

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

    def calculate_performance_metrics(self, data):
        """Calculate performance metrics for each ETF"""
        performance_data = {}
        
        for region, region_data in data.items():
            prices = region_data['prices']
            returns = region_data['returns'].dropna()
            
            if len(prices) == 0 or len(returns) == 0:
                continue
            
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
            
            performance_data[region] = {
                'Ticker': region_data['ticker'],
                'Weight': f"{region_data['weight']*100:.1f}%",
                'Total Return (%)': round(total_return, 2),
                'Annual Return (%)': round(annual_return, 2),
                'Volatility (%)': round(volatility, 2),
                'Max Drawdown (%)': round(max_drawdown, 2),
                'Sharpe Ratio': round(sharpe_ratio, 2),
                'Win Rate (%)': round(win_rate, 1),
                'Color': region_data['color']
            }
        
        return performance_data

    def calculate_portfolio_returns(self, data, initial_capital):
        """Calculate portfolio returns based on weights"""
        # Combine all returns into a single DataFrame
        returns_df = pd.DataFrame()
        
        for region, region_data in data.items():
            returns_df[region] = region_data['returns']
        
        if returns_df.empty:
            return None, None, None
        
        # Drop NaN values
        returns_df = returns_df.dropna()
        
        if returns_df.empty:
            return None, None, None
        
        # Get weights
        weights = {region: region_data['weight'] for region, region_data in data.items()}
        
        # Calculate weighted portfolio returns
        portfolio_returns = pd.Series(0.0, index=returns_df.index)
        
        for region in returns_df.columns:
            if region in weights:
                portfolio_returns += weights[region] * returns_df[region]
        
        # Calculate portfolio value over time
        portfolio_value = initial_capital * (1 + portfolio_returns).cumprod()
        
        # Calculate benchmark (equal weight)
        equal_weight_returns = returns_df.mean(axis=1)
        benchmark_value = initial_capital * (1 + equal_weight_returns).cumprod()
        
        return portfolio_returns, portfolio_value, benchmark_value

    def create_portfolio_performance_chart(self, portfolio_value, benchmark_value, initial_capital):
        """Create portfolio performance chart"""
        fig = go.Figure()
        
        # Add portfolio line
        fig.add_trace(go.Scatter(
            x=portfolio_value.index,
            y=portfolio_value,
            mode='lines',
            name='Your Portfolio',
            line=dict(color='#1E88E5', width=3)
        ))
        
        # Add benchmark line
        fig.add_trace(go.Scatter(
            x=benchmark_value.index,
            y=benchmark_value,
            mode='lines',
            name='Equal Weight Benchmark',
            line=dict(color='#FF5722', width=2, dash='dash')
        ))
        
        # Add initial investment line
        fig.add_hline(
            y=initial_capital,
            line_dash="dot",
            line_color="gray",
            annotation_text=f"Initial: ${initial_capital:,.0f}",
            annotation_position="bottom right"
        )
        
        fig.update_layout(
            title='Portfolio Performance Over Time',
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

    def create_etf_performance_chart(self, data):
        """Create normalized ETF performance chart"""
        fig = go.Figure()
        
        for region, region_data in data.items():
            # Normalize prices to starting value
            prices = region_data['prices']
            normalized = prices / prices.iloc[0]
            
            fig.add_trace(go.Scatter(
                x=normalized.index,
                y=normalized,
                mode='lines',
                name=f"{region} ({region_data['ticker']})",
                line=dict(color=region_data['color'], width=2),
                hovertemplate=f"{region}: %{{y:.2f}}x<extra></extra>"
            ))
        
        fig.update_layout(
            title='ETF Performance (Normalized to Starting Value)',
            xaxis_title='Date',
            yaxis_title='Growth Multiple',
            hovermode='x unified',
            template='plotly_white',
            height=400,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )
        
        return fig

    def create_returns_distribution_chart(self, returns_data):
        """Create distribution of returns chart"""
        fig = go.Figure()
        
        for region, returns in returns_data.items():
            fig.add_trace(go.Histogram(
                x=returns,
                name=region,
                opacity=0.7,
                nbinsx=50,
                marker_color=returns_data[region]['color']
            ))
        
        fig.update_layout(
            title='Distribution of Daily Returns',
            xaxis_title='Daily Return (%)',
            yaxis_title='Frequency',
            barmode='overlay',
            template='plotly_white',
            height=400
        )
        
        # Add mean line
        for region, returns in returns_data.items():
            mean_return = returns.mean() * 100
            fig.add_vline(
                x=mean_return,
                line_dash="dash",
                line_color=returns_data[region]['color'],
                annotation_text=f"{region}: {mean_return:.2f}%",
                annotation_position="top"
            )
        
        return fig

    def create_risk_return_scatter(self, performance_data):
        """Create risk-return scatter plot"""
        fig = go.Figure()
        
        regions = list(performance_data.keys())
        returns = [performance_data[r]['Annual Return (%)'] for r in regions]
        volatilities = [performance_data[r]['Volatility (%)'] for r in regions]
        colors = [performance_data[r]['Color'] for r in regions]
        sizes = [performance_data[r]['Weight'].replace('%', '') for r in regions]
        
        fig.add_trace(go.Scatter(
            x=volatilities,
            y=returns,
            mode='markers+text',
            marker=dict(
                size=[float(s)*2 for s in sizes],  # Scale size by weight
                color=colors,
                line=dict(width=2, color='DarkSlateGrey')
            ),
            text=regions,
            textposition="top center",
            hovertemplate="<b>%{text}</b><br>" +
                        "Return: %{y:.2f}%<br>" +
                        "Volatility: %{x:.2f}%<br>" +
                        "Weight: %{marker.size:.0f}%<extra></extra>"
        ))
        
        # Add quadrant lines (average return and volatility)
        avg_return = np.mean(returns)
        avg_volatility = np.mean(volatilities)
        
        fig.add_hline(y=avg_return, line_dash="dot", line_color="gray")
        fig.add_vline(x=avg_volatility, line_dash="dot", line_color="gray")
        
        fig.update_layout(
            title='Risk-Return Profile of ETFs',
            xaxis_title='Annual Volatility (%)',
            yaxis_title='Annual Return (%)',
            template='plotly_white',
            height=500,
            showlegend=False
        )
        
        # Add quadrant annotations
        fig.add_annotation(x=avg_volatility*0.8, y=avg_return*1.2, 
                          text="High Return<br>Low Risk", showarrow=False)
        fig.add_annotation(x=avg_volatility*1.2, y=avg_return*1.2, 
                          text="High Return<br>High Risk", showarrow=False)
        fig.add_annotation(x=avg_volatility*0.8, y=avg_return*0.8, 
                          text="Low Return<br>Low Risk", showarrow=False)
        fig.add_annotation(x=avg_volatility*1.2, y=avg_return*0.8, 
                          text="Low Return<br>High Risk", showarrow=False)
        
        return fig

    def create_correlation_matrix(self, data):
        """Create correlation matrix heatmap"""
        # Prepare returns data
        returns_df = pd.DataFrame()
        
        for region, region_data in data.items():
            returns_df[region] = region_data['returns']
        
        if returns_df.empty:
            return None
        
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
            hoverongaps=False
        ))
        
        fig.update_layout(
            title='Correlation Matrix Between ETFs',
            xaxis_title='ETF',
            yaxis_title='ETF',
            template='plotly_white',
            height=400
        )
        
        return fig

    def display_portfolio_summary(self, portfolio_value, benchmark_value, initial_capital):
        """Display portfolio summary metrics"""
        st.markdown('<h2 class="section-header">📊 Portfolio Summary</h2>', unsafe_allow_html=True)
        
        if portfolio_value is None or len(portfolio_value) == 0:
            st.warning("Unable to calculate portfolio metrics. Please check your data.")
            return
        
        # Calculate portfolio metrics
        final_value = portfolio_value.iloc[-1]
        total_return = (final_value / initial_capital - 1) * 100
        
        # Calculate portfolio returns
        portfolio_returns = portfolio_value.pct_change().dropna()
        annualized_return = ((1 + total_return/100) ** (252/len(portfolio_returns)) - 1) * 100
        volatility = portfolio_returns.std() * np.sqrt(252) * 100
        sharpe_ratio = (annualized_return / volatility) if volatility != 0 else 0
        
        # Calculate maximum drawdown
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_dd = drawdown.min() * 100
        
        # Calculate benchmark metrics
        if benchmark_value is not None:
            benchmark_final = benchmark_value.iloc[-1]
            benchmark_return = (benchmark_final / initial_capital - 1) * 100
            alpha = total_return - benchmark_return
        else:
            benchmark_return = None
            alpha = None
        
        # Display metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Final Portfolio Value",
                f"${final_value:,.0f}",
                f"{total_return:.1f}% total return"
            )
        
        with col2:
            st.metric(
                "Annualized Return",
                f"{annualized_return:.2f}%",
                f"{sharpe_ratio:.2f} Sharpe Ratio"
            )
        
        with col3:
            st.metric(
                "Volatility",
                f"{volatility:.2f}%",
                f"Max Drawdown: {max_dd:.2f}%"
            )
        
        with col4:
            if benchmark_return is not None:
                delta_color = "normal" if alpha >= 0 else "inverse"
                st.metric(
                    "vs. Benchmark",
                    f"{total_return:.1f}%",
                    f"Alpha: {alpha:+.1f}%",
                    delta_color=delta_color
                )
            else:
                st.metric("Benchmark", "N/A", "No benchmark data")

    def display_etf_details(self, performance_data):
        """Display detailed ETF performance metrics"""
        st.markdown('<h2 class="section-header">📈 ETF Performance Details</h2>', unsafe_allow_html=True)
        
        if not performance_data:
            st.warning("No performance data available.")
            return
        
        # Convert to DataFrame for display
        metrics_df = pd.DataFrame(performance_data).T
        
        # Reorder columns
        columns_order = ['Ticker', 'Weight', 'Total Return (%)', 'Annual Return (%)', 
                        'Volatility (%)', 'Max Drawdown (%)', 'Sharpe Ratio', 'Win Rate (%)']
        
        metrics_df = metrics_df[columns_order]
        
        # Display with formatting
        st.dataframe(
            metrics_df.style.format({
                'Total Return (%)': '{:.2f}%',
                'Annual Return (%)': '{:.2f}%',
                'Volatility (%)': '{:.2f}%',
                'Max Drawdown (%)': '{:.2f}%',
                'Win Rate (%)': '{:.1f}%'
            }).background_gradient(cmap='RdYlGn', subset=['Annual Return (%)', 'Sharpe Ratio']),
            use_container_width=True,
            height=300
        )

    def run_analysis(self, config):
        """Run the complete analysis"""
        # Fetch data
        data = self.fetch_etf_data(
            config['etf_config'], 
            config['start_date'], 
            config['end_date']
        )
        
        if not data:
            st.error("❌ No data could be fetched. Please check your ticker symbols and internet connection.")
            return
        
        # Calculate performance metrics
        performance_data = self.calculate_performance_metrics(data)
        
        # Calculate portfolio returns
        portfolio_returns, portfolio_value, benchmark_value = self.calculate_portfolio_returns(
            data, config['initial_capital']
        )
        
        # Store in session state
        st.session_state.data = data
        st.session_state.performance = performance_data
        
        # Display results
        self.display_portfolio_summary(portfolio_value, benchmark_value, config['initial_capital'])
        
        # Portfolio Performance Chart
        st.markdown('<h2 class="section-header">📊 Portfolio Performance</h2>', unsafe_allow_html=True)
        fig1 = self.create_portfolio_performance_chart(portfolio_value, benchmark_value, config['initial_capital'])
        st.plotly_chart(fig1, use_container_width=True)
        
        # ETF Performance Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<h3 class="section-header" style="font-size: 1.2rem;">📈 Individual ETF Performance</h3>', unsafe_allow_html=True)
            fig2 = self.create_etf_performance_chart(data)
            st.plotly_chart(fig2, use_container_width=True)
        
        with col2:
            st.markdown('<h3 class="section-header" style="font-size: 1.2rem;">⚖️ Risk-Return Profile</h3>', unsafe_allow_html=True)
            fig3 = self.create_risk_return_scatter(performance_data)
            st.plotly_chart(fig3, use_container_width=True)
        
        # ETF Details
        self.display_etf_details(performance_data)
        
        # Additional Charts
        col3, col4 = st.columns(2)
        
        with col3:
            # Prepare returns data for distribution chart
            returns_data = {}
            for region, region_data in data.items():
                returns = region_data['returns'].dropna() * 100  # Convert to percentage
                if len(returns) > 0:
                    returns_data[region] = {
                        'returns': returns,
                        'color': region_data['color']
                    }
            
            if returns_data:
                st.markdown('<h3 class="section-header" style="font-size: 1.2rem;">📊 Returns Distribution</h3>', unsafe_allow_html=True)
                fig4 = self.create_returns_distribution_chart(returns_data)
                st.plotly_chart(fig4, use_container_width=True)
        
        with col4:
            st.markdown('<h3 class="section-header" style="font-size: 1.2rem;">🔗 Correlation Matrix</h3>', unsafe_allow_html=True)
            fig5 = self.create_correlation_matrix(data)
            if fig5:
                st.plotly_chart(fig5, use_container_width=True)
            else:
                st.info("Not enough data to calculate correlations.")
        
        # Export Data Section
        st.markdown('<h2 class="section-header">💾 Export Data</h2>', unsafe_allow_html=True)
        
        col5, col6, col7 = st.columns(3)
        
        with col5:
            # Export portfolio values
            if portfolio_value is not None:
                portfolio_df = pd.DataFrame({
                    'Date': portfolio_value.index,
                    'Portfolio_Value': portfolio_value.values,
                    'Daily_Return': portfolio_returns if portfolio_returns is not None else 0
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
                
                csv = prices_df.to_csv()
                st.download_button(
                    label="📥 Download ETF Prices",
                    data=csv,
                    file_name="etf_prices.csv",
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
                Analyze and visualize your global ETF portfolio performance
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Instructions
        st.markdown("""
        ## 🚀 How to Use This Tool
        
        1. **Configure Portfolio** (in sidebar):
           - Adjust date range for analysis
           - Set ETF tickers and weights (must sum to 100%)
           - Choose initial investment amount
        
        2. **Click "Run Portfolio Analysis"** to see results
        
        3. **Analyze Results**:
           - View portfolio performance vs. benchmark
           - Compare individual ETF returns
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
        
        ## 💡 Tips
        
        - Use any ETF ticker from Yahoo Finance (e.g., QQQ, VTI, EFA)
        - Weights must sum to 100% for proper analysis
        - Longer time periods provide more stable statistics
        - Monitor correlation to ensure proper diversification
        """)

    def run_dashboard(self):
        """Main function to run the dashboard"""
        # Display header
        st.markdown('<h1 class="main-header">ETF Portfolio Analyzer</h1>', unsafe_allow_html=True)
        
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
        
        
        
# TO OPEN, RUN THIS SCRIPT: 
# streamlit run Investment_strategies/app_stage1.py