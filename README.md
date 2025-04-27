# 🚀 Government Tender Tracker & Bid-Match Recommender

## Overview

The **Government Tender Tracker & Bid-Match Recommender** is a web-based application built using **Streamlit** that automatically aggregates government tenders from multiple e-procurement portals (e.g., CPPP, GeM, state portals). The application allows companies to upload or link their capability profiles and receive personalized tender recommendations based on their services. The tool is designed to help organizations automate the tender tracking process, reduce manual effort, and improve the efficiency of tender matching.
---

## 📌 Key Features
- 🔎 Real-time tender scraping (GeM Portal)
- 🧠 Smart tender matching with TF-IDF similarity
- 📬 Email notifications for high matches (>80%)
- 📈 Download matched tenders as CSV
- 🎯 Simple interactive dashboard (Streamlit)

---

## 🛠️ Tech Stack
- Python 3, Streamlit
- BeautifulSoup4 (Scraping)
- Scikit-learn (TF-IDF, Cosine Similarity)
- Pandas, Requests
- Gmail SMTP (Email Alerts)

---

## ⚙️ Setup Instructions
```bash
# Clone the repository
git clone https://github.com/SanthoshRubanF/Government-Tender-Tracker-Bid-Match-Recommender.get
cd Government-Tender-Tracker-Bid-Match-Recommender

# To view in Streamlit
https://government-tender-tracker-bid-match-recommender-iofqgmdddvsea5.streamlit.app/
