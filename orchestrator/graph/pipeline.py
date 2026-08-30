"""LangGraph pipeline — 14 nodes, conditional edges for gates/retries."""
from __future__ import annotations
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END

from orchestrator.models.graph_state import GraphState
from orchestrator.agents.input_validator import input_validator_node
from orchestrator.agents.coreference_resolver import coreference_resolver_node
from orchestrator.agents.router_agent import router_node
from orchestrator.agents.planner_agent import planner_node
from orchestrator.agents.encoder_selector import encoder_selector_node
from orchestrator.agents.encoder_compat import encoder_compat_node
from orchestrator.agents.preprocessing import preprocessing_node
from orchestrator.agents.coreg_gate import coreg_gate_node
from orchestrator.agents.vision_encoder import vision_encoder_node
from orchestrator.agents.fusion import fusion_node
from orchestrator.agents.task_agents import task_agent_node
from orchestrator.agents.tile_manager import tile_manager_node
from orchestrator.agents.post_processing import post_processing_node
from orchestrator.agents.error_handler import error_handler_node
from orchestrator.agents.response_composer import response_composer_node

# --- conditional routing helpers ---
def after_validator(state: GraphState) -> Literal["router","error_handler"]:
    if not state.get("validation_passed"):
        return "error_handler"
    return "router"

def after_compat(state: GraphState) -> Literal["coreg_gate","error_handler"]:
    if not state.get("compat_passed"):
        return "error_handler"
    return "coreg_gate"

def after_coreg_gate(state: GraphState) -> Literal["vision_encoder","preprocessing","error_handler"]:
    if state.get("coreg_passed"):
        return "vision_encoder"
    policy = state.get("retry_policy") or {"max_coreg": 2}
    max_coreg = policy.get("max_coreg", 2) if isinstance(policy, dict) else 2
    retries = state.get("coreg_retries", 0)
    # audit #4: transient while retries <= max, permanent after
    if retries <= max_coreg:
        # transient — retry preprocessing (re-tile / re-coreg with higher GCP)
        return "preprocessing"
    state["error"] = f"coreg failed after {retries} retries (ssim={state.get('coreg',{}).get('ssim')})"
    state["error_type"] = "permanent"
    state["error_code"] = "coreg_ssim_below_threshold"
    return "error_handler"

def after_post_processing(state: GraphState) -> Literal["task_agent","response_composer","error_handler"]:
    if state.get("_needs_retry"):
        policy = state.get("retry_policy") or {"max_confidence": 3}
        max_conf = policy.get("max_confidence", 3) if isinstance(policy, dict) else 3
        retries = state.get("retry_count", 0)
        if retries <= max_conf:
            return "task_agent"
        state["error"] = f"low confidence after {retries} retries"
        state["error_type"] = "permanent"
        state["error_code"] = "low_confidence_permanent"
        return "error_handler"
    if state.get("final_result") is None and state.get("error"):
        # if error is permanent, go to error_handler; if transient and retries left, error_handler will decide
        return "error_handler"
    return "response_composer"

def after_vision_encoder(state: GraphState) -> Literal["fusion","vision_encoder","error_handler"]:
    # node increments retry_count on transient; pure routing here
    if state.get("error_type") == "transient" and state.get("error_code") in ("vision_encoder_timeout","node_timeout","gpu_oom","connection_reset","fusion_llm_timeout"):
        policy = state.get("retry_policy") or {"max_transient": 2}
        max_tr = policy.get("max_transient", 2) if isinstance(policy, dict) else 2
        retries = state.get("retry_count", 0)
        # retries is already incremented by node (1 after first failure, 2 after second, etc.)
        # allow up to max_tr retries → total attempts = max_tr + 1
        if retries <= max_tr:
            return "vision_encoder"
    if state.get("error"):
        return "error_handler"
    return "fusion"

def after_fusion(state: GraphState) -> Literal["task_agent","fusion","error_handler"]:
    if state.get("error_type") == "transient" and state.get("error_code") in ("fusion_llm_timeout","node_timeout","circuit_open","gpu_oom","vision_encoder_timeout"):
        policy = state.get("retry_policy") or {"max_transient": 2}
        max_tr = policy.get("max_transient", 2) if isinstance(policy, dict) else 2
        retries = state.get("retry_count", 0)
        if retries <= max_tr:
            return "fusion"
    if state.get("error"):
        return "error_handler"
    return "task_agent"

def after_task_agent(state: GraphState) -> Literal["tile_manager","error_handler"]:
    if state.get("error") and not state.get("task_output"):
        return "error_handler"
    return "tile_manager"

def build_graph():
    g = StateGraph(GraphState)

    # add nodes
    g.add_node("input_validator", input_validator_node)
    g.add_node("coreference_resolver", coreference_resolver_node)
    g.add_node("router", router_node)
    g.add_node("planner", planner_node)
    g.add_node("encoder_selector", encoder_selector_node)
    g.add_node("encoder_compat", encoder_compat_node)
    g.add_node("preprocessing", preprocessing_node)
    g.add_node("coreg_gate", coreg_gate_node)
    g.add_node("vision_encoder", vision_encoder_node)
    g.add_node("fusion", fusion_node)
    g.add_node("task_agent", task_agent_node)
    g.add_node("tile_manager", tile_manager_node)
    g.add_node("post_processing", post_processing_node)
    g.add_node("error_handler", error_handler_node)
    g.add_node("response_composer", response_composer_node)

    # INTENTIONALLY SEQUENTIAL: planner → preprocessing → encoder_selector → encoder_compat
    # Parallel fan-out (planner → {preprocessing, encoder_selector}) was tested and rejected:
    # encoder_selector is ~1ms (rule-based), preprocessing is O(seconds) — no latency gain.
    # Parallel caused 2× execution of all downstream nodes (vision_encoder, fusion, task_agent)
    # and barrier deadlock on coreg_gate → preprocessing retry path in Pregel.
    # Intended parallel topology is documented in graph.mmd only.
    g.set_entry_point("input_validator")
    g.add_conditional_edges("input_validator", after_validator, {"router":"coreference_resolver", "error_handler":"error_handler"})
    g.add_edge("coreference_resolver", "router")
    g.add_edge("router", "planner")
    g.add_edge("planner", "preprocessing")
    g.add_edge("preprocessing", "encoder_selector")
    g.add_edge("encoder_selector", "encoder_compat")
    g.add_conditional_edges("encoder_compat", after_compat, {"coreg_gate":"coreg_gate", "error_handler":"error_handler"})
    # FIX #2: coreg_gate retry goes explicitly to preprocessing (not error_handler until max retries)
    g.add_conditional_edges("coreg_gate", after_coreg_gate, {"vision_encoder":"vision_encoder", "preprocessing":"preprocessing", "error_handler":"error_handler"})
    g.add_conditional_edges("vision_encoder", after_vision_encoder, {"fusion":"fusion", "vision_encoder":"vision_encoder", "error_handler":"error_handler"})
    g.add_conditional_edges("fusion", after_fusion, {"task_agent":"task_agent", "fusion":"fusion", "error_handler":"error_handler"})
    g.add_conditional_edges("task_agent", after_task_agent, {"tile_manager":"tile_manager", "error_handler":"error_handler"})
    # Note FIX #3: Tile Manager is a persistent state service — preprocessing writes tile list to Redis/state,
    # task_agent updates per-tile status; graph shows sequential task_agent → tile_manager → post_processing
    # for simplicity, but actual tile creation event is via state write in preprocessing_node (see preprocessing.py:42)
    g.add_edge("tile_manager", "post_processing")
    g.add_conditional_edges("post_processing", after_post_processing, {"task_agent":"task_agent", "response_composer":"response_composer", "error_handler":"error_handler"})
    g.add_edge("response_composer", END)
    g.add_edge("error_handler", END)

    compiled = g.compile()
    return compiled

# singleton
pipeline = build_graph()

def get_pipeline():
    return pipeline
