PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

install:
	$(PIP) install -e .[dev]

run:
	uvicorn paddleocr_quant.api:app --reload

test:
	pytest -q

seed:
	paddleocr-quant seed

fmt:
	python -m compileall src
