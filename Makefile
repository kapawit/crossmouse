VERSION ?= 0.1.0
SUDO ?= sudo

ifeq ($(OS),Windows_NT)
PY := python
DEPS_CMD = python -m pip install -r requirements.txt
BUILD_CMD = powershell -ExecutionPolicy Bypass -NoProfile -File packaging/build-windows.ps1
INSTALL_CMD = powershell -ExecutionPolicy Bypass -NoProfile -File packaging/install-windows.ps1
RUN_CMD = dist\CrossMouse.exe
CLEAN_CMD = powershell -NoProfile -Command "Remove-Item -Recurse -Force dist,.deb-build -ErrorAction SilentlyContinue"
else
PY := python3
DEPS_CMD = python3 -m pip install --target .deps -r requirements.txt
BUILD_CMD = ./packaging/build-deb.sh $(VERSION)
INSTALL_CMD = $(SUDO) dpkg -i dist/crossmouse_$(VERSION)_amd64.deb
RUN_CMD = ./run.sh
CLEAN_CMD = rm -rf dist .deb-build
endif

.PHONY: help deps build install build-linux install-linux build-windows install-windows run test clean

help:
	@echo "CrossMouse targets:"
	@echo "  make build            - build installer for this OS"
	@echo "  make install          - build then install for this OS"
	@echo "  make run              - run from the source tree"
	@echo "  make test             - run the test suite"
	@echo "  make build-linux      - build .deb (requires dpkg-deb)"
	@echo "  make install-linux    - build and install .deb (uses SUDO=$(SUDO))"
	@echo "  make build-windows    - build CrossMouse.exe (Windows only)"
	@echo "  make install-windows  - build and install to LOCALAPPDATA (Windows only)"
	@echo "  make deps             - install Python dependencies into .deps"
	@echo "  make clean            - remove build artifacts"

deps:
	$(DEPS_CMD)

build:
	$(BUILD_CMD)

install: build
	$(INSTALL_CMD)

build-linux: deps
	./packaging/build-deb.sh $(VERSION)

install-linux: build-linux
	$(SUDO) dpkg -i dist/crossmouse_$(VERSION)_amd64.deb

build-windows:
	powershell -ExecutionPolicy Bypass -NoProfile -File packaging/build-windows.ps1

install-windows: build-windows
	powershell -ExecutionPolicy Bypass -NoProfile -File packaging/install-windows.ps1

run:
	$(RUN_CMD)

test:
ifeq ($(OS),Windows_NT)
	$(PY) -m unittest discover -s tests -v
else
	PYTHONPATH=.deps:. $(PY) -m unittest discover -s tests -v
endif

clean:
	$(CLEAN_CMD)
