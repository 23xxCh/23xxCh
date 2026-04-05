# H2Track-Xian Makefile
# Usage: make <target>

.PHONY: help install build test coverage lint format clean

help:  ## Show this help message
	@echo "H2Track-Xian Development Commands"
	@echo "================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install pre-commit hooks
	pip install pre-commit ruff mypy pytest pytest-cov
	pre-commit install

build:  ## Build the ROS 2 workspace
	source /opt/ros/humble/setup.bash && colcon build

test:  ## Run all tests
	pytest src/h2track_tracking/test/ -v

coverage:  ## Run tests with coverage report
	pytest src/h2track_tracking/test/ -v --cov --cov-report=term-missing --cov-fail-under=70

coverage-html:  ## Generate HTML coverage report
	pytest src/h2track_tracking/test/ -v --cov --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

lint:  ## Run linters (ruff + mypy)
	ruff check src/h2track_tracking/
	mypy src/h2track_tracking/ --ignore-missing-imports

format:  ## Format code with ruff
	ruff format src/h2track_tracking/
	ruff check src/h2track_tracking/ --fix

format-check:  ## Check code formatting without modifying
	ruff format --check src/h2track_tracking/
	ruff check src/h2track_tracking/

clean:  ## Clean build artifacts
	rm -rf build/ install/ log/ htmlcov/ .coverage coverage.xml .pytest_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

ci-local: lint test  ## Run CI checks locally (lint + test)
	@echo "✅ All CI checks passed!"
