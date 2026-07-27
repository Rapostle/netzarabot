//+------------------------------------------------------------------+
//| Live Candidate Signal Bridge EA                                  |
//| Reads live_candidate_signals.csv from MQL5/Files.                |
//| Default mode is signals-only; live order execution is OFF.        |
//+------------------------------------------------------------------+
#property strict

#include <Trade/Trade.mqh>

input bool   EnableLiveTrading = false;
input string SignalFileName = "live_candidate_signals.csv";
input string SymbolOverride = "";
input double LotSize = 0.10;
input long   MagicNumber = 27072026;
input int    MaxSpreadPoints = 500;
input int    TimerSeconds = 10;

CTrade trade;
string lastSignalKey = "";

struct BotSignal
{
   string timestamp;
   string symbol;
   string timeframe;
   string side;
   string rule_id;
   double entry;
   double stop_loss;
   double take_profit;
   double confidence;
   string mode;
   string status;
   string reason;
};

int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   EventSetTimer(TimerSeconds);
   Print("Live Candidate Signal Bridge loaded. Live trading enabled: ", EnableLiveTrading);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   BotSignal signal;
   if(!ReadLatestSignal(signal))
      return;

   string targetSymbol = SymbolOverride == "" ? signal.symbol : SymbolOverride;
   string signalKey = signal.timestamp + "|" + signal.symbol + "|" + signal.side + "|" + signal.status;
   if(signalKey == lastSignalKey)
      return;

   lastSignalKey = signalKey;
   Print("Candidate signal: ", signal.symbol, " ", signal.timeframe, " ", signal.status, " ", signal.side, " ", signal.reason);

   if(signal.status != "active_signal")
      return;

   if(signal.side != "buy" && signal.side != "sell")
      return;

   if(targetSymbol != _Symbol)
   {
      Print("Signal symbol ", targetSymbol, " does not match chart symbol ", _Symbol);
      return;
   }

   if(HasOpenPosition(targetSymbol))
   {
      Print("Existing candidate position found for ", targetSymbol, ". Skipping duplicate.");
      return;
   }

   if(!SpreadOk(targetSymbol))
   {
      Print("Spread is too high for ", targetSymbol, ". Skipping.");
      return;
   }

   if(!EnableLiveTrading)
   {
      Print("LIVE TRADING OFF. Signal only: ", signal.side, " ", targetSymbol);
      return;
   }

   PlaceTrade(signal, targetSymbol);
}

bool ReadLatestSignal(BotSignal &signal)
{
   int handle = FileOpen(SignalFileName, FILE_READ | FILE_CSV | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      Print("Could not open signal file in MQL5/Files: ", SignalFileName);
      return false;
   }

   if(FileIsEnding(handle))
   {
      FileClose(handle);
      return false;
   }

   for(int i = 0; i < 12 && !FileIsEnding(handle); i++)
      FileReadString(handle);

   while(!FileIsEnding(handle))
   {
      signal.timestamp = FileReadString(handle);
      signal.symbol = FileReadString(handle);
      signal.timeframe = FileReadString(handle);
      signal.side = FileReadString(handle);
      signal.rule_id = FileReadString(handle);
      signal.entry = StringToDouble(FileReadString(handle));
      signal.stop_loss = StringToDouble(FileReadString(handle));
      signal.take_profit = StringToDouble(FileReadString(handle));
      signal.confidence = StringToDouble(FileReadString(handle));
      signal.mode = FileReadString(handle);
      signal.status = FileReadString(handle);
      signal.reason = FileReadString(handle);
   }

   FileClose(handle);
   return signal.symbol != "";
}

bool HasOpenPosition(string symbol)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == symbol && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         return true;
   }
   return false;
}

bool SpreadOk(string symbol)
{
   long spread = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   return spread <= MaxSpreadPoints;
}

void PlaceTrade(BotSignal &signal, string symbol)
{
   bool ok = false;
   if(signal.side == "buy")
      ok = trade.Buy(LotSize, symbol, 0.0, signal.stop_loss, signal.take_profit, signal.rule_id);
   else if(signal.side == "sell")
      ok = trade.Sell(LotSize, symbol, 0.0, signal.stop_loss, signal.take_profit, signal.rule_id);

   if(ok)
      Print("Candidate live order placed for ", symbol);
   else
      Print("Candidate order failed. Retcode: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
}
