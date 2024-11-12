import pypandoc

def convert_md_to_docx(input_file, output_file):
    try:
        # Convert the Markdown file to DOCX
        output = pypandoc.convert_file(input_file, "docx", outputfile=output_file)
        assert output == ""
        print(f"Successfully converted {input_file} to {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

# # Example usage for Markdown
# input_markdown_file = "example.md"  # Path to your Markdown file
# output_docx_file = "output.docx"    # Desired output path for the DOCX file
# # convert_md_to_docx(input_markdown_file, output_docx_file)

def convert_md_to_pdf(input_file, output_file):
    try:
        # Convert the Markdown file to PDF
        output = pypandoc.convert_file(input_file, "pdf", outputfile=output_file)
        assert output == ""
        print(f"Successfully converted {input_file} to {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

# # Example usage for PDF
# output_pdf_file = "output.pdf"       # Desired output path for the PDF file
# # convert_md_to_pdf(input_markdown_file, output_pdf_file)

def convert_html_to_docx(input_file, output_file):
    try:
        # Convert the HTML file to DOCX
        output = pypandoc.convert_file(input_file, "docx", outputfile=output_file)
        assert output == ""
        print(f"Successfully converted {input_file} to {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

# # Example usage for HTML
# input_html_file = "example.html"     # Path to your HTML file
# output_docx_file_html = "output_from_html.docx"  # Desired output path for the DOCX file
# convert_html_to_docx(input_html_file, output_docx_file_html)
