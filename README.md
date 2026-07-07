# AgriConnect Market - Digital Escrow & Logistics Marketplace

AgriConnect Market is a premium peer-to-peer web application designed to empower smallholder vegetable farmers, wholesale buyers, and logistics providers in Bono East (Techiman Municipal), Ghana. It facilitates secure transactions via digital escrow, calculates dynamic logistics match pricing, supports AI-driven crop disease analysis, provides trust circle networking, and simulates offline USSD marketplace interactions.

---

## Key Features

1. **Digital Escrow & Wallet**: Protects funds securely during the order lifecycle. Payments are held by the platform and released to farmers instantly when the buyer confirms delivery. Integrated with a sandbox Paystack initialization and payout flow.
2. **Logistics Marketplace**: Automatic matching with transporters. Distance and pricing are estimated using Haversine formulas.
3. **Trust Circles**: Users must request and accept connections to transact, preventing fraud and building robust local networks.
4. **AI Pathology & Chatbot**: Instant simulated plant pathology checks and a context-aware chat assistant (AgriBot) built with modern layouts.
5. **Offline USSD Simulator**: A realistic frontend widget allowing users to perform main dashboard actions offline by dialing `*920*44#`.

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Django 4.x
- SQLite

### Setup Instructions

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

4. **Setup Git Ignore**:
   A `.gitignore` file has been added to automatically exclude `venv/`, `.env`, and `db.sqlite3` from being pushed to version control, keeping your environment and database secure during GitHub uploads.

5. **Configure Environment Variables**:
   Create a `.env` file in the root directory (based on `.env.example` if available):
   ```env
   DEBUG=True
   DJANGO_SECRET_KEY=your-secret-key
   PAYSTACK_SECRET_KEY=sk_test_...
   PAYSTACK_PUBLIC_KEY=pk_test_...
   ARKESEL_API_KEY=your_arkesel_api_key
   ARKESEL_SENDER_ID=AgriConnect
   ```

6. **Run Migrations & Seed Demo Data**:
   ```bash
   python manage.py migrate
   # Seed demo profiles, tomato listings, transport jobs, and chats
   python manage.py loaddata demo_fixtures.json
   ```

7. **Start the Development Server**:
   ```bash
   python manage.py runserver
   ```
   Open `http://127.0.0.1:8000/` in your browser.

---

## User Roles & Actors

- **Buyer** (e.g., `Kumasi_Restaurant_Hub`): Purchases vegetable crops, deposits escrow funds, hires/approves drivers, and confirms final cargo delivery.
- **Farmer** (e.g., `Kofi_Mensah`): Lists crop harvests, coordinates logistics matches, dispatches orders directly, and receives payouts.
- **Transporter** (e.g., `KIA_Bongo_Kojo`): Claims logistics contracts, verifies cargo pickup, coordinates routing on the map, and delivers goods.

---

## API Reference

All requests must send the `Content-Type: application/json` header. Session authentication is CSRF-exempt under the API paths.

### 1. User Authentication & Profile

#### `POST /api/register/`
Registers a new user profile.
- **Request Body**:
  ```json
  {
    "username": "buyer_test",
    "password": "password123",
    "role": "BUYER",
    "phone_number": "0240001111",
    "region": "Bono East",
    "district": "Techiman Municipal"
  }
  ```
- **Response** (HTTP 201):
  ```json
  {
    "id": 4,
    "username": "buyer_test",
    "role": "BUYER",
    "phone_number": "0240001111",
    "region": "Bono East",
    "district": "Techiman Municipal",
    "wallet_balance": "0.00"
  }
  ```

#### `POST /api/login/`
Authenticates a user and starts a session.
- **Request Body**:
  ```json
  {
    "username": "buyer_test",
    "password": "password123"
  }
  ```
- **Response** (HTTP 200):
  ```json
  {
    "id": 4,
    "username": "buyer_test",
    "role": "BUYER",
    "wallet_balance": "0.00"
  }
  ```

#### `POST /api/logout/`
Logs out the current authenticated user and invalidates the session.

#### `GET /api/profile/`
Returns the active authenticated user profile details.

#### `GET /api/users/list/`
Lists system users. Optional query parameters: `role=BUYER` or `role=FARMER` or `role=TRANSPORTER`.

---

### 2. Trust Circle Network

#### `GET /api/connections/`
Lists accepted connections, pending incoming/outgoing request cards, and all users available to connect.

#### `POST /api/connections/request/`
Sends a new connection request to build trust circles.
- **Request Body**:
  ```json
  {
    "receiver_id": 2
  }
  ```
  *(Or provide `"phone_number": "0241112222"` instead of receiver ID)*

#### `POST /api/connections/respond/`
Accepts or rejects an incoming connection request.
- **Request Body**:
  ```json
  {
    "request_id": 5,
    "action": "accept"
  }
  ```

#### `DELETE /api/connections/delete/<int:pk>/`
Deletes an accepted connection.

---

### 3. Messaging Center

#### `GET /api/messages/chats/`
Lists all active chat channels, showing user avatars, message previews, unread counts, and connection statuses.

#### `GET /api/messages/history/<int:other_user_id>/`
Fetches the message logs with another user. Marks incoming messages as read.

#### `POST /api/messages/send/`
Sends a text message to a connection.
- **Request Body**:
  ```json
  {
    "receiver_id": 2,
    "content": "Is the Gboma Greens crop ready for dispatch?"
  }
  ```

---

### 4. Notifications & Alert Logs

#### `GET /api/notifications/`
Retrieves SMS and Email notification logs for the user. Automatically marks unread alerts as read.

#### `DELETE /api/notifications/`
Clears all notifications for the authenticated user from the database.

#### `DELETE /api/notifications/<int:pk>/`
Deletes a single notification record by ID.

---

### 5. Crop Listings (Produce)

#### `GET /api/produce/`
Lists all available produce. Filter by farmer: `/api/produce/?farmer=<farmer_id>`.

#### `POST /api/produce/create/`
Creates a new harvest listing. AI calculations automatically predict the crop freshness and rot dates based on the harvest date.
- **Request Body**:
  ```json
  {
    "name": "Tomatoes",
    "variety": "Power Rano",
    "quantity_available": 15,
    "unit": "Crates",
    "price_per_unit": "120.00",
    "harvest_date": "2026-06-18",
    "description": "Premium fresh tomatoes harvested yesterday"
  }
  ```

---

### 6. Escrow Orders & Cart

#### `GET /api/cart/`
Lists items in the buyer's active shopping cart.

#### `POST /api/cart/`
Adds or updates item quantity in the cart.
- **Request Body**:
  ```json
  {
    "produce": 1,
    "quantity": 5
  }
  ```

#### `DELETE /api/cart/<int:pk>/`
Removes a produce item from the cart.

#### `POST /api/cart/checkout/`
Converts cart items to unpaid orders, reserving produce quantities. Checks for sufficient wallet balance to pay for goods + logistics fees.

#### `POST /api/orders/create/`
Creates a single pending purchase order.
- **Request Body**:
  ```json
  {
    "produce": 1,
    "quantity": 3,
    "delivery_type": "PLATFORM_DELIVERY"
  }
  ```

#### `POST /api/orders/<int:pk>/pay/`
Pays for an order using the buyer's pre-funded platform wallet. Debits the cost of goods and the logistics fee, placing them securely in platform escrow.

#### `POST /api/orders/<int:pk>/confirm-delivery/`
Releases the escrowed payment instantly to the farmer's mobile money wallet. Also pays out the logistics fee to the transporter's wallet if a driver was assigned. Returns error details on failure.

#### `POST /api/orders/dispatch/`
Allows farmers to create a direct dispatch order for a client.
- **Request Body**:
  ```json
  {
    "produce": 1,
    "buyer": 3,
    "quantity": 5,
    "driver": 2
  }
  ```

---

### 7. Logistics & Transport Matching

#### `GET /api/logistics/jobs/`
Lists logistics jobs. Filters for transporters: `/api/logistics/jobs/?claimed=true`.

#### `POST /api/logistics/jobs/<int:pk>/claim/`
Transporters claim a delivery job. Transitions status to `PENDING_APPROVAL`.
- **Response** (HTTP 200): Returns job model data.

#### `POST /api/logistics/jobs/<int:pk>/approve/`
Buyers approve or reject a transporter's claim.
- **Request Body**:
  ```json
  {
    "action": "approve"
  }
  ```

#### `POST /api/logistics/jobs/<int:pk>/assign/`
Farmers directly hire a transporter for an order.
- **Request Body**:
  ```json
  {
    "driver": 2
  }
  ```

#### `POST /api/logistics/jobs/<int:pk>/update/`
Transporters confirm cargo status changes.
- **Request Body**:
  ```json
  {
    "status": "PICKED_UP"
  }
  ```
  *(Or `"status": "DELIVERED"`)*

---

### 8. Paystack Digital Wallet

#### `POST /api/payments/initialize/`
Initializes a Paystack top-up request.
- **Request Body**:
  ```json
  {
    "amount": 250
  }
  ```
- **Response**: Returns Paystack checkout url, unique reference, and sandbox configurations.

#### `GET /api/payments/verify/<str:reference>/`
Verifies a transaction using Paystack's endpoint. credits the user wallet upon verification.

#### `POST /api/payments/withdraw/`
Requests a payout to a mobile money account or bank account.
- **Request Body**:
  ```json
  {
    "amount": "150.00",
    "channel": "mobile_money",
    "account_number": "0241112222"
  }
  ```

#### `GET /api/payments/transactions/`
Retrieves wallet ledger transaction logs.

---

### 9. AI Pathology & AgriBot

#### `POST /api/disease-scanner/`
Uploads a simulated leaf scan request to identify plant pathology diseases automatically.
- **Request Body**:
  ```json
  {
    "crop_name": "Tomatoes"
  }
  ```
- **Response**: Returns diagnosis, confidence rate, and recommended treatment guidelines.

#### `POST /api/agribot/`
Chats with the AI expert.
- **Request Body**:
  ```json
  {
    "message": "My tomato plants have yellow leaves, what should I do?"
  }
  ```
- **Response**: Returns context-aware advice for Bono East farmers.

---

## Testing

Run the Django automated test suite:
```bash
python run_tests.py
```
This runs the full suite in `core/tests.py`, verifying authentication, inventory decay calculations, end-to-end digital escrow transfers, transporter matching, and disease diagnosis simulations.
