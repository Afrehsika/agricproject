# System Architecture & Design

AgriConnect Market is designed using a monolithic architecture built around the Django Web Framework. It leverages server-side rendering for its UI combined with vanilla JavaScript for dynamic interactions.

## Technology Stack

- **Backend**: Python 3.10+, Django 4.x
- **Database**: SQLite (Development)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (ES2020+)
- **Authentication**: Django Session Auth (Frontend) & OAuth2 (USSD Webhook API)
- **APIs**: Django REST Framework (DRF)
- **Integrations**: Paystack API (Payments), Arkesel API (SMS), Gmail SMTP (Email)

## Core Application Modules

The system is divided into modular Django apps:

### 1. `core`
Serves as the central router and provider of global utilities. It handles:
- The main landing page rendering.
- Test data seeding logic (`views.py`).

### 2. `users`
Handles custom user models, authentication, and communication.
- Extended `AbstractUser` to support `role`, `wallet_balance`, `latitude`, and `longitude`.
- Manages **Trust Circles** (Connections) and P2P messaging.
- Dispatch system for **Notifications** (SMS/Email).

### 3. `produce`
Manages the inventory listings.
- `Produce` models tracking quantity, price, and harvest date.
- AI decay estimation logic to dynamically calculate crop freshness.

### 4. `orders`
Handles the e-commerce lifecycle.
- Cart functionality and checkout logic.
- **Digital Escrow**: Order payments are reserved in platform wallets until delivery confirmation.

### 5. `logistics`
Manages the transport matchmaking.
- `TransportJob` models linking Farmers/Buyers to Transporters.
- Dynamic route distance calculations using Haversine formulas.
- Status workflows (`PENDING_APPROVAL` -> `PICKED_UP` -> `DELIVERED`).

### 6. `payments`
Manages the digital wallet ledger and Paystack integration.
- Top-up flows via Paystack checkout.
- Withdrawal requests.
- Transaction histories.

### 7. `ai`
Provides specialized artificial intelligence features.
- Plant pathology image scanning.
- AgriBot conversational AI assistant.

---

## Data Flow: The Escrow Lifecycle

1. **Listing**: Farmer lists Produce.
2. **Order**: Buyer adds to cart and checks out.
3. **Payment**: Buyer's wallet is debited. Funds move to the Platform Escrow ledger.
4. **Logistics**: A Transporter claims the delivery and is approved.
5. **Fulfillment**: Transporter delivers the goods. Buyer clicks "Confirm Delivery".
6. **Payout**: The Escrow automatically splits the funds—crediting the Farmer for the goods, and the Transporter for the delivery fee.
