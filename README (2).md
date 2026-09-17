# 🚀 Crypto Investment Projection & DCA Simulator

A **professional-grade crypto investment calculator and simulation
dashboard** built with **Python + Streamlit**, designed to model
realistic long‑term cryptocurrency investing.

This AI‑assisted project simulates weekly or monthly DCA, auto‑detects
historical CAGR using yfinance, analyzes best/worst/base scenarios, and
visualizes long‑term compounding growth with beautiful charts.

------------------------------------------------------------------------

## ✨ Key Features

### 🔹 Real-Time Crypto Price

-   Fetches live data via **yfinance**
-   Assets supported: **BTC, ETH, BNB, SOL, ADA, DOT, MATIC, AVAX, LINK,
    LTC, UNI, XLM**
-   Prices displayed in **numeric & written English**

------------------------------------------------------------------------

### 🔹 Historical Price Data (yfinance)

-   Full price history downloaded automatically
-   Used to compute:
    -   Historical CAGR\
    -   Price projections\
    -   Long‑term compounding outcomes

------------------------------------------------------------------------

### 🔹 DCA (Dollar Cost Averaging) Simulation Engine

Simulates growth using: - Lump-sum starting investment\
- Weekly / monthly / annual contributions\
- Custom time horizon (1--60 years)\
- Optional CAGR decay\
- Price fluctuation modeling

Outputs: - Final portfolio value\
- Total contributions\
- Gains / Interest earned\
- ROI\
- Annualized return

------------------------------------------------------------------------

### 🔹 Scenario Modeling

Compare: - **Worst-case** (CAGR − X%)\
- **Base-case** (real CAGR or manual input)\
- **Best-case** (CAGR + X%)

Each scenario includes charts for: - Price projection\
- Portfolio value\
- Contributions vs interest

------------------------------------------------------------------------

### 🔹 Monte Carlo Crash Simulation

Simulates: - Random market crashes\
- Crash probability\
- Crash severity (−10% to −90%)

Outputs include: - Mean result\
- Median result\
- 10th percentile\
- 90th percentile

------------------------------------------------------------------------

### 🔹 Visualizations (Plotly)

-   📈 Portfolio growth chart\
-   💹 Price projection (linear/log)\
-   💰 Contribution vs Interest earned\
-   🟦 Long-term Bitcoin history

------------------------------------------------------------------------

### 🔹 Export Options

-   Export simulation results as **CSV** for Excel/Sheets/analysis

------------------------------------------------------------------------

## 🛠 Tech Stack

-   Python 3.10+\
-   Streamlit\
-   Pandas\
-   NumPy\
-   Plotly\
-   yfinance\
-   Requests

Skills demonstrated: - Financial modeling\
- Time-series analysis\
- CAGR calculations\
- Monte Carlo simulation\
- Data visualization\
- Streamlit dashboard engineering\
- Real API integration

------------------------------------------------------------------------

## 📦 Installation Guide

Run these commands in **CMD / PowerShell / macOS Terminal / Linux**.

### 1. Clone repository

``` bash
git clone https://gitlab.com/smith.reevah/crypto-price-predictor-calculator-simulator.git
cd crypto-price-predictor-calculator-simulator
```

### 2. Create virtual environment

``` bash
python -m venv venv
```

### 3. Activate environment

**Windows**

``` bash
venv\Scriptsctivate
```

**macOS/Linux**

``` bash
source venv/bin/activate
```

### 4. Install dependencies

``` bash
pip install -r requirements.txt
```

### 5. Run the application

``` bash
streamlit run crypto_dca_streamlit.py
```

------------------------------------------------------------------------

## 📂 Project Structure

    project-folder/
    ├── crypto_dca_streamlit.py   # Main Streamlit application
    ├── requirements.txt          # Python dependencies
    ├── README.md                 # This file
    ├── LICENSE                   # MIT License
    └── assets/                   # Optional: screenshots / demo video

------------------------------------------------------------------------

## 🎥 Demo Video

Watch the full demo here:\
https://youtu.be/qhuUiI0LaII

------------------------------------------------------------------------

## 👤 Created By

**@smith.reevah**

AI-assisted development using ChatGPT, Claude, Cursor.\
Designed for investors, analysts, and crypto enthusiasts.

------------------------------------------------------------------------

## ⚠️ Disclaimer

This tool is for **educational purposes only**.\
Not financial advice. Crypto markets are highly volatile.\
Use responsibly.

------------------------------------------------------------------------
