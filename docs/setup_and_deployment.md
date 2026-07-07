# Setup & Deployment Guide

This guide covers local development setup and how to configure third-party credentials (like real Email and SMS).

## Local Development Setup

### Prerequisites
- Python 3.10+
- Django 4.x
- SQLite

### Step-by-Step Installation

1. **Clone the repository and enter the directory**:
   ```bash
   cd agriproject
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows (CMD/PowerShell)
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Migrations**:
   ```bash
   python manage.py migrate
   ```

5. **Start the Development Server**:
   ```bash
   python manage.py runserver
   ```
   Open `http://127.0.0.1:8000/` in your browser.

---

## Configuring Environment Variables (`.env`)

For production, or to test real functionality locally, you must create a `.env` file at the root of your project.

### 1. Core Django Settings
```env
DEBUG=True
DJANGO_SECRET_KEY=your-secure-secret-key
```
*(In production, ensure `DEBUG=False`)*

### 2. Real Email Configuration (SMTP)
By default, emails are logged to the console. To send real emails (e.g., using a Gmail account), add the following to your `.env`:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=AgriConnect Ghana <your_email@gmail.com>
```
*Note: For Gmail, you must generate a 16-digit "App Password" from your Google Account Security settings.*

### 3. Real SMS Configuration (Arkesel)
The platform integrates natively with the Arkesel SMS Gateway in Ghana.
```env
ARKESEL_API_KEY=your_arkesel_api_key_here
ARKESEL_SENDER_ID=YourApprovedSenderID
```
*Note: Your Sender ID must be approved on your Arkesel dashboard. If you use an unverified Sender ID, the API will reject the request with a 422 error.*

### 4. Paystack Payments (Digital Wallet)
To enable real digital wallet top-ups:
```env
PAYSTACK_SECRET_KEY=sk_test_...
PAYSTACK_PUBLIC_KEY=pk_test_...
```

---

## Automated Testing

To ensure the system is stable before deployment, run the automated test suite:
```bash
python run_tests.py
```
This runs the full suite in `core/tests.py`, verifying authentication, inventory decay calculations, end-to-end digital escrow transfers, transporter matching, and disease diagnosis simulations.
