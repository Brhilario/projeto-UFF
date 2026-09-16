"""
Script para converter o GUIA_TEORICO_E_TECNICO.md em um documento PDF profissional,
utilizando markdown + PyQt5.QtPrintSupport (QPrinter e QTextDocument).
"""
from __future__ import annotations

import os
import sys
import markdown
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QTextDocument
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtCore import QSizeF

def markdown_to_pdf(input_md: str, output_pdf: str) -> None:
    if not os.path.exists(input_md):
        raise FileNotFoundError(f"Arquivo {input_md} não encontrado!")

    with open(input_md, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Converte markdown com extensões de tabelas e blocos de código
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    # Folha de estilos CSS elegante para impressão
    css = """
    <style>
        body {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.5;
            color: #2d3748;
            margin: 0;
            padding: 0;
        }
        h1 {
            color: #1a365d;
            font-size: 20pt;
            border-bottom: 2px solid #2b6cb0;
            padding-bottom: 6px;
            margin-top: 24px;
            margin-bottom: 12px;
        }
        h2 {
            color: #2b6cb0;
            font-size: 15pt;
            border-bottom: 1px solid #cbd5e0;
            padding-bottom: 4px;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        h3 {
            color: #2c5282;
            font-size: 12pt;
            margin-top: 14px;
            margin-bottom: 6px;
        }
        h4 {
            color: #4a5568;
            font-size: 11pt;
            margin-top: 10px;
            margin-bottom: 4px;
        }
        p, li {
            font-size: 10pt;
            color: #2d3748;
            margin-bottom: 6px;
        }
        ul, ol {
            margin-top: 4px;
            margin-bottom: 10px;
            padding-left: 20px;
        }
        code {
            font-family: 'Courier New', Courier, monospace;
            background-color: #edf2f7;
            color: #805ad5;
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 9.5pt;
        }
        pre {
            background-color: #f7fafc;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #4299e1;
            padding: 10px;
            margin: 10px 0;
            font-family: 'Courier New', Courier, monospace;
            font-size: 9pt;
            color: #1a202c;
        }
        blockquote {
            background-color: #ebf8ff;
            border-left: 4px solid #3182ce;
            margin: 10px 0;
            padding: 8px 14px;
            color: #2b6cb0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 14px 0;
        }
        th {
            background-color: #2b6cb0;
            color: #ffffff;
            font-weight: bold;
            padding: 6px 10px;
            border: 1px solid #cbd5e0;
            text-align: left;
            font-size: 9.5pt;
        }
        td {
            padding: 6px 10px;
            border: 1px solid #e2e8f0;
            font-size: 9.5pt;
        }
        hr {
            border: 0;
            height: 1px;
            background-color: #e2e8f0;
            margin: 20px 0;
        }
    </style>
    """

    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{css}</head><body>{html_body}</body></html>"

    # Cria app Qt para renderização
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    document = QTextDocument()
    document.setHtml(full_html)

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(output_pdf)
    printer.setPageSize(QPrinter.A4)
    printer.setPageMargins(15, 15, 15, 15, QPrinter.Millimeter)

    # Imprime para o PDF
    document.print_(printer)
    print(f"Sucesso: Documento PDF gerado em '{output_pdf}'")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(base_dir, "GUIA_TEORICO_E_TECNICO.md")
    output_file = os.path.join(base_dir, "GUIA_TEORICO_E_TECNICO.pdf")

    markdown_to_pdf(input_file, output_file)
