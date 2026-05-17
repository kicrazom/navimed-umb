---
type: project
status: active
domain: [pulmonologia, CDSS, ML-infrastructure]
code_path: ~/code/navimed-umb
github: https://github.com/kicrazom/navimed-umb
models_used: [Bielik-11b, Qwen2.5-72b-awq, Qwen3.6-27b]
related_projects:
  - "[[10_Projekty/0002-Broncho-Nome/Broncho-Nome_index|Broncho-Nome]]"
  - "[[10_Projekty/0003-Capno-Nome/Capno-Nome_index|Capno-Nome]]"
  - "[[10_Projekty/0004-ego_architecture_ai/ego_architecture_ai_index|ego_architecture_ai]]"
papers:
  - "[[30_Badania/DWM/README|DWM]]"
tags: [project/active, domain/clinical, domain/ml-infra]
claude_import: "[[Claude/projects/navimed-umb/navimed-umb]]"
claude_memory: "[[Claude/projects/navimed-umb/navimed-umb-memory]]"
---

# NaviMed-UMB

Główny system CDSS dla Uniwersytetu Medycznego w Białymstoku — łączy moduły kliniczne pulmonologii z infrastrukturą ML/inference.

## Powiązania
- Bazuje na architekturze [[10_Projekty/0004-ego_architecture_ai/ego_architecture_ai_index|ego_architecture_ai]]
- Korzysta z modułów [[10_Projekty/0002-Broncho-Nome/Broncho-Nome_index|Broncho-Nome]] (bronchoskopia) i [[10_Projekty/0003-Capno-Nome/Capno-Nome_index|Capno-Nome]] (kapnografia)
- Modele: lokalne (Bielik, Qwen) na `~/models/`
- Benchmarki: `~/code/navimed-umb/benchmarks/`

## Kod
- Lokalnie: `~/code/navimed-umb/`
- Branch aktywny (2026-05-16): `wip/layout-unification-2026-05-04` (100 niezatwierdzonych zmian — do commitu)
- GitHub: https://github.com/kicrazom/navimed-umb

## Aktualny stan
- ✅ Phase 2 sweep fp16-tp2-max8192 (N={10..1000}) — ostatni commit `3d28946`
- 🔄 Layout unification — w toku
- 📊 Benchmarki: hardware envelope + thermal runs

## Otwarte pytania
- [ ] Commit dirty changes na branchu wip/layout-unification
