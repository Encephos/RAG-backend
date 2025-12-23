
import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService

async def main():
    kg = KnowledgeGraphService()
    
    strain_name = "ZZZ..."
    print(f"--- Profiling Lineage Fetch for '{strain_name}' ---")
    
    start_time = time.time()
    try:
        # Fetch lineage with same parameters as API
        lineage = await kg.get_lineage(strain_name, depth=20)
        
        duration = time.time() - start_time
        
        nodes = lineage.get("nodes", [])
        links = lineage.get("links", [])
        
        print(f"Fetch completed in {duration:.4f} seconds.")
        print(f"Nodes: {len(nodes)}")
        print(f"Links: {len(links)}")
        
        # Check for obvious cycles in Links
        # Build adjacency
        adj = {}
        for l in links:
            src = l['source']
            tgt = l['target']
            if src not in adj: adj[src] = []
            adj[src].append(tgt)
            
        # DFS for cycle
        cycle_found = False
        visited = set()
        path = set()
        
        def visit(node_id):
            nonlocal cycle_found
            if node_id in path:
                cycle_found = True
                return
            if node_id in visited:
                return
            
            visited.add(node_id)
            path.add(node_id)
            for neighbor in adj.get(node_id, []):
                visit(neighbor)
            path.remove(node_id)

        for n in nodes:
            if n['id'] not in visited:
                visit(n['id'])
                
        if cycle_found:
            print("!! CYCLE DETECTED in output graph !!")
        else:
            print("No cycles detected in output graph.")

        if duration > 2.0:
            print("!! BACKEND IS SLOW !!")
        elif len(nodes) > 150:
            print("!! GRAPH IS LARGE (Frontend might be choking) !!")
        else:
            print("Backend seems fine. Freeze might be strictly Frontend rendering.")

    except Exception as e:
        print(f"!! Error fetching lineage: {e}")

if __name__ == "__main__":
    asyncio.run(main())
