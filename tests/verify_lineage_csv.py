
import pandas as pd
import os
import sys
import re

# Simple normalization consistent with ingestion
def normalize(name):
    if not name or pd.isna(name): return None
    return str(name).strip().lower()

def load_and_verify(target_strain="zzz..."):
    print(f"Verifying lineage for: {target_strain}")
    
    strains = {}
    
    # 1. Load Seedfinder (Primary source for these types of lineages)
    csv_path = "data/sources/all_strains_seedfinder.csv"
    if os.path.exists(csv_path):
        print(f"Loading {csv_path}...")
        df = pd.read_csv(csv_path, sep=";", on_bad_lines='skip', low_memory=False)
        for _, row in df.iterrows():
            name = normalize(row.get('Name der Strain'))
            if not name: continue
            
            p1 = normalize(row.get('Eltern 1'))
            p2 = normalize(row.get('Eltern 2'))
            parents = []
            if p1: parents.append(p1)
            if p2: parents.append(p2)
            
            strains[name] = {"parents": parents, "source": "seedfinder"}

    # 2. Check Scrape (Secondary)
    csv_path = "scrape_data/scrape/scrape.csv"
    if os.path.exists(csv_path):
        print(f"Loading {csv_path}...")
        # Scrape.csv might use different sep? Ingestion used ';'.
        try:
            df = pd.read_csv(csv_path, sep=";", on_bad_lines='skip', low_memory=False)
            for _, row in df.iterrows():
                name = normalize(row.get('Name') or row.get('strain_name'))
                if not name: continue
                
                # Check for HTML Tree (scrape.csv specific)
                parent_html = row.get('parent_tree')
                parents = []
                
                if parent_html and isinstance(parent_html, str) and "<li" in parent_html:
                    # Quick dirty regex parse for verification (avoid full BS4 complexity if possible, or use full)
                    # For verification script, let's use the same parsing logic if we can import it, 
                    # OR just regex to find <a> tags which usually contain parents in simple lists
                    # But Seedfinder trees are nested.
                    # Let's just create a simplified parser for links inside the HTML
                    # "herz og auto" etc are inside <a> tags.
                    links = re.findall(r'<a.*?>(.*?)</a>', parent_html)
                    # Filter out "Upload your info" or similar if any
                    parents = [normalize(l) for l in links if "Upload" not in l and "info" not in l]
                    # Note: This regex flattens the tree, but good for checking *existence* of parents
                    # To reconstruct structure we need BS4.
                
                if not parents:
                     p_str = str(row.get('parents', ''))
                     if p_str and p_str != 'nan':
                         parents = [normalize(p) for p in p_str.split(',')]
                
                strains[name] = {"parents": parents, "source": "scrape", "html": parent_html}
        except Exception as e:
            print(f"Error loading scrape.csv: {e}")

    # 3. Recursive Print
    target = normalize(target_strain)
    if target not in strains:
        print(f"Target '{target}' not found in loaded CSVs.")
        # Try fuzzy ?
        for s in strains:
            if target in s:
                print(f"Did you mean: {s}?")
        return

    print(f"\n--- Lineage Tree for '{target}' (Source: {strains[target]['source']}) ---")
    
    if strains[target].get("html"):
        print("HTML Structure Snippet:")
        print(strains[target]["html"][:1000] + "...") # Print first 1000 chars
    
    def print_tree(strain, depth=0, visited=None):
        if visited is None: visited = set()
        
        prefix = "  " * depth
        if depth > 0: prefix += "-> "
        
        info = strains.get(strain, {"parents": []})
        parents = info.get("parents", [])
        
        # Check for simple cycles in visualization
        is_cycle = strain in visited
        suffix = " (Cycle)" if is_cycle else ""
        if not info.get("source"): suffix += " (Unknown/Missing in CSV)"
        
        print(f"{prefix}{strain}{suffix}")
        
        if is_cycle or depth > 6: return # Limit depth for viewing
        
        visited.add(strain)
        for p in parents:
            print_tree(p, depth + 1, visited.copy())

    print_tree(target)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "zzz..."
    load_and_verify(target)
