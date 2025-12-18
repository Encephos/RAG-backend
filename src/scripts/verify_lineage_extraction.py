
from bs4 import BeautifulSoup
import re

# Same HTML sample (real snippet)
html_real = """
<li class="strain-entry">
    <a href="...">Z and Z Auto</a>
    <ul>
        <li>»»» <a href="...">Z3</a> x <a href="...">Monster Mash</a></li>
        <li>
            <a href="...">Z3</a>
            <ul>
                 <li>»»» <a href="...">The Original Z</a> x <a href="...">Hindu Kush</a></li>
                 <li>
                     <a href="...">The Original Z</a>
                     <ul>
                         <li>»»» (Grape Ape x Grapefruit) x <a href="...">Unknown Strain</a></li>
                         <li>
                             (Grape Ape x Grapefruit)
                             <ul>
                                 <li>»»» <a href="...">Grape Ape</a> x <a href="...">Grapefruit</a></li>
                             </ul>
                         </li>
                     </ul>
                 </li>
            </ul>
        </li>
        <li>
            <a href="...">Monster Mash</a>
            <ul>
               <li>»»» ...</li>
            </ul>
        </li>
    </ul>
</li>
"""

def extract_full_tree(html_content, root_strain_name):
    soup = BeautifulSoup(html_content, "html.parser")
    tree_map = {}
    
    # Fallback if root name not provided or mismatch, but let's use it as key
    
    # 1. Find the root LI. Often the HTML snippet IS the LI. 
    # Or contains one main LI.
    root_li = soup.find('li')
    
    def parse_li_hierarchy(li, child_name):
        # Find ULs. Be careful of nested structures.
        # Structure in snippet: LI -> UL -> UL -> LI (with arrow) ...
        # Or LI -> UL -> LI (simple)
        
        # Search for the "»»»" marker which indicates the PARENTS line
        # This marker is inside the LI corresponding to the PARENT LIST item?
        # Actually in the snippet:
        # <li class="bg..."> »»» <a parent 1> x <a parent 2> </li>
        # This LI is inside a UL, which is inside the Child LI.
        
        # Let's find all "»»»" text nodes inside `li`.
        # But only the DIRECT ones (immediate children logic)
        
        # Filter Logic:
        # Iterate all "»»»" nodes properly.
        pass
        
    # BETTER APPROACH:
    # 1. Flatten the tree by finding ALL `li` elements that contain `»»»`.
    # 2. For each such `li`, identify the PARENTS listed in it.
    # 3. Identify the CHILD? The child is the Strain Name associated with the enclosing LI/UL.
    
    # This "Child Identification" is the hard part in a flat search.
    # So we MUST traverse recursively.
    
    def recursive_parse(element, current_child):
        # Look for the UL that contains the lineage info for `current_child`
        uls = element.find_all('ul', recursive=False)
        print(f"DEBUG: In recursion for {current_child}, found {len(uls)} direct ULs")
        for ul in uls:
            # 1. Formula Search (Robust to wrappers)
            # Find the arrow in this UL's scope (but not deep in *other* definition nodes)
            # This is tricky. simpler: Iterate direct children. If child is UL, check it.
            
            # Robust Approach:
            # Iterate direct children of the MAIN UL.
            for child in ul.children:
                if child.name == 'ul':
                     # This might be the wrapper for the formula line
                     # check for formula inside
                     for inner_li in child.find_all('li'):
                         if "»»»" in inner_li.get_text():
                             # FOUND FORMULA
                             links = inner_li.find_all('a')
                             parents = [a.get_text(strip=True) for a in links]
                             if parents:
                                 tree_map[current_child] = list(set(tree_map.get(current_child, []) + parents))
                             break # Assume one formula per block
                
                elif child.name == 'li':
                    li = child
                    text = li.get_text()
                    
                    # Direct LI Formula?
                    if "»»»" in text and not li.find('ul'):
                         links = li.find_all('a')
                         parents = [a.get_text(strip=True) for a in links]
                         if parents:
                             tree_map[current_child] = list(set(tree_map.get(current_child, []) + parents))
                    
                    # Definition Node (Ancestors)
                    if li.find('ul'):
                        child_name = None
                        # Robust name extraction: split before UL
                        pre_ul_html = str(li).split('<ul')[0]
                        pre_soup = BeautifulSoup(pre_ul_html, "html.parser")
                        child_a = pre_soup.find('a')

                        if child_a:
                            child_name = child_a.get_text(strip=True)
                        else:
                            # Text-only node?
                            raw_text = pre_soup.get_text(strip=True)
                            if raw_text and len(raw_text) > 1:
                                child_name = raw_text.strip()
                    
                        if child_name and child_name != current_child:
                            # It is a parent/ancestor!
                            # Add it to the relations for current_child
                            tree_map[current_child] = list(set(tree_map.get(current_child, []) + [child_name]))
                            
                            recursive_parse(li, child_name)
                             
                             # Also, if we missed the Formula line earlier (because it was weird), 
                             # the existence of this sibling definition usually implies it IS a parent.
                             # But let's trust the formula line for existing relations.
                             
    # Start
    if root_li:
        print(f"DEBUG: Found root_li, recursing for {root_strain_name}")
        recursive_parse(root_li, root_strain_name)
    else:
        print("DEBUG: Root LI NOT found!")
        # Try finding the ULs directly if root_li failed
        pass
    return tree_map

print("--- Recursive Extraction Test ---")
tree = extract_full_tree(html_real, "Z and Z Auto")
for child, parents in tree.items():
    print(f"{child} bred from {parents}")
