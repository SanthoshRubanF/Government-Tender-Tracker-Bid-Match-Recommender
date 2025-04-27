# app.py
import streamlit as st
import pandas as pd
import sqlite3
import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import re
import time
import threading
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import hashlib
from streamlit.runtime.scriptrunner import RerunException

# --- CONFIG ---
st.set_page_config(page_title="Tender Tracker", page_icon="📢", layout="wide")

# --- DB Setup ---
conn = sqlite3.connect('tenders.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS tenders 
             (id INTEGER PRIMARY KEY, title TEXT, description TEXT, emd TEXT, deadline TEXT)''')
conn.commit()

# --- Scraper ---
def fetch_cppt_tenders():
    url = "https://etenders.gov.in/eprocure/app"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    tenders = []

    # Simple demo: get all anchor tags containing 'Tender' word
    for link in soup.find_all('a', href=True):
        title = link.text.strip()
        if "tender" in title.lower():
            tenders.append({
                "title": title,
                "description": "Sample Description",
                "emd": "N/A",
                "deadline": "N/A"
            })
    return tenders

def save_to_db(tenders):
    for tender in tenders:
        c.execute("INSERT INTO tenders (title, description, emd, deadline) VALUES (?, ?, ?, ?)",
                  (tender['title'], tender['description'], tender['emd'], tender['deadline']))
    conn.commit()

# --- Background Fetch ---
def background_scraper():
    while True:
        tenders = fetch_cppt_tenders()
        save_to_db(tenders)
        print("Updated tenders...")
        time.sleep(300)  # 5 mins

# --- Password Authentication ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(input_password, hashed_password):
    return hash_password(input_password) == hashed_password

USERNAME = "admin"
PASSWORD_HASH = hash_password("1234")  # password = 1234

# --- Profile Matcher ---
def load_company_profile(uploaded_file):
    df = pd.read_csv(uploaded_file)
    services = df['services'].tolist()
    return " ".join(services)

def fetch_tenders_from_db():
    df = pd.read_sql_query("SELECT * FROM tenders", conn)
    return df

def match_tenders(profile_text, tenders_df):
    corpus = [profile_text] + tenders_df['title'].tolist()
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform(corpus)
    cosine_sim = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
    tenders_df['match_score'] = cosine_sim
    return tenders_df.sort_values(by='match_score', ascending=False)

# --- Streamlit App ---

# --- Auto Refresh ---
def auto_refresh():
    time.sleep(300)
    raise RerunException()

auto_refresh()

# --- Start Background Scraper ---
if 'bg_thread' not in st.session_state:
    thread = threading.Thread(target=background_scraper, daemon=True)
    thread.start()
    st.session_state.bg_thread = thread

# --- Login Page ---
st.title("🔒 Tender Tracker Login")
with st.form("login_form"):
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    submitted = st.form_submit_button("Login")

if submitted:
    if username == USERNAME and check_password(password, PASSWORD_HASH):
        st.session_state['logged_in'] = True
    else:
        st.error("Invalid credentials")

# --- Main App if Logged In ---
if st.session_state.get('logged_in'):

    st.title("📢 Government Tender Tracker & Bid-Match Recommender")

    tab1, tab2 = st.tabs(["📋 Tenders", "📂 Upload Profile"])

    with tab2:
        uploaded_file = st.file_uploader("Upload your Company Profile (CSV with 'services' column)", type=["csv"])

    with tab1:
        search_query = st.text_input("🔍 Search Tenders by Title")

        if uploaded_file:
            profile_text = load_company_profile(uploaded_file)
            tenders_df = fetch_tenders_from_db()
            matched_df = match_tenders(profile_text, tenders_df)

            if search_query:
                matched_df = matched_df[matched_df['title'].str.contains(search_query, case=False)]

            col1, col2 = st.columns(2)
            with col1:
                st.metric("📄 Total Tenders", len(matched_df))
            with col2:
                st.metric("✅ Average Match Score", f"{matched_df['match_score'].mean():.2f}")

            st.subheader("🎯 Top Matched Tenders")
            st.dataframe(matched_df[['title', 'match_score']])

            st.download_button("📥 Download Matched Tenders", data=matched_df.to_csv(index=False), file_name="matched_tenders.csv", mime="text/csv")
        else:
            st.info("📂 Please upload your company profile to start matching.")

