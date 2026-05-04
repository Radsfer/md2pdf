import os
import glob

import markdown
from xhtml2pdf import pisa
from pypdf import PdfWriter

CSS_BASICO = """
<style>
    @page {
        size: A4;
        margin: 2cm;
    }
    body {
        font-family: "Segoe UI", "Helvetica", "Arial", sans-serif;
        font-size: 11pt;
        line-height: 1.5;
        color: #333;
    }
    h1 {
        font-size: 18pt;
        color: #1a1a1a;
        border-bottom: 2px solid #0078d4;
        padding-bottom: 6px;
    }
    h2 {
        font-size: 14pt;
        color: #222;
        margin-top: 20px;
    }
    h3 {
        font-size: 12pt;
        color: #333;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 12px 0;
        font-size: 10pt;
        table-layout: fixed;
    }
    th, td {
        border: 1px solid #999;
        padding: 6px;
        text-align: left;
        word-wrap: break-word;
        -pdf-word-wrap: break-word;
        white-space: normal;
        vertical-align: top;
    }
    th {
        background-color: #f2f2f2;
        font-weight: bold;
    }
    code {
        font-family: Consolas, monospace;
        background-color: #f4f4f4;
        padding: 2px 4px;
        font-size: 10pt;
    }
    pre {
        background-color: #f4f4f4;
        padding: 10px;
        border-left: 3px solid #0078d4;
        overflow-x: auto;
        font-size: 9pt;
    }
    blockquote {
        border-left: 4px solid #ccc;
        margin: 0;
        padding-left: 12px;
        color: #666;
    }
    hr {
        border: none;
        border-top: 1px solid #ddd;
        margin: 20px 0;
    }
</style>
"""


def encontrar_mds(diretorio):
    """Retorna lista ordenada de arquivos .md no diretorio informado."""
    padrao = os.path.join(diretorio, "*.md")
    return sorted(glob.glob(padrao))


def md_para_pdf(caminho_md, caminho_pdf):
    """Converte um unico arquivo Markdown para PDF."""
    with open(caminho_md, "r", encoding="utf-8") as f:
        texto_md = f.read()

    html_body = markdown.markdown(
        texto_md,
        extensions=["tables", "fenced_code", "toc"]
    )

    html_completo = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{os.path.basename(caminho_md)}</title>
    {CSS_BASICO}
</head>
<body>
    {html_body}
</body>
</html>"""

    with open(caminho_pdf, "wb") as out:
        result = pisa.CreatePDF(html_completo, dest=out)

    return result.err == 0


def mesclar_pdfs(lista_pdfs, caminho_saida):
    """Junta varios PDFs em um unico arquivo."""
    writer = PdfWriter()
    for pdf in lista_pdfs:
        writer.append(pdf)
    writer.write(caminho_saida)
    writer.close()


def exportar_diretorio(diretorio, saida=None, consolidar=False):
    """Exporta todos os .md de um diretorio para PDF.

    Args:
        diretorio: Caminho do diretorio com os arquivos .md.
        saida: Diretorio de saida dos PDFs (default: mesmo diretorio).
        consolidar: Se True, gera um PDF consolidado alem dos individuais.

    Returns:
        Lista de caminhos dos PDFs gerados.
    """
    arquivos_md = encontrar_mds(diretorio)

    if not arquivos_md:
        print(f"Nenhum arquivo .md encontrado em: {diretorio}")
        return []

    if saida is None:
        saida = diretorio

    os.makedirs(saida, exist_ok=True)
    pdfs_gerados = []

    print(f"Encontrados {len(arquivos_md)} arquivo(s) Markdown.\n")

    for md_path in arquivos_md:
        nome = os.path.splitext(os.path.basename(md_path))[0]
        pdf_path = os.path.join(saida, f"{nome}.pdf")

        print(f"  Convertendo: {nome}.md ... ", end="", flush=True)
        sucesso = md_para_pdf(md_path, pdf_path)

        if sucesso:
            print("OK")
            pdfs_gerados.append(pdf_path)
        else:
            print("FALHA")

    if consolidar and len(pdfs_gerados) > 1:
        consolidado_path = os.path.join(saida, "consolidado.pdf")
        print(f"\n  Gerando PDF consolidado ... ", end="", flush=True)
        mesclar_pdfs(pdfs_gerados, consolidado_path)
        print("OK")
        pdfs_gerados.append(consolidado_path)

    return pdfs_gerados


def exportar_arquivo(caminho_md, saida=None):
    """Exporta um unico arquivo .md para PDF.

    Args:
        caminho_md: Caminho do arquivo .md.
        saida: Caminho do PDF de saida (default: mesmo nome, .pdf).

    Returns:
        Caminho do PDF gerado, ou None em caso de falha.
    """
    if saida is None:
        saida = os.path.splitext(caminho_md)[0] + ".pdf"

    print(f"  Convertendo: {os.path.basename(caminho_md)} ... ", end="", flush=True)
    sucesso = md_para_pdf(caminho_md, saida)

    if sucesso:
        print("OK")
        return saida
    else:
        print("FALHA")
        return None
