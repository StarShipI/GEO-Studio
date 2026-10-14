"""告警：负面提及 / 可见度骤降 推送飞书 + 写 alerts 表。

调度器会定时调用 check_all_brands()：扫近 24h 负面提及（>= 品牌配置阈值）与
可见度环比骤降（对比最近两次快照，>= 品牌配置阈值），
若该品牌还没有未解决的同类告警，则新建 alert 并推飞书群。
"""
from __future__ import annotations

import logging

import requests

from app.config import settings
from app.database import SessionLocal
from app.models import Alert, Brand
from app.services.metrics import recent_negative_mentions
from app.services.snapshot import last_two_visibility

logger = logging.getLogger(__name__)


def send_feishu(text: str) -> bool:
    if not settings.feishu_webhook:
        logger.info("未配置 GEO_FEISHU_WEBHOOK，跳过推送")
        return False
    try:
        resp = requests.post(
            settings.feishu_webhook,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as exc:
        logger.error("飞书推送失败: %s", exc)
        return False


def _alert_exists(db, brand_id: int, alert_type: str) -> bool:
    return bool(
        db.query(Alert).filter(
            Alert.brand_id == brand_id,
            Alert.type == alert_type,
            Alert.is_resolved.is_(False),
        ).first()
    )


def check_all_brands() -> list[int]:
    """调度器入口：全品牌扫负面提及与可见度骤降并告警。返回新建告警的品牌 id 列表。"""
    db = SessionLocal()
    try:
        created: list[int] = []
        for brand in db.query(Brand).all():
            # 负面提及（>= 品牌配置阈值）
            negs = recent_negative_mentions(db, brand.id, hours=24)
            threshold = brand.alert_negative_threshold or 1
            if len(negs) >= threshold and not _alert_exists(db, brand.id, "negative_mention"):
                detail_lines = [f"{n['query']}（{n['engine']}）：{n['context'][:80]}" for n in negs[:3]]
                detail = "\n".join(detail_lines)
                db.add(Alert(
                    brand_id=brand.id,
                    type="negative_mention",
                    severity="high",
                    detail=detail,
                ))
                db.commit()
                send_feishu(f"⚠️ GEO 告警｜{brand.name} 出现负面提及（近24h {len(negs)} 条）\n{detail}")
                created.append(brand.id)

            # 可见度骤降（对比最近两次快照）
            prev_v, curr_v = last_two_visibility(db, brand.id)
            if prev_v is not None and curr_v is not None and prev_v > curr_v:
                drop = prev_v - curr_v
                if drop >= (brand.alert_visibility_drop or 0.2) and not _alert_exists(db, brand.id, "visibility_drop"):
                    db.add(Alert(
                        brand_id=brand.id,
                        type="visibility_drop",
                        severity="high",
                        detail=f"AI 可见度由 {prev_v:.1%} 降至 {curr_v:.1%}（降幅 {drop:.1%}，阈值 "
                               f"{(brand.alert_visibility_drop or 0.2):.0%}）",
                    ))
                    db.commit()
                    send_feishu(f"⚠️ GEO 告警｜{brand.name} AI 可见度骤降 {drop:.1%}")
                    created.append(brand.id)
        return created
    finally:
        db.close()
