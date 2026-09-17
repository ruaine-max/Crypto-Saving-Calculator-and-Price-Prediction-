# crypto_dca_streamlit.py
# Streamlit app: Crypto Investment Projection Dashboard
# Features:
# - Fetch current price + historical data from yfinance (Yahoo Finance, free)
# - Automatic CAGR detection based on date range
# - Weekly DCA vs Monthly DCA comparison
# - Worst/Base/Best scenarios
# - Optional CAGR decay over time (every N years)
# - Market crash simulation (random -30% or user-defined)
# - Log scale chart option for long-term price growth
# - New: Explicit separation of total contributions vs interest earned (compounding)

import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import plotly.graph_objects as go
import time
import random
import yfinance as yf

# ----------------- Helper functions -----------------
# Map coin names to Yahoo Finance tickers
YF_TICKER_MAP = {
    "bitcoin": "BTC-USD",
    "ethereum": "ETH-USD",
    "binancecoin": "BNB-USD",
    "solana": "SOL-USD",
    "cardano": "ADA-USD",
    "polkadot": "DOT-USD",
    "polygon": "MATIC-USD",
    "avalanche": "AVAX-USD",
    "chainlink": "LINK-USD",
    "litecoin": "LTC-USD",
    "uniswap": "UNI-USD",
    "stellar": "XLM-USD"
}

def number_to_words(num):
    """Convert a number to words (e.g., 1000000 -> 'One Million')"""
    if num < 0:
        return "Negative " + number_to_words(abs(num))
    
    if num == 0:
        return "Zero"
    
    # Define word mappings
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def convert_hundreds(n):
        result = ""
        if n >= 100:
            result += ones[n // 100] + " Hundred "
            n %= 100
        if n >= 20:
            result += tens[n // 10] + " "
            n %= 10
        if n > 0:
            result += ones[n] + " "
        return result.strip()
    
    # Handle large numbers
    if num >= 1_000_000_000_000:
        trillions = num // 1_000_000_000_000
        remainder = num % 1_000_000_000_000
        result = convert_hundreds(trillions) + " Trillion"
        if remainder > 0:
            result += " " + number_to_words(remainder)
        return result
    elif num >= 1_000_000_000:
        billions = num // 1_000_000_000
        remainder = num % 1_000_000_000
        result = convert_hundreds(billions) + " Billion"
        if remainder > 0:
            result += " " + number_to_words(remainder)
        return result
    elif num >= 1_000_000:
        millions = num // 1_000_000
        remainder = num % 1_000_000
        result = convert_hundreds(millions) + " Million"
        if remainder > 0:
            result += " " + number_to_words(remainder)
        return result
    elif num >= 1_000:
        thousands = num // 1_000
        remainder = num % 1_000
        result = convert_hundreds(thousands) + " Thousand"
        if remainder > 0:
            result += " " + convert_hundreds(remainder)
        return result
    else:
        return convert_hundreds(num)
    
def format_currency_with_words(amount):
    """Format currency with both number and words"""
    if amount < 0:
        return f"-${abs(amount):,.2f}", f"Negative {number_to_words(abs(amount))} Dollars"
    
    # Format number
    formatted_num = f"${amount:,.2f}"
    
    # Convert to words
    dollars = int(amount)
    cents = int((amount - dollars) * 100)
    
    if dollars == 0 and cents == 0:
        words = "Zero Dollars"
    elif dollars == 0:
        words = f"{number_to_words(cents)} Cent{'s' if cents != 1 else ''}"
    elif cents == 0:
        words = f"{number_to_words(dollars)} Dollar{'s' if dollars != 1 else ''}"
    else:
        words = f"{number_to_words(dollars)} Dollar{'s' if dollars != 1 else ''} and {number_to_words(cents)} Cent{'s' if cents != 1 else ''}"
    
    return formatted_num, words

@st.cache_data
def fetch_current_price(coin_id: str = 'bitcoin'):
    """Fetch current price using yfinance."""
    try:
        ticker = YF_TICKER_MAP.get(coin_id.lower(), "BTC-USD")
        crypto = yf.Ticker(ticker)
        data = crypto.history(period="1d", interval="1m")
        if not data.empty:
            return float(data["Close"].iloc[-1])
        return None
    except Exception as e:
        st.warning(f"Failed to fetch current price: {str(e)}")
        return None

@st.cache_data
def fetch_historical_prices(coin):
    """Fetch historical prices using yfinance (Yahoo Finance, free)."""
    try:
        ticker = YF_TICKER_MAP.get(coin.lower(), "BTC-USD")
        crypto = yf.Ticker(ticker)
        hist = crypto.history(period="max")
        if not hist.empty:
            df = pd.DataFrame({"price": hist["Close"]})
            df.index.name = "date"
            return df
        else:
            raise Exception("No historical data returned from yfinance")
    except ImportError:
        st.error("yfinance not installed. Install with: pip install yfinance")
        raise
    except Exception as e:
        st.error(f"Failed to fetch historical data from yfinance: {str(e)}")
        raise


def calc_cagr(start_price, end_price, years):
    if start_price <= 0 or years <= 0:
        return 0.0
    return (end_price / start_price) ** (1.0 / years) - 1.0


def get_cagr_from_range(df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp):
    df_range = df.loc[start_date:end_date]
    if df_range.empty:
        return None
    start_price = float(df_range.iloc[0]['price'])
    end_price = float(df_range.iloc[-1]['price'])
    years = (end_date - start_date).days / 365.25
    return calc_cagr(start_price, end_price, years)


def build_period_rates(annual_rate, total_periods, period_per_year, decay=False, decay_interval_years=1, decay_amount=0.0):
    rates = []
    current_annual = annual_rate
    periods_per_decay = int(decay_interval_years * period_per_year)
    for p in range(total_periods):
        if decay and p > 0 and (p % periods_per_decay) == 0:
            current_annual = max(current_annual - decay_amount, -0.9999)
        period_rate = (1 + current_annual) ** (1.0 / period_per_year) - 1
        rates.append(period_rate)
    return np.array(rates)


def simulate_dca(start_invest, contrib, contrib_freq, years, annual_rate, decay=False, decay_interval_years=1, decay_amount=0.0, start_price=1.0, crash_sim=False, crash_chance=0.0, crash_impact=-0.3, seed=None):
    # contrib_freq is one of the shared FREQ_OPTIONS keys (day/week/biweekly/semimonthly/
    # month/bimonthly/quarterly/half_year/year); periods_per_year() is defined further down
    # in this file but is resolved at call time, so it's available by the time this runs.
    n_periods_per_year = periods_per_year(contrib_freq) if contrib_freq in FREQ_OPTIONS else 12

    total_periods = max(1, int(round(years * n_periods_per_year)))
    period_rates = build_period_rates(annual_rate, total_periods, n_periods_per_year, decay, decay_interval_years, decay_amount)

    if seed is not None:
        random.seed(seed)

    coin_amount = start_invest / start_price
    total_contrib = 0.0
    contrib_amount = contrib
    history = []
    price = start_price

    crash_period = None
    if crash_sim and crash_chance > 0:
        if random.random() < crash_chance:
            crash_period = random.randint(0, total_periods - 1)

    for p in range(total_periods):
        if contrib_amount > 0:
            coin_amount += contrib_amount / price
            total_contrib += contrib_amount
        price *= (1 + period_rates[p])
        if crash_period == p:
            price *= (1 + crash_impact)
        value = coin_amount * price
        interest_earned = value - start_invest - total_contrib
        history.append({'period': p, 'price': price, 'coin_amount': coin_amount, 'value': value, 'total_contributions': total_contrib, 'interest_earned': interest_earned})

    df_hist = pd.DataFrame(history)
    return df_hist

# ----------------- Compounding / Withdrawal / ROI Calculators -----------------
# Shared frequency vocabulary used by the compounding, withdrawal and ROI tools below.
# Calendar-day and business-day lengths let us convert any of these labels into an
# exact "periods per year" figure (used inside A = P(1 + r/n)^(n*t)).
# NOTE: "bi-monthly" is ambiguous in everyday use, so both meanings are offered as
# distinct options: internal key 'semimonthly' = "Bi-Monthly (twice a month)" (24x/year),
# internal key 'bimonthly' = "Every 2 Months" (6x/year).
CALENDAR_DAYS_PER_PERIOD = {
    'day': 1, 'week': 7, 'biweekly': 14, 'semimonthly': 15.21875, 'month': 30.4375,
    'bimonthly': 60.875, 'quarterly': 91.3125, 'half_year': 182.625, 'year': 365.25,
}
BUSINESS_DAYS_PER_PERIOD = {
    'day': 1, 'week': 5, 'biweekly': 10, 'semimonthly': 10.5, 'month': 21,
    'bimonthly': 42, 'quarterly': 63, 'half_year': 126, 'year': 252,
}
FREQ_LABELS = {
    'day': 'Daily', 'week': 'Weekly', 'biweekly': 'Bi-Weekly',
    'semimonthly': 'Bi-Monthly (twice a month)', 'month': 'Monthly',
    'bimonthly': 'Every 2 Months', 'quarterly': 'Quarterly',
    'half_year': 'Half-Yearly', 'year': 'Yearly',
}
FREQ_OPTIONS = ['day', 'week', 'biweekly', 'semimonthly', 'month', 'bimonthly', 'quarterly', 'half_year', 'year']


def periods_per_year(freq, exclude_weekends=False):
    """Number of compounding/contribution periods per year for a given frequency label.
    exclude_weekends=True uses a 252 business-day year instead of a 365.25 calendar year."""
    if exclude_weekends:
        return 252.0 / BUSINESS_DAYS_PER_PERIOD[freq]
    return 365.25 / CALENDAR_DAYS_PER_PERIOD[freq]


# --- Compounding frequency (n in A = P(1 + r/n)^(nt)) ---
# This is how often interest actually compounds, so it gets the full weekend-aware list:
# day, day-excl-weekends, week, week-excl-weekends, bi-weekly, bi-weekly-excl-weekends,
# then semimonthly, month, bi-monthly, quarterly, half-year, year (no weekend variant
# needed at that scale).
COMPOUND_FREQ_MAP = {
    'day': ('day', False), 'day_nw': ('day', True),
    'week': ('week', False), 'week_nw': ('week', True),
    'biweekly': ('biweekly', False), 'biweekly_nw': ('biweekly', True),
    'semimonthly': ('semimonthly', False), 'month': ('month', False),
    'bimonthly': ('bimonthly', False), 'quarterly': ('quarterly', False),
    'half_year': ('half_year', False), 'year': ('year', False),
}
COMPOUND_FREQ_OPTIONS = list(COMPOUND_FREQ_MAP.keys())
COMPOUND_FREQ_LABELS = {
    'day': 'Daily', 'day_nw': 'Daily (excl. weekends)',
    'week': 'Weekly', 'week_nw': 'Weekly (excl. weekends)',
    'biweekly': 'Bi-Weekly', 'biweekly_nw': 'Bi-Weekly (excl. weekends)',
    'semimonthly': 'Bi-Monthly (twice a month)', 'month': 'Monthly',
    'bimonthly': 'Every 2 Months',
    'quarterly': 'Quarterly', 'half_year': 'Half-Yearly', 'year': 'Yearly',
}


def compound_periods_per_year(compound_freq_key):
    """Resolve one of the 12 COMPOUND_FREQ_OPTIONS keys into an exact periods-per-year (n)."""
    base_freq, exclude_weekends = COMPOUND_FREQ_MAP[compound_freq_key]
    return periods_per_year(base_freq, exclude_weekends=exclude_weekends)


# --- Interest-rate cadence ---
# This is the cadence the rate itself is quoted/known at (e.g. "0.02% daily" vs "5% annually").
# Only the plain 8 cadences apply here (no weekend split) -- it just describes how the number
# was given to you, and gets converted into an annual-equivalent rate before being used anywhere.
RATE_FREQ_OPTIONS = FREQ_OPTIONS


def rate_to_annual(rate_value, rate_freq):
    """Convert an interest rate quoted at a given cadence (daily/weekly/monthly/etc.) into its
    annual-equivalent rate: annual = (1 + period_rate)^(periods_per_year) - 1."""
    ppy = periods_per_year(rate_freq)
    return (1.0 + rate_value) ** ppy - 1.0


def compounding_schedule(principal, annual_rate, years, compound_freq='year',
                          additional_deposit=0.0, deposit_freq='month', compounding_enabled=True,
                          decay_enabled=False, decay_interval_years=1.0, decay_amount=0.0):
    """
    Interest calculator with optional recurring deposits made at their own (independent) frequency.

    compounding_enabled=True  -> compound interest: A = P(1 + r/n)^(n*t). Each period's interest
                                  is calculated on principal + deposits + all previously earned
                                  interest, so interest itself earns interest.
    compounding_enabled=False -> simple interest: A = P(1 + r*t). Each period's interest is
                                  calculated on principal + deposits ONLY -- earned interest is
                                  tracked separately and never reinvested/compounded.

    decay_enabled=True -> the annual rate itself steps DOWN by decay_amount (absolute percentage
                           points) every decay_interval_years, mirroring the "CAGR decay over time"
                           option in the DCA tool above -- useful for modeling a savings/staking
                           APY that's expected to compress over a long multi-decade horizon rather
                           than holding a single rate flat for 30 years.

    Deposits land at the start of whichever period they fall in, then that period's interest
    is applied (the standard convention used by most bank/savings calculators).
    Returns (period-by-period DataFrame, summary dict).
    """
    n = compound_periods_per_year(compound_freq)
    total_periods = max(1, int(round(years * n)))
    period_length_years = 1.0 / n

    dep_n = periods_per_year(deposit_freq)
    deposit_interval_years = (1.0 / dep_n) if additional_deposit > 0 else None

    principal_balance = principal   # grows only via new deposits, never via interest
    interest_balance = 0.0          # accumulated interest; reinvested only if compounding_enabled
    total_deposited = principal
    elapsed = 0.0
    next_deposit_at = deposit_interval_years
    current_annual_rate = annual_rate
    next_decay_at = decay_interval_years if decay_enabled else None

    rows = []
    for p in range(1, total_periods + 1):
        period_end = elapsed + period_length_years
        deposit_this_period = 0.0
        if next_deposit_at is not None:
            while next_deposit_at <= period_end + 1e-9:
                principal_balance += additional_deposit
                total_deposited += additional_deposit
                deposit_this_period += additional_deposit
                next_deposit_at += deposit_interval_years

        if decay_enabled:
            while next_decay_at is not None and next_decay_at <= elapsed + 1e-9:
                current_annual_rate = max(current_annual_rate - decay_amount, -0.9999)
                next_decay_at += decay_interval_years
        period_rate = current_annual_rate / n

        base_for_interest = (principal_balance + interest_balance) if compounding_enabled else principal_balance
        interest_this_period = base_for_interest * period_rate
        interest_balance += interest_this_period
        elapsed = period_end
        balance = principal_balance + interest_balance

        rows.append({
            'period': p, 'years_elapsed': round(elapsed, 4),
            'deposit': round(deposit_this_period, 8), 'interest': round(interest_this_period, 8),
            'balance': round(balance, 8), 'total_deposited': round(total_deposited, 8),
            'total_interest': round(interest_balance, 8), 'rate_used': round(current_annual_rate * 100, 4),
        })

    df = pd.DataFrame(rows)
    summary = {
        'final_balance': balance, 'total_deposited': total_deposited,
        'total_interest': balance - total_deposited,
        'periods_per_year': n, 'total_periods': total_periods,
        'final_annual_rate': current_annual_rate,
    }
    return df, summary


def format_years_months(years_float):
    """Format a fractional year count (e.g. 3.5) as a readable 'Xy Ymo' string."""
    y = int(years_float)
    m = int(round((years_float - y) * 12))
    if m == 12:
        y += 1
        m = 0
    if y and m:
        return f"{y}y {m}mo"
    elif y:
        return f"{y}y"
    else:
        return f"{m}mo"


def compounding_yearly_table(principal, annual_rate, years, n=1, compounding_enabled=True,
                              decay_enabled=False, decay_interval_years=1.0, decay_amount=0.0):
    """
    Reproduces the classic textbook year-by-year table (no extra deposits):
    Year | Starting Balance | Rate | Interest Earned | Ending Balance
    n = compounding periods per year (1 = annual, 12 = monthly, etc.)
    e.g. compounding_yearly_table(10000, 0.05, 10, n=1) matches the
    $10,000 -> $16,288.95 @ 5% annual example (compounding_enabled=True).
    With compounding_enabled=False, interest is simple interest (flat $ each year: P * r).
    With decay_enabled=True, the annual rate steps down by decay_amount every decay_interval_years.

    `years` can be fractional (e.g. 3.5 for "3 years 6 months") — full years are shown
    one row at a time, and any leftover months are shown as a final partial-year row.
    """
    rows = []
    principal_balance = principal
    interest_balance = 0.0
    full_years = int(years + 1e-9)
    remainder = years - full_years
    current_annual_rate = annual_rate
    next_decay_at = decay_interval_years if decay_enabled else None
    elapsed = 0.0

    def run_periods(num_periods):
        nonlocal interest_balance, current_annual_rate, next_decay_at, elapsed
        step = 1.0 / n
        for _ in range(int(round(num_periods))):
            if decay_enabled:
                while next_decay_at is not None and next_decay_at <= elapsed + 1e-9:
                    current_annual_rate = max(current_annual_rate - decay_amount, -0.9999)
                    next_decay_at += decay_interval_years
            period_rate = current_annual_rate / n
            base = (principal_balance + interest_balance) if compounding_enabled else principal_balance
            interest_balance += base * period_rate
            elapsed += step

    for year in range(1, full_years + 1):
        start_total = principal_balance + interest_balance
        run_periods(n)
        end_total = principal_balance + interest_balance
        rows.append({
            'Year': str(year), 'Starting Balance': round(start_total, 8),
            'Rate Applied': f"{current_annual_rate*100:.2f}%",
            'Interest Earned': round(end_total - start_total, 8),
            'Ending Balance': round(end_total, 8),
        })

    if remainder > 1e-9:
        start_total = principal_balance + interest_balance
        run_periods(n * remainder)
        end_total = principal_balance + interest_balance
        months_label = format_years_months(remainder)
        rows.append({
            'Year': f"{full_years + 1} ({months_label})", 'Starting Balance': round(start_total, 8),
            'Rate Applied': f"{current_annual_rate*100:.2f}%",
            'Interest Earned': round(end_total - start_total, 8),
            'Ending Balance': round(end_total, 8),
        })

    return pd.DataFrame(rows)


def withdrawal_schedule(starting_balance, annual_rate, years, compound_freq='year',
                         withdrawal_amount=0.0, withdrawal_freq='month', withdrawal_type='fixed',
                         compounding_enabled=True, decay_enabled=False, decay_interval_years=1.0, decay_amount=0.0):
    """
    Simulates a balance that keeps earning interest while regular withdrawals are taken.

    withdrawal_type:
      - 'fixed'                  : withdraw a fixed dollar amount each withdrawal period
      - 'percentage'              : withdraw a % of the CURRENT balance each withdrawal period
      - 'percentage_of_earnings'  : withdraw a % of just that period's interest/earnings,
                                     leaving the principal untouched as long as earnings cover it

    compounding_enabled=True  -> interest is calculated on principal + all undrawn interest
                                  (compound interest).
    compounding_enabled=False -> interest is calculated on the principal only, never on
                                  undrawn interest (simple interest). Withdrawals still draw
                                  from earned-but-undrawn interest first, then principal.

    decay_enabled=True -> the annual rate steps DOWN by decay_amount (absolute percentage points)
                           every decay_interval_years, same convention as compounding_schedule.
    """
    n = compound_periods_per_year(compound_freq)
    total_periods = max(1, int(round(years * n)))
    period_length_years = 1.0 / n

    wd_n = periods_per_year(withdrawal_freq)
    withdrawal_interval_years = 1.0 / wd_n

    principal_balance = starting_balance
    interest_balance = 0.0
    total_withdrawn = 0.0
    elapsed = 0.0
    next_withdrawal_at = withdrawal_interval_years
    current_annual_rate = annual_rate
    next_decay_at = decay_interval_years if decay_enabled else None

    rows = []
    depleted_at_period = None
    for p in range(1, total_periods + 1):
        period_end = elapsed + period_length_years

        if decay_enabled:
            while next_decay_at is not None and next_decay_at <= elapsed + 1e-9:
                current_annual_rate = max(current_annual_rate - decay_amount, -0.9999)
                next_decay_at += decay_interval_years
        period_rate = current_annual_rate / n

        base_for_interest = (principal_balance + interest_balance) if compounding_enabled else principal_balance
        interest_this_period = base_for_interest * period_rate
        interest_balance += interest_this_period
        balance = principal_balance + interest_balance

        withdrawal_this_period = 0.0
        while next_withdrawal_at <= period_end + 1e-9 and balance > 0:
            if withdrawal_type == 'fixed':
                amt = withdrawal_amount
            elif withdrawal_type == 'percentage':
                amt = balance * withdrawal_amount
            elif withdrawal_type == 'percentage_of_earnings':
                amt = max(interest_this_period, 0.0) * withdrawal_amount
            else:
                amt = 0.0
            amt = min(amt, balance)
            from_interest = min(amt, max(interest_balance, 0.0))
            interest_balance -= from_interest
            principal_balance -= (amt - from_interest)
            balance -= amt
            total_withdrawn += amt
            withdrawal_this_period += amt
            next_withdrawal_at += withdrawal_interval_years

        elapsed = period_end
        if balance <= 0 and depleted_at_period is None:
            depleted_at_period = p

        rows.append({
            'period': p, 'years_elapsed': round(elapsed, 4),
            'interest': round(interest_this_period, 8), 'withdrawal': round(withdrawal_this_period, 8),
            'balance': round(max(balance, 0.0), 8), 'total_withdrawn': round(total_withdrawn, 8),
            'rate_used': round(current_annual_rate * 100, 4),
        })
        if balance <= 0:
            break

    df = pd.DataFrame(rows)
    summary = {
        'final_balance': max(balance, 0.0), 'total_withdrawn': total_withdrawn,
        'depleted': depleted_at_period is not None, 'depleted_at_period': depleted_at_period,
        'final_annual_rate': current_annual_rate,
        'periods_per_year': n,
    }
    return df, summary


def roi_yield_breakdown(annual_rate):
    """
    Converts a single annual rate (e.g. the detected CAGR) into the equivalent periodic
    ROI/yield for every requested cadence. This is deliberately separate from CAGR itself:
    CAGR describes the long-run annualized growth rate, while this shows what that same
    growth rate implies per day/week/month/etc. Returns a DataFrame, one row per cadence.
    """
    cadences = [
        ('day', False, 'Daily'), ('day', True, 'Daily (excl. weekends)'),
        ('week', False, 'Weekly'), ('week', True, 'Weekly (excl. weekends)'),
        ('biweekly', False, 'Bi-Weekly'), ('biweekly', True, 'Bi-Weekly (excl. weekends)'),
        ('semimonthly', False, 'Bi-Monthly (twice a month)'),
        ('month', False, 'Monthly'), ('bimonthly', False, 'Every 2 Months'),
        ('quarterly', False, 'Quarterly'), ('half_year', False, 'Half-Yearly'),
        ('year', False, 'Yearly'),
    ]
    rows = []
    for freq, excl, label in cadences:
        ppy = periods_per_year(freq, exclude_weekends=excl)
        period_roi = (1 + annual_rate) ** (1.0 / ppy) - 1.0
        rows.append({
            'Cadence': label, 'Periods / Year': round(ppy, 2),
            'ROI per Period': f"{period_roi*100:.4f}%", '_period_roi': period_roi,
        })
    return pd.DataFrame(rows)


# ----------------- Streamlit UI -----------------
st.set_page_config(page_title='Crypto DCA Projection', layout='wide', initial_sidebar_state='expanded')

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    .result-box {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 1rem 0;
    }
    .number-display {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .words-display {
        font-size: 1.1rem;
        color: #666;
        font-style: italic;
        margin-top: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">📈 Crypto Investment Projection Dashboard</h1>', unsafe_allow_html=True)
st.markdown("---")

with st.sidebar:
    st.header('⚙️ Investment Parameters')
    
    # Crypto selection with display names
    crypto_options = {
        'bitcoin': 'Bitcoin (BTC)',
        'ethereum': 'Ethereum (ETH)',
        'binancecoin': 'Binance Coin (BNB)',
        'solana': 'Solana (SOL)',
        'cardano': 'Cardano (ADA)',
        'polkadot': 'Polkadot (DOT)',
        'polygon': 'Polygon (MATIC)',
        'avalanche': 'Avalanche (AVAX)',
        'chainlink': 'Chainlink (LINK)',
        'litecoin': 'Litecoin (LTC)',
        'uniswap': 'Uniswap (UNI)',
        'stellar': 'Stellar (XLM)'
    }
    
    selected_crypto_display = st.selectbox(
        '💰 Choose Cryptocurrency',
        options=list(crypto_options.values()),
        index=0
    )
    coin = [k for k, v in crypto_options.items() if v == selected_crypto_display][0]
    
    current_price = fetch_current_price(coin)
    if current_price:
        price_num, price_words = format_currency_with_words(current_price)
        st.markdown(f'### Current Price')
        st.markdown(f'<div class="number-display">{price_num}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="words-display">{price_words}</div>', unsafe_allow_html=True)
    else:
        st.warning('Unable to fetch current price')

    st.markdown('---')
    st.subheader('💵 Investment Details')
    
    start_invest = st.number_input('Starting Investment (USD)', min_value=0.0, value=1000.0, step=50.0, help="Initial lump sum investment")
    contrib = st.number_input('Contribution Amount (per period)', min_value=0.0, value=100.0, step=10.0, help="Amount to invest each period")
    contrib_freq = st.selectbox('Contribution Frequency', FREQ_OPTIONS, index=FREQ_OPTIONS.index('month'),
                                 format_func=lambda f: FREQ_LABELS[f], help="How often you'll make contributions")
    
    st.markdown('---')
    st.subheader('📅 Time Horizon')
    years = st.slider('Projection Period (Years)', min_value=1, max_value=60, value=10, help="How many years to project forward (up to 60 years)")
    if years > 30:
        st.info(f"📊 Long-term projection: {years} years - Great for retirement planning!")

    st.markdown('---')
    st.subheader('📊 Return Assumptions')
    auto_cagr = st.checkbox('Auto-detect CAGR from historical data', value=True, help="Uses historical price data to calculate average annual return")
    custom_cagr = st.number_input('Manual Annual Return (%)', min_value=-99.0, max_value=1000.0, value=10.0, help="Enter expected annual return if not using auto-detect") / 100.0

    decay_toggle = st.checkbox('Enable CAGR decay over time', value=False)
    if decay_toggle:
        decay_interval = st.number_input('Decay interval (years)', min_value=1, max_value=10, value=5)
        decay_amount_pct = st.number_input('Decay amount (absolute percentage points)', min_value=0.0, max_value=100.0, value=1.0) / 100.0
    else:
        decay_interval = 1
        decay_amount_pct = 0.0

    st.markdown('---')
    st.subheader('🎯 Scenario Analysis')
    include_scenarios = st.checkbox('Show Worst/Base/Best Scenarios', value=True, help="Compare different return scenarios")
    worst_delta = st.number_input('Worst-case Delta (%)', min_value=0.0, max_value=100.0, value=5.0, help="How much lower returns could be") / 100.0
    best_delta = st.number_input('Best-case Delta (%)', min_value=0.0, max_value=1000.0, value=5.0, help="How much higher returns could be") / 100.0

    crash_sim = st.checkbox('Enable market crash simulation (random)', value=True)
    if crash_sim:
        crash_chance = st.number_input('Probability of a crash in projection (%)', min_value=0.0, max_value=100.0, value=20.0) / 100.0
        crash_impact = st.number_input('Crash impact (e.g. -30% enter -30)', min_value=-99.0, max_value=0.0, value=-30.0) / 100.0
        monte_carlo_runs = st.number_input('Monte Carlo runs (for crash percentiles)', min_value=10, max_value=5000, value=500)
    else:
        crash_chance = 0.0
        crash_impact = 0.0
        monte_carlo_runs = 0

    st.markdown('---')
    st.subheader('📈 Chart Options')
    show_log = st.checkbox('Log Scale for Price Chart', value=True, help="Better visualization for long-term growth")
    show_price_chart = st.checkbox('Show Price Projection Chart', value=True)
    show_value_chart = st.checkbox('Show Portfolio Value Chart', value=True)
    show_compounding_chart = st.checkbox('Show Contributions vs Interest Chart', value=True, help="See how compounding grows your wealth")

# ----------------- Data & Calculations -----------------
with st.spinner('Fetching historical data and computing...'):
    hist_df = fetch_historical_prices(coin)
    first_date = hist_df.index.min()
    last_date = hist_df.index.max()
    detected_cagr = None
    if auto_cagr and not hist_df.empty:
        detected_cagr = get_cagr_from_range(hist_df, first_date, last_date)
    base_annual = detected_cagr if (auto_cagr and detected_cagr is not None) else custom_cagr
    base = base_annual
    worst = base - worst_delta
    best = base + best_delta

# Show summary
st.markdown("---")
st.markdown("### 📋 Investment Summary")
summary_cols = st.columns(4)
with summary_cols[0]:
    crypto_display_name = crypto_options.get(coin, coin).split('(')[0].strip()
    st.metric('Cryptocurrency', crypto_display_name)
with summary_cols[1]:
    st.metric('Detected CAGR', f"{base_annual*100:.2f}%")
with summary_cols[2]:
    st.metric('Time Horizon', f"{years} years")
with summary_cols[3]:
    freq_display = FREQ_LABELS[contrib_freq]
    st.metric('Frequency', freq_display)

# Run simulations
results = {}
for label, ann in [('Worst', worst), ('Base', base), ('Best', best)]:
    if not include_scenarios and label != 'Base':
        continue
    for freq in FREQ_OPTIONS:
        df_hist = simulate_dca(start_invest, contrib, freq, years, ann, decay=decay_toggle, decay_interval_years=decay_interval, decay_amount=decay_amount_pct, start_price=current_price if current_price else 1.0, crash_sim=False)
        final_value = float(df_hist['value'].iloc[-1])
        total_contributions = float(df_hist['total_contributions'].iloc[-1])
        interest_earned = float(df_hist['interest_earned'].iloc[-1])
        key = f"{label}_{freq}"
        results[key] = {'df': df_hist, 'final_value': final_value, 'annual': ann, 'total_contrib': total_contributions, 'interest': interest_earned}

# Display numeric results with words
st.markdown("---")
st.markdown("### 💰 Projection Results")

# Filter to show selected frequency
selected_freq_results = {k: v for k, v in results.items() if k.split('_', 1)[1] == contrib_freq}

if selected_freq_results:
    # Display main results in cards
    scenario_order = ['Base', 'Worst', 'Best'] if include_scenarios else ['Base']
    
    for scenario in scenario_order:
        key = f"{scenario}_{contrib_freq}"
        if key in selected_freq_results:
            v = selected_freq_results[key]
            final_num, final_words = format_currency_with_words(v['final_value'])
            contrib_num, contrib_words = format_currency_with_words(v['total_contrib'])
            interest_num, interest_words = format_currency_with_words(v['interest'])
            
            st.markdown(f"#### {scenario} Case Scenario ({FREQ_LABELS[contrib_freq]} Contributions)")
            
            cols = st.columns(3)
            
            with cols[0]:
                st.markdown('<div class="result-box">', unsafe_allow_html=True)
                st.markdown("**Final Portfolio Value**")
                st.markdown(f'<div class="number-display">{final_num}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="words-display">{final_words}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with cols[1]:
                st.markdown('<div class="result-box">', unsafe_allow_html=True)
                st.markdown("**Total Contributions**")
                st.markdown(f'<div class="number-display">{contrib_num}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="words-display">{contrib_words}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with cols[2]:
                st.markdown('<div class="result-box">', unsafe_allow_html=True)
                st.markdown("**Interest/Gains Earned**")
                st.markdown(f'<div class="number-display">{interest_num}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="words-display">{interest_words}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Calculate ROI
            roi = ((v['final_value'] - v['total_contrib'] - start_invest) / (v['total_contrib'] + start_invest)) * 100 if (v['total_contrib'] + start_invest) > 0 else 0
            st.markdown(f"**Return on Investment:** {roi:.2f}% | **Annual Return:** {v['annual']*100:.2f}%")
            st.markdown("---")

# Detailed comparison table
if include_scenarios and len(results) > 1:
    st.markdown("### 📊 Detailed Comparison Table")
    res_table = []
    for k, v in results.items():
        scenario, freq = k.split('_', 1)
        res_table.append({
            'Scenario': scenario,
            'Frequency': FREQ_LABELS[freq],
            'Final Value': f"${v['final_value']:,.2f}",
            'Contributions': f"${v['total_contrib']:,.2f}",
            'Gains': f"${v['interest']:,.2f}",
            'Annual Return': f"{v['annual']*100:.2f}%"
        })
    res_df = pd.DataFrame(res_table)
    st.dataframe(res_df, use_container_width=True, hide_index=True)

def format_coin_amount(amount, symbol, decimals=8):
    """Format a crypto quantity with a fixed number of decimals and its ticker symbol."""
    return f"{amount:,.{decimals}f} {symbol}"


FIAT_SYMBOLS = {'USD': '$', 'EUR': '€', 'GBP': '£'}
FX_TICKERS = {'EUR': 'EURUSD=X', 'GBP': 'GBPUSD=X'}  # gives USD per 1 unit of that currency


@st.cache_data(ttl=300)
def fetch_fx_rate_usd_per(currency):
    """USD value of 1 unit of `currency` (e.g. 1.08 for EUR). Returns None on failure."""
    if currency == 'USD':
        return 1.0
    ticker = FX_TICKERS.get(currency)
    if not ticker:
        return None
    try:
        fx = yf.Ticker(ticker)
        hist = fx.history(period="5d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception:
        pass
    return None


def format_fiat_amount(amount, currency):
    symbol = FIAT_SYMBOLS.get(currency, currency + ' ')
    return f"{symbol}{amount:,.2f}"


# ----------------- Compounding Savings / Withdrawal / ROI Section -----------------
# IMPORTANT: this is a high-yield SAVINGS account calculator -- the principal, deposits,
# and withdrawals are all denominated in the coin itself (e.g. BTC), and the interest rate
# represents a yield paid ON that coin (like a crypto savings/staking product). This is
# intentionally separate from the DCA/price-appreciation tool above, which instead answers
# "if I buy X coin now and keep contributing $Y, what is it worth later given price growth?"
crypto_symbol = crypto_options.get(coin, coin).split('(')[-1].rstrip(')').strip() or coin.upper()
crypto_disp_name_full = crypto_options.get(coin, coin)

st.markdown("---")
st.markdown(f"## 🏦 {crypto_symbol} High-Yield Savings Calculator")
st.caption(
    f"Models a high-yield savings/staking account where your {crypto_symbol} itself earns interest "
    f"(A = P(1 + r/n)^(nt), all in {crypto_symbol}) — separate from the DCA price-appreciation "
    f"projection above, which is about buying more {crypto_symbol} over time as its price changes."
)

unit_options = [crypto_symbol, 'USD', 'EUR', 'GBP']
savings_unit = st.selectbox(
    'Enter amounts in...', unit_options, index=0, key='savings_unit',
    help=f"Type amounts directly in {crypto_symbol}, or in a fiat currency — fiat entries are "
         f"converted to {crypto_symbol} at today's exchange rate to run the actual yield simulation "
         f"(the account still earns yield in {crypto_symbol}, not fiat)."
)

if savings_unit == crypto_symbol:
    unit_price = 1.0  # 1 coin = 1 coin; no conversion needed
else:
    unit_price_usd = current_price
    fx_rate = fetch_fx_rate_usd_per(savings_unit)  # USD per 1 unit of savings_unit
    unit_price = (unit_price_usd / fx_rate) if (unit_price_usd and fx_rate) else None
    if unit_price is None:
        st.warning(f"Couldn't fetch a live {savings_unit} exchange rate right now — falling back to {crypto_symbol} units below.")
        savings_unit = crypto_symbol
        unit_price = 1.0
    else:
        st.caption(f"💱 Using ≈ {format_fiat_amount(unit_price, savings_unit)} per {crypto_symbol} for conversion.")


def unit_amount_input(label, key, default_coin, min_value=0.0):
    """Number input that adapts to the selected savings unit (coin vs fiat).
    Always RETURNS the coin-equivalent amount for use in the calculation engine."""
    if savings_unit == crypto_symbol:
        return st.number_input(f'{label} ({crypto_symbol})', min_value=min_value,
                                value=float(default_coin), step=0.001, format="%.8f", key=key)
    default_display = round(float(default_coin) * unit_price, 2)
    raw = st.number_input(f'{label} ({savings_unit})', min_value=min_value,
                           value=default_display, step=50.0, format="%.2f", key=key)
    return raw / unit_price


def display_amount(coin_amount):
    """Format a coin-denominated amount in whichever unit is currently selected."""
    if savings_unit == crypto_symbol:
        return format_coin_amount(coin_amount, crypto_symbol)
    return format_fiat_amount(coin_amount * unit_price, savings_unit)


def convert_df_to_display_unit(df, coin_cols):
    """Return a copy of df with the given coin-denominated columns converted to the display unit."""
    if savings_unit == crypto_symbol:
        return df
    df2 = df.copy()
    for c in coin_cols:
        if c in df2.columns:
            df2[c] = (df2[c] * unit_price).round(2)
    return df2


calc_tabs = st.tabs(["📈 Compounding", "📉 Withdrawal", "🎯 ROI / Yield Breakdown", "💵 USD Outlook"])

FREQ_DISPLAY_FUNC = lambda f: FREQ_LABELS[f]

# --- Tab 1: Compounding ---
with calc_tabs[0]:
    st.subheader(f"Compound Interest on Your {crypto_symbol} Holdings")
    c1, c2 = st.columns(2)
    with c1:
        cc_principal = unit_amount_input('Initial Deposit — Principal (P)', 'cc_principal', default_coin=1.0)
        ccr1, ccr2 = st.columns(2)
        with ccr1:
            cc_rate_value = st.number_input('Interest Rate / APY (%)', min_value=-99.0, max_value=1000.0, value=5.0, step=0.1, key='cc_rate_value')
        with ccr2:
            cc_rate_freq = st.selectbox('Rate Is Quoted...', RATE_FREQ_OPTIONS, index=RATE_FREQ_OPTIONS.index('year'),
                                         format_func=FREQ_DISPLAY_FUNC, key='cc_rate_freq')
        cc_rate = rate_to_annual(cc_rate_value / 100.0, cc_rate_freq)
        st.caption(f"≈ {cc_rate*100:.4f}% equivalent annual rate")
        cyt1, cyt2 = st.columns(2)
        with cyt1:
            cc_years_part = st.number_input('Time Horizon — Years', min_value=0, max_value=60, value=10, step=1, key='cc_years_part')
        with cyt2:
            cc_months_part = st.number_input('+ Months', min_value=0, max_value=11, value=0, step=1, key='cc_months_part')
        cc_years = max(cc_years_part + cc_months_part / 12.0, 1.0 / 12.0)
        st.caption(f"t = {format_years_months(cc_years)} ({cc_years:.4f} years)")
        cc_decay_on = st.checkbox('📉 Rate Decays Over Time', value=False, key='cc_decay_on',
                                   help="Steps the APY down over long horizons instead of holding it flat — useful for 20-30 year projections where a high starting yield is unlikely to last.")
        if cc_decay_on:
            ccd1, ccd2 = st.columns(2)
            with ccd1:
                cc_decay_interval = st.number_input('Decay Every (years)', min_value=0.5, max_value=30.0, value=5.0, step=0.5, key='cc_decay_interval')
            with ccd2:
                cc_decay_amount = st.number_input('Decay Amount (pp)', min_value=0.0, max_value=50.0, value=1.0, step=0.5, key='cc_decay_amount')
        else:
            cc_decay_interval, cc_decay_amount = 5.0, 0.0
    with c2:
        cc_compounding_on = st.checkbox('🔁 Compounding Enabled', value=True, key='cc_compounding_on',
                                         help="Checked = compound interest (interest earns interest). Unchecked = simple interest (interest is only ever calculated on principal + deposits).")
        cc_compound_freq = st.selectbox('Compounding Frequency (n)', COMPOUND_FREQ_OPTIONS, index=COMPOUND_FREQ_OPTIONS.index('year'),
                                         format_func=lambda f: COMPOUND_FREQ_LABELS[f], key='cc_compound_freq',
                                         disabled=not cc_compounding_on,
                                         help="Ignored while compounding is off, since simple interest doesn't compound." if not cc_compounding_on else None)
        cc_deposit = unit_amount_input('Additional Recurring Deposit', 'cc_deposit', default_coin=0.0)
        cc_deposit_freq = st.selectbox('Deposit Frequency', FREQ_OPTIONS, index=FREQ_OPTIONS.index('month'),
                                        format_func=FREQ_DISPLAY_FUNC, key='cc_deposit_freq')
        if not cc_compounding_on:
            st.caption("📐 Simple interest mode: A = P(1 + r·t). Interest never earns interest.")

    cc_df, cc_summary = compounding_schedule(cc_principal, cc_rate, cc_years, cc_compound_freq, cc_deposit, cc_deposit_freq,
                                              cc_compounding_on, cc_decay_on, cc_decay_interval, cc_decay_amount / 100.0)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown("**Future Value (A)**")
        st.markdown(f'<div class="number-display">{display_amount(cc_summary["final_balance"])}</div>', unsafe_allow_html=True)
        if current_price and savings_unit != 'USD':
            st.markdown(f'<div class="words-display">≈ ${cc_summary["final_balance"]*current_price:,.2f} USD at today\'s price</div>', unsafe_allow_html=True)
    with m2:
        st.markdown("**Total Deposited**")
        st.markdown(f'<div class="number-display">{display_amount(cc_summary["total_deposited"])}</div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f"**Total {crypto_symbol} Earned (Interest)**")
        st.markdown(f'<div class="number-display">{display_amount(cc_summary["total_interest"])}</div>', unsafe_allow_html=True)

    if cc_decay_on:
        st.caption(f"📉 Rate decayed from {cc_rate*100:.2f}% to {cc_summary['final_annual_rate']*100:.2f}% annual by the end of the horizon (-{cc_decay_amount:.2f}pp every {cc_decay_interval:g}y).")

    if cc_compounding_on:
        st.caption(
            f"Formula: A = P(1 + r/n)^(nt) [compound interest] — rate entered as {cc_rate_value:.4f}% {FREQ_LABELS[cc_rate_freq].lower()} "
            f"→ {cc_rate*100:.4f}% annual; n = {cc_summary['periods_per_year']:.2f} periods/year "
            f"({COMPOUND_FREQ_LABELS[cc_compound_freq]} compounding), {cc_summary['total_periods']} total periods."
        )
    else:
        st.caption(
            f"Formula: A = P(1 + r·t) [simple interest — compounding OFF] — rate entered as {cc_rate_value:.4f}% "
            f"{FREQ_LABELS[cc_rate_freq].lower()} → {cc_rate*100:.4f}% annual. Interest never earns interest."
        )

    with st.expander(f"📄 Classic Year-by-Year Table (no extra deposits)"):
        yearly_table = compounding_yearly_table(cc_principal, cc_rate, cc_years, n=round(compound_periods_per_year(cc_compound_freq)),
                                                  compounding_enabled=cc_compounding_on, decay_enabled=cc_decay_on,
                                                  decay_interval_years=cc_decay_interval, decay_amount=cc_decay_amount / 100.0)
        st.dataframe(convert_df_to_display_unit(yearly_table, ['Starting Balance', 'Interest Earned', 'Ending Balance']),
                     use_container_width=True, hide_index=True)

    with st.expander(f"📊 Full Period-by-Period Schedule (with deposits)"):
        st.dataframe(convert_df_to_display_unit(cc_df, ['deposit', 'interest', 'balance', 'total_deposited', 'total_interest']),
                     use_container_width=True, hide_index=True)

    cc_df_display = convert_df_to_display_unit(cc_df, ['total_deposited', 'balance'])
    fig_cc = go.Figure()
    fig_cc.add_trace(go.Scatter(x=cc_df_display['period'], y=cc_df_display['total_deposited'], name='Total Deposited', line=dict(dash='dash')))
    fig_cc.add_trace(go.Scatter(x=cc_df_display['period'], y=cc_df_display['balance'], name='Balance (Deposits + Interest)'))
    fig_cc.update_layout(height=400, xaxis_title='Period', yaxis_title=savings_unit, template='plotly_white', hovermode='x unified')
    st.plotly_chart(fig_cc, use_container_width=True)

# --- Tab 2: Withdrawal ---
with calc_tabs[1]:
    st.subheader("Withdrawal Calculator")
    st.caption("Simulates drawing money out of a balance that keeps earning interest — useful for retirement / passive-income planning.")
    w1, w2 = st.columns(2)
    with w1:
        wd_start_balance = unit_amount_input('Starting Balance', 'wd_start_balance', default_coin=cc_summary['final_balance'])
        wdr1, wdr2 = st.columns(2)
        with wdr1:
            wd_rate_value = st.number_input('Interest Rate (%)', min_value=-99.0, max_value=1000.0, value=5.0, step=0.1, key='wd_rate_value')
        with wdr2:
            wd_rate_freq = st.selectbox('Rate Is Quoted...', RATE_FREQ_OPTIONS, index=RATE_FREQ_OPTIONS.index('year'),
                                         format_func=FREQ_DISPLAY_FUNC, key='wd_rate_freq')
        wd_rate = rate_to_annual(wd_rate_value / 100.0, wd_rate_freq)
        st.caption(f"≈ {wd_rate*100:.4f}% equivalent annual rate")
        wyt1, wyt2 = st.columns(2)
        with wyt1:
            wd_years_part = st.number_input('Time Horizon — Years', min_value=0, max_value=60, value=10, step=1, key='wd_years_part')
        with wyt2:
            wd_months_part = st.number_input('+ Months', min_value=0, max_value=11, value=0, step=1, key='wd_months_part')
        wd_years = max(wd_years_part + wd_months_part / 12.0, 1.0 / 12.0)
        st.caption(f"t = {format_years_months(wd_years)} ({wd_years:.4f} years)")
        wd_decay_on = st.checkbox('📉 Rate Decays Over Time', value=False, key='wd_decay_on',
                                   help="Steps the APY down over long horizons instead of holding it flat.")
        if wd_decay_on:
            wdd1, wdd2 = st.columns(2)
            with wdd1:
                wd_decay_interval = st.number_input('Decay Every (years)', min_value=0.5, max_value=30.0, value=5.0, step=0.5, key='wd_decay_interval')
            with wdd2:
                wd_decay_amount = st.number_input('Decay Amount (pp)', min_value=0.0, max_value=50.0, value=1.0, step=0.5, key='wd_decay_amount')
        else:
            wd_decay_interval, wd_decay_amount = 5.0, 0.0
        wd_compounding_on = st.checkbox('🔁 Compounding Enabled', value=True, key='wd_compounding_on',
                                         help="Checked = compound interest (interest earns interest). Unchecked = simple interest on the principal only.")
        wd_compound_freq = st.selectbox('Compounding Frequency', COMPOUND_FREQ_OPTIONS, index=COMPOUND_FREQ_OPTIONS.index('year'),
                                         format_func=lambda f: COMPOUND_FREQ_LABELS[f], key='wd_compound_freq',
                                         disabled=not wd_compounding_on,
                                         help="Ignored while compounding is off." if not wd_compounding_on else None)
        if not wd_compounding_on:
            st.caption("📐 Simple interest mode: interest is only ever calculated on the principal.")
    with w2:
        wd_type = st.selectbox(
            'Withdrawal Type', ['fixed', 'percentage', 'percentage_of_earnings'],
            format_func=lambda t: {'fixed': 'Fixed Amount', 'percentage': '% of Current Balance',
                                    'percentage_of_earnings': '% of Earnings Only'}[t],
            key='wd_type')
        if wd_type == 'fixed':
            wd_amount = unit_amount_input('Withdrawal Amount', 'wd_amount', default_coin=cc_summary['final_balance'] * 0.04 if cc_summary['final_balance'] > 0 else 0.01)
        else:
            wd_amount = st.number_input('Withdrawal Percentage (%)', min_value=0.0, max_value=100.0, value=4.0, step=0.5, key='wd_amount_pct') / 100.0
        wd_freq = st.selectbox('Withdrawal Frequency', FREQ_OPTIONS, index=FREQ_OPTIONS.index('month'),
                                format_func=FREQ_DISPLAY_FUNC, key='wd_freq')

    wd_df, wd_summary = withdrawal_schedule(wd_start_balance, wd_rate, wd_years, wd_compound_freq, wd_amount, wd_freq, wd_type,
                                             wd_compounding_on, wd_decay_on, wd_decay_interval, wd_decay_amount / 100.0)

    wm1, wm2 = st.columns(2)
    with wm1:
        st.markdown("**Remaining Balance**")
        st.markdown(f'<div class="number-display">{display_amount(wd_summary["final_balance"])}</div>', unsafe_allow_html=True)
        if current_price and savings_unit != 'USD':
            st.markdown(f'<div class="words-display">≈ ${wd_summary["final_balance"]*current_price:,.2f} USD at today\'s price</div>', unsafe_allow_html=True)
    with wm2:
        st.markdown("**Total Withdrawn**")
        st.markdown(f'<div class="number-display">{display_amount(wd_summary["total_withdrawn"])}</div>', unsafe_allow_html=True)

    if wd_decay_on:
        st.caption(f"📉 Rate decayed from {wd_rate*100:.2f}% to {wd_summary['final_annual_rate']*100:.2f}% annual by the end of the horizon.")

    if wd_summary['depleted']:
        st.warning(f"⚠️ Balance hit $0 at period {wd_summary['depleted_at_period']} ({COMPOUND_FREQ_LABELS[wd_compound_freq]} periods).")

    with st.expander("📊 Full Withdrawal Schedule"):
        st.dataframe(convert_df_to_display_unit(wd_df, ['interest', 'withdrawal', 'balance', 'total_withdrawn']),
                     use_container_width=True, hide_index=True)

    wd_df_display = convert_df_to_display_unit(wd_df, ['balance', 'total_withdrawn'])
    fig_wd = go.Figure()
    fig_wd.add_trace(go.Scatter(x=wd_df_display['period'], y=wd_df_display['balance'], name='Remaining Balance'))
    fig_wd.add_trace(go.Scatter(x=wd_df_display['period'], y=wd_df_display['total_withdrawn'], name='Cumulative Withdrawn', line=dict(dash='dash')))
    fig_wd.update_layout(height=400, xaxis_title='Period', yaxis_title=savings_unit, template='plotly_white', hovermode='x unified')
    st.plotly_chart(fig_wd, use_container_width=True)

# --- Tab 3: ROI / Yield Breakdown ---
with calc_tabs[2]:
    st.subheader("ROI / Yield Breakdown (separate from CAGR)")
    st.caption(
        "CAGR describes long-run annualized growth. This breaks that same annual rate down into "
        "the equivalent yield for shorter cadences — handy for comparing to daily/weekly staking "
        "or savings yields."
    )
    roi_rate = st.number_input(
        'Annual Rate to Break Down (%)', min_value=-99.0, max_value=1000.0,
        value=float(round(base_annual * 100, 4)), step=0.1, key='roi_rate',
        help="Defaults to the detected/entered CAGR from the sidebar, but you can override it."
    ) / 100.0
    roi_table = roi_yield_breakdown(roi_rate)
    st.dataframe(roi_table.drop(columns=['_period_roi']), use_container_width=True, hide_index=True)

    fig_roi = go.Figure()
    fig_roi.add_trace(go.Bar(x=roi_table['Cadence'], y=roi_table['_period_roi'] * 100))
    fig_roi.update_layout(height=400, xaxis_title='Cadence', yaxis_title='ROI per Period (%)', template='plotly_white')
    st.plotly_chart(fig_roi, use_container_width=True)

# --- Tab 4: Fiat/Price Outlook ---
with calc_tabs[3]:
    st.subheader(f"💵 What Your {crypto_symbol} Savings Balance Is Worth")
    st.caption(
        f"Your savings-account balance above is {cc_summary['final_balance']:,.8f} {crypto_symbol} "
        f"(grown purely from the interest rate you set — no price change assumed). This tab converts "
        f"that {crypto_symbol} quantity into fiat, both at today's price and at the price the DCA "
        f"tool's CAGR projects for the same time horizon — a separate, optional comparison, not part "
        f"of the yield math itself."
    )
    if current_price:
        future_price_compounded = current_price * ((1 + base_annual) ** cc_years)

        value_today = cc_summary['final_balance'] * current_price
        value_future_price = cc_summary['final_balance'] * future_price_compounded

        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            st.metric(f'{crypto_symbol} Price Today', f"${current_price:,.2f}")
        with pc2:
            st.metric(f'Projected Price in {format_years_months(cc_years)} (CAGR)', f"${future_price_compounded:,.2f}")
        with pc3:
            st.metric('CAGR Used (from DCA tool)', f"{base_annual*100:.2f}%")

        cq1, cq2 = st.columns(2)
        with cq1:
            st.markdown(f"**Your {cc_summary['final_balance']:,.8f} {crypto_symbol} is worth, at today's price:**")
            st.markdown(f'<div class="number-display">${value_today:,.2f}</div>', unsafe_allow_html=True)
        with cq2:
            st.markdown(f"**...or, if {crypto_symbol}'s price also grows at that CAGR:**")
            st.markdown(f'<div class="number-display">${value_future_price:,.2f}</div>', unsafe_allow_html=True)

        st.info(
            f"This deliberately separates two different growth effects: your savings-account balance "
            f"grows because it earns {crypto_symbol}-denominated interest (the Compounding tab above); "
            f"its fiat value can *also* grow if {crypto_symbol}'s price appreciates (this tab, using the "
            f"DCA tool's CAGR). They're independent — one doesn't require the other."
        )
    else:
        st.warning("Current price unavailable — can't convert to fiat right now.")

# Charts
st.markdown("---")
st.markdown("### 📈 Visualizations")

if show_price_chart or show_value_chart:
    chart_cols = st.columns(2)
    
    if show_price_chart:
        with chart_cols[0]:
            st.markdown('#### 💹 Projected Price Growth')
            fig = go.Figure()
            for k, v in results.items():
                scenario, freq = k.split('_', 1)
                if freq != contrib_freq:
                    continue
                dfv = v['df']
                fig.add_trace(go.Scatter(
                    x=dfv.index, 
                    y=dfv['price'], 
                    name=f'{scenario} ({FREQ_LABELS[freq]})',
                    line=dict(width=2)
                ))
            fig.update_layout(
                height=450,
                yaxis_type='log' if show_log else 'linear',
                xaxis_title='Period',
                yaxis_title='Price (USD)',
                hovermode='x unified',
                template='plotly_white',
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)

    if show_value_chart:
        with chart_cols[1]:
            st.markdown('#### 💼 Portfolio Value Over Time')
            fig2 = go.Figure()
            for k, v in results.items():
                scenario, freq = k.split('_', 1)
                if freq != contrib_freq:
                    continue
                dfv = v['df']
                fig2.add_trace(go.Scatter(
                    x=dfv.index, 
                    y=dfv['value'], 
                    name=f'{scenario} ({FREQ_LABELS[freq]})',
                    line=dict(width=2)
                ))
            fig2.update_layout(
                height=450,
                yaxis_type='linear',
                xaxis_title='Period',
                yaxis_title='Portfolio Value (USD)',
                hovermode='x unified',
                template='plotly_white',
                showlegend=True
            )
            st.plotly_chart(fig2, use_container_width=True)

if show_compounding_chart:
    st.markdown('#### 📊 Contributions vs Interest Earned (The Power of Compounding)')
    fig3 = go.Figure()
    
    # Filter to show only selected frequency
    for k, v in results.items():
        scenario, freq = k.split('_', 1)
        if freq == contrib_freq:
            dfv = v['df']
            fig3.add_trace(go.Scatter(
                x=dfv.index, 
                y=dfv['total_contributions'], 
                name=f'{scenario} - Contributions',
                line=dict(width=2, dash='dash'),
                mode='lines'
            ))
            fig3.add_trace(go.Scatter(
                x=dfv.index, 
                y=dfv['interest_earned'], 
                name=f'{scenario} - Interest/Gains',
                line=dict(width=2),
                mode='lines'
            ))
    
    fig3.update_layout(
        height=450,
        xaxis_title='Period',
        yaxis_title='Amount (USD)',
        yaxis_type='linear',
        hovermode='x unified',
        template='plotly_white',
        showlegend=True
    )
    st.plotly_chart(fig3, use_container_width=True)

st.markdown('---')
st.markdown("### ℹ️ Important Notes")
st.info("""
- **Contributions vs Interest Chart**: Shows how much of your portfolio comes from your own contributions versus gains from compounding
- **Contributions**: Added at the start of each period (weekly, monthly, or annually)
- **Historical CAGR**: Calculated from full price history using yfinance (Yahoo Finance data)
- **Long-term Projections**: For projections over 30 years, consider that market conditions may change significantly
- **Disclaimer**: These projections are estimates based on historical data and should not be considered financial advice
""")
