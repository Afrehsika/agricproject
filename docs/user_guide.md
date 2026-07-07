# User Guide

AgriConnect Market caters to three primary roles. The workflows are designed to enforce trust and guarantee secure payments via digital escrow.

---

## 1. The Buyer Workflow

Buyers (e.g., Restaurants, Wholesalers) use the platform to source fresh produce reliably.

1. **Top-Up Wallet**: Before buying, a buyer must fund their digital wallet via Paystack.
2. **Build Trust Circles**: Buyers send connection requests to Farmers. Only connected users can transact or chat.
3. **Browse & Order**: 
   - Buyers view available crop listings.
   - They add items to their cart.
   - During checkout, they can opt for **Platform Delivery** (auto-match a transporter) or **Self-Pickup**.
4. **Escrow Payment**: The buyer authorizes the payment. The funds are instantly deducted from their wallet but are held securely in escrow.
5. **Logistics Management**: If Platform Delivery is chosen, the buyer waits for a Transporter to claim the job. The buyer reviews the Transporter's profile and clicks **Approve**.
6. **Confirm Delivery**: Once the Transporter physically delivers the goods, the buyer clicks **Confirm Delivery**. This action releases the escrow funds to the Farmer and Transporter simultaneously.

---

## 2. The Farmer Workflow

Farmers use the platform to list harvests and guarantee they get paid upon delivery.

1. **List Produce**: Farmers input harvest details (crop name, variety, quantity, price). The system uses AI to estimate freshness decay over time.
2. **Accept Connections**: Farmers review incoming requests from Buyers and Transporters.
3. **Fulfill Orders**: 
   - Farmers prepare the cargo when an order is placed.
   - They can optionally choose to "Directly Assign" a trusted Transporter to an order instead of waiting for public matchmaking.
4. **Receive Payouts**: The moment the Buyer confirms delivery, the funds instantly hit the Farmer's wallet.
5. **Withdraw Funds**: Farmers can withdraw their wallet balance directly to their Mobile Money numbers.

---

## 3. The Transporter Workflow

Transporters (e.g., KIA Bongo trucks, Aboboyaa Tricycles) use the platform to find delivery jobs.

1. **Find Jobs**: The Logistics dashboard lists all pending deliveries near them.
2. **Claim Contract**: A Transporter claims a job. They must wait for the Buyer to approve their claim.
3. **Pickup & Transit**: 
   - Upon approval, they drive to the Farmer's location.
   - They update the system status to **PICKED_UP**.
4. **Delivery**: They deliver the goods to the Buyer. Once the Buyer confirms receipt, the Transporter's delivery fee is instantly credited to their wallet.

---

## 4. USSD Simulator (Offline Access)

Farmers who lack internet access can interact with the marketplace via USSD.

1. Navigate to `/simulator/` on your browser.
2. The UI looks like an Android phone.
3. Select a demo user from the dropdown to auto-fill their phone number.
4. Click **Connect Gateway**.
5. Dial the shortcode `*920*44#` on the simulated keypad to browse inventory, check wallet balance, or confirm pickups offline!
