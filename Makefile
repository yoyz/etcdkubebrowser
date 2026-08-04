PYTHON ?= python3 -S

.PHONY: clean status open browse close export verify version

# Remove runtime/generated files that should not be committed:
# tmp/ holds the state file, restored etcd data dir and exports; __pycache__
# and *.pyc are Python bytecode.
clean:
	rm -rf tmp
	rm -rf __pycache__ etcdbrowser/__pycache__
	find . -name '*.pyc' -type f -delete
	@echo "cleaned"

status:
	$(PYTHON) etcdbrowser.py status $(SNAPSHOT)

open:
	$(PYTHON) etcdbrowser.py open $(SNAPSHOT)

browse:
	$(PYTHON) etcdbrowser.py browse $(VIEW)

export:
	$(PYTHON) etcdbrowser.py export $(PREFIX) $(OUT)

verify:
	$(PYTHON) etcdbrowser.py verify

close:
	$(PYTHON) etcdbrowser.py close

version:
	$(PYTHON) etcdbrowser.py --version
