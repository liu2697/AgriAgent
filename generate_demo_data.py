"""
农智链 AgriAgent —— 比赛演示数据生成脚本

生成：
  memory/store/plot_history.json   3 个示范地块 × 各 6-8 条历史诊断（时间跨度半年）
  memory/store/task_history.json   至少 3 条示范工单（覆盖待审核/已发布/已关闭）
  memory/store/plot_profiles.json  3 个地块档案（土壤/经纬度/播种时间/农事日志）

运行：
    python generate_demo_data.py

执行完成后自动调用 database.migrate.migrate_json_to_sqlite()，
将演示数据幂等写入 SQLite（data/agragent.db），启动 App 即可见，
无需再手动执行 python database/migrate.py。

幂等设计：
- 演示诊断/农事日志使用固定基准时间 DEMO_NOW（而非 datetime.now()），
  同一批演示数据每次生成的 timestamp 完全一致；
- 演示工单使用固定 task_id（tk_demo_001 ~ tk_demo_004）；
- 配合 migrate.py 的 UNIQUE 约束 + INSERT OR IGNORE，可安全重复运行。

⚠️ 本脚本会覆盖 memory/store/ 下已有 JSON 文件，用于比赛演示一键初始化。
⚠️ 不修改任何业务逻辑，不创建新模块，不删除任何已有数据（真实或旧演示）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 支持 `python generate_demo_data.py` 直接运行：将项目根加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.migrate import migrate_json_to_sqlite

# ------------------------------------------------------------------
# 路径 —— 与 memory/history.py 中的 MEMORY_DIR 保持一致
# ------------------------------------------------------------------
MEMORY_DIR = PROJECT_ROOT / "memory" / "store"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 演示数据固定基准时间
# 所有演示 timestamp 均由 DEMO_NOW - timedelta(days_ago) 推导，
# 保证同一批演示数据每次生成身份完全一致（INSERT OR IGNORE 幂等去重）。
# 仅用于演示数据，不影响运行时真实诊断记录的 datetime.now() 逻辑。
# ------------------------------------------------------------------
DEMO_NOW = datetime(2026, 10, 3, 9, 0, 0)

HISTORY_FILE = MEMORY_DIR / "plot_history.json"
TASK_FILE = MEMORY_DIR / "task_history.json"
PROFILE_FILE = MEMORY_DIR / "plot_profiles.json"


# ------------------------------------------------------------------
# 3 个示范地块配置
# ------------------------------------------------------------------
PLOTS = [
    {
        "location": "河北石家庄·栾城区·示范田",
        "crop": "玉米",
        "area": 120.0,
        "plot_key": "河北石家庄·栾城区·示范田::玉米::120.0亩",
        "soil_type": "壤土",
        "latitude": "38.03",
        "longitude": "114.51",
        "planting_date": "2026-04-20",
        "farmers": ["张建国", "李巧云"],
        "main_disease": "玉米大斑病",
        "history": [
            # (days_ago, growth_stage, risk_level, disease_label, diagnosis_text, recommendation_text)
            (175, "播种期", "无", "玉米大斑病",
             "播前整地阶段，田间未发现明显病斑。土壤墒情良好。",
             "建议深翻灭茬，减少田间菌源；播前使用种衣剂处理。"),
            (140, "苗期", "低", "玉米大斑病",
             "苗期调查发现零星病斑，主要在下部老叶。",
             "建议及时清除病株残体，加强通风透光，田间湿度控制在 60% 以下。"),
            (105, "拔节期", "中", "玉米大斑病",
             "拔节期病斑明显增多，部分植株叶片出现长梭形褐色病斑，数量约 20 株/百株。",
             "推荐使用 25% 吡唑醚菌酯 30ml/亩 兑水叶面喷雾，间隔 7-10 天连喷 2 次。"),
            (70, "抽雄期", "高", "玉米大斑病",
             "抽雄期病斑大面积扩散，上部功能叶受害严重，部分田块病株率达 60%，疑似大斑病暴发。",
             "紧急防治：使用 30% 苯醚甲环唑·丙环唑悬浮剂 40ml/亩 + 25% 吡唑醚菌酯 30ml/亩，混合喷雾。同时建议清理重病株集中深埋。注意安全间隔期不少于 21 天。"),
            (35, "灌浆期", "中", "玉米大斑病",
             "灌浆期复查，经过前期防治，病斑扩展速度减缓，但仍有部分植株下部叶片感病。",
             "可补充喷施 40% 氟硅唑 10ml/亩，保护剩余功能叶；避免大水漫灌，雨后及时排水。"),
            (12, "灌浆期", "低", "玉米大斑病",
             "当前病情平稳，病斑扩展已基本停止，对产量影响可控。",
             "建议做好后期田间管理，适时收获；秸秆集中处理，减少来年菌源。"),
            (0, "成熟期", "无", "玉米大斑病",
             "成熟期调查，病株率已控制在 10% 以下，功能叶保持率良好。",
             "近期天气晴好，可适时收获；收获后秸秆深翻还田或集中处理。"),
        ],
    },
    {
        "location": "内蒙古赤峰·松山区·基地",
        "crop": "马铃薯",
        "area": 80.0,
        "plot_key": "内蒙古赤峰·松山区·基地::马铃薯::80.0亩",
        "soil_type": "沙壤土",
        "latitude": "42.26",
        "longitude": "118.89",
        "planting_date": "2026-05-10",
        "farmers": ["王强"],
        "main_disease": "马铃薯晚疫病",
        "history": [
            (155, "播种期", "无", "马铃薯晚疫病",
             "播种前期，土壤墒情良好，未发现病害迹象。",
             "建议选用脱毒种薯，播前进行晾晒；实行轮作倒茬，避免连作。"),
            (120, "苗期", "无", "马铃薯晚疫病",
             "苗期植株生长整齐，病害未见发生。",
             "保持田间排水通畅，避免积水；合理密植，保证通风。"),
            (85, "现蕾期", "中", "马铃薯晚疫病",
             "现蕾期调查，部分植株叶片出现水渍状暗绿色病斑，阴雨后扩展迅速，疑似晚疫病早期症状。",
             "推荐使用 58% 甲霜灵·锰锌可湿性粉剂 150g/亩 兑水喷雾，重点喷施叶片背面。间隔 7 天连喷 2 次。"),
            (50, "开花期", "高", "马铃薯晚疫病",
             "近期连续阴雨 5 天，田间湿度持续偏高，晚疫病大面积暴发，病株率达 75%，部分植株整株枯死。",
             "紧急处置：1) 发病中心地块喷施 68% 精甲霜·锰锌水分散粒剂 120g/亩；2) 及时清除重病株并集中深埋；3) 增施磷钾肥增强植株抗性；4) 雨后必喷药。注意药剂轮换，避免抗性产生。"),
            (20, "结薯期", "中", "马铃薯晚疫病",
             "经过防治后病情得到控制，仍有部分下部叶片病斑，上部新叶生长正常。",
             "继续保护功能叶，使用 72% 霜脲氰·锰锌 100g/亩；控制田间湿度，注意排水。"),
            (0, "收获期", "低", "马铃薯晚疫病",
             "收获前调查，病株率降至 15% 以下，块茎发育正常。",
             "近期天气晴好，可适时收获；收获前 10 天割秧晒田，减少薯块带菌。"),
        ],
    },
    {
        "location": "山东潍坊·寿光·生产基地",
        "crop": "小麦",
        "area": 200.0,
        "plot_key": "山东潍坊·寿光·生产基地::小麦::200.0亩",
        "soil_type": "壤土",
        "latitude": "36.86",
        "longitude": "118.74",
        "planting_date": "2025-10-15",
        "farmers": ["赵德利", "刘凤华"],
        "main_disease": "小麦条锈病",
        "history": [
            (180, "播种期", "无", "小麦条锈病",
             "播种前期，田间菌源基数较低。",
             "建议选用抗锈品种，合理密植；增施有机肥，提高植株抗性。"),
            (150, "冬前苗期", "低", "小麦条锈病",
             "冬前调查发现极少量病斑，主要在东南向田块。",
             "建议对发病中心进行挑治，使用 15% 三唑酮可湿性粉剂 80g/亩。"),
            (115, "返青期", "中", "小麦条锈病",
             "返青后气温回升，条锈病明显扩展，病株率 25%，叶片上覆大量黄色粉状孢子堆。",
             "建议普治一次，使用 15% 三唑酮可湿性粉剂 80g/亩 + 25% 氰烯菌酯 200ml/亩，混合喷雾。间隔 10 天。"),
            (78, "拔节期", "高", "小麦条锈病",
             "拔节期病情加重，病株率达 70%，主要危害上部功能叶，严重田块叶片提前枯死，严重影响光合作用。",
             "紧急防治：使用 25% 戊唑醇可湿性粉剂 30g/亩 + 25% 氰烯菌酯 250ml/亩 + 99% 磷酸二氢钾 200g/亩叶面喷施。7 天后第二次用药。重病田可适当加量。同时增施叶面肥促进籽粒灌浆。"),
            (42, "灌浆期", "中", "小麦条锈病",
             "灌浆期病情仍较重，上部功能叶受害严重，但经过前期防治后扩展速度有所减缓。",
             "重点保护旗叶和倒二叶，使用 43% 戊唑醇悬浮剂 25ml/亩 + 磷酸二氢钾 200g/亩，叶面喷施一次。避免高温时段作业。"),
            (15, "灌浆后期", "低", "小麦条锈病",
             "灌浆后期调查，病斑基本停止扩展，籽粒灌浆接近完成。",
             "近期天气晴好，避免再喷药；适时收获，注意抢晴晾晒。"),
            (0, "成熟期", "无", "小麦条锈病",
             "成熟期调查，整体病情可控，预计亩产 950-1050 斤，较常年略有下降但总体稳产。",
             "近期适时收获；麦茬深翻处理，减少夏播病害风险。"),
        ],
    },
]


def _plot_key(loc: str, crop: str, area: float) -> str:
    return f"{loc}::{crop}::{round(area, 1)}亩"


def _risk_tag(level: str) -> str:
    return f"综合风险等级：{level}"


def generate_history() -> dict:
    """生成 plot_history.json 数据。"""
    store: dict[str, list[dict]] = {}
    now = DEMO_NOW  # 固定基准时间：保证演示数据身份稳定，重复运行幂等

    for plot in PLOTS:
        key = plot["plot_key"]
        records: list[dict] = []
        for days_ago, stage, risk, disease, diag, rec in plot["history"]:
            ts = (now - timedelta(days=days_ago)).isoformat(timespec="seconds")
            summary = f"# {plot['crop']}{disease}诊断\n\n{diag}\n\n{_risk_tag(risk)}"
            records.append({
                "timestamp": ts,
                "crop": plot["crop"],
                "growth_stage": stage,
                "area": plot["area"],
                "location": plot["location"],
                "diagnosis_summary": summary,
                "recommendation_summary": rec,
                "risk_level": risk,
                "note": "DEMO_DATA",
            })
        store[key] = records
    return store


def generate_tasks() -> dict:
    """生成 task_history.json 数据（覆盖 待审核 / 处理中 / 已发布 / 已关闭 四种状态）。"""
    now = DEMO_NOW  # 固定基准时间：保证演示数据身份稳定，重复运行幂等
    store: dict[str, dict] = {}

    tasks_cfg = [
        # (days_ago, plot_idx, status, farmer, contact, symptoms, risk_level, ai_summary, ai_rec, final_diag, final_rec, reviewer, notes)
        {
            "days": 3, "plot": 0, "status": "待审核",
            "farmer": "张建国", "contact": "139****8801",
            "symptoms": "玉米下部叶片出现大斑病病斑，近期降雨较多",
            "risk_level": "中",
            "ai_content": "### 初步诊断\n玉米大斑病（可能性 90%）\n\n### 防治建议\n建议使用 25% 吡唑醚菌酯 30ml/亩 叶面喷雾。",
            "final_diag": "", "final_rec": "",
            "reviewer": "", "notes": "",
            "publish_time": "", "close_time": "",
        },
        {
            "days": 8, "plot": 1, "status": "处理中",
            "farmer": "王强", "contact": "138****6655",
            "symptoms": "马铃薯叶片水渍状病斑，持续阴雨天气",
            "risk_level": "高",
            "ai_content": "### 初步诊断\n马铃薯晚疫病（可能性 95%）\n\n### 防治建议\n紧急喷施精甲霜·锰锌，清除重病株。",
            "final_diag": "", "final_rec": "",
            "reviewer": "李农技",
            "notes": "已电话联系农户，预计明日到达现场勘察。",
            "publish_time": "", "close_time": "",
        },
        {
            "days": 22, "plot": 2, "status": "已完成",
            "farmer": "赵德利", "contact": "137****4210",
            "symptoms": "小麦叶片上布满黄色粉状斑（条锈病）",
            "risk_level": "高",
            "ai_content": "### 初步诊断\n小麦条锈病（可能性 92%）\n\n### 防治建议\n戊唑醇+氰烯菌酯混合喷雾，重点保护功能叶。",
            "final_diag": "小麦条锈病暴发，病株率 75%，已组织紧急防治。",
            "final_rec": "1. 使用 25% 戊唑醇 30g/亩 + 25% 氰烯菌酯 250ml/亩叶面喷施；2. 7 天后二次用药；3. 增施磷钾肥。",
            "reviewer": "孙站长",
            "notes": "2026-09-06 已现场勘察并发布处置方案，回访病情得到控制。",
            "publish_time": (now - timedelta(days=20)).isoformat(timespec="seconds"),
            "close_time": "",
        },
        {
            "days": 60, "plot": 0, "status": "已关闭",
            "farmer": "李巧云", "contact": "139****8802",
            "symptoms": "玉米拔节期病斑增多",
            "risk_level": "中",
            "ai_content": "### 初步诊断\n玉米大斑病\n\n### 防治建议\n吡唑醚菌酯叶面喷雾。",
            "final_diag": "玉米大斑病中期，已完成防治，病情得到控制。",
            "final_rec": "1. 吡唑醚菌酯 30ml/亩 喷雾；2. 7 天后视情况复喷；3. 清理病株残体。",
            "reviewer": "李农技",
            "notes": "2026-07-30 现场勘察后发布建议，2026-08-20 回访病情平稳，工单关闭。",
            "publish_time": (now - timedelta(days=58)).isoformat(timespec="seconds"),
            "close_time": (now - timedelta(days=18)).isoformat(timespec="seconds"),
        },
    ]

    for idx, cfg in enumerate(tasks_cfg, start=1):
        plot = PLOTS[cfg["plot"]]
        create_time = (now - timedelta(days=cfg["days"])).isoformat(timespec="seconds")
        # 固定 task_id：配合 tasks.task_id UNIQUE + INSERT OR IGNORE 实现幂等
        task_id = f"tk_demo_{idx:03d}"

        task = {
            "task_id": task_id,
            "plot_key": plot["plot_key"],
            "create_time": create_time,
            "update_time": create_time if not cfg.get("publish_time") else cfg["publish_time"],
            "status": cfg["status"],
            "location": plot["location"],
            "crop": plot["crop"],
            "growth_stage": cfg.get("stage", "—"),
            "soil_type": plot["soil_type"],
            "area": plot["area"],
            "farmer_name": cfg["farmer"],
            "contact": cfg["contact"],
            "symptoms": cfg["symptoms"],
            "image_path": "",
            "ai_result": {
                "content": cfg["ai_content"],
                "source": "农智链 AgriAgent · qwen-vl-plus",
                "risk_level": cfg["risk_level"],
                "success": True,
            },
            "final_diagnosis": cfg["final_diag"],
            "final_recommendation": cfg["final_rec"],
            "reviewer": cfg["reviewer"],
            "review_notes": cfg["notes"],
            "publish_time": cfg["publish_time"],
            "close_time": cfg["close_time"],
        }
        store[task_id] = task

    return store


def generate_profiles() -> dict:
    """生成 plot_profiles.json 数据（地块基础档案 + 农事日志）。"""
    store: dict[str, dict] = {}
    now = DEMO_NOW  # 固定基准时间：保证演示数据身份稳定，重复运行幂等

    for plot in PLOTS:
        logs = []
        # 灌溉日志（每 20 天一次）
        for i, days_ago in enumerate(range(160, -5, -20)):
            logs.append({
                "timestamp": (now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
                "log_type": "灌溉",
                "note": f"第 {i+1} 次灌溉，喷灌 40 方/亩",
            })
        # 施肥日志（每月一次）
        for i, days_ago in enumerate(range(150, -10, -30)):
            logs.append({
                "timestamp": (now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
                "log_type": "施肥",
                "note": f"追肥 尿素 25kg/亩 + 复合肥 15kg/亩",
            })
        # 打药日志（病害高发期）
        for days_ago in [78, 50, 35, 20]:
            if days_ago <= 180:
                logs.append({
                    "timestamp": (now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
                    "log_type": "打药",
                    "note": f"防治 {plot['main_disease']}，喷施对应药剂",
                })
        # 巡田日志（每 15 天一次）
        for days_ago in range(170, -1, -15):
            logs.append({
                "timestamp": (now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
                "log_type": "巡田",
                "note": "日常巡田，观察生长情况与病虫害",
            })
        logs.sort(key=lambda x: x["timestamp"])

        store[plot["plot_key"]] = {
            "soil_type": plot["soil_type"],
            "latitude": plot["latitude"],
            "longitude": plot["longitude"],
            "planting_date": plot["planting_date"],
            "farmers": plot["farmers"],
            "updated_at": now.isoformat(timespec="seconds"),
            "logs": logs,
        }

    return store


def main() -> None:
    print("=" * 60)
    print("  农智链 AgriAgent · 比赛演示数据生成脚本")
    print("=" * 60)

    # 1. 地块历史诊断
    history_store = generate_history()
    HISTORY_FILE.write_text(
        json.dumps(history_store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total_records = sum(len(v) for v in history_store.values())
    print(f"\n✅ plot_history.json  → {len(history_store)} 地块 × {total_records} 条历史记录")

    # 2. 工单
    task_store = generate_tasks()
    TASK_FILE.write_text(
        json.dumps(task_store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    status_count: dict[str, int] = {}
    for t in task_store.values():
        status_count[t["status"]] = status_count.get(t["status"], 0) + 1
    print(f"✅ task_history.json  → {len(task_store)} 条工单 {status_count}")

    # 3. 地块档案
    profile_store = generate_profiles()
    PROFILE_FILE.write_text(
        json.dumps(profile_store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total_logs = sum(len(p.get("logs", [])) for p in profile_store.values())
    print(f"✅ plot_profiles.json → {len(profile_store)} 地块档案 · {total_logs} 条农事日志")

    # 4. 预览摘要
    print("\n📋 数据预览")
    print("-" * 40)
    for plot in PLOTS:
        key = plot["plot_key"]
        recs = history_store.get(key, [])
        latest = recs[-1] if recs else {}
        print(f"\n  📍 {plot['location']}")
        print(f"     作物: {plot['crop']} · 面积: {plot['area']}亩")
        print(f"     诊断记录: {len(recs)} 条 · 近半年")
        print(f"     最近风险: {latest.get('risk_level', '—')}")
        print(f"     主发病害: {plot['main_disease']}")

    # 5. 自动迁移 JSON → SQLite（复用现有 migrate 接口，幂等，可重复运行）
    print("\n🔄 正在将演示数据写入 SQLite …")
    migrate_json_to_sqlite(store_dir=MEMORY_DIR, verbose=True)

    print("\n" + "=" * 60)
    print("  演示数据生成完成！")
    print("  启动系统: streamlit run app.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
