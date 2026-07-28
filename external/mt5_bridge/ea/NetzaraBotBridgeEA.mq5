//+------------------------------------------------------------------+
//| NetzaraBotBridgeEA.mq5                                           |
//| Polls the NetzaraBot VPS bridge and executes MT5/CFD orders.      |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

#include <Trade/Trade.mqh>

input string BridgeUrl = "http://127.0.0.1:8765/signal";
input string ControlUrl = "http://127.0.0.1:8765/control.txt";
input bool EnableLiveTrading = false;
input double FixedLot = 0.01;
input int PollSeconds = 15;
input int MagicNumber = 7302026;
input int MaxSpreadPoints = 250;
input bool OnePositionPerSymbol = true;
input bool UseSignalStops = true;
input bool EmergencyStopClosesPositions = true;

CTrade trade;
datetime lastPoll = 0;
string lastSignalId = "";
bool remoteTradingEnabled = false;
bool remoteEmergencyStop = false;
double remoteMaxLot = 0.01;
string remoteLotMode = "fixed";
double remoteFixedLot = 0.01;
double remoteMinLot = 0.01;
double remoteRiskPercent = 0.5;
string remoteStopMode = "signal";
double remoteOverrideSLPoints = 0.0;
double remoteOverrideTPPoints = 0.0;
bool remoteBreakevenEnabled = false;
double remoteBreakevenTriggerPoints = 0.0;
double remoteBreakevenOffsetPoints = 0.0;
bool remoteTrailingEnabled = false;
double remoteTrailingStartPoints = 0.0;
double remoteTrailingDistancePoints = 0.0;
double remoteCloseAfterMinutes = 0.0;

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

double PointValue(string symbol)
{
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(point <= 0.0)
      point = _Point;
   return point;
}

double NormalizeVolume(string symbol, double volume)
{
   double minVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxVolume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(minVolume <= 0.0)
      minVolume = 0.01;
   if(step <= 0.0)
      step = 0.01;
   double hardMax = remoteMaxLot > 0.0 ? remoteMaxLot : maxVolume;
   if(maxVolume > 0.0)
      hardMax = MathMin(hardMax, maxVolume);
   if(remoteMinLot > 0.0)
      minVolume = MathMax(minVolume, remoteMinLot);
   volume = MathMin(volume, hardMax);
   if(volume < minVolume)
      return 0.0;
   volume = MathFloor(volume / step) * step;
   volume = MathMax(volume, minVolume);
   volume = MathMin(volume, hardMax);
   return NormalizeDouble(volume, 2);
}

double LotFromRisk(string symbol, double entryPrice, double stopLoss)
{
   if(remoteRiskPercent <= 0.0 || stopLoss <= 0.0 || entryPrice <= 0.0)
      return 0.0;
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0)
      return 0.0;
   double distance = MathAbs(entryPrice - stopLoss);
   if(distance <= 0.0)
      return 0.0;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney = equity * remoteRiskPercent / 100.0;
   double riskPerLot = (distance / tickSize) * tickValue;
   if(riskMoney <= 0.0 || riskPerLot <= 0.0)
      return 0.0;
   return riskMoney / riskPerLot;
}

double CalculateAllowedLot(string symbol, double entryPrice, double stopLoss, double signalLot, double signalMaxLot)
{
   double requestedLot = remoteFixedLot > 0.0 ? remoteFixedLot : FixedLot;
   if(remoteLotMode == "signal_quantity" && signalLot > 0.0)
      requestedLot = signalLot;
   else if(remoteLotMode == "risk_percent")
   {
      double riskLot = LotFromRisk(symbol, entryPrice, stopLoss);
      if(riskLot > 0.0)
         requestedLot = riskLot;
   }

   double cappedLot = requestedLot;
   if(signalMaxLot > 0.0)
      cappedLot = MathMin(cappedLot, signalMaxLot);
   if(remoteMaxLot > 0.0)
      cappedLot = MathMin(cappedLot, remoteMaxLot);
   return NormalizeVolume(symbol, cappedLot);
}

bool ImprovesStop(long type, double currentSL, double nextSL)
{
   if(nextSL <= 0.0)
      return false;
   if(currentSL <= 0.0)
      return true;
   if(type == POSITION_TYPE_BUY)
      return nextSL > currentSL;
   return nextSL < currentSL;
}

void CloseBridgePositions(string reason)
{
   trade.SetExpertMagicNumber(MagicNumber);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      string symbol = PositionGetString(POSITION_SYMBOL);
      if(trade.PositionClose(symbol))
         Print("Closed NetzaraBot position on ", symbol, ": ", reason);
      else
         Print("Failed closing NetzaraBot position on ", symbol, ". Retcode: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   }
}

void ManageOpenPositions()
{
   trade.SetExpertMagicNumber(MagicNumber);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      long type = PositionGetInteger(POSITION_TYPE);
      datetime openedAt = (datetime)PositionGetInteger(POSITION_TIME);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      double point = PointValue(symbol);
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double profitPoints = type == POSITION_TYPE_BUY ? (bid - openPrice) / point : (openPrice - ask) / point;

      if(remoteCloseAfterMinutes > 0.0 && (TimeCurrent() - openedAt) >= remoteCloseAfterMinutes * 60.0)
      {
         if(trade.PositionClose(symbol))
            Print("Closed NetzaraBot position after time limit: ", symbol);
         else
            Print("Time-limit close failed on ", symbol, ". Retcode: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
         continue;
      }

      double nextSL = currentSL;
      if(remoteBreakevenEnabled && remoteBreakevenTriggerPoints > 0.0 && profitPoints >= remoteBreakevenTriggerPoints)
      {
         double breakevenSL = type == POSITION_TYPE_BUY
            ? openPrice + remoteBreakevenOffsetPoints * point
            : openPrice - remoteBreakevenOffsetPoints * point;
         if(ImprovesStop(type, nextSL, breakevenSL))
            nextSL = breakevenSL;
      }

      if(remoteTrailingEnabled && remoteTrailingStartPoints > 0.0 && remoteTrailingDistancePoints > 0.0 && profitPoints >= remoteTrailingStartPoints)
      {
         double trailingSL = type == POSITION_TYPE_BUY
            ? bid - remoteTrailingDistancePoints * point
            : ask + remoteTrailingDistancePoints * point;
         if(ImprovesStop(type, nextSL, trailingSL))
            nextSL = trailingSL;
      }

      if(nextSL != currentSL && nextSL > 0.0)
      {
         if(trade.PositionModify(symbol, nextSL, currentTP))
            Print("Updated NetzaraBot stop on ", symbol, " to ", DoubleToString(nextSL, _Digits));
         else
            Print("Stop update failed on ", symbol, ". Retcode: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
      }
   }
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

bool FetchControl()
{
   char data[];
   char result[];
   string headers = "";
   string resultHeaders = "";
   ResetLastError();
   int status = WebRequest("GET", ControlUrl, headers, 8000, data, result, resultHeaders);
   if(status == -1)
   {
      Print("Control WebRequest failed. Add bridge URL in MT5 Tools > Options > Expert Advisors. Error: ", GetLastError());
      remoteTradingEnabled = false;
      return false;
   }
   string body = CharArrayToString(result, 0, -1, CP_UTF8);
   if(status < 200 || status >= 300)
   {
      Print("Control endpoint returned HTTP ", status, ": ", body);
      remoteTradingEnabled = false;
      return false;
   }
   string parts[];
   if(!SplitSignal(body, parts) || parts[0] != "CONTROL" || ArraySize(parts) < 5)
   {
      Print("Invalid control response: ", body);
      remoteTradingEnabled = false;
      return false;
   }
   remoteTradingEnabled = parts[1] == "true";
   remoteEmergencyStop = parts[2] == "true";
   remoteMaxLot = StringToDouble(parts[4]);
   if(remoteMaxLot <= 0.0)
      remoteMaxLot = 0.0;
   if(ArraySize(parts) >= 17)
   {
      remoteStopMode = parts[7];
      remoteOverrideSLPoints = StringToDouble(parts[8]);
      remoteOverrideTPPoints = StringToDouble(parts[9]);
      remoteBreakevenEnabled = parts[10] == "true";
      remoteBreakevenTriggerPoints = StringToDouble(parts[11]);
      remoteBreakevenOffsetPoints = StringToDouble(parts[12]);
      remoteTrailingEnabled = parts[13] == "true";
      remoteTrailingStartPoints = StringToDouble(parts[14]);
      remoteTrailingDistancePoints = StringToDouble(parts[15]);
      remoteCloseAfterMinutes = StringToDouble(parts[16]);
   }
   if(ArraySize(parts) >= 21)
   {
      remoteLotMode = parts[17];
      remoteFixedLot = StringToDouble(parts[18]);
      remoteMinLot = StringToDouble(parts[19]);
      remoteRiskPercent = StringToDouble(parts[20]);
   }
   return true;
}

void ApplyRemoteStops(string symbol, string side, double entryPrice, double &stopLoss, double &takeProfit)
{
   if(!UseSignalStops)
   {
      stopLoss = 0.0;
      takeProfit = 0.0;
      return;
   }
   if(remoteStopMode == "none")
   {
      stopLoss = 0.0;
      takeProfit = 0.0;
      return;
   }
   if(remoteStopMode != "override_points")
      return;

   double point = PointValue(symbol);
   if(side == "buy")
   {
      stopLoss = remoteOverrideSLPoints > 0.0 ? entryPrice - remoteOverrideSLPoints * point : 0.0;
      takeProfit = remoteOverrideTPPoints > 0.0 ? entryPrice + remoteOverrideTPPoints * point : 0.0;
   }
   else if(side == "sell")
   {
      stopLoss = remoteOverrideSLPoints > 0.0 ? entryPrice + remoteOverrideSLPoints * point : 0.0;
      takeProfit = remoteOverrideTPPoints > 0.0 ? entryPrice - remoteOverrideTPPoints * point : 0.0;
   }
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
   double signalMaxLot = ArraySize(parts) >= 11 ? StringToDouble(parts[10]) : remoteMaxLot;
   double signalLot = ArraySize(parts) >= 12 ? StringToDouble(parts[11]) : 0.0;

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
   if(!remoteTradingEnabled)
   {
      Print("Phone/VPS control says trading is stopped. Signal skipped: ", signalId);
      return;
   }
   if(remoteEmergencyStop)
   {
      Print("Emergency stop is active. Signal skipped: ", signalId);
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
      ApplyRemoteStops(symbol, side, ask, stopLoss, takeProfit);
      double allowedLot = CalculateAllowedLot(symbol, ask, stopLoss, signalLot, signalMaxLot);
      if(allowedLot <= 0.0)
      {
         Print("Allowed lot is zero after flexible lot sizing. Signal skipped: ", signalId);
         return;
      }
      ok = trade.Buy(allowedLot, symbol, ask, stopLoss, takeProfit, "NetzaraBot " + signalId);
   }
   else if(side == "sell")
   {
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      ApplyRemoteStops(symbol, side, bid, stopLoss, takeProfit);
      double allowedLot = CalculateAllowedLot(symbol, bid, stopLoss, signalLot, signalMaxLot);
      if(allowedLot <= 0.0)
      {
         Print("Allowed lot is zero after flexible lot sizing. Signal skipped: ", signalId);
         return;
      }
      ok = trade.Sell(allowedLot, symbol, bid, stopLoss, takeProfit, "NetzaraBot " + signalId);
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

   FetchControl();
   if(remoteEmergencyStop)
   {
      if(EmergencyStopClosesPositions)
         CloseBridgePositions("emergency stop");
      return;
   }

   ManageOpenPositions();

   if(!remoteTradingEnabled)
      return;

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
