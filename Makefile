PYTHON ?= python3 -S

.PHONY: clean status open browse close export export-tree verify version test release-test

# Remove runtime/generated files that should not be committed:
# tmp/ holds the state file, restored etcd data dir and exports; __pycache__
# and *.pyc are Python bytecode.
clean:
	rm -rf tmp
	rm -rf __pycache__ etcdbrowser/__pycache__ test/__pycache__
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

export-tree:
	$(PYTHON) etcdbrowser.py export-tree $(OUTDIR) --layout $(LAYOUT) --format $(FMT)

verify:
	$(PYTHON) etcdbrowser.py verify

close:
	$(PYTHON) etcdbrowser.py close

version:
	$(PYTHON) etcdbrowser.py --version

# Fast unit tests only (stdlib, no etcd, runs anywhere).
test:
	$(PYTHON) -m unittest discover -s test -p 'test_export_tree.py' -v

# Full release gate: unit tests plus integration tests that (against the
# bundled snapshot or an already-open one) export the whole tree in both
# layouts and both formats, validate every leaf is well-formed, and assert
# >= 90% of useful objects are decoded with their metadata intact.
release-test:
	$(PYTHON) -m unittest discover -s test -p 'test_*.py' -v
