# Makefile
VENV_DIR := .venv
PYTHON := $(VENV_DIR)/bin/python
REQUIREMENTS := requirements.txt

SHELL := /bin/bash

.PHONY: install venv money clean shell tests coverage

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
	ruff check .

tests:
	@echo "🧪 Running tests..."
	$(PYTHON) -m pytest test_technical_analysis.py test_main.py -v

coverage:
	@echo "📊 Running tests with coverage..."
	$(PYTHON) -m pytest test_technical_analysis.py test_main.py --cov=technical_analysis --cov=main --cov-report=term-missing --cov-report=html
	@echo "📂 HTML report generated in htmlcov/index.html"