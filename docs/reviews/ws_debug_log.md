# WS Debug Log (DRAFT)

Status: Draft – do not treat as approved.

## What we’ve tried (chronological)

1) Added WS logging on tech, commissioning, diagnostics pages (client) and WS endpoints (server).  
2) Added test(s) to enforce WS log markers in generated HTML/JS and server endpoints.  
3) Confirmed WS broker is shared via broker_id logs.  
4) Added broker subscribe/publish/unsubscribe logging (counts + broker id).  
5) Removed SSE endpoint and moved broker into WS-only module (`ws_broker.py`).  
6) Added client-side normalize logging in commissioning UI to inspect event fields.  
7) Added tech-side logging for expected targetKey vs received targetKey (row-miss).  

## Observations (evidence)

1) Server receives `test_result.submit` and publishes `test_result` with the correct projectId and targetKey.  
2) Broker logs show subscribers exist at publish time (subs >= 2).  
3) Server logs show `[commissioning-ws] send type=test_result` at least intermittently.  
4) Commissioning Network → WS Messages sometimes shows only `keepalive`, even when server sent `test_result`.  
5) Commissioning console shows `recv test_result` on diagnostics WS but Live Status does not update.  
6) Tech console shows `expect` + `send` but sometimes no `recv`, leaving “Saving…” stuck.  
