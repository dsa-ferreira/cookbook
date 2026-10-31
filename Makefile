UV ?= uv
DOCKER ?= docker
IMAGE ?= cookbook
REGISTRY ?= album.lan
# Extra flags for push, e.g. PUSH_FLAGS=--tls-verify=false (podman only).
PUSH_FLAGS ?=
VERSION := $(shell sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)
# Podman drops HEALTHCHECK from OCI-format images; ask it for Docker format.
BUILD_FLAGS ?= $(if $(shell $(DOCKER) --version 2>/dev/null | grep -i podman),--format docker,)
BIND ?= 0.0.0.0:8080

.PHONY: install lint format test run migrate apikey image push

install:
	$(UV) sync

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format:
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

test:
	$(UV) run pytest

# Needs COOKBOOK_DATABASE_URL and COOKBOOK_API_KEYS in the environment.
run:
	$(UV) run gunicorn --bind $(BIND) 'cookbook.app:create_app()'

migrate:
	$(UV) run cookbook migrate

# Usage: make apikey NAME=diogo
apikey:
	@test -n "$(NAME)" || { echo "usage: make apikey NAME=<key name>" >&2; exit 2; }
	@$(UV) run cookbook apikey "$(NAME)"

image:
	$(DOCKER) build $(BUILD_FLAGS) -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .

# Builds first so the pushed image always matches the working tree.
# Needs `docker login $(REGISTRY)` and a machine that trusts the registry's CA.
push: image
	@for tag in $(VERSION) latest; do \
		echo "pushing $(REGISTRY)/$(IMAGE):$$tag"; \
		$(DOCKER) tag $(IMAGE):$$tag $(REGISTRY)/$(IMAGE):$$tag || exit 1; \
		$(DOCKER) push $(PUSH_FLAGS) $(REGISTRY)/$(IMAGE):$$tag || exit 1; \
	done
