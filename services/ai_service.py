import base64
from typing import Optional

import requests

from config import AI_API_KEY, AI_API_URL, AI_MODEL, AI_MODEL_SUPPORTS_VISION


# 各作物常见病害（用于无 Key 示例诊断，病害名与 knowledge_center 知识库条目一致）
_MOCK_DISEASES = {
    "玉米": "玉米大斑病",
    "马铃薯": "马铃薯晚疫病",
    "小麦": "小麦条锈病",
    "大豆": "大豆根腐病",
    "棉花": "棉蚜",
    "花生": "花生叶斑病",
    "高粱": "高粱丝黑穗病",
    "向日葵": "向日葵菌核病",
    "其他": "叶部真菌性病害",
}


def _encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def build_prompt(crop: str, growth_stage: str, soil_type: str, area: float,
                 location: str, symptoms: str) -> str:
    """构造诊断提示词。

    V1.1 硬化要点（针对"通用大模型农业不专业"的三个真实失效模式）：
      1. 强制证据意识：先列观察到的症状，再下判断，禁止只给病名不给依据
      2. 允许且要求"认怂"：信息不足时必须说无法确定并列出还需观察什么，
         而不是硬凑一个病名（通用模型最大的风险是永远给答案）
      3. 药剂白名单：只能使用下方注入的登记药剂清单，禁止自由生成药名；
         清单里没有的药一律写"请按登记标签选用"，杜绝编造药名与剂量
    """
    location_text = location or "未填写"
    return f"""你是北方大田植保专家，正在协助农户做病虫害辅助诊断。你的结论会由农技员复核，因此**准确性优先于给出答案**。

【作物与地块信息】
- 作物类型：{crop}
- 生长阶段：{growth_stage}
- 土壤类型：{soil_type}
- 地块面积：{area} 亩
- 地理位置：{location_text}
- 农户描述与系统检索资料：{symptoms or "未描述"}

【硬性规则】
1. **有候选时必须限定在候选内**：若上文提供了「知识库检索命中」，你的判断必须从这些条目中选择；确有必要考虑候选之外的问题时，必须显式说明"候选外推测"并给出理由。
2. **先证据后判断**：每条可能性都必须写出支持它的具体观察依据（看到什么斑、什么颜色、什么部位、有没有霉层/虫体），以及有无**不符合**之处。没有依据的猜测不要写。
3. **信息不足时必须明说**：若仅凭现有信息无法区分，就明确回答"当前信息不足以确定，建议人工复核"，并列出「还需补充的观察项」（例如：叶背是否有灰白色霉层、病斑是否受叶脉限制、茎基部是否腐烂）。**不允许为了给出答案而虚构症状。**
4. **药剂白名单**：涉及用药时，只能推荐上文「知识库检索命中」里出现的登记药剂。清单里没有合适药剂时，写"请按当地登记标签选用"，不要自行生成药名。禁止推荐国家禁限用农药。
5. **剂量不编造**：不确定具体用量时写"按标签推荐剂量"，不要虚构数字；已给出的剂量必须标注需以登记标签为准。

【输出结构】（使用 Markdown，标题用 `###` 形式，便于系统解析）
### 1. 观察到的症状
（逐条列出，只写确实观察到或农户明确描述的）

### 2. 可能性排序
按可能性从高到低排列，每条包含：名称 / 可能性（高-中-低）/ 支持依据 / 不符合之处

### 3. 整体风险等级
高 / 中 / 低，并说明判断理由与把握程度

### 4. 还需补充的观察项
（若信息已足够则写"暂无"，不得留空）

### 5. 防治方案
分物理防治 / 生物防治 / 化学防治；化学防治只使用上方候选中的登记药剂，注明安全间隔期（不确定则写"以标签为准"）

### 6. 农事建议
结合生长阶段与华北、内蒙古等北方气候特点，给出灌溉、施肥、轮作等管理建议

### 7. 风险提示
不及时处理的产量损失区间，以及何时必须联系农技员

结尾固定注明：本结论为 AI 辅助判断，须经当地农技人员复核后实施。"""


def build_vision_prompt(crop: str, growth_stage: str) -> str:
    """视觉步骤专用提示词：只做结构化症状抽取，禁止给出病名。

    让视觉模型抢答病名会污染后续诊断（它的答案会被当成"视觉证据"注入
    最终 Prompt），因此这里只要求它客观描述可观察特征。
    """
    return f"""请只观察并客观描述这张作物照片，不要给出任何病害名称或结论。

作物：{crop}　生长阶段：{growth_stage}

请按以下要点逐项描述（看不到的写"不可见"，不要猜测）：
1. 拍摄部位（叶片正面/背面、茎秆、果穗、根部、整体）
2. 病斑的**形状**（圆形、梭形、长条形、不规则）与**大小**
3. 病斑的**颜色**，以及边缘与中央是否颜色不同
4. 病斑的**分布**（是否沿叶脉、是否密集、是否从叶尖开始）
5. 表面是否有**霉层/粉状物/水渍状油浸感/虫体/虫孔/粪屑**
6. 植株整体状态（萎蔫、矮化、卷曲、枯黄）

只输出上述观察结果，不要写"可能是XX病"。"""


def _request_ai(messages: list):
    """调用大模型接口，返回 (content, error)。"""
    try:
        resp = requests.post(
            AI_API_URL,
            headers={
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": AI_MODEL, "messages": messages, "temperature": 0.6},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"], None
    except Exception as exc:
        return None, str(exc)


def diagnose(image_bytes: Optional[bytes], crop: str, growth_stage: str,
             soil_type: str, area: float, location: str, symptoms: str,
             vision_only: bool = False) -> dict:
    """调用大模型做诊断。

    vision_only=True 时走「只做症状描述、不给病名」的视觉抽取提示词，
    供 Agent 的视觉步骤使用（避免视觉模型的抢答结论被当成诊断证据）。
    """
    if vision_only:
        prompt = build_vision_prompt(crop, growth_stage)
    else:
        prompt = build_prompt(crop, growth_stage, soil_type, area, location, symptoms)

    if not AI_API_KEY:
        return _mock_diagnose(crop, growth_stage, location)

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    # 模型已知不支持图片：直接走文字模式，不做一次注定失败的视觉请求
    if image_bytes and not AI_MODEL_SUPPORTS_VISION:
        content, error = _request_ai(messages)
        if content is None:
            return {"success": False, "content": f"AI 服务调用失败：{error}", "source": "error"}
        return {
            "success": True,
            "content": (
                f"> 当前模型（{AI_MODEL}）为纯文字模型，未使用上传的图片，"
                "以下结果基于文字信息诊断。\n\n" + content
            ),
            "source": f"{AI_MODEL}（纯文字模式）",
        }

    if image_bytes:
        img_b64 = _encode_image(image_bytes)
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
        })
        content, error = _request_ai(messages)
        if content is None:
            # 视觉接口调用失败（模型不可用 / 无权限 / 不支持图片），自动降级为纯文字诊断
            messages[0]["content"] = [{"type": "text", "text": prompt}]
            content, error = _request_ai(messages)
            if content is not None:
                return {
                    "success": True,
                    "content": (
                        f"> 图片识别未生效（模型 {AI_MODEL} 不提供图片输入或调用失败），"
                        "以下结果基于文字信息诊断。\n\n" + content
                    ),
                    "source": f"{AI_MODEL}（文字模式）",
                }
    else:
        content, error = _request_ai(messages)

    if content is None:
        return {"success": False, "content": f"AI 服务调用失败：{error}", "source": "error"}

    return {"success": True, "content": content, "source": AI_MODEL}


def _mock_diagnose(crop: str, growth_stage: str, location: str) -> dict:
    disease = _MOCK_DISEASES.get(crop, _MOCK_DISEASES["其他"])
    loc_text = f"，位于 {location}" if location else ""
    content = f"""当前未配置 AI 服务密钥，以下为示例诊断结果，仅用于功能演示。

---

### 1. 初步诊断
- **{disease}**（可能性 85%）
- **缺素引起的叶片黄化**（可能性 60%）
- **早期蚜虫危害**（可能性 30%）

**整体风险等级　中**

### 2. 问题分析
{crop} 处于 **{growth_stage}**{loc_text}，此阶段对养分需求较高。叶片黄化通常与氮素供应不足、根系吸收受阻或环境胁迫有关；若近期降雨偏多、田间湿度大，病害扩展风险会明显上升。

### 3. 防治方案
- **物理防治**　人工检查叶背，清除病残叶；悬挂黄板诱杀有翅蚜
- **生物防治**　释放瓢虫、草蛉等天敌昆虫
- **化学防治**　优先选用低毒登记药剂，如吡虫啉 10% 可湿性粉剂 1500 倍液喷雾，安全间隔期 7 天

### 4. 农事建议
- 追施尿素 5-8 kg/亩，配合叶面喷施 0.2% 磷酸二氢钾
- 保持土壤湿润但不积水，避免大水漫灌，雨后及时排涝
- 间隔 7-10 天复查一次，观察新叶与病害发展情况

### 5. 风险提示
若不及时处理，可能导致减产 10%-30%，严重时影响灌浆 / 结薯 / 坐果。

---

*安全提示　以上用药建议仅供参考，实际用药请咨询当地农技人员，严禁使用禁限用农药。*"""
    return {"success": True, "content": content, "source": "mock"}


def generate_management_advice(plot_key: str, records: list, profile: dict,
                               logs: list) -> dict:
    """基于地块档案（历史诊断 + 基础信息 + 农事日志）生成长期管理建议。"""
    lines = [
        f"【地块】{plot_key}",
        "【基础信息】"
        f"土壤：{profile.get('soil_type') or '未填写'}，"
        f"经纬度：{profile.get('longitude') or '未填写'}, {profile.get('latitude') or '未填写'}，"
        f"播种时间：{profile.get('planting_date') or '未填写'}",
        f"【历史诊断 {len(records)} 次】",
    ]
    for r in records[-8:]:
        lines.append(
            f"- {r['timestamp'][:10]} | {r['growth_stage']} | "
            f"风险：{r.get('risk_level') or '未知'} | "
            f"诊断：{r['diagnosis_summary'][:60]} | 建议：{r['recommendation_summary'][:80]}"
        )
    if logs:
        lines.append(f"【农事日志 {len(logs)} 条】")
        for log in logs[-8:]:
            lines.append(f"- {log['timestamp'][:16]} | {log['type']} | {log['note'][:60]}")

    prompt = (
        "你是一位北方大田作物植保专家。请根据以下地块档案，为该地块制定长期管理建议，"
        "内容包括：1) 轮作与茬口安排 2) 水肥管理 3) 病虫害预防重点（结合历史病害记录）"
        "4) 田间监测与巡田安排。使用 Markdown 输出，总字数不超过 500 字。\n\n"
        + "\n".join(lines)
    )

    if not AI_API_KEY:
        return {
            "success": True,
            "content": _mock_advice(plot_key, records, profile, logs),
            "source": "mock",
        }

    content, error = _request_ai(
        [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    )
    if content is None:
        return {"success": False, "content": f"AI 服务调用失败：{error}", "source": "error"}
    return {"success": True, "content": content, "source": AI_MODEL}


def _mock_advice(plot_key: str, records: list, profile: dict, logs: list) -> str:
    from collections import Counter

    risks = Counter((r.get("risk_level") or "未知") for r in records)
    last = records[-1] if records else None
    risk_text = " ".join(f"{k}风险 {v} 次" for k, v in risks.items()) or "暂无"
    last_text = (
        f"最近一次诊断风险等级为「{last.get('risk_level') or '未知'}」，需持续监测。"
        if last else "暂无诊断记录，建议先建立监测档案。"
    )
    return f"""当前未配置 AI 服务密钥，以下为规则生成的示例建议（仅演示）。

### {plot_key} 长期管理建议

1. **轮作安排**　建议与豆科作物 2-3 年轮作，降低土传病害基数。
2. **水肥管理**　结合土壤类型（{profile.get('soil_type') or '未填写'}）合理施肥，避免偏施氮肥，雨后及时排涝。
3. **病虫害预防**　本块地历史诊断 {len(records)} 次，风险分布 {risk_text}。{last_text}
4. **监测安排**　生长关键期每 7-10 天巡田一次，重点观察叶部病斑与虫口密度。"""
