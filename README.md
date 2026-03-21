
# For running bot:
1. source .venv/bin/activate && USE_WEBSOCKET=true USE_API=true NUM_CANDLES=3 WS_TIMEOUT=900 python -u main.py 2>&1

# For running dashboard:
1. pip install -e .
2. streamlit run dashboard.py