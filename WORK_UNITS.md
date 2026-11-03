# WORK_UNITS — 단위 작업 명세

> [PRD.md](PRD.md)·[TECH_SPEC.md](TECH_SPEC.md)를 구현 순서대로 쪼갠 작업 목록.
> 한 번에 한 단위씩 진행하고, **완료조건을 모두 체크해야 다음 단위로 넘어간다.** 단위가 끝날 때마다 커밋한다.

## 진행 현황

| WU | 작업 | 산출물 | 상태 |
|---|---|---|---|
| 01 | 프로젝트·저장소 준비 | 폴더 구조, venv, `.gitignore`, GitHub 저장소 | ✅ |
| 02 | 근거 문서 수집·작성 | `docs/sources.md`, `docs/policy_modustay.md` | ✅ |
| 03 | 카테고리 확정·매핑표 | `context.py` (파싱·매핑·도구) | ✅ |
| 04 | 평가셋 작성 | `data/goldenset.json` | ✅ |
| 05 | 프롬프트 작성 | `prompts.py` | ✅ |
| 06 | 기계적 검증기 | `verify.py` | ✅ |
| 07 | 파이프라인 구현 | `agent.py` | ✅ |
| 08 | 채점기 구현·검증 | `evaluate.py` (채점·검증 모드) | ✅ |
| 09 | 기준 측정·오답 분석 | `results/run_01_baseline.json`, 오답 분석 메모 | ✅ |
| 10 | 개선 반복 | `results/run_02~`, 개선 기록표 | ⬜ |
| 11 | 데모 | `app.py`, 화면 캡처 | ⬜ |
| 12 | REPORT 작성·제출 | `REPORT.md`, 최종 푸시 | ⬜ |

상태 표기: ⬜ 대기 · 🔄 진행 중 · ✅ 완료

---

## WU-01 프로젝트·저장소 준비

**할 일**
- TECH_SPEC 2절의 디렉토리 구조 생성
- `python -m venv .venv`, `requirements.txt`(langgraph, langchain-openai, pydantic, streamlit, python-dotenv) 설치
- `.env.example`(`OPENAI_API_KEY=`), `.gitignore`(`.env`, `.venv/`, `__pycache__/`, `.streamlit/secrets.toml`)
- `git init`, GitHub 저장소 생성·연결, 기획 문서 4종 첫 커밋

**완료조건**
- [x] `pip install -r requirements.txt`가 오류 없이 끝난다
- [x] `python -c "import langgraph, langchain_openai, streamlit"` 성공
- [x] `.env`에 키를 넣고 `gpt-5.6-luna`에 한 줄 호출해 응답을 받는다
- [x] `git status`에 `.env`가 나타나지 않는다
- [x] GitHub 원격에 PRD·TECH_SPEC·WORK_UNITS·FINAL_CHECKLIST가 올라가 있다

---

## WU-02 근거 문서 수집·작성

**할 일**
- 공정위 공공 문서(소비자분쟁해결기준 숙박업 등) 원문 확인, 출처·발행일을 `docs/sources.md`에 기록
- `docs/policy_modustay.md` 작성: 공정위 기준 조항 + 모두스테이 보충 조항(예약·결제, 체크인·이용규칙 등 공정위 문서에 없는 부분)
- 조항마다 `### [접두어-번호] 제목` 형식, `출처: 공정위 / 보충` 표시

**완료조건**
- [x] 4개 카테고리(BKG/REF/STY/DSP) 각각 조항이 **3개 이상** 있다
- [x] 모든 조항이 `### [XXX-00] 제목` 형식이고 ID가 중복되지 않는다
- [x] 모든 조항에 출처(공정위/보충)가 표시돼 있다
- [x] 공정위 출처 조항은 `sources.md`의 원문과 수치(비율·기간)가 일치한다
- [x] "문서에 없지만 그럴듯하게 답할 수 있는 질문"을 카테고리별로 1개 이상 떠올릴 수 있다 (메모로 남김 → WU-04에 사용)

---

## WU-03 카테고리 확정·매핑표

**할 일**
- 문서를 읽고 PRD 3절 카테고리 초안을 확정 (필요하면 재분할·문서 보강)
- `context.py`: `load_clauses()`, `PREFIX_CATEGORY`, `CATEGORY_TOOL`, 도구 함수 4개 + `handoff`
- 카테고리 ↔ 조항 매핑표를 PRD 3절(또는 REPORT 초안)에 기록

**완료조건**
- [x] `load_clauses()`가 문서의 조항 수와 같은 개수를 반환한다
- [x] 각 조항의 `id, category, title, text, source`가 비어 있지 않다
- [x] `get_refund()` 등이 해당 카테고리 조항**만** 반환한다 (다른 접두어 0건)
- [x] 연결할 조항이 0개인 카테고리가 없다
- [x] 매핑표(카테고리 | 도구 | 조항 ID 목록 | 나눈 근거)가 문서에 기록돼 있다

---

## WU-04 평가셋 작성

**할 일**
- `data/goldenset.json`: 평가용(`split: "eval"`) 20건 + 예시용(`split: "example"`) 5건
- 문항마다 `question, category, expected_tools, must_include, must_not, reference_answer, note`
- `must_not`에는 문서를 안 읽었을 때 나오기 쉬운 그럴듯한 오답을 넣는다

**완료조건**
- [x] 평가용 20건, 예시용 5건이고 질문이 서로 겹치지 않는다
- [x] 평가용의 카테고리별 개수가 3~5건 사이로 균형 잡혀 있다 (범위 밖 포함)
- [x] 넘기기가 정답인 문항이 **4건 이상** (범위 밖 `["handoff"]` + 문서에 답 없음 `["get_xxx","handoff"]` 둘 다 포함)
- [x] 모든 문항의 `must_include`·`must_not`이 비어 있지 않다
- [x] 모든 `expected_tools`가 실제 도구 이름(`get_booking` 등)만 쓴다
- [x] 각 `note`에 근거 조항 ID가 적혀 있고, 그 조항에 실제로 필수 사실이 있다
- [x] JSON 파싱 오류가 없다 (`python -c "import json; json.load(open('data/goldenset.json'))"`)

---

## WU-05 프롬프트 작성

**할 일**
- `prompts.py`: 분류 지침(카테고리 정의·경계 사례, 예시용 문항 few-shot), 게이트 지침, 답변 규칙(근거만 사용·문장마다 조항 인용·모르면 지어내지 말 것), 재생성 지침(위반 내역 삽입), 채점 지침(표현이 아니라 사실 비교)

**완료조건**
- [x] 분류 지침에 카테고리 5개의 정의와 경계 사례가 있다
- [x] 분류 지침이 "넘길지"를 판단하라고 요구하지 **않는다** (게이트와 분리)
- [x] few-shot에 `split: "example"` 문항만 쓰였다 (평가용 문항 0건)
- [x] 답변 규칙에 "모든 문장 끝에 `[조항ID]` 인용" 규칙이 있다
- [x] 채점 지침에 "표현이 아니라 사실이 같은지 판단" 문구가 있다

---

## WU-06 기계적 검증기

**할 일**
- `verify.py`: 문장 분리, 인용 추출, 미인용 문장 / 모르는 인용 / 근거 없는 숫자 검사, 숫자 정규화표

**완료조건**
- [x] 인용 없는 문장이 있으면 `uncited_sentences`에 잡힌다
- [x] context에 없는 조항 ID를 인용하면 `unknown_citations`에 잡힌다
- [x] 인용 조항에 없는 숫자(예: 근거는 `10%`, 답변은 `20%`)가 `unsupported_numbers`에 잡힌다
- [x] 정규화 사례(`10 %`↔`10%`, `1만원`↔`10,000원`)는 통과한다
- [x] 모범 답안(인용 포함) 몇 건이 `passed=True`로 나온다
- [x] 위 사례들을 확인하는 간단한 테스트 코드(또는 `if __name__ == "__main__"` 블록)가 통과한다

---

## WU-07 파이프라인 구현

**할 일**
- `agent.py`: `AgentState`, 노드 6개(`classify`, `retrieve`, `gate`, `answer`, `verify`, `handoff`), 조건부 엣지, `run(question) -> dict`

**완료조건**
- [x] TECH_SPEC 6절 그래프와 노드·엣지가 일치한다 (`graph.get_graph().draw_mermaid()` 출력으로 확인)
- [x] 범위 밖 질문 1건 → `tools_called == ["handoff"]`, 고정 문구 응답
- [x] 카테고리는 맞지만 문서에 답 없는 질문 1건 → `["get_xxx", "handoff"]`
- [x] 정상 질문 1건 → 해당 도구만 호출, 인용 포함 답변, `verification.passed=True`
- [x] 검증 실패 시 재생성은 최대 1회이고, 이후 handoff로 간다 (일부러 실패를 유도해 확인)
- [x] 프롬프트에 들어간 근거가 판정 카테고리의 조항뿐이다 (로그로 확인)
- [x] `run()` 반환값에 `categories, tools_called, context, answerable, answer, verification, handoff`가 모두 있다

---

## WU-08 채점기 구현·검증

**할 일**
- `evaluate.py`: 도구 호출 적절성(집합 비교), 답변 적절성(LLM 채점, 구조화 출력), `--validate-grader` 모드, 결과 JSON 저장

**완료조건**
- [x] `--validate-grader`: `reference_answer` 20건이 **20/20** 1점
- [x] 일부러 틀린 답(사실 누락·금지 표현) 5건 이상이 **전부** 0점
- [x] 채점 결과에 항목별 `included/violated`와 근거(evidence)가 남는다
- [x] 도구 적절성 계산이 순서와 무관한 집합 비교다
- [x] 결과가 `results/run_<번호>_<태그>.json`으로 저장된다

---

## WU-09 기준 측정·오답 분석

**할 일**
- `python evaluate.py --tag baseline` 실행
- 틀린 건을 **직접 읽고** 원인 분류: 분류 오류 / 게이트 오류 / 사실 누락 / 금지 표현 / 검증 오탐

**완료조건**
- [x] `results/run_01_baseline.json`이 있고 두 지표 수치가 기록돼 있다
- [x] 틀린 문항 **전부**에 대해 원인 분류 + 구체 내용(어느 근거를 잘못 골랐는지, 어떤 사실을 빠뜨렸는지)이 적혀 있다
- [x] 다음에 바꿀 것 **하나**가 정해져 있다

---

## WU-10 개선 반복

**할 일**
- 한 번에 하나만 바꾸고 재측정 → 기록표에 추가. PRD 6절 목표 도달 또는 3회 이상 시도할 때까지 반복

**완료조건**
- [ ] 개선 시도가 **2회 이상** 기록돼 있다
- [ ] 각 회차가 "바꾼 것 하나 | 도구 적절성 | 답변 적절성 | 메모" 형식이다
- [ ] 각 회차의 결과 JSON이 `results/`에 있다
- [ ] 점수가 떨어진 시도도 지우지 않고 기록돼 있다
- [ ] 최종 수치가 PRD 6절 목표를 넘었거나, 못 넘었다면 이유가 적혀 있다

---

## WU-11 데모

**할 일**
- `app.py`: 입력창, 예시 질문 버튼, 답변 + 카테고리·호출 도구·근거 조항(펼치기)·게이트 판단·검증 결과·재시도/넘기기 표시

**완료조건**
- [ ] `streamlit run app.py`로 실행되고 질문에 답한다
- [ ] 정상 질문 / 범위 밖 / 문서에 답 없음 세 경우 모두 화면에서 동작한다
- [ ] 화면에 호출한 도구, 근거 조항 ID·본문, 검증 결과가 보인다
- [ ] API 키가 코드·저장소에 없다 (`git grep -i "sk-"` 결과 0건)
- [ ] 세 경우의 화면 캡처가 저장돼 있다 (REPORT용)

---

## WU-12 REPORT 작성·제출

**할 일**
- `REPORT.md` 7개 항목 작성, README 성격의 실행 방법 포함, 최종 푸시, 제출

**완료조건**
- [ ] 7개 항목(주제·문서 / 카테고리 설계·매핑표 / 평가셋 설계 / 측정 결과·원인 분류·개선 기록표 / 파이프라인 구조도 / 데모 설계·캡처 / 회고)이 모두 있다
- [ ] 구조도(Mermaid)가 실제 `agent.py` 그래프와 일치한다
- [ ] REPORT의 수치가 `results/` JSON과 일치한다
- [ ] [FINAL_CHECKLIST.md](FINAL_CHECKLIST.md) 전 항목 체크
- [ ] 새로 clone 받은 폴더에서 실행 방법대로 따라 했을 때 동작한다
