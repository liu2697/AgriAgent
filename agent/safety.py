from __future__ import annotations

from safety.reviewer import (
    review as _review,
    ReviewResult,
    ReviewIssue,
    FORBIDDEN_PESTICIDES,
)


class SafetyService:
    """
    Agent 封装层：安全审核服务。

    底层复用 safety.reviewer.review：
      - 禁限用农药黑名单
      - 风险措辞 / 危险操作 / 剂量复核
      - 农药登记合规核验（超范围用药拦截），需传入 crop / disease
    """

    def __init__(self):
        self._forbidden = list(FORBIDDEN_PESTICIDES)

    def review(self, text: str, diagnosis_context: str = "",
               crop: str = "", disease: str = "") -> ReviewResult:
        return _review(
            text=text,
            diagnosis_context=diagnosis_context,
            crop=crop,
            disease=disease,
        )

    @property
    def forbidden_pesticides(self) -> list[str]:
        return list(self._forbidden)


__all__ = ["SafetyService", "ReviewResult", "ReviewIssue", "FORBIDDEN_PESTICIDES"]
