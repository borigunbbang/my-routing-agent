"""기계적 검증: LLM 없이 코드로 답변이 근거를 벗어났는지 검사한다.

1. 미인용 문장: [XXX-00] 인용이 없는 문장
2. 모르는 인용: 조립된 근거(context)에 없는 조항 ID
3. 근거 없는 숫자: 문장이 인용한 조항과 질문 어디에도 없는 숫자
"""

import re

from context import Clause

CITATION = re.compile(r"\[([A-Z]{3}-\d{2})\]")

# 숫자를 비교하기 전에 같은 뜻의 표현을 하나로 맞춘다.
WORD_NUMBERS = {
    "하루": "1일", "이틀": "2일", "사흘": "3일", "나흘": "4일",
    "일주일": "7일", "열흘": "10일", "한 시간": "1시간", "절반": "50%",
}
UNITS = "퍼센트|영업일|시간|만원|만 원|%|일|시|분|원|배|회|명|박|월|년|마리"
NUMBER = re.compile(rf"(\d[\d,]*(?:\.\d+)?)\s*(?:~\s*(\d[\d,]*(?:\.\d+)?)\s*)?({UNITS})?")


def split_sentences(text: str) -> list[str]:
    """문장 끝(. ! ?)이나 인용 뒤 공백에서 자른다. 인용만 남은 조각은 앞 문장에 붙인다."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|(?<=\])\s+(?=[^\[])", text) if p.strip()]
    sentences = []
    for part in parts:
        if sentences and not CITATION.sub("", part).strip(" .!?"):
            sentences[-1] += " " + part
        else:
            sentences.append(part)
    return sentences


def _normalize(text: str) -> str:
    text = CITATION.sub("", text)  # 인용 ID의 숫자("02")를 숫자로 세지 않는다
    for word, num in WORD_NUMBERS.items():
        text = text.replace(word, num)
    text = re.sub(r"오후\s*(\d{1,2})\s*시", lambda m: f"{int(m.group(1)) % 12 + 12}시", text)
    text = re.sub(r"(오전|자정)\s*", "", text)
    return text


def extract_numbers(text: str) -> set[str]:
    """'60%', '3일', '15시', '10000원'처럼 값+단위로 정규화한 숫자 집합. 단위 없는 숫자는 값만."""
    numbers = set()
    for start, end, unit in NUMBER.findall(_normalize(text)):
        unit = {"퍼센트": "%", "만 원": "만원", "영업일": "일"}.get(unit, unit)
        for raw in filter(None, [start, end]):
            value = raw.replace(",", "")
            if unit == "만원":
                value, unit_out = str(int(float(value) * 10000)), "원"
            else:
                unit_out = unit
            numbers.add(value + unit_out)
    return numbers


def _supported(number: str, allowed: set[str]) -> bool:
    if number in allowed:
        return True
    value = re.match(r"[\d.]+", number).group()
    return number == value and any(re.match(r"[\d.]+", a).group() == value for a in allowed)


def verify(answer: str, context: list[Clause], question: str = "") -> dict:
    by_id = {c["id"]: c for c in context}
    question_numbers = extract_numbers(question)
    uncited, unknown, unsupported, citations = [], [], [], []

    for sentence in split_sentences(answer):
        cites = CITATION.findall(sentence)
        if not cites:
            uncited.append(sentence)
            continue
        citations += [c for c in cites if c not in citations]
        unknown += [c for c in cites if c not in by_id and c not in unknown]
        allowed = question_numbers.union(*(extract_numbers(by_id[c]["text"]) for c in cites if c in by_id))
        unsupported += [
            {"number": n, "sentence": sentence}
            for n in sorted(extract_numbers(sentence)) if not _supported(n, allowed)
        ]

    return {
        "passed": not (uncited or unknown or unsupported),
        "citations": citations,
        "uncited_sentences": uncited,
        "unknown_citations": unknown,
        "unsupported_numbers": unsupported,
    }


def describe_violations(result: dict) -> str:
    """재생성 프롬프트에 넣을 위반 내역."""
    lines = [f"- 인용이 없는 문장: {s}" for s in result["uncited_sentences"]]
    lines += [f"- 근거에 없는 조항을 인용함: [{c}]" for c in result["unknown_citations"]]
    lines += [f"- 인용한 조항에 없는 숫자 '{u['number']}': {u['sentence']}" for u in result["unsupported_numbers"]]
    return "\n".join(lines)


if __name__ == "__main__":
    import json

    from context import CATEGORY_TOOL, CLAUSE_BY_ID, HANDOFF_MESSAGE, assemble_context

    ref = [CLAUSE_BY_ID["REF-03"]]

    # 1. 미인용 문장
    r = verify("총요금의 60%를 공제합니다 [REF-03]. 감사합니다.", ref)
    assert not r["passed"] and r["uncited_sentences"] == ["감사합니다."], r
    # 2. 모르는 인용
    r = verify("결제 후 24시간 이내면 전액 환불됩니다 [REF-02].", ref)
    assert r["unknown_citations"] == ["REF-02"], r
    # 3. 근거 없는 숫자 (근거는 10%, 답변은 15%)
    r = verify("성수기 주중 7일 전 취소는 총요금의 15%를 공제합니다 [REF-03].", ref)
    assert [u["number"] for u in r["unsupported_numbers"]] == ["15%"], r
    # 4. 정규화: 띄어쓰기·말로 쓴 숫자·오후 시각
    assert verify("총요금의 60 %를 공제합니다 [REF-03].", ref)["passed"]
    assert verify("하루 전 취소는 80%를 공제합니다 [REF-03].", ref)["passed"]
    assert verify("체크인은 15시부터입니다 [STY-01].", [CLAUSE_BY_ID["STY-01"]])["passed"]
    assert extract_numbers("1만원") == extract_numbers("10,000원") == {"10000원"}
    # 5. 인용 ID의 숫자를 숫자로 세지 않음
    assert verify("전액 환불됩니다 [REF-03].", ref)["passed"]
    # 6. 질문에 나온 숫자는 허용
    q = "4명 기준 객실에 5명이 자도 되나요?"
    assert verify("5명이면 기준 인원을 넘어 추가 요금이 있습니다 [STY-02].", [CLAUSE_BY_ID["STY-02"]], q)["passed"]
    # 7. 인용이 문장 마침표 뒤에 와도 같은 문장으로 본다
    assert verify("총요금의 60%를 공제합니다. [REF-03]", ref)["passed"]

    # 모범 답안은 기대 도구로 조립한 근거로 모두 통과해야 한다
    tool_category = {t: c for c, t in CATEGORY_TOOL.items()}
    failed = []
    for g in json.load(open("data/goldenset.json", encoding="utf-8")):
        if g["reference_answer"] == HANDOFF_MESSAGE:
            continue
        _, context = assemble_context([tool_category[t] for t in g["expected_tools"] if t in tool_category])
        r = verify(g["reference_answer"], context, g["question"])
        if not r["passed"]:
            failed.append((g["id"], describe_violations(r)))
    assert not failed, failed
    print("verify.py 테스트 전부 통과")
