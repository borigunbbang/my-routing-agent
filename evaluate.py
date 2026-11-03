"""두 지표 측정: 도구 호출 적절성 · 답변 적절성. --validate-grader로 채점기 자체를 먼저 검증한다.

python evaluate.py --validate-grader
python evaluate.py --tag baseline
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

import prompts

load_dotenv()

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"
GOLDENSET = [g for g in json.loads((ROOT / "data" / "goldenset.json").read_text(encoding="utf-8")) if g["split"] == "eval"]
NEGATIVES = json.loads((ROOT / "data" / "grader_negatives.json").read_text(encoding="utf-8"))
WORKERS = 5


class FactCheck(BaseModel):
    fact: str
    included: bool
    evidence: str


class ViolationCheck(BaseModel):
    item: str
    violated: bool
    evidence: str


class Grade(BaseModel):
    facts: list[FactCheck]
    violations: list[ViolationCheck]


grader = ChatOpenAI(model="gpt-5.6-luna", temperature=0, timeout=60, max_retries=2).with_structured_output(Grade)


def tool_score(tools_called: list[str], expected: list[str]) -> int:
    """호출한 도구 집합이 기대 도구 집합과 정확히 같으면 1 (순서 무관)."""
    return int(set(tools_called) == set(expected))


def grade_answer(answer: str, item: dict) -> dict:
    """필수 사실을 전부 담고 금지 표현을 하나도 어기지 않으면 1."""
    user = prompts.GRADER_USER.format(
        answer=answer,
        must_include="\n".join(f"- {f}" for f in item["must_include"]),
        must_not="\n".join(f"- {f}" for f in item["must_not"]),
    )
    grade = grader.invoke([("system", prompts.GRADER_SYSTEM), ("human", user)])
    facts = [f.model_dump() for f in grade.facts]
    violations = [v.model_dump() for v in grade.violations]
    # 채점기가 항목을 빠뜨리면 통과로 치지 않는다
    complete = len(facts) == len(item["must_include"]) and len(violations) == len(item["must_not"])
    score = int(complete and all(f["included"] for f in facts) and not any(v["violated"] for v in violations))
    return {"answer_score": score, "facts": facts, "violations": violations, "grade_complete": complete}


def _parallel(fn, items):
    with ThreadPoolExecutor(WORKERS) as pool:
        return list(pool.map(fn, items))


def validate_grader() -> bool:
    """모범 답안은 전부 1점, 일부러 틀린 답은 전부 0점이어야 채점기를 믿을 수 있다."""
    by_id = {g["id"]: g for g in GOLDENSET}
    positives = _parallel(lambda g: (g["id"], grade_answer(g["reference_answer"], g)), GOLDENSET)
    negatives = _parallel(lambda n: (n["id"], n["why"], grade_answer(n["answer"], by_id[n["id"]])), NEGATIVES)

    pos_fail = [(i, r) for i, r in positives if r["answer_score"] != 1]
    neg_fail = [(i, why, r) for i, why, r in negatives if r["answer_score"] != 0]
    print(f"모범 답안: {len(positives) - len(pos_fail)}/{len(positives)} 1점")
    print(f"틀린 답:   {len(negatives) - len(neg_fail)}/{len(negatives)} 0점")
    for i, r in pos_fail:
        print(f"  [모범 답안 감점] {i}: {r}")
    for i, why, r in neg_fail:
        print(f"  [틀린 답 통과] {i} ({why}): {r}")

    RESULTS_DIR.mkdir(exist_ok=True)
    report = {"positives": dict(positives), "negatives": [{"id": i, "why": w, **r} for i, w, r in negatives]}
    (RESULTS_DIR / "grader_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return not pos_fail and not neg_fail


def evaluate_item(item: dict) -> dict:
    from agent import run

    result = run(item["question"])
    graded = grade_answer(result["answer"], item)
    return {
        "id": item["id"],
        "question": item["question"],
        "expected_category": item["category"],
        "expected_tools": item["expected_tools"],
        "categories": result["categories"],
        "tools_called": result["tools_called"],
        "tool_score": tool_score(result["tools_called"], item["expected_tools"]),
        "context_ids": [c["id"] for c in result["context"]],
        "answerable": result["answerable"],
        "gate_reason": result["gate_reason"],
        "answer": result["answer"],
        "verification": result["verification"],
        "retries": result["retries"],
        "handoff": result["handoff"],
        **graded,
    }


def next_run_path(tag: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    n = len(list(RESULTS_DIR.glob("run_*.json"))) + 1
    return RESULTS_DIR / f"run_{n:02d}_{tag}.json"


def evaluate(tag: str) -> dict:
    rows = _parallel(evaluate_item, GOLDENSET)
    summary = {
        "tag": tag,
        "n": len(rows),
        "tool_accuracy": sum(r["tool_score"] for r in rows) / len(rows),
        "answer_accuracy": sum(r["answer_score"] for r in rows) / len(rows),
    }
    path = next_run_path(tag)
    path.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"도구 호출 적절성: {summary['tool_accuracy']:.2f}  |  답변 적절성: {summary['answer_accuracy']:.2f}  →  {path.name}")
    for r in rows:
        if not (r["tool_score"] and r["answer_score"]):
            print(f"  ✗ {r['id']} 도구={r['tool_score']} 답변={r['answer_score']}  "
                  f"기대 {r['expected_tools']} / 실제 {r['tools_called']}  {r['question']}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-grader", action="store_true")
    parser.add_argument("--tag", default="run")
    parser.add_argument("--repeat", type=int, default=1, help="같은 설정을 여러 번 재서 변동 폭을 본다")
    args = parser.parse_args()
    if args.validate_grader:
        raise SystemExit(0 if validate_grader() else 1)
    summaries = [evaluate(args.tag if args.repeat == 1 else f"{args.tag}_r{i + 1}") for i in range(args.repeat)]
    if args.repeat > 1:
        for key in ["tool_accuracy", "answer_accuracy"]:
            values = [s[key] for s in summaries]
            print(f"{key}: 평균 {sum(values) / len(values):.3f}  범위 {min(values):.2f}~{max(values):.2f}  {values}")
