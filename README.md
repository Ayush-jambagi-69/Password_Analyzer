# PasswordLab: Password Strength & Combinatorics Analyzer

Discrete Mathematics project. **Python 3 + Flask backend** (all the maths) and a **vanilla HTML/CSS/JS frontend** (Chart.js bundled locally). No compiler, CMake, Node.js, database or internet access (after installing Flask) is needed.

## Requirements
Python 3.9 or newer from <https://www.python.org/downloads/>. In the installer, tick **Add python.exe to PATH**.

## Start (one click)
Double-click **`run.bat`**. It checks for Python, creates `.venv`, installs `backend\requirements.txt`, starts the server in its own window, waits until it responds and opens <http://127.0.0.1:5000>. Running it again while the server is up just opens the browser (no second server). Close the "PasswordLab server" window to stop.

## Start (manual, from the project root)
```cmd
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
python backend\app.py
```
Open <http://127.0.0.1:5000>. Another port: `python backend\app.py 5001`.

## Project structure
```
PasswordLab/
├── run.bat                    one-click launcher (Windows)
├── backend/
│   ├── app.py                 Flask server: API routes + serves frontend/
│   ├── password_analyzer.py   JSON request -> JSON report (analyze, compare, sweep)
│   ├── combinatorics.py       pools (set union), R^L, inclusion-exclusion
│   ├── entropy.py             H = L*log2(R), log10(N), scientific notation
│   ├── guessing_time.py       T_worst = N/G, T_avg = N/(2G), readable units
│   └── requirements.txt
├── frontend/                  index.html, styles.css, app.js, vendor/chart.umd.js
└── tests/test_backend.py      math, API and frontend-contract tests
```

## Privacy
The typed password is inspected only in the browser (patterns, character classes). The server receives just `length` and four true/false flags, processes them in memory, and never logs or stores request bodies. Nothing is written to localStorage, sessionStorage or cookies, and there are no third-party requests.

## API (JSON over HTTP, same origin, no CORS needed)
| Method | URL | Purpose |
|---|---|---|
| POST | `/api/analyze-config` | pool, search space, entropy, guessing times, optional constrained count |
| POST | `/api/compare` | two configurations plus entropy difference split into length and pool terms |
| POST | `/api/sweep` | entropy and log10(N) for lengths 1..maxLength for up to 8 configurations (charts) |
| GET | `/api/health` | `{"ok": true}` |

Config fields: `length` (1..1024, integer), `lower`, `upper`, `digits`, `symbols` (booleans), `symbolSet` (printable ASCII, default is the 32 standard symbols), `useCustom` + `customPool`, `required` (list of `lower|upper|digit|symbol`), `guessesPerSecond` (0 < G ≤ 1e30, default 1e9). Omitted fields default to length 8, lowercase only.

Example (PowerShell):
```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/analyze-config -ContentType application/json `
  -Body '{"length":6,"lower":true,"digits":true,"required":["digit"],"guessesPerSecond":1e10}'
```
Response (abridged):
```json
{"ok":true,"pool":{"size":36},"searchSpace":{"exact":"2,176,782,336","scientific":"2.17e+9","log10":9.338},
 "entropyBits":31.02,"guessing":{"worst":{"human":"217.7 ms"},"average":{"human":"108.8 ms"}},
 "constrained":{"count":"1,867,866,560","terms":[{"subset":"none (all strings)","unionSize":0,"sign":1,"value":"2,176,782,336"},
                {"subset":"violates all of: digit","unionSize":10,"sign":-1,"value":"308,915,776"}]},
 "steps":["R = 26 + 10 = 36", "..."]}
```
Errors return HTTP 400 (413 for bodies over 64 KB) as `{"ok": false, "errors": ["Impossible requirement: 'symbol' is required but the pool contains no such character."]}`.

## Tests
From the project root (with `.venv` active, or any Python 3):
```cmd
python -m unittest discover -s tests -v
```

## Discrete Mathematics map
| Topic | Where |
|---|---|
| Fundamental counting principle | N = R^L (`search_space`), Lab, Learn §1 |
| Sets, union, overlap | pool = union of enabled sets, duplicates counted once (`build_pool`), Learn §2 |
| Logarithms and entropy | H = L·log2 R (`entropy_bits`), charts, Learn §3 |
| Counting with constraints | R^L − (R−A)^L for "at least one" (`constrained_count`), Learn §4 |
| Inclusion-exclusion | sum over subsets of the requirements with sign (−1)^|S| (term table in the Lab), Learn §5 |
| Logic and predicates | policy as AND/OR of predicates, Learn §6 |

All results describe a *uniform random generation model*. Character variety alone does not make a password strong, and guessing times are theoretical estimates (exhaustive search at a constant rate), not predictions of real cracking time. The Analyzer's "effective bits" subtracts rough penalties for recognisable patterns and is a teaching heuristic, not a measurement.

## Troubleshooting
- **"Python was not found"**: install Python 3 and tick *Add python.exe to PATH*; or use `py -3` if the launcher `py` is installed.
- **pip fails**: check the internet connection (needed once to download Flask), or a proxy/firewall.
- **Port 5000 is busy**: run `python backend\app.py 5001` and open `http://127.0.0.1:5001`.
- **"Cannot reach the PasswordLab server" in the page**: open the app through the server URL, not by double-clicking `index.html`.
- **PowerShell blocks `activate`**: use `.venv\Scripts\activate.bat` in Command Prompt, or call `.venv\Scripts\python.exe backend\app.py` directly.
- **Broken `.venv`** (for example after upgrading Python): delete the `.venv` folder and run `run.bat` again.
