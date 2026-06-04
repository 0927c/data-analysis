"""报表生成器：组装图表 + 洞察 + 数据为完整报告。"""

from __future__ import annotations
import json

from backend.utils import convert_numpy


def assemble_report(
    title: str,
    charts: list[dict],
    insights: list[dict],
    data_table: dict | None = None,
) -> dict:
    """将各组件组装为可存储的报告数据。"""
    chart_config = json.dumps([
        {
            'id': c['id'],
            'title': c['title'],
            'type': c['type'],
            'option': c['option'],
        }
        for c in convert_numpy(charts)
    ], ensure_ascii=False)

    data_payload = json.dumps(convert_numpy(data_table), ensure_ascii=False) if data_table else '{}'

    insights_json = json.dumps(convert_numpy(insights), ensure_ascii=False) if insights else '[]'

    # 推断报告类型
    report_type = charts[0]['type'] if charts else 'unknown'

    return {
        'chart_config': chart_config,
        'data_payload': data_payload,
        'insights': insights_json,
        'report_type': report_type,
    }
