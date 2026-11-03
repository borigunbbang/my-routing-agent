"""파이프라인: classify → retrieve → gate → answer → verify (실패 시 1회 재생성) / 모르면 handoff."""

from typing import Literal, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

import prompts
from context import HANDOFF_MESSAGE, OUT_OF_SCOPE, Clause, assemble_context, format_context
from verify import describe_violations, verify

load_dotenv()

MODEL = "gpt-5.6-luna"
MAX_RETRIES = 1

Category = Literal["예약·결제", "취소·환불", "체크인·이용규칙", "분쟁·보상", "범위 밖"]


class AgentState(TypedDict, total=False):
    question: str
    categories: list[str]
    tools_called: list[str]
    context: list[Clause]
    answerable: bool
    gate_reason: str
    answer: str
    citations: list[str]
    verification: dict
    retries: int
    handoff: bool


class Classification(BaseModel):
    categories: list[Category] = Field(description="해당 카테고리 1~2개")


class GateDecision(BaseModel):
    answerable: bool
    reason: str


llm = ChatOpenAI(model=MODEL, temperature=0, timeout=60, max_retries=2)
classifier = llm.with_structured_output(Classification)
gatekeeper = llm.with_structured_output(GateDecision)


def classify(state: AgentState) -> AgentState:
    """카테고리만 고른다. 넘길지는 여기서 판단하지 않는다."""
    result = classifier.invoke([("system", prompts.CLASSIFY_SYSTEM), ("human", state["question"])])
    categories = list(dict.fromkeys(result.categories))[:2]  # 중복 제거, 최대 2개
    if not categories or (OUT_OF_SCOPE in categories and len(categories) > 1):
        categories = [c for c in categories if c != OUT_OF_SCOPE] or [OUT_OF_SCOPE]
    return {"categories": categories, "tools_called": [], "retries": 0, "handoff": False}


def retrieve(state: AgentState) -> AgentState:
    """매핑표대로 코드가 도구를 호출하고 근거를 조립한다."""
    tools_called, context = assemble_context(state["categories"])
    return {"tools_called": tools_called, "context": context}


def gate(state: AgentState) -> AgentState:
    """조립된 근거만으로 질문의 핵심에 답할 수 있는지 판단한다."""
    user = prompts.GATE_USER.format(context=format_context(state["context"]), question=state["question"])
    result = gatekeeper.invoke([("system", prompts.GATE_SYSTEM), ("human", user)])
    return {"answerable": result.answerable, "gate_reason": result.reason}


def answer(state: AgentState) -> AgentState:
    user = prompts.ANSWER_USER.format(context=format_context(state["context"]), question=state["question"])
    retries = state.get("retries", 0)
    if state.get("verification"):  # 검증 실패 후 재생성
        user += prompts.RETRY_ADDENDUM.format(
            previous_answer=state["answer"], violations=describe_violations(state["verification"]))
        retries += 1
    text = llm.invoke([("system", prompts.ANSWER_SYSTEM), ("human", user)]).content.strip()
    return {"answer": text, "retries": retries}


def check(state: AgentState) -> AgentState:
    result = verify(state["answer"], state["context"], state["question"])
    return {"verification": result, "citations": result["citations"]}


def handoff(state: AgentState) -> AgentState:
    return {
        "tools_called": state.get("tools_called", []) + ["handoff"],
        "answer": HANDOFF_MESSAGE,
        "handoff": True,
    }


def after_classify(state: AgentState) -> str:
    return "handoff" if state["categories"] == [OUT_OF_SCOPE] else "retrieve"


def after_gate(state: AgentState) -> str:
    return "answer" if state["answerable"] else "handoff"


def after_verify(state: AgentState) -> str:
    if state["verification"]["passed"]:
        return END
    return "answer" if state["retries"] < MAX_RETRIES else "handoff"


def build():
    g = StateGraph(AgentState)
    g.add_node("classify", classify)
    g.add_node("retrieve", retrieve)
    g.add_node("gate", gate)
    g.add_node("answer", answer)
    g.add_node("verify", check)
    g.add_node("handoff", handoff)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", after_classify, ["retrieve", "handoff"])
    g.add_edge("retrieve", "gate")
    g.add_conditional_edges("gate", after_gate, ["answer", "handoff"])
    g.add_edge("answer", "verify")
    g.add_conditional_edges("verify", after_verify, [END, "answer", "handoff"])
    g.add_edge("handoff", END)
    return g.compile()


graph = build()

RESULT_KEYS = ["question", "categories", "tools_called", "context", "answerable", "gate_reason",
               "answer", "citations", "verification", "retries", "handoff"]


def run(question: str) -> dict:
    state = graph.invoke({"question": question})
    defaults = {"context": [], "answerable": None, "gate_reason": "", "citations": [], "verification": None}
    return {k: state.get(k, defaults.get(k)) for k in RESULT_KEYS}


if __name__ == "__main__":
    import sys

    result = run(" ".join(sys.argv[1:]) or "성수기 주말 숙박을 사용일 3일 전에 취소하면 얼마나 돌려받나요?")
    print("카테고리:", result["categories"])
    print("호출 도구:", result["tools_called"])
    print("근거 조항:", [c["id"] for c in result["context"]])
    print("게이트:", result["answerable"], "-", result["gate_reason"])
    print("답변:", result["answer"])
    print("검증:", result["verification"])
    print("재시도:", result["retries"], "| 넘김:", result["handoff"])
