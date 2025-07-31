# Makefile
VENV_DIR := .venv
PYTHON := $(VENV_DIR)/bin/python
REQUIREMENTS := requirements.txt

SHELL := /bin/bash

.PHONY: install venv money clean shell

install:
	@echo "🛠️  Setting up virtual environment and installing dependencies..."
	python3 -m venv $(VENV_DIR)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r $(REQUIREMENTS)
	@echo "✅ Environment setup complete."

shell:
	@echo "🐚 Entering shell with virtual environment activated..."
	@$(SHELL) --rcfile <(echo "source $(VENV_DIR)/bin/activate; exec $(SHELL)")

money:
	@echo "💸 Running script..."
	$(PYTHON) main.py

clean:
	@echo "🧹 Cleaning up..."
	rm -rf $(VENV_DIR)
	rm -rf __pycache__

lint:
	@echo "Checking linting using ruff..."
	ruff check main.py