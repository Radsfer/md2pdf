# md2pdf

Converte arquivos Markdown (`.md`) para PDF via linha de comando.

## Instalação

```bash
pip install git+https://github.com/Radsfer/md2pdf.git
```

> **Nota para Python da Microsoft Store:** o comando `md2pdf` pode não ser reconhecido
> porque a pasta `Scripts` não está no PATH. Adicione-a manualmente:
> ```powershell
> # PowerShell (admin)
> [Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts", "User")
> ```
> Após fechar e reabrir o terminal, o comando estará disponível.

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

## Diagramas Mermaid

Blocos ` ```mermaid ` ` sao automaticamente renderizados como imagens no PDF.

Na primeira conversao com diagramas, o **mermaid-cli e instalado
automaticamente** (requer Node.js/npm no PATH).

Para instalar manualmente:

```bash
npm install -g @mermaid-js/mermaid-cli
```

Caso o Node.js nao esteja disponivel, os blocos Mermaid serao mantidos
como codigo-fonte no PDF.

## Dependências

- [markdown](https://pypi.org/project/markdown/)
- [xhtml2pdf](https://pypi.org/project/xhtml2pdf/)
- [pypdf](https://pypi.org/project/pypdf/)
- [Node.js](https://nodejs.org/) + [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (opcional, para diagramas Mermaid)

## Licença

MIT © Radsfer
