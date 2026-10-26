"""Render the chatflow DSL from cardlib. The YAML is committed; check_deck compares it."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cardlib import pick_node_code, rewrite_node_code

ROOT = Path(__file__).resolve().parents[1]
DSL_PATH = ROOT / "dsl" / "ob-meme-card.yml"
DATASET_ID = "00000000-0000-4000-8000-00000000ae05"
START = "6000761001"
REWRITE = "6000762001"
RETRIEVE = "6000763001"
PICK = "6000765001"
GATE = "6000765501"
ASSIGN = "6000766001"
LLM = "6000767001"
ANSWER_OK = "6000768001"
ANSWER_MISS = "6000769001"

HEADER = """# OB梗图冷知识抽卡机 Chatflow
# 由 dify/scripts/render_dsl.py 根据 dify/scripts/cardlib.py 生成。
# 导入后重绑知识库与对话模型。本文件没有密钥，也不是某次线上工作室的导出件。
"""

PROMPT = """你是「OB梗图冷知识抽卡机」的主持人。
卡面由代码节点印好。冷知识、数字、card_id、出处都不可改，也不要复述整张卡。
只输出两行，不要加别的字：
主持吐槽：不超过 28 个字，玩梗，不新增数字、版本号或专有名词。
下句引导：请对方说「再来一张」，或点一个主题。
如果卡面写着没摸到牌，不要编造知识，只邀请换个关键词。

卡面：
{{#6000765001.card_face#}}
"""


class Literal(str):
    pass


def _literal_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(Literal, _literal_representer)


def _node(node_id, x, y, data, height=90):
    return {
        "id": node_id,
        "type": "custom",
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x, "y": y},
        "width": 244,
        "height": height,
        "sourcePosition": "right",
        "targetPosition": "left",
        "selected": False,
        "data": data,
    }


def _edge(source, target, source_type, target_type, handle="source"):
    return {
        "id": source + "-" + handle + "-" + target,
        "source": source,
        "sourceHandle": handle,
        "target": target,
        "targetHandle": "target",
        "type": "custom",
        "zIndex": 0,
        "data": {
            "sourceType": source_type,
            "targetType": target_type,
            "isInIteration": False,
            "isInLoop": False,
        },
    }


def _outputs(spec):
    return {key: {"type": kind, "children": None} for key, kind in spec.items()}


def _var(name, *selector):
    return {"variable": name, "value_selector": list(selector)}


def document():
    return {
        "version": "0.6.0",
        "kind": "app",
        "app": {
            "name": "OB梗图冷知识抽卡机",
            "mode": "advanced-chat",
            "icon": "🃏",
            "icon_background": "#FFEAD5",
            "icon_type": "emoji",
            "description": "从 seekdb 知识库抽一张 OceanBase 梗图冷知识。再说「再来一张」就换一张。",
            "use_icon_as_answer_icon": False,
        },
        "dependencies": [],
        "workflow": {
            "environment_variables": [],
            "conversation_variables": [
                {
                    "id": "6f0e0a05-0001-4000-8000-000000000001",
                    "name": "last_card_id",
                    "value_type": "string",
                    "value": "",
                    "description": "本会话上一张牌的 card_id。再来一张时排除它。",
                },
                {
                    "id": "6f0e0a05-0001-4000-8000-000000000002",
                    "name": "last_theme",
                    "value_type": "string",
                    "value": "",
                    "description": "上一张牌的 theme。纯「再来一张」时沿用这个主题。",
                },
                {
                    "id": "6f0e0a05-0001-4000-8000-000000000003",
                    "name": "draw_count",
                    "value_type": "number",
                    "value": 0,
                    "description": "本会话已经成功打出的牌数。",
                },
            ],
            "features": {
                "file_upload": {"enabled": False},
                "opening_statement": (
                    "我是 OB 梗图冷知识抽卡机。说「抽一张 seekdb 混合检索」，或「来一张 SSR」。"
                    "不想重复就说「再来一张」。冷知识来自牌库原文，我只负责吐槽。"
                ),
                "retriever_resource": {"enabled": True},
                "sensitive_word_avoidance": {"enabled": False},
                "speech_to_text": {"enabled": False},
                "suggested_questions": [
                    "抽一张 seekdb 混合检索",
                    "来一张 SSR",
                    "再来一张",
                    "午饭吃什么",
                ],
                "suggested_questions_after_answer": {"enabled": False},
                "text_to_speech": {"enabled": False},
            },
            "graph": {
                "edges": [
                    _edge(START, REWRITE, "start", "code"),
                    _edge(REWRITE, RETRIEVE, "code", "knowledge-retrieval"),
                    _edge(RETRIEVE, PICK, "knowledge-retrieval", "code"),
                    _edge(PICK, GATE, "code", "if-else"),
                    _edge(GATE, ASSIGN, "if-else", "assigner", "true"),
                    _edge(GATE, ANSWER_MISS, "if-else", "answer", "false"),
                    _edge(ASSIGN, LLM, "assigner", "llm"),
                    _edge(LLM, ANSWER_OK, "llm", "answer"),
                ],
                "nodes": [
                    _node(
                        START,
                        80,
                        280,
                        {"type": "start", "title": "开场", "desc": "玩家的一句话", "variables": []},
                        54,
                    ),
                    _node(
                        REWRITE,
                        380,
                        280,
                        {
                            "type": "code",
                            "title": "改写检索词",
                            "desc": "把抽卡口令收成知识库查询，并认出稀有度",
                            "code_language": "python3",
                            "code": Literal(rewrite_node_code()),
                            "variables": [
                                _var("query", "sys", "query"),
                                _var("last_theme", "conversation", "last_theme"),
                            ],
                            "outputs": _outputs(
                                {"search_query": "string", "redraw": "string", "rarity": "string"}
                            ),
                        },
                        120,
                    ),
                    _node(
                        RETRIEVE,
                        700,
                        280,
                        {
                            "type": "knowledge-retrieval",
                            "title": "牌库检索",
                            "desc": "向量在 seekdb。导入后把 dataset_ids 换成工作室里的知识库。",
                            "query_variable_selector": [REWRITE, "search_query"],
                            "query_attachment_selector": [],
                            "dataset_ids": [DATASET_ID],
                            "retrieval_mode": "multiple",
                            "metadata_filtering_mode": "disabled",
                            "multiple_retrieval_config": {
                                "top_k": 8,
                                "reranking_enable": False,
                            },
                        },
                        120,
                    ),
                    _node(
                        PICK,
                        1020,
                        280,
                        {
                            "type": "code",
                            "title": "抽一张",
                            "desc": "只使用召回片段里的原文，排除上一张",
                            "code_language": "python3",
                            "code": Literal(pick_node_code()),
                            "variables": [
                                _var("query", "sys", "query"),
                                _var("chunks", RETRIEVE, "result"),
                                _var("last_card_id", "conversation", "last_card_id"),
                                _var("last_theme", "conversation", "last_theme"),
                                _var("draw_count", "conversation", "draw_count"),
                                _var("redraw", REWRITE, "redraw"),
                                _var("rarity", REWRITE, "rarity"),
                                _var("search_query", REWRITE, "search_query"),
                            ],
                            "outputs": _outputs(
                                {
                                    "card_id": "string",
                                    "theme": "string",
                                    "rarity": "string",
                                    "card_face": "string",
                                    "host_brief": "string",
                                    "picked": "string",
                                    "source_url": "string",
                                    "next_draw_count": "number",
                                }
                            ),
                        },
                        140,
                    ),
                    _node(
                        GATE,
                        1340,
                        280,
                        {
                            "type": "if-else",
                            "title": "摸到牌了吗",
                            "desc": "picked 为 yes 才发牌",
                            "cases": [
                                {
                                    "case_id": "true",
                                    "logical_operator": "and",
                                    "conditions": [
                                        {
                                            "id": "c0a1b2c3-d4e5-6789-0abc-def012345678",
                                            "varType": "string",
                                            "variable_selector": [PICK, "picked"],
                                            "comparison_operator": "is",
                                            "value": "yes",
                                        }
                                    ],
                                }
                            ],
                        },
                        126,
                    ),
                    _node(
                        ASSIGN,
                        1660,
                        120,
                        {
                            "type": "assigner",
                            "title": "记下这张牌",
                            "desc": "同一会话里再来一张时排除它",
                            "version": "2",
                            "items": [
                                {
                                    "variable_selector": ["conversation", "last_card_id"],
                                    "input_type": "variable",
                                    "operation": "over-write",
                                    "value": [PICK, "card_id"],
                                },
                                {
                                    "variable_selector": ["conversation", "last_theme"],
                                    "input_type": "variable",
                                    "operation": "over-write",
                                    "value": [PICK, "theme"],
                                },
                                {
                                    "variable_selector": ["conversation", "draw_count"],
                                    "input_type": "variable",
                                    "operation": "over-write",
                                    "value": [PICK, "next_draw_count"],
                                },
                            ],
                        },
                        120,
                    ),
                    _node(
                        LLM,
                        1980,
                        120,
                        {
                            "type": "llm",
                            "title": "主持人吐槽",
                            "desc": "只加一句吐槽。事实以卡面为准。导入后重绑模型。",
                            "model": {
                                "provider": "langgenius/openai_api_compatible/openai_api_compatible",
                                "name": "REPLACE_WITH_YOUR_CHAT_MODEL",
                                "mode": "chat",
                                "completion_params": {"temperature": 0.7, "max_tokens": 256},
                            },
                            "prompt_template": [{"role": "system", "text": Literal(PROMPT)}],
                            "variables": [],
                            "context": {"enabled": False, "variable_selector": []},
                            "vision": {"enabled": False},
                            "memory": {
                                "query_prompt_template": "{{#sys.query#}}",
                                "window": {"enabled": False, "size": 10},
                            },
                        },
                        98,
                    ),
                    _node(
                        ANSWER_OK,
                        2300,
                        120,
                        {
                            "type": "answer",
                            "title": "出牌",
                            "desc": "卡面原文加主持人两行",
                            "answer": "{{#6000765001.card_face#}}\n\n{{#6000767001.text#}}",
                            "variables": [],
                        },
                        80,
                    ),
                    _node(
                        ANSWER_MISS,
                        1660,
                        460,
                        {
                            "type": "answer",
                            "title": "没摸到",
                            "desc": "不调用模型，避免编一条冷知识",
                            "answer": "{{#6000765001.card_face#}}",
                            "variables": [],
                        },
                        80,
                    ),
                ],
                "viewport": {"x": 0, "y": 0, "zoom": 0.55},
            },
        },
    }


def render():
    dumped = yaml.dump(
        document(),
        allow_unicode=True,
        sort_keys=False,
        width=1000,
        default_flow_style=False,
    )
    return HEADER + dumped


def main():
    DSL_PATH.parent.mkdir(parents=True, exist_ok=True)
    DSL_PATH.write_text(render(), encoding="utf-8")
    print(DSL_PATH)


if __name__ == "__main__":
    main()
