import logging
import time
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

import os
os.environ['HF_HUB_DISABLE_SYMLINKS_WINDOWS'] = '1'

# Docling Importe
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.datamodel.base_models import InputFormat, DocumentStream

# Logging Konfiguration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeterministicPDFProcessor:

    def __init__(self, artifacts_path: str = None):

        # Aktivieren von 'do_table_structure' mit Modus "ACCURATE" -> stärkere Encoder-Modelle statt Heuristiken
        pipeline_options = PdfPipelineOptions(do_table_structure=True)
        pipeline_options.table_structure_options.mode = TableFormerMode.FAST 
        
        # Optional: OCR aktivieren
        pipeline_options.do_ocr = False 

        # Reduziert die interne Bildauflösung -> Weniger Rechenlast
        # Werte zwischen 1.0 (schnell) und 2.0 (genau)
        pipeline_options.images_scale = 2.0
        
        # Für lokale Modelle
        if artifacts_path:
            pipeline_options.artifacts_path = Path(artifacts_path)

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        logger.info("DeterministicPDFProcessor erfolgreich initialisiert (TableFormer: ACCURATE).")

    def process_file(self, file_path: Path, output_dir: Path) -> Dict[str, Any]:

        if not file_path.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {file_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        start_time = time.time()

        logger.info(f"Starte Konvertierung von: {file_path.name}")
        
        try:
            # 'result' Objekt = DoclingDocument
            conversion_result = self.converter.convert(file_path)
            doc = conversion_result.document
            
            # Export als Markdown
            markdown_content = doc.export_to_markdown()
            md_filename = output_dir / f"{file_path.stem}.md"
            
            with open(md_filename, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            # Tabellenexktraktion
            generated_tables: List[str] = [] 
            if doc.tables:
                logger.info(f"Gefundene Tabellen: {len(doc.tables)}")
                for i, table in enumerate(doc.tables):
                    # KORREKTUR 1: 'doc' als Argument übergeben, um die Warnung zu beheben
                    df = table.export_to_dataframe(doc)
                    
                    # Leere Tabellen verwerfen
                    if df.empty or df.dropna(how='all').empty:
                        continue
                        
                    csv_name = f"{file_path.stem}_table_{i+1}.csv"
                    csv_path = output_dir / csv_name
                    df.to_csv(csv_path, index=False)
                    generated_tables.append(str(csv_path))
            
            duration = time.time() - start_time
            logger.info(f"Verarbeitung abgeschlossen in {duration:.2f}s.")
            
            return {
                "status": "success",
                "markdown_file": str(md_filename),
                "tables": generated_tables,
                "document_name": doc.name if hasattr(doc, 'name') else str(file_path.name),
                "duration": duration
            }

        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung von {file_path}: {e}")
            raise e


#Anwendungsbeipiel: 
if __name__ == "__main__":
    processor = DeterministicPDFProcessor()
    aktuelles_verzeichnis = Path(__file__).resolve().parent # aktuelles Verzeichnis abrufen
    pdf_pfad = aktuelles_verzeichnis.parent / 'downloads' / 'Bedienungsanleitung_SSV_komplett.pdf' # src Verzeichnis abrufen + /download/test.pdf 

    result = processor.process_file(pdf_pfad, Path("./output"))
    print(result)
