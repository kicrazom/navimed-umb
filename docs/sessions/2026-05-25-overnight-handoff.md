# Overnight Run-3 handoff — 2026-05-25 morning

**Orchestrator finished:** 2026-05-24 23:30:57
**Walltime od startu:** 1386s

## Status

- **12B-chat-2512_quant**: FAIL (3s)
- **8B-chat-2512_quant**: OK (1294s)
- **8B-chat-2512_sanity**: 5/5 (raw: /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/environment/sanity-tests/2026-05-25-Llama-PLLuM-8B-chat-2512-awq-sanity.json)

## Errors

- 12B-chat-2512 quant fail (log: /home/mozarcik/models/_run3_logs/12B-chat-2512_quant.log)

## TODO jutro (Łukasz)

**ERRORS DETECTED — investigation needed:**

1. **Read orchestrator log w pierwszej kolejności:**
   - `$LOG` (full chronologia)

2. **Per error decide retry vs debug:**
   - quant fail → przeczytaj `~/models/_run3_logs/<SIZE>_quant.log` — szukaj OOM, missing layers, gemma3-style mappings
   - sanity weak (<3/5) → przeczytaj raw outputs JSON + decide czy retry quant z `targets="Linear", ignore=["lm_head"]`
   - sentinel timeout → download wciąż w toku albo network completely dead, sprawdź watchdog log

3. **Nie publikuj nic na HF** dopóki Gate 2 PASS dla wszystkich modeli.

4. **Memory updates:** jeśli to nowy failure mode, dopisz do `~/.claude/projects/...../memory/`

## Files do nawigacji jutro

- Logbook: `/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/logbook/2026-05-25.md`
- Orchestrator log: `/home/mozarcik/models/_run3_logs/overnight_20260524_2307.log`
- AWQ outputs (jeśli OK):
  - `~/models/Llama-PLLuM-8B-chat-2512-awq/`
  - `~/models/PLLuM-12B-chat-2512-awq/`
- Sanity raw: `environment/sanity-tests/2026-05-25-*-sanity.json`

## Context — co się działo wczoraj (2026-05-24)

- AQLM pre-flight FAIL (ROCm incompatible, saved $50 na MI300X) — task #30
- 4B-chat-2512 = multimodal Gemma3, deferred (memory project_pllum_4b_multimodal)
- Run-3 download stabilizowany po debugowaniu (Xet off + hf_transfer on + IPv4 forced)
- Skill **hf-download-watchdog** utworzony i commitnięty (`923dbba`)
- Graphify pracował w innej sesji Claude — sprawdź `graphify-out/` rano

---

## Update — retry 12B po fix protobuf+sentencepiece + redownload

**Finish run zakończony:** 2026-05-25 13:29:22

### Wyniki 12B

- **12B quant**: SKIPPED (sentinel timeout)
- **12B sanity**: SKIPPED (no AWQ)


### Errors

- sentinel-timeout-21601s


### Co teraz (Łukasz wraca z pracy)

**12B WCIĄŻ MA PROBLEMY** — przeczytaj log:
`/home/mozarcik/models/_run3_logs/finish_12b_20260525_0729.log`
Decide: retry quant z poprawkami, czy publikuj tylko 8B (jest gotowy).
