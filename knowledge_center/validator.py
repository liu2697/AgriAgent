"""
农业知识中心 · 知识质量检查（V1.0 新增）。

只报告问题，绝不删除、绝不修改任何知识数据。
- source 缺失只报 warning（source_status=unverified），不视为错误
- 检查结果用于知识库管理与后续人工补充权威资料
"""
from __future__ import annotations

import json
from typing import Optional

from knowledge_center.loader import DATA_DIR, load_knowledge
from knowledge_center.schema import CATEGORIES, RISK_LEVELS, as_list, normalize_category


def _check_json_files() -> list[str]:
    """检查 data/*.json 是否都能正常解析（检查项 8）。"""
    errors: list[str] = []
    if not DATA_DIR.exists():
        return errors
    for f in sorted(DATA_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                json.load(fp)
        except Exception as exc:  # noqa: BLE001 — 检查器需捕获全部解析异常
            errors.append(f"JSON 解析失败: {f.name}（{exc}）")
    return errors


def validate_knowledge(entries: Optional[list[dict]] = None) -> dict:
    """知识库质量检查。

    参数：
        entries: 待检查条目；缺省时自动加载全部知识条目。

    检查项：
        1. id 是否重复 / 缺失
        2. crop 是否为空（农药安全类条目允许无 crop）
        3. category 是否合法（可映射到枚举）
        4. disease 类知识是否缺少 disease 名称
        5. source 是否存在（缺失仅 warning）
        6. 是否存在明显重复条目（crop+disease+category 相同）
        7. 是否存在空数组/空字段异常（核心内容字段）
        8. data/*.json 是否可以正常解析
        9. risk_level 是否合法（高/中/低/未知；未知仅 warning）

    返回：
        {
            "valid": bool,          # 无 error 即 True（warning 不影响）
            "total": int,
            "errors": [str],
            "warnings": [str],
            "error_count": int,
            "warning_count": int,
        }
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- 检查 8：JSON 文件可解析性（直接读原始文件） ---
    errors.extend(_check_json_files())

    if entries is None:
        entries = load_knowledge()

    seen_ids: dict[str, str] = {}
    seen_dup_keys: dict[tuple, str] = {}

    for idx, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            errors.append(f"条目#{idx}：不是 dict 结构")
            continue

        where = str(e.get("id") or "").strip() or f"条目#{idx}"
        cat_code = (
            e.get("category_code")
            or normalize_category(e.get("category"))
        )
        cat_code = str(cat_code or "").strip()
        is_pesticide = cat_code == "pesticide_safety"

        # --- 检查 1：id 重复 / 缺失 ---
        eid = str(e.get("id") or "").strip()
        if not eid:
            errors.append(f"{where}：缺少 id")
        elif eid in seen_ids:
            errors.append(f"{where}：id 重复（与 {seen_ids[eid]} 相同）")
        else:
            seen_ids[eid] = where

        # --- 检查 2：crop 为空（农药安全类允许无 crop） ---
        if not str(e.get("crop") or "").strip() and not is_pesticide:
            errors.append(f"{where}：crop 为空")

        # --- 检查 3：category 合法性 ---
        if not str(e.get("category") or "").strip():
            errors.append(f"{where}：缺少 category")
        elif not cat_code:
            errors.append(f"{where}：category 非法（无法映射到枚举）→ {e.get('category')}")
        elif cat_code not in CATEGORIES:
            errors.append(f"{where}：category 不在枚举内 → {cat_code}")

        # --- 检查 4：disease 类条目缺少 disease ---
        if cat_code == "disease" and not str(e.get("disease") or "").strip():
            errors.append(f"{where}：disease 类条目缺少 disease 名称")

        # --- 检查 9：risk_level 合法性（未知是合法值，仅 warning 提示后续补充） ---
        if not is_pesticide:
            risk = str(e.get("risk_level") or "").strip()
            if risk not in RISK_LEVELS:
                errors.append(f"{where}：risk_level 非法（不在 高/中/低/未知）→ {risk!r}")
            elif risk == "未知":
                warnings.append(
                    f"{where}：risk_level 未知，可依据权威来源补充，禁止凭空填写"
                )

        # --- 检查 5：source（缺失仅 warning，不删数据） ---
        if not str(e.get("source") or "").strip():
            warnings.append(f"{where}：缺少来源 → source_status=unverified")

        # --- 检查 6：明显重复条目 ---
        dup_key = (
            str(e.get("crop") or "").strip(),
            str(e.get("disease") or "").strip(),
            str(e.get("category") or "").strip(),
        )
        if dup_key in seen_dup_keys:
            warnings.append(
                f"{where}：疑似重复条目（与 {seen_dup_keys[dup_key]} 的"
                f" crop/disease/category 完全相同）"
            )
        else:
            seen_dup_keys[dup_key] = where

        # --- 检查 7：核心内容字段空数组/空字段异常 ---
        if is_pesticide:
            if not as_list(e.get("products")) and not as_list(e.get("forbidden_substances")):
                warnings.append(f"{where}：products/forbidden_substances 均为空")
        else:
            if not as_list(e.get("symptoms")):
                warnings.append(f"{where}：symptoms 为空")
            if not as_list(e.get("prevention")) and not as_list(e.get("control_measures")):
                warnings.append(f"{where}：prevention 与 control_measures 均为空")

    return {
        "valid": len(errors) == 0,
        "total": len(entries),
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


__all__ = ["validate_knowledge"]
