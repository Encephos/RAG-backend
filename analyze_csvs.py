
import pandas as pd
import os
import glob

csv_files = [
    'scrape_data/scrape/cannabis-strains-final.csv',
    'scrape_data/scrape/cannabis.csv',
    'scrape_data/scrape/cepas.csv',
    'scrape_data/scrape/leafly_strain_data.csv',
    'scrape_data/scrape/OCPDB.csv',
    'scrape_data/scrape/results.csv', # This seems to be the one with messy HTML? or scrape.csv?
    'scrape_data/scrape/scrape.csv',
    'scrape_data/scrape/strainmaster.csv',
    'scrape_data/scrape/strains-kushy_api.2017-11-14.csv',
    'data/sources/all_strains_seedfinder.csv'
]

def analyze_csvs():
    strains_per_file = {}
    
    print(f"{'File':<50} | {'Rows':<6} | {'Columns'}")
    print("-" * 120)

    all_other_strains = set()
    seedfinder_strains = set()

    for file_path in csv_files:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
            
        try:
            # Determine separator
            sep = ','
            if 'seedfinder' in file_path:
                sep = ';'
            
            df = pd.read_csv(file_path, on_bad_lines='skip', low_memory=False, sep=sep)
            
            print(f"{os.path.basename(file_path):<50} | {len(df):<6} | {list(df.columns)}")
            
            # Identify name column
            name_col = None
            for col in df.columns:
                if 'name' in col.lower() and 'filename' not in col.lower():
                    name_col = col
                    break
            
            if name_col:
                names = df[name_col].astype(str).str.lower().str.strip().unique()
                if 'seedfinder' in file_path:
                    seedfinder_strains.update(names)
                else:
                    all_other_strains.update(names)
                    
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    with open('analysis_report.txt', 'w') as f:
        f.write("Analysis of Seedfinder vs Others:\n")
        f.write(f"Total Unique Strains in Seedfinder: {len(seedfinder_strains)}\n")
        f.write(f"Total Unique Strains in Others: {len(all_other_strains)}\n")
        
        unique_to_seedfinder = seedfinder_strains - all_other_strains
        f.write(f"Strains UNIQUE to Seedfinder: {len(unique_to_seedfinder)}\n")
        f.write(f"Examples of unique strains: {list(unique_to_seedfinder)[:10]}\n")
    
    print("Analysis complete. Check analysis_report.txt")

if __name__ == "__main__":
    analyze_csvs()
