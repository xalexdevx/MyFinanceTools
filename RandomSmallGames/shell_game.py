import streamlit as st
import random

# Page configuration
st.set_page_config(
    page_title="Shell Game - Stone Guessing",
    page_icon="🎲",
    layout="centered"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .game-container {
        background-color: #f0f2f6;
        border-radius: 15px;
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .pot-container {
        display: flex;
        justify-content: center;
        gap: 2rem;
        margin: 2rem 0;
    }
    .pot {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        background: linear-gradient(145deg, #8B4513, #654321);
        border: 3px solid #654321;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 2rem;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .pot:hover {
        transform: scale(1.05);
        box-shadow: 0 6px 12px rgba(0,0,0,0.3);
    }
    .pot.selected {
        border-color: #FFD700;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
    }
    .stone {
        color: #2E2E2E;
        font-size: 1.5rem;
    }
    .gold-display {
        font-size: 2rem;
        font-weight: bold;
        color: #FFD700;
        text-align: center;
        margin: 1rem 0;
    }
    .result-message {
        font-size: 1.5rem;
        text-align: center;
        margin: 1rem 0;
        padding: 1rem;
        border-radius: 10px;
    }
    .win-message {
        background-color: #4CAF50;
        color: white;
    }
    .lose-message {
        background-color: #f44336;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'gold' not in st.session_state:
    st.session_state.gold = 120
if 'game_active' not in st.session_state:
    st.session_state.game_active = True
if 'selected_pot' not in st.session_state:
    st.session_state.selected_pot = None
if 'stone_pot' not in st.session_state:
    st.session_state.stone_pot = None
if 'bet_amount' not in st.session_state:
    st.session_state.bet_amount = 10
if 'game_result' not in st.session_state:
    st.session_state.game_result = None
if 'show_result' not in st.session_state:
    st.session_state.show_result = False

def reset_game():
    """Reset the game state for a new round"""
    st.session_state.selected_pot = None
    st.session_state.stone_pot = None
    st.session_state.game_result = None
    st.session_state.show_result = False

def play_game():
    """Execute the game logic"""
    if st.session_state.selected_pot is None:
        st.error("Please select a pot first!")
        return

    # Generate random stone location
    st.session_state.stone_pot = random.randint(1, 3)

    # Determine result
    if st.session_state.stone_pot == st.session_state.selected_pot:
        st.session_state.game_result = "win"
        st.session_state.gold += st.session_state.bet_amount * 2
    else:
        st.session_state.game_result = "lose"
        st.session_state.gold -= st.session_state.bet_amount

    st.session_state.show_result = True

    # Check if game should end
    if st.session_state.gold <= 0:
        st.session_state.game_active = False

# Main game interface
st.title("🎲 Shell Game - Stone Guessing")
st.markdown("**Guess which pot contains the stone!**")

# Gold display
st.markdown(f'<div class="gold-display">💰 Gold: {st.session_state.gold}</div>', unsafe_allow_html=True)

if not st.session_state.game_active:
    st.error("💸 Game Over! You've run out of gold.")
    if st.button("🔄 Start New Game"):
        st.session_state.gold = 120
        st.session_state.game_active = True
        reset_game()
        st.rerun()
else:
    # Betting interface
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### 💵 Place Your Bet")
        bet_options = [5, 10, 20, 50, 100]
        available_bets = [b for b in bet_options if b <= st.session_state.gold]

        if available_bets:
            st.session_state.bet_amount = st.selectbox(
                "Select bet amount:",
                available_bets,
                index=available_bets.index(min(st.session_state.bet_amount, max(available_bets))) if st.session_state.bet_amount in available_bets else 0
            )
        else:
            st.error("Not enough gold to bet!")
            st.session_state.game_active = False

    with col2:
        st.markdown("### 🎯 Select a Pot")
        st.markdown("Click on one of the pots below:")

    # Pot selection interface
    st.markdown('<div class="pot-container">', unsafe_allow_html=True)

    cols = st.columns(3)
    for i in range(3):
        with cols[i]:
            pot_num = i + 1
            if st.button(f"Pot {pot_num}", key=f"pot_{pot_num}", use_container_width=True):
                st.session_state.selected_pot = pot_num
                play_game()

    st.markdown('</div>', unsafe_allow_html=True)

    # Show selected pot
    if st.session_state.selected_pot:
        st.info(f"🎯 You selected Pot {st.session_state.selected_pot}")

    # Show result
    if st.session_state.show_result:
        if st.session_state.game_result == "win":
            st.markdown('<div class="result-message win-message">🎉 You Win! The stone was in Pot {}</div>'.format(st.session_state.stone_pot), unsafe_allow_html=True)
        else:
            st.markdown('<div class="result-message lose-message">😞 You Lose! The stone was in Pot {}</div>'.format(st.session_state.stone_pot), unsafe_allow_html=True)

        # Show pots with stone revealed
        st.markdown("### 🔍 Reveal")
        reveal_cols = st.columns(3)
        for i in range(3):
            with reveal_cols[i]:
                pot_num = i + 1
                if pot_num == st.session_state.stone_pot:
                    st.markdown(f'<div class="pot"><div class="stone">🪨</div></div>', unsafe_allow_html=True)
                    st.caption("Stone here!")
                else:
                    st.markdown(f'<div class="pot"><div class="stone">❌</div></div>', unsafe_allow_html=True)
                    st.caption("Empty")

        # Play again button
        if st.button("🎮 Play Again", use_container_width=True):
            reset_game()
            st.rerun()

# Game rules
with st.expander("📖 Game Rules"):
    st.markdown("""
    **How to Play:**
    1. You start with 120 gold coins
    2. Place a bet (5, 10, 20, 50, or 100 gold)
    3. Click on one of the three pots to guess where the stone is
    4. If you guess correctly, you win double your bet!
    5. If you guess wrong, you lose your bet
    6. Keep playing until you run out of gold or decide to stop

    **Tips:**
    - Start with smaller bets to learn the game
    - The stone location is completely random each time
    - There's a 1/3 chance of winning each round
    """)

# Statistics
with st.expander("📊 Game Statistics"):
    if st.session_state.gold != 120:
        initial_gold = 120
        current_gold = st.session_state.gold
        profit_loss = current_gold - initial_gold
        win_rate = "N/A (no games played yet)"

        st.metric("Starting Gold", f"{initial_gold} 💰")
        st.metric("Current Gold", f"{current_gold} 💰")
        st.metric("Profit/Loss", f"{profit_loss:+} 💰")
    else:
        st.info("Play a few rounds to see your statistics!")