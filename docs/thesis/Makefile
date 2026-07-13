.PHONY: pdf clean

# TeX Live 2026, pineado por digest: el tag `latest` avanza de versión cada abril
# y el PDF de la tesis debe seguir compilando igual dentro de un año.
TEX_IMAGE ?= texlive/texlive@sha256:d39efa547acfa518072600315280f92357ca8e0b9e295e09b6ccd5f5d82a1373

ifeq ($(shell command -v latexmk >/dev/null 2>&1 && echo yes),yes)
RUN :=
else
# --user: sin él el contenedor escribe main.pdf y los .aux como root en el host.
# HOME: TeX necesita un directorio escribible para texmf-var y la caché de fuentes,
# y el uid del host no tiene entrada en /etc/passwd de la imagen.
RUN := docker run --rm --user $(shell id -u):$(shell id -g) -e HOME=/tmp \
	-v "$(CURDIR)":/thesis -w /thesis $(TEX_IMAGE)
endif

pdf:
	$(RUN) latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error main.tex

# -bibtex: sin él, latexmk trata main.bbl como fuente y -C no lo borra.
clean:
	$(RUN) latexmk -C -bibtex main.tex
