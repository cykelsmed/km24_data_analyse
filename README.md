# KM24 Data Analyst

AI-powered data quality analyzer for quick dataset triage. Generates prioritized cleanup tasks, concrete Python code, and story ideas for data journalism.

## Features

🤖 **AI-Powered Analysis** - Uses Claude Sonnet 4.5 for intelligent data profiling
📊 **Data Quality Scoring** - 1-10 scale with detailed compliance log
⚠️ **Prioritized Tasks** - Critical/Important/Nice-to-have cleanup roadmap
💻 **Ready-to-Use Code** - Concrete Python snippets for each fix
📰 **Story Ideas** - 3 factual article suggestions with methodology
🔗 **Enrichment Suggestions** - External data sources (DAWA, CVR, DST)
🧹 **Auto-Cleanup** - Removes old reports before each run

## Quick Start

### 1. Install Dependencies

```bash
pip install pandas numpy anthropic matplotlib tabulate
```

### 2. Set API Key

```bash
export ANTHROPIC_API_KEY='your-key-here'
```

Or create a `.env` file:
```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### 3. Run Analysis

```bash
# Drop your dataset in the data/ folder
cp ~/Downloads/dataset.csv data/

# Run the analyzer
cd data
python3 ../km24_auto_analyst.py
```

### 4. Read Results

Open `ANALYSE_[filename].md` for:
- Technical audit report
- Prioritized cleanup tasks with code
- Article ideas with headlines
- Data enrichment suggestions

## What Gets Analyzed

- ✅ **Encoding issues** (UTF-8, cp1252)
- ✅ **Date formats** (Danish formats, ISO 8601 compliance)
- ✅ **Data types** (comma decimals, ghost nulls)
- ✅ **ID patterns** (CVR, P-numbers, EAN codes)
- ✅ **Geographic codes** (postal codes, municipalities, regions)
- ✅ **Null handling** ("ghost nulls" detection)

## Example Output

### Technical Report
```
Datakvalitets-Score: 6/10

⚠️ KRITISK (Må fixes før brug)
1. Konverter datoer til ISO 8601 format
   - Problem: Format "24jun2025 12:26:46"
   - Løsning: pd.to_datetime(df['col'], format='%d%b%Y %H:%M:%S')
   - Estimat: 15 minutter
```

### Story Ideas
```
Overskrift: "Akutberedskabet når 12 minutter langsommere frem i yderområder"
Vinkel: Geografisk ulighed i responstider
Metode: Beregn median responstid pr. postnummer, kryds med DAWA
```

## Customization

Edit `system_prompt.txt` to adjust:
- Analysis depth and focus
- Output format and tone
- Domain-specific requirements
- Story angle preferences

## File Structure

```
km24_data_analyse/
├── km24_auto_analyst.py    # Main analyzer script
├── system_prompt.txt        # Customizable AI instructions
├── .env                     # API key (gitignored)
├── data/                    # Drop datasets here
│   ├── *.csv
│   └── ANALYSE_*.md         # Generated reports
└── .gitignore              # Protects sensitive files
```

## Security

- ✅ `.env` is gitignored (API keys stay local)
- ✅ Data files are gitignored (no sensitive data in repo)
- ✅ Only analysis code is version controlled

## Danish Data Patterns

Optimized for Danish public sector data:
- CVR numbers (8 digits)
- P-numbers (10 digits)
- EAN location codes (13 digits)
- Danish postal codes (1000-9990)
- Municipality codes (101-860)
- Danish date formats ("maj" → "May")
- Comma decimals ("5,19" → "5.19")

## Use Case

**Quick Triage Workflow:**
1. Receive dataset from source
2. Run analyzer (< 2 minutes)
3. Decide:
   - ⛔ Too messy? Send cleanup tasks back to source
   - ✅ Good enough? Use provided code to clean
   - 🌟 Ready? Pick a story idea and start analysis

---

Built with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
