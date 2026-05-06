import html as html_mod
import os
import re
import shutil
import struct
import subprocess
import tempfile
from glob import glob

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
    .mermaid-diagram {
        text-align: center;
        page-break-inside: avoid;
        margin: 1.5em 0;
    }
    .mermaid-diagram img {
        max-width: 100%;
        height: auto;
    }
    .mermaid-page-break {
        page-break-before: always;
    }
</style>
"""


def encontrar_mds(diretorio):
    """Retorna lista ordenada de arquivos .md no diretorio informado."""
    padrao = os.path.join(diretorio, "*.md")
    return sorted(glob(padrao))


def _check_mmdc():
    """Verifica se o mermaid-cli (mmdc) esta disponivel no PATH.

    Tenta instalar automaticamente se npm estiver disponivel.
    Levanta RuntimeError com instrucoes em caso de falha.
    """
    if shutil.which("mmdc") is not None:
        return

    mensagem_base = (
        "mmdc nao encontrado. Para renderizar diagramas Mermaid, instale:\n"
        "    npm install -g @mermaid-js/mermaid-cli"
    )

    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError(
            mensagem_base + "\n"
            "    (Node.js/npm tambem nao encontrado: https://nodejs.org/)"
        )

    print("  Instalando mermaid-cli automaticamente ... ", end="", flush=True)
    result = subprocess.run(
        [npm, "install", "-g", "@mermaid-js/mermaid-cli"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Falha ao instalar mmdc:\n{result.stderr.strip()}\n\n"
            f"{mensagem_base}"
        )

    if shutil.which("mmdc") is None:
        raise RuntimeError(
            "mmdc instalado mas nao encontrado no PATH.\n"
            "Adicione a pasta global do npm ao PATH e reinicie o terminal:\n"
            "    npm bin -g\n\n"
            f"Ou instale manualmente:\n    {mensagem_base.split(chr(10))[1]}"
        )

    print("OK")


def _render_mermaid(code, png_path):
    """Renderiza diagrama Mermaid para PNG via mmdc.

    Args:
        code: Codigo fonte Mermaid.
        png_path: Caminho do arquivo PNG de saida.

    Returns:
        (png_bytes, width, height) do PNG gerado.
    """
    mmdc = shutil.which("mmdc")
    result = subprocess.run(
        [mmdc,
            "--theme", "default",
            "--backgroundColor", "white",
            "--width", "1200",
            "-o", png_path,
            "-i", "-",
        ],
        input=code,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Falha ao renderizar diagrama Mermaid:\n{result.stderr}"
        )

    with open(png_path, "rb") as f:
        png_bytes = f.read()

    width = struct.unpack(">I", png_bytes[16:20])[0]
    height = struct.unpack(">I", png_bytes[20:24])[0]

    return png_bytes, width, height


def _replace_mermaid_blocks(html, temp_dir):
    """Substitui blocos <code class="language-mermaid"> por imagens PNG.

    Renderiza cada diagrama Mermaid com mmdc e substitui no HTML por
    uma tag <img> apontando para o arquivo temporario.

    Args:
        html: HTML com blocos de codigo Mermaid (pos-markdown).
        temp_dir: Diretorio temporario para armazenar os PNGs gerados.

    Returns:
        HTML com blocos Mermaid substituidos por <div><img ...></div>.
    """
    padrao = re.compile(
        r'<pre><code class="language-mermaid">(.+?)</code></pre>',
        re.DOTALL,
    )

    matches = list(padrao.finditer(html))
    if not matches:
        return html

    try:
        _check_mmdc()
    except RuntimeError as e:
        print(f"  Aviso: {e}")
        return html

    substituicoes = []

    for idx, match in enumerate(matches):
        code_html = match.group(1)
        code = html_mod.unescape(code_html)

        png_path = os.path.join(temp_dir, f"mermaid_{idx}.png")

        try:
            _, _, height = _render_mermaid(code, png_path)
        except RuntimeError as e:
            print(f"  Aviso: {e}")
            continue

        extra_class = " mermaid-page-break" if height > 800 else ""
        png_url = png_path.replace(os.sep, "/")

        substituicoes.append((
            match.start(),
            match.end(),
            (
                f'<div class="mermaid-diagram{extra_class}">'
                f'<img src="{png_url}" alt="mermaid diagram" />'
                f'</div>'
            ),
        ))

    for start, end, replacement in sorted(
        substituicoes, key=lambda x: x[0], reverse=True
    ):
        html = html[:start] + replacement + html[end:]

    return html


def md_para_pdf(caminho_md, caminho_pdf):
    """Converte um unico arquivo Markdown para PDF."""
    with open(caminho_md, "r", encoding="utf-8") as f:
        texto_md = f.read()

    html_body = markdown.markdown(
        texto_md,
        extensions=["tables", "fenced_code", "toc"]
    )

    temp_dir = tempfile.TemporaryDirectory()
    try:
        html_body = _replace_mermaid_blocks(html_body, temp_dir.name)

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
    finally:
        temp_dir.cleanup()

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
