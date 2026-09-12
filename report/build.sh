#!/bin/sh
# Build review copies only. The author completes the official template separately.
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python verify_results.py
.venv/bin/python -m pytest tests/test_report.py -q
pandoc report/report.md --standalone --toc --toc-depth=1 \
  --css=review.css -o report/review.html
pandoc report/report.md --pdf-engine=pdflatex -o report/evidence-pack.pdf
pdfinfo report/evidence-pack.pdf
