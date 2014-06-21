#!/bin/sh

# Build C module and run tests if compilation succeeds.
# Can be used together with nosier to create a decent code-build-test cycle
# nosier "./build_run.sh"
python setup.py clean --all && python setup.py install && py.test tests/ "$@"
