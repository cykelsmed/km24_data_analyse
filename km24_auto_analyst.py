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

        # Auto-konverter float-kolonner der faktisk indeholder heltal (fx postnumre som 8700.0)
        for col in df.columns:
            if df[col].dtype == 'float64':
                # Tjek om alle ikke-NaN værdier er hele tal
                non_null = df[col].dropna()
                if len(non_null) > 0 and non_null.apply(lambda x: x == int(x)).all():
                    # Konverter til nullable integer (Int64 understøtter NaN)
                    df[col] = df[col].astype('Int64')

        # Byg rapporten som en string
        report = []
        report.append(f"KM24 AUDIT LOG: {filename}")
        report.append(f"Format: {encoding_used} | Størrelse: {filesize:.2f} MB")

        # Tjek for trunkerede kolonnenavne, metadata-problemer, ID-inkonsistenser og CSV parsing-fejl
        truncation_warnings = detect_truncated_columns(df)
        metadata_warnings = detect_metadata_issues(df)
        id_warnings = detect_id_inconsistencies(df)
        csv_warnings = detect_csv_parsing_issues(df, filepath)
        all_warnings = truncation_warnings + metadata_warnings + id_warnings + csv_warnings

        if all_warnings:
            report.append("\n🚨 KOLONNE-ADVARSLER:")
            for warning in all_warnings:
                report.append(f"   {warning}")
            report.append("")

        report.append("-" * 80)
        report.append(f"{'KOLONNE':<35} | {'TYPE':<10} | {'FLAGS'} | {'INDHOLD (Top 5)'}")
        
        for col in df.columns:
            flags = detect_problematic_types(df[col])
            dtype = str(df[col].dtype).replace("object", "Tekst").replace("int64", "Heltal").replace("Int64", "Heltal").replace("float64", "Tal")
            
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

    # Mere præcis dansk dato-pattern (undgår false positives på hex IDs)
    # Matcher: "24maj2025", "24 maj 2025", "24-maj-2025", "24.maj.2025"
    danish_months = r'(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)'
    if sample.str.match(rf'\d{{1,2}}[\s\-\.]*{danish_months}[a-zæøå]*[\s\-\.]*\d{{4}}', case=False).any():
        flags.append("DATO_TEXT_DK")
    if sample.str.match(r'^-?\d+,\d+$').any(): flags.append("NUM_COMMA")
    empty_count = series.astype(str).str.fullmatch(r'\s*').sum()
    if empty_count > 0 and empty_count < len(series) and (empty_count/len(series) > 0.01): flags.append("GHOST_NULLS")
    id_match = s.str.match(r'^\d{8}$') | s.str.match(r'^\d{10}$')
    if id_match.mean() > 0.1 and id_match.mean() < 0.99: flags.append("DIRTY_ID")
    if s.str.len().mean() > 60: flags.append("LONG_TEXT")

    # Danish postal code validation
    col_name = series.name.lower() if hasattr(series, 'name') else ''
    if 'postnummer' in col_name or 'postal' in col_name or 'postcode' in col_name:
        # Convert to numeric, ignoring NaN
        numeric_vals = pd.to_numeric(series.dropna(), errors='coerce').dropna()
        if len(numeric_vals) > 0:
            # Danish postal codes are 1000-9990 (with some gaps, but this catches obvious errors)
            invalid = ((numeric_vals < 1000) | (numeric_vals > 9990)).sum()
            if invalid > 0:
                invalid_pct = (invalid / len(numeric_vals)) * 100
                flags.append(f"INVALID_POSTAL ({invalid}/{len(numeric_vals)} = {invalid_pct:.1f}%)")

    return flags

def detect_truncated_columns(df):
    """Detektér trunkerede kolonnenavne (ofte fra Excel/CSV eksport)"""
    warnings = []

    # BOM detection - check first column
    if len(df.columns) > 0:
        first_col = str(df.columns[0])
        if first_col.startswith('\ufeff'):
            clean_name = first_col.replace('\ufeff', '')
            warnings.append(f"⚠️ BOM-MARKØR: Første kolonne '{clean_name}' starter med UTF-8 BOM (byte order mark)")

    # Track overly long column names (from rapport.txt: makes code hard to read)
    very_long_cols = []

    # Truncation detection
    for col in df.columns:
        col_str = str(col).replace('\ufeff', '')  # Strip BOM for display

        # Flag very long column names (>50 chars)
        if len(col_str) > 50:
            very_long_cols.append(col_str[:40] + "...")

        # Trunkerede kolonner slutter ofte med incomplete ord eller er mistænkeligt lange
        if col_str.endswith('...'):
            warnings.append(f"⚠️ TRUNKERET: '{col_str}' (ender med '...')")
        elif len(col_str) >= 34 and len(col_str) <= 50:  # Don't double-flag very long ones
            # Pandas truncerer kolonnenavne til 34 tegn i visse situationer
            # Tjek om det ligner et afskåret ord (fx "dispone" i stedet for "disponering")
            last_word = col_str.split()[-1] if ' ' in col_str else col_str.split('_')[-1]
            if len(last_word) >= 4 and len(last_word) <= 10:
                # Sandsynligvis trunkeret ord (for kort til at være komplet, for langt til at være akronym)
                warnings.append(f"⚠️ MULIG TRUNKING: '{col_str}' (kolonne virker afskåret)")

    # Report overly long columns
    if very_long_cols:
        warnings.append(f"⚠️ MEGET LANGE KOLONNENAVNE: {len(very_long_cols)} kolonner >50 tegn (gør kode svær at læse)")

    return warnings

def detect_metadata_issues(df):
    """Detektér manglende metadata-kolonner (dårlig data governance)"""
    warnings = []

    # Check for common metadata columns
    col_names_lower = [str(col).lower() for col in df.columns]

    metadata_indicators = {
        'temporal': ['created', 'updated', 'modified', 'timestamp', 'dato', 'tidspunkt'],
        'source': ['source', 'kilde', 'origin'],
        'version': ['version', 'revision', 'v_'],
        'id': ['id', 'key', 'nøgle']
    }

    missing_types = []

    # Check for temporal metadata
    has_temporal = any(ind in col for col in col_names_lower for ind in metadata_indicators['temporal'])
    if not has_temporal and len(df) > 100:  # Only warn for larger datasets
        missing_types.append("tidsstempler (created_at/updated_at)")

    # Check for source/provenance
    has_source = any(ind in col for col in col_names_lower for ind in metadata_indicators['source'])
    if not has_source and len(df) > 100:
        missing_types.append("kilde-sporing (source/kilde)")

    # Check for unique ID
    has_id = any(ind in col for col in col_names_lower for ind in metadata_indicators['id'])
    if not has_id:
        missing_types.append("entydigt ID (id/key)")

    if missing_types:
        warnings.append(f"⚠️ MANGLENDE METADATA: {', '.join(missing_types)} - indikerer dårlig data governance")

    return warnings

def detect_id_inconsistencies(df):
    """Detektér kolonner med blandede ID-formater (CVR, P-nummer, etc.)"""
    warnings = []

    for col in df.columns:
        col_name = str(col).lower()

        # Kun tjek kolonner der ligner ID-kolonner
        if any(keyword in col_name for keyword in ['cvr', 'p-nummer', 'pnr', 'p_nr', 'virksomhed', 'enhed', 'company', 'id']):
            # Konverter til streng og fjern NaN
            s = df[col].dropna().astype(str).str.strip()

            if len(s) == 0:
                continue

            # Detektér forskellige ID-typer
            cvr_pattern = s.str.match(r'^\d{8}$')  # CVR: nøjagtigt 8 cifre
            p_nummer_pattern = s.str.match(r'^\d{10}$')  # P-nummer: nøjagtigt 10 cifre

            cvr_count = cvr_pattern.sum()
            p_nummer_count = p_nummer_pattern.sum()
            total_count = len(s)

            # Hvis kolonnen indeholder både CVR og P-numre, er det inkonsistent
            if cvr_count > 0 and p_nummer_count > 0:
                cvr_pct = (cvr_count / total_count) * 100
                p_pct = (p_nummer_count / total_count) * 100
                warnings.append(
                    f"⚠️ BLANDET ID-FORMAT i '{col}': {cvr_count} CVR-numre ({cvr_pct:.1f}%) + "
                    f"{p_nummer_count} P-numre ({p_pct:.1f}%) - inkonsistent identifikation"
                )

            # Tjek også for varierende længder generelt (indikerer dårlig data-hygiejne)
            elif 'cvr' in col_name or 'p-nummer' in col_name or 'pnr' in col_name:
                lengths = s.str.len()
                unique_lengths = lengths.unique()

                if len(unique_lengths) > 2:  # Mere end 2 forskellige længder er mistænkeligt
                    length_counts = lengths.value_counts().head(3)
                    length_summary = ", ".join([f"{length}cifre: {count}stk" for length, count in length_counts.items()])
                    warnings.append(
                        f"⚠️ VARIERENDE ID-LÆNGDER i '{col}': {len(unique_lengths)} forskellige længder ({length_summary})"
                    )

    return warnings

def detect_csv_parsing_issues(df, filepath):
    """Detektér CSV parsing-problemer (forkerte separatorer, ukorrekt antal kolonner)"""
    warnings = []

    # Tjek for "Unnamed" kolonner - indikerer at pandas har tilføjet ekstra kolonner
    unnamed_cols = [col for col in df.columns if str(col).startswith('Unnamed:')]
    if unnamed_cols:
        warnings.append(
            f"⚠️ CSV PARSING FEJL: {len(unnamed_cols)} 'Unnamed' kolonner fundet - "
            f"CSV'en har sandsynligvis forkert antal felter per række (tjek kommaer i data)"
        )

    # For CSV filer: Tjek om første 10 rækker har konsistent antal separatorer
    if filepath.endswith('.csv'):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = [f.readline() for _ in range(11)]  # Header + 10 data-rækker

            if len(lines) > 1:
                # Detektér separator (antag komma eller semikolon)
                header = lines[0]
                sep = ',' if ',' in header else ';' if ';' in header else None

                if sep:
                    header_count = header.count(sep)
                    inconsistent_rows = []

                    for i, line in enumerate(lines[1:], start=1):
                        if line.strip():  # Skip tomme linjer
                            row_count = line.count(sep)
                            if row_count != header_count:
                                inconsistent_rows.append((i, row_count, header_count))

                    if inconsistent_rows:
                        examples = ", ".join([f"række {r}: {c} felter (forventet {h})"
                                            for r, c, h in inconsistent_rows[:3]])
                        warnings.append(
                            f"⚠️ INKONSISTENT FELTANTAL: {len(inconsistent_rows)} rækker har forkert antal felter. "
                            f"Eksempler: {examples}"
                        )
        except Exception as e:
            # Hvis vi ikke kan læse filen, skip warning
            pass

    return warnings

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