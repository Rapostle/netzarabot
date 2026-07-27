# Rule Kill-Switch Report

Last updated UTC: 2026-07-27T20:47:46.694294+00:00

This recommends which paper rules should be frozen or killed. The matching blocklist is used by paper monitoring.

Strict mode is active: paper rules below 70% win rate, net-negative rules, and rules with weak stop-loss patterns are blocked from new entries.

| track | rule | action | trades | wins | losses | win_rate | stop_losses | pnl | avg | why |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Original stable rules | SR010 | KILL NOW | 6 | 0 | 6 | 0.0% | 4 | -130.87 | -21.81 | Strict accuracy gate: enough paper evidence and rule is hurting quality. |
| Experimental pair candidates | PAIR019 | KILL NOW | 3 | 2 | 1 | 66.7% | 1 | -13.12 | -4.37 | Strict accuracy gate: enough paper evidence and rule is hurting quality. |
| Advanced sniper candidates | PAIR019 | KILL NOW | 3 | 2 | 1 | 66.7% | 1 | -12.18 | -4.06 | Strict accuracy gate: enough paper evidence and rule is hurting quality. |
| Experimental pair candidates | PAIR001 | FREEZE | 2 | 0 | 2 | 0.0% | 0 | -12.95 | -6.48 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Original stable rules | SR017 | FREEZE | 2 | 1 | 1 | 50.0% | 1 | -0.73 | -0.37 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Experimental pair candidates | PAIR024 | FREEZE | 2 | 1 | 1 | 50.0% | 1 | 5.36 | 2.68 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Advanced sniper candidates | PAIR001 | FREEZE | 2 | 1 | 1 | 50.0% | 1 | 5.40 | 2.70 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Experimental pair candidates | PAIR005 | FREEZE | 3 | 2 | 1 | 66.7% | 1 | 5.51 | 1.84 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Advanced sniper candidates | PAIR023 | FREEZE | 2 | 1 | 1 | 50.0% | 1 | 5.71 | 2.86 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Advanced sniper candidates | PAIR002 | FREEZE | 3 | 2 | 1 | 66.7% | 1 | 12.50 | 4.17 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Experimental pair candidates | PAIR002 | FREEZE | 3 | 2 | 1 | 66.7% | 1 | 12.51 | 4.17 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Advanced sniper candidates | PAIR006 | FREEZE | 2 | 1 | 1 | 50.0% | 0 | 21.11 | 10.56 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Advanced sniper candidates | PAIR024 | FREEZE | 3 | 2 | 1 | 66.7% | 1 | 23.67 | 7.89 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Experimental pair candidates | PAIR023 | FREEZE | 3 | 2 | 1 | 66.7% | 1 | 41.71 | 13.90 | Strict accuracy gate: rule is below 70% paper win rate or not net-positive. |
| Experimental pair candidates | PAIR016 | WATCH | 1 | 0 | 1 | 0.0% | 1 | -30.29 | -30.29 | Recent stop loss; keep watching before allowing promotion. |
| Boom/Crash expansion candidates | BCX0021 | WATCH | 1 | 0 | 1 | 0.0% | 1 | -30.00 | -30.00 | Recent stop loss; keep watching before allowing promotion. |
| Original stable rules | SR003 | WATCH | 1 | 0 | 1 | 0.0% | 0 | -3.15 | -3.15 | Negative, but sample is still small. |
| Boom/Crash expansion candidates | BCX0048 | KEEP PAPER | 1 | 1 | 0 | 100.0% | 0 | 0.30 | 0.30 | No kill signal yet. |
| Boom/Crash expansion candidates | BCX0005 | KEEP PAPER | 1 | 1 | 0 | 100.0% | 0 | 18.61 | 18.61 | No kill signal yet. |
| Boom/Crash expansion candidates | BCX0051 | KEEP PAPER | 1 | 1 | 0 | 100.0% | 0 | 21.80 | 21.80 | No kill signal yet. |
| Experimental pair candidates | PAIR006 | KEEP PAPER | 2 | 2 | 0 | 100.0% | 0 | 61.90 | 30.95 | No kill signal yet. |
| Experimental pair candidates | PAIR017 | KEEP PAPER | 4 | 4 | 0 | 100.0% | 0 | 91.06 | 22.76 | No kill signal yet. |
| Advanced sniper candidates | PAIR017 | KEEP PAPER | 4 | 4 | 0 | 100.0% | 0 | 97.39 | 24.35 | No kill signal yet. |

Machine-readable blocklist: `/Users/ocmix/Documents/Codex/2026-07-09/continue-working-on-my-trading-bot/outputs/rule_kill_switch_blocklist.csv`
