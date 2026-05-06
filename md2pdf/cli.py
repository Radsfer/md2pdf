import argparse
import os
import sys

from md2pdf.converter import exportar_arquivo, exportar_diretorio, mesclar_pdfs


def main():
    parser = argparse.ArgumentParser(
        prog="md2pdf",
        description="Converte arquivos Markdown (.md) para PDF.",
    )
    sub = parser.add_subparsers(dest="comando", help="Comandos disponiveis")

    parser.add_argument(
        "-v", "--version",
        action="version",
        version="md2pdf 1.1.0",
    )

    # md2pdf export <arquivo.md>
    export_parser = sub.add_parser("export", help="Exporta .md para PDF")
    export_parser.add_argument(
        "entrada",
        nargs="+",
        help="Arquivo(s) .md ou diretorio contendo .md",
    )
    export_parser.add_argument(
        "-o", "--out",
        help="Arquivo/diretorio de saida (default: mesmo nome/lugar, .pdf)",
        default=None,
    )
    export_parser.add_argument(
        "--merge",
        action="store_true",
        help="Gera um PDF consolidado ao exportar um diretorio",
    )

    # md2pdf merge <pdf1> <pdf2> ... -o saida.pdf
    merge_parser = sub.add_parser("merge", help="Junta varios PDFs em um so")
    merge_parser.add_argument(
        "entrada",
        nargs="+",
        help="Arquivos PDF para juntar",
    )
    merge_parser.add_argument(
        "-o", "--out",
        required=True,
        help="Caminho do PDF consolidado de saida",
    )

    # Sem argumentos: exporta .md do diretorio atual
    if len(sys.argv) == 1:
        cwd = os.getcwd()
        print(f"Modo automatico: exportando .md de {cwd}\n")
        pdfs = exportar_diretorio(cwd)
        if pdfs:
            print(f"\n{len(pdfs)} PDF(s) gerado(s).")
        return

    args = parser.parse_args()

    if args.comando == "export":
        for item in args.entrada:
            if os.path.isdir(item):
                pdfs = exportar_diretorio(
                    item,
                    saida=args.out,
                    consolidar=args.merge,
                )
                if pdfs:
                    print(f"\n{len(pdfs)} PDF(s) gerado(s) em: {args.out or item}")
            elif os.path.isfile(item):
                if not item.lower().endswith(".md"):
                    print(f"Erro: arquivo deve ser .md: {item}")
                    continue
                pdf = exportar_arquivo(item, saida=args.out)
                if pdf:
                    print(f"  PDF gerado: {pdf}")
            else:
                print(f"Erro: caminho nao encontrado: {item}")

    elif args.comando == "merge":
        for entrada in args.entrada:
            if not os.path.isfile(entrada):
                print(f"Erro: arquivo nao encontrado: {entrada}")
                return
        mesclar_pdfs(args.entrada, args.out)
        print(f"PDF consolidado gerado: {args.out}")


if __name__ == "__main__":
    main()
