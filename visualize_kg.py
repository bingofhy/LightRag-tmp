"""
LightRAG 知识图谱可视化工具 (简化版)

功能:
- 选择实体，只显示它的关系网络
- 设置跳数（1跳、2跳等）
- 实体搜索过滤
"""

import argparse
import json
from pathlib import Path
from typing import Optional

import networkx as nx


def load_graph_from_storage(storage_path: str) -> nx.DiGraph:
    """从 rag_storage 加载图数据"""
    storage = Path(storage_path)

    # 优先读取 GraphML
    graphml_file = storage / "graph_chunk_entity_relation.graphml"
    if graphml_file.exists():
        print(f"Loading GraphML: {graphml_file}")
        return nx.read_graphml(graphml_file)

    # 从 JSON 文件构建
    print("Building graph from JSON files...")

    entities_file = storage / "kv_store_full_entities.json"
    relations_file = storage / "kv_store_full_relations.json"

    G = nx.DiGraph()

    # 加载实体
    if entities_file.exists():
        with open(entities_file, "r", encoding="utf-8") as f:
            entities_data = json.load(f)
            for doc_id, doc_data in entities_data.items():
                for entity in doc_data.get("entity_names", []):
                    G.add_node(entity, type="entity")

    # 加载关系
    if relations_file.exists():
        with open(relations_file, "r", encoding="utf-8") as f:
            relations_data = json.load(f)
            for doc_id, doc_data in relations_data.items():
                for source, target in doc_data.get("relation_pairs", []):
                    G.add_edge(source, target)

    print(f"Loaded {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def extract_subgraph(
    G: nx.Graph,
    center_node: str,
    hops: int = 1,
    max_nodes: int = 100,
) -> nx.Graph:
    """提取以某个节点为中心的子图"""
    if center_node not in G:
        print(f"Node '{center_node}' not found in graph!")
        return G.subgraph([]).copy()

    # 获取n跳内的所有节点
    nodes_set = {center_node}
    current_level = {center_node}

    for _ in range(hops):
        next_level = set()
        for node in current_level:
            neighbors = set(G.neighbors(node))
            next_level.update(neighbors)
        nodes_set.update(next_level)
        current_level = next_level

        # 限制节点数
        if len(nodes_set) >= max_nodes:
            print(f"Reached max nodes limit ({max_nodes})")
            break

    subgraph = G.subgraph(nodes_set).copy()
    print(f"Extracted {subgraph.number_of_nodes()} nodes, {subgraph.number_of_edges()} edges (center: {center_node}, hops: {hops})")
    return subgraph


def list_entities(G: nx.Graph, top_n: int = 20) -> list:
    """列出所有实体（按度数排序）"""
    degrees = dict(G.degree())
    sorted_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)
    return sorted_nodes[:top_n]


def visualize_pyvis(
    G: nx.Graph,
    output_path: str = "kg_visualization.html",
    center_node: Optional[str] = None,
    height: str = "900px",
):
    """使用 pyvis 生成交互式 HTML"""
    try:
        from pyvis.network import Network
    except ImportError:
        print("pyvis not installed. Install with: pip install pyvis")
        return

    print(f"Generating interactive visualization...")

    net = Network(
        height=height,
        width="100%",
        directed=G.is_directed(),
        notebook=False,
        cdn_resources="in_line",
    )

    net.from_nx(G)

    # 高亮中心节点
    if center_node:
        for node in net.nodes:
            if node["label"] == center_node or node["id"] == center_node:
                node["color"] = "#ff6b6b"
                node["size"] = 50
            else:
                node["color"] = "#4ecdc4"
                node["size"] = 20

    # 物理布局参数
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -5000,
          "centralGravity": 0.3,
          "springLength": 100,
          "springConstant": 0.05
        }
      },
      "nodes": {
        "font": {"size": 16, "color": "#333"},
        "borderWidth": 2,
        "borderWidthSelected": 4
      },
      "edges": {
        "arrows": {"to": {"enabled": true}},
        "smooth": {"type": "continuous"},
        "color": {"color": "#999", "highlight": "#ff6b6b"}
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "navigationButtons": true
      }
    }
    """)

    # 手动保存确保 UTF-8 编码
    html = net.generate_html()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Interactive visualization saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Visualize LightRAG Knowledge Graph")
    parser.add_argument(
        "--storage",
        type=str,
        default="./rag_storage",
        help="Path to rag_storage directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="kg_visualization.html",
        help="Output file path",
    )
    parser.add_argument(
        "--entity",
        type=str,
        default=None,
        help="Center entity to focus on (e.g., '小米公司')",
    )
    parser.add_argument(
        "--hops",
        type=int,
        default=1,
        help="Number of hops from center entity (default: 1)",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=100,
        help="Maximum number of nodes to display",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List top entities and exit",
    )
    parser.add_argument(
        "--min-degree",
        type=int,
        default=0,
        help="Minimum node degree to include (only used when --entity is not specified)",
    )

    args = parser.parse_args()

    # 加载图
    G = load_graph_from_storage(args.storage)

    print(f"\nGraph Statistics:")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")

    # 列出实体
    if args.list:
        print(f"\nTop {args.max_nodes} entities by degree:")
        for entity, degree in list_entities(G, args.max_nodes):
            print(f"  {entity}: {degree} connections")
        return

    # 选择模式
    if args.entity:
        # 聚焦某个实体
        subgraph = extract_subgraph(G, args.entity, args.hops, args.max_nodes)
        visualize_pyvis(subgraph, args.output, center_node=args.entity)
    else:
        # 全图模式（带过滤）
        if args.min_degree > 0:
            nodes_to_keep = [n for n, d in G.degree() if d >= args.min_degree]
            G = G.subgraph(nodes_to_keep).copy()
            print(f"After degree filter (min={args.min_degree}): {G.number_of_nodes()} nodes")

        if G.number_of_nodes() > args.max_nodes:
            # 按度数排序，保留最重要的节点
            top_nodes = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:args.max_nodes]
            nodes_to_keep = [n for n, _ in top_nodes]
            G = G.subgraph(nodes_to_keep).copy()
            print(f"Limited to {G.number_of_nodes()} nodes")

        visualize_pyvis(G, args.output)


if __name__ == "__main__":
    main()
