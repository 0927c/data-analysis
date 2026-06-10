"""长记忆服务 — 整合用户偏好、分析历史、数据源元数据、对话上下文四种记忆。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import UserPreference, AnalysisHistory, DatasourceMetadata, Session
from backend.config import settings


class MemoryService:
    """统一记忆服务入口。

    四种记忆类型：
    A. 用户偏好记忆 — 记住常用分析维度和筛选条件
    B. 分析历史记忆 — 保存分析结论，后续可检索引用
    C. 数据源元数据记忆 — 自动提取字段结构和数据特征
    D. 对话上下文增强 — 跨轮引用、对话摘要
    """

    def __init__(self, db_session_factory, file_kv_store=None):
        """
        Args:
            db_session_factory: 异步 session 工厂（如 async_session）
            file_kv_store: 可选的文件 KV 存储（internal.memory.store.MemoryStore）
        """
        self._session_factory = db_session_factory
        self._kv = file_kv_store

    # ================================================================
    # A. 用户偏好记忆
    # ================================================================

    async def get_user_preferences(self, user_id: int) -> dict:
        """获取用户所有偏好，返回 {key: value} 字典。"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserPreference).where(UserPreference.user_id == user_id)
            )
            prefs = result.scalars().all()
            return {p.preference_key: json.loads(p.preference_value) for p in prefs}

    async def track_usage(self, user_id: int, dimension: str, metadata: dict = None):
        """追踪某分析维度的使用次数（每次分析后调用）。"""
        if not getattr(settings, "MEMORY_ENABLED", True):
            return

        async with self._session_factory() as session:
            key = "preferred_dimensions"
            result = await session.execute(
                select(UserPreference).where(
                    UserPreference.user_id == user_id,
                    UserPreference.preference_key == key,
                )
            )
            pref = result.scalar_one_or_none()

            if pref:
                current = json.loads(pref.preference_value)
                current[dimension] = current.get(dimension, 0) + 1
                pref.preference_value = json.dumps(current, ensure_ascii=False)
                pref.usage_count = pref.usage_count + 1
                pref.updated_at = datetime.now(timezone.utc)
            else:
                pref = UserPreference(
                    user_id=user_id,
                    preference_key=key,
                    preference_value=json.dumps({dimension: 1}, ensure_ascii=False),
                    usage_count=1,
                )
                session.add(pref)

            # 同时记录元数据（最近使用的数据源等）
            if metadata:
                meta_key = "usage_metadata"
                meta_result = await session.execute(
                    select(UserPreference).where(
                        UserPreference.user_id == user_id,
                        UserPreference.preference_key == meta_key,
                    )
                )
                meta_pref = meta_result.scalar_one_or_none()
                if meta_pref:
                    current_meta = json.loads(meta_pref.preference_value)
                    # 记录最近使用的数据源
                    ds_id = metadata.get("datasource_id")
                    if ds_id is not None:
                        recent = current_meta.get("recent_datasource_ids", [])
                        if ds_id not in recent:
                            recent.append(ds_id)
                            recent = recent[-10:]  # 只保留最近 10 个
                        current_meta["recent_datasource_ids"] = recent
                    meta_pref.preference_value = json.dumps(current_meta, ensure_ascii=False)
                    meta_pref.updated_at = datetime.now(timezone.utc)
                else:
                    session.add(UserPreference(
                        user_id=user_id,
                        preference_key=meta_key,
                        preference_value=json.dumps(metadata, ensure_ascii=False),
                        usage_count=1,
                    ))

            await session.commit()

    async def suggest_filters(self, user_id: int) -> dict:
        """基于历史使用推荐默认筛选条件。"""
        prefs = await self.get_user_preferences(user_id)
        suggestions = {}

        # 基于常用维度推荐
        dimensions = prefs.get("preferred_dimensions", {})
        threshold = getattr(settings, "MEMORY_PREFERENCE_THRESHOLD", 3)

        # 如果某个维度使用次数超过阈值，认为用户关注该维度
        high_freq_dims = [k for k, v in dimensions.items() if v >= threshold]
        if high_freq_dims:
            suggestions["frequent_dimensions"] = high_freq_dims

        return suggestions

    # ================================================================
    # B. 分析历史记忆
    # ================================================================

    async def save_conclusion(
        self,
        user_id: int,
        session_id: int,
        datasource_id: Optional[int],
        analysis_type: str,
        summary: str,
        findings: list = None,
        snapshot: dict = None,
        tags: list = None,
    ):
        """保存一次分析的结论。"""
        if not getattr(settings, "MEMORY_ENABLED", True):
            return
        if not getattr(settings, "MEMORY_AUTO_SAVE_HISTORY", True):
            return

        async with self._session_factory() as session:
            history = AnalysisHistory(
                user_id=user_id,
                session_id=session_id,
                datasource_id=datasource_id,
                analysis_type=analysis_type,
                summary=summary[:1000],  # 限制长度
                key_findings=json.dumps(findings or [], ensure_ascii=False),
                data_snapshot=json.dumps(snapshot or {}, ensure_ascii=False),
                tags=",".join(tags or []),
            )
            session.add(history)
            await session.commit()

    async def search_relevant(
        self,
        user_id: int,
        query_text: str,
        datasource_id: Optional[int] = None,
        limit: int = 3,
    ) -> list[dict]:
        """关键词检索相关历史分析。"""
        async with self._session_factory() as session:
            # 从查询文本中提取关键词（简单分词）
            keywords = self._extract_keywords(query_text)

            if not keywords:
                return []

            # 构建查询：在 summary 和 tags 中搜索关键词
            conditions = []
            for kw in keywords:
                pattern = f"%{kw}%"
                conditions.append(AnalysisHistory.summary.like(pattern))
                conditions.append(AnalysisHistory.tags.like(pattern))

            stmt = (
                select(AnalysisHistory)
                .where(AnalysisHistory.user_id == user_id)
                .where(or_(*conditions))
            )

            if datasource_id is not None:
                stmt = stmt.where(AnalysisHistory.datasource_id == datasource_id)

            stmt = stmt.order_by(AnalysisHistory.created_at.desc()).limit(limit)

            result = await session.execute(stmt)
            histories = result.scalars().all()

            return [
                {
                    "id": h.id,
                    "analysis_type": h.analysis_type,
                    "summary": h.summary,
                    "tags": h.tags.split(",") if h.tags else [],
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                }
                for h in histories
            ]

    async def get_patterns(self, user_id: int, pattern_type: str = "recurring") -> list[dict]:
        """获取历史模式（如反复出现的故障类型、SLA 趋势等）。"""
        async with self._session_factory() as session:
            stmt = (
                select(AnalysisHistory.analysis_type, func.count().label("cnt"))
                .where(AnalysisHistory.user_id == user_id)
                .group_by(AnalysisHistory.analysis_type)
                .order_by(func.count().desc())
                .limit(10)
            )
            result = await session.execute(stmt)
            rows = result.all()
            return [{"type": r[0], "count": r[1]} for r in rows]

    # ================================================================
    # C. 数据源元数据记忆
    # ================================================================

    async def extract_and_save(self, datasource_id: int, df, col_map: dict = None):
        """从 DataFrame 自动提取元数据并保存。"""
        import pandas as pd

        # 字段结构
        field_structure = []
        for col in df.columns:
            col_data = df[col]
            field_info = {
                "name": col,
                "type": str(col_data.dtype),
                "unique_count": int(col_data.nunique()),
                "null_count": int(col_data.isna().sum()),
                "null_rate": round(float(col_data.isna().mean()), 4),
                "top_values": [],
            }
            # 取 top 5 值
            try:
                top = col_data.value_counts().head(5)
                field_info["top_values"] = [
                    {"value": str(k), "count": int(v)} for k, v in top.items()
                ]
            except Exception:
                pass
            field_structure.append(field_info)

        # 数据特征
        total_rows = len(df)
        column_count = len(df.columns)

        # 尝试提取时间范围
        time_range = {}
        for date_col in ["created_at", "创建时间"]:
            if date_col in df.columns:
                try:
                    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
                    if len(dates) > 0:
                        time_range = {
                            "min": str(dates.min()),
                            "max": str(dates.max()),
                        }
                        break
                except Exception:
                    pass

        data_characteristics = {
            "total_rows": total_rows,
            "column_count": column_count,
            "time_range": time_range,
        }

        # 质量指标
        total_cells = total_rows * column_count
        total_nulls = int(df.isna().sum().sum())
        quality_metrics = {
            "total_cells": total_cells,
            "total_nulls": total_nulls,
            "overall_null_rate": round(total_nulls / max(total_cells, 1), 4),
            "duplicate_rows": int(df.duplicated().sum()),
        }

        # 关键分布（如果存在相关列）
        key_distributions = {}
        for col_name, dist_key in [
            ("status", "status_dist"),
            ("service_group", "service_group_dist"),
            ("responsible_person", "assignee_dist"),
            ("requester_dept", "department_dist"),
        ]:
            if col_name in df.columns:
                dist = df[col_name].value_counts().head(10)
                key_distributions[dist_key] = {
                    str(k): int(v) for k, v in dist.items()
                }

        # 保存到数据库
        metadata_json = {
            "field_structure": json.dumps(field_structure, ensure_ascii=False, default=str),
            "data_characteristics": json.dumps(data_characteristics, ensure_ascii=False, default=str),
            "quality_metrics": json.dumps(quality_metrics, ensure_ascii=False),
            "key_distributions": json.dumps(key_distributions, ensure_ascii=False),
        }

        async with self._session_factory() as session:
            result = await session.execute(
                select(DatasourceMetadata).where(
                    DatasourceMetadata.datasource_id == datasource_id
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                for k, v in metadata_json.items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.now(timezone.utc)
            else:
                meta = DatasourceMetadata(
                    datasource_id=datasource_id,
                    **metadata_json,
                )
                session.add(meta)

            await session.commit()

        return {
            "field_structure": field_structure,
            "data_characteristics": data_characteristics,
            "quality_metrics": quality_metrics,
            "key_distributions": key_distributions,
        }

    async def get_metadata(self, datasource_id: int) -> Optional[dict]:
        """获取数据源元数据。"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(DatasourceMetadata).where(
                    DatasourceMetadata.datasource_id == datasource_id
                )
            )
            meta = result.scalar_one_or_none()
            if not meta:
                return None

            def _safe_json(val):
                try:
                    return json.loads(val) if val else {}
                except (json.JSONDecodeError, TypeError):
                    return {}

            return {
                "datasource_id": meta.datasource_id,
                "field_structure": _safe_json(meta.field_structure),
                "data_characteristics": _safe_json(meta.data_characteristics),
                "quality_metrics": _safe_json(meta.quality_metrics),
                "key_distributions": _safe_json(meta.key_distributions),
                "extracted_at": meta.extracted_at.isoformat() if meta.extracted_at else None,
            }

    # ================================================================
    # D. 对话上下文增强
    # ================================================================

    async def update_session_summary(self, session_id: int, message: str, role: str):
        """增量更新对话摘要。"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(Session).where(Session.id == session_id)
            )
            sess = result.scalar_one_or_none()
            if not sess:
                return

            current_summary = sess.context_summary or ""
            prefix = f"[用户]" if role == "user" else "[助手]"
            entry = f"{prefix}: {message[:200]}\n"

            # 保留最近的摘要（限制总长度在 3000 字符内）
            new_summary = current_summary + entry
            if len(new_summary) > 3000:
                # 截断前面的内容，保留最近的
                lines = new_summary.split("\n")
                # 保留最后 15 行
                lines = lines[-15:]
                new_summary = "\n".join(lines)

            sess.context_summary = new_summary
            await session.commit()

    async def resolve_references(self, session_id: int, message: str) -> dict:
        """检测消息中的跨轮引用（如"刚才的分析""上次的结果"）。"""
        reference_patterns = {
            "刚才": "last",
            "上次": "previous",
            "之前": "previous",
            "那个分析": "last_analysis",
            "那个报表": "last_report",
            "那个图表": "last_chart",
            "刚说的": "last",
            "前面说的": "earlier",
        }

        detected = {}
        for pattern, ref_type in reference_patterns.items():
            if pattern in message:
                detected["reference_type"] = ref_type
                detected["pattern"] = pattern
                break

        if not detected:
            return {}

        # 获取对话摘要来解析引用
        async with self._session_factory() as session_db:
            result = await session_db.execute(
                select(Session.context_summary).where(Session.id == session_id)
            )
            summary = result.scalar_one_or_none()

        if summary:
            detected["context_summary"] = summary

        return detected

    # ================================================================
    # 主入口：富化上下文
    # ================================================================

    async def enrich_context(
        self,
        session_id: int,
        user_id: int,
        message: str,
        primary_datasource_id: Optional[int] = None,
    ) -> dict:
        """记忆富化主入口 — 汇总四种记忆返回。

        在 chat router 的意图解析前调用。
        """
        if not getattr(settings, "MEMORY_ENABLED", True):
            return {}

        result = {
            "suggested_filters": {},
            "relevant_analyses": [],
            "datasource_metadata": None,
            "session_summary": None,
            "resolved_references": {},
        }

        # A. 用户偏好
        result["suggested_filters"] = await self.suggest_filters(user_id)

        # B. 分析历史（用当前消息检索相关历史）
        result["relevant_analyses"] = await self.search_relevant(
            user_id=user_id,
            query_text=message,
            datasource_id=primary_datasource_id,
            limit=3,
        )

        # C. 数据源元数据
        if primary_datasource_id is not None:
            result["datasource_metadata"] = await self.get_metadata(primary_datasource_id)

        # D. 对话上下文增强
        result["resolved_references"] = await self.resolve_references(session_id, message)

        # 获取对话摘要
        async with self._session_factory() as session_db:
            sess_result = await session_db.execute(
                select(Session.context_summary).where(Session.id == session_id)
            )
            result["session_summary"] = sess_result.scalar_one_or_none()

        return result

    # ================================================================
    # 工具方法
    # ================================================================

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """从文本中提取关键词（简单中文分词）。"""
        # 简单策略：按标点和空格分割，过滤短词
        import re
        # 移除标点
        text = re.sub(r'[，。！？、；：""''（）【】《》\s]+', ' ', text)
        words = [w.strip() for w in text.split() if len(w.strip()) >= 2]

        # ITSM 领域关键词
        itsm_keywords = [
            '工单', '状态', '服务组', '责任人', '部门', '故障', '原因',
            'SLA', '趋势', '挂起', '评价', '满意度', '解决', '时效',
            '排名', '分布', '占比', 'KPI', '分析', '报表', '周报', '月报',
            '重复', '高频', '运维', '质量', '症状', '方案', '请求人',
        ]
        found = [w for w in words if w in itsm_keywords]

        # 如果没有匹配到领域关键词，返回原始词（至少2个字符）
        return found if found else words[:5]
