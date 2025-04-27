# 📢 Government Tender Tracker & Bid-Match Recommender

![Built with Python](https://img.shields.io/badge/Built%20with-Python-3776AB?logo=python&logoColor=white)
![Streamlit App](https://img.shields.io/badge/Made%20with-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

A Streamlit web app that scrapes government tenders from the GeM portal, matches them to a company's capability profile using machine learning (TF-IDF), and recommends high-fit tenders.

> **Technologies Used:** Streamlit, Python, SQLite, BeautifulSoup, scikit-learn, TF-IDF, Cosine Similarity.

---

## ✨ Key Features

- 🔒 **Secure Login System** (Username + Password authentication)
- 🛠 **Live Tender Scraper** from [eTenders.gov.in](https://etenders.gov.in/eprocure/app)
- ⏳ **Background Auto-Update** of tenders every 5 minutes
- 🧠 **AI-Based Recommendation Engine** (TF-IDF + Cosine Similarity)
- 📂 **Upload your Company Profile** (.csv file) to match services
- 📊 **Dynamic Tender Statistics** (Total tenders, Match score averages)
- 🔍 **Tender Search & Filter** options
- 📥 **Download Matched Tenders** as CSV
- 🔄 **Auto-Refresh App** to fetch latest tenders
- 🖥 **Simple and Responsive UI** built with Streamlit

---

## 📚 How It Works

1. **Login** using secure admin credentials.
2. **Upload your company's profile** containing a list of your services (CSV format).
3. **The app automatically fetches tenders** from [eTenders.gov.in](https://etenders.gov.in/eprocure/app).
4. **Matching Engine** ranks tenders based on relevance to your company's services.
5. **Explore, search, and download** the most relevant tender opportunities!

---

## 🛠 Installation Guide

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/SanthoshRubanF/Government-Tender-Tracker-Bid-Match-Recommender.git
   cd Government-Tender-Tracker-Bid-Match-Recommender

2. **To Run in Streamlite:**

      ```bash
      https://government-tender-tracker-bid-match-recommender-iofqgmdddvsea5.streamlit.app/
