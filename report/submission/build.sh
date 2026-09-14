#!/bin/sh
# Build the submission DOCX and PDF from final-report.md using the official
# template's typography. Run from the repository root. Requires pandoc and LibreOffice.
set -eu
out=report/submission
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
# The Google Docs template export makes LibreOffice collapse pandoc tables, so start
# from pandoc's default reference and transplant the template's fonts and heading styles.
pandoc -o "$tmp/default.docx" --print-default-data-file reference.docx
.venv/bin/python - report/official-template.docx "$tmp/default.docx" "$tmp/reference.docx" <<'PY'
import re, sys, zipfile
template, default, dst = sys.argv[1:]
styles = zipfile.ZipFile(template).read("word/styles.xml").decode()

def style(xml, sid):
    return re.search(r'<w:style [^>]*w:styleId="%s".*?</w:style>' % sid, xml, re.S)

with zipfile.ZipFile(default) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "word/styles.xml":
            xml = data.decode()
            xml = re.sub(r"<w:rPrDefault>.*?</w:rPrDefault>",
                         re.search(r"<w:rPrDefault>.*?</w:rPrDefault>", styles, re.S).group(0), xml, flags=re.S)
            for sid in ("Title", "Heading1", "Heading2", "Heading3"):
                source, target = style(styles, sid), style(xml, sid)
                if source and target:
                    xml = xml.replace(target.group(0), source.group(0))
            data = xml.encode()
        zout.writestr(item, data)
PY
(cd "$out" && pandoc final-report.md --columns=40 -o final-report.docx \
  --reference-doc="$tmp/reference.docx" --resource-path=.:..)
.venv/bin/python - "$out/final-report.docx" <<'DOCX'
import sys, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
path = Path(sys.argv[1])
ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
w = "{" + ns["w"] + "}"
with zipfile.ZipFile(path) as source:
    entries = [(info, source.read(info.filename)) for info in source.infolist()]
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target:
    for info, data in entries:
        if info.filename == "word/document.xml":
            root = ET.fromstring(data)
            for row in root.findall(".//w:tr", ns):
                props = row.find("w:trPr", ns)
                if props is None:
                    props = ET.Element(w + "trPr")
                    row.insert(0, props)
                ET.SubElement(props, w + "cantSplit")
            for paragraph in root.findall(".//w:body/w:p", ns):
                text = "".join(paragraph.itertext())
                if text.startswith("Table "):
                    props = paragraph.find("w:pPr", ns)
                    if props is None:
                        props = ET.Element(w + "pPr")
                        paragraph.insert(0, props)
                    ET.SubElement(props, w + "keepNext")
            data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        target.writestr(info, data)
DOCX
cp "$out/final-report.docx" "$tmp/"
soffice --headless --norestore -env:UserInstallation="file://$tmp/profile" \
  --convert-to pdf --outdir "$tmp" "$tmp/final-report.docx" >/dev/null 2>&1
cp "$tmp/final-report.pdf" "$out/final-report.pdf"
pdfinfo "$out/final-report.pdf" | grep Pages
