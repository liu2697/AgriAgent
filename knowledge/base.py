from __future__ import annotations

import re
import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class KnowledgeEntry:
    id: str
    crop: str
    disease: str
    aliases: list[str] = field(default_factory=list)
    symptoms: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    prevention: list[str] = field(default_factory=list)
    registered_pesticides: list[str] = field(default_factory=list)
    source: str = "内置农业知识库 v1.0"
    url: str = ""


_KNOWLEDGE_DB: list[KnowledgeEntry] = [
    KnowledgeEntry(
        id="KM001",
        crop="玉米",
        disease="玉米大斑病",
        aliases=["大斑病", "叶枯病", "玉米褐斑病"],
        symptoms=["叶片出现长梭形褐色病斑", "病斑中央灰褐色边缘暗褐色", "严重时叶片枯死"],
        conditions=["高温高湿", "连阴雨", "氮肥过量种植过密"],
        prevention=["选用抗病品种", "轮作倒茬", "清除田间病残体", "合理密植"],
        registered_pesticides=["苯醚甲环唑·丙环唑", "吡唑醚菌酯", "戊唑醇"],
    ),
    KnowledgeEntry(
        id="KM002",
        crop="玉米",
        disease="玉米蚜虫",
        aliases=["蜜虫", "腻虫"],
        symptoms=["心叶被汁液", "叶片卷曲黄化", "蜜露诱发煤污病"],
        conditions=["干旱少雨", "种群繁殖快"],
        prevention=["黄板诱杀", "保护天敌瓢虫草蛉", "种衣剂拌种"],
        registered_pesticides=["吡虫啉", "噻虫嗪", "啶虫脒"],
    ),
    KnowledgeEntry(
        id="KM003",
        crop="小麦",
        disease="小麦条锈病",
        aliases=["条锈", "黄疸"],
        symptoms=["叶片出现鲜黄色夏孢子堆", "沿叶脉成行排列成虚线状", "后期叶枯"],
        conditions=["低温高湿", "早春气温回升快"],
        prevention=["种植抗锈品种", "秋苗早发现早防治", "合理施肥"],
        registered_pesticides=["三唑酮", "戊唑醇", "氟环唑"],
    ),
    KnowledgeEntry(
        id="KM004",
        crop="小麦",
        disease="小麦赤霉病",
        aliases=["红麦头", "烂麦头"],
        symptoms=["小穗颖壳基部变褐", "渐及整穗粉红霉层", "籽粒干瘪有霉味"],
        conditions=["抽穗扬花期连续阴雨", "相对湿度>80%"],
        prevention=["选用抗病品种", "扬花初期抢雨隙打药", "增施磷钾肥"],
        registered_pesticides=["氰烯菌酯", "戊唑醇·咪鲜胺", "吡唑醚菌酯"],
    ),
    KnowledgeEntry(
        id="KM005",
        crop="马铃薯",
        disease="马铃薯晚疫病",
        aliases=["晚疫", "黑胫病"],
        symptoms=["叶片出现暗褐水渍状病斑", "扩大后病斑边缘有白色霉层", "块茎内部变褐坏死"],
        conditions=["气温15-25℃", "相对湿度>95%持续48小时以上"],
        prevention=["选用无病种薯", "高垄栽培", "及时清除中心病株"],
        registered_pesticides=["霜脲氰·氰霜唑", "吡唑醚菌酯·代森联", "氟吡菌胺·霜脲氰"],
    ),
    KnowledgeEntry(
        id="KM006",
        crop="大豆",
        disease="大豆霜霉病",
        aliases=["霜霉", "龙头病"],
        symptoms=["叶片正面出现圆形或不规则黄褐斑点", "背面生灰白色霉层", "严重时叶片枯黄脱落"],
        conditions=["高湿低温", "播种带菌种子"],
        prevention=["选用抗病品种", "种子消毒", "合理密植通风透光"],
        registered_pesticides=["甲霜灵·锰锌", "霜脲氰·氰霜唑", "代森锰锌"],
    ),
    KnowledgeEntry(
        id="KM007",
        crop="棉花",
        disease="棉花枯萎病",
        aliases=["枯萎", "半边黄"],
        symptoms=["叶片自下而上黄化萎蔫", "维管束变褐色", "病株矮小甚至枯死"],
        conditions=["连作棉田", "土温25-30℃发病重"],
        prevention=["选用抗枯耐萎品种", "与禾本科作物轮作3年以上", "增施有机肥"],
        registered_pesticides=["恶霉灵", "枯草芽孢杆菌", "咯菌腈"],
    ),
    KnowledgeEntry(
        id="KM008",
        crop="花生",
        disease="花生褐斑病",
        aliases=["褐斑", "叶斑病"],
        symptoms=["叶片出现圆形褐色至黑色病斑", "病斑边缘有黄色晕圈", "严重时叶片脱落"],
        conditions=["高温高湿", "7-8月多雨年份"],
        prevention=["选用抗病品种", "水旱轮作", "收获后清除病残体"],
        registered_pesticides=["戊唑醇", "苯醚甲环唑", "吡唑醚菌酯"],
    ),
    KnowledgeEntry(
        id="KM009",
        crop="向日葵",
        disease="向日葵菌核病",
        aliases=["菌核", "烂盘病"],
        symptoms=["根茎基部腐烂", "盘部褐色凹陷病斑", "后期黑色菌核"],
        conditions=["花期多雨高湿", "连作重茬"],
        prevention=["与禾本科轮作5年以上", "合理稀植", "花期及时排水"],
        registered_pesticides=["腐霉利", "异菌脲", "菌核净"],
    ),
    KnowledgeEntry(
        id="KM010",
        crop="高粱",
        disease="高粱炭疽病",
        aliases=["炭疽", "叶炭疽病"],
        symptoms=["叶片出现卵圆形红褐色病斑", "中央生小黑点", "严重时叶片枯死"],
        conditions=["高温高湿", "暴风雨后伤口多"],
        prevention=["种植抗病品种", "深翻灭茬", "合理施肥避免偏施氮肥"],
        registered_pesticides=["咪鲜胺", "吡唑醚菌酯", "苯醚甲环唑"],
    ),
]


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s，。、；：,.;:()（）\[\]【】\"'`]+", text.lower()) if t]


def _score(entry: KnowledgeEntry, query_tokens: list[str], crop_hint: Optional[str] = None) -> float:
    score = 0.0
    if crop_hint and entry.crop == crop_hint:
        score += 5.0

    hay = " ".join(
        [entry.disease] + entry.aliases + entry.symptoms + entry.conditions
    ).lower()

    for tok in query_tokens:
        if not tok:
            continue
        if tok in hay:
            score += 2.0
        elif any(tok in hay_word for hay_word in hay.split() if len(tok) >= 2):
            score += 1.0
    return score


def search_knowledge(query: str, crop_hint: Optional[str] = None, top_k: int = 3) -> list[dict]:
    """
    本地农业知识库检索。
    :param query: 农户描述 / 初步诊断关键词
    :param crop_hint: 作物类型，用于加权排序
    :param top_k: 返回 Top-K
    :return: 按相关性排序的知识库条目（dict）
    """
    tokens = _tokenize(query)
    if not tokens:
        tokens = _tokenize(crop_hint or "")

    scored = [(_score(e, tokens, crop_hint), e) for e in _KNOWLEDGE_DB]
    scored = [(s, e) for s, e in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, entry in scored[:top_k]:
        d = asdict(entry)
        d["relevance_score"] = round(score, 2)
        results.append(d)
    return results


def dump_knowledge() -> str:
    return json.dumps([asdict(e) for e in _KNOWLEDGE_DB], ensure_ascii=False, indent=2)


__all__ = ["search_knowledge", "KnowledgeEntry", "dump_knowledge"]
