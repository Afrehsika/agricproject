<div align="center">
  <h1>AgriConnect Market</h1>
  <p><strong>Digital Escrow & Logistics Marketplace for Ghana's Agricultural Sector</strong></p>
  
  [![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
  [![Django](https://img.shields.io/badge/Django-4.x-092E20.svg)](https://www.djangoproject.com/)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
</div>

<br />

AgriConnect Market is a premium peer-to-peer web application designed to empower smallholder vegetable farmers, wholesale buyers, and logistics providers in Bono East (Techiman Municipal), Ghana. 

It facilitates secure transactions via **digital escrow**, calculates dynamic **logistics matchmaking**, supports **AI-driven crop disease analysis**, and provides **trust circle networking**. It even includes a standalone web simulator for testing offline **USSD** interactions!

---

## 🌟 Key Features

1. **Digital Escrow & Wallet**: Protects funds securely during the order lifecycle. Payments are held by the platform and released to farmers instantly when the buyer confirms delivery.
2. **Logistics Marketplace**: Automatic matching with transporters. Distance and pricing are estimated dynamically using Haversine formulas.
3. **Trust Circles**: Users must request and accept connections to transact, preventing fraud and building robust local networks.
4. **AI Pathology & Chatbot**: Instant simulated plant pathology checks and a context-aware chat assistant (AgriBot) built with modern layouts.
5. **Real-Time Notifications**: Fully integrated with the Arkesel SMS API and SMTP Mailers to dispatch real notifications to users.
6. **Standalone USSD Simulator**: A highly realistic, Material Design 3-inspired smartphone simulator at `/simulator/` mimicking offline USSD gateways.

---

## 📖 Documentation

Detailed guides and technical specifications have been separated into the `docs/` directory for easier reading:

- 🏗️ **[System Architecture](docs/architecture.md)** - Understand the tech stack, data models, and the Escrow lifecycle.
- 🚀 **[Setup & Deployment](docs/setup_and_deployment.md)** - Instructions for local development, `.env` API configurations, and automated testing.
- 🧑‍🌾 **[User Guide](docs/user_guide.md)** - Learn how Farmers, Buyers, and Transporters interact with the platform.
- 🔌 **[API Reference](docs/api_reference.md)** - Comprehensive REST API documentation with endpoints for Auth, Produce, Orders, and Paystack.

---

## ⚡ Quick Start

```bash
# 1. Clone the repository
cd agriproject

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Migrate the database
python manage.py migrate

# 5. Seed demo data (Profiles, Tomatoes, Logs)
python manage.py loaddata demo_fixtures.json

# 6. Start the server!
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser to view the application!

---

*For detailed setup of `.env` variables (Paystack, Arkesel SMS, Gmail), please refer to the **[Setup & Deployment Guide](docs/setup_and_deployment.md)**.*
