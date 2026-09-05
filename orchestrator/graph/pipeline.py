"""LangGraph pipeline — minimal real path: no external encoders (models 1-4 bundle their own CLIP/Swin/Prithvi/CROMA).

Previous 14-node graph included preprocessing/encoder_selector/encoder_compat/coreg_gate/vision_encoder/fusion/tile_manager
which synthesized dummy tiles/SSIM and external embeddings. Since shims call load_and_convert_s2 / ask_geochat /
compute_indices / Model4Engine directly with raw image_path, those nodes are removed. Only real nodes remain.
"""
from __future__ import annotations
from typing import Literal
from langgraph.graph import StateGraph, END

from orchestrator.models.graph_state import GraphState
from orchestrator.agents.input_validator import input_validator_node
from orchestrator.agents.coreference_resolver import coreference_resolver_node
from orchestrator.agents.router_agent import router_node
from orchestrator.agents.planner_agent import planner_node
from orchestrator.agents.task_agents import task_agent_node
from orchestrator.agents.post_processing import post_processing_node
from orchestrator.agents.error_handler import error_handler_node
from orchestrator.agents.response_composer import response_composer_node
from orchestrator.registry.policy_gate import policy_gate_node

# --- conditional routing helpers ---
def after_validator(state: GraphState) -> Literal["router","error_handler"]:
    if not state.get("validation_passed"):
        return "error_handler"
    return "router"

def after_policy_gate(state: GraphState) -> Literal["task_agent","error_handler"]:
    if state.get("error") and state.get("error_code") == "policy_denied":
        return "error_handler"
    if state.get("policy_passed"):
        return "task_agent"
    return "error_handler"

def after_planner(state: GraphState) -> Literal["policy_gate","response_composer"]:
    plan = state.get("plan") or {}
    # Generalizable skip: if planner set skip_models (LLM-driven for any new vocab), jump to composer
    # This handles greeting/chitchat/help/out_of_scope and definitional NDVI without hardcoding word lists
    if plan.get("skip_models") or state.get("skip_models"):
        return "response_composer"
    # Also handle any non-geospatial intent that should not run vision
    if state.get("query_intent") in ("greeting","chitchat","help","out_of_scope") or state.get("task_type") in ("greeting","chitchat","help","out_of_scope","general"):
        return "response_composer"
    if plan.get("task_type") in ("greeting","chitchat","help","out_of_scope","general","REFUSE"):
        return "response_composer"
    # REFUSE also goes to composer for friendly message
    if plan.get("task_type") == "REFUSE" or state.get("task_type") == "REFUSE":
        return "response_composer"
    # All 4 real models handle their own vision encoding internally — no external encoder needed.
    # All geospatial go through policy gate before GPU
    return "policy_gate"

MAX_ATTEMPTS = 2  # total attempts: 1 initial + 1 retry (retries = MAX_ATTEMPTS-1) per approved P0-01
MAX_REFLECTION_ITERATIONS = MAX_ATTEMPTS  # kept for compat

def after_post_processing(state: GraphState) -> Literal["task_agent","response_composer","error_handler"]:
    if state.get("_needs_retry"):
        policy = state.get("retry_policy") or {"max_confidence": MAX_ATTEMPTS}
        max_conf = policy.get("max_confidence", MAX_ATTEMPTS) if isinstance(policy, dict) else MAX_ATTEMPTS
        max_conf = min(int(max_conf), MAX_ATTEMPTS)
        retries = state.get("retry_count", 0)
        if retries < max_conf:
            return "task_agent"
        state["error"] = f"low confidence after {retries} retries (cap MAX_ATTEMPTS={MAX_ATTEMPTS})"
        state["error_type"] = "permanent"
        state["error_code"] = "low_confidence_permanent"
        return "error_handler"
    if state.get("final_result") is None and state.get("error"):
        return "error_handler"
    return "response_composer"

def after_task_agent(state: GraphState) -> Literal["post_processing","error_handler"]:
    if state.get("error") and not state.get("task_output"):
        return "error_handler"
    return "post_processing"

def build_graph():
    g = StateGraph(GraphState)

    # 8-node state graph (7 happy + terminal) + policy_gate cross-cutting (counts as control, not happy step)
    g.add_node("input_validator", input_validator_node)
    g.add_node("coreference_resolver", coreference_resolver_node)
    g.add_node("router", router_node)
    g.add_node("planner", planner_node)
    g.add_node("policy_gate", policy_gate_node)
    g.add_node("task_agent", task_agent_node)
    g.add_node("post_processing", post_processing_node)
    g.add_node("error_handler", error_handler_node)
    g.add_node("response_composer", response_composer_node)

    g.set_entry_point("input_validator")
    g.add_conditional_edges("input_validator", after_validator, {"router":"coreference_resolver", "error_handler":"error_handler"})
    g.add_edge("coreference_resolver", "router")
    g.add_edge("router", "planner")
    g.add_conditional_edges("planner", after_planner, {"policy_gate":"policy_gate", "response_composer":"response_composer"})
    g.add_conditional_edges("policy_gate", after_policy_gate, {"task_agent":"task_agent", "error_handler":"error_handler"})
    g.add_conditional_edges("task_agent", after_task_agent, {"post_processing":"post_processing", "error_handler":"error_handler"})
    g.add_conditional_edges("post_processing", after_post_processing, {"task_agent":"task_agent", "response_composer":"response_composer", "error_handler":"error_handler"})
    g.add_edge("response_composer", END)
    g.add_edge("error_handler", END)

    compiled = g.compile()
    return compiled

# singleton
pipeline = build_graph()

def get_pipeline():
    return pipeline
