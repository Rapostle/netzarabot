"""Makes the paper rules judge finished candles only. Exact-match edits: stops if main.py is not as expected."""
import sys
from pathlib import Path
p = Path(sys.argv[1] if len(sys.argv) > 1 else "external/trading_bot/trading_bot/cli/main.py")
s = p.read_text()
if "def completed_candles(" in s:
    print("ALREADY APPLIED"); raise SystemExit(0)
old = '''        df = add_indicators(load_ohlcv_csv(path)).tail(args.max_rows).reset_index(drop=True)
        if df.empty:'''
new = '''        df = completed_candles(load_ohlcv_csv(path), timeframe_seconds(timeframe))
        df = add_indicators(df).tail(args.max_rows).reset_index(drop=True) if not df.empty else df
        if df.empty:'''
anchor = "def run_paper_stable_rules("
helper = '''def completed_candles(df: pd.DataFrame, seconds: int, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Drops the candle that is still forming (Deriv's newest candle is the one in progress).
    The rules were found on finished candles, so they must be judged on finished candles.
    Set PAPER_USE_PARTIAL_CANDLE=1 to get the old behaviour back."""
    if df.empty or os.environ.get("PAPER_USE_PARTIAL_CANDLE") == "1":
        return df
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    closed = df["timestamp"] + pd.Timedelta(seconds=seconds) <= now
    return df[closed].reset_index(drop=True)


'''
for text, name in ((old, "decision line"), (anchor, "function anchor")):
    if s.count(text) != 1:
        print(f"STOP: {name} found {s.count(text)} times. Nothing changed."); raise SystemExit(1)
for needle in ("import os", "def timeframe_seconds("):
    if needle not in s:
        print(f"STOP: main.py has no '{needle}'. Nothing changed."); raise SystemExit(1)
Path(str(p) + ".bak_before_closed_candles").write_text(s)
s = s.replace(old, new).replace(anchor, helper + anchor, 1)
p.write_text(s)
print("APPLIED closed-candle rule. Backup:", str(p) + ".bak_before_closed_candles")
