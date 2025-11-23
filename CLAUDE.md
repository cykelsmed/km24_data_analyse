# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KM24 Data Analyst is an AI-powered data quality analyzer for quick dataset triage. It's designed for Danish data journalism at KM24 media. The tool generates prioritized cleanup tasks, concrete Python code snippets, and story ideas for data journalism.

**Key workflow:**
1. Drop CSV/Excel/Parquet file in `data/` folder
2. Run analyzer from `data/` directory: `python3 ../km24_auto_analyst.py`
3. Review generated `ANALYSE_[filename].md` report

## Commands

### Running the Analyzer
```bash
# Basic usage (must be run from data/ directory)
cd data
python3 ../km24_auto_analyst.py

# The script will auto-cleanup old ANALYSE_*.md and RAPPORT_*.txt files before running
```

### Dependencies
```bash
pip install pandas numpy anthropic matplotlib tabulate
```

### API Key Setup
```bash
# Set as environment variable (recommended)
export ANTHROPIC_API_KEY='your-key-here'

# Or create .env file (gitignored)
echo "ANTHROPIC_API_KEY=sk-ant-api03-..." > .env
```

## Architecture

### Single-File Design
The entire analyzer is contained in `km24_auto_analyst.py` (~400 lines). It follows a pipeline pattern:

1. **File Discovery** → Glob for CSV/Excel/Parquet files in current directory
2. **Local Audit** → `run_local_audit()` generates technical log with multiple detectors
3. **AI Analysis** → `analyze_and_ask_claude()` sends to Claude API
4. **Report Generation** → Saves markdown with analysis + raw log

### Key Functions

- **`load_system_prompt()`** (lines 13-48)
  Loads AI instructions from `system_prompt.txt`. Falls back to hardcoded prompt if file missing.

- **`run_local_audit(filepath)`** (lines 104-191)
  Generates comprehensive technical audit log. Returns formatted string with:
  - File metadata (encoding, size)
  - **Multi-detector warnings** (truncation, metadata, ID issues, CSV parsing)
  - Column-by-column analysis with pattern flags
  - Top 5 values per column
  - Raw data sample (first 5 rows)

  Integrates all detectors:
  - `detect_truncated_columns()`
  - `detect_metadata_issues()`
  - `detect_id_inconsistencies()`
  - `detect_csv_parsing_issues()`

- **`detect_problematic_types(series)`** (lines 193-225)
  Pattern detection for Danish data issues:
  - `DATO_TEXT_DK`: Danish date formats like "24maj2025" (flexible regex - accepts with/without separators)
  - `NUM_COMMA`: Comma decimals ("5,19")
  - `GHOST_NULLS`: Whitespace masquerading as empty strings
  - `DIRTY_ID`: Inconsistent ID formats (8 or 10 digits)
  - `LONG_TEXT`: Columns averaging >60 chars
  - `INVALID_POSTAL`: Invalid Danish postal codes (validates 1000-9990 range)

- **`detect_truncated_columns(df)`** (lines 227-264)
  Detects problematic column names:
  - **BOM detection**: UTF-8 byte order mark in first column (U+FEFF)
  - **Long column names**: >50 characters (makes code hard to read)
  - **Truncation patterns**: Columns ending in "..." or suspiciously cut-off words

- **`detect_metadata_issues(df)`** (lines 266-300)
  Flags missing data governance columns:
  - Temporal metadata (created_at, updated_at, timestamp)
  - Source tracking (source, kilde, origin)
  - Version control (version, revision)
  - Unique identifiers (id, key)

- **`detect_id_inconsistencies(df)`** (lines 302-348)
  Identifies mixed ID formats in columns:
  - **Mixed CVR/P-numbers**: Same column containing both 8-digit CVR and 10-digit P-numbers
  - **Variable ID lengths**: Columns with inconsistent digit counts
  - Targets columns with names like 'cvr', 'p-nummer', 'virksomhed', 'id'

- **`detect_csv_parsing_issues(df, filepath)`** (lines 350-394)
  Catches CSV structural problems:
  - **Unnamed columns**: Pandas-generated 'Unnamed:X' columns indicate parsing errors
  - **Inconsistent field counts**: Validates first 10 rows have same number of separators as header
  - Essential for catching unquoted commas in data fields

- **`analyze_and_ask_claude(filepath, system_prompt)`** (lines 50-102)
  Orchestrates the AI analysis. Calls `run_local_audit()`, sends to Claude API (model: `claude-sonnet-4-5-20250929`), saves markdown report.

### Configuration Constants (lines 7-11)
- `READ_ROWS = 50000`: Max rows to analyze (performance vs completeness)
- `MAX_SAMPLE = 5`: Rows shown in audit log sample
- `SYSTEM_PROMPT_FILE = "system_prompt.txt"`: AI instruction file
- `API_KEY`: Reads from `ANTHROPIC_API_KEY` env var

### Danish Data Patterns
The analyzer is optimized for Danish public sector data:
- CVR numbers (8 digits) - Company registry
- P-numbers (10 digits) - Production unit numbers
- EAN location codes (13 digits)
- Postal codes (1000-9990)
- Municipality codes (101-860)
- Danish month names in dates ("maj" → "May")
- Comma decimals instead of dots

### AI Prompt Architecture
`system_prompt.txt` defines a two-part analysis structure:

**DEL 1: TEKNISK TILSTANDSRAPPORT**
- Data quality score (1-10)
- Compliance log (ISO 8601, CSV standards)
- Prioritized cleanup tasks in 3 tiers:
  - ⚠️ KRITISK (blocking issues - må fixes før brug)
  - 🔧 VIGTIGT (important but workable - bør fixes)
  - ✨ NICE-TO-HAVE (cosmetic improvements)
- Distinction between **KILDEDATA-PROBLEMER** (fixable with code) vs **EKSPORT-PROBLEMER** (requires re-export from source system)

**DEL 2: DATAJOURNALISTISK VURDERING**
- Dataset context inference (what does the data represent?)
- Enrichment opportunities (DAWA, CVR, DST APIs)
- **Research-potentiale og videre analyse** (changed from concrete story proposals):
  - **A. Hvad kunne materialet potentielt bruges til?** - Open-ended exploration questions
  - **B. Hvor er det særligt relevant at researche videre?** - 2-3 concrete analysis areas with:
    - **Område**: Area of investigation (e.g., geographic inequality, temporal patterns)
    - **Hypotese**: What could we expect to find?
    - **Næste skridt**: Concrete analysis steps, missing data requirements
    - **Datamæssigt grundlag**: Assessment of data sufficiency

This approach focuses on **hypothesis generation** rather than premature conclusions, providing research direction for further investigation.

Each technical task includes:
- Problem description
- Concrete solution (with code)
- Tool recommendation
- Time estimate

### File Structure Expectations
```
km24_data_analyse/
├── km24_auto_analyst.py    # Main script (~400 lines)
├── system_prompt.txt        # AI instructions (customizable)
├── .env                     # API key (gitignored)
├── CLAUDE.md                # This file - documentation for Claude Code
├── README.md                # User-facing documentation
└── data/                    # Working directory
    ├── [dataset].csv        # Input files
    ├── test_problems.csv    # Regression test suite
    └── ANALYSE_[dataset].md # Generated reports
```

### Test-Driven Development
The repository includes `data/test_problems.csv` - a synthetic dataset with known issues:
- Invalid postal codes (500, 999, 10000)
- Danish date formats without separators ("24maj2025")
- Comma decimal separators ("5,19")
- Invalid email addresses

This serves as a regression test to verify all detectors work correctly. Run analysis on this file after making changes to detector logic to ensure no regressions.

## Development Notes

### Why Run from data/ Directory?
The script uses `glob.glob()` to find data files in the current working directory (line 233). It's designed to be run from inside `data/` to avoid accidentally analyzing files in the root directory.

### Encoding Fallback Strategy (lines 118-123)
1. Try UTF-8 first (standard)
2. Fall back to CP1252 (Windows-1252) for legacy Danish data
3. Excel/Parquet formats handle encoding automatically

### Error Handling Pattern
The script has defensive error handling for:
- API errors (authentication, rate limits, connection issues) - lines 91-102
- File reading errors (encoding, parsing, permissions) - lines 159-173
- Missing system prompt file - lines 22-27

### Auto-Cleanup Behavior (lines 209-226)
Before each run, the script deletes:
- `ANALYSE_*.md` (previous AI reports)
- `RAPPORT_*.txt` (legacy format)

This prevents stale reports from confusing users.

### Security Considerations
- `.env` file is gitignored (line 2 of .gitignore)
- All data files are gitignored (lines 5-8)
- Script warns if API key is hardcoded (lines 202-204)
- Only analysis code is version controlled

## Customization

### Adjusting AI Analysis
Edit `system_prompt.txt` to customize:
- Output format or tone
- Research focus (shift from hypothesis generation to concrete stories if needed)
- Domain-specific requirements
- Prioritization logic for cleanup tasks

The prompt uses a strict structure with emoji markers (⚠️ 🔧 ✨) that downstream tools may parse - maintain these if automation depends on them.

### Adding New Detectors
To add custom data quality checks:

1. **Create detector function** following the pattern:
```python
def detect_your_issue(df):
    """Describe what this detects"""
    warnings = []
    # Your detection logic here
    if problem_found:
        warnings.append(f"⚠️ ISSUE_NAME: Description")
    return warnings
```

2. **Integrate in `run_local_audit()`** around line 147:
```python
your_warnings = detect_your_issue(df)
all_warnings = truncation_warnings + metadata_warnings + id_warnings + csv_warnings + your_warnings
```

3. **Test with `test_problems.csv`** to verify it works

### Detector Examples by Category

**Column-level detectors** (work on individual pandas Series):
- `detect_problematic_types()` - Pattern matching within column values
- Add flags like `DATO_TEXT_DK`, `NUM_COMMA`, `INVALID_POSTAL`

**DataFrame-level detectors** (work on entire dataset):
- `detect_truncated_columns()` - Column name issues
- `detect_metadata_issues()` - Missing governance columns
- `detect_id_inconsistencies()` - Cross-column validation
- `detect_csv_parsing_issues()` - Structural file problems

## Iterative Improvements

This tool was developed iteratively based on real-world data analysis:

**Phase 1: Core detectors**
- Danish date formats (DATO_TEXT_DK)
- Comma decimals (NUM_COMMA)
- BOM detection

**Phase 2: Data governance** (inspired by analyzing rapport.txt - Danish government data accessibility report)
- Long column names (>50 chars makes code hard to read)
- Missing metadata columns (created_at, source, version)
- Mixed ID formats (CVR/P-nummer confusion)

**Phase 3: Structural validation**
- CSV parsing errors (inconsistent field counts)
- Danish postal code validation (1000-9990 range)
- Improved DATO_TEXT_DK regex (now handles "24maj2025" without separators)

**Phase 4: Research-oriented output**
- Changed from "3 concrete story ideas" to "research-potentiale"
- Focus on hypothesis generation rather than premature conclusions
- Provides research direction instead of finished angles

Each improvement was validated against `test_problems.csv` and real ambulance response time datasets from Danish regions.
