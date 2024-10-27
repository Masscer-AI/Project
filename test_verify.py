from api.whatsapp.actions import verify_whatsapp_number

# Example usage
if __name__ == "__main__":
    country_code = "52"
    phone_number = "17299751395"
    method = "sms"  # or "voice"
    cert = "CmcKIwjtjOCouN/kAxIGZW50OndhIgpNYXNzY2VyIEFJULes37gGGkCcj3NNqKtJH5Z2NPLHc80WtMG6MMcii/TE/Etiq6xIbwrlpGND053t5cwK3WSDA9eXpf9MB0QZ6OMzRmQTaTQKEi9tKQ2UyqeFbuBFi7CZq28gnF3h5F/M9QXxYF7wixz8uFyOf/9wBp+Sa6PveF2qqg=="
    # pin = "123456"

    result = verify_whatsapp_number(country_code, phone_number, method, cert)
    print(result)
