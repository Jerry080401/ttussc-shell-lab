# 每個步驟一個指令，設定全部在 .env。`make` 會列出所有指令。
SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

ENV ?= .env
-include $(ENV)

PYTHON ?= python3
LABCTL := $(PYTHON) -m labctl --env $(ENV)
TF := terraform -chdir=netbird/terraform
ANSIBLE := cd netbird/ansible && ../../.venv/bin/ansible-playbook
HOST_DIR := /opt/ttussc/labs
ON_HOST := ssh $(LAB_SSH) sudo $(HOST_DIR)/host

# Ansible 和 Terraform 從環境變數讀設定。
export NETBIRD_SSH NETBIRD_DOMAIN NETBIRD_PUBLIC_IP ADMIN_EMAIL
export NB_PAT := $(NETBIRD_PAT)
export TF_VAR_cohort := $(COHORT)
export TF_VAR_student_count := $(STUDENT_COUNT)
export TF_VAR_teacher_devices := $(TEACHER_DEVICES)
export TF_VAR_revoked_students := $(REVOKED_STUDENTS)
export TF_VAR_management_url := https://$(NETBIRD_DOMAIN)
export TF_VAR_setup_key_days := $(SETUP_KEY_DAYS)

.PHONY: help env check netbird class-start class-stop keys host vms enroll labs passwords cards status teardown \
	test lint fmt

help: ## 列出所有指令
	@grep -E '^[a-z-]+:.*## ' $(firstword $(MAKEFILE_LIST)) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

env: ## 從 .env.example 建立 .env，LAB_SECRET 自動產生
	@if [ -e $(ENV) ]; then echo "$(ENV) already exists, not touched"; exit 0; fi; \
	umask 077; \
	secret=$$($(PYTHON) -c 'import secrets; print(secrets.token_hex(32))'); \
	sed "s/^LAB_SECRET=$$/LAB_SECRET=$$secret/" .env.example >$(ENV); \
	echo "created $(ENV), fill it in and run: make check"

check: ## 檢查 .env
	@mkdir -p -m 700 local
	@$(LABCTL) config check

.venv/bin/ansible-playbook: versions.lock.json
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -q "ansible-core==$$($(PYTHON) -c 'import json; print(json.load(open("versions.lock.json"))["control_node"]["ansible_core"])')"
	@touch $@

netbird: check .venv/bin/ansible-playbook ## 在 VPS 上安裝 NetBird
	$(ANSIBLE) site.yml $(ANSIBLE_ARGS)

class-start: check .venv/bin/ansible-playbook ## 上課前開 NetBird
	$(ANSIBLE) class-start.yml

class-stop: check .venv/bin/ansible-playbook ## 下課後關 NetBird
	$(ANSIBLE) class-stop.yml

keys: check ## 建立 NetBird 群組、規則和 setup key（需要 NETBIRD_PAT）
	$(TF) init -input=false >/dev/null
	policy=$$($(LABCTL) netbird default-policy); TF_VAR_default_policy_id=$$policy $(TF) apply

host: check ## 把程式和設定放到實驗主機，裝好 Incus 和隔離防火牆
	@# 這些程式之後由 root 執行，解開時不保留老師電腦上的擁有者，一律歸 root。
	tar -cz --exclude=__pycache__ labctl host versions.lock.json | ssh $(LAB_SSH) \
		"sudo sh -c 'rm -rf $(HOST_DIR).new && mkdir -p $(HOST_DIR).new && tar -xz --no-same-owner -C $(HOST_DIR).new && rm -rf $(HOST_DIR) && mv $(HOST_DIR).new $(HOST_DIR)'"
	$(LABCTL) config host-env | ssh $(LAB_SSH) "sudo sh -c 'umask 077 && mkdir -p /etc/ttussc && cat >/etc/ttussc/lab.env'"
	$(ON_HOST)/install.sh

vms: check ## 建立所有學生的 VM，先建兩台試跑
	$(ON_HOST)/create-vm.sh all

enroll: check ## 每台 VM 加入 NetBird，IP 存到 local/peers.json
	$(TF) output -json setup_keys | $(LABCTL) keys vm | $(ON_HOST)/enroll-netbird.sh all | $(LABCTL) peers import

labs: check ## 把題目放進每台 VM
	$(ON_HOST)/seed-labs.sh all

passwords: check ## 產生學生密碼（local/passwords.json）並設定到每台 VM
	$(LABCTL) passwords new
	$(LABCTL) passwords export | $(ON_HOST)/set-password.sh all

cards: check ## 產生全班的連線清單 local/cards.md
	$(TF) output -json setup_keys | $(LABCTL) cards

status: check ## 看全班的 VM 和電腦在不在線
	@$(LABCTL) netbird status

teardown: check ## 課程結束：VM 關機，停掉 Incus 和隔離防火牆
	$(ON_HOST)/teardown.sh

test: ## 跑測試
	$(PYTHON) -m unittest discover -s tests -t .

lint: ## 檢查程式格式
	ruff check .
	ruff format --check .
	shellcheck -x host/*.sh host/gateway-sync tests/netlab.sh
	terraform -chdir=netbird/terraform fmt -check -recursive

fmt: ## 自動整理程式格式
	ruff check --fix .
	ruff format .
	terraform -chdir=netbird/terraform fmt -recursive
