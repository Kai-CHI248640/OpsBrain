# Analysis

## agent_chat.py (1218 lines) — Structure Map

```
Lines 1-68     : Constants + LLM helpers (_PROVIDER_URLS, _sanitize, _fetch_ak, _build_url)
Lines 70-165   : Tool definitions (COMMANDER_TOOLS, SUBAGENT_TOOLS)
Lines 168-293  : Tool execution engine (_execute_tool_call — 125 lines, 12 tools)
Lines 296-396  : LLM service (_llm_with_tools, _llm_raw)
Lines 398-520  : Device execution (SSH/Telnet/Ping)
Lines 523-576  : Memory system (load/save memory JSON files)
Lines 579-623  : Config verification + E2E test
Lines 626-770  : Hermes Subagent loop
Lines 773-868  : System prompts (commander + subagent)
Lines 871-958  : Internal dispatch
Lines 961-1081 : API endpoints (4 routes)
Lines 1084-1218: Feishu integration
```

## Impact

- **12 responsibilities** in 1 file (God File)
- **3 bare `except:` blocks** (lines 463, 551, 564) — swallowed exceptions
- **Inline imports**: `os`, `paramiko`, `telnetlib3`, `lark_oapi`, `platform_info` scattered
- **Hardcoded localhost URL**: `http://127.0.0.1:8000` in tool execution (line 206)

## Plan

Extract 3 service modules from `agent_chat.py`:

| Batch | Module | Lines | Functions |
|-------|--------|-------|-----------|
| 1 | `services/llm_service.py` | ~100 | `_PROVIDER_URLS`, `_requires_reasoning`, `_sanitize`, `_fetch_ak`, `_build_url`, `_llm_with_tools`, `_llm_raw` |
| 2 | `services/device_executor.py` | ~125 | `_socket_check`, `_ssh_exec`, `_telnet_exec`, `_execute_on_devices`, `_run_e2e_test`, `VERIFY_COMMANDS`, `_get_verify_command` |
| 3 | `services/memory.py` | ~55 | `_get_memory_dir`, `_MEMORY_DIR`, `_MAX_CONTEXT`, `_memory_path`, `_load_memory`, `_save_memory` |

Each batch: ≤5 files, ≤300 LOC. Route file becomes thin controller.

## Files

- MODIFY: `web/backend/app/routes/agent_chat.py` — remove extracted code, import from services
- CREATE: `web/backend/app/services/__init__.py`
- CREATE: `web/backend/app/services/llm_service.py`
- CREATE: `web/backend/app/services/device_executor.py`
- CREATE: `web/backend/app/services/memory.py`

## Validation

- Build: `python -c "from app import app"`
- No API changes (same endpoints, same behavior)
- No DB schema changes

## Risk

LOW — pure extraction, no logic changes.
