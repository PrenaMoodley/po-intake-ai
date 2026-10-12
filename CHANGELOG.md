# Changelog

All notable changes to this project. Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.1.0] - 2026-10-12

### Added
- Interactive extraction with a tool-use loop (`find_customer`, `search_catalogue`).
- Backlog extraction with the Message Batches API.
- Structured outputs from a single Pydantic `PurchaseOrder` model.
- Prompt caching for tool rounds and for batch reference data.
- Deterministic checks: totals, 15% VAT, price-list variance, unknown customers and SKUs, past delivery dates.
- Excel review workbook with live formulas, a Python cross-check column and an approval drop-down.
- Claude Code project setup: `CLAUDE.md`, `add-po-field` skill, secret-blocking and lint hooks.
- CI: ruff and pytest on Python 3.11 and 3.13.
