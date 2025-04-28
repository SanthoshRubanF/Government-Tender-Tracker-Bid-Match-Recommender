# app.py
import streamlit as st
import pandas as pd
import sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pdfplumber
import re

# ---------------------------
# Database setup
# ---------------------------
conn = sqlite3.connect('tenders.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS tenders 
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT, 
    scope_of_work TEXT, 
    estimated_cost TEXT,
    emd TEXT,
    bid_submission_deadline TEXT,
    technical_bid_opening TEXT)
''')
conn.commit()

# ---------------------------
# Functions
# ---------------------------

def extract_tender_info_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()

    # Example basic extraction rules using regex
    title = re.search(r'(?i)(Providing.*?)\n', text)
    estimated_cost = re.search(r'Estimated cost:?[\s₹:]*([0-9,]+)', text)
    emd = re.search(r'EMD:?[\s₹:]*([0-9,]+)', text)
    deadline = re.search(r'Submission Deadline:? (.*?)\n', text)
    technical_opening = re.search(r'Technical Bid Opening:? (.*?)\n', text)

    extracted = {
        "title": title.group(1).strip() if title else "No Title Found",
        "scope_of_work": "Scope extracted from tender PDF",
        "estimated_cost": estimated_cost.group(1) if estimated_cost else "N/A",
        "emd": emd.group(1) if emd else "N/A",
        "bid_submission_deadline": deadline.group(1) if deadline else "N/A",
        "technical_bid_opening": technical_opening.group(1) if technical_opening else "N/A"
    }
    return extracted

def insert_tender_into_db(tender):
    c.execute('''
        INSERT INTO tenders (title, scope_of_work, estimated_cost, emd, bid_submission_deadline, technical_bid_opening)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (tender['title'], tender['scope_of_work'], tender['estimated_cost'], tender['emd'],
          tender['bid_submission_deadline'], tender['technical_bid_opening']))
    conn.commit()

def load_company_profile(uploaded_file):
    df = pd.read_csv(uploaded_file)
    services = df['services'].tolist()
    return " ".join(services)

def fetch_tenders():
    return pd.read_sql_query('SELECT * FROM tenders', conn)

def match_tenders(company_profile_text, tenders_df):
    corpus = [company_profile_text] + (tenders_df['scope_of_work'] + " " + tenders_df['title']).tolist()
    tfidf = TfidfVectorizer()
    vectors = tfidf.fit_transform(corpus)
    cosine_sim = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
    tenders_df['match_score'] = cosine_sim
    return tenders_df.sort_values(by='match_score', ascending=False)

def send_email(to_email, subject, body):
    from_email = "your_gmail@gmail.com"
    password = "your_gmail_app_password"  # Use App Password

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_email, password)
    server.send_message(msg)
    server.quit()

# ---------------------------
# Streamlit App
# ---------------------------
st.set_page_config(page_title="Tender Tracker", layout="wide")

st.title("🚀 Government Tender Tracker & Bid-Match Recommender")

# --- Upload Tender PDFs ---
st.subheader("📄 Upload Tender Notice PDFs")

uploaded_pdfs = st.file_uploader("Upload Tender PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    for pdf in uploaded_pdfs:
        tender = extract_tender_info_from_pdf(pdf)
        insert_tender_into_db(tender)
    st.success(f"✅ {len(uploaded_pdfs)} tender(s) extracted and saved!")

st.divider()

# --- Upload Company Profile ---
st.subheader("📂 Upload Company Profile")

uploaded_file = st.file_uploader("Upload Company Profile (CSV with 'services' column)", type=["csv"])

if uploaded_file:
    company_profile_text = load_company_profile(uploaded_file)
    tenders_df = fetch_tenders()
    matched_df = match_tenders(company_profile_text, tenders_df)

    st.success("✅ Company Profile Uploaded Successfully!")

    search_query = st.text_input("🔍 Search Tenders by Title or Scope")

    if search_query:
        matched_df = matched_df[matched_df['title'].str.contains(search_query, case=False) |
                                matched_df['scope_of_work'].str.contains(search_query, case=False)]

    st.metric("📄 Total Tenders Matched", len(matched_df))
    st.metric("✅ Average Match Score", f"{matched_df['match_score'].mean():.2f}")

    st.subheader("🎯 Tender Matches")
    st.dataframe(matched_df[['title', 'scope_of_work', 'match_score', 'bid_submission_deadline']])

    # Download Matched tenders
    st.download_button("📥 Download Matched Tenders", data=matched_df.to_csv(index=False),
                       file_name="matched_tenders.csv", mime="text/csv")

    # Email Notification Section
    st.subheader("📬 Send High Matches as Email Notification")
    email = st.text_input("Enter Your Email to Receive Notifications:")
    if st.button("Send Email for High Matches (>80%)"):
        high_matches = matched_df[matched_df['match_score'] > 0.80]
        if not high_matches.empty:
            body = high_matches[['title', 'scope_of_work', 'bid_submission_deadline']].to_string(index=False)
            send_email(email, "High Matching Tenders Notification", body)
            st.success(f"📨 Email Sent Successfully to {email}!")
        else:
            st.warning("⚠️ No high match tenders found (match >80%)!")

else:
    st.info("📄 Please upload your company profile CSV to start matching.")
