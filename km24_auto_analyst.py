import pandas as pd
import os
import glob
import anthropic  # Kræver: pip install anthropic

# --- KONFIGURATION ---
READ_ROWS = 50000
MAX_SAMPLE = 5
SYSTEM_PROMPT_FILE = "system_prompt.txt"  # Fil med AI-instruktioner
# Indsæt din nøgle her, ELLER sæt den som environment variable (bedre sikkerhed)
API_KEY = os.environ.get("ANTHROPIC_API_KEY") or "INDSÆT_DIN_NØGLE_HER"

def load_system_prompt():
    """Indlæser system-prompten fra fil"""
    # Prøv først relativ til script-location, så relativ til current directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_paths = [
        os.path.join(script_dir, SYSTEM_PROMPT_FILE),  # Ved siden af scriptet
        SYSTEM_PROMPT_FILE  # I current directory
    ]

    for path in prompt_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            continue

    # Hvis ingen fil findes, brug fallback
    print(f"⚠️  ADVARSEL: {SYSTEM_PROMPT_FILE} ikke fundet. Bruger standard prompt.")
    return """Du er Technical Data Auditor og Datajournalist for mediet KM24.
Jeg sender dig en teknisk logfil over et datasæt.

Din opgave er at levere en todelt analyse:

DEL 1: TEKNISK TILSTANDSRAPPORT (Revisoren)
- Vær tør, objektiv og kortfattet.
- Datakvalitets-Score (1-10).
- Compliance Log: Notér brud på standarder (ISO 8601, CSV-format, ID-integritet).
- Rensnings-dom: "Quick Fix" eller "Heavy ETL"?

DEL 2: DATAJOURNALISTISK VURDERING (Redaktøren)
- Vær nysgerrig og idérig.
- Hvad handler data om? (Baseret på kolonnenavne/samples).
- Berigelses-muligheder: Hvilke andre åbne data (DAWA, CVR, DST) bør dette krydses med?
- Ideer til vinkler: 3 konkrete historie-forslag.

Svar i pænt formateret Markdown."""

def analyze_and_ask_claude(filepath, system_prompt):
    client = anthropic.Anthropic(api_key=API_KEY)
    filename = os.path.basename(filepath)

    print(f"\n🚀 Starter fuld analyse af: {filename}...")

    # 1. Kør den lokale audit (genererer rapport-teksten)
    report_content = run_local_audit(filepath)

    if not report_content:
        print("   -> Sprang over (kunne ikke læse filen).")
        return

    # 2. Send til Claude
    print("   -> Sender rapport til Claude (venter på svar)...")
    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",  # Nyeste model (bedre kvalitet)
            max_tokens=4000,  # Øget for mere detaljeret feedback
            temperature=0.5,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Her er logfilen for {filename}:\n\n{report_content}"}
            ]
        )
        
        analysis_text = message.content[0].text
        
        # 3. Gem resultatet
        output_filename = f"ANALYSE_{filename}.md"
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(f"# ANALYSE AF {filename}\n")
            f.write(analysis_text)
            f.write("\n\n---\n")
            f.write("### Bilag: Teknisk Log\n")
            f.write("```text\n")
            f.write(report_content)
            f.write("\n```")
            
        print(f"✅ FÆRDIG! Analyse gemt som: {output_filename}")
        
    except anthropic.AuthenticationError as e:
        print(f"❌ GODKENDELSES FEJL: Ugyldig API-nøgle")
        print("   → Tjek at ANTHROPIC_API_KEY er sat korrekt")
    except anthropic.RateLimitError as e:
        print(f"❌ RATE LIMIT: For mange forespørgsler. Vent et øjeblik og prøv igen.")
    except anthropic.APIConnectionError as e:
        print(f"❌ NETVÆRKS FEJL: Kan ikke forbinde til Anthropic API")
        print(f"   → Tjek din internetforbindelse")
    except anthropic.APIError as e:
        print(f"❌ API FEJL: {e}")
    except Exception as e:
        print(f"❌ UKENDT FEJL: {type(e).__name__}: {e}")

def run_local_audit(filepath):
    """Den samme logik som før, men returnerer tekst-strengen i stedet for at gemme den"""
    filename = os.path.basename(filepath)
    try:
        filesize = os.path.getsize(filepath) / (1024 * 1024)
    except (OSError, FileNotFoundError) as e:
        print(f"   ⚠️ Kunne ikke læse filstørrelse: {e}")
        filesize = 0
        
    df = None
    ext = os.path.splitext(filename)[1].lower()
    encoding_used = "utf-8"
    
    try:
        if ext == '.csv':
            try:
                df = pd.read_csv(filepath, nrows=READ_ROWS, sep=None, engine='python', encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(filepath, nrows=READ_ROWS, sep=None, engine='python', encoding='cp1252')
                encoding_used = "cp1252"
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(filepath, nrows=READ_ROWS)
            encoding_used = "Excel"
        elif ext == '.parquet':
            df = pd.read_parquet(filepath).head(READ_ROWS)
            encoding_used = "Parquet"

        if df is None: return None
        
        # Byg rapporten som en string
        report = []
        report.append(f"KM24 AUDIT LOG: {filename}")
        report.append(f"Format: {encoding_used} | Størrelse: {filesize:.2f} MB")
        report.append("-" * 80)
        report.append(f"{'KOLONNE':<35} | {'TYPE':<10} | {'FLAGS'} | {'INDHOLD (Top 5)'}")
        
        for col in df.columns:
            flags = detect_problematic_types(df[col])
            dtype = str(df[col].dtype).replace("object", "Tekst").replace("int64", "Heltal").replace("float64", "Tal")
            
            top_vals = df[col].value_counts().head(5).index.tolist()
            top_str = str(top_vals).replace("[","").replace("]","")[:40]
            flags_str = ", ".join(flags)
            
            report.append(f"{str(col)[:34]:<35} | {dtype:<10} | {flags_str:<10} | {top_str}")
            
        report.append("-" * 80)
        report.append("DATA SAMPLE (RÅ):")
        try:
            report.append(df.head(MAX_SAMPLE).to_string(index=False))
        except:
            pass
            
        return "\n".join(report)

    except UnicodeDecodeError as e:
        print(f"   ❌ ENCODING FEJL: Kunne ikke afkode filen. {e}")
        return None
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        print(f"   ❌ PARSE FEJL: Filen har fejlagtigt format eller er tom. {e}")
        return None
    except FileNotFoundError:
        print(f"   ❌ FIL IKKE FUNDET: {filepath}")
        return None
    except PermissionError:
        print(f"   ❌ ADGANG NÆGTET: Mangler rettigheder til at læse {filepath}")
        return None
    except Exception as e:
        print(f"   ❌ UKENDT FEJL ved læsning: {type(e).__name__}: {e}")
        return None

def detect_problematic_types(series):
    """Samme detektiv-logik som før"""
    s = series.astype(str).str.strip()
    sample = s.iloc[:200] if len(s) > 200 else s 
    flags = []
    
    if sample.str.match(r'.*\d{1,2}.*[a-zæøå]{3}.*\d{4}.*', case=False).any(): flags.append("DATO_TEXT_DK")
    if sample.str.match(r'^-?\d+,\d+$').any(): flags.append("NUM_COMMA")
    empty_count = series.astype(str).str.fullmatch(r'\s*').sum()
    if empty_count > 0 and empty_count < len(series) and (empty_count/len(series) > 0.01): flags.append("GHOST_NULLS")
    id_match = s.str.match(r'^\d{8}$') | s.str.match(r'^\d{10}$')
    if id_match.mean() > 0.1 and id_match.mean() < 0.99: flags.append("DIRTY_ID")
    if s.str.len().mean() > 60: flags.append("LONG_TEXT")
    
    return flags

# --- HOVEDPROGRAM ---
if __name__ == "__main__":
    # Tjek API nøgle sikkerhed
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if "INDSÆT" in API_KEY or not API_KEY:
            print("❌ FEJL: Ingen API-nøgle fundet!")
            print("   → Sæt ANTHROPIC_API_KEY som environment variable:")
            print("   export ANTHROPIC_API_KEY='din-nøgle-her'")
            print("   ELLER indsæt nøglen i linje 10 (ikke anbefalet til git repos)")
            exit(1)
        else:
            print("⚠️  SIKKERHEDSADVARSEL: API-nøgle er hardcoded i scriptet")
            print("   → Sørg for at scriptet IKKE committes til git!")
            print("   → Bedre: Brug environment variable i stedet")
            print()

    if API_KEY:
        # Ryd op i gamle analyser og rapporter først
        print("🧹 Rydder op i gamle filer...")
        cleanup_patterns = ['ANALYSE_*.md', 'RAPPORT_*.txt']
        deleted_count = 0

        for pattern in cleanup_patterns:
            old_files = glob.glob(pattern)
            for old_file in old_files:
                try:
                    os.remove(old_file)
                    print(f"   ✓ Slettet: {old_file}")
                    deleted_count += 1
                except OSError as e:
                    print(f"   ⚠️  Kunne ikke slette {old_file}: {e}")

        if deleted_count > 0:
            print(f"\n   Fjernede {deleted_count} gamle filer\n")
        else:
            print("   Ingen gamle filer at rydde op\n")

        # Indlæs system prompt fra fil
        system_prompt = load_system_prompt()
        print(f"📝 System prompt indlæst fra: {SYSTEM_PROMPT_FILE}\n")

        files = []
        for ext in ['*.csv', '*.xlsx', '*.xls', '*.parquet']:
            files.extend(glob.glob(ext))

        if not files:
            print("Ingen datafiler fundet.")
        else:
            for f in files:
                if not f.startswith("ANALYSE_") and not f.endswith(".py"):
                    analyze_and_ask_claude(f, system_prompt)