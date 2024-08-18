import streamlit as st
import PyPDF2
import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def extract_text_from_pdf(file):
    text = ""
    pdf_reader = PyPDF2.PdfReader(file)
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"  # Add newline to separate pages
    return text

def split_questions(text):
    modules = text.split("Module –")
    module_texts = []
    for i in range(1, len(modules)):
        module_texts.append("Module –" + modules[i].strip())
    return module_texts

def query_groq_api(text):
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise ValueError("API key not found.")

    endpoint = "https://api.groq.com/openai/v1/chat/completions"  
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You should answer the questions given in the text. Exaggerate it enough so that single answer has more than 200-500 words."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "model": "llama3-8b-8192"  # Model for Groq
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.text}")
    except Exception as err:
        print(f"Other error occurred: {err}")

def display_human_readable_response(result):
    if 'choices' in result:
        for choice in result['choices']:
            if 'message' in choice and 'content' in choice['message']:
                st.write(choice['message']['content'])

def main():
    st.title("PDF Question Paper Analyzer")

    uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

    if uploaded_file:
        # Extract text from the uploaded PDF
        text = extract_text_from_pdf(uploaded_file)

        # Option to expand or collapse extracted text
        with st.expander("Extracted Text", expanded=False):
            st.text_area("Extracted Text", text, height=300)

        # Split the text by modules
        modules = split_questions(text)

        if st.button("Analyze"):
            responses = []
            with st.spinner("Analyzing..."):
                for i, module_text in enumerate(modules, start=1):
                    result = query_groq_api(module_text)
                    if result:
                        responses.append(result)
                        st.subheader(f"Module {i} Response")
                        display_human_readable_response(result)

if __name__ == "__main__":
    main()
