# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

# """
# Agentic Search Engine (No Templates, with self-correction)

# - 不提供任何预置 Cypher 模版/样例/片段
# - 仅向 LLM 提供 schema 与约束；LLM 每轮即时生成查询
# - 查询若空/报错或缺列，把问题、上次查询、缺失列、已返回列、行数与错误原样反馈，要求其自修正
# - 参与者匹配、事件关键词匹配等仅通过“需求描述约束”，具体写法由 LLM 自主决定
# - 排序/去重在 Python 后处理（无任何 Cypher 日期转换片段）
# """

# import os
# import re
# import json
# import uuid
# from datetime import datetime
# from typing import Any, Dict, List, Optional, Tuple

# from neo4j import GraphDatabase
# from openai import OpenAI


# # ------------------------- 工具函数 -------------------------

# _ORDINAL_RE = re.compile(r'(\d+)(st|nd|rd|th)$', re.IGNORECASE)

# def _strip_ordinal(day_str: str) -> str:
#     """把 '23rd' -> '23'。"""
#     m = _ORDINAL_RE.match(day_str.strip())
#     return m.group(1) if m else day_str.strip()

# def _parse_date_safe(s: str) -> Optional[datetime]:
#     """把 'March 23, 2024' / 'Mar 23, 2024' / 'March 23rd, 2024' 等解析为 datetime；失败返回 None。"""
#     if not s:
#         return None
#     txt = s.strip().replace(",", " ")
#     parts = [p for p in txt.split() if p]
#     if len(parts) >= 3:
#         # 规范化 day 去掉序数词尾
#         parts[1] = _strip_ordinal(parts[1])
#         txt = " ".join(parts[:3])
#     # 尝试若干格式
#     for fmt in ("%B %d %Y", "%b %d %Y"):
#         try:
#             return datetime.strptime(txt, fmt)
#         except Exception:
#             continue
#     return None

# def _unique_in_order(seq: List[Any]) -> List[Any]:
#     seen = set()
#     out = []
#     for x in seq:
#         if x not in seen:
#             seen.add(x)
#             out.append(x)
#     return out

# def _extract_person_and_event(question: str) -> Tuple[Optional[str], Optional[str]]:
#     """先用 regex 粗提人名/事件词（不影响“无模版”生成，仅用于参数传递）。"""
#     person = None
#     evt = None
#     # 人名：两个或三个首字母大写单词
#     m = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", question)
#     if m:
#         person = m.group(1).strip()
#     # 事件关键词：引号内/related to X/involving both A and X
#     pats = [r'“([^”]+)”', r'"([^"]+)"',
#             r'related to ([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)',
#             r'involving both .* and ([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)']
#     for p in pats:
#         m2 = re.search(p, question, flags=re.IGNORECASE)
#         if m2:
#             evt = m2.group(1).strip()
#             break
#     return person, evt


# # ------------------------- 引擎状态 -------------------------

# class SearchState:
#     def __init__(self, question: str):
#         self.session_id = str(uuid.uuid4())
#         self.question = question
#         self.iteration = 0
#         self.max_iterations = 5

#         self.query_history: List[str] = []
#         self.reasoning: List[str] = []

#         self.final_answer: Optional[Any] = None
#         self.last_error: Optional[str] = None
#         self.last_result_rows: int = 0

#         # 新增：用于指导 LLM 修正返回列
#         self.last_missing_cols: List[str] = []
#         self.last_row_keys: List[str] = []


# # ------------------------- 主引擎（无模版） -------------------------

# class AgenticSearchEngine:
#     """
#     仅提供 schema 与返回列要求，所有 Cypher 由 LLM 即时生成。
#     排序/去重在 Python 完成；如果缺列（如没返回 date），会触发“请补列并重写查询”的反馈迭代。
#     """

#     def __init__(
#         self,
#         neo4j_uri: Optional[str] = None,
#         neo4j_user: Optional[str] = None,
#         neo4j_password: Optional[str] = None,
#         openai_api_key: Optional[str] = None,
#         neo4j_database: Optional[str] = None,
#     ):
#         self.database = neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")
#         self.driver = GraphDatabase.driver(
#             neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687"),
#             auth=(neo4j_user or os.getenv("NEO4J_USER", "neo4j"),
#                   neo4j_password or os.getenv("NEO4J_PASSWORD", "password"))
#         )
#         api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
#         if not api_key:
#             raise ValueError("OPENAI_API_KEY not set")
#         self.client = OpenAI(api_key=api_key)

#         # 仅描述 schema，不给任何查询模版
#         self.schema_hint = (
#             "There is a single label `Event` you must use. "
#             "`Event` has properties: `name` (string), `date` (string like 'March 23, 2024'), "
#             "`location` (string), `event_type` (string), `description` (string), "
#             "`participants` (array of strings). "
#             "Do NOT use any relationships. Only query `Event` nodes and their properties. "
#             "Participants are stored as an array of names on the `Event` node."
#         )

#     # ---------- LLM 兜底实体抽取（避免 regex 漏检） ----------
#     def _extract_entities_llm(self, question: str) -> Tuple[Optional[str], Optional[str]]:
#         prompt = f"""
# Extract two optional fields (strict JSON):
# {{
#   "person": "<full name if clearly a single person is referenced, else null>",
#   "event": "<event keyword if clearly referenced (e.g., 'Photography Exhibition'), else null>"
# }}
# Question: {question}
# """
#         try:
#             resp = self.client.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=[{"role": "user", "content": prompt}],
#                 temperature=0.0
#             )
#             data = json.loads(resp.choices[0].message.content.strip())
#             p = data.get("person")
#             e = data.get("event")
#             return (p if isinstance(p, str) and p.strip() else None,
#                     e if isinstance(e, str) and e.strip() else None)
#         except Exception:
#             return (None, None)

#     # ---------- LLM 问题类型分类（无模版） ----------
#     def _classify_llm(self, question: str) -> Dict[str, Any]:
#         type_defs = {
#             "latest_activity_of_person": {
#                 "desc": "What was PERSON doing the last time they were observed? Return the most recent event for a person.",
#                 "need": ["event_type", "name", "event", "activity", "date", "timestamp"]
#             },
#             "most_recent_date_of_person": {
#                 "desc": "What is the most recent date PERSON was observed or mentioned? Return the latest date only.",
#                 "need": ["date", "timestamp"]
#             },
#             "chrono_locations_by_person": {
#                 "desc": "List all locations visited by PERSON in chronological order according to the story's timeline.",
#                 "need": ["location", "date"]
#             },
#             "dates_by_filters": {
#                 "desc": "List all dates for events that involve both a PERSON and an EVENT KEYWORD.",
#                 "need": ["date"]
#             },
#             "protagonists_by_event": {
#                 "desc": "List all protagonists of events related to an EVENT KEYWORD.",
#                 "need": ["protagonist"]
#             },
#             "dates_by_event": {
#                 "desc": "List all dates of events related to an EVENT KEYWORD.",
#                 "need": ["date"]
#             },
#             "locations_by_event": {
#                 "desc": "List all locations of events related to an EVENT KEYWORD.",
#                 "need": ["location"]
#             },
#             "generic": {
#                 "desc": "If none fits well, choose generic.",
#                 "need": ["date", "location", "name", "event_type"]
#             }
#         }
        
#         prompt = f"""
# You are a task classifier for a knowledge-graph QA system (NO query templates).
# Given a question, choose the SINGLE closest task type from this set and list the columns we need from rows:

# TYPES:
# {json.dumps({k: v["desc"] for k, v in type_defs.items()}, indent=2)}

# Return STRICT JSON:
# {{
#   "type": "<one of: {', '.join(type_defs.keys())}>",
#   "need": ["<column names we must return from Cypher rows>"]
# }}

# Rules:
# - Pick the closest type even if phrasing differs.
# - If unsure, pick "generic".
# - The 'need' list should usually match the default for that type (you may add/remove columns if obviously necessary).
# - Do NOT include any explanation text outside the JSON.

# Question: {question}
# """

#         try:
#             resp = self.client.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=[{"role": "user", "content": prompt}],
#                 temperature=0.0
#             )
#             data = json.loads(resp.choices[0].message.content.strip())
#             t = data.get("type", "generic")
#             need = data.get("need") or type_defs.get(t, type_defs["generic"])["need"]
#             if t not in type_defs:
#                 t = "generic"
#             if not isinstance(need, list) or not all(isinstance(x, str) for x in need):
#                 need = type_defs[t]["need"]
#             return {"type": t, "need": need}
#         except Exception:
#             return {"type": "generic", "need": type_defs["generic"]["need"]}

#     # ---------- 任务类型兜底 ----------
#     def _classify(self, question: str) -> Dict[str, Any]:
#         result = self._classify_llm(question)
#         if result and result.get("type"):
#             return result
#         # 兜底关键词（极少命中）
#         q = question.lower()
#         if "what was" in q and "doing the last time" in q:
#             return {"type": "latest_activity_of_person", "need": ["event_type", "name", "date"]}
#         if "list all locations visited by" in q and "chronological" in q:
#             return {"type": "chrono_locations_by_person", "need": ["location", "date"]}
#         if ("related to" in q or "involving both" in q or "involving" in q) and "date" in q:
#             return {"type": "dates_by_filters", "need": ["date"]}
#         if ("reflect on events related to" in q or "related to" in q) and "protagonists" in q:
#             return {"type": "protagonists_by_event", "need": ["protagonist"]}
#         if ("recall all events related to" in q or "reflect on events related to" in q) and "date" in q:
#             return {"type": "dates_by_event", "need": ["date"]}
#         if ("consider all events" in q and "locations" in q and ("involving" in q or "related to" in q)):
#             return {"type": "locations_by_event", "need": ["location"]}
#         return {"type": "generic", "need": ["date", "location", "name", "event_type"]}

#     # ---------- 生成查询（无模版） ----------
#     def _gen_query_json(
#         self,
#         question: str,
#         need_columns: List[str],
#         person: Optional[str],
#         keyword: Optional[str],
#         prev_query: Optional[str] = None,
#         last_error: Optional[str] = None,
#         last_rows: Optional[int] = None,
#         missing_cols: Optional[List[str]] = None,
#         last_keys: Optional[List[str]] = None,
#     ) -> Tuple[str, Dict[str, Any]]:
#         """
#         让 LLM 生成只含 `query` 与 `params` 的 JSON。不给任何样例/片段。
#         如果有上一次错误/0 行/缺列，会附带诊断信息要求自修复。
#         """
#         constraints = [
#             "Use only (e:Event) and its properties; do NOT use relationships.",
#             "If you need to filter by a person, treat `participants` as an array of strings.",
#             "For person matching, use: ANY(p IN e.participants WHERE toLower(trim(p)) = toLower(trim($person)))",
#             "NEVER use trim() directly on e.participants array - only on individual elements within ANY().",
#             "If you need to filter by an event keyword, match it against `event_type` (preferred), or `name`/`description`.",
#             "Return ONLY the minimal columns requested, using EXACT aliases from the required list.",
#             "Do NOT add ORDER BY; raw rows are fine. Sorting/dedup happens outside Cypher.",
#             "If previous result had 0 rows, you MUST adjust filters (e.g., relax keyword to name/description, or normalize participants with ANY + toLower(trim(...))).",
#             "Aliases in RETURN must EXACTLY match the required output columns."
#         ]

#         diagnose = ""
#         if prev_query is not None:
#             diagnose = f"\nPrevious query returned {last_rows} rows. Last error: {last_error or 'none'}.\n"
#             if missing_cols:
#                 diagnose += f"Missing required columns last time: {missing_cols}. Include them EXACTLY with these aliases.\n"
#             if last_keys:
#                 diagnose += f"Last returned columns were: {last_keys}. Adjust RETURN aliases accordingly.\n"
#             # 关键词“先等值后放宽”
#             if keyword:
#                 if (last_rows is None) or (last_rows > 0):
#                     diagnose += "For the event keyword: prefer case-insensitive EQUALITY on e.event_type to $kw.\n"
#                 else:
#                     diagnose += "Last attempt returned 0 rows. You MAY broaden keyword filtering to case-insensitive CONTAINS over e.name or e.description.\n"
        
#         prompt = f"""
# You are a Cypher generator. Do not use any templates or examples.
# Database schema hint: {self.schema_hint}

# Question: {question}

# Required output columns (exact aliases): {need_columns}
# Rules:
# - {chr(10) + '- '.join(constraints)}

# {('Parameters to expect: ' + json.dumps({'person': person, 'kw': keyword})) if (person or keyword) else 'No external parameters are required.'}
# {diagnose}

# Return ONLY a valid JSON object with fields:
# - "query": string
# - "params": object (may be empty if no params)
# """

#         # 最多两次生成尝试（解析失败则重试）
#         for _ in range(2):
#             resp = self.client.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=[{"role": "user", "content": prompt}],
#                 temperature=0.0,
#             )
#             text = resp.choices[0].message.content.strip()
#             try:
#                 data = json.loads(text)
#                 q = data.get("query", "")
#                 params = data.get("params", {}) or {}
#                 if not isinstance(q, str):
#                     raise ValueError("`query` must be a string")
#                 if not isinstance(params, dict):
#                     raise ValueError("`params` must be an object")
#                 # 填充参数默认值（仅在未提供时）
#                 if person and "person" not in params:
#                     params["person"] = person
#                 if keyword and "kw" not in params:
#                     params["kw"] = keyword
#                 return q, params
#             except Exception as e:
#                 # 下一轮要求严格 JSON
#                 prompt += f"\nYour previous JSON was invalid: {e}. Return a strict JSON next time.\n"
#                 continue

#         raise RuntimeError("LLM failed to return a valid JSON {query, params}.")

#     # ---------- 执行查询 ----------
#     def _run(self, query: str, params: Dict[str, Any]) -> Tuple[List[Dict], Optional[str]]:
#         try:
#             with self.driver.session(database=self.database) as sess:
#                 res = sess.run(query, **params)
#                 rows = [dict(r) for r in res]
#                 return rows, None
#         except Exception as e:
#             return [], str(e)

#     # ---------- 结果标准化 ----------
#     def _standardize(self, question: str, qtype: str, rows: List[Dict]) -> Any:
#         if not rows:
#             return None

#         if qtype == "latest_activity_of_person":
#             # 选择日期最晚的一条，返回 event_type 或 name
#             best = None
#             best_dt = None
#             for r in rows:
#                 # 尝试多个可能的日期字段名
#                 date_str = str(r.get("date", "") or r.get("timestamp", "") or "")
#                 d = _parse_date_safe(date_str)
#                 if d is None:
#                     continue
#                 if best_dt is None or d > best_dt:
#                     best_dt = d
#                     best = r
#             if best is None:
#                 best = rows[0]
#             # 尝试多个可能的事件名称字段
#             return (best.get("event_type") or 
#                     best.get("name") or 
#                     best.get("event") or 
#                     best.get("activity") or "")

#         if qtype == "most_recent_date_of_person":
#             # 选择日期最晚的一条，返回日期
#             best = None
#             best_dt = None
#             for r in rows:
#                 # 尝试多个可能的日期字段名
#                 date_str = str(r.get("date", "") or r.get("timestamp", "") or "")
#                 d = _parse_date_safe(date_str)
#                 if d is None:
#                     continue
#                 if best_dt is None or d > best_dt:
#                     best_dt = d
#                     best = r
#             if best is None:
#                 best = rows[0]
#             # 返回日期字符串
#             return (best.get("date") or best.get("timestamp") or "")

#         if qtype == "chrono_locations_by_person":
#             # 用最早日期排序地点，唯一化
#             bucket: Dict[str, datetime] = {}
#             for r in rows:
#                 loc = r.get("location")
#                 d = _parse_date_safe(str(r.get("date", "")))
#                 if not loc or d is None:
#                     continue
#                 bucket[loc] = min(bucket.get(loc, d), d) if loc in bucket else d
#             if not bucket:
#                 # 若没拿到 date，只能保序去重
#                 return _unique_in_order([r.get("location") for r in rows if r.get("location")])
#             ordered = sorted(bucket.items(), key=lambda x: x[1])
#             return [loc for loc, _ in ordered]

#         if qtype in ("dates_by_filters", "dates_by_event"):
#             ds = []
#             for r in rows:
#                 d = r.get("date")
#                 if isinstance(d, str) and d.strip():
#                     ds.append(d.strip())
#             # 解析排序
#             ds_parsed = [(s, _parse_date_safe(s)) for s in ds]
#             ds_parsed = [x for x in ds_parsed if x[1] is not None]
#             ds_parsed.sort(key=lambda x: x[1])
#             return _unique_in_order([s for s, _ in ds_parsed])

#         if qtype == "protagonists_by_event":
#             people = [r.get("protagonist") for r in rows if r.get("protagonist")]
#             return sorted(_unique_in_order(people))

#         if qtype == "locations_by_event":
#             locs = [r.get("location") for r in rows if r.get("location")]
#             return sorted(_unique_in_order(locs))

#         # 通用：优先 date/location/name/event_type
#         if len(rows) == 1 and len(rows[0]) == 1:
#             return list(rows[0].values())[0]
#         for key in ("date", "location", "name", "event_type"):
#             if key in rows[0] and all(key in r for r in rows):
#                 vals = [r.get(key) for r in rows if r.get(key)]
#                 return _unique_in_order(vals)
#         return rows[0]

#     # ---------- 主流程 ----------
#     def search(self, question: str, max_iterations: int = 5) -> Dict[str, Any]:
#         state = SearchState(question)
#         state.max_iterations = max_iterations
        
#         print(f"Starting agentic search for: {question}")
#         print(f"Session: {state.session_id}")

#         # 轻量抽取作为参数传递（不改变“无模版”本质）
#         person, evt = _extract_person_and_event(question)
#         # regex 漏检时 LLM 兜底
#         if not person or (("involving" in question.lower() or "related to" in question.lower()) and not evt):
#             p2, e2 = self._extract_entities_llm(question)
#             person = person or p2
#             evt = evt or e2

#         cls = self._classify(question)
#         need_cols: List[str] = cls["need"]

#         while state.iteration < state.max_iterations and state.final_answer is None:
#             state.iteration += 1
#             print(f"\n-- Iteration {state.iteration} --")

#             # 让 LLM 生成查询（无任何模板/样例）
#             try:
#                 query, params = self._gen_query_json(
#                     question=question,
#                     need_columns=need_cols,
#                     person=person,
#                     keyword=evt,
#                     prev_query=state.query_history[-1] if state.query_history else None,
#                     last_error=state.last_error,
#                     last_rows=state.last_result_rows,
#                     missing_cols=state.last_missing_cols,
#                     last_keys=state.last_row_keys,
#                 )
#             except Exception as e:
#                 state.reasoning.append(f"Query generation error: {e}")
#                 break

#             state.query_history.append(query)
#             print("Generated query:", query)
#             print("Params:", params)

#             # 执行
#             rows, err = self._run(query, params)
#             state.last_error = err
#             state.last_result_rows = len(rows)
#             state.last_row_keys = list(rows[0].keys()) if rows else []
#             if err:
#                 print("Execution error:", err)
#                 state.reasoning.append(f"Execution error: {err}")
#                 continue

#             print(f"Rows: {len(rows)}")

#             # 如果缺关键列（例如需要 date 却没返回），触发一次修正
#             # 但对于某些类型，有部分字段就足够了
#             missing = [c for c in need_cols if rows and c not in rows[0]]
#             state.last_missing_cols = missing
            
#             # 对于latest_activity_of_person，只需要至少有日期字段和事件字段之一
#             if cls["type"] == "latest_activity_of_person" and rows:
#                 has_date = any(field in rows[0] for field in ["date", "timestamp"])
#                 has_event = any(field in rows[0] for field in ["event_type", "name", "event", "activity"])
#                 if has_date or has_event:
#                     missing = []  # 有足够的字段可以处理
            
#             if rows and missing:
#                 msg = f"Missing columns {missing}, ask LLM to include them next round."
#                 print(msg)
#                 state.reasoning.append(msg)
#                 continue

#             if rows:
#                 state.final_answer = self._standardize(question, cls["type"], rows)
#                 break
            
#             state.reasoning.append("0 rows; ask LLM to self-correct and widen/adjust filters.")
        
#         result = {
#             "session_id": state.session_id,
#             "question": question,
#             "final_answer": state.final_answer,
#             "standardized_answer": self._to_list(state.final_answer),
#             "total_iterations": state.iteration,
#             "search_successful": state.final_answer is not None,
#             "reasoning_chain": state.reasoning,
#             "query_history": state.query_history,
#         }
#         print("Final:", result)
#         return result

#     def close(self):
#         """Close database connection"""
#         if hasattr(self, 'driver') and self.driver:
#             self.driver.close()

#     @staticmethod
#     def _to_list(ans: Any) -> List[str]:
#         if ans is None:
#             return []
#         if isinstance(ans, list):
#             return [str(x).strip() for x in ans if str(x).strip()]
#         return [str(ans).strip()]
    
#     def close(self):
#         if self.driver:
#             self.driver.close()


# # ------------------------- 自测 -------------------------

# if __name__ == "__main__":
#     engine = AgenticSearchEngine(
#         neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
#         neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
#         neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
#         openai_api_key=os.getenv("OPENAI_API_KEY"),
#         neo4j_database=os.getenv("NEO4J_DATABASE", "test9"),
#     )
#     try:
#         q = "List all locations visited by Carter Stewart in chronological order according to the story's timeline."
#         print(engine.search(q))
#     finally:
#         engine.close() 

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agentic Search Engine (No Templates, with self-correction)

- 不提供任何预置 Cypher 模版/样例/片段
- 仅向 LLM 提供 schema 与约束；LLM 每轮即时生成查询
- 查询若空/报错或缺列，把问题、上次查询、缺失列、已返回列、行数与错误原样反馈，要求其自修正
- 参与者匹配、事件关键词匹配等仅通过“需求描述约束”，具体写法由 LLM 自主决定
- 排序/去重在 Python 后处理（无任何 Cypher 日期转换片段）
"""

import os
import re
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase
from openai import OpenAI


# ------------------------- 工具函数 -------------------------

_ORDINAL_RE = re.compile(r'(\d+)(st|nd|rd|th)$', re.IGNORECASE)

def _strip_ordinal(day_str: str) -> str:
    """把 '23rd' -> '23'。"""
    m = _ORDINAL_RE.match(day_str.strip())
    return m.group(1) if m else day_str.strip()

def _parse_date_safe(s: str) -> Optional[datetime]:
    """把 'March 23, 2024' / 'Mar 23, 2024' / 'March 23rd, 2024' 等解析为 datetime；失败返回 None。"""
    if not s:
        return None
    txt = s.strip().replace(",", " ")
    parts = [p for p in txt.split() if p]
    if len(parts) >= 3:
        # 规范化 day 去掉序数词尾
        parts[1] = _strip_ordinal(parts[1])
        txt = " ".join(parts[:3])
    # 尝试若干格式
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(txt, fmt)
        except Exception:
            continue
    return None

def _unique_in_order(seq: List[Any]) -> List[Any]:
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def _extract_person_and_event(question: str) -> Tuple[Optional[str], Optional[str]]:
    """先用 regex 粗提人名/事件词（不影响“无模版”生成，仅用于参数传递）。"""
    person = None
    evt = None
    # 人名：两个或三个首字母大写单词
    m = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", question)
    if m:
        person = m.group(1).strip()
    # 事件关键词：引号内/related to X/involving both A and X
    pats = [r'“([^”]+)”', r'"([^"]+)"',
            r'related to ([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)',
            r'involving both .* and ([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)']
    for p in pats:
        m2 = re.search(p, question, flags=re.IGNORECASE)
        if m2:
            evt = m2.group(1).strip()
            break
    return person, evt


# ------------------------- 引擎状态 -------------------------

class SearchState:
    def __init__(self, question: str):
        self.session_id = str(uuid.uuid4())
        self.question = question
        self.iteration = 0
        self.max_iterations = 5

        self.query_history: List[str] = []
        self.reasoning: List[str] = []

        self.final_answer: Optional[Any] = None
        self.last_error: Optional[str] = None
        self.last_result_rows: int = 0

        # 新增：用于指导 LLM 修正返回列
        self.last_missing_cols: List[str] = []
        self.last_row_keys: List[str] = []


# ------------------------- 主引擎（无模版） -------------------------

class AgenticSearchEngine:
    """
    仅提供 schema 与返回列要求，所有 Cypher 由 LLM 即时生成。
    排序/去重在 Python 完成；如果缺列（如没返回 date），会触发“请补列并重写查询”的反馈迭代。
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        neo4j_database: Optional[str] = None,
    ):
        self.database = neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver = GraphDatabase.driver(
            neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(neo4j_user or os.getenv("NEO4J_USER", "neo4j"),
                  neo4j_password or os.getenv("NEO4J_PASSWORD", "password"))
        )
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key)

        # 仅描述 schema，不给任何查询模版
        self.schema_hint = (
            "There is a single label `Event` you must use. "
            "`Event` has properties: `name` (string), `date` (string like 'March 23, 2024'), "
            "`location` (string), `event_type` (string), `description` (string), "
            "`participants` (array of strings). "
            "Do NOT use any relationships. Only query `Event` nodes and their properties. "
            "Participants are stored as an array of names on the `Event` node."
        )

    # ---------- LLM 兜底实体抽取（避免 regex 漏检） ----------
    def _extract_entities_llm(self, question: str) -> Tuple[Optional[str], Optional[str]]:
        prompt = f"""
Extract two optional fields (strict JSON):
{{
  "person": "<full name if clearly a single person is referenced, else null>",
  "event": "<event keyword if clearly referenced (e.g., 'Photography Exhibition'), else null>"
}}
Question: {question}
"""
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            data = json.loads(resp.choices[0].message.content.strip())
            p = data.get("person")
            e = data.get("event")
            return (p if isinstance(p, str) and p.strip() else None,
                    e if isinstance(e, str) and e.strip() else None)
        except Exception:
            return (None, None)

    # ---------- LLM 问题类型分类（无模版，强兜底） ----------
    def _classify_llm(self, question: str) -> Dict[str, Any]:
        type_defs = {
            "latest_activity_of_person": {
                "desc": "What was PERSON doing the last time they were observed? Return the most recent event for a person.",
                "need": ["event_type", "name", "event", "activity", "date", "timestamp"]
            },
            "most_recent_date_of_person": {
                "desc": "What is the most recent date PERSON was observed or mentioned? Return the latest date only.",
                "need": ["date", "timestamp"]
            },
            "chrono_locations_by_person": {
                "desc": "List all locations visited by PERSON in chronological order according to the story's timeline.",
                "need": ["location", "date"]
            },
            "dates_by_filters": {
                "desc": "List all dates for events that involve both a PERSON and an EVENT KEYWORD.",
                "need": ["date"]
            },
            "protagonists_by_event": {
                "desc": "List all protagonists of events related to an EVENT KEYWORD.",
                "need": ["protagonist"]
            },
            "dates_by_event": {
                "desc": "List all dates of events related to an EVENT KEYWORD.",
                "need": ["date"]
            },
            "locations_by_event": {
                "desc": "List all locations of events related to an EVENT KEYWORD.",
                "need": ["location"]
            },
            "generic": {
                "desc": "If none fits well, choose generic.",
                "need": ["date", "location", "name", "event_type"]
            }
        }

        valid_types = set(type_defs.keys())
        allowed_cols = {
            "date", "timestamp", "location", "name", "event_type",
            "protagonist", "participants", "event", "activity"
        }

        prompt = f"""
You are a task classifier for a knowledge-graph QA system (NO query templates).
You MUST choose ONE type from this fixed set ONLY (no new types):
{', '.join(sorted(valid_types))}

Return STRICT JSON ONLY (no prose):
{{
  "type": "<one of: {', '.join(sorted(valid_types))}>",
  "need": ["<columns to return from Cypher rows>"]
}}

Rules:
- If none fits well, RETURN "generic" (do NOT invent a new type).
- The 'need' list should usually match the default for that type; you may add/remove columns if obviously necessary.
- Columns must be simple strings. No duplicates. Prefer lowercase.
- No extra fields, no explanations.

Question: {question}
""".strip()

        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            raw = resp.choices[0].message.content.strip()
            data = json.loads(raw)
        except Exception:
            return {"type": "generic", "need": type_defs["generic"]["need"]}

        # 规范化与兜底
        t = str(data.get("type", "")).strip()
        if t not in valid_types:
            t = "generic"

        need = data.get("need")
        if not isinstance(need, list):
            need = type_defs[t]["need"]
        else:
            cleaned = []
            seen = set()
            for col in need:
                if not isinstance(col, str):
                    continue
                col_norm = col.strip().lower()
                if not col_norm:
                    continue
                if col_norm in allowed_cols and col_norm not in seen:
                    seen.add(col_norm)
                    cleaned.append(col_norm)
            need = cleaned or type_defs[t]["need"]

        return {"type": t, "need": need}

    # ---------- 任务类型兜底 ----------
    def _classify(self, question: str) -> Dict[str, Any]:
        result = self._classify_llm(question)
        if result and result.get("type"):
            return result
        # 兜底关键词（极少命中）
        q = question.lower()
        if "what was" in q and "doing the last time" in q:
            return {"type": "latest_activity_of_person", "need": ["event_type", "name", "date"]}
        if "list all locations visited by" in q and "chronological" in q:
            return {"type": "chrono_locations_by_person", "need": ["location", "date"]}
        if ("related to" in q or "involving both" in q or "involving" in q) and "date" in q:
            return {"type": "dates_by_filters", "need": ["date"]}
        if ("reflect on events related to" in q or "related to" in q) and "protagonists" in q:
            return {"type": "protagonists_by_event", "need": ["protagonist"]}
        if ("recall all events related to" in q or "reflect on events related to" in q) and "date" in q:
            return {"type": "dates_by_event", "need": ["date"]}
        if ("consider all events" in q and "locations" in q and ("involving" in q or "related to" in q)):
            return {"type": "locations_by_event", "need": ["location"]}
        return {"type": "generic", "need": ["date", "location", "name", "event_type"]}

    # ---------- 生成查询（无模版） ----------
    def _gen_query_json(
        self,
        question: str,
        need_columns: List[str],
        person: Optional[str],
        keyword: Optional[str],
        prev_query: Optional[str] = None,
        last_error: Optional[str] = None,
        last_rows: Optional[int] = None,
        missing_cols: Optional[List[str]] = None,
        last_keys: Optional[List[str]] = None,
        query_history: Optional[List[str]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        让 LLM 生成只含 `query` 与 `params` 的 JSON。不给任何样例/片段。
        如果有上一次错误/0 行/缺列，会附带诊断信息要求自修复。
        """
        constraints = [
            "Use only (e:Event) and its properties; do NOT use relationships.",
            "If you need to filter by a person, treat `participants` as an array of strings.",
            "For person matching, use: ANY(p IN e.participants WHERE toLower(trim(p)) = toLower(trim($person)))",
            "NEVER use trim() directly on e.participants array - only on individual elements within ANY().",
            "CRITICAL: Variables defined inside ANY() are NOT accessible in RETURN clause. To return participants, use 'e.participants'.",
            "WRONG: RETURN p (where p is from ANY clause). CORRECT: RETURN e.participants AS participants",
            "If you need to filter by an event keyword, first try case-insensitive equality on e.event_type to $kw.",
            "If both a person and a keyword are present, you MUST apply BOTH filters (logical AND).",
            "If previous attempt returned 0 rows, you MAY broaden keyword filtering to case-insensitive CONTAINS over e.name or e.description.",
            "Return ONLY the minimal columns requested, using EXACT aliases from the required list.",
            "Do NOT add ORDER BY; raw rows are fine. Sorting/dedup happens outside Cypher.",
            "Aliases in RETURN must EXACTLY match the required output columns."
        ]

        diagnose = ""
        if prev_query is not None:
            iteration_num = len(query_history) if query_history else 1
            diagnose = f"\nIteration {iteration_num}: Previous query returned {last_rows} rows. Last error: {last_error or 'none'}.\n"
            
            # 检测常见的Cypher语法错误并提供具体指导
            if last_error and "Variable" in last_error and "not defined" in last_error:
                if "ANY(" in prev_query and "RETURN" in prev_query:
                    diagnose += "ERROR DETECTED: You're trying to use a variable from ANY() clause in RETURN. This is invalid Cypher syntax.\n"
                    diagnose += "FIX: Use 'e.participants' instead of the ANY() variable in RETURN clause.\n"
            
            # 智能策略反思机制 - 避免重复相同查询
            if last_rows == 0 and query_history:
                diagnose += self._generate_strategy_reflection(iteration_num, question, keyword, person, query_history)
            
            if missing_cols:
                diagnose += f"Missing required columns last time: {missing_cols}. Include them EXACTLY with these aliases.\n"
            if last_keys:
                diagnose += f"Last returned columns were: {last_keys}. Adjust RETURN aliases accordingly.\n"
            if keyword:
                if (last_rows is None) or (last_rows > 0):
                    diagnose += "For the event keyword: prefer case-insensitive EQUALITY on e.event_type to $kw.\n"
                else:
                    diagnose += "Last attempt returned 0 rows. You MAY broaden keyword filtering to case-insensitive CONTAINS over e.name or e.description.\n"

        prompt = f"""
You are a Cypher generator. Do not use any templates or examples.
Database schema hint: {self.schema_hint}

Question: {question}

Required output columns (exact aliases): {need_columns}
Rules:
- {chr(10) + '- '.join(constraints)}

{('Parameters to expect: ' + json.dumps({'person': person, 'kw': keyword})) if (person or keyword) else 'No external parameters are required.'}
{diagnose}

Return ONLY a valid JSON object with fields:
- "query": string
- "params": object (may be empty if no params)
"""

        # 最多两次生成尝试（解析失败则重试）
        for _ in range(2):
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            text = resp.choices[0].message.content.strip()
            try:
                data = json.loads(text)
                q = data.get("query", "")
                params = data.get("params", {}) or {}
                if not isinstance(q, str):
                    raise ValueError("`query` must be a string")
                if not isinstance(params, dict):
                    raise ValueError("`params` must be an object")
                # 填充参数默认值（仅在未提供时）
                if person and "person" not in params:
                    params["person"] = person
                if keyword and "kw" not in params:
                    params["kw"] = keyword
                return q, params
            except Exception as e:
                # 下一轮要求严格 JSON
                prompt += f"\nYour previous JSON was invalid: {e}. Return a strict JSON next time.\n"
                continue

        raise RuntimeError("LLM failed to return a valid JSON {query, params}.")

    # ---------- 执行查询 ----------
    def _run(self, query: str, params: Dict[str, Any]) -> Tuple[List[Dict], Optional[str]]:
        try:
            with self.driver.session(database=self.database) as sess:
                res = sess.run(query, **params)
                rows = [dict(r) for r in res]
                return rows, None
        except Exception as e:
            return [], str(e)

    # ---------- 结果标准化 ----------
    def _standardize(self, question: str, qtype: str, rows: List[Dict]) -> Any:
        if not rows:
            return None

        # 让GPT根据问题和查询结果智能决定返回什么答案
        return self._ask_gpt_for_answer(question, rows)

    def _generate_strategy_reflection(self, iteration_num: int, question: str, keyword: str, person: str, query_history: List[str]) -> str:
        """生成智能策略反思，避免重复相同查询"""
        
        if iteration_num <= 1:
            return ""
        
        # 检查是否重复了相同的查询
        if len(query_history) >= 2 and query_history[-1] == query_history[-2]:
            reflection = "\n🚨 CRITICAL: You just repeated the EXACT same query! This is ineffective.\n"
        else:
            reflection = "\n💭 STRATEGY REFLECTION: The previous approach failed. "
        
        # 根据迭代次数提供不同的策略建议
        if iteration_num == 2:
            reflection += """
🔄 TRY DIFFERENT APPROACH:
- If you used exact matching on event_type, try CONTAINS matching on name/description
- If you filtered by both person AND keyword, try removing person filter first
- If you used location filter, double-check the location name spelling
"""
        elif iteration_num == 3:
            reflection += """
🔄 BROADEN YOUR SEARCH STRATEGY:
- Remove ALL person filters and search by keyword/location only
- Try searching without keyword filter - just by location
- Consider that the event might be stored with different terminology
"""
        elif iteration_num == 4:
            reflection += """
🔄 GLOBAL SEARCH STRATEGY:
- Try a global search: MATCH (e:Event) WHERE toLower(e.location) CONTAINS 'part_of_location_name'
- Search by partial matches: use CONTAINS instead of exact equality
- Maybe the data doesn't exist - try searching all events at this location first
"""
        else:  # iteration_num >= 5
            reflection += """
🔄 EXHAUSTIVE FINAL ATTEMPT:
- Search ALL events at the location: MATCH (e:Event) WHERE toLower(e.location) = toLower('location_name')
- If still 0 rows, the data likely doesn't exist in the database
- As last resort, try different location name variations
"""
        
        # 提供具体的查询变化建议
        if keyword and person:
            reflection += f"\n💡 SPECIFIC SUGGESTION: Try removing person filter '{person}' and search only by keyword '{keyword}' and location.\n"
        elif keyword:
            reflection += f"\n💡 SPECIFIC SUGGESTION: Try broader keyword matching - use CONTAINS instead of exact match for '{keyword}'.\n"
        
        return reflection

    def _ask_gpt_for_answer(self, question: str, rows: List[Dict]) -> Any:
        """让GPT根据问题和查询结果智能生成最终答案"""
        
        # 为列表型问题发送更多数据
        question_lower = question.lower()
        is_list_question = any(keyword in question_lower for keyword in [
            "all dates", "all events", "all locations", "list of", "provide a list", 
            "chronological list", "describe all", "reflect on all"
        ])
        
        if is_list_question and len(rows) > 10:
            # 对于列表问题，发送更多数据以确保完整性
            sample_rows = rows[:25]  # 增加到25行
            data_info = f"Total {len(rows)} rows, showing first 25 for analysis"
            
            # 如果还有更多数据，提供统计信息
            if len(rows) > 25:
                # 统计所有唯一值
                all_values = {}
                for key in rows[0].keys():
                    values = [str(row.get(key, "")) for row in rows if row.get(key)]
                    all_values[key] = list(set(values))
                
                data_info += f"\nComplete unique values across all {len(rows)} rows:"
                for key, values in all_values.items():
                    data_info += f"\n{key}: {len(values)} unique values: {values[:10]}{'...' if len(values) > 10 else ''}"
        else:
            # 普通问题处理
            if len(rows) > 10:
                sample_rows = rows[:10]
                data_info = f"Total {len(rows)} rows, showing first 10 as sample"
            else:
                sample_rows = rows
                data_info = f"All {len(rows)} rows"
        
        # 构建数据摘要
        data_summary = []
        for i, row in enumerate(sample_rows):
            data_summary.append(f"Row {i+1}: {dict(row)}")
        
        prompt = f"""
You are analyzing query results to answer a specific question. Based on the question and the data returned from the database, provide the most appropriate answer.

Question: {question}

Data returned ({data_info}):
{chr(10).join(data_summary)}

Instructions:
1. Read the question carefully to understand what is being asked
2. Analyze the data to extract the relevant information
3. Return the answer in the most appropriate format:
   - For single item questions: return the item directly (string/number)
   - For list questions: return a JSON array ["item1", "item2", ...]
   - For chronological questions: sort by date and return appropriately
   - For "most recent" questions: find the latest date and return the requested field
4. If the question asks for dates, return ALL dates from the data
5. If the question asks for locations, return ALL locations from the data
6. If the question asks for activities/events, return ALL activity/event names from the data
7. If the question asks for descriptions, return ALL descriptions from the data
8. Remove duplicates appropriately
9. Sort chronologically if requested
10. IMPORTANT: If the question asks for "all" or "list of" something, make sure to include ALL items from the data, not just one

Return ONLY the final answer (no explanation, no extra text):
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            answer_text = response.choices[0].message.content.strip()
            
            # 尝试解析JSON数组
            if answer_text.startswith('[') and answer_text.endswith(']'):
                try:
                    return json.loads(answer_text)
                except:
                    # 如果JSON解析失败，按逗号分割
                    items = answer_text[1:-1].split(',')
                    return [item.strip().strip('"') for item in items if item.strip()]
            
            # 清理引号
            answer_text = answer_text.strip('"').strip("'")
            
            return answer_text
            
        except Exception as e:
            print(f"ERROR in _ask_gpt_for_answer: {e}")
            # 失败时的简单回退逻辑
            if len(rows) == 1:
                # 单行数据，返回第一个非空值
                for value in rows[0].values():
                    if value:
                        return str(value)
            else:
                # 多行数据，返回第一列的所有值
                first_key = list(rows[0].keys())[0]
                return [str(row.get(first_key, "")) for row in rows if row.get(first_key)]
            
            return "No answer found"

    # ---------- 主流程 ----------
    def search(self, question: str, max_iterations: int = 5) -> Dict[str, Any]:
        state = SearchState(question)
        state.max_iterations = max_iterations

        print(f"Starting agentic search for: {question}")
        print(f"Session: {state.session_id}")

        # 轻量抽取作为参数传递（不改变“无模版”本质）
        person, evt = _extract_person_and_event(question)
        # regex 漏检时 LLM 兜底
        if not person or (("involving" in question.lower() or "related to" in question.lower()) and not evt):
            p2, e2 = self._extract_entities_llm(question)
            person = person or p2
            evt = evt or e2

        cls = self._classify(question)
        need_cols: List[str] = cls["need"]

        while state.iteration < state.max_iterations and state.final_answer is None:
            state.iteration += 1
            print(f"\n-- Iteration {state.iteration} --")

            # 让 LLM 生成查询（无任何模板/样例）
            try:
                query, params = self._gen_query_json(
                    question=question,
                    need_columns=need_cols,
                    person=person,
                    keyword=evt,
                    prev_query=state.query_history[-1] if state.query_history else None,
                    last_error=state.last_error,
                    last_rows=state.last_result_rows,
                    missing_cols=state.last_missing_cols,
                    last_keys=state.last_row_keys,
                    query_history=state.query_history,
                )
            except Exception as e:
                state.reasoning.append(f"Query generation error: {e}")
                break

            state.query_history.append(query)
            print("Generated query:", query)
            print("Params:", params)

            # 执行
            rows, err = self._run(query, params)
            state.last_error = err
            state.last_result_rows = len(rows)
            state.last_row_keys = list(rows[0].keys()) if rows else []
            if err:
                print("Execution error:", err)
                state.reasoning.append(f"Execution error: {err}")
                continue

            print(f"Rows: {len(rows)}")
            if rows:
                print("First row keys:", list(rows[0].keys()))

            # 如果缺关键列（例如需要 date 却没返回），触发一次修正
            missing = [c for c in need_cols if rows and c not in rows[0]]
            state.last_missing_cols = missing

            # latest_activity_of_person：至少需要日期字段或事件字段之一
            if cls["type"] == "latest_activity_of_person" and rows:
                has_date = any(field in rows[0] for field in ["date", "timestamp"])
                has_event = any(field in rows[0] for field in ["event_type", "name", "event", "activity"])
                if has_date or has_event:
                    missing = []

            if rows and missing:
                msg = f"Missing columns {missing}, ask LLM to include them next round."
                print(msg)
                state.reasoning.append(msg)
                continue

            if rows:
                state.final_answer = self._standardize(question, cls["type"], rows)
                break

            state.reasoning.append("0 rows; ask LLM to self-correct and widen/adjust filters.")

        result = {
            "session_id": state.session_id,
            "question": question,
            "final_answer": state.final_answer,
            "standardized_answer": self._to_list(state.final_answer),
            "total_iterations": state.iteration,
            "search_successful": state.final_answer is not None,
            "reasoning_chain": state.reasoning,
            "query_history": state.query_history,
        }
        print("Final:", result)
        return result

    @staticmethod
    def _to_list(ans: Any) -> List[str]:
        if ans is None:
            return []
        if isinstance(ans, list):
            return [str(x).strip() for x in ans if str(x).strip()]
        return [str(ans).strip()]

    def close(self):
        """Close database connection"""
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()


# ------------------------- 自测 -------------------------

if __name__ == "__main__":
    engine = AgenticSearchEngine(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "test9"),
    )
    try:
        q = "List all locations visited by Carter Stewart in chronological order according to the story's timeline."
        print(engine.search(q))
    finally:
        engine.close()
