SHELL := /bin/bash
export BASE_URL ?= https://mdraft-web.onrender.com

.PHONY: smoke-criteria smoke-outline gen-eval check-prompts health

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
