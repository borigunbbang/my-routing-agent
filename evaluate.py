"""두 지표 측정: 도구 호출 적절성 · 답변 적절성 (+ 분류 정확도·macro F1). --validate-grader로 채점기 자체를 먼저 검증한다.

python evaluate.py --validate-grader
python evaluate.py --tag baseline
python evaluate.py --metrics run_03 run_04   # 저장된 결과로 분류 지표·근거 검사를 다시 계산 (API 호출 없음)
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

import prompts
from context import CATEGORIES, CATEGORY_TOOL, OUT_OF_SCOPE, clauses_for

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


TOOL_CATEGORY = {t: c for c, t in CATEGORY_TOOL.items()}


def expected_categories(row: dict) -> set[str]:
    """기대 도구에서 기대 카테고리를 역산한다. 두 카테고리 문의(E03)는 2개."""
    return {TOOL_CATEGORY[t] for t in row["expected_tools"] if t in TOOL_CATEGORY} or {OUT_OF_SCOPE}


def classification_metrics(rows: list[dict]) -> dict:
    """정확도 = 예측 카테고리 집합이 기대 집합과 정확히 같은 비율. F1은 카테고리별 일대다(one-vs-rest)."""
    per_category = {}
    for c in CATEGORIES:
        tp = sum(c in expected_categories(r) and c in r["categories"] for r in rows)
        fp = sum(c not in expected_categories(r) and c in r["categories"] for r in rows)
        fn = sum(c in expected_categories(r) and c not in r["categories"] for r in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_category[c] = {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
    return {
        "classification_accuracy": sum(expected_categories(r) == set(r["categories"]) for r in rows) / len(rows),
        "macro_f1": sum(m["f1"] for m in per_category.values()) / len(per_category),
        "per_category": per_category,
    }


def context_check(rows: list[dict]) -> list[str]:
    """프롬프트에 들어간 근거가 판정된 카테고리의 조항과 정확히 같지 않은 문항 ID."""
    bad = []
    for r in rows:
        allowed = {c["id"] for cat in r["categories"] if cat != OUT_OF_SCOPE for c in clauses_for(cat)}
        if set(r["context_ids"]) != allowed:
            bad.append(r["id"])
    return bad


def print_classification(metrics: dict) -> None:
    print(f"분류 정확도: {metrics['classification_accuracy']:.3f}  |  macro F1: {metrics['macro_f1']:.3f}")
    for c, m in metrics["per_category"].items():
        print(f"  {c:8} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}  (TP {m['tp']} FP {m['fp']} FN {m['fn']})")


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
        **classification_metrics(rows),
    }
    path = next_run_path(tag)
    path.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"도구 호출 적절성: {summary['tool_accuracy']:.2f}  |  답변 적절성: {summary['answer_accuracy']:.2f}  →  {path.name}")
    print_classification(summary)
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
    parser.add_argument("--metrics", nargs="+", metavar="RUN", help="저장된 결과(run_03 등)를 합쳐 분류 지표·근거 검사를 다시 계산")
    args = parser.parse_args()
    if args.validate_grader:
        raise SystemExit(0 if validate_grader() else 1)
    if args.metrics:
        rows = [r for run in args.metrics for path in RESULTS_DIR.glob(f"{run}_*.json")
                for r in json.loads(path.read_text(encoding="utf-8"))["rows"]]
        print(f"{' + '.join(args.metrics)}: {len(rows)}건")
        print_classification(classification_metrics(rows))
        bad = context_check(rows)
        print(f"근거가 판정 카테고리 조항과 다른 문항: {len(bad)}건 {bad}")
        raise SystemExit(0)
    summaries = [evaluate(args.tag if args.repeat == 1 else f"{args.tag}_r{i + 1}") for i in range(args.repeat)]
    if args.repeat > 1:
        for key in ["tool_accuracy", "answer_accuracy"]:
            values = [s[key] for s in summaries]
            print(f"{key}: 평균 {sum(values) / len(values):.3f}  범위 {min(values):.2f}~{max(values):.2f}  {values}")
