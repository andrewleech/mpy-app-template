# Hook for injecting project-specific setup into the test targets.
.PHONY: custom-tests
custom-tests: # Anything that must happen before the unit tests run.
custom-tests:
	@echo "unit-tests : no custom setup required."
