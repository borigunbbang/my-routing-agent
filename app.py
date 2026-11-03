"""Streamlit 데모: 답변과 함께 분류 → 근거 조립 → 게이트 → 검증 단계를 보여 준다.

streamlit run app.py
"""

import re

import streamlit as st

from agent import run
from context import OUT_OF_SCOPE

EXAMPLES = [
    "비수기 주중 예약을 당일에 취소하면 어떻게 되나요?",
    "태풍 특보 때문에 당일에 숙소에 못 가요. 환불되나요?",
    "숙소에 바비큐 시설이 있나요?",
    "렌터카도 같이 예약할 수 있나요?",
]

st.set_page_config(page_title="모두스테이 문의 라우팅 에이전트", page_icon="🏨")
st.title("🏨 모두스테이 고객문의")
st.caption("판정 → 근거 조립 → 근거만으로 답변 → 검증. 근거에 없으면 상담원에게 넘깁니다.")

st.write("예시 질문")
cols = st.columns(2)
for i, example in enumerate(EXAMPLES):
    if cols[i % 2].button(example, use_container_width=True):
        st.session_state.question = example

question = st.text_input("문의 내용", key="question", placeholder="예: 성수기 주말 예약을 3일 전에 취소하면 얼마나 돌려받나요?")
if not st.button("질문하기", type="primary") and not question:
    st.stop()
if not question:
    st.stop()

with st.spinner("분류하고 근거를 찾는 중..."):
    result = run(question)


def handoff_stage(r: dict) -> str:
    if r["categories"] == [OUT_OF_SCOPE]:
        return "분류에서 범위 밖으로 판정"
    if r["answerable"] is False:
        return "게이트에서 근거로 답할 수 없다고 판단"
    return "검증에 두 번 실패"


# ── 답변
st.subheader("답변")
if result["handoff"]:
    st.warning(result["answer"])
    st.caption(f"넘긴 이유: {handoff_stage(result)}")
else:
    st.success(re.sub(r"\[([A-Z]{3}-\d{2})\]", r"`\1`", result["answer"]))

# ── 단계별 처리 과정
st.subheader("처리 과정")

st.markdown("**① 카테고리 판정**")
st.write(" · ".join(result["categories"]))

st.markdown("**② 호출한 도구와 근거 조항**")
st.write("호출한 도구: " + ", ".join(f"`{t}`" for t in result["tools_called"]))
if result["context"]:
    cited = set(result["citations"])
    st.caption(f"프롬프트에 넣은 조항 {len(result['context'])}개 (문서 전체가 아니라 판정된 카테고리 조항만). ⭐ = 답변이 인용한 조항")
    for clause in result["context"]:
        mark = "⭐ " if clause["id"] in cited else ""
        with st.expander(f"{mark}[{clause['id']}] {clause['title']}  · 출처: {clause['source']}", expanded=clause["id"] in cited):
            st.markdown(clause["text"])
else:
    st.caption("근거를 조회하지 않았습니다.")

st.markdown("**③ 게이트: 근거만으로 답할 수 있는가**")
if result["answerable"] is None:
    st.caption("범위 밖이라 게이트를 거치지 않았습니다.")
else:
    st.write(("✅ 답할 수 있음" if result["answerable"] else "⛔ 답할 수 없음") + f" — {result['gate_reason']}")

st.markdown("**④ 검증: 문서에 없는 내용이 섞였는가**")
v = result["verification"]
if v is None:
    st.caption("답변을 만들지 않아 검증하지 않았습니다.")
else:
    st.write(("✅ 통과" if v["passed"] else "❌ 실패") + f" · 재생성 {result['retries']}회")
    st.table({
        "검사": ["인용이 없는 문장", "근거에 없는 조항 인용", "인용 조항에 없는 숫자"],
        "결과": [
            ", ".join(v["uncited_sentences"]) or "없음",
            ", ".join(v["unknown_citations"]) or "없음",
            ", ".join(u["number"] for u in v["unsupported_numbers"]) or "없음",
        ],
    })
