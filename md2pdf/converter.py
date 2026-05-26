import html as html_mod
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import warnings
from glob import glob
from io import StringIO
from pathlib import Path

import markdown
from xhtml2pdf import pisa
from pypdf import PdfWriter

try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    _HAS_SVGLIB = True
except Exception:
    _HAS_SVGLIB = False

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
    td code {
        white-space: normal;
        word-break: break-all;
        overflow-wrap: break-word;
        -pdf-word-wrap: break-word;
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
        white-space: pre-wrap;
        word-wrap: break-word;
        -pdf-word-wrap: break-word;
        word-break: break-all;
    }
    pre code {
        white-space: pre-wrap;
        word-wrap: break-word;
        -pdf-word-wrap: break-word;
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


def _find_chrome_or_edge():
    """Tenta localizar chrome.exe ou msedge.exe no Windows."""
    candidatos = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for caminho in candidatos:
        if os.path.isfile(caminho):
            return caminho
    return None


def _render_svg_browser(browser_path, svg_path, png_path, scale=2):
    """Renderiza SVG para PNG usando Chrome/Edge headless.

    Args:
        browser_path: Caminho do executavel chrome/msedge.
        svg_path: Caminho do arquivo SVG de entrada.
        png_path: Caminho do arquivo PNG de saida.
        scale: Fator de escala para alta resolucao (default 2x).

    Returns:
        True se o PNG foi gerado com sucesso.
    """
    # Extrair dimensoes do SVG via svglib (apenas para window-size)
    try:
        old_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            drawing = svg2rlg(svg_path)
            if drawing is None:
                return False
            base_w = int(drawing.width)
            base_h = int(drawing.height)
        finally:
            sys.stderr = old_stderr
    except Exception:
        return False

    w = base_w * scale
    h = base_h * scale

    svg_url = Path(svg_path).as_uri()

    # Garante que o PNG de saida nao exista previamente
    if os.path.isfile(png_path):
        os.remove(png_path)

    cmd = [
        browser_path,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        "--screenshot=" + os.path.abspath(png_path),
        "--window-size={},{}".format(w, h),
        svg_url,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return False

    # O Chrome/Edge headless demora um pouco para escrever o arquivo
    for _ in range(10):
        if os.path.isfile(png_path) and os.path.getsize(png_path) > 0:
            return True
        time.sleep(0.3)

    return False


def _replace_svg_images(html, temp_dir, base_dir):
    """Substitui <img src=\"... .svg\"> por imagens PNG.

    O xhtml2pdf nao renderiza SVGs complexos. Esta funcao converte
    arquivos SVG referenciados em <img> para PNG, preferindo
    Chrome/Edge headless (alta qualidade) e fallback para svglib.

    Args:
        html: HTML pos-markdown.
        temp_dir: Diretorio temporario para armazenar os PNGs gerados.
        base_dir: Diretorio base para resolver caminhos relativos.

    Returns:
        HTML com atributos src de imagens SVG atualizados para PNG.
    """
    browser = _find_chrome_or_edge()
    tem_browser = browser is not None

    padrao = re.compile(
        r'<img([^>]+?)src=["\']([^"\']+\.svg)["\']([^>]*?)>',
        re.IGNORECASE,
    )

    substituicoes = []

    for idx, match in enumerate(padrao.finditer(html)):
        svg_src = match.group(2)
        # Resolver caminho absoluto
        if os.path.isabs(svg_src):
            svg_path = svg_src
        else:
            svg_path = os.path.join(base_dir, svg_src)

        if not os.path.isfile(svg_path):
            continue

        png_name = f"svg_{idx}.png"
        png_path = os.path.join(temp_dir, png_name)

        ok = False
        # Tenta renderizar com browser headless (melhor qualidade)
        if tem_browser:
            ok = _render_svg_browser(browser, svg_path, png_path, scale=1)

        # Fallback para svglib + renderPM
        if not ok and _HAS_SVGLIB:
            try:
                old_stderr = sys.stderr
                sys.stderr = StringIO()
                try:
                    drawing = svg2rlg(svg_path)
                    if drawing is not None:
                        renderPM.drawToFile(drawing, png_path, fmt="PNG")
                        ok = True
                finally:
                    sys.stderr = old_stderr
            except Exception:
                ok = False

        if not ok:
            continue

        png_url = png_path.replace(os.sep, "/")
        new_tag = (
            f'<div style="text-align:center;margin:1.5em 0;">'
            f'<img{match.group(1)}src="{png_url}"{match.group(3)}>'
            f'</div>'
        )
        substituicoes.append((match.start(), match.end(), new_tag))

    for start, end, replacement in sorted(
        substituicoes, key=lambda x: x[0], reverse=True
    ):
        html = html[:start] + replacement + html[end:]

    return html


def _ajustar_code_em_tabelas(html, max_len=25):
    """Insere <br/> dentro de <code> longos em <td> para forcar quebra,
    pois o xhtml2pdf nao respeita word-break em <code> inline."""
    def process_td(match):
        td_inner = match.group(1)

        def quebrar_code(code_match):
            conteudo = code_match.group(1)
            if len(conteudo) <= max_len:
                return code_match.group(0)
            partes = [conteudo[i:i+max_len] for i in range(0, len(conteudo), max_len)]
            return '<code>' + '<br/>'.join(partes) + '</code>'

        new_inner = re.sub(r'<code>(.+?)</code>', quebrar_code, td_inner, flags=re.DOTALL)
        return '<td>' + new_inner + '</td>'

    return re.sub(r'<td>(.*?)</td>', process_td, html, flags=re.DOTALL)


def _ajustar_pre_blocks(html, max_len=80):
    """Insere <br/> em linhas longas dentro de <pre><code> para forcar quebra,
    pois o xhtml2pdf nao respeita word-wrap em blocos pre."""
    def process_pre_code(match):
        content = match.group(1)
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if len(line) > max_len:
                parts = [line[i:i+max_len] for i in range(0, len(line), max_len)]
                new_lines.append('<br/>'.join(parts))
            else:
                new_lines.append(line)
        return '<pre><code>' + '\n'.join(new_lines) + '</code></pre>'

    return re.sub(r'<pre><code[^>]*>(.*?)</code></pre>', process_pre_code, html, flags=re.DOTALL)


def _ajustar_code_inline(html, max_len=50):
    """Insere <br/> dentro de <code> inline longos (fora de <td> e <pre>)
    para forcar quebra na pagina."""
    placeholders_pre = []
    placeholders_td = []

    def save_pre(m):
        placeholders_pre.append(m.group(0))
        return '__PRE_{}__'.format(len(placeholders_pre) - 1)

    def save_td(m):
        placeholders_td.append(m.group(0))
        return '__TD_{}__'.format(len(placeholders_td) - 1)

    html_temp = re.sub(r'<pre>.*?</pre>', save_pre, html, flags=re.DOTALL)
    html_temp = re.sub(r'<td>.*?</td>', save_td, html_temp, flags=re.DOTALL)

    def quebrar_code(code_match):
        conteudo = code_match.group(1)
        if len(conteudo) <= max_len:
            return code_match.group(0)
        partes = [conteudo[i:i+max_len] for i in range(0, len(conteudo), max_len)]
        return '<code>' + '<br/>'.join(partes) + '</code>'

    html_temp = re.sub(r'<code>(.*?)</code>', quebrar_code, html_temp, flags=re.DOTALL)

    for i, val in enumerate(placeholders_td):
        html_temp = html_temp.replace('__TD_{}__'.format(i), val)
    for i, val in enumerate(placeholders_pre):
        html_temp = html_temp.replace('__PRE_{}__'.format(i), val)

    return html_temp


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
        base_dir = os.path.dirname(os.path.abspath(caminho_md))
        html_body = _replace_mermaid_blocks(html_body, temp_dir.name)
        html_body = _replace_svg_images(html_body, temp_dir.name, base_dir)
        html_body = _ajustar_pre_blocks(html_body)
        html_body = _ajustar_code_em_tabelas(html_body)
        html_body = _ajustar_code_inline(html_body)

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
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
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
