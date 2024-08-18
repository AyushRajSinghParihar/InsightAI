import streamlit as st
import PyPDF2
import requests
import os
from dotenv import load_dotenv
import re
import sqlite3

# Load environment variables from .env file
load_dotenv()

# SQLite database setup
def create_database():
    conn = sqlite3.connect('responses.db')
    c = conn.cursor()
    # Ensure the table includes the subject_code column
    c.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_code TEXT,
            module TEXT,
            response TEXT
        )
    ''')
    conn.commit()
    conn.close()

def store_response(subject_code, module, response):
    conn = sqlite3.connect('responses.db')
    c = conn.cursor()
    c.execute("INSERT INTO responses (subject_code, module, response) VALUES (?, ?, ?)", (subject_code, module, response))
    conn.commit()
    conn.close()

def get_existing_responses(subject_code, module):
    conn = sqlite3.connect('responses.db')
    c = conn.cursor()
    c.execute("SELECT response FROM responses WHERE subject_code = ? AND module = ?", (subject_code, module))
    rows = c.fetchall()
    conn.close()
    return rows

def extract_subject_code(text):
    # Assuming the subject code is the first 6 characters of the text
    match = re.match(r'\b[A-Z]{3}\d{3}\b', text)
    return match.group(0) if match else ""

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

def format_matrix_latex(matrix_text):
    matrix_text = matrix_text.replace('|', '')
    rows = matrix_text.strip().split('\n')
    formatted_rows = []
    for row in rows:
        elements = row.split()
        formatted_row = ' & '.join(elements)
        formatted_rows.append(formatted_row)
    latex_matrix = '\\begin{bmatrix} ' + ' \\\\ '.join(formatted_rows) + ' \\end{bmatrix}'
    return latex_matrix

def display_human_readable_response(result, module_text, subject_code):
    if 'choices' in result:
        for choice in result['choices']:
            if 'message' in choice and 'content' in choice['message']:
                content = choice['message']['content']
                
                # Find and replace matrices in content
                pattern = re.compile(r'\|[^\|]+\|')
                content = pattern.sub(lambda x: f'$$ {format_matrix_latex(x.group())} $$', content)
                
                st.markdown(content, unsafe_allow_html=True)
                
                # Store the response in the SQLite database
                store_response(subject_code, module_text, content)

def main():
    create_database()  # Initialize the database when the app starts

    st.title("InsightAI")

    # Guidelines section
    st.markdown("""
    **Few things to keep in mind:**
    1. **DON'T USE THIS WHEN YOU HAVE NOTES:** Use this when you don't have proper notes (for e.g. when the subject is new). If your teacher has provided notes, please study that.
    2. **Only VTU Model papers for now:** For now, this only supports VTU official model papers. It won't support scanned question paper. Use the ones you get from the official website.
    3. **Not perfect:** Repeating point number 1, this HAS issues. Don't completely rely on this. This cannot answer questions which have diagrams and photos.
    4. **To get answer:** Upload the PDF, click on Analyze and it should scan our database if the question paper has been already answered. If you're not satisfied with that answer, click on Analyze Again so that the request goes to the Groq (alternative to ChatGPT) API and you get a new answer. Press Ctrl+P, and select print to PDF to get a PDF file of the answers (I'm too lazy to add a print button, sorry). 
    5. **My contact:**
        [LinkedIn ](https://www.linkedin.com/in/ayushraj-parihar-01a937267/) | 
        [ Instagram ](https://www.instagram.com/ayushrajsinghparihar) | 
        [ Email ](mailto:ayushrajparihar222sp@gmail.com) | 
         Reach out if you have any suggestions.
    """)


    uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

    if uploaded_file:
        # Extract text from the uploaded PDF
        text = extract_text_from_pdf(uploaded_file)
        
        # Extract subject code from the text
        subject_code = extract_subject_code(text)
        st.write(f"Subject Code Extracted: {subject_code}")

        # Option to expand or collapse extracted text
        with st.expander("Extracted Text", expanded=False):
            st.text_area("Extracted Text", text, height=300)

        # Split the text by modules
        modules = split_questions(text)

        analyze = st.button("Analyze")
        analyze_again = st.button("Analyze Again")

        if analyze:
            responses = []
            with st.spinner("Analyzing..."):
                for i, module_text in enumerate(modules, start=1):
                    # Check if the response already exists in the database
                    existing_responses = get_existing_responses(subject_code, module_text)
                    
                    if existing_responses:
                        st.subheader(f"Module {i} Response")
                        for response in existing_responses:
                            st.markdown(response[0], unsafe_allow_html=True)
                    else:
                        result = query_groq_api(module_text)
                        if result:
                            responses.append(result)
                            st.subheader(f"Module {i} Response")
                            display_human_readable_response(result, module_text, subject_code)

        if analyze_again:
            responses = []
            with st.spinner("Analyzing Again..."):
                for i, module_text in enumerate(modules, start=1):
                    result = query_groq_api(module_text)
                    if result:
                        responses.append(result)
                        st.subheader(f"Module {i} Response")
                        display_human_readable_response(result, module_text, subject_code)

if __name__ == "__main__":
    main()
