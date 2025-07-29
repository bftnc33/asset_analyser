# 📈 Asset Analyzer

This project fetches and analyzes stock and crypto market data, detects technical signals, and sends alerts via email and Telegram.

The workflow is managed using a `Makefile` to streamline setup, development, and execution.

THE OUTPUT OF THIS SHOULD NOT BE USED TO MAKE ANY INVESTMENT DECISIONS.  ITS ALERTS ARE DESIGNED TO BE SIMPLE CURRENT STATUS INDICATORS TO BE UTILISED ALONGSIDE MANUAL ANALYSIS.

---

## 🧰 Makefile Commands

# 🔧 Project Setup
make install     # Create virtual environment and install dependencies

# 🐍 Virtual Environment
make shell       # Open an interactive shell with the venv activated

# 🚀 Run Script
make money       # Run the main analysis script

# 🧹 Clean Up
make clean       # Remove venv and Python cache files