.PHONY: fetch build report profile all clean

fetch:
	python src/fetch_data.py --centrali

build:
	python src/build_fatti.py

report:
	python src/report.py --profili

profile:
	python src/profiler.py 97103880585

all: fetch build report

clean:
	rm -f data/*.parquet
	rm -f reports/data.json
