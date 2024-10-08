import fitz
import chardet
from docx import Document
from io import BytesIO


def detect_file_encoding(file):
    raw_data = file.read(10000)
    result = chardet.detect(raw_data)
    file.seek(0)
    return result["encoding"]


def read_file_content(file):
    file_extension = file.name.split(".")[-1].lower()
    file_name = file.name

    if file_extension == "pdf":
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text += page.get_text()
        return text, file_name
    elif file_extension == "docx":
        doc = Document(BytesIO(file.read()))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text, file_name
    else:
        file_encoding = detect_file_encoding(file)
        return file.read().decode(file_encoding), file_name
