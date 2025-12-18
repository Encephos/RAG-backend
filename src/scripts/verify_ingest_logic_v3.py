
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simulated parent_html from CSV (fragment starting with <a>)
# Simplified structure representing "Z and Z Auto" log
parent_html_fragment = """
<a class="font-bold text-black text-base" href="...">Z and Z Auto</a>
<ul class="strain-list">
   <ul>
      <li>»»» <a href="...">Z3</a> x <a href="...">Monster Mash</a></li>
   </ul>
   <li>
      <span class="...">Parent 1 Node</span>
   </li>
</ul>
"""

# Current Logic
logger.info("--- TEST 1: Current Logic (soup.find('li')) ---")
soup = BeautifulSoup(parent_html_fragment, "html.parser")
root_li = soup.find('li')

if root_li:
    logger.info(f"Checking found LI text: {root_li.get_text(strip=True)[:50]}...")
    # Does this LI contain the main formula?
    # In the fragment above, the first LI is the formula inner LI: "»»» Z3 x Monster Mash"
    # If parse_node is called on THIS, does it find the parents?
    # parse_node expects the LI to CONTAIN the UL.
    # The inner LI (formula) usually DOES NOT contain a UL.
    if root_li.find('ul'):
        logger.info("The found LI has a UL.")
    else:
        logger.info("The found LI does NOT have a UL (It's likely a leaf/formula node).")
else:
    logger.info("No LI found.")

# Proposed Fix
logger.info("\n--- TEST 2: Proposed Fix (Wrap in <li>) ---")
wrapped_html = f"<li>{parent_html_fragment}</li>"
soup_wrapped = BeautifulSoup(wrapped_html, "html.parser")
root_li_wrapped = soup_wrapped.find('li')

if root_li_wrapped:
    logger.info(f"Checking found LI text: {root_li_wrapped.get_text(strip=True)[:50]}...")
    # This should be the wrapper
    ul = root_li_wrapped.find('ul')
    if ul:
         logger.info("The found LI has a UL. Correct structure.")
    else:
         logger.info("No UL found.")
else:
    logger.info("No LI found.")
