
from bs4 import BeautifulSoup, Tag
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock Parser Logic from ingest_scraped.py
def parse_node(element: Tag, current_name: str, tree_relations):
     if not current_name: return
     
     # Find the UL containing children/lineage info
     # Usually a direct child of the LI
     ul = element.find('ul', recursive=False)
     if not ul: 
         # DEBUG: why no UL?
         # Check if maybe the UL is inside a DIV or something?
         # Or maybe the structure is flattened?
         logger.info(f"DEBUG: No direct UL found for {current_name}. Element contents: {element.prettify()[:200]}")
         return 

     logger.info(f"DEBUG: Found UL for {current_name}. Processing children...")

     for child in ul.children:
         if child.name == 'ul':
              # Potential Formula Wrapper
              for inner_li in child.find_all('li'):
                  if "»»»" in inner_li.get_text():
                      # Found Formula
                      links = inner_li.find_all('a')
                      p_list = []
                      for link in links:
                          p_name = link.get_text(strip=True)
                          # Strip potential trailing/leading whitespace and noise
                          p_name = p_name.strip()
                          if p_name and "Ruderalis" not in p_name: # Simple filter
                               p_list.append(p_name)
                      
                      if p_list:
                          logger.info(f"DEBUG: Found Formula Relations: {p_list}")
                          tree_relations[current_name] = list(set(tree_relations.get(current_name, []) + p_list))
                      break 
         
         elif child.name == 'li':
             li = child
             text = li.get_text()
             
             # Direct LI Formula?
             if "»»»" in text and not li.find('ul'):
                  links = li.find_all('a')
                  p_list = []
                  for link in links:
                      p_name = link.get_text(strip=True)
                      if p_name:
                           p_list.append(p_name)
                  
                  if p_list:
                       tree_relations[current_name] = list(set(tree_relations.get(current_name, []) + p_list))
             
             # Definition Node (Ancestors)
             if li.find('ul'):
                 child_name = None
                 # Robust name extraction: split before UL unlikely to work if classes present?
                 # Let's see how the real HTML looks.
                 # User snippet: <a class="font-bold..." ...> Z and Z Auto </a>
                 
                 # Logic in script:
                 # pre_ul_html = str(li).split('<ul')[0] -> This is fragile if attributes span lines
                 
                 # Better logic: find first 'a' that is NOT inside the nested 'ul'
                 # But 'find' is depth-first.
                 
                 # Alternative: iterate children of LI. First 'a' is likely the name.
                 child_a = li.find('a', recursive=False) # Only direct child? A typically is direct child of LI
                 if not child_a:
                     # Maybe text node?
                     # Let's look for any 'a' before the 'ul'
                     # 'ul' is usually the last child.
                     pass 
                 
                 # OLD FRAGILE LOGIC:
                 pre_ul_html = str(li).split('<ul')[0]
                 pre_soup = BeautifulSoup(pre_ul_html, "html.parser")
                 child_a = pre_soup.find('a')

                 if child_a:
                     child_name = child_a.get_text(strip=True)
                 
                 if child_name and child_name != current_name:
                     logger.info(f"DEBUG: Found Ancestor Node: {child_name}")
                     tree_relations[current_name] = list(set(tree_relations.get(current_name, []) + [child_name]))
                     parse_node(li, child_name, tree_relations)

# REAL HTML SNIPPET FROM USER LOG (Reconstructed Structure)
# The snippet starts with <a class...> Z and Z Auto </a> inside what implies is an LI
html_real = """
<li class="strain-entry">
<a class="font-bold text-black text-base" href="https://seedfinder.eu/en/strain-info/zampz-auto/exotic-seed">                     Z and Z Auto                                             &nbsp;(F4)   </a>
<br>
<ul class="strain-list">
     <li>
         <span class="formula-marker">»»»</span> 
         <a href="...">Z3</a> x <a href="...">Monster Mash</a>
     </li>
     <!-- Recursive children would be here -->
</ul>
</li>
"""

soup = BeautifulSoup(html_real, "html.parser")
root_li = soup.find('li')
tree_relations = {}
parse_node(root_li, "Z and Z Auto", tree_relations)

print("Relations:", tree_relations)
