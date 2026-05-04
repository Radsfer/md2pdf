# md2pdf

Converte arquivos Markdown (`.md`) para PDF via linha de comando.

## Instalação

```bash
pip install git+https://github.com/Radsfer/md2pdf.git
```

Ou instale as dependências manualmente:

```bash
pip install markdown xhtml2pdf pypdf
```

## Uso

```bash
# Exporta um arquivo
md2pdf export README.md

# Exporta com saída personalizada
md2pdf export README.md -o docs/README.pdf

# Exporta todos os .md de um diretório
md2pdf export docs/

# Exporta diretório gerando também um PDF consolidado
md2pdf export docs/ --merge

# Junta PDFs existentes em um só
md2pdf merge doc1.pdf doc2.pdf doc3.pdf -o consolidado.pdf

# Sem argumentos: exporta todos os .md do diretório atual
md2pdf
```

## Dependências

- [markdown](https://pypi.org/project/markdown/)
- [xhtml2pdf](https://pypi.org/project/xhtml2pdf/)
- [pypdf](https://pypi.org/project/pypdf/)

## Licença

MIT © Radsfer
