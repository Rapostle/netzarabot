//+------------------------------------------------------------------+
//| NetzaraBotBridgeEA.mq5                                           |
//| Polls the NetzaraBot VPS bridge and executes MT5/CFD orders.      |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

#include <Trade/Trade.mqh>

input string BridgeUrl = "http://127.0.0.1:8765/signal";
input bool EnableLiveTrading = false;
input double FixedLot = 0.01;
input int PollSeconds = 15;
input int MagicNumber = 7302026;
input int MaxSpreadPoints = 250;
input bool OnePositionPerSymbol = true;
input bool UseSignalStops = true;

CTrade trade;
datetime lastPoll = 0;
string lastSignalId = "";

string Trim(string value)
{
   StringTrimLeft(value);
   StringTrimRight(value);
   return value;
}

bool SplitSignal(string body, string &parts[])
{
   StringReplace(body, "\r", "");
   StringReplace(body, "\n", "");
   int count = StringSplit(body, '|', parts);
   return count >= 2;
}

bool HasOpenPosition(string symbol)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == symbol &&
            PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         {
            return true;
         }
      }
   }
   return false;
}

bool SpreadOk(string symbol)
{
   long spread = 0;
   if(!SymbolInfoInteger(symbol, SYMBOL_SPREAD, spread))
      return false;
   return spread <= MaxSpreadPoints;
}

string BuildUrl()
{
   string symbol = Symbol();
   string separator = StringFind(BridgeUrl, "?") >= 0 ? "&" : "?";
   return BridgeUrl + separator + "symbol=" + symbol;
}

bool FetchSignal(string &body)
{
   char data[];
   char result[];
   string headers = "";
   string resultHeaders = "";
   ResetLastError();
   int status = WebRequest("GET", BuildUrl(), headers, 8000, data, result, resultHeaders);
   if(status == -1)
   {
      Print("WebRequest failed. Add bridge URL in MT5 Tools > Options > Expert Advisors. Error: ", GetLastError());
      return false;
   }
   body = CharArrayToString(result, 0, -1, CP_UTF8);
   if(status < 200 || status >= 300)
   {
      Print("Bridge returned HTTP ", status, ": ", body);
      return false;
   }
   return true;
}

void ExecuteSignal(string &parts[])
{
   if(parts[0] != "SIGNAL")
      return;

   string signalId = parts[1];
   string symbol = parts[2];
   string side = parts[3];
   double stopLoss = StringToDouble(parts[5]);
   double takeProfit = StringToDouble(parts[6]);

   if(signalId == lastSignalId || GlobalVariableCheck("NetzaraBot_" + signalId))
      return;
   if(symbol != Symbol())
   {
      Print("Signal is for ", symbol, " but EA is attached to ", Symbol());
      return;
   }
   if(!EnableLiveTrading)
   {
      Print("Live trading disabled. Signal received but not executed: ", signalId);
      lastSignalId = signalId;
      return;
   }
   if(OnePositionPerSymbol && HasOpenPosition(symbol))
   {
      Print("Position already open for ", symbol, ". Signal skipped: ", signalId);
      lastSignalId = signalId;
      return;
   }
   if(!SpreadOk(symbol))
   {
      Print("Spread too high. Signal skipped: ", signalId);
      return;
   }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(30);

   bool ok = false;
   if(side == "buy")
   {
      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      ok = trade.Buy(FixedLot, symbol, ask, UseSignalStops ? stopLoss : 0.0, UseSignalStops ? takeProfit : 0.0, "NetzaraBot " + signalId);
   }
   else if(side == "sell")
   {
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      ok = trade.Sell(FixedLot, symbol, bid, UseSignalStops ? stopLoss : 0.0, UseSignalStops ? takeProfit : 0.0, "NetzaraBot " + signalId);
   }

   if(ok)
   {
      GlobalVariableSet("NetzaraBot_" + signalId, TimeCurrent());
      lastSignalId = signalId;
      Print("NetzaraBot trade placed: ", signalId);
   }
   else
   {
      Print("Trade failed for signal ", signalId, ". Retcode: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   }
}

int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   Print("NetzaraBotBridgeEA loaded. EnableLiveTrading=", EnableLiveTrading, ", BridgeUrl=", BridgeUrl);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(TimeCurrent() - lastPoll < PollSeconds)
      return;
   lastPoll = TimeCurrent();

   string body = "";
   if(!FetchSignal(body))
      return;

   string parts[];
   if(!SplitSignal(body, parts))
      return;

   if(parts[0] == "NO_SIGNAL")
   {
      Print("No fresh NetzaraBot signal: ", parts[1]);
      return;
   }
   ExecuteSignal(parts);
}
