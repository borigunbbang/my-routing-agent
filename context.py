"""문서 쪼개기(조항 단위) · 카테고리↔조항 매핑 · 카테고리별 근거 조립."""

import re
from pathlib import Path
from typing import TypedDict

POLICY_PATH = Path(__file__).parent / "docs" / "policy_modustay.md"

OUT_OF_SCOPE = "범위 밖"
HANDOFF_MESSAGE = "정확한 안내를 위해 상담원에게 연결해 드리겠습니다."

# 조항 ID 접두어 → 카테고리
PREFIX_CATEGORY = {
    "BKG": "예약·결제",
    "REF": "취소·환불",
    "STY": "체크인·이용규칙",
    "DSP": "분쟁·보상",
}

# 카테고리 → 근거 조회 도구
CATEGORY_TOOL = {
    "예약·결제": "get_booking",
    "취소·환불": "get_refund",
    "체크인·이용규칙": "get_stay_rules",
    "분쟁·보상": "get_dispute",
}

# 접두어 매핑의 예외: 다른 카테고리 조항이 필요할 때만 명시한다.
# 분쟁·보상 배상표(DSP-01·02)는 성수기·주말 정의(REF-01) 없이는 답할 수 없다.
EXTRA_MAP = {
    "분쟁·보상": ["REF-01"],
}

CATEGORIES = list(CATEGORY_TOOL) + [OUT_OF_SCOPE]


class Clause(TypedDict):
    id: str
    category: str
    title: str
    text: str
    source: str


_HEADING = re.compile(r"^### \[([A-Z]{3})-(\d{2})\] (.+)$", re.M)


def load_clauses(path: Path = POLICY_PATH) -> list[Clause]:
    """`### [XXX-00] 제목` 헤딩 단위로 문서를 조항으로 자른다."""
    doc = path.read_text(encoding="utf-8")
    matches = list(_HEADING.finditer(doc))
    clauses = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(doc)
        body = doc[m.end():end].split("\n---")[0].strip()  # 다음 카테고리 구분선 이후는 제외
        source_line, _, text = body.partition("\n")
        clauses.append(Clause(
            id=f"{m.group(1)}-{m.group(2)}",
            category=PREFIX_CATEGORY[m.group(1)],
            title=m.group(3).strip(),
            text=text.strip(),
            source=source_line.removeprefix("출처:").strip(),
        ))
    return clauses


CLAUSES = load_clauses()
CLAUSE_BY_ID = {c["id"]: c for c in CLAUSES}


def clauses_for(category: str) -> list[Clause]:
    """카테고리에 매핑된 조항: 접두어가 같은 조항 + EXTRA_MAP 예외."""
    own = [c for c in CLAUSES if c["category"] == category]
    extra = [CLAUSE_BY_ID[i] for i in EXTRA_MAP.get(category, [])]
    return own + extra


# 근거 조회 도구 — 카테고리 하나의 조항만 돌려준다.
def get_booking() -> list[Clause]:
    return clauses_for("예약·결제")


def get_refund() -> list[Clause]:
    return clauses_for("취소·환불")


def get_stay_rules() -> list[Clause]:
    return clauses_for("체크인·이용규칙")


def get_dispute() -> list[Clause]:
    return clauses_for("분쟁·보상")


def handoff() -> str:
    return HANDOFF_MESSAGE


TOOLS = {
    "get_booking": get_booking,
    "get_refund": get_refund,
    "get_stay_rules": get_stay_rules,
    "get_dispute": get_dispute,
}


def assemble_context(categories: list[str]) -> tuple[list[str], list[Clause]]:
    """판정된 카테고리의 도구를 호출해 (호출한 도구, 중복 없는 근거 조항)을 돌려준다."""
    tools_called, context, seen = [], [], set()
    for category in categories:
        if category not in CATEGORY_TOOL:
            continue
        tool = CATEGORY_TOOL[category]
        tools_called.append(tool)
        for clause in TOOLS[tool]():
            if clause["id"] not in seen:
                seen.add(clause["id"])
                context.append(clause)
    return tools_called, context


def format_context(context: list[Clause]) -> str:
    """프롬프트에 넣을 근거 텍스트."""
    return "\n\n".join(f"[{c['id']}] {c['title']}\n{c['text']}" for c in context)


if __name__ == "__main__":
    for category in CATEGORY_TOOL:
        ids = [c["id"] for c in clauses_for(category)]
        print(f"{category:10} {CATEGORY_TOOL[category]:15} {ids}")
