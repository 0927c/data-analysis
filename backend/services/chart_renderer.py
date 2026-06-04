"""将结构化数据转为 ECharts option JSON，替代 AntV Studio 外部 API。"""

from __future__ import annotations
from typing import Optional


# 暗色主题色板
COLORS = [
    '#00d4ff', '#ff6b6b', '#ffd93d', '#6bcb77', '#9b59b6',
    '#e67e22', '#1abc9c', '#e74c3c', '#3498db', '#f39c12',
    '#2ecc71', '#8e44ad', '#16a085', '#d35400', '#2980b9',
    '#c0392b', '#27ae60', '#7f8c8d',
]

TOOLTIP_STYLE = {
    'backgroundColor': 'rgba(26, 40, 55, 0.95)',
    'borderColor': '#2a3f54',
    'borderWidth': 1,
    'textStyle': {'color': '#e0e8f0', 'fontSize': 13},
    'padding': [10, 14],
    'extraCssText': 'box-shadow: 0 4px 16px rgba(0,0,0,0.3); border-radius: 8px;',
}

AXIS_STYLE = {
    'axisLine': {'lineStyle': {'color': '#2a3f54'}},
    'axisLabel': {'color': '#8899aa'},
    'splitLine': {'lineStyle': {'color': '#1a2f44'}},
}

ANIMATION_DEFAULTS = {
    'animationDuration': 800,
    'animationEasing': 'cubicOut',
}


def _gradient_bar(start: str = '#0099cc', end: str = '#00d4ff') -> dict:
    return {
        'color': {
            'type': 'linear',
            'x': 0, 'y': 0, 'x2': 1, 'y2': 0,
            'colorStops': [
                {'offset': 0, 'color': start},
                {'offset': 1, 'color': end},
            ],
        }
    }


def render_horizontal_bar(labels: list, values: list, title: str = '', color: Optional[str] = None) -> dict:
    """横向柱状图（产品线分布等）。"""
    rev_labels = list(reversed(labels))
    rev_values = list(reversed(values))
    grad = color or ('#0099cc', '#00d4ff')
    item_style = _gradient_bar(*grad) if isinstance(grad, tuple) else grad

    return {
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}, **TOOLTIP_STYLE},
        'grid': {'left': 80, 'right': 60, 'top': 10, 'bottom': 30},
        'xAxis': {'type': 'value', **AXIS_STYLE},
        'yAxis': {
            'type': 'category',
            'data': rev_labels,
            'axisLine': {'lineStyle': {'color': '#2a3f54'}},
            'axisLabel': {'color': '#e0e8f0', 'fontSize': 12},
        },
        'series': [{
            'type': 'bar',
            'data': rev_values,
            'itemStyle': {
                **item_style,
                'borderRadius': [0, 4, 4, 0],
            },
            'barWidth': 18,
            'label': {'show': True, 'position': 'right', 'color': '#e0e8f0', 'fontSize': 11},
            **ANIMATION_DEFAULTS,
        }],
    }


def render_pie(labels: list, values: list, title: str = '') -> dict:
    """环形饼图（原因大类占比等）。"""
    data = [
        {'name': l, 'value': v, 'itemStyle': {'color': COLORS[i % len(COLORS)]}}
        for i, (l, v) in enumerate(zip(labels, values))
    ]
    return {
        'tooltip': {
            'trigger': 'item',
            'formatter': '{b}: {c}件 ({d}%)',
            **TOOLTIP_STYLE,
        },
        'legend': {
            'orient': 'vertical', 'right': 10, 'top': 'center',
            'textStyle': {'color': '#e0e8f0', 'fontSize': 12},
            'itemWidth': 12, 'itemHeight': 12,
        },
        'series': [{
            'type': 'pie',
            'radius': ['40%', '70%'],
            'center': ['40%', '50%'],
            'avoidLabelOverlap': True,
            'itemStyle': {'borderRadius': 6, 'borderColor': '#1a2837', 'borderWidth': 2},
            'label': {'show': True, 'color': '#e0e8f0', 'fontSize': 11, 'formatter': '{b}\n{d}%'},
            'labelLine': {'lineStyle': {'color': '#2a3f54'}},
            'data': data,
            **ANIMATION_DEFAULTS,
        }],
    }


def render_bar(labels: list, values: list, title: str = '', horizontal: bool = False) -> dict:
    """纵向/横向柱状图（不良类型 TOP15 等）。"""
    if horizontal:
        return render_horizontal_bar(labels, values, title)

    item_style_data = []
    for i, v in enumerate(values):
        if v >= 200:
            grad = _gradient_bar('#cc3333', '#ff6b6b')
        elif v >= 80:
            grad = _gradient_bar('#cc8800', '#ffd93d')
        else:
            grad = _gradient_bar('#0099cc', '#00d4ff')
        item_style_data.append({
            'value': v,
            'itemStyle': {**grad, 'borderRadius': [0, 4, 4, 0]},
        })

    return {
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}, **TOOLTIP_STYLE},
        'grid': {'left': 110, 'right': 60, 'top': 10, 'bottom': 30},
        'xAxis': {'type': 'value', **AXIS_STYLE},
        'yAxis': {
            'type': 'category',
            'data': list(reversed(labels)),
            'axisLine': {'lineStyle': {'color': '#2a3f54'}},
            'axisLabel': {'color': '#e0e8f0', 'fontSize': 12},
        },
        'series': [{
            'type': 'bar',
            'data': item_style_data,
            'barWidth': 16,
            'label': {'show': True, 'position': 'right', 'color': '#e0e8f0', 'fontSize': 11},
            **ANIMATION_DEFAULTS,
        }],
    }


def render_stacked_bar(products: list, causes: dict, title: str = '') -> dict:
    """堆叠柱状图（产品线 × 原因交叉）。"""
    cause_names = list(causes.keys())
    series = []
    for i, cn in enumerate(cause_names):
        series.append({
            'name': cn,
            'type': 'bar',
            'stack': 'total',
            'emphasis': {'focus': 'series'},
            'itemStyle': {'color': COLORS[i % len(COLORS)]},
            'data': [int(causes[cn].get(p, 0)) for p in products],
            **ANIMATION_DEFAULTS,
        })

    return {
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}, **TOOLTIP_STYLE},
        'legend': {
            'top': 0,
            'textStyle': {'color': '#e0e8f0', 'fontSize': 11},
            'itemWidth': 12, 'itemHeight': 12,
        },
        'grid': {'left': 50, 'right': 20, 'top': 40, 'bottom': 60},
        'xAxis': {
            'type': 'category',
            'data': products,
            'axisLabel': {'color': '#e0e8f0', 'fontSize': 11, 'rotate': 30},
            'axisLine': {'lineStyle': {'color': '#2a3f54'}},
        },
        'yAxis': {'type': 'value', **AXIS_STYLE},
        'series': series,
    }


def render_rose(labels: list, values: list, title: str = '') -> dict:
    """南丁格尔玫瑰图（制造/研发原因细分）。"""
    data = [
        {'name': l, 'value': v, 'itemStyle': {'color': COLORS[i % len(COLORS)]}}
        for i, (l, v) in enumerate(zip(labels, values))
    ]
    return {
        'tooltip': {
            'trigger': 'item',
            'formatter': '{b}: {c}件 ({d}%)',
            **TOOLTIP_STYLE,
        },
        'legend': {
            'orient': 'vertical', 'right': 0, 'top': 'middle',
            'textStyle': {'color': '#e0e8f0', 'fontSize': 11},
            'itemWidth': 10, 'itemHeight': 10,
        },
        'series': [{
            'type': 'pie',
            'radius': ['35%', '65%'],
            'center': ['35%', '50%'],
            'roseType': 'radius',
            'itemStyle': {'borderRadius': 5, 'borderColor': '#1a2837', 'borderWidth': 2},
            'label': {'color': '#e0e8f0', 'fontSize': 10, 'formatter': '{b}'},
            'data': data,
            **ANIMATION_DEFAULTS,
        }],
    }


def render_line(dates: list, series_list: list[dict], title: str = '') -> dict:
    """平滑面积线图（趋势分析）。
    series_list: [{'name': str, 'data': list[float], 'color': str}]
    """
    series = []
    for i, s in enumerate(series_list):
        series.append({
            'name': s['name'],
            'type': 'line',
            'smooth': True,
            'symbol': 'circle',
            'symbolSize': 6,
            'itemStyle': {'color': s.get('color', COLORS[i % len(COLORS)])},
            'areaStyle': {
                'opacity': 0.15,
                'color': {
                    'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                    'colorStops': [
                        {'offset': 0, 'color': s.get('color', COLORS[i % len(COLORS)])},
                        {'offset': 1, 'color': 'rgba(0,0,0,0)'},
                    ],
                },
            },
            'data': s['data'],
            **ANIMATION_DEFAULTS,
        })

    return {
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'line'}, **TOOLTIP_STYLE},
        'legend': {
            'top': 0,
            'textStyle': {'color': '#e0e8f0', 'fontSize': 12},
            'itemWidth': 14, 'itemHeight': 14,
        },
        'grid': {'left': 60, 'right': 30, 'top': 40, 'bottom': 30},
        'xAxis': {
            'type': 'category',
            'data': dates,
            'axisLabel': {'color': '#8899aa', 'fontSize': 11, 'rotate': 20},
            'axisLine': {'lineStyle': {'color': '#2a3f54'}},
        },
        'yAxis': {'type': 'value', **AXIS_STYLE},
        'series': series,
    }


def render_gauge(value: float, max_val: float, title: str = '', label: str = '') -> dict:
    """半圆仪表盘（KPI 指标）。"""
    pct = (value / max_val * 100) if max_val > 0 else 0
    if pct < 50:
        color = '#6bcb77'
    elif pct < 80:
        color = '#ffd93d'
    else:
        color = '#ff6b6b'

    return {
        'tooltip': {
            'formatter': '{a}: {b}',
            **TOOLTIP_STYLE,
        },
        'series': [{
            'name': title or '指标',
            'type': 'gauge',
            'startAngle': 180,
            'endAngle': 0,
            'min': 0,
            'max': max_val,
            'splitNumber': 5,
            'axisLine': {
                'lineStyle': {
                    'width': 16,
                    'color': [
                        (0.5, '#6bcb77'),
                        (0.8, '#ffd93d'),
                        (1, '#ff6b6b'),
                    ],
                },
            },
            'pointer': {
                'itemStyle': {'color': color},
                'width': 4,
            },
            'axisTick': {'distance': -16, 'length': 6, 'lineStyle': {'color': '#fff', 'width': 1}},
            'splitLine': {'distance': -20, 'length': 14, 'lineStyle': {'color': '#fff', 'width': 2}},
            'axisLabel': {'color': '#8899aa', 'fontSize': 11, 'distance': -12},
            'detail': {
                'valueAnimation': True,
                'formatter': '{value}',
                'color': '#e0e8f0',
                'fontSize': 28,
                'fontWeight': 'bold',
                'offsetCenter': [0, '30%'],
            },
            'title': {'offsetCenter': [0, '60%'], 'color': '#8899aa', 'fontSize': 13},
            'data': [{'value': value, 'name': label or title}],
            **ANIMATION_DEFAULTS,
        }],
    }


def render_scatter(x_data: list, y_data: list, labels: list, title: str = '',
                   x_label: str = '', y_label: str = '') -> dict:
    """气泡散点图（相关性分析）。"""
    data = [
        {
            'value': [x_data[i], y_data[i]],
            'name': labels[i] if i < len(labels) else f'#{i}',
            'symbolSize': max(8, min(30, y_data[i] / max(y_data) * 30)) if max(y_data) > 0 else 12,
            'itemStyle': {
                'color': {
                    'type': 'radial', 'x': 0.5, 'y': 0.5, 'r': 0.5,
                    'colorStops': [
                        {'offset': 0, 'color': COLORS[i % len(COLORS)]},
                        {'offset': 1, 'color': COLORS[(i + 3) % len(COLORS)]},
                    ],
                },
            },
        }
        for i in range(len(x_data))
    ]

    return {
        'tooltip': {
            'trigger': 'item',
            'formatter': '{b}<br/>{c}',
            **TOOLTIP_STYLE,
        },
        'grid': {'left': 60, 'right': 30, 'top': 30, 'bottom': 40},
        'xAxis': {
            'name': x_label,
            'nameTextStyle': {'color': '#8899aa'},
            'type': 'value',
            **AXIS_STYLE,
        },
        'yAxis': {
            'name': y_label,
            'nameTextStyle': {'color': '#8899aa'},
            'type': 'value',
            **AXIS_STYLE,
        },
        'series': [{
            'type': 'scatter',
            'data': data,
            'emphasis': {
                'itemStyle': {
                    'shadowBlur': 10,
                    'shadowColor': 'rgba(0, 212, 255, 0.5)',
                },
            },
            **ANIMATION_DEFAULTS,
        }],
    }
