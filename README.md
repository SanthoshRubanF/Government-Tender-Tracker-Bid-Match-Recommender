# Government Tender Tracker & Bid-Match Recommender

## Overview

The **Government Tender Tracker & Bid-Match Recommender** is a web-based application built using **Streamlit** that automatically aggregates government tenders from multiple e-procurement portals (e.g., CPPP, GeM, state portals). The application allows companies to upload or link their capability profiles and receive personalized tender recommendations based on their services. The tool is designed to help organizations automate the tender tracking process, reduce manual effort, and improve the efficiency of tender matching.

---

## Features

- **Real-Time Tender Aggregation**: Aggregates tenders from multiple government portals, including **CPPP** (Central Public Procurement Portal), **GeM** (Government e-Marketplace), and a state-specific portal.
- **Automated Requirement Scanner**: Extracts key tender data such as **EMD** (Earnest Money Deposit), **bid deadlines**, and **scope of work** using libraries like `pdfplumber` and `BeautifulSoup`.
- **Company Profile Matching**: Uses **TF-IDF** or **embedding-based** similarity scoring to match tenders with company profiles and provides **high-fit recommendations**.
- **Interactive Dashboard**: Built with **Streamlit**, the dashboard allows users to:
  - View and search aggregated tenders.
  - Upload or link company capability profiles.
  - View match scores and tender details.
- **Real-Time Alerts**: Optionally, set up **email/SMS notifications** via **Twilio** or **Gmail SMTP** for real-time alerts on relevant tenders.

---

## Project Structure

