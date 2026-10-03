"""LangGraph topology: coordinator fans out to four data agents, which join at quant risk,
then hedging strategy and the evidence audit run in sequence."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from stop_loss.agents.nodes import Toolkit, build_nodes
from stop_loss.agents.state import AnalysisState

FAN_OUT = ("market", "news", "impact")


def build_analysis_graph(
    kit: Toolkit, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    nodes = build_nodes(kit)
    builder = StateGraph(AnalysisState)
    for name, fn in nodes.items():
        builder.add_node(name, fn)
    builder.add_edge(START, "coordinator")
    for name in FAN_OUT:
        builder.add_edge("coordinator", name)
    builder.add_edge(list(FAN_OUT), "quant")
    builder.add_edge("quant", "hedging")
    builder.add_edge("hedging", "audit")
    builder.add_edge("audit", END)
    return builder.compile(checkpointer=checkpointer)
