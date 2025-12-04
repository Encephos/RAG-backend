from typing import Dict, List, Set, Optional

class KnowledgeGraphService:
    def __init__(self):
        # Adjacency list: {node: {neighbor: relation_type}}
        # Using a simple dictionary structure for minimal overhead
        self.graph: Dict[str, Dict[str, str]] = {}

    def add_entity(self, entity: str) -> None:
        """Add a node to the graph if it doesn't exist."""
        if entity not in self.graph:
            self.graph[entity] = {}

    def add_relation(self, source: str, target: str, relation: str) -> None:
        """Add a directed edge between source and target with a relation type."""
        self.add_entity(source)
        self.add_entity(target)
        self.graph[source][target] = relation

    def get_neighbors(self, entity: str) -> Dict[str, str]:
        """Get all outgoing neighbors and their relations."""
        return self.graph.get(entity, {})

    def get_subgraph(self, entities: List[str], depth: int = 1) -> Dict[str, Dict[str, str]]:
        """
        Retrieve a subgraph starting from a list of entities up to a certain depth.
        Returns a dictionary representing the subgraph structure.
        """
        subgraph = {}
        queue = [(e, 0) for e in entities]
        visited = set(entities)

        while queue:
            current_node, current_depth = queue.pop(0)
            
            if current_depth >= depth:
                continue

            if current_node in self.graph:
                subgraph[current_node] = self.graph[current_node]
                
                for neighbor in self.graph[current_node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, current_depth + 1))
        
        return subgraph

    def clear(self) -> None:
        """Clear the entire graph."""
        self.graph = {}
