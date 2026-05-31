.PHONY: help install dev test hello demo clean

help:
	@echo "Targets:"
	@echo "  install   pip install runtime dependency (requests)"
	@echo "  dev       pip install dev dependencies (pytest)"
	@echo "  test      run the test suite"
	@echo "  hello     run examples/01_hello_agent.py"
	@echo "  demo      run examples/02_iso20022_demo.py"
	@echo "  clean     remove __pycache__ and .pytest_cache"

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v

hello:
	python examples/01_hello_agent.py

demo:
	python examples/02_iso20022_demo.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache
