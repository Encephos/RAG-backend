import re
import time
from tqdm import tqdm
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding

# 1. KONFIGURATION
# Liste aller 10 Collections (Wissens- und Entitäts-Collections)
COLLECTIONS_TO_MIGRATE = [
    # Vector / Knowledge Collections
    # "master_collection",
    # "botanical_knowledge",
    # "pharmacological_knowledge",
    # "studies_data",
    # "production_knowledge",
    
    # Entity / Graph Collections
    # "rag_entities",
    "botanical_entities", # <-- NUR DAS HIER IST WICHTIG FÜR GENEALOGY / STRAINS
    # "pharmacological_entities",
    # "studies_entities",
    # "production_entities"
]

# Use 'qdrant' hostname within Docker network, fallback to localhost for local dev
import os
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
import gc
QDRANT_URL = f"http://{QDRANT_HOST}:6333"
BATCH_SIZE = 50 # Drastically reduced to prevent OOM

# 2. INITIALISIERUNG
client = QdrantClient(url=QDRANT_URL)
# parallel=None nutzt alle verfügbaren Kerne (Standard)
model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")

# DYNAMISCHES REGEX-MUSTER
# Erklärt: Findet den Block von "Here you can find..." bis "...even more information."
# Dabei sind Strain und Source flexibel (.*?)
DYNAMIC_CLEAN_PATTERN = re.compile(
    r"Here\s+you\s+can\s+find\s+all\s+info\s+about\s+.*?\s+from\s+.*?\.?\s*"
    r"If\s+you\s+are\s+searching\s+for\s+information\s+about\s+.*?\s+from\s+.*?\s*check\s+out\s+our:\s*"
    r"Basic\s+infos,.*?Gallery,.*?Degustation,.*?Awards,.*?Strain\s+Reviews,.*?"
    r"Direct\s+Comparisons,.*?Lineage\s+/\s+Genealogy,.*?Hybrids\s+/\s+Crossbreeds,.*?"
    r"User\s+comments,.*?for\s+this\s+cannabis\s+variety\s+here\s+at\s+this\s+page\s+"
    r"and\s+follow\s+the\s+links\s+to\s+get\s+even\s+more\s+information\.",
    re.IGNORECASE | re.DOTALL
)

def clean_text(text):
    """Entfernt dynamische Werbeblöcke und normalisiert den Text."""
    if not text: return ""
    # Entfernt den dynamischen Block
    cleaned = DYNAMIC_CLEAN_PATTERN.sub("", text)
    # Entfernt überschüssige Whitespaces
    return " ".join(cleaned.split()).strip()

def ensure_new_collection(new_name):
    """Erstellt die Ziel-Collection, falls sie nicht existiert."""
    if not client.collection_exists(new_name):
        client.create_collection(
            collection_name=new_name,
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE, on_disk=True),
            quantization_config=models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(type=models.ScalarType.INT8, always_ram=True)
            )
        )

def run_migration():
    for old_name in COLLECTIONS_TO_MIGRATE:
        new_name = f"{old_name}_768"
        print(f"\n--- Migriere: {old_name} -> {new_name} ---")
        
        try:
            total_count = client.count(old_name).count
        except Exception as e:
            print(f"⚠️ Collection '{old_name}' nicht gefunden oder Fehler: {e}")
            continue

        if total_count == 0:
            print(f"⏩ Überspringe '{old_name}' (leer).")
            continue

        # Ziel-Collection sicherstellen
        ensure_new_collection(new_name)

        next_page = None
        pbar = tqdm(total=total_count, desc=f"Processing {old_name}")

        while True:
            t0 = time.time()
            res, next_page = client.scroll(
                collection_name=old_name, limit=BATCH_SIZE, with_payload=True, offset=next_page
            )
            t_scroll = time.time()
            if not res: break

            # Prepare texts for embedding
            texts_to_embed = []
            for p in res:
                # 1. Try existing 'text' field
                raw_text = p.payload.get("text", "")
                cleaned = clean_text(raw_text)
                
                # 2. If empty (common for Entities), construct from Name + Description
                if not cleaned:
                    name = p.payload.get("name", "")
                    desc = p.payload.get("description", "")
                    # Also try other useful fields for context
                    type_str = p.payload.get("type", "")
                    cleaned = f"{name} ({type_str}): {desc}".strip()
                    
                    # If still empty (edge case), use Name
                    if not cleaned and name:
                        cleaned = name

                if not cleaned:
                     # Fallback to avoid empty embedding error
                     cleaned = "Unknown Entity"
                     
                texts_to_embed.append(cleaned)
            
            t_prep = time.time()
            
            # Lokales Embedding
            new_vectors = list(model.embed(texts_to_embed))
            t_embed = time.time()

            points = []
            for i, point in enumerate(res):
                new_payload = point.payload.copy()
                new_payload["text"] = texts_to_embed[i] # Store the text we used for embedding
                new_payload["migrated_from"] = old_name # Traceability
                
                points.append(models.PointStruct(
                    id=point.id,
                    vector=new_vectors[i].tolist(),
                    payload=new_payload
                ))
            
            t_struct = time.time()

            client.upsert(collection_name=new_name, points=points)
            t_upsert = time.time()
            
            pbar.update(len(res))
            
            # Print Timing Stats for first few batches to diagnose
            if pbar.n < (BATCH_SIZE * 20) or (pbar.n % 1000 == 0):
                print(f"\n[Timing] Batch {len(res)} items | "
                      f"Scroll: {t_scroll-t0:.2f}s | "
                      f"Clean/Prep: {t_prep-t_scroll:.2f}s | "
                      f"Embed: {t_embed-t_prep:.2f}s | "
                      f"Upsert: {t_upsert-t_struct:.2f}s", flush=True)
            
            # Force Garbage Collection to prevent OOM
            del new_vectors
            del texts_to_embed
            del points
            del res
            gc.collect()

            if next_page is None: break

        pbar.close()

if __name__ == "__main__":
    start = time.time()
    try:
        run_migration()
        print(f"Migration beendet. Dauer: {(time.time() - start) / 3600:.2f} Stunden.")
    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer.")
    except Exception as e:
        print(f"\nFATAL ERROR UNCAUGHT: {e}")
