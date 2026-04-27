.PHONY: test lint run

test:
	pytest backend/tarkov/tests -q

run:
	python -m tarkov.main process-articles --input-source jsonl --input-path articles.jsonl
