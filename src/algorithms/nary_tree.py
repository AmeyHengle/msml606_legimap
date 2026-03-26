"""
nary_tree.py — N-ary citation tree with BFS traversal.

Each node is a court case. Each directed edge from A to B means "A cites B".
Technically this is an adjacency-list directed graph, but I'm calling it a
tree because I always traverse it rooted at a single seed node (BFS), which
gives you a tree-shaped subgraph — which is exactly what the UI visualises.

I track in-degree separately so the Seed-and-Expand algorithm can use it
as a quick importance signal without doing an expensive reverse scan.
"""

from __future__ import annotations
from typing import Optional
from collections import deque


class TreeNode:
    """One case in the network. Stores its metadata and outgoing citation edges."""

    __slots__ = ("case_id", "metadata", "children")

    def __init__(self, case_id, metadata: dict = None):
        self.case_id  = case_id
        self.metadata = metadata or {}
        self.children: list["Edge"] = []

    def __repr__(self) -> str:
        return f"TreeNode(id={self.case_id}, name={self.metadata.get('name', '?')!r}, children={len(self.children)})"


class Edge:
    """A directed citation edge. weight = how many times the opinion cites that case."""

    __slots__ = ("target_id", "weight")

    def __init__(self, target_id, weight: int = 1):
        self.target_id = target_id
        self.weight    = weight

    def __repr__(self) -> str:
        return f"Edge(-> {self.target_id}, weight={self.weight})"


class NaryTree:
    """
    The full citation network, stored as an adjacency list.

    _nodes maps case_id -> TreeNode.
    _in_degree maps case_id -> how many other nodes point to it.
    """

    def __init__(self):
        self._nodes:     dict = {}
        self._in_degree: dict = {}

    def add_node(self, case_id, metadata: dict = None) -> None:
        """Register a case. If it already exists, update its metadata."""
        if case_id in self._nodes:
            self._nodes[case_id].metadata = metadata or {}
        else:
            self._nodes[case_id]     = TreeNode(case_id, metadata)
            self._in_degree[case_id] = 0

    def add_edge(self, parent_id, child_id, weight: int = 1) -> None:
        """
        Add a citation edge: parent_id cites child_id.
        Silently skips if either node isn't registered yet.
        If the edge already exists, I accumulate the weight instead of
        adding a duplicate.
        """
        if parent_id not in self._nodes or child_id not in self._nodes:
            return

        for existing_edge in self._nodes[parent_id].children:
            if existing_edge.target_id == child_id:
                existing_edge.weight += weight
                return

        self._nodes[parent_id].children.append(Edge(child_id, weight))
        self._in_degree[child_id] = self._in_degree.get(child_id, 0) + 1

    def has_node(self, case_id) -> bool:
        return case_id in self._nodes

    def get_node(self, case_id) -> Optional[TreeNode]:
        return self._nodes.get(case_id)

    def get_metadata(self, case_id) -> Optional[dict]:
        node = self._nodes.get(case_id)
        return node.metadata if node else None

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return sum(len(n.children) for n in self._nodes.values())

    def in_degree(self, case_id) -> int:
        return self._in_degree.get(case_id, 0)

    def out_degree(self, case_id) -> int:
        node = self._nodes.get(case_id)
        return len(node.children) if node else 0

    def all_node_ids(self) -> list:
        return list(self._nodes.keys())

    def bfs(self, root_id, max_depth: int = 3, direction: str = "outgoing") -> list[tuple]:
        """
        BFS from root_id up to max_depth hops.
        Returns a list of (case_id, depth) in discovery order.

        direction:
          "outgoing" — cases that root_id cites
          "incoming" — cases that cite root_id
          "both"     — union of the above
        """
        if root_id not in self._nodes:
            return []

        visited: set = set()
        result: list = []
        queue: deque = deque()

        queue.append((root_id, 0))
        visited.add(root_id)

        while queue:
            current_id, depth = queue.popleft()
            result.append((current_id, depth))

            if depth >= max_depth:
                continue

            for neighbour_id in self._get_neighbours(current_id, direction):
                if neighbour_id not in visited:
                    visited.add(neighbour_id)
                    queue.append((neighbour_id, depth + 1))

        return result

    def _get_neighbours(self, case_id, direction: str) -> list:
        """Return neighbour IDs for BFS expansion in the given direction."""
        node = self._nodes.get(case_id)
        if node is None:
            return []

        outgoing = [e.target_id for e in node.children]

        if direction == "outgoing":
            return outgoing

        incoming = [
            nid for nid, n in self._nodes.items()
            if any(e.target_id == case_id for e in n.children)
        ]

        if direction == "incoming":
            return incoming

        return list(set(outgoing + incoming))

    def bfs_subgraph(self, root_id, max_depth: int = 3, direction: str = "outgoing") -> dict:
        """
        Return the BFS subgraph as a vis.js-compatible dict:
          { "nodes": [...], "edges": [...] }
        Only includes edges between nodes that are actually in the subgraph.
        """
        bfs_result           = self.bfs(root_id, max_depth=max_depth, direction=direction)
        node_ids_in_subgraph = {nid for nid, _ in bfs_result}
        depth_map            = {nid: depth for nid, depth in bfs_result}

        nodes = []
        for nid, depth in bfs_result:
            meta = self.get_metadata(nid) or {}
            nodes.append({
                "id"       : nid,
                "name"     : meta.get("name_abbreviation", meta.get("name", str(nid))),
                "full_name": meta.get("name", str(nid)),
                "cite"     : meta.get("citations", [{}])[0].get("cite", ""),
                "year"     : meta.get("decision_date", "")[:4],
                "in_degree": self.in_degree(nid),
                "depth"    : depth,
            })

        edges = []
        for nid in node_ids_in_subgraph:
            for edge in self._nodes[nid].children:
                if edge.target_id in node_ids_in_subgraph:
                    edges.append({"from": nid, "to": edge.target_id, "weight": edge.weight})

        return {"nodes": nodes, "edges": edges}


if __name__ == "__main__":
    tree = NaryTree()

    tree.add_node(1001, {"name": "Griswold v. Connecticut", "decision_date": "1965-06"})
    tree.add_node(1002, {"name": "Eisenstadt v. Baird",     "decision_date": "1972-03"})
    tree.add_node(1003, {"name": "Roe v. Wade",             "decision_date": "1973-01"})
    tree.add_node(1005, {"name": "Planned Parenthood v. Casey", "decision_date": "1992-06"})
    tree.add_node(1007, {"name": "Obergefell v. Hodges",    "decision_date": "2015-06"})

    tree.add_edge(1002, 1001, weight=2)
    tree.add_edge(1003, 1001, weight=3)
    tree.add_edge(1003, 1002, weight=1)
    tree.add_edge(1005, 1003, weight=3)
    tree.add_edge(1005, 1001, weight=2)
    tree.add_edge(1007, 1005, weight=2)
    tree.add_edge(1007, 1001, weight=2)

    print(f"Nodes: {tree.node_count()}, Edges: {tree.edge_count()}")
    print(f"In-degree of Griswold (1001): {tree.in_degree(1001)}")

    print("\nBFS from Griswold (depth=1, outgoing):")
    for nid, depth in tree.bfs(1001, max_depth=1, direction="outgoing"):
        print(f"  depth={depth}  {tree.get_metadata(nid)['name']}")

    print("\nBFS from Griswold (depth=2, incoming):")
    for nid, depth in tree.bfs(1001, max_depth=2, direction="incoming"):
        print(f"  depth={depth}  {tree.get_metadata(nid)['name']}")

    import json
    sg = tree.bfs_subgraph(1003, max_depth=2)
    print(f"\nSubgraph (Roe, depth=2): {len(sg['nodes'])} nodes, {len(sg['edges'])} edges")
