import re
import time
from tqdm import tqdm
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding

# 1. KONFIGURATION
# Liste aller 10 Collections (Wissens- und Entitäts-Collections)
COLLECTIONS_TO_MIGRATE = [
    # Vector / Knowledge Collections
    "master_collection",
    "botanical_knowledge",
    "pharmacological_knowledge",
    "studies_data",
    "production_knowledge",
    
    # Entity / Graph Collections
    "rag_entities",
    "botanical_entities",
    "pharmacological_entities",
    "studies_entities",
    "production_entities"
]

QDRANT_URL = "http://localhost:6333"
BATCH_SIZE = 100

# 2. INITIALISIERUNG
client = QdrantClient(url=QDRANT_URL)
# parallel=4 lässt 4 Kerne für andere Aufgaben frei
model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5", parallel=4)

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
                scalar=models.ScalarQuantizationConfig(type=models.ScalarDataType.INT8, always_ram=True)
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
            res, next_page = client.scroll(
                collection_name=old_name, limit=BATCH_SIZE, with_payload=True, offset=next_page
            )
            if not res: break

            original_texts = [p.payload.get("text", "") for p in res]
            cleaned_texts = [clean_text(t) for t in original_texts]
            
            # Lokales Embedding
            new_vectors = list(model.embed(cleaned_texts))

            points = []
            for i, point in enumerate(res):
                new_payload = point.payload.copy()
                new_payload["text"] = cleaned_texts[i]
                new_payload["migrated_from"] = old_name # Traceability
                
                points.append(models.PointStruct(
                    id=point.id,
                    vector=new_vectors[i].tolist(),
                    payload=new_payload
                ))

            client.upsert(collection_name=new_name, points=points)
            pbar.update(len(res))
            if next_page is None: break

        pbar.close()

if __name__ == "__main__":
    start = time.time()
    run_migration()
    print(f"Migration beendet. Dauer: {(time.time() - start) / 3600:.2f} Stunden.")
