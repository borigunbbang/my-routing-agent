# FINAL_CHECKLIST — 제출 전 최종 점검

> 과제 요구 사항을 빠짐없이 갖췄는지 제출 직전에 확인한다. 각 항목 옆에 확인한 근거(파일·수치)를 적는다.
> 단위별 세부 완료조건은 [WORK_UNITS.md](WORK_UNITS.md) 참고. 점검일: 2026-11-03

## 1. 주제 조건

- [x] 카테고리가 3~5개이고(범위 밖 제외), 카테고리마다 답하는 내용이 실제로 다르다 — 4개, 조항 겹침 없음 (REPORT 2절)
- [x] 카테고리별로 나눠 넣을 만큼 충분한 근거 문서가 `docs/`에 있다 — 22조항 (BKG 5 · REF 6 · STY 5 · DSP 6)
- [x] 문서에 근거가 없는데 그럴듯하게 답할 수 있는 질문이 평가셋에 있다 — E04 · E08 · E12 · E16

## 2. 카테고리와 문서 연결

- [x] 카테고리 3~5개 + 어디에도 속하지 않는 "범위 밖" 카테고리 1개
- [x] 왜 그렇게 나눴는지 설명이 REPORT에 있다 — REPORT 2절 "나눈 근거", "경계 규칙"
- [x] 카테고리 ↔ 문서 조항 매핑표가 있고, 코드(`context.py`)가 그 매핑을 그대로 쓴다 — `PREFIX_CATEGORY` · `CATEGORY_TOOL` · `EXTRA_MAP`
- [x] 연결할 조항이 없는 카테고리가 없다 — `python context.py` 출력

## 3. 평가셋

- [x] 평가용 문의 10건 이상 (계획: 20건) — 20건
- [x] 카테고리별 개수가 비슷하다 — 카테고리별 4건
- [x] 문항마다 기대 도구 · 반드시 담아야 할 사실 · 말하면 안 되는 것이 있다 — `expected_tools` · `must_include` · `must_not`
- [x] 문서에 답이 없어 넘기는 것이 정답인 문항이 섞여 있다 — 8건 (범위 밖 4 + 문서에 없음 4)
- [x] "말하면 안 되는 것"에 문서를 안 읽었을 때 나오기 쉬운 그럴듯한 오답이 들어 있다 — REPORT 3절 표
- [x] 프롬프트 예시용과 평가용이 분리돼 있고, 겹치는 문항이 없다 — `split` 필드, 프롬프트 속 평가 문항 0건

## 4. 파이프라인

- [x] 판정 → 근거 조립 → 답변 → 검증이 하나의 LangGraph 흐름으로 이어진다 — `agent.py` `build()`
- [x] 문서 전체가 아니라 카테고리별로 필요한 조항만 프롬프트에 들어간다 — `assemble_context()`, 데모 ② 패널
- [x] 카테고리를 고르는 일(`classify`)과 넘길지 판단(`gate`)이 분리돼 있다
- [x] 문서에 없는 내용이 답변에 섞였는지 **코드로** 검사한다 (`verify.py`) — `python verify.py` 통과
- [x] 모르겠으면 넘기는 경로(handoff)가 동작한다 — 넘기기 문항 재현율 1.00 (32/32)

## 5. 측정

- [x] 도구 호출 적절성 수치 (호출 도구 집합 == 기대 도구 집합) — 기준 0.95 → 최종 평균 0.950
- [x] 답변 적절성 수치 (필수 사실 전부 포함 + 금지 표현 0건) — 기준 0.80 → 최종 평균 0.938
- [x] 채점 지침에 "표현이 아니라 사실을 보라"가 명시돼 있다 — `prompts.GRADER_SYSTEM`
- [x] 모범 답안으로 채점기 자체를 검증한 결과가 있다 — 모범 20/20, 틀린 답 7/7 (`results/grader_validation.json`)
- [x] 틀린 건을 직접 읽고 원인(어느 근거를 잘못 골랐는지, 어떤 사실을 빠뜨렸는지)을 적었다 — `results/ANALYSIS.md`, REPORT 4절
- [x] 개선은 한 번에 하나씩, 매번 재측정한 기록표가 있다 — REPORT 4절 개선 기록표

## 6. 데모

- [x] streamlit으로 사람이 직접 질문해 볼 수 있다 — `streamlit run app.py`
- [x] 답변과 함께 호출한 도구 · 근거로 쓴 조항 · 검증 결과가 보인다 — `screenshots/` 3장
- [ ] (선택) 공개 배포 — 하지 않음

## 7. 보안

- [x] API 키가 저장소 어디에도 없다 (`git log -p | grep -i "sk-"` 결과 0건) — 전체 기록 검색 0건
- [x] `.env`가 `.gitignore`에 있고 커밋되지 않았다
- [x] `.env.example`만 커밋돼 있다

## 8. 제출물·디렉토리

- [x] `docs/` · `data/goldenset.json` · `prompts.py` · `context.py` · `agent.py` · `evaluate.py` · `app.py` · `requirements.txt` · `REPORT.md` (+ `verify.py`)
- [x] 기획 문서: `PRD.md` · `TECH_SPEC.md` · `WORK_UNITS.md` · `FINAL_CHECKLIST.md`
- [x] `results/`에 측정 회차별 결과 JSON — run_01~09
- [x] 새로 clone한 폴더에서 실행 방법대로 설치·평가·데모가 동작한다 — 설치 · `verify.py` · `agent.py` 확인 (평가·데모는 원본 폴더에서 같은 코드로 확인)

## 9. REPORT.md 7개 항목

- [x] ① 주제와 근거 문서: 무엇을 골랐고 왜 골랐는지
- [x] ② 카테고리 설계: 목록, 나눈 근거, 매핑표
- [x] ③ 평가셋 설계: 건수·작성 방법, 기대 도구·필수 사실을 정한 근거, 평가용/예시용 분리 방법
- [x] ④ 측정 결과: 두 지표 수치, 틀린 건 원인 분류, 개선 시도별 기록표 — 수치 10개를 results JSON과 대조해 일치
- [x] ⑤ 파이프라인 구조도: LangGraph 노드와 State 흐름 (Mermaid), 실제 코드와 일치
- [x] ⑥ 데모 설계: 신경 쓴 부분 + 화면 캡처
- [x] ⑦ 회고: 가장 공들인 부분, 향후 개선점 (검증기 한계 포함)

## 10. 제출

- [x] 최종 커밋이 GitHub에 푸시됐다
- [x] 제출한 GitHub 주소에서 REPORT.md가 바로 보인다 — https://github.com/borigunbbang/my-routing-agent/blob/main/REPORT.md
