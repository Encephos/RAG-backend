from typing import Dict, List, Any, Optional

class KnowledgeGraphService:
    def __init__(self):
        # Enhanced structure: {subject: {object: {"relation": str, "confidence": float}}}
        self.graph: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def add_entity(self, entity: str) -> None:
        """Add a node to the graph if it doesn't exist."""
        if entity not in self.graph:
            self.graph[entity] = {}

    def add_relation(self, source: str, target: str, relation: str, confidence: float = 1.0) -> None:
        """Add a directed edge between source and target with a relation type and confidence."""
        self.add_entity(source)
        self.add_entity(target)
        self.graph[source][target] = {
            "relation": relation,
            "confidence": confidence
        }

    def add_triple(self, subject: str, predicate: str, obj: str, confidence: float = 1.0) -> None:
        """Add a semantic triple to the graph."""
        self.add_relation(subject, obj, predicate, confidence)

    def get_neighbors(self, entity: str) -> Dict[str, Dict[str, Any]]:
        """Get all outgoing neighbors with their relations and confidence."""
        return self.graph.get(entity, {})

    def get_subgraph(self, entities: List[str], depth: int = 1) -> Dict[str, Dict[str, Dict[str, Any]]]:
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

    def get_graph_context_string(self, entities: List[str], depth: int = 1) -> str:
        """Get a human-readable string representation of the subgraph."""
        subgraph = self.get_subgraph(entities, depth)
        if not subgraph:
            return ""
        
        lines = []
        for subject, relations in subgraph.items():
            for obj, data in relations.items():
                relation = data["relation"]
                confidence = data["confidence"]
                lines.append(f"- {subject} --[{relation}]--> {obj} (confidence: {confidence:.2f})")
        
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear the entire graph."""
        self.graph = {}
