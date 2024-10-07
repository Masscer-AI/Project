import fitz

import chardet


def detect_file_encoding(file):
    raw_data = file.read(10000)  # Read the first 10,000 bytes
    result = chardet.detect(raw_data)
    file.seek(0)  # Reset file pointer to the beginning
    return result["encoding"]


def read_file_content(file):
    # Detect encoding
    file_encoding = detect_file_encoding(file)
    print(f"Detected encoding: {file_encoding}")

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
        return file.read().decode(file_encoding), file_name
