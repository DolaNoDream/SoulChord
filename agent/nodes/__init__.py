"""LangGraph 7 节点。

★ H19: Runtime 负责生命周期 / Graph 负责单次推理 / 禁 while True: graph.invoke()
★ v0.1.2 P0-1: 所有 Node return dict | str（partial update），不调 state.update()
"""
