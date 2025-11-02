import streamlit as st
import google.generativeai as genai
import io
import PyPDF2
import gspread
import json

def get_gemini_model(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-pro')

def get_file_content(uploaded_file):
    file_type = uploaded_file.type
    if "text" in file_type or "markdown" in file_type:
        return uploaded_file.getvalue().decode("utf-8")
    elif "pdf" in file_type:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.getvalue()))
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            text += pdf_reader.pages[page_num].extract_text()
        return text
    else:
        return "Unsupported file type."

def save_to_google_sheet(data, sheet_name, worksheet_name, credentials_json):
    try:
        gc = gspread.service_account_from_dict(credentials_json)
        sh = gc.open(sheet_name)
        worksheet = sh.worksheet(worksheet_name)
        worksheet.append_row(data)
        st.success(f"Data saved to Google Sheet '{sheet_name}' (worksheet '{worksheet_name}')")
    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")

def main():
    st.title("Chatbot for Document Q&A and Statistical Analysis")

    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = ""
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "document_content" not in st.session_state:
        st.session_state["document_content"] = ""
    if "google_sheet_credentials" not in st.session_state:
        st.session_state["google_sheet_credentials"] = None

    # Gemini API Key input
    gemini_api_key = st.text_input("Enter your Gemini API Key", type="password", value=st.session_state["gemini_api_key"])
    if gemini_api_key:
        st.session_state["gemini_api_key"] = gemini_api_key
        st.success("Gemini API Key set!")
    else:
        st.warning("Please enter your Gemini API Key to proceed.")
        return

    # Google Sheet Credentials
    st.sidebar.subheader("Google Sheet Integration")
    credentials_file = st.sidebar.file_uploader("Upload Google Service Account Key (JSON)", type=["json"])
    if credentials_file:
        st.session_state["google_sheet_credentials"] = json.load(credentials_file)
        st.sidebar.success("Google Sheet credentials loaded!")
    else:
        st.sidebar.info("Upload a service account key JSON for Google Sheet integration. Instructions: https://docs.gspread.org/en/latest/oauth2setup.html#service-account")

    google_sheet_name = st.sidebar.text_input("Google Sheet Name", value="")
    analysis_worksheet_name = st.sidebar.text_input("Analysis Worksheet Name", value="Analysis")
    questions_worksheet_name = st.sidebar.text_input("Questions Worksheet Name", value="Questions")

    # File uploader
    uploaded_file = st.file_uploader("Upload a document", type=["txt", "md", "pdf"])

    if uploaded_file and st.session_state["document_content"] == "":
        with st.spinner("Processing file..."):
            st.session_state["document_content"] = get_file_content(uploaded_file)
            if st.session_state["document_content"] != "Unsupported file type.":
                try:
                    model = get_gemini_model(st.session_state["gemini_api_key"])
                    response = model.generate_content(f"Summarize the following document:\n\n{st.session_state['document_content']}")
                    st.subheader("Document Summary:")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"Error summarizing document: {e}")
            else:
                st.error(st.session_state["document_content"])

    if st.session_state["document_content"]:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Propose Statistical Analysis"):
                with st.spinner("Generating statistical analysis proposals..."):
                    try:
                        model = get_gemini_model(st.session_state["gemini_api_key"])
                        response = model.generate_content(f"Based on the following document content, propose relevant statistical analysis methods and why they are suitable:\n\n{st.session_state['document_content']}")
                        st.subheader("Statistical Analysis Proposals:")
                        st.write(response.text)
                        if st.session_state["google_sheet_credentials"] and google_sheet_name and analysis_worksheet_name:
                            save_to_google_sheet([uploaded_file.name, "Analysis Proposal", response.text], google_sheet_name, analysis_worksheet_name, st.session_state["google_sheet_credentials"])
                    except Exception as e:
                        st.error(f"Error generating statistical analysis proposals: {e}")
        with col2:
            if st.button("Generate Quiz"):
                with st.spinner("Generating quiz..."):
                    try:
                        model = get_gemini_model(st.session_state["gemini_api_key"])
                        response = model.generate_content(f"Generate a multiple-choice quiz with answers based on the following document content:\n\n{st.session_state['document_content']}")
                        st.subheader("Quiz:")
                        st.write(response.text)
                    except Exception as e:
                        st.error(f"Error generating quiz: {e}")

        st.subheader("Ask a question about the document or statistical analysis:")
        user_question = st.text_input("Your question:")

        if user_question:
            model = get_gemini_model(st.session_state["gemini_api_key"])
            chat = model.start_chat(history=st.session_state["chat_history"])
            
            try:
                response = chat.send_message(f"Document content: {st.session_state['document_content']}\n\nUser question: {user_question}")
                st.session_state["chat_history"].append({"role": "user", "parts": [user_question]})
                st.session_state["chat_history"].append({"role": "model", "parts": [response.text]})
                if st.session_state["google_sheet_credentials"] and google_sheet_name and questions_worksheet_name:
                    save_to_google_sheet([uploaded_file.name, user_question, response.text], google_sheet_name, questions_worksheet_name, st.session_state["google_sheet_credentials"])
            except Exception as e:
                st.error(f"Error communicating with Gemini: {e}")

            for message in st.session_state["chat_history"]:
                with st.chat_message(message["role"]):
                    st.markdown(message["parts"][0])

if __name__ == "__main__":
    main()
