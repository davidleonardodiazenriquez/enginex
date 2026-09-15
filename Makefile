PYTHON := .venv/bin/python
ADDRESS ?= 127.0.0.1:8000

.PHONY: setup dev worker test check db-init db-start db-stop db-status db-shell

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

dev: db-start
	$(PYTHON) manage.py runserver $(ADDRESS)

# The local worker processes jobs in the local PostgreSQL database.
worker: db-start
	$(PYTHON) manage.py process_contracts --loop

test:
	$(PYTHON) manage.py test --settings=config.test_settings

check:
	$(PYTHON) manage.py check

db-init:
	$(PYTHON) scripts/local_database.py init

db-start:
	$(PYTHON) scripts/local_database.py start

db-stop:
	$(PYTHON) scripts/local_database.py stop

db-status:
	$(PYTHON) scripts/local_database.py status

db-shell:
	$(PYTHON) scripts/local_database.py shell
