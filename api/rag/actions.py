import fitz

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
    else:
        return file.read().decode("utf-8"), file_name
