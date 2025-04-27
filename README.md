# 📢 Tender Tracker & Bid-Match Recommender

![Built with Python](https://img.shields.io/badge/Built%20with-Python-3776AB?logo=python&logoColor=white)
![Streamlit App](https://img.shields.io/badge/Made%20with-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

A **Streamlit web app** that **tracks government tenders**, **scrapes live tenders**, **matches them with your company profile** using AI (TF-IDF and Cosine Similarity), and **recommends the best tender opportunities** based on your services.

> **Built With:** Streamlit, Python, SQLite, BeautifulSoup, scikit-learn

---

## ✨ Features

- 🔒 **Secure Login** (Username & Password)
- 📈 **Live Tender Scraper** from [eTenders.gov.in](https://etenders.gov.in/eprocure/app)
- 🛠 **Auto Background Tender Updates** every 5 minutes
- 🧠 **AI-based Matching Engine** using TF-IDF + Cosine Similarity
- 📂 **Upload Company Profile (CSV)** with your services
- 🎯 **Tender Matching Score** shown in real-time
- 📥 **Download Matched Tenders** in CSV
- 🔄 **Auto-refresh** page every 5 minutes
- 📊 **Tender Statistics** (Total tenders, Average Match Score)

---

## 🖥 Demo

| Login Page | Main App |
|:-----------|:---------|
| ![Login Screenshot](https://via.placeholder.com/400x200?text=Login+Page) | ![Main Screenshot](https://via.placeholder.com/400x200?text=Main+App+Page) |

> (*Replace placeholder images with your real screenshots*)

---

## 🚀 Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/tender-tracker.git
   cd tender-tracker
