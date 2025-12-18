
from bs4 import BeautifulSoup
import csv

# Mocking the functions from ingest_scraped.py

def parse_node(element, current_name, tree_relations):
     if not current_name: return
     
     # Find the UL containing children/lineage info
     # Usually a direct child of the LI
     ul = element.find('ul', recursive=False)
     if not ul: return 
     
     # 1. Iterate direct children to find Formula (wrapped in UL?) vs Definitions (LI)
     # Validated logic from verify_lineage_extraction.py
     
     for child in ul.children:
         if child.name == 'ul':
              # Potential Formula Wrapper
              for inner_li in child.find_all('li'):
                  if "»»»" in inner_li.get_text():
                      # Found Formula
                      links = inner_li.find_all('a')
                      p_list = []
                      for link in links:
                          # Filter noise
                          p_name = link.get_text(strip=True)
                          if p_name and p_name != "Unknown Ruderalis":
                               p_list.append(p_name)
                      
                      if p_list:
                          tree_relations[current_name] = list(set(tree_relations.get(current_name, []) + p_list))
                      break # Found formula in this wrapper
         
         elif child.name == 'li':
             li = child
             text = li.get_text()
             
             # Direct LI Formula?
             if "»»»" in text and not li.find('ul'):
                  links = li.find_all('a')
                  p_list = []
                  for link in links:
                      p_name = link.get_text(strip=True)
                      if p_name and p_name != "Unknown Ruderalis":
                           p_list.append(p_name)
                  
                  if p_list:
                       tree_relations[current_name] = list(set(tree_relations.get(current_name, []) + p_list))
             
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

                 if child_name and child_name != current_name:
                     # It is a parent/ancestor!
                     # Add it to the relations for current_name
                     tree_relations[current_name] = list(set(tree_relations.get(current_name, []) + [child_name]))
                     
                     parse_node(li, child_name, tree_relations)

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

soup = BeautifulSoup(html_real, "html.parser")
root_li = soup.find('li')
tree_relations = {}
main_name = "Z and Z Auto"

if root_li:
    parse_node(root_li, main_name, tree_relations)

print("Generated Relations:", tree_relations)

# Simulate Upsert Prep
lineage_str = ", ".join(tree_relations.get(main_name, []))
print("Main Lineage CSV String:", lineage_str)
