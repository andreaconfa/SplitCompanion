#!/usr/bin/env python3
"""Prepare a new directory for the separate GitHub Wiki repository. Never publish."""
import argparse
from pathlib import Path
import re
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
source = Path(__file__).resolve().parents[1] / 'wiki'
for page in source.glob('*.md'):
    text = re.sub(r'\]\(([A-Za-z0-9_-]+)\.md\)', r'](\1)', page.read_text())
    (args.output / page.name).write_text(text)
print('Wiki files prepared; nothing was published.')
