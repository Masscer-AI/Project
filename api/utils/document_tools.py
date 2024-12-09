import pypandoc
from api.utils.color_printer import printer


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

# Convert using PyPandoc to different formats
# The list of formats is here: https://pandoc.org/MANUAL.html#output-formats


def convert_html(input_file, output_file, to_type="docx"):
    try:
        # Convert the HTML file to DOCX
        output = pypandoc.convert_file(input_file, to_type, outputfile=output_file)
        assert output == ""
        printer.green(f"Successfully converted {input_file} to {output_file}")
    except Exception as e:
        printer.red(f"An error occurred during conversion: {e}")
