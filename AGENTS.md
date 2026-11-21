# Repository Guidelines

## Thesis Objective

Finish the thesis by following the work checklist in `TODO.md`.

## Project Structure

- `summary/` captures the work completed so far. Read it before every thesis task and use it as context. Update the relevant summary when an edit changes its claims or scope.
- `canonical/` contains the full current Portuguese thesis on JWT and Biscuit authorization in Mosquitto. Consult it for additional detail and make thesis edits here. Edit `chapter1.latex` through `chapter4.latex` for chapter content and `principal.latex` for front matter and document setup.
- `benchmarks/` holds the final data collection. Use it as the primary source for experimental results and claims based on them.
- `benchmark-archive/` preserves legacy runs, logs, and infrastructure. Consult it only for historical reference.
- If you have the separate `implementation/` checkout, its `mqtt-auth-biscuit/crates/` contains the Rust code and `mqtt-auth-biscuit/tests/integration/` contains broker integration tests. Follow that checkout’s `AGENTS.md` and `TESTING.md`.

## Build and Validate the Thesis

The complete UFFS LaTeX project supplies `UFFStex.cls`, `bibliografia.bib`, and the images under `figuras/`. Copy the canonical sources into that project as `principal.tex` and `capitulos/capitulo_1.tex` through `capitulos/capitulo_4.tex`, matching the entry point’s include paths.

Run `latexmk -pdf -interaction=nonstopmode -halt-on-error principal.tex` from the assembled project to build the PDF and resolve references. Check the log for missing citations and undefined references. Review affected pages for figure placement, table overflow, and formatting. Thesis validation is manual in this repository.

## LaTeX Style

Write thesis prose in Brazilian Portuguese and preserve the English abstract. Follow the surrounding indentation, use spaces for new nested environments, and preserve established citation keys and label prefixes such as `chap:` and `fig:`. Use the existing ABNT citation commands, such as `\citeonline{key}`, when adding references.

## Commits and Pull Requests

Use concise, action-oriented subjects, following recent commits such as “Add TODO.md with thesis work checklist.” In the PR description, name the affected chapters, report how you validated the change, and link related issues when available. Include an excerpt from the rendered PDF when reviewing a layout change.
