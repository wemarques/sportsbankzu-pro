# Known Test Failures — Baseline

> **Last updated:** 2026-03-21 (REGRAS #057)
> **Total:** 10 known failures (1 collection error + 1 missing sklearn + 8 Streamlit visual tests)

## Category 1: Broken pandas installation (1 test)

| Test | Error | Root Cause |
|------|-------|------------|
| `tests/unit/test_util_service.py` (collection) | `ModuleNotFoundError: No module named 'pandas._libs.pandas_parser'` | Corrupted pandas install in .venv — needs `pip install --force-reinstall pandas` |

**Impact:** Test collection fails entirely for this file. Ignored via `--ignore` in CI.

## Category 2: Missing sklearn dependency (1 test)

| Test | Error | Root Cause |
|------|-------|------------|
| `tests/test_corner_framework.py::TestMLRegression::test_train_corner_regressor` | `ModuleNotFoundError: No module named 'sklearn'` | scikit-learn not in requirements.txt (optional ML dependency) |

**Fix:** `pip install scikit-learn` or mark as optional.

## Category 3: Streamlit visual tests (8 tests)

All in `tests/test_visual.py` — require running Streamlit app with full pandas/rendering environment:

| Test | Error |
|------|-------|
| `test_app_loads` | ElementList assertion |
| `test_title_present` | 'SportsBankZU Pro' not found |
| `test_backend_url_displayed` | assert False |
| `test_filters_present` | assert 0 > 0 |
| `test_quadro_resumo_section` | assert False |
| `test_checkboxes_present` | assert 0 > 0 |
| `test_buttons_present` | assert False |
| `test_responsive_css_present` | assert False |

**Root Cause:** These tests use `streamlit.testing.v1.AppTest` which requires a full Streamlit runtime with pandas. The test environment has broken pandas (see Category 1).

**Impact:** None on backend or Next.js frontend. These test the legacy Streamlit UI (app.py).

## Running tests without known failures

```bash
python -m pytest -q -o "addopts=" --ignore=tests/unit/test_util_service.py --ignore=tests/test_visual.py -k "not test_train_corner_regressor"
```

Or with the full suite (expect 9 failures + 1 collection error):
```bash
python -m pytest -q -o "addopts=" --ignore=tests/unit/test_util_service.py
```
