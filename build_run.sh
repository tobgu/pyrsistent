#!/bin/sh

# Build C module and run tests if compilation succeeds.
# Can be used together with nosier to create a decent code-build-test cycle
# nosier "./build_run.sh"
~/py/bin/python setup.py build --debug && ~/py/bin/python pyrsistentc_vector_test.py
