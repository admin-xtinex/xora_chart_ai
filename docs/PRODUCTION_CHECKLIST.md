# XORA Production Completion Checklist

Updated: 2026-08-27

This checklist is the source of truth for the current production stabilization work. Items are marked complete only after verification in production or CI.

## Infrastructure and access

- [x] Public DNS points `xora.xtinex.com` at the production VM.
- [x] HTTPS certificate installed and HTTPS confirmed working.
- [x] GCP automation service account `xora-automation@xtinex-trading.iam.gserviceaccount.com` created.
- [x] Automation account granted Compute Instance Admin, Compute Network Admin, and Service Account User roles.
- [x] Automation service account attached to `xora-chart-ai` with `cloud-platform` scope.
- [x] Self-hosted GitHub Actions runner is active on the production VM.
- [ ] Make production deployment idempotent after runner file-mode changes.
- [ ] Make production frontend verification HTTPS-aware.

## Market-data runtime

- [x] Market-data architecture remains Binance Futures WebSocket-only; no REST market-data fallback.
- [x] Individual ticker bootstrap streams implemented.
- [x] Closed-candle history separated from live/in-progress candles.
- [x] CI health rejects `ws_tickers=0` instead of reporting a false healthy deployment.
- [x] Direct `!ticker@arr`, BTC ticker, BTC kline, and BTC mark stream probes executed in `us-central1`; all timed out waiting for payloads.
- [ ] Test Binance Futures `/ws` + `SUBSCRIBE` mode from current `us-central1` VM.
- [ ] If current region remains unusable, probe another Always Free eligible GCP region without leaving a paid resource running.
- [ ] Select viable Always Free production region.

## Application functionality

- [ ] Binance ticker count is greater than zero in production health.
- [ ] At least one symbol accumulates the minimum closed-candle history.
- [ ] `cycle.run` discovers symbols and completes without market-data readiness errors.
- [ ] Opportunities populate in the WebSocket API and frontend.
- [ ] Manual coin analysis works for supported symbols.
- [ ] Symbol normalization works for inputs such as `BTC` and `ETHUSDT`.
- [ ] Reference-chart verification remains mandatory.
- [ ] Manual demo trade is available only for `APPROVE` + verified reference match + valid entry.
- [ ] Auto demo trading obeys the same approval/reference gates.

## Frontend/product

- [x] XORA by XTINEX product redesign committed.
- [x] Live market readiness counters surfaced in the application shell.
- [x] Manual trade button gating tightened in the UI.
- [ ] Warm-up/readiness state verified against live backend behavior.
- [ ] Scan error/output messaging verified in production.
- [ ] Coin-analysis error/output messaging verified in production.
- [ ] Responsive/mobile behavior verified after runtime data is restored.

## Final production acceptance

- [ ] HTTPS serves the production UI after a fresh automated deploy.
- [ ] Browser WebSocket connects over `wss://xora.xtinex.com/ws`.
- [ ] Production health reports live Binance market data.
- [ ] Scan produces real output.
- [ ] Coin analysis produces a real analysis after candle readiness.
- [ ] Opportunities render and refresh automatically.
- [ ] Demo position workflow verified end-to-end.
- [ ] CI tests and production deployment both green.
