#!/bin/sh
# Build review copies only. The author completes the official template separately.
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python verify_results.py
.venv/bin/python -m pytest tests/test_report.py -q
rsvg-convert -w 2200 report/boundaries.svg -o report/boundaries.png
pandoc report/report.md --standalone --embed-resources --resource-path=report --toc --toc-depth=1 \
  --css=review.css -o report/track1-review.html
pandoc report/report.md --resource-path=report --pdf-engine=pdflatex -o report/track1-review.pdf
pdfinfo report/track1-review.pdf
