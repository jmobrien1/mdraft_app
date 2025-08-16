SHELL := /bin/bash
export BASE_URL ?= https://mdraft-web.onrender.com

.PHONY: smoke-criteria smoke-outline gen-eval check-prompts health test-cookies validate-cookies lock lock-dev security-audit security-scan build-validate install-dev test-pip-tools

# Dependency management with pip-tools
lock:
	@echo "🔒 Locking production dependencies..."
	pip-compile requirements.in --upgrade --generate-hashes --output-file requirements.txt
	@echo "✅ Production dependencies locked"

lock-dev:
	@echo "🔒 Locking development dependencies..."
	pip-compile requirements-dev.in --upgrade --generate-hashes --output-file requirements-dev.txt
	@echo "✅ Development dependencies locked"

# Security scanning
security-audit:
	@echo "🔍 Running pip-audit for vulnerability scanning..."
	pip-audit --format json --output pip-audit-report.json || true
	@echo "📊 pip-audit report saved to pip-audit-report.json"
	@echo "🔍 Running safety for additional security checks..."
	safety check --json --output safety-report.json || true
	@echo "📊 safety report saved to safety-report.json"

security-scan: security-audit
	@echo "🔍 Checking for high/critical vulnerabilities..."
	@if [ -f pip-audit-report.json ]; then \
		echo "📋 pip-audit findings:"; \
		cat pip-audit-report.json | grep -E '"severity": "(HIGH|CRITICAL)"' || echo "✅ No high/critical vulnerabilities found in pip-audit"; \
	fi
	@if [ -f safety-report.json ]; then \
		echo "📋 safety findings:"; \
		cat safety-report.json | grep -E '"severity": "(HIGH|CRITICAL)"' || echo "✅ No high/critical vulnerabilities found in safety"; \
	fi

# Build validation
build-validate:
	@echo "🔍 Running comprehensive build validation..."
	python3 scripts/build_validation.py

# Development setup
install-dev:
	@echo "📦 Installing development dependencies..."
	pip install -r requirements-dev.txt
	@echo "✅ Development dependencies installed"

# Testing
test-pip-tools:
	@echo "🧪 Testing pip-tools workflow..."
	python3 scripts/test_pip_tools.py

# Existing targets
smoke-criteria:
	./scripts/dev_curl.sh smoke_criteria

smoke-outline:
	./scripts/dev_curl.sh smoke_outline

gen-eval:
	@if [ -z "$(DOC_ID)" ]; then echo "Usage: make gen-eval DOC_ID=<uuid>"; exit 2; fi
	./scripts/dev_curl.sh gen_eval $(DOC_ID)

check-prompts:
	./scripts/dev_curl.sh check_prompts

health:
	./scripts/dev_curl.sh health

test-cookies:
	python test_cookie_hardening.py $(BASE_URL)

validate-cookies:
	python scripts/validate_cookie_hardening.py $(BASE_URL) cookie_validation_results.json
