# ──────────────────────────────────────────────────────────────
# PG Helpers — Makefile para macOS / Linux
# Detecta automaticamente Docker ou Podman.
# ──────────────────────────────────────────────────────────────

PYTHON   ?= python3
PIP      ?= pip3
VENV_DIR ?= .venv

# ── Detecção automática do runtime de containers ─────────────
CONTAINER_RT :=
ifeq ($(shell command -v docker 2>/dev/null),)
  ifeq ($(shell command -v podman 2>/dev/null),)
    CONTAINER_RT := none
  else
    CONTAINER_RT := podman
  endif
else
  CONTAINER_RT := docker
endif

# Permite override manual:  make CONTAINER_RT=podman ...
# ──────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

# ── Targets ──────────────────────────────────────────────────

.PHONY: help check-runtime check-deps setup install run create list view \
        remove remove-all seed create-many clean info

help: ## Mostra esta ajuda
	@echo ""
	@echo "PG Helpers — comandos disponíveis"
	@echo "─────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

check-runtime: ## Verifica se Docker ou Podman está disponível
	@echo "Verificando runtime de containers..."
	@if [ "$(CONTAINER_RT)" = "none" ]; then \
		echo "ERRO: Nem Docker nem Podman foram encontrados."; \
		echo "  Instale Docker: https://docs.docker.com/get-docker/"; \
		echo "  Instale Podman: https://podman.io/getting-started/installation"; \
		exit 1; \
	fi
	@echo "Runtime detectado: $(CONTAINER_RT)"
	@if [ "$(CONTAINER_RT)" = "docker" ]; then \
		if docker info >/dev/null 2>&1; then \
			echo "Docker está em execução."; \
		else \
			echo "AVISO: Docker encontrado, mas não está respondendo."; \
			echo "  Inicie o Docker Desktop ou o daemon do Docker."; \
			exit 1; \
		fi; \
	elif [ "$(CONTAINER_RT)" = "podman" ]; then \
		if podman info >/dev/null 2>&1; then \
			echo "Podman está em execução."; \
		else \
			echo "AVISO: Podman encontrado, mas não está respondendo."; \
			echo "  Execute: podman machine start"; \
			exit 1; \
		fi; \
	fi

check-deps: ## Verifica dependências do sistema (Python, pip, runtime)
	@echo "Verificando dependências..."
	@command -v $(PYTHON) >/dev/null 2>&1 || \
		{ echo "ERRO: $(PYTHON) não encontrado. Instale Python 3.11+."; exit 1; }
	@$(PYTHON) -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null || \
		{ echo "AVISO: Python 3.11+ recomendado. Versão atual: $$($(PYTHON) --version)"; }
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Runtime: $(CONTAINER_RT)"
	@echo "Tudo certo!"

setup: check-deps ## Cria virtualenv e instala dependências
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Criando virtualenv em $(VENV_DIR)..."; \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	@echo "Instalando dependências..."
	@$(VENV_DIR)/bin/pip install --quiet --upgrade pip
	@$(VENV_DIR)/bin/pip install --quiet -r requirements.txt
	@echo "Pronto! Ative o ambiente com: source $(VENV_DIR)/bin/activate"

install: ## Instala dependências no ambiente atual (sem virtualenv)
	$(PIP) install -r requirements.txt

# ── Atalhos para a CLI ───────────────────────────────────────

run: ## Executa a CLI (ex: make run ARGS="create --seed ecommerce")
	$(PYTHON) main.py $(ARGS)

create: check-runtime ## Cria uma instância PostgreSQL (ex: make create ARGS="my-db --seed blog")
	$(PYTHON) main.py create $(ARGS)

create-many: check-runtime ## Cria múltiplas instâncias (ex: make create-many ARGS="3 --seed hr")
	$(PYTHON) main.py create-many $(ARGS)

list: ## Lista instâncias gerenciadas
	$(PYTHON) main.py list

view: ## Inicia o visualizador web (ex: make view ARGS="--port 9000")
	$(PYTHON) main.py view $(ARGS)

seed: ## Adiciona dados incrementais (ex: make seed ARGS="my-db --rows 50")
	$(PYTHON) main.py seed $(ARGS)

remove: ## Remove uma instância (ex: make remove ARGS="my-db --force")
	$(PYTHON) main.py remove $(ARGS)

remove-all: ## Remove todas as instâncias (ex: make remove-all ARGS="--force")
	$(PYTHON) main.py remove-all $(ARGS)

# ── Utilidades ───────────────────────────────────────────────

info: check-runtime ## Mostra informações do ambiente
	@echo ""
	@echo "PG Helpers — Informações do ambiente"
	@echo "────────────────────────────────────"
	@echo "  Python:    $$($(PYTHON) --version)"
	@echo "  Runtime:   $(CONTAINER_RT)"
	@echo "  SO:        $$(uname -s) $$(uname -m)"
	@if [ "$(CONTAINER_RT)" = "docker" ]; then \
		echo "  Docker:    $$(docker --version 2>/dev/null || echo 'não disponível')"; \
	elif [ "$(CONTAINER_RT)" = "podman" ]; then \
		echo "  Podman:    $$(podman --version 2>/dev/null || echo 'não disponível')"; \
	fi
	@echo ""

clean: ## Remove virtualenv e arquivos temporários
	rm -rf $(VENV_DIR) __pycache__ pg_helpers/__pycache__ pg_helpers/**/__pycache__
	@echo "Limpeza concluída."
