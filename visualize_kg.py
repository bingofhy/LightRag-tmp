"""
LightRAG 知识图谱可视化工具

直接读取 LightRAG 生成的 GraphML 文件进行可视化
"""

import argparse
from pathlib import Path

import networkx as nx


def load_graph(graphml_path: str) -> nx.DiGraph:
    """从 GraphML 文件加载图数据"""
    path = Path(graphml_path)
    if not path.exists():
        raise FileNotFoundError(f"GraphML file not found: {graphml_path}")

    print(f"Loading GraphML: {graphml_path}")
    G = nx.read_graphml(graphml_path)

    print(f"Loaded {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def filter_graph(
    G: nx.DiGraph,
    center_node: str = None,
    hops: int = None,
    min_degree: int = 0,
    max_nodes: int = None,
) -> nx.DiGraph:
    """过滤图数据"""
    if center_node and hops:
        # 聚焦模式：提取以某节点为中心的子图
        if center_node not in G:
            print(f"Warning: Node '{center_node}' not found in graph")
            available = [n for n in G.nodes() if center_node.lower() in n.lower()]
            if available:
                print(f"Did you mean: {', '.join(available[:5])}")
            return G.subgraph([]).copy()

        nodes_set = {center_node}
        current_level = {center_node}

        for _ in range(hops):
            next_level = set()
            for node in current_level:
                neighbors = set(G.neighbors(node)) | set(G.predecessors(node))
                next_level.update(neighbors)
            nodes_set.update(next_level)
            current_level = next_level

        result = G.subgraph(nodes_set).copy()
        print(f"Extracted subgraph: {result.number_of_nodes()} nodes, {result.number_of_edges()} edges (center: {center_node}, hops: {hops})")
        return result

    if min_degree > 0:
        # 按度数过滤
        nodes_to_keep = [n for n, d in G.degree() if d >= min_degree]
        isolated_removed = G.number_of_nodes() - len(nodes_to_keep)
        G = G.subgraph(nodes_to_keep).copy()
        print(f"Removed {isolated_removed} isolated nodes (min_degree={min_degree})")

    if max_nodes and G.number_of_nodes() > max_nodes:
        # 按度数排序，保留最重要的节点
        sorted_nodes = sorted(G.degree(), key=lambda x: x[1], reverse=True)
        nodes_to_keep = [n for n, _ in sorted_nodes[:max_nodes]]
        removed = G.number_of_nodes() - len(nodes_to_keep)
        G = G.subgraph(nodes_to_keep).copy()
        print(f"Limited to {max_nodes} nodes (removed {removed} low-degree nodes)")

    return G


def list_entities(G: nx.DiGraph, top_n: int = 20) -> list:
    """列出所有实体（按度数排序）"""
    degrees = dict(G.degree())
    sorted_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)
    return sorted_nodes[:top_n]


def visualize_pyvis(
    G: nx.DiGraph,
    output_path: str = "kg_visualization.html",
    center_node: str = None,
    height: str = "900px",
):
    """使用 pyvis 生成交互式 HTML"""
    try:
        from pyvis.network import Network
    except ImportError:
        print("pyvis not installed. Install with: pip install pyvis")
        return

    print(f"Generating interactive visualization...")

    # 创建网络
    net = Network(
        height=height,
        width="100%",
        directed=True,
        notebook=False,
        cdn_resources="in_line",
    )

    # 手动添加节点和边，确保所有属性都被保留
    for node, data in G.nodes(data=True):
        label = node
        title = data.get("description", "")
        entity_type = data.get("entity_type", "unknown")

        # 根据类型设置颜色
        color_map = {
            "person": "#6ab0ff",
            "organization": "#ff6b6b",
            "location": "#51cf66",
            "event": "#ffd43b",
            "concept": "#cc5de8",
            "method": "#ff922b",
            "unknown": "#adb5bd",
        }
        color = color_map.get(entity_type.lower(), "#adb5bd")

        # 根据度数设置大小
        degree = G.degree(node)
        size = 10 + min(degree * 2, 40)

        # 高亮中心节点
        if center_node and (node == center_node or center_node.lower() in node.lower()):
            color = "#e03131"
            size = 50

        net.add_node(
            node,
            label=label,
            title=title,
            color=color,
            size=size,
            font={"size": 14, "color": "#333"},
        )

    # 添加边
    for u, v, data in G.edges(data=True):
        description = data.get("description", "")
        keywords = data.get("keywords", "")
        title = f"{keywords}\n{description}" if keywords else description

        net.add_edge(
            u,
            v,
            title=title,
            color="#999",
            arrows="to",
            smooth={"type": "continuous"},
        )

    # 配置物理布局
    # 调整参数让孤立节点也能被看到
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -5000,
          "centralGravity": 0.2,
          "springLength": 200,
          "springConstant": 0.05,
          "damping": 0.6,
          "avoidOverlap": 0.5
        },
        "solver": "barnesHut",
        "timestep": 0.5,
        "stabilization": {
          "iterations": 500,
          "updateInterval": 50
        }
      },
      "nodes": {
        "borderWidth": 1,
        "borderWidthSelected": 3,
        "font": {"size": 14}
      },
      "edges": {
        "color": {"color": "#999", "highlight": "#ff6b6b", "hover": "#ff6b6b"},
        "selectionWidth": 2,
        "width": 1
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "navigationButtons": true,
        "keyboard": true,
        "zoomView": true
      }
    }
    """)

    # 保存 HTML
    html = net.generate_html()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Visualization saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Visualize LightRAG Knowledge Graph from GraphML"
    )
    parser.add_argument(
        "--graphml",
        type=str,
        default="./rag_storage/graph_chunk_entity_relation.graphml",
        help="Path to GraphML file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="kg_visualization.html",
        help="Output HTML file path",
    )
    parser.add_argument(
        "--entity",
        type=str,
        default=None,
        help="Center entity to focus on (e.g., 'Xiaomi Company')",
    )
    parser.add_argument(
        "--hops",
        type=int,
        default=2,
        help="Number of hops from center entity (default: 2)",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=None,
        help="Maximum number of nodes to display (default: no limit)",
    )
    parser.add_argument(
        "--min-degree",
        type=int,
        default=0,
        help="Minimum node degree to include (default: 0, include all)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List top entities and exit",
    )
    parser.add_argument(
        "--list-all",
        action="store_true",
        help="List ALL entities including isolated ones",
    )

    args = parser.parse_args()

    # 加载图
    G = load_graph(args.graphml)

    print(f"\nGraph Statistics:")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")

    # 统计孤立节点
    isolated = [n for n, d in G.degree() if d == 0]
    if isolated:
        print(f"  Isolated nodes: {len(isolated)}")

    # 统计实体类型
    entity_types = {}
    for _, data in G.nodes(data=True):
        etype = data.get("entity_type", "unknown")
        entity_types[etype] = entity_types.get(etype, 0) + 1
    print(f"  Entity types: {entity_types}")

    # 列出实体
    if args.list or args.list_all:
        top_n = G.number_of_nodes() if args.list_all else 50
        print(f"\nTop {top_n} entities by degree:")
        for entity, degree in list_entities(G, top_n):
            etype = G.nodes[entity].get("entity_type", "unknown")
            print(f"  {entity} [{etype}]: {degree} connections")
        return

    # 过滤图
    G_filtered = filter_graph(
        G,
        center_node=args.entity,
        hops=args.hops if args.entity else None,
        min_degree=args.min_degree,
        max_nodes=args.max_nodes,
    )

    print(f"\nFinal graph: {G_filtered.number_of_nodes()} nodes, {G_filtered.number_of_edges()} edges")

    # 可视化
    visualize_pyvis(G_filtered, args.output, center_node=args.entity)


if __name__ == "__main__":
    main()
