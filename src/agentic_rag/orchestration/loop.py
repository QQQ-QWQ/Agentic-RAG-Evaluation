"""
规划层 → 执行层（Deep Agent）→ 研判层 → 分支（结束 / 继续执行 / 重规划 / 问用户）。

通过 ``OrchestrationConfig``、``OrchestrationHooks`` 扩展；核心调度在本模块。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from agentic_rag import config as app_cfg

from agentic_rag.deep_planning.agent_runner import (
    build_topic4_deep_agent,
    format_agent_print,
    invoke_agent_once,
)
from agentic_rag.deep_planning.session_planner import (
    SessionPlan,
    compose_layer2_user_message,
    format_layer1_console,
    resolve_document_path,
    run_layer1_session_plan,
)
from agentic_rag.orchestration.judge_layer import run_orchestration_judge
from agentic_rag.orchestration.registry import OrchestrationHooks
from agentic_rag.orchestration.types import OrchestrationConfig, JudgeVerdict


def _plan_digest(plan: SessionPlan) -> str:
    return (
        f"task_summary={plan.task_summary}\n"
        f"needs_retrieval_tools={plan.needs_retrieval_tools}\n"
        f"suggested_pipelines={plan.suggested_pipelines}\n"
        f"plan_for_layer2={plan.plan_for_layer2}\n"
        f"reasoning_brief={plan.reasoning_brief}"
    )


def _read_multiline_until_end(
    prompt: str,
    *,
    end_sentinel: str = "END",
) -> str:
    """读取多行文本，直到单独一行（strip 后）等于 ``end_sentinel``（大小写不敏感）。"""
    print(prompt)
    lines: list[str] = []
    end_lower = end_sentinel.strip().lower()
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().lower() == end_lower:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def run_cli_agent_session(
    *,
    cli_doc: Path | None,
    skip_layer1: bool,
    once_text: str | None,
    temperature: float,
    json_debug: bool,
    config: OrchestrationConfig | None = None,
    hooks: OrchestrationHooks | None = None,
    multiline_interactive: bool = True,
) -> None:
    cfg = config or OrchestrationConfig()
    hk = hooks or OrchestrationHooks()

    if once_text is not None and once_text.strip():
        _run_single_turn_pipeline(
            user_raw=once_text.strip(),
            cli_doc=cli_doc,
            skip_layer1=skip_layer1,
            temperature=temperature,
            json_debug=json_debug,
            cfg=cfg,
            hooks=hk,
        )
        return

    print(
        "\n"
        "============================================================\n"
        "  Topic4 多层级编排\n"
        "  【第一层】会话规划\n"
        "  【第二层】Deep Agent + Topic4 RAG 工具\n"
        "  【第三层】研判（结束 / 继续执行 / 重规划 / 问用户）\n"
        "============================================================\n"
    )
    if cli_doc:
        print(f"  命令行已指定绑定文档：{cli_doc}\n")
    else:
        print(
            "  默认使用工程 Chroma 全库知识库（data/processed/documents.csv）。\n"
            "  请用自然语言描述需求；仅在需要单文件检索时再给出路径或命令行传文档。\n"
        )
    if multiline_interactive:
        print(
            "  【输入方式】多行粘贴：粘贴任意内容后换行，单独一行输入 END 再回车提交。\n"
            "  （不要用 PowerShell 的 PS> 直接粘贴整段当作命令；此处须在 Python 提示下输入。）\n"
            "  也可用：uv run python main.py agent --once-file data\\\\testset\\\\questions.csv\n"
        )
    else:
        print(
            "  【单行模式】每次只读一行；粘贴多行 CSV 只会读到第一行。"
            " 若需大段文本请去掉 --single-line 或使用 --once-file。\n"
        )

    try:
        if multiline_interactive:
            first_line = _read_multiline_until_end(
                "请在下方粘贴内容（可为多行 CSV / 长文本），最后单独一行输入 end 或 END 结束；仅输入 end 退出：\n",
            )
        else:
            first_line = input("请输入内容（自然语言；直接回车退出）：\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n再见。")
        return
    if not first_line:
        print("再见。")
        return

    agent, _state = _orchestrate_until_stable(
        user_original=first_line,
        cli_doc=cli_doc,
        skip_layer1=skip_layer1,
        temperature=temperature,
        cfg=cfg,
        hooks=hk,
        interactive_replan_prompt=True,
    )

    if agent is None:
        return

    while True:
        try:
            tip = (
                "继续对话（默认仅第二层）。走完整三层：块首行写 /full，其余为正文，最后单独一行 end 结束。\n"
                if not cfg.orchestrate_follow_ups
                else "继续（每轮完整编排已开启）；多行时仍以单独一行 end 结束。\n"
            )
            if multiline_interactive:
                extra = _read_multiline_until_end(f"{tip}")
            else:
                extra = input(tip).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not extra:
            print("再见。")
            break
        lines = extra.strip().splitlines()
        first_line = lines[0].strip().lower() if lines else ""
        full_body = "\n".join(lines[1:]).strip() if first_line == "/full" else ""
        want_full = first_line == "/full" or cfg.orchestrate_follow_ups
        if want_full:
            user_turn = full_body if first_line == "/full" else extra.strip()
            _orchestrate_until_stable(
                user_original=user_turn,
                cli_doc=cli_doc,
                skip_layer1=False,
                temperature=temperature,
                cfg=cfg,
                hooks=hk,
                interactive_replan_prompt=True,
                reuse_agent=agent,
                reuse_doc_path=cli_doc,
            )
            continue
        st = invoke_agent_once(agent, extra)
        print("\n--- 第二层回复 ---\n")
        print(format_agent_print(st))
        print()


def _run_single_turn_pipeline(
    *,
    user_raw: str,
    cli_doc: Path | None,
    skip_layer1: bool,
    temperature: float,
    json_debug: bool,
    cfg: OrchestrationConfig,
    hooks: OrchestrationHooks,
) -> None:
    _agent, state = _orchestrate_until_stable(
        user_original=user_raw,
        cli_doc=cli_doc,
        skip_layer1=skip_layer1,
        temperature=temperature,
        cfg=cfg,
        hooks=hooks,
        interactive_replan_prompt=False,
    )
    if json_debug and state:
        raw_msgs = state.get("messages", [])
        serial = []
        for m in raw_msgs:
            try:
                serial.append({"type": m.__class__.__name__, "content": getattr(m, "content", "")})
            except Exception:
                serial.append(str(m))
        print(json.dumps({"messages_debug": serial}, ensure_ascii=False, indent=2))


def _orchestrate_until_stable(
    *,
    user_original: str,
    cli_doc: Path | None,
    skip_layer1: bool,
    temperature: float,
    cfg: OrchestrationConfig,
    hooks: OrchestrationHooks,
    interactive_replan_prompt: bool,
    reuse_agent: Any | None = None,
    reuse_doc_path: Path | None = None,
) -> tuple[Any | None, dict[str, Any] | None]:
    hk = hooks

    def _fire(name: str, *args: Any) -> None:
        cb = getattr(hk, name, None)
        if callable(cb):
            cb(*args)

    accumulated_context = ""
    agent = reuse_agent
    doc_resolved: Path | None = reuse_doc_path or cli_doc
    last_state: dict[str, Any] | None = None

    orch_round = 0
    while orch_round < cfg.max_orchestration_rounds:
        orch_round += 1
        _fire("on_round_start", orch_round)

        if skip_layer1 and orch_round == 1:
            doc_hint = str(cli_doc) if cli_doc is not None else None
            plan = SessionPlan(
                document_path=doc_hint,
                task_summary=user_original[:80000],
                needs_retrieval_tools=True,
                suggested_pipelines=[],
                plan_for_layer2="（跳过第一层）按用户原文调用 Topic4 工具完成。",
                reasoning_brief="skip_layer1",
                raw={},
            )
            print("（已跳过第一层）\n")
            _fire("on_plan", plan)
        else:
            planning_input = user_original
            if accumulated_context.strip():
                planning_input = (
                    f"{user_original}\n\n【编排系统·重规划上下文】\n{accumulated_context.strip()}"
                )
            plan = run_layer1_session_plan(
                planning_input,
                cli_document_path=str(cli_doc) if cli_doc else None,
                prior_context=accumulated_context if orch_round > 1 else None,
                temperature=cfg.planner_temperature,
            )
            print()
            print(format_layer1_console(plan))
            print()
            _fire("on_plan", plan)

        if doc_resolved is None:
            doc_resolved = cli_doc or resolve_document_path(plan)
        # 未指定单文件时默认走 Chroma 全库（documents.csv），不要求用户补路径。

        if agent is None:
            sandbox_ws: Path | None = None
            if cfg.enable_sandbox_tools:
                if app_cfg.SANDBOX_ENABLED:
                    sandbox_ws = Path(tempfile.mkdtemp(prefix="topic4_agent_sbx_"))
                    print(f"[编排] 沙箱工作目录：{sandbox_ws}\n")
                else:
                    print(
                        "[编排] 已请求沙箱工具，但 SANDBOX_ENABLED 未开启；"
                        "未注册 sandbox_exec_python（可在 .env 设为 true）。\n"
                    )
            use_kb = doc_resolved is None
            agent = build_topic4_deep_agent(
                doc_path=str(doc_resolved) if doc_resolved else None,
                use_knowledge_base=use_kb,
                temperature=temperature,
                sandbox_workspace=sandbox_ws,
            )

        exec_addon = accumulated_context if orch_round > 1 else None
        exec_msg = compose_layer2_user_message(
            user_original=user_original,
            plan=plan,
            orchestration_addon=exec_addon,
            use_knowledge_base=(doc_resolved is None),
        )

        verdict: JudgeVerdict | None = None
        for attempt_idx in range(cfg.max_execute_retries_per_round):
            if attempt_idx > 0:
                print(
                    "\n[编排] 第三层判定「继续执行」，正在开始第二层第 "
                    f"{attempt_idx + 1}/{cfg.max_execute_retries_per_round} 次调用。\n"
                    "（Deep Agent 可能再次多次调用检索；完成前若终端暂无新标题属正常，并非卡死。）\n"
                )
            last_state = invoke_agent_once(agent, exec_msg)
            _fire("on_execute_state", last_state)
            transcript = format_agent_print(last_state)
            print("\n--- 第二层回复 ---\n")
            print(transcript)
            print()

            if not cfg.enable_judge:
                return agent, last_state

            kb_digest: dict | None = None
            if cfg.enable_kb_grounding_judge:
                from agentic_rag.orchestration.evidence_extract import (
                    extract_last_assistant_text,
                    extract_latest_evidence_excerpt,
                )
                from agentic_rag.orchestration.kb_grounding import run_kb_grounding_check

                msgs = last_state.get("messages") if isinstance(last_state, dict) else []
                ev = extract_latest_evidence_excerpt(msgs)
                ans_txt = extract_last_assistant_text(msgs) or transcript
                kb_digest = run_kb_grounding_check(
                    question=user_original,
                    generated_answer=ans_txt,
                    evidence_excerpt=ev,
                )
                print("\n--- 知识库对齐核验 ---\n")
                print(
                    json.dumps(
                        {
                            "grounded": kb_digest.get("grounded"),
                            "confidence": kb_digest.get("confidence"),
                            "issues": kb_digest.get("issues"),
                            "skipped": kb_digest.get("skipped"),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                print()

            verdict = run_orchestration_judge(
                user_goal=user_original,
                plan_digest=_plan_digest(plan),
                execution_transcript=transcript,
                orchestration_round=orch_round,
                temperature=cfg.judge_temperature,
                kb_grounding=kb_digest,
            )
            _fire("on_judge", verdict)
            print("\n--- 第三层研判 ---\n")
            print(verdict.summary_for_user or verdict.reasoning_brief)
            print()

            if verdict.verdict == "complete":
                return agent, last_state
            if verdict.verdict == "continue_execute":
                exec_msg = (
                    verdict.hint_for_next_execution
                    or "请结合上轮与用户目标改进答复，必要时再次调用检索工具。"
                )
                continue
            break

        if verdict is None:
            return agent, last_state

        if verdict.verdict == "replan":
            hint = (verdict.hint_for_next_planner or "").strip()
            accumulated_context += (
                f"\n[轮次{orch_round}] 研判要求重规划"
                f"{('：' + hint) if hint else '。'}\n"
            )
            continue

        if verdict.verdict == "need_user_input":
            if interactive_replan_prompt:
                extra = input("研判层需要您补充（单行，可空跳过）：\n> ").strip()
                if extra:
                    accumulated_context += f"\n[用户补充] {extra}\n"
            else:
                return agent, last_state
            continue

        if verdict.verdict == "continue_execute":
            accumulated_context += (
                f"\n[编排器] 本轮执行已达 {cfg.max_execute_retries_per_round} "
                "次上限；转入下一轮外层规划。\n"
            )
            continue

    print(f"\n（已达最大编排轮次 {cfg.max_orchestration_rounds}。）\n")
    return agent, last_state

