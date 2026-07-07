// AgriConnect Ghana Application Client Logic

let currentUser = null;
let currentTab = 'marketplace';
let map = null;
let activeChatPartnerId = null;
let chatPollingInterval = null;
let notificationPollingInterval = null;
let seenNotificationIds = new Set();
let discoverUsersCache = []; // Cache to store explore users for local client-side search filtering
let mapMarkers = [];
let routingLine = null;
let ussdState = {
    active: false,
    menu: 'dial',
    inputField: '',
    tempData: {}
};

// Available Mock Users for Demo Role Switching
const demoUsers = [
    { username: 'Kofi_Mensah', role: 'FARMER', phone: '0241112222' },
    { username: 'Kumasi_Restaurant_Hub', role: 'BUYER', phone: '0247778888' },
    { username: 'KIA_Bongo_Kojo', role: 'TRANSPORTER', phone: '0248889999' }
];

document.addEventListener('DOMContentLoaded', () => {

    
    const searchInput = document.getElementById('logistics-board-search');
    if (searchInput) {
        let typingTimer;
        searchInput.addEventListener('input', () => {
            clearTimeout(typingTimer);
            typingTimer = setTimeout(loadLogisticsJobs, 500);
        });
    }

    initApp();
    setupEventListeners();
});

// Initialize Application
async function initApp() {
    initMap();
    setupLoginHandlers();
    
    // Check if user is logged in
    try {
        const res = await fetch('/api/profile/');
        if (res.ok) {
            currentUser = await res.json();
            showDashboard();
        } else {
            showLoginPortal();
        }
    } catch (e) {
        console.error("App init error: ", e);
        showLoginPortal();
    }
}

// Setup Maps
function initMap() {
    if (map) return;
    
    // Center of Techiman (Bono East capital)
    map = L.map('supply-map', {
        zoomControl: true,
        scrollWheelZoom: false
    }).setView([7.5848, -1.9392], 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
}

function showDashboard() {
    document.getElementById('login-portal').style.display = 'none';
    document.getElementById('app-container').style.display = 'flex';
    updateUIForUser();
    
    // Trigger map redraw to ensure leaflet loads container correctly once display is block
    if (map) {
        setTimeout(() => {
            map.invalidateSize();
        }, 100);
    }
    
    // Load default tab by role
    if (currentUser.role === 'TRANSPORTER') {
        switchTab('logistics');
    } else {
        switchTab('marketplace');
    }

    // Start background polling for unread messages and chats
    pollMessages();
    if (!chatPollingInterval) {
        chatPollingInterval = setInterval(pollMessages, 4000);
    }

    // Start background polling for notifications
    pollNotifications();
    if (!notificationPollingInterval) {
        notificationPollingInterval = setInterval(pollNotifications, 5000);
    }
}

function showLoginPortal() {
    document.getElementById('login-portal').style.display = 'flex';
    document.getElementById('app-container').style.display = 'none';
    currentUser = null;
    
    // Clear chat polling interval
    if (chatPollingInterval) {
        clearInterval(chatPollingInterval);
        chatPollingInterval = null;
    }

    // Clear notifications polling interval
    if (notificationPollingInterval) {
        clearInterval(notificationPollingInterval);
        notificationPollingInterval = null;
    }
    
    // Reset seen notifications cache
    seenNotificationIds.clear();
}

function setupLoginHandlers() {
    const tabLogin = document.getElementById('tab-btn-login');
    const tabRegister = document.getElementById('tab-btn-register');
    const formLogin = document.getElementById('login-form');
    const formRegister = document.getElementById('register-form');

    if (tabLogin && tabRegister) {
        tabLogin.addEventListener('click', () => {
            tabLogin.classList.add('active');
            tabRegister.classList.remove('active');
            formLogin.style.display = 'block';
            formRegister.style.display = 'none';
        });

        tabRegister.addEventListener('click', () => {
            tabRegister.classList.add('active');
            tabLogin.classList.remove('active');
            formRegister.style.display = 'block';
            formLogin.style.display = 'none';
        });
    }

    if (formLogin) {
        formLogin.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;

            try {
                const res = await fetch('/api/login/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });

                if (res.ok) {
                    currentUser = await res.json();
                    formLogin.reset();
                    showDashboard();
                } else {
                    const err = await res.json();
                    alert("Login failed: " + (err.detail || JSON.stringify(err)));
                }
            } catch (err) {
                console.error(err);
                alert("Error connecting to login server.");
            }
        });
    }

    if (formRegister) {
        formRegister.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('reg-username').value;
            const password = document.getElementById('reg-password').value;
            const role = document.getElementById('reg-role').value;
            const phone = document.getElementById('reg-phone').value;
            const region = document.getElementById('reg-region').value;
            const district = document.getElementById('reg-district').value;

            try {
                const res = await fetch('/api/register/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username,
                        password,
                        role,
                        phone_number: phone,
                        region,
                        district,
                        latitude: 7.5848 + (Math.random() - 0.5) * 0.05,
                        longitude: -1.9392 + (Math.random() - 0.5) * 0.05
                    })
                });

                if (res.ok) {
                    currentUser = await res.json();
                    formRegister.reset();
                    showDashboard();
                } else {
                    const err = await res.json();
                    alert("Registration failed: " + JSON.stringify(err));
                }
            } catch (err) {
                console.error(err);
                alert("Error connecting to registration server.");
            }
        });
    }

    // Quick Demo Logins
    const btnFarmer = document.getElementById('demo-login-farmer');
    const btnBuyer = document.getElementById('demo-login-buyer');
    const btnTransporter = document.getElementById('demo-login-transporter');

    if (btnFarmer) btnFarmer.onclick = () => quickDemoLogin('Kofi_Mensah');
    if (btnBuyer) btnBuyer.onclick = () => quickDemoLogin('Kumasi_Restaurant_Hub');
    if (btnTransporter) btnTransporter.onclick = () => quickDemoLogin('KIA_Bongo_Kojo');
}

async function quickDemoLogin(username) {
    try {
        let success = await autoLoginDemoUser(username);
        if (!success) {
            // Demo profile not found, try to auto-seed
            console.log("Quick demo profile login failed, attempting to auto-seed database...");
            const seedRes = await fetch('/api/seed/', { method: 'POST' });
            if (seedRes.ok) {
                // Retry login after seeding
                success = await autoLoginDemoUser(username);
            }
        }
        
        if (success) {
            showDashboard();
        } else {
            alert("Login failed: Unable to authenticate or auto-seed demo profiles.");
        }
    } catch (e) {
        console.error(e);
    }
}

// Auto Login Demo User
async function autoLoginDemoUser(username) {
    try {
        const res = await fetch('/api/login/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: username, password: 'password123' })
        });
        
        if (res.ok) {
            currentUser = await res.json();
            updateUIForUser();
            return true;
        }
    } catch (e) {
        console.error("Auto login error: ", e);
    }
    return false;
}

// Update UI depending on current logged in user
function updateUIForUser() {
    if (!currentUser) return;
    
    document.getElementById('logged-username').textContent = currentUser.username;
    
    // Set modern welcome hero details
    const heroUser = document.getElementById('hero-username');
    if (heroUser) {
        heroUser.textContent = currentUser.username.replace(/_/g, ' ');
    }
    const heroWallet = document.getElementById('hero-wallet-balance-mock');
    if (heroWallet) {
        heroWallet.textContent = parseFloat(currentUser.wallet_balance).toFixed(2);
    }
    const headerDate = document.getElementById('header-date');
    if (headerDate) {
        headerDate.textContent = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
    }

    document.getElementById('logged-role').textContent = currentUser.role.charAt(0) + currentUser.role.slice(1).toLowerCase();
    document.getElementById('header-wallet-balance').textContent = parseFloat(currentUser.wallet_balance).toFixed(2);
    
    // Fund/Withdraw visibility
    const fundBtn = document.getElementById('sidebar-fund-btn');
    const withdrawBtn = document.getElementById('sidebar-withdraw-btn');
    if (fundBtn) fundBtn.style.display = 'block';
    if (withdrawBtn) {
        if (currentUser.role === 'FARMER' || currentUser.role === 'TRANSPORTER' || currentUser.role === 'BUYER') {
            withdrawBtn.style.display = 'block';
        } else {
            withdrawBtn.style.display = 'none';
        }
    }

    // Trigger cart badge loading
    updateCartBadge();

    // Get navigation elements
    const navMarket = document.getElementById('nav-marketplace');
    const navFarmer = document.getElementById('nav-farmer-listings');
    const navOrders = document.getElementById('nav-orders');
    const navLogistics = document.getElementById('nav-logistics');
    const navDisease = document.getElementById('nav-disease-scanner');
    const navNetwork = document.getElementById('nav-network');
    const navMessages = document.getElementById('nav-messages');
    const navAnalytics = document.getElementById('nav-analytics');
    
    const logisticsSpan = document.querySelector('#nav-logistics span');
    
    // Connections and messages are available to everyone
    if (navNetwork) navNetwork.style.display = 'flex';
    if (navMessages) navMessages.style.display = 'flex';

    if (currentUser.role === 'FARMER') {
        if (navMarket) navMarket.style.display = 'flex';
        if (navFarmer) navFarmer.style.display = 'flex';
        if (navOrders) navOrders.style.display = 'flex';
        if (navLogistics) navLogistics.style.display = 'flex';
        if (logisticsSpan) logisticsSpan.textContent = 'Logistics & Dispatch';
        if (navDisease) navDisease.style.display = 'flex';
        if (navAnalytics) navAnalytics.style.display = 'flex';
        
        // Default harvest dates for listing form safely guarded
        const harvestDateInput = document.getElementById('produce-harvest-date');
        if (harvestDateInput) {
            harvestDateInput.value = new Date().toISOString().split('T')[0];
        }
    } else if (currentUser.role === 'TRANSPORTER') {
        if (navMarket) navMarket.style.display = 'flex';
        if (navFarmer) navFarmer.style.display = 'none';
        if (navOrders) navOrders.style.display = 'none';
        if (navLogistics) navLogistics.style.display = 'flex';
        if (logisticsSpan) logisticsSpan.textContent = 'Logistics Jobs';
        if (navDisease) navDisease.style.display = 'none';
        if (navAnalytics) navAnalytics.style.display = 'flex';
    } else if (currentUser.role === 'BUYER') {
        if (navMarket) navMarket.style.display = 'flex';
        if (navFarmer) navFarmer.style.display = 'none';
        if (navOrders) navOrders.style.display = 'flex';
        if (navLogistics) navLogistics.style.display = 'none';
        if (navDisease) navDisease.style.display = 'none';
        if (navAnalytics) navAnalytics.style.display = 'flex';
    }

    // Fetch real orders to populate Items Sold / Items Bought dynamically with live sync
    fetch('/api/orders/create/')
        .then(res => res.ok ? res.json() : [])
        .then(orders => {
            const sidebarSalesLabel = document.getElementById('sidebar-sales-label');
            const sidebarSalesValue = document.getElementById('sidebar-sales-value');
            const heroSalesLabel = document.getElementById('hero-sales-label');
            const heroSalesValue = document.getElementById('hero-sales-value');
            const heroSalesTrend = document.getElementById('hero-sales-trend');

            let label = "Items Sold";
            if (currentUser.role === 'BUYER') {
                label = "Items Bought";
            } else if (currentUser.role === 'TRANSPORTER') {
                label = "Jobs Completed";
            }

            // Calculate total quantity of items sold or bought across all orders
            const totalQuantity = orders.reduce((sum, order) => sum + parseInt(order.quantity || 0), 0);
            
            // Format suffix (e.g. "5 Baskets" or "10 Crates", fallback to "Crops")
            let unitSuffix = "Crops";
            if (orders.length > 0) {
                const firstOrder = orders[0];
                if (firstOrder.produce_details && firstOrder.produce_details.unit) {
                    unitSuffix = firstOrder.produce_details.unit;
                }
            }

            const valueText = `${totalQuantity} ${unitSuffix}`;

            if (sidebarSalesLabel) sidebarSalesLabel.textContent = label;
            if (sidebarSalesValue) sidebarSalesValue.textContent = valueText;
            if (heroSalesLabel) heroSalesLabel.textContent = label;
            if (heroSalesValue) heroSalesValue.textContent = valueText;
            if (heroSalesTrend) {
                heroSalesTrend.innerHTML = `<i class="fa-solid fa-circle-check"></i> Live Sync (${orders.length} orders)`;
            }
        })
        .catch(err => console.error("Error fetching order stats:", err));
}

// Event Listeners
function setupEventListeners() {
    // Logout button handler
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/logout/', { method: 'POST' });
                if (res.ok) {
                    showLoginPortal();
                }
            } catch (e) {
                console.error(e);
                showLoginPortal();
            }
        });
    }

    // Sidebar navigation
    document.querySelectorAll('.sidebar-menu .menu-item').forEach(item => {
        item.addEventListener('click', () => {
            const tabName = item.getAttribute('data-tab');
            switchTab(tabName);
        });
    });

    // Seed Demo Data button
    document.getElementById('seed-demo-btn').addEventListener('click', async () => {
        const originalText = document.getElementById('seed-demo-btn').innerHTML;
        document.getElementById('seed-demo-btn').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Seeding...';
        
        try {
            const res = await fetch('/api/seed/', { method: 'POST' });
            if (res.ok) {
                alert("Demo data successfully pre-populated! Dynamic maps, price advisor, MoMo simulation, and urgent listings are ready for live testing.");
                await initApp();
            }
        } catch (e) {
            console.error(e);
            alert("Error seeding data.");
        } finally {
            document.getElementById('seed-demo-btn').innerHTML = originalText;
        }
    });

    // Crop Search
    document.getElementById('marketplace-search').addEventListener('input', () => {
        loadMarketplace();
    });

    // Crop tag filters
    document.querySelectorAll('.crop-tags .tag').forEach(tag => {
        tag.addEventListener('click', () => {
            document.querySelectorAll('.crop-tags .tag').forEach(t => t.classList.remove('active'));
            tag.classList.add('active');
            loadMarketplace();
        });
    });

    // Urgency toggle sorting
    document.getElementById('urgency-sort-toggle').addEventListener('change', () => {
        loadMarketplace();
    });

    // Create Crop Listing
    document.getElementById('create-produce-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const crop = document.getElementById('produce-crop').value;
        const variety = document.getElementById('produce-variety').value;
        const qty = document.getElementById('produce-qty').value;
        const unit = document.getElementById('produce-unit').value;
        const price = document.getElementById('produce-price').value;
        const harvestDate = document.getElementById('produce-harvest-date').value;
        const desc = document.getElementById('produce-desc').value;
        
        const formData = new FormData();
        formData.append('name', crop);
        formData.append('variety', variety);
        formData.append('quantity_available', qty);
        formData.append('unit', unit);
        formData.append('price_per_unit', price);
        formData.append('harvest_date', harvestDate);
        formData.append('description', desc);
        
        const imageInput = document.getElementById('produce-image');
        if (imageInput && imageInput.files[0]) {
            formData.append('image', imageInput.files[0]);
        }

        try {
            const res = await fetch('/api/produce/create/', {
                method: 'POST',
                body: formData
            });

            if (res.ok) {
                alert("Successfully listed your harvest! Estimated rotting date and freshness score have been calculated by the AI engine.");
                document.getElementById('create-produce-form').reset();
                // Refresh listings
                switchTab('farmer-listings');
            } else {
                const err = await res.json();
                alert("Error listing crop: " + JSON.stringify(err));
            }
        } catch (err) {
            console.error(err);
        }
    });

    // Dispatch goods form submit
    const dispatchForm = document.getElementById('dispatch-goods-form');
    if (dispatchForm) {
        dispatchForm.addEventListener('submit', (e) => submitDispatch(e));
    }

    // Assign driver form submit & cancel handlers
    const assignForm = document.getElementById('assign-driver-form');
    if (assignForm) {
        assignForm.addEventListener('submit', (e) => submitAssignDriver(e));
    }
    const assignCancelBtn = document.getElementById('assign-driver-cancel');
    if (assignCancelBtn) {
        assignCancelBtn.addEventListener('click', () => {
            const modal = document.getElementById('assign-driver-modal');
            if (modal) modal.style.display = 'none';
        });
    }

    // Dynamic AI Pricing & Rot calculations in Farmer Listing form
    const formCrop = document.getElementById('produce-crop');
    const formHarvestDate = document.getElementById('produce-harvest-date');
    const formPrice = document.getElementById('produce-price');

    const updateListingAdvisor = () => {
        const crop = formCrop.value;
        const dateVal = formHarvestDate.value;
        if (!dateVal) return;

        const harvestDate = new Date(dateVal);
        const today = new Date();
        
        // Shelf life averages
        const shelfLives = {
            'Tomatoes': 7,
            'Habanero Peppers': 12,
            'Garden Eggs': 10,
            'Okra': 4,
            'Leafy Greens': 3,
        };

        const shelfLife = shelfLives[crop] || 7;
        const rotDate = new Date(harvestDate);
        rotDate.setDate(rotDate.getDate() + shelfLife);

        const elapsedDays = Math.max(0, Math.floor((today - harvestDate) / (1000 * 60 * 60 * 24)));
        const freshness = Math.max(0, Math.min(100, Math.round((1.0 - (elapsedDays / shelfLife)) * 100)));

        // Recommended price suggestion based on freshness
        const basePrice = parseFloat(formPrice.value) || 120.00;
        let recPrice = basePrice;
        if (freshness >= 80) {
            recPrice = basePrice;
        } else if (freshness >= 50) {
            recPrice = basePrice * 0.85;
        } else if (freshness >= 20) {
            recPrice = basePrice * 0.60;
        } else {
            recPrice = basePrice * 0.30;
        }

        // Render Advisor
        document.getElementById('adv-freshness').textContent = `${freshness}%`;
        const options = { month: 'long', day: 'numeric', year: 'numeric' };
        document.getElementById('adv-rot-date').textContent = rotDate.toLocaleDateString('en-US', options);
        document.getElementById('adv-rec-price').textContent = `GHS ${recPrice.toFixed(2)}`;

        // Adjust text colors based on freshness levels
        const frEl = document.getElementById('adv-freshness');
        frEl.className = 'weight-600';
        if (freshness >= 70) {
            frEl.classList.add('text-emerald');
        } else if (freshness >= 40) {
            frEl.classList.add('text-amber');
        } else {
            frEl.classList.add('text-orange');
        }
    };

    if (formCrop) formCrop.addEventListener('change', updateListingAdvisor);
    if (formHarvestDate) formHarvestDate.addEventListener('change', updateListingAdvisor);
    if (formPrice) formPrice.addEventListener('input', updateListingAdvisor);

    // USSD Floating Widget triggers
    document.getElementById('ussd-toggle')?.addEventListener('click', () => {
        const phone = document.getElementById('ussd-phone');
        if (phone.style.display === 'none') {
            phone.style.display = 'flex';
            resetUSSD();
        } else {
            phone.style.display = 'none';
        }
    });

    document.getElementById('phone-close')?.addEventListener('click', () => {
        document.getElementById('ussd-phone').style.display = 'none';
    });

    document.getElementById('ussd-btn-cancel')?.addEventListener('click', () => {
        resetUSSD();
    });

    document.getElementById('ussd-btn-send')?.addEventListener('click', () => {
        handleUSSDInput();
    });

    document.getElementById('ussd-user-input')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleUSSDInput();
    });

    // AgriBot Triggers
    document.getElementById('agribot-toggle')?.addEventListener('click', () => {
        const box = document.getElementById('agribot-chat-box');
        box.style.display = box.style.display === 'none' ? 'flex' : 'none';
    });

    document.getElementById('agribot-close-btn')?.addEventListener('click', () => {
        document.getElementById('agribot-chat-box').style.display = 'none';
    });

    document.getElementById('agribot-send-btn')?.addEventListener('click', sendAgriBotMessage);
    document.getElementById('agribot-user-text')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendAgriBotMessage();
    });

    // Disease Scanner dropzone interaction
    const dropzone = document.getElementById('dropzone');
    const scannerInput = document.getElementById('scanner-file-input');

    if (dropzone) {
        dropzone.addEventListener('click', () => scannerInput?.click());
        
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.style.borderColor = '#10b981';
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.style.borderColor = '#334155';
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.style.borderColor = '#334155';
            if (e.dataTransfer.files.length) {
                runDiseaseScanner(e.dataTransfer.files[0]);
            }
        });
    }

    if (scannerInput) {
        scannerInput.addEventListener('change', (e) => {
            if (e.target.files.length) {
                runDiseaseScanner(e.target.files[0]);
            }
        });
    }

    // Fund Wallet & Withdraw Sidebar Buttons
    const fundBtn = document.getElementById('sidebar-fund-btn');
    if (fundBtn) {
        fundBtn.addEventListener('click', () => openTopUpModal());
    }

    const withdrawBtn = document.getElementById('sidebar-withdraw-btn');
    if (withdrawBtn) {
        withdrawBtn.addEventListener('click', () => openWithdrawModal());
    }

    // Header Cart Button
    const headerCartBtn = document.getElementById('header-cart-btn');
    if (headerCartBtn) {
        headerCartBtn.addEventListener('click', () => loadCart());
    }

    // Cart Modal Close & Checkout
    const cartCloseBtn = document.getElementById('cart-close-btn');
    if (cartCloseBtn) {
        cartCloseBtn.addEventListener('click', () => {
            document.getElementById('cart-modal').style.display = 'none';
        });
    }

    const cartCheckoutBtn = document.getElementById('cart-checkout-btn');
    if (cartCheckoutBtn) {
        cartCheckoutBtn.addEventListener('click', () => checkoutCart());
    }

    // Top-Up Modal Cancel & Confirm
    const topupCancelBtn = document.getElementById('topup-btn-cancel');
    if (topupCancelBtn) {
        topupCancelBtn.addEventListener('click', () => {
            document.getElementById('topup-modal').style.display = 'none';
        });
    }

    const topupConfirmBtn = document.getElementById('topup-btn-confirm');
    if (topupConfirmBtn) {
        topupConfirmBtn.addEventListener('click', () => initPaystackTopUp());
    }

    // Withdraw Modal Cancel & Submit
    const withdrawCancelBtn = document.getElementById('withdraw-btn-cancel');
    if (withdrawCancelBtn) {
        withdrawCancelBtn.addEventListener('click', () => {
            document.getElementById('withdraw-modal').style.display = 'none';
        });
    }

    const withdrawForm = document.getElementById('withdraw-form');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', (e) => submitWithdrawal(e));
    }

    // Network / Discover Search Input
    const netSearch = document.getElementById('network-search');
    if (netSearch) {
        netSearch.addEventListener('input', () => {
            renderDiscoverUsers();
        });
    }

    // Message Input Controls
    const chatSendBtn = document.getElementById('chat-message-send-btn');
    if (chatSendBtn) {
        chatSendBtn.addEventListener('click', () => sendDirectMessage());
    }
    const chatInput = document.getElementById('chat-message-input');
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendDirectMessage();
        });
    }

    // Contextual Connection request inside active chat headers
    const contextualConnectBtn = document.getElementById('chat-contextual-connect-btn');
    if (contextualConnectBtn) {
        contextualConnectBtn.addEventListener('click', () => {
            if (activeChatPartnerId) {
                sendConnectionRequest(activeChatPartnerId);
            }
        });
    }

    // 🔔 Notifications Inbox Bindings
    const alertsBtn = document.getElementById('header-alerts-btn');
    if (alertsBtn) {
        alertsBtn.addEventListener('click', () => {
            const modal = document.getElementById('alerts-modal');
            if (modal) {
                modal.style.display = 'flex';
                pollNotifications();
            }
        });
    }

    const alertsCloseBtn = document.getElementById('alerts-btn-close');
    if (alertsCloseBtn) {
        alertsCloseBtn.addEventListener('click', () => {
            const modal = document.getElementById('alerts-modal');
            if (modal) modal.style.display = 'none';
        });
    }

    const alertsMarkReadBtn = document.getElementById('alerts-mark-read-btn');
    if (alertsMarkReadBtn) {
        alertsMarkReadBtn.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/notifications/');
                if (res.ok) {
                    pollNotifications();
                }
            } catch (e) {
                console.error("Error marking alerts as read:", e);
            }
        });
    }

    const alertsClearAllBtn = document.getElementById('alerts-clear-all-btn');
    if (alertsClearAllBtn) {
        alertsClearAllBtn.addEventListener('click', async () => {
            if (confirm("Are you sure you want to clear all notifications from the system?")) {
                try {
                    const res = await fetch('/api/notifications/', { method: 'DELETE' });
                    if (res.ok) {
                        pollNotifications();
                    }
                } catch (e) {
                    console.error("Error clearing all notifications:", e);
                }
            }
        });
    }

    // Mobile Sidebar Toggle
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const sidebar = document.querySelector('.sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    if (mobileMenuToggle && sidebar && sidebarOverlay) {
        mobileMenuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarOverlay.classList.toggle('open');
        });

        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('open');
        });

        // Close sidebar when clicking any menu item on mobile
        document.querySelectorAll('.sidebar-menu .menu-item').forEach(item => {
            item.addEventListener('click', () => {
                sidebar.classList.remove('open');
                sidebarOverlay.classList.remove('open');
            });
        });
    }
}

// Tab switcher logic
function switchTab(tabName) {
    currentTab = tabName;
    
    // Manage Sidebar active class
    document.querySelectorAll('.sidebar-menu .menu-item').forEach(item => {
        if (item.getAttribute('data-tab') === tabName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Manage Page content panes
    document.querySelectorAll('.content-body .tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    
    const targetPane = document.getElementById(`tab-${tabName}`);
    if (targetPane) {
        targetPane.classList.add('active');
    }

    // Toggle map visibility based on tab name to maintain design consistency
    const mapSection = document.querySelector('.map-section');
    if (mapSection) {
        if (tabName === 'marketplace' || tabName === 'logistics') {
            mapSection.style.display = 'block';
            setTimeout(() => {
                if (window.map) window.map.invalidateSize();
            }, 360);
        } else {
            mapSection.style.display = 'none';
        }
    }

    // Set headers
    const titleEl = document.getElementById('tab-title');
    const subEl = document.getElementById('tab-subtitle');
    
    if (tabName === 'marketplace') {
        titleEl.textContent = 'Marketplace';
        subEl.textContent = 'Discover fresh vegetables directly from smallholders in Bono East';
        loadMarketplace();
    } else if (tabName === 'farmer-listings') {
        titleEl.textContent = 'My Crop Listings';
        subEl.textContent = 'Upload your harvest yields and set dynamic pricing advisor metrics';
        loadFarmerListings();
    } else if (tabName === 'orders') {
        titleEl.textContent = 'My Orders';
        subEl.textContent = 'Secure transactions and escrow payments release status';
        loadOrders();
    } else if (tabName === 'logistics') {
        if (currentUser.role === 'FARMER') {
            titleEl.textContent = 'Logistics & Dispatch';
            subEl.textContent = 'Book transporters, dispatch goods directly to clients, and track active deliveries';
        } else {
            titleEl.textContent = 'Logistics Jobs';
            subEl.textContent = 'Coordinate matching delivery requests and update transport routing status';
        }
        loadLogisticsJobs();
    } else if (tabName === 'disease-scanner') {
        titleEl.textContent = 'AI Plant Pathology Lab';
        subEl.textContent = 'Check crop diseases instantly using high confidence computer vision scans';
    } else if (tabName === 'analytics') {
        titleEl.textContent = 'Analytics & Wallet';
        subEl.textContent = 'Real-time Techiman market index averages and digital wallet metrics';
        loadProfileData(); // updates wallet
        loadWalletTransactions();
        renderAnalyticsChart();
    } else if (tabName === 'network') {
        titleEl.textContent = 'My Trust Circle & Network';
        subEl.textContent = 'Connect with farmers, buyers, and transporters to build trust circles';
        loadNetwork();
    } else if (tabName === 'messages') {
        titleEl.textContent = 'AgriConnect Messaging Center';
        subEl.textContent = 'Discuss harvest quality, coordinate delivery logistics, and chat with connections';
        loadChats();
    }
}

// Update profile wallet balance in header
async function loadProfileData() {
    try {
        const res = await fetch('/api/profile/');
        if (res.ok) {
            currentUser = await res.json();
            updateUIForUser();
        }
    } catch (e) {
        console.error(e);
    }
}

// Clear map markers
function clearMapMarkers() {
    mapMarkers.forEach(m => map.removeLayer(m));
    mapMarkers = [];
    if (routingLine) {
        map.removeLayer(routingLine);
        routingLine = null;
    }
}

// -------------------------------------------------------------
// MARKETPLACE TAB LOGIC
async function loadMarketplace() {
    clearMapMarkers();
    
    const queryVal = document.getElementById('marketplace-search').value;
    const activeCropTag = document.querySelector('.crop-tags .tag.active').getAttribute('data-crop');
    const sortUrgency = document.getElementById('urgency-sort-toggle').checked;
    
    let url = '/api/produce/';
    const params = [];
    if (queryVal) params.push(`search=${encodeURIComponent(queryVal)}`);
    if (activeCropTag) params.push(`crop=${encodeURIComponent(activeCropTag)}`);
    if (sortUrgency) params.push('sort=urgency');
    
    if (params.length) {
        url += '?' + params.join('&');
    }

    try {
        const res = await fetch(url);
        if (!res.ok) return;
        const produceList = await res.json();

        // Separate produce list into Urgent (freshness < 50%) and standard
        const urgentItems = produceList.filter(p => p.freshness_score < 50);
        const standardItems = produceList.filter(p => p.freshness_score >= 50);

        // Render Urgent Items
        const urgentSec = document.getElementById('urgent-crops-container');
        const urgentGrid = document.getElementById('urgent-produce-grid');
        
        if (urgentItems.length > 0) {
            urgentSec.style.display = 'block';
            urgentGrid.innerHTML = '';
            urgentItems.forEach(p => {
                urgentGrid.appendChild(createProduceCard(p, true));
                addMapMarker(p, 'urgent');
            });
        } else {
            urgentSec.style.display = 'none';
        }

        // Render Standard Items
        const standardGrid = document.getElementById('standard-produce-grid');
        standardGrid.innerHTML = '';
        if (standardItems.length > 0) {
            standardItems.forEach(p => {
                standardGrid.appendChild(createProduceCard(p, false));
                addMapMarker(p, 'standard');
            });
        } else if (urgentItems.length === 0) {
            standardGrid.innerHTML = '<div class="text-secondary p-4 w-full text-center">No available produce matches. Click Reset & Seed Demo Data to pre-populate.</div>';
        }
        
    } catch (e) {
        console.error(e);
    }
}

// Add markers to Leaflet map
function addMapMarker(p, type) {
    if (!map) return;
    
    // Custom color markers
    const iconColor = type === 'urgent' ? 'orange' : 'green';
    const markerHtmlStyles = `
        background-color: ${iconColor === 'orange' ? '#f97316' : '#10b981'};
        width: 14px;
        height: 14px;
        display: block;
        border-radius: 50%;
        border: 2px solid #fff;
        box-shadow: 0 0 8px rgba(0,0,0,0.5);
    `;
    
    const customIcon = L.divIcon({
        className: "my-custom-pin",
        iconAnchor: [7, 7],
        html: `<span style="${markerHtmlStyles}" />`
    });

    const m = L.marker([p.farmer_lat, p.farmer_lng], { icon: customIcon })
        .addTo(map)
        .bindPopup(`
            <div style="font-family: inherit; font-size: 11px; color:#fff;">
                <strong style="color:#10b981; font-size:13px;">${p.variety || p.name}</strong><br>
                <span>Farmer: ${p.farmer_name}</span><br>
                <span>Qty: ${p.quantity_available} ${p.unit}</span><br>
                <span>Price: GHS ${p.price_per_unit}</span><br>
                <span>Freshness: <strong>${p.freshness_score}%</strong></span>
            </div>
        `);
        
    mapMarkers.push(m);
}

// Helper to create HTML elements for crop cards
function createProduceCard(p, isUrgent) {
    const col = document.createElement('div');
    col.className = 'produce-card';
    if (isUrgent) {
        col.classList.add('urgent-highlight');
    }

    // Determine fallback crop image if URL is missing
    const cropImages = {
        'Tomatoes': 'https://images.unsplash.com/photo-1595855759920-86582396756a?auto=format&fit=crop&w=300&q=80',
        'Habanero Peppers': 'https://images.unsplash.com/photo-1588252303782-cb80119abd6d?auto=format&fit=crop&w=300&q=80',
        'Garden Eggs': 'https://images.unsplash.com/photo-1590301157890-4810ed352733?auto=format&fit=crop&w=300&q=80',
        'Okra': 'https://images.unsplash.com/photo-1627308595229-7830a5c91f9f?auto=format&fit=crop&w=300&q=80',
        'Leafy Greens': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?auto=format&fit=crop&w=300&q=80'
    };
    const imageUrl = p.image_url || cropImages[p.name] || cropImages['Tomatoes'];

    // Freshness indicator
    let freshnessClass = 'high';
    if (p.freshness_score < 30) {
        freshnessClass = 'low';
    } else if (p.freshness_score < 60) {
        freshnessClass = 'med';
    }

    let urgencyTagHtml = '';
    if (isUrgent) {
        urgencyTagHtml = `<div class="urgency-badge"><i class="fa-solid fa-triangle-exclamation"></i> Spoilage Risk</div>`;
    }

    // Discount indicator
    let priceHtml = `<span class="price-val">GHS ${p.price_per_unit}</span>`;
    if (p.freshness_score < 80) {
        priceHtml = `
            <div class="price-box">
                <span class="original-price-val">GHS ${p.price_per_unit}</span>
                <span class="price-val">GHS ${p.suggested_price}</span>
            </div>
        `;
    }

    // AI shelf life prediction
    const shelfLife = Math.max(1, Math.round((new Date(p.predicted_rot_date) - new Date()) / (1000 * 60 * 60 * 24)));
    // AI Recommendation
    const recomBadge = p.freshness_score >= 70 ? '<div class="ai-recom-badge"><i class="fa-solid fa-wand-magic-sparkles"></i> AI Recommends</div>' : '';
    // Mock distance
    const mockDist = (Math.random() * 4 + 1.2).toFixed(1);

    col.innerHTML = `
        <div class="produce-img-wrapper" style="position: relative;">
            <img src="${imageUrl}" alt="${p.name}">
            <div class="verified-badge"><i class="fa-solid fa-circle-check"></i> Verified Farmer</div>
            ${urgencyTagHtml}
        </div>
        <div class="produce-info">
            <div class="crop-title-row">
                <div>
                    <h3 class="crop-name">${p.variety || p.name}</h3>
                    <span class="crop-variety">${p.name}</span>
                </div>
                <div class="badge ${isUrgent ? 'badge-orange' : 'badge-green'}" style="border-radius: 50px;">${p.quantity_available} ${p.unit}</div>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                <div class="farmer-pill">
                    <i class="fa-solid fa-circle-user"></i>
                    <span>${p.farmer_name}</span>
                </div>
                <div class="rating-badge">
                    <i class="fa-solid fa-star"></i> <span>4.8</span>
                </div>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--text-secondary); margin-top: 4px;">
                <span><i class="fa-solid fa-location-dot"></i> Techiman • ${mockDist} km</span>
                <span><i class="fa-solid fa-calendar-day"></i> Shelf life: ~${shelfLife} days</span>
            </div>

            ${recomBadge}
            
            <div class="freshness-container" style="margin-top: 6px;">
                <div class="freshness-lbl-row">
                    <span>AI Freshness:</span>
                    <span class="text-${freshnessClass === 'low' ? 'orange' : (freshnessClass === 'med' ? 'amber' : 'emerald')}">${p.freshness_score}%</span>
                </div>
                <div class="freshness-bar">
                    <div class="freshness-fill ${freshnessClass}" style="width: ${p.freshness_score}%;"></div>
                </div>
            </div>

            <div class="price-row">
                ${priceHtml}
                <span class="unit-label">per ${p.unit.slice(0, -1)}</span>
            </div>
        </div>
        <div class="card-footer-actions">
            ${(() => {
                if (currentUser.role === 'BUYER') {
                    return `
                        <div style="display: flex; gap: 8px; width: 100%; align-items: center;">
                            <input type="number" class="form-control quantity-input" value="1" min="1" max="${p.quantity_available}" style="width: 54px; text-align: center; padding: 6px; border-radius: var(--radius-sm); border-color: var(--border-color); background-color: var(--bg-main); color: var(--text-primary);">
                            <button class="btn ${isUrgent ? 'btn-orange' : 'btn-primary'} add-to-cart-btn" data-id="${p.id}" style="flex-grow: 1; padding: 10px; font-size: 11px;">
                                <i class="fa-solid fa-cart-plus"></i> Buy Now
                            </button>
                            <button class="btn btn-secondary" style="width: 36px; height: 36px; padding: 0; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm);" onclick="alert('Opening secure chat channel with ${p.farmer_name} (simulation)')" title="Chat Farmer">
                                <i class="fa-solid fa-comments text-emerald"></i>
                            </button>
                            <button class="btn btn-secondary" style="width: 36px; height: 36px; padding: 0; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm);" onclick="alert('Produce saved to favorites & comparison matrix (simulation)')" title="Save / Compare">
                                <i class="fa-solid fa-heart text-amber"></i>
                            </button>
                        </div>
                    `;
                } else if (currentUser.role === 'FARMER') {
                    return `
                        <button class="btn btn-secondary btn-block" disabled style="opacity: 0.65; cursor: not-allowed; width: 100%; border-radius: var(--radius-sm);">
                            <i class="fa-solid fa-wheat-awn text-emerald"></i> Farmer View (Listing)
                        </button>
                    `;
                } else {
                    return `
                        <button class="btn btn-secondary btn-block" disabled style="opacity: 0.65; cursor: not-allowed; width: 100%; border-radius: var(--radius-sm);">
                            <i class="fa-solid fa-truck text-emerald"></i> Transporter View
                        </button>
                    `;
                }
            })()}
        </div>
    `;

    // Add to Cart event
    const addBtn = col.querySelector('.add-to-cart-btn');
    if (addBtn) {
        addBtn.addEventListener('click', (e) => {
            const id = e.currentTarget.getAttribute('data-id');
            const qtyInput = col.querySelector('.quantity-input');
            const qty = parseInt(qtyInput.value) || 1;
            addToCart(id, qty);
        });
    }

    return col;
}

// Place Order and open Mobile Money payment simulation
async function triggerPurchaseFlow(produceId, price) {
    if (currentUser.role !== 'BUYER') {
        alert("Only buyers can purchase produce! Switch your user role to 'Buyer' using the demo panel on the left.");
        return;
    }
    
    const qty = prompt("Enter quantity to purchase:", "1");
    if (!qty || isNaN(qty) || parseInt(qty) <= 0) return;

    // Create a pending Order
    try {
        const res = await fetch('/api/orders/create/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                produce: produceId,
                quantity: parseInt(qty),
                delivery_type: 'PLATFORM_DELIVERY'
            })
        });

        if (res.ok) {
            const order = await res.json();
            
            // Pop up simulated MoMo dialog
            showMoMoPaymentDialog(order);
        } else {
            const err = await res.json();
            if (err.not_connected) {
                if (confirm(err.detail + "\nWould you like to open the My Circle tab to connect?")) {
                    switchTab('network');
                }
            } else {
                alert("Order failed: " + (err.detail || JSON.stringify(err)));
            }
        }
    } catch (e) {
        console.error(e);
    }
}

// MoMo Modal
function showMoMoPaymentDialog(order) {
    const modal = document.getElementById('momo-modal');
    modal.style.display = 'flex';
    document.getElementById('momo-amount').textContent = `GHS ${parseFloat(order.total_price).toFixed(2)}`;

    // Set buttons handlers
    document.getElementById('momo-btn-cancel').onclick = () => {
        modal.style.display = 'none';
        alert("Payment canceled. The order is stored as PENDING and UNPAID in your transaction dashboard.");
        switchTab('orders');
    };

    document.getElementById('momo-btn-confirm').onclick = async () => {
        const pin = document.getElementById('momo-pin').value;
        if (pin.length < 4) {
            alert("Invalid PIN. Enter a 4-digit code.");
            return;
        }
        
        modal.style.display = 'none';
        
        // Approve MoMo transaction
        try {
            const res = await fetch(`/api/orders/${order.id}/pay/`, { method: 'POST' });
            if (res.ok) {
                alert("Mobile Money Payment Successful! Funds have been securely placed in Platform Escrow. The transporter match has been initialized.");
                switchTab('orders');
            }
        } catch (e) {
            console.error(e);
        }
    };
}


// -------------------------------------------------------------
// FARMER TAB LOGIC
async function loadFarmerListings() {
    try {
        const res = await fetch(`/api/produce/?farmer=${currentUser.id}`);
        if (!res.ok) return;
        const list = await res.json();
        
        const body = document.getElementById('farmer-produce-list-body');
        body.innerHTML = '';

        if (list.length === 0) {
            body.innerHTML = '<tr><td colspan="6" class="text-center text-secondary">You have no active listings. Create one on the right!</td></tr>';
        } else {
            list.forEach(p => {
                const tr = document.createElement('tr');
                
                let statusBadge = `<span class="badge badge-green">Available</span>`;
                if (p.status === 'SOLD') {
                    statusBadge = `<span class="badge badge-slate">Sold Out</span>`;
                } else if (p.status === 'RESERVED') {
                    statusBadge = `<span class="badge badge-blue">Reserved</span>`;
                }

                const rotOptions = { month: 'short', day: 'numeric' };
                const rotDate = new Date(p.predicted_rot_date).toLocaleDateString('en-US', rotOptions);

                tr.innerHTML = `
                    <td><strong>${p.variety || p.name}</strong><br><span class="font-xxs text-secondary">${p.name}</span></td>
                    <td>${p.quantity_available} ${p.unit}</td>
                    <td>GHS ${p.price_per_unit}</td>
                    <td><span class="badge ${p.freshness_score < 40 ? 'badge-orange' : 'badge-green'}">${p.freshness_score}%</span></td>
                    <td>${rotDate}</td>
                    <td>${statusBadge}</td>
                `;
                body.appendChild(tr);
            });
        }

        // Populate dispatch produce listings dropdown
        const prodSelect = document.getElementById('dispatch-produce');
        if (prodSelect) {
            prodSelect.innerHTML = '<option value="">-- Choose Listing to Ship --</option>';
            list.filter(p => p.status === 'AVAILABLE' && p.quantity_available > 0).forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = `${p.variety || p.name} (${p.quantity_available} ${p.unit} available)`;
                prodSelect.appendChild(opt);
            });
        }

        // Fetch and populate buyers and drivers from connections
        const connRes = await fetch('/api/users/connections/');
        if (connRes.ok) {
            const connData = await connRes.json();
            const connectedUsers = connData.connections.map(c => c.user);
            
            const buyers = connectedUsers.filter(u => u.role === 'BUYER');
            const buyerSelect = document.getElementById('dispatch-buyer');
            if (buyerSelect) {
                buyerSelect.innerHTML = '<option value="">-- Choose Client / Buyer --</option>';
                buyers.forEach(b => {
                    const opt = document.createElement('option');
                    opt.value = b.id;
                    opt.textContent = `${b.username} (${b.district}, ${b.region})`;
                    buyerSelect.appendChild(opt);
                });
            }

            const drivers = connectedUsers.filter(u => u.role === 'TRANSPORTER');
            const driverSelect = document.getElementById('dispatch-driver');
            if (driverSelect) {
                driverSelect.innerHTML = '<option value="">No Driver Pre-Assigned (Post to Marketplace)</option>';
                drivers.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.id;
                    opt.textContent = `${d.username} (${d.district})`;
                    driverSelect.appendChild(opt);
                });
            }

            const assignDriverSelect = document.getElementById('assign-driver-select');
            if (assignDriverSelect) {
                assignDriverSelect.innerHTML = '<option value="">-- Choose Driver --</option>';
                drivers.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.id;
                    opt.textContent = `${d.username} (${d.district})`;
                    assignDriverSelect.appendChild(opt);
                });
            }
        }

        // Clear and load drivers onto map
        clearMapMarkers();
        await loadTransportersForMap();

    } catch (e) {
        console.error(e);
    }
}


// -------------------------------------------------------------
// ORDERS & ESCROW TAB LOGIC
// -------------------------------------------------------------
// ORDERS & ESCROW TAB LOGIC
async function loadOrders() {
    clearMapMarkers();
    
    try {
        const res = await fetch('/api/orders/create/');
        if (!res.ok) return;
        const orders = await res.json();
        
        const container = document.getElementById('orders-list-container');
        container.innerHTML = '';

        if (orders.length === 0) {
            container.innerHTML = '<div class="text-secondary text-center p-4">You have no active transactions. Go to the Marketplace to buy vegetables!</div>';
            return;
        }

        orders.forEach(order => {
            const card = document.createElement('div');
            card.className = 'order-card';
            
            // Format Date
            const orderDate = new Date(order.created_at).toLocaleDateString('en-US', {
                month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
            });

            // Payment Badge styling
            let paymentBadge = `<span class="badge badge-slate">Unpaid</span>`;
            if (order.payment_status === 'HELD_IN_ESCROW') {
                paymentBadge = `<span class="badge badge-orange"><i class="fa-solid fa-clock-rotate-left"></i> Held in Escrow</span>`;
            } else if (order.payment_status === 'RELEASED') {
                paymentBadge = `<span class="badge badge-green"><i class="fa-solid fa-circle-check"></i> Released to Farmer</span>`;
            } else if (order.payment_status === 'REFUNDED') {
                paymentBadge = `<span class="badge badge-red">Refunded</span>`;
            }

            // Stepper timeline configuration
            const stages = ['PENDING', 'PAID', 'SHIPPED', 'DELIVERED'];
            let currentStageIndex = stages.indexOf(order.status);
            if (order.payment_status === 'RELEASED') {
                currentStageIndex = 3; // Fully complete
            }
            
            const progressPercent = (currentStageIndex / (stages.length - 1)) * 100;
            
            // Build stepper nodes HTML
            let stepperNodesHtml = '';
            stages.forEach((stage, idx) => {
                let statusClass = '';
                if (idx < currentStageIndex) statusClass = 'completed';
                else if (idx === currentStageIndex) statusClass = 'active';
                
                let icon = '<i class="fa-solid fa-circle"></i>';
                if (idx < currentStageIndex) icon = '<i class="fa-solid fa-check"></i>';
                
                let label = stage;
                if (stage === 'PENDING') label = 'Ordered';
                else if (stage === 'PAID') label = 'Escrow Paid';
                else if (stage === 'SHIPPED') label = 'In Transit';
                else if (stage === 'DELIVERED') label = 'Delivered';

                stepperNodesHtml += `
                    <div class="step-node ${statusClass}">
                        ${icon}
                        <span class="step-label">${label}</span>
                    </div>
                `;
            });

            // Actions for the buyer and farmer
            let actionButtonsHtml = '';
            if (currentUser.role === 'BUYER') {
                if (order.payment_status === 'UNPAID') {
                    let totalToPay = parseFloat(order.total_price);
                    let label = "Pay Produce Escrow";
                    if (order.transporter_details) {
                        totalToPay += parseFloat(order.transporter_details.estimated_cost);
                        label = "Pay Produce + Logistics";
                    }
                    actionButtonsHtml = `
                        <button class="btn btn-primary pay-order-btn" data-id="${order.id}">
                            <i class="fa-solid fa-wallet"></i> ${label} (GHS ${totalToPay.toFixed(2)})
                        </button>
                    `;
                } else if (order.transporter_details && order.transporter_details.status === 'PENDING_APPROVAL') {
                    actionButtonsHtml = `
                        <div class="flex gap-2" style="width: 100%;">
                            <button class="btn btn-success approve-driver-btn flex-1" data-job-id="${order.transporter_details.job_id}" data-id="${order.id}">
                                <i class="fa-solid fa-user-check"></i> Approve Driver (${order.transporter_details.username})
                            </button>
                            <button class="btn btn-danger reject-driver-btn" data-job-id="${order.transporter_details.job_id}" data-id="${order.id}" style="width: auto; padding: 8px 16px;">
                                <i class="fa-solid fa-user-xmark"></i> Reject
                            </button>
                        </div>
                    `;
                } else if (order.payment_status === 'HELD_IN_ESCROW' && order.status === 'DELIVERED') {
                    actionButtonsHtml = `
                        <button class="btn btn-success confirm-delivery-btn pulsing-green" data-id="${order.id}">
                            <i class="fa-solid fa-circle-check"></i> Confirm Delivery & Release Funds
                        </button>
                    `;
                } else if (order.transporter_details && order.transporter_details.payment_status === 'REQUESTED') {
                    actionButtonsHtml = `
                        <button class="btn btn-primary approve-logistics-payment-btn" data-job-id="${order.transporter_details.id}" data-id="${order.id}">
                            <i class="fa-solid fa-wallet"></i> Pay Logistics Fee (GHS ${parseFloat(order.transporter_details.estimated_cost).toFixed(2)})
                        </button>
                    `;
                } else if (order.transporter_details && order.transporter_details.status === 'PENDING_MATCH') {
                    actionButtonsHtml = `
                        <button class="btn btn-orange open-assign-driver-btn" data-job-id="${order.transporter_details.id}" data-id="${order.id}">
                            <i class="fa-solid fa-truck-ramp-box"></i> Hire/Assign Driver
                        </button>
                    `;
                }
            } else if (currentUser.role === 'FARMER') {
                if (order.transporter_details && order.transporter_details.status === 'PENDING_MATCH') {
                    actionButtonsHtml = `
                        <button class="btn btn-orange open-assign-driver-btn" data-job-id="${order.transporter_details.id}" data-id="${order.id}">
                            <i class="fa-solid fa-truck-ramp-box"></i> Hire/Assign Driver
                        </button>
                    `;
                }
            }

            card.innerHTML = `
                <div class="order-header-row">
                    <div>
                        <strong class="font-outfit text-emerald">Order #${order.id}</strong>
                        <span class="text-secondary font-xs ml-2">Placed on ${orderDate}</span>
                    </div>
                    <div>
                        ${paymentBadge}
                    </div>
                </div>
                
                <div class="order-details-summary">
                    <div class="ord-block">
                        <label>Vegetable Crop</label>
                        <span>${order.produce_details.variety || order.produce_details.name}</span>
                    </div>
                    <div class="ord-block">
                        <label>Quantity Ordered</label>
                        <span>${order.quantity} ${order.produce_details.unit}</span>
                    </div>
                    <div class="ord-block">
                        <label>Total Price (Escrow)</label>
                        <span class="text-emerald">GHS ${order.total_price}</span>
                    </div>
                    <div class="ord-block">
                        <label>Farmer</label>
                        <span>${order.produce_details.farmer_name} (${order.produce_details.farmer_phone})</span>
                    </div>
                    ${order.transporter_details ? `
                    <div class="ord-block">
                        <label>Logistics Fee</label>
                        <span class="text-amber">GHS ${parseFloat(order.transporter_details.estimated_cost).toFixed(2)}</span>
                    </div>
                    <div class="ord-block">
                        <label>Logistics Mode</label>
                        <span>${order.transporter_details.vehicle_type} (${order.transporter_details.status})</span>
                    </div>
                    ` : ''}
                </div>

                <!-- Timeline Stepper -->
                <div class="stepper-timeline">
                    <div class="stepper-progress-line" style="width: ${progressPercent}%;"></div>
                    ${stepperNodesHtml}
                </div>
                
                ${actionButtonsHtml ? `<div class="order-actions">${actionButtonsHtml}</div>` : ''}
            `;

            // Bind Actions
            if (card.querySelector('.pay-order-btn')) {
                card.querySelector('.pay-order-btn').addEventListener('click', async (e) => {
                    const id = e.currentTarget.getAttribute('data-id');
                    try {
                        const payRes = await fetch(`/api/orders/${id}/pay/`, { method: 'POST' });
                        const data = await payRes.json();
                        if (payRes.ok) {
                            alert("Payment Successful! Funds have been securely placed in Platform Escrow.");
                            loadOrders();
                            loadProfileData(); // update wallet balance
                        } else if (payRes.status === 402 && data.needs_topup) {
                            if (confirm(`Insufficient balance. You need an additional GHS ${data.shortfall.toFixed(2)}. Top up now?`)) {
                                openTopUpModal(data.shortfall);
                            }
                        } else {
                            alert("Payment failed: " + (data.detail || JSON.stringify(data)));
                        }
                    } catch (err) {
                        console.error(err);
                    }
                });
            }
            if (card.querySelector('.confirm-delivery-btn')) {
                card.querySelector('.confirm-delivery-btn').addEventListener('click', async (e) => {
                    const id = e.currentTarget.getAttribute('data-id');
                    if (confirm("Confirming delivery will release the GHS " + order.total_price + " instantly to the farmer's mobile wallet. Do you want to proceed?")) {
                        try {
                            const releaseRes = await fetch(`/api/orders/${id}/confirm-delivery/`, { method: 'POST' });
                            if (releaseRes.ok) {
                                alert("Delivery confirmed! Escrow funds have been successfully released to " + order.produce_details.farmer_name + "'s mobile money account.");
                                switchTab('orders');
                                loadProfileData(); // update wallet balance in header
                            } else {
                                const errData = await releaseRes.json();
                                alert("Failed to confirm delivery: " + (errData.detail || JSON.stringify(errData)));
                            }
                        } catch (err) {
                            console.error(err);
                            alert("Network error: Could not contact server to confirm delivery.");
                        }
                    }
                });
            }
            if (card.querySelector('.approve-driver-btn')) {
                card.querySelector('.approve-driver-btn').addEventListener('click', async (e) => {
                    const jobId = e.currentTarget.getAttribute('data-job-id');
                    if (confirm("Do you want to approve this transporter for your delivery?")) {
                        try {
                            const res = await fetch(`/api/logistics/jobs/${jobId}/approve/`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ action: 'approve' })
                            });
                            if (res.ok) {
                                alert("Transporter match approved successfully! They are now authorized to pick up and deliver your cargo.");
                                loadOrders();
                            } else {
                                const err = await res.json();
                                alert("Failed to approve transporter: " + (err.detail || JSON.stringify(err)));
                            }
                        } catch (err) {
                            console.error(err);
                        }
                    }
                });
            }
            if (card.querySelector('.reject-driver-btn')) {
                card.querySelector('.reject-driver-btn').addEventListener('click', async (e) => {
                    const jobId = e.currentTarget.getAttribute('data-job-id');
                    if (confirm("Are you sure you want to reject this transporter claim?")) {
                        try {
                            const res = await fetch(`/api/logistics/jobs/${jobId}/approve/`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ action: 'reject' })
                            });
                            if (res.ok) {
                                alert("Transporter match rejected. The logistics job has been reopened for other drivers.");
                                loadOrders();
                            } else {
                                const err = await res.json();
                                alert("Failed to reject transporter: " + (err.detail || JSON.stringify(err)));
                            }
                        } catch (err) {
                            console.error(err);
                        }
                    }
                });
            }
            if (card.querySelector('.open-assign-driver-btn')) {
                card.querySelector('.open-assign-driver-btn').addEventListener('click', (e) => {
                    const jobId = e.currentTarget.getAttribute('data-job-id');
                    openAssignDriverModal(jobId);
                });
            }
            if (card.querySelector('.approve-logistics-payment-btn')) {
                card.querySelector('.approve-logistics-payment-btn').addEventListener('click', async (e) => {
                    const jobId = e.currentTarget.getAttribute('data-job-id');
                    if (confirm("Are you sure you want to pay the logistics fee for this delivery? This will deduct the amount from your wallet.")) {
                        try {
                            const res = await fetch(`/api/logistics/jobs/${jobId}/approve_payment/`, {
                                method: 'POST',
                                credentials: 'same-origin',
                                headers: { 'Content-Type': 'application/json' }
                            });
                            if (res.ok) {
                                alert("Logistics fee paid successfully!");
                                loadOrders();
                            } else {
                                const err = await res.json();
                                alert("Failed to pay logistics fee: " + (err.detail || JSON.stringify(err)));
                            }
                        } catch (err) {
                            console.error(err);
                            alert("Error paying logistics fee");
                        }
                    }
                });
            }

            container.appendChild(card);

            // Draw route on map for this order
            drawOrderRoute(order);
        });

    } catch (e) {
        console.error(e);
    }
}

// Draw polyline route on map
function drawOrderRoute(order) {
    if (!map) return;
    
    const fLat = order.produce_details.farmer_lat;
    const fLng = order.produce_details.farmer_lng;
    
    // Buyer Coordinates. If buyer coordinates are Kumasi/Accra, draw line to show long-haul transport.
    // Buyer info is nested or we can fetch current user coordinates
    let bLat = currentUser.latitude;
    let bLng = currentUser.longitude;
    
    // Draw route if buyer is different than farmer
    if (fLat !== bLat || fLng !== bLng) {
        // Draw polyline
        routingLine = L.polyline([[fLat, fLng], [bLat, bLng]], {
            color: '#3b82f6',
            weight: 3,
            dashArray: '5, 10',
            opacity: 0.8
        }).addTo(map);
        
        // Zoom map to cover the route
        map.fitBounds(routingLine.getBounds(), { padding: [30, 30] });
    }
}


// -------------------------------------------------------------
// LOGISTICS / TRANSPORTER TAB LOGIC
async function loadLogisticsJobs() {
    clearMapMarkers();
    
    try {
        if (currentUser.role === 'FARMER') {
            const farmerView = document.getElementById('farmer-logistics-view');
            const transporterView = document.getElementById('transporter-logistics-view');
            if (farmerView) farmerView.style.display = 'grid';
            if (transporterView) transporterView.style.display = 'none';

            // Populate Farmer Dispatch dropdowns
            await loadFarmerDispatchDropdowns();

            // Fetch and render farmer's dispatched jobs
            const res = await fetch('/api/logistics/jobs/');
            const jobs = res.ok ? await res.json() : [];

            const container = document.getElementById('farmer-dispatched-jobs');
            if (container) {
                container.innerHTML = '';
                if (jobs.length === 0) {
                    container.innerHTML = '<div class="text-secondary font-xs text-center p-3">You have no active dispatched shipments. Use the form to dispatch goods.</div>';
                } else {
                    jobs.forEach(job => {
                        const card = createFarmerJobCard(job);
                        container.appendChild(card);
                        addLogisticsMarkers(job);
                    });
                }
            }

            // Also load transporters on the map
            await loadTransportersForMap();

        } else if (currentUser.role === 'TRANSPORTER') {
            const farmerView = document.getElementById('farmer-logistics-view');
            const transporterView = document.getElementById('transporter-logistics-view');
            if (farmerView) farmerView.style.display = 'none';
            if (transporterView) transporterView.style.display = 'grid';

            // Fetch open jobs
            const searchInput = document.getElementById('logistics-board-search');
            let searchParam = '';
            if (searchInput && searchInput.value) {
                searchParam = `?search=${encodeURIComponent(searchInput.value)}`;
            }
            const openRes = await fetch('/api/logistics/jobs/' + searchParam);
            const openJobs = openRes.ok ? await openRes.json() : [];

            // Fetch claimed jobs
            const claimedRes = await fetch('/api/logistics/jobs/?claimed=true');
            const claimedJobs = claimedRes.ok ? await claimedRes.json() : [];

            // Render Open Jobs
            const openContainer = document.getElementById('logistics-open-jobs');
            if (openContainer) {
                openContainer.innerHTML = '';
                if (openJobs.length === 0) {
                    openContainer.innerHTML = '<div class="text-secondary font-xs text-center p-3">No available transport requests in Techiman. Place orders as a Buyer to request delivery.</div>';
                } else {
                    openJobs.forEach(job => {
                        const card = createJobCard(job, false);
                        openContainer.appendChild(card);
                        addLogisticsMarkers(job);
                    });
                }
            }

            // Render Claimed Jobs
            const myContainer = document.getElementById('logistics-my-jobs');
            if (myContainer) {
                myContainer.innerHTML = '';
                if (claimedJobs.length === 0) {
                    myContainer.innerHTML = '<div class="text-secondary font-xs text-center p-3">You have no active claimed transport jobs. Claim a job on the left.</div>';
                } else {
                    claimedJobs.forEach(job => {
                        const card = createJobCard(job, true);
                        myContainer.appendChild(card);
                        addLogisticsMarkers(job);
                    });
                }
            }
        }
    } catch (e) {
        console.error(e);
    }
}

function addLogisticsMarkers(job) {
    if (!map) return;
    const fLat = job.order_details.produce_details.farmer_lat;
    const fLng = job.order_details.produce_details.farmer_lng;
    const bLat = job.order_details.buyer_phone ? 5.6037 : 7.5848; // coordinates mock

    const fMarker = L.marker([fLat, fLng]).addTo(map).bindPopup("Pickup: " + job.order_details.produce_details.farmer_name);
    mapMarkers.push(fMarker);
}

function createJobCard(job, isClaimed) {
    const card = document.createElement('div');
    card.className = 'job-card';
    
    let btnHtml = '';
    if (!isClaimed) {
        btnHtml = `
            <button class="btn btn-primary claim-job-btn" data-id="${job.id}">
                <i class="fa-solid fa-circle-check"></i> Claim Delivery Contract (GHS ${job.estimated_cost})
            </button>
        `;
    } else {
        if (job.status === 'MATCHED') {
            btnHtml = `
                <button class="btn btn-orange pick-job-btn" data-id="${job.id}">
                    <i class="fa-solid fa-truck-pickup"></i> Confirm Cargo Pickup
                </button>
            `;
            if (job.paid_by === 'BUYER' && job.payment_status === 'UNPAID') {
                btnHtml += `
                    <button class="btn btn-primary mt-2 w-full req-payment-btn" data-id="${job.id}" style="padding: 10px;">
                        <i class="fa-solid fa-hand-holding-dollar"></i> Request Payment from Client
                    </button>
                `;
            } else if (job.paid_by === 'BUYER' && job.payment_status === 'REQUESTED') {
                btnHtml += `
                    <span class="badge badge-amber mt-2 block text-center w-full py-2">Payment Requested</span>
                `;
            }
        } else if (job.status === 'PICKED_UP') {
            btnHtml = `
                <button class="btn btn-success deliver-job-btn" data-id="${job.id}">
                    <i class="fa-solid fa-house-chimney-user"></i> Confirm Delivery to Buyer
                </button>
            `;
        } else {
            btnHtml = `<span class="badge badge-green text-center block w-full py-2">Delivery Complete</span>`;
        }
    }

    card.innerHTML = `
        <div class="job-header">
            <div class="job-route">
                <span>${job.order_details.produce_details.farmer_district}</span>
                <i class="fa-solid fa-arrow-right"></i>
                <span>${job.order_details.buyer_name} (${job.order_details.delivery_type === 'SELF_PICKUP' ? 'Local' : 'Long-haul'})</span>
            </div>
            <span class="badge badge-amber">GHS ${job.estimated_cost}</span>
        </div>
        <div class="job-body">
            <div class="job-detail-row">
                <span>Vegetable Cargo:</span>
                <strong class="text-primary">${job.order_details.quantity} ${job.order_details.produce_details.unit} of ${job.order_details.produce_details.variety || job.order_details.produce_details.name}</strong>
            </div>
            <div class="job-detail-row">
                <span>Recommended Vehicle:</span>
                <span>${job.vehicle_type}</span>
            </div>
            <div class="job-detail-row">
                <span>Pickup Farmer:</span>
                <span>${job.order_details.produce_details.farmer_name} (${job.order_details.produce_details.farmer_phone})</span>
            </div>
        </div>
        ${btnHtml}
    `;

    // Action handlers
    if (card.querySelector('.claim-job-btn')) {
        card.querySelector('.claim-job-btn').addEventListener('click', async () => {
            try {
                const res = await fetch(`/api/logistics/jobs/${job.id}/claim/`, { method: 'POST' });
                if (res.ok) {
                    alert("Contract Claimed! You are matched for this delivery. Go to pickup destination.");
                    loadLogisticsJobs();
                }
            } catch (e) {
                console.error(e);
            }
        });
    }

    if (card.querySelector('.pick-job-btn')) {
        card.querySelector('.pick-job-btn').addEventListener('click', async () => {
            try {
                const res = await fetch(`/api/logistics/jobs/${job.id}/update/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'PICKED_UP' })
                });
                if (res.ok) {
                    alert("Status Updated: Cargo Picked Up and In Transit.");
                    loadLogisticsJobs();
                }
            } catch (e) {
                console.error(e);
            }
        });
    }

    if (card.querySelector('.req-payment-btn')) {
        card.querySelector('.req-payment-btn').addEventListener('click', async () => {
            try {
                const res = await fetch(`/api/logistics/jobs/${job.id}/request_payment/`, { method: 'POST', credentials: 'same-origin' });
                if (res.ok) {
                    alert("Payment requested from client.");
                    loadLogisticsJobs();
                } else {
                    const err = await res.json();
                    alert("Failed to request payment: " + (err.detail || JSON.stringify(err)));
                }
            } catch (e) {
                console.error(e);
            }
        });
    }

    if (card.querySelector('.deliver-job-btn')) {
        card.querySelector('.deliver-job-btn').addEventListener('click', async () => {
            try {
                const res = await fetch(`/api/logistics/jobs/${job.id}/update/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'DELIVERED' })
                });
                if (res.ok) {
                    alert("Delivery confirmed. Waiting for buyer delivery verification to release escrow payment.");
                    loadLogisticsJobs();
                }
            } catch (e) {
                console.error(e);
            }
        });
    }

    return card;
}


// -------------------------------------------------------------
// PLANT PATHOLOGY DIAGNOSTIC SCANS
function runDiseaseScanner(file) {
    const progress = document.getElementById('scanner-progress-bar');
    const resultCard = document.getElementById('scanner-result-card');
    const cropName = document.getElementById('scanner-crop-select').value;
    
    progress.style.display = 'block';
    resultCard.style.display = 'none';

    (async () => {
        try {
            const formData = new FormData();
            formData.append('crop_name', cropName);
            formData.append('file', file);

            const res = await fetch('/api/disease-scanner/', {
                method: 'POST',
                body: formData
            });

            if (res.ok) {
                const diag = await res.json();
                
                // Render diagnostic card
                document.getElementById('diag-disease').textContent = diag.diagnosis;
                document.getElementById('diag-confidence').textContent = diag.confidence_score;
                document.getElementById('diag-severity').textContent = diag.severity_level;
                
                const sevBadge = document.getElementById('diag-severity');
                sevBadge.className = 'badge mt-1';
                if (diag.severity_level === 'High') {
                    sevBadge.classList.add('badge-red');
                } else if (diag.severity_level === 'Moderate') {
                    sevBadge.classList.add('badge-orange');
                } else if (diag.severity_level === 'Low') {
                    sevBadge.classList.add('badge-green');
                } else {
                    sevBadge.classList.add('badge-secondary');
                }

                // Show AI source badge
                const sourceBadgeEl = document.getElementById('diag-source-badge');
                if (sourceBadgeEl) {
                    if (diag.source === 'AI_CLOUD') {
                        sourceBadgeEl.innerHTML = '<i class="fa-solid fa-cloud"></i> Live HF Vision AI';
                        sourceBadgeEl.className = 'badge badge-blue';
                    } else if (diag.source === 'LOCAL_CV') {
                        sourceBadgeEl.innerHTML = '<i class="fa-solid fa-microscope"></i> Local Pixel Analysis';
                        sourceBadgeEl.className = 'badge badge-amber';
                    } else {
                        sourceBadgeEl.innerHTML = '<i class="fa-solid fa-database"></i> Crop Advisory';
                        sourceBadgeEl.className = 'badge badge-slate';
                    }
                }

                document.getElementById('diag-treatment').textContent = diag.treatment_plan;
                
                progress.style.display = 'none';
                resultCard.style.display = 'block';
            }
        } catch (e) {
            console.error(e);
            progress.style.display = 'none';
        }
    })();
}


// -------------------------------------------------------------
// AGRIBOT CONVERSATIONAL CHAT LOGIC
async function sendAgriBotMessage() {
    const input = document.getElementById('agribot-user-text');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    
    const messages = document.getElementById('agribot-messages-area');
    
    // Add User Bubble
    const userBubble = document.createElement('div');
    userBubble.className = 'user-msg';
    userBubble.textContent = text;
    messages.appendChild(userBubble);
    messages.scrollTop = messages.scrollHeight;

    // Send to bot endpoint
    try {
        const res = await fetch('/api/agribot/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        if (res.ok) {
            const botData = await res.json();
            
            // Add Bot Bubble
            const botBubble = document.createElement('div');
            botBubble.className = 'bot-msg';
            
            // Format simple markdown links or bold text
            let formattedReply = botData.reply
                .replace(/\n/g, '<br>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>');
                
            botBubble.innerHTML = formattedReply;
            messages.appendChild(botBubble);
            messages.scrollTop = messages.scrollHeight;

            // If bot did an auto listing, update views
            if (text.toLowerCase().includes('harvest') || text.toLowerCase().includes('list') || text.toLowerCase().includes('sell')) {
                loadFarmerListings();
                loadMarketplace();
            }
        }
    } catch (e) {
        console.error(e);
    }
}


// -------------------------------------------------------------
// INTERACTIVE USSD OFFLINE/ONLINE SIMULATOR
function resetUSSD() {
    ussdState = {
        active: false,
        menu: 'dial',
        inputField: '',
        tempData: {}
    };
    
    document.getElementById('ussd-screen-text').innerHTML = `
        Dial <strong style="color: #0b0f19;">*920*44#</strong> to connect to AgriConnect Ghana.
    `;
    document.getElementById('ussd-input-row').style.display = 'none';
    document.getElementById('ussd-user-input').value = '';
    document.getElementById('ussd-btn-send').textContent = 'Dial';
    document.getElementById('ussd-btn-cancel').textContent = 'Cancel';
}

async function handleUSSDInput() {
    const inputEl = document.getElementById('ussd-user-input');
    const val = inputEl.value.trim();
    inputEl.value = '';

    if (!currentUser) {
        document.getElementById('ussd-screen-text').innerHTML = `
            Error: You must be logged into the dashboard to simulate USSD session.<br><br>
            Please close and log in.
        `;
        document.getElementById('ussd-input-row').style.display = 'none';
        return;
    }

    if (ussdState.menu === 'dial') {
        if (val === '*920*44#' || val === '') {
            ussdState.active = true;
            ussdState.menu = 'main';
            showUSSDMainMenu();
            document.getElementById('ussd-input-row').style.display = 'block';
            document.getElementById('ussd-btn-send').textContent = 'Send';
            document.getElementById('ussd-btn-cancel').textContent = 'Exit';
            inputEl.focus();
        } else {
            alert("Invalid USSD String. Try dialing *920*44#");
        }
        return;
    }

    if (val === '0' && ussdState.menu !== 'main') {
        // Go back to main menu
        ussdState.menu = 'main';
        ussdState.tempData = {};
        showUSSDMainMenu();
        inputEl.focus();
        return;
    }

    // --- MAIN MENU OPTION SELECTION ---
    if (ussdState.menu === 'main') {
        if (val === '1') {
            // Option 1: Check Wallet (All roles)
            document.getElementById('ussd-screen-text').innerHTML = `
                AgriConnect Wallet:<br>
                Balance: GHS ${parseFloat(currentUser.wallet_balance).toFixed(2)}<br><br>
                0. Back
            `;
            ussdState.menu = 'back_only';
        } else if (val === '4') {
            ussdState.menu = 'request_connection_phone';
            document.getElementById('ussd-screen-text').innerHTML = `
                Enter mobile phone number to connect:<br><br>
                0. Back
            `;
        } else if (currentUser.role === 'BUYER') {
            if (val === '2') {
                loadUSSDTransporterApprovals();
            } else if (val === '3') {
                loadUSSDConfirmReleases();
            } else {
                showUSSDMainMenu("Invalid option. Try again:");
            }
        } else if (currentUser.role === 'TRANSPORTER') {
            if (val === '2') {
                loadUSSDAvailableContracts();
            } else if (val === '3') {
                loadUSSDActiveCargoes();
            } else {
                showUSSDMainMenu("Invalid option. Try again:");
            }
        } else if (currentUser.role === 'FARMER') {
            if (val === '2') {
                ussdState.menu = 'farmer_tomato_qty';
                document.getElementById('ussd-screen-text').innerHTML = `
                    Enter Tomato Crates yield quantity:
                `;
            } else if (val === '3') {
                loadUSSDDispatchProduceList();
            } else {
                showUSSDMainMenu("Invalid option. Try again:");
            }
        } else {
            showUSSDMainMenu("Invalid option. Try again:");
        }
        return;
    }

    if (ussdState.menu === 'request_connection_phone') {
        if (!val) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Error: Phone number cannot be empty.<br><br>
                0. Back
            `;
            return;
        }
        submitUSSDConnectionRequest(val);
        return;
    }

    // --- BUYER USSD FLOWS ---
    if (ussdState.menu === 'buyer_approvals_list') {
        const idx = parseInt(val);
        const orders = ussdState.tempData.orders || [];
        if (isNaN(idx) || idx < 1 || idx > orders.length) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid selection. Try again:<br>
                ${ussdState.tempData.listText}
                0. Back
            `;
            return;
        }
        const order = orders[idx - 1];
        ussdState.tempData.selectedOrder = order;
        ussdState.menu = 'buyer_approval_action';
        document.getElementById('ussd-screen-text').innerHTML = `
            Order #${order.id} Match:<br>
            Driver: ${order.transporter_details.username}<br>
            Fee: GHS ${parseFloat(order.transporter_details.estimated_cost).toFixed(2)}<br><br>
            1. Approve Driver<br>
            2. Reject Driver<br>
            0. Back
        `;
        return;
    }

    if (ussdState.menu === 'buyer_approval_action') {
        const order = ussdState.tempData.selectedOrder;
        if (val === '1') {
            submitUSSDApproval(order.transporter_details.job_id, 'approve');
        } else if (val === '2') {
            submitUSSDApproval(order.transporter_details.job_id, 'reject');
        } else {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid option. Choose action:<br>
                1. Approve Driver<br>
                2. Reject Driver<br>
                0. Back
            `;
        }
        return;
    }

    if (ussdState.menu === 'buyer_releases_list') {
        const idx = parseInt(val);
        const orders = ussdState.tempData.orders || [];
        if (isNaN(idx) || idx < 1 || idx > orders.length) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid selection. Try again:<br>
                ${ussdState.tempData.listText}
                0. Back
            `;
            return;
        }
        const order = orders[idx - 1];
        ussdState.tempData.selectedOrder = order;
        ussdState.menu = 'buyer_release_confirm';
        document.getElementById('ussd-screen-text').innerHTML = `
            Release GHS ${parseFloat(order.total_price).toFixed(2)} to Farmer ${order.produce_details.farmer_name}?<br><br>
            1. Confirm Release<br>
            0. Back
        `;
        return;
    }

    if (ussdState.menu === 'buyer_release_confirm') {
        if (val === '1') {
            submitUSSDRelease(ussdState.tempData.selectedOrder.id);
        } else {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid option:<br>
                1. Confirm Release<br>
                0. Back
            `;
        }
        return;
    }

    // --- TRANSPORTER USSD FLOWS ---
    if (ussdState.menu === 'transporter_claim_list') {
        const idx = parseInt(val);
        const jobs = ussdState.tempData.jobs || [];
        if (isNaN(idx) || idx < 1 || idx > jobs.length) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid selection. Try again:<br>
                ${ussdState.tempData.listText}
                0. Back
            `;
            return;
        }
        const job = jobs[idx - 1];
        ussdState.tempData.selectedJob = job;
        ussdState.menu = 'transporter_claim_confirm';
        document.getElementById('ussd-screen-text').innerHTML = `
            Claim delivery matching for Order #${job.order}? Est. Fee: GHS ${parseFloat(job.estimated_cost).toFixed(2)}<br><br>
            1. Confirm Claim<br>
            0. Back
        `;
        return;
    }

    if (ussdState.menu === 'transporter_claim_confirm') {
        if (val === '1') {
            submitUSSDClaim(ussdState.tempData.selectedJob.id);
        } else {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid option:<br>
                1. Confirm Claim<br>
                0. Back
            `;
        }
        return;
    }

    if (ussdState.menu === 'transporter_active_list') {
        const idx = parseInt(val);
        const jobs = ussdState.tempData.jobs || [];
        if (isNaN(idx) || idx < 1 || idx > jobs.length) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid selection. Try again:<br>
                ${ussdState.tempData.listText}
                0. Back
            `;
            return;
        }
        const job = jobs[idx - 1];
        ussdState.tempData.selectedJob = job;
        ussdState.menu = 'transporter_update_action';
        const label = job.status === 'MATCHED' ? 'Mark Picked Up / In Transit' : 'Mark Delivered';
        document.getElementById('ussd-screen-text').innerHTML = `
            Cargo Status Update:<br>
            Order #${job.order}<br>
            Current: ${job.status}<br><br>
            1. ${label}<br>
            0. Back
        `;
        return;
    }

    if (ussdState.menu === 'transporter_update_action') {
        if (val === '1') {
            const job = ussdState.tempData.selectedJob;
            const targetStatus = job.status === 'MATCHED' ? 'PICKED_UP' : 'DELIVERED';
            submitUSSDStatusUpdate(job.id, targetStatus);
        } else {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid option. Choose action:<br>
                1. Update Status<br>
                0. Back
            `;
        }
        return;
    }

    // --- FARMER USSD FLOWS ---
    if (ussdState.menu === 'farmer_tomato_qty') {
        const qty = parseInt(val);
        if (isNaN(qty) || qty <= 0) {
            document.getElementById('ussd-screen-text').textContent = "Invalid qty. Enter Tomato Crates quantity:";
            return;
        }
        ussdState.tempData.qty = qty;
        ussdState.menu = 'farmer_tomato_price';
        document.getElementById('ussd-screen-text').textContent = "Enter Price per Crate (GHS):";
        return;
    }

    if (ussdState.menu === 'farmer_tomato_price') {
        const price = parseFloat(val);
        if (isNaN(price) || price <= 0) {
            document.getElementById('ussd-screen-text').textContent = "Invalid price. Enter Price per Crate (GHS):";
            return;
        }
        submitUSSDFarmerTomato(ussdState.tempData.qty, price);
        return;
    }

    if (ussdState.menu === 'farmer_dispatch_produce_list') {
        const idx = parseInt(val);
        const produces = ussdState.tempData.produces || [];
        if (isNaN(idx) || idx < 1 || idx > produces.length) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid selection. Try again:<br>
                ${ussdState.tempData.listText}
                0. Back
            `;
            return;
        }
        const prod = produces[idx - 1];
        ussdState.tempData.selectedProduce = prod;
        loadUSSDFarmerBuyersList();
        return;
    }

    if (ussdState.menu === 'farmer_dispatch_buyer_list') {
        const idx = parseInt(val);
        const buyers = ussdState.tempData.buyers || [];
        if (isNaN(idx) || idx < 1 || idx > buyers.length) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid selection. Try again:<br>
                ${ussdState.tempData.listText}
                0. Back
            `;
            return;
        }
        const buyer = buyers[idx - 1];
        ussdState.tempData.selectedBuyer = buyer;
        ussdState.menu = 'farmer_dispatch_qty';
        document.getElementById('ussd-screen-text').innerHTML = `
            Enter quantity to dispatch (max ${ussdState.tempData.selectedProduce.quantity_available}):
        `;
        return;
    }

    if (ussdState.menu === 'farmer_dispatch_qty') {
        const qty = parseInt(val);
        const max = ussdState.tempData.selectedProduce.quantity_available;
        if (isNaN(qty) || qty < 1 || qty > max) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid quantity. Enter quantity to dispatch (max ${max}):
            `;
            return;
        }
        ussdState.tempData.qty = qty;
        ussdState.menu = 'farmer_dispatch_confirm';
        document.getElementById('ussd-screen-text').innerHTML = `
            Dispatch ${qty} to ${ussdState.tempData.selectedBuyer.username}?<br><br>
            1. Confirm Dispatch<br>
            0. Back
        `;
        return;
    }

    if (ussdState.menu === 'farmer_dispatch_confirm') {
        if (val === '1') {
            submitUSSDDispatch(
                ussdState.tempData.selectedProduce.id,
                ussdState.tempData.selectedBuyer.id,
                ussdState.tempData.qty
            );
        } else {
            document.getElementById('ussd-screen-text').innerHTML = `
                Invalid option:<br>
                1. Confirm Dispatch<br>
                0. Back
            `;
        }
        return;
    }

    if (ussdState.menu === 'back_only') {
        resetUSSD();
        return;
    }
}

function showUSSDMainMenu(msgPrefix = "") {
    let screenHtml = msgPrefix ? `${msgPrefix}<br>` : "AgriConnect Market:<br>";
    screenHtml += "1. Check Wallet<br>";
    if (currentUser.role === 'BUYER') {
        screenHtml += "2. Transporter Approvals<br>3. Confirm Escrow Releases<br>4. Connect via Phone";
    } else if (currentUser.role === 'TRANSPORTER') {
        screenHtml += "2. Claim Available Contracts<br>3. My Active Cargoes<br>4. Connect via Phone";
    } else if (currentUser.role === 'FARMER') {
        screenHtml += "2. List Tomato Harvest<br>3. Dispatch Cargo to Buyer<br>4. Connect via Phone";
    }
    document.getElementById('ussd-screen-text').innerHTML = screenHtml;
}

// --- Dynamic API Loaders for USSD Menu Flows ---

async function loadUSSDTransporterApprovals() {
    try {
        const res = await fetch('/api/orders/create/');
        if (!res.ok) return;
        const orders = await res.json();
        
        const pending = orders.filter(o => o.transporter_details && o.transporter_details.status === 'PENDING_APPROVAL');
        ussdState.tempData.orders = pending;
        ussdState.menu = 'buyer_approvals_list';
        
        if (pending.length === 0) {
            document.getElementById('ussd-screen-text').innerHTML = `
                No transporter claims pending approval.<br><br>
                0. Back
            `;
            return;
        }
        
        let listText = "Select driver match:<br>";
        pending.forEach((o, i) => {
            listText += `${i + 1}. Order #${o.id} - ${o.transporter_details.username}<br>`;
        });
        ussdState.tempData.listText = listText;
        
        document.getElementById('ussd-screen-text').innerHTML = `${listText}<br>0. Back`;
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function loadUSSDConfirmReleases() {
    try {
        const res = await fetch('/api/orders/create/');
        if (!res.ok) return;
        const orders = await res.json();
        
        const releases = orders.filter(o => o.payment_status === 'HELD_IN_ESCROW' && o.status === 'DELIVERED');
        ussdState.tempData.orders = releases;
        ussdState.menu = 'buyer_releases_list';
        
        if (releases.length === 0) {
            document.getElementById('ussd-screen-text').innerHTML = `
                No delivered orders awaiting escrow release.<br><br>
                0. Back
            `;
            return;
        }
        
        let listText = "Select order to release:<br>";
        releases.forEach((o, i) => {
            listText += `${i + 1}. Order #${o.id} - GHS ${o.total_price}<br>`;
        });
        ussdState.tempData.listText = listText;
        
        document.getElementById('ussd-screen-text').innerHTML = `${listText}<br>0. Back`;
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function loadUSSDAvailableContracts() {
    try {
        const res = await fetch('/api/logistics/jobs/');
        if (!res.ok) return;
        const jobs = await res.json();
        
        ussdState.tempData.jobs = jobs;
        ussdState.menu = 'transporter_claim_list';
        
        if (jobs.length === 0) {
            document.getElementById('ussd-screen-text').innerHTML = `
                No available transport contracts.<br><br>
                0. Back
            `;
            return;
        }
        
        let listText = "Select job to claim:<br>";
        jobs.forEach((j, i) => {
            listText += `${i + 1}. Order #${j.order} - GHS ${parseFloat(j.estimated_cost).toFixed(2)}<br>`;
        });
        ussdState.tempData.listText = listText;
        
        document.getElementById('ussd-screen-text').innerHTML = `${listText}<br>0. Back`;
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function loadUSSDActiveCargoes() {
    try {
        const res = await fetch('/api/logistics/jobs/?claimed=true');
        if (!res.ok) return;
        const jobs = await res.json();
        
        const active = jobs.filter(j => j.status === 'MATCHED' || j.status === 'PICKED_UP');
        ussdState.tempData.jobs = active;
        ussdState.menu = 'transporter_active_list';
        
        if (active.length === 0) {
            document.getElementById('ussd-screen-text').innerHTML = `
                No active delivery cargoes.<br><br>
                0. Back
            `;
            return;
        }
        
        let listText = "Select active cargo:<br>";
        active.forEach((j, i) => {
            listText += `${i + 1}. Order #${j.order} (${j.status})<br>`;
        });
        ussdState.tempData.listText = listText;
        
        document.getElementById('ussd-screen-text').innerHTML = `${listText}<br>0. Back`;
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function loadUSSDDispatchProduceList() {
    try {
        const res = await fetch(`/api/produce/?farmer=${currentUser.id}`);
        if (!res.ok) return;
        const produces = await res.json();
        
        const available = produces.filter(p => p.status === 'AVAILABLE');
        ussdState.tempData.produces = available;
        ussdState.menu = 'farmer_dispatch_produce_list';
        
        if (available.length === 0) {
            document.getElementById('ussd-screen-text').innerHTML = `
                You have no available produce listed.<br><br>
                0. Back
            `;
            return;
        }
        
        let listText = "Select produce:<br>";
        available.forEach((p, i) => {
            listText += `${i + 1}. ${p.variety || p.name} (${p.quantity_available} left)<br>`;
        });
        ussdState.tempData.listText = listText;
        
        document.getElementById('ussd-screen-text').innerHTML = `${listText}<br>0. Back`;
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function loadUSSDFarmerBuyersList() {
    try {
        const res = await fetch('/api/connections/');
        if (!res.ok) return;
        const data = await res.json();
        
        const buyers = data.connections.map(c => c.user).filter(u => u.role === 'BUYER');
        ussdState.tempData.buyers = buyers;
        ussdState.menu = 'farmer_dispatch_buyer_list';
        
        if (buyers.length === 0) {
            document.getElementById('ussd-screen-text').innerHTML = `
                No connected buyers found in your circle.<br><br>
                0. Back
            `;
            return;
        }
        
        let listText = "Select buyer client:<br>";
        buyers.forEach((b, i) => {
            listText += `${i + 1}. ${b.username}<br>`;
        });
        ussdState.tempData.listText = listText;
        
        document.getElementById('ussd-screen-text').innerHTML = `${listText}<br>0. Back`;
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

// --- Submit Actions ---

async function submitUSSDApproval(jobId, action) {
    try {
        const res = await fetch(`/api/logistics/jobs/${jobId}/approve/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });
        
        if (res.ok) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Transporter match ${action}d successfully!<br><br>
                0. Main Menu
            `;
            ussdState.menu = 'back_only';
            loadOrders();
        } else {
            const err = await res.json();
            document.getElementById('ussd-screen-text').innerHTML = `
                Action failed:<br>
                ${err.detail || JSON.stringify(err)}<br><br>
                0. Back
            `;
        }
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function submitUSSDConnectionRequest(phone) {
    try {
        const res = await fetch('/api/connections/request/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone_number: phone })
        });
        const data = await res.json();
        
        if (res.ok) {
            let msg = "Connection request sent successfully!";
            if (data.status === 'ACCEPTED') {
                msg = `Connection accepted! You are now connected with ${data.receiver_username || data.sender_username}.`;
            }
            document.getElementById('ussd-screen-text').innerHTML = `
                ${msg}<br><br>
                0. Main Menu
            `;
        } else {
            document.getElementById('ussd-screen-text').innerHTML = `
                Error:<br>
                ${data.detail || 'Could not send request.'}<br><br>
                0. Back
            `;
        }
        ussdState.menu = 'back_only';
    } catch (e) {
        console.error(e);
        document.getElementById('ussd-screen-text').innerHTML = `
            Error sending request. Please check connection.<br><br>
            0. Back
        `;
        ussdState.menu = 'back_only';
    }
}

async function submitUSSDRelease(orderId) {
    try {
        const res = await fetch(`/api/orders/${orderId}/confirm-delivery/`, { method: 'POST' });
        if (res.ok) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Escrow payment released successfully to farmer!<br><br>
                0. Main Menu
            `;
            ussdState.menu = 'back_only';
            loadOrders();
            loadProfileData();
        } else {
            const err = await res.json();
            document.getElementById('ussd-screen-text').innerHTML = `
                Release failed:<br>
                ${err.detail || JSON.stringify(err)}<br><br>
                0. Back
            `;
        }
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function submitUSSDClaim(jobId) {
    try {
        const res = await fetch(`/api/logistics/jobs/${jobId}/claim/`, { method: 'POST' });
        if (res.ok) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Claim successful!<br>
                Awaiting Buyer approval.<br><br>
                0. Main Menu
            `;
            ussdState.menu = 'back_only';
            if (currentTab === 'logistics') loadLogisticsJobs();
        } else {
            const err = await res.json();
            document.getElementById('ussd-screen-text').innerHTML = `
                Claim failed:<br>
                ${err.detail || JSON.stringify(err)}<br><br>
                0. Back
            `;
        }
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function submitUSSDStatusUpdate(jobId, newStatus) {
    try {
        const res = await fetch(`/api/logistics/jobs/${jobId}/update/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (res.ok) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Status updated to ${newStatus === 'PICKED_UP' ? 'In Transit' : 'Delivered'}!<br><br>
                0. Main Menu
            `;
            ussdState.menu = 'back_only';
            if (currentTab === 'logistics') loadLogisticsJobs();
        } else {
            const err = await res.json();
            document.getElementById('ussd-screen-text').innerHTML = `
                Update failed:<br>
                ${err.detail || JSON.stringify(err)}<br><br>
                0. Back
            `;
        }
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function submitUSSDFarmerTomato(qty, price) {
    try {
        const harvestDate = new Date().toISOString().split('T')[0];
        const res = await fetch('/api/produce/create/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: 'Tomatoes',
                variety: 'Local Tomato',
                quantity_available: qty,
                unit: 'Crates',
                price_per_unit: price,
                harvest_date: harvestDate,
                description: 'Uploaded via USSD offline code.'
            })
        });
        
        if (res.ok) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Tomato harvest listed successfully!<br>
                ${qty} Crates at GHS ${price}.<br><br>
                0. Main Menu
            `;
            ussdState.menu = 'back_only';
            loadFarmerListings();
            loadMarketplace();
        } else {
            const err = await res.json();
            document.getElementById('ussd-screen-text').innerHTML = `
                Listing failed:<br>
                ${err.detail || JSON.stringify(err)}<br><br>
                0. Back
            `;
        }
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

async function submitUSSDDispatch(produceId, buyerId, qty) {
    try {
        const res = await fetch('/api/orders/dispatch/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                produce: produceId,
                buyer: buyerId,
                quantity: qty
            })
        });
        
        if (res.ok) {
            document.getElementById('ussd-screen-text').innerHTML = `
                Produce dispatch order created successfully!<br><br>
                0. Main Menu
            `;
            ussdState.menu = 'back_only';
            loadFarmerListings();
            loadMarketplace();
        } else {
            const err = await res.json();
            document.getElementById('ussd-screen-text').innerHTML = `
                Dispatch failed:<br>
                ${err.detail || JSON.stringify(err)}<br><br>
                0. Back
            `;
        }
    } catch (e) {
        console.error(e);
        resetUSSD();
    }
}

// Show animated SMS drop notification toast on mockup screen
function showSMSNotification(text) {
    const sms = document.getElementById('sms-notification');
    document.getElementById('sms-text').textContent = text;
    
    sms.style.display = 'flex';
    
    // Auto hide after 4.5 seconds
    setTimeout(() => {
        sms.style.display = 'none';
    }, 4500);
}


// --- Cart Functions ---
async function updateCartBadge() {
    if (!currentUser || currentUser.role !== 'BUYER') {
        const headerCartBtn = document.getElementById('header-cart-btn');
        if (headerCartBtn) headerCartBtn.style.display = 'none';
        const sidebarCartBadge = document.getElementById('sidebar-cart-badge');
        if (sidebarCartBadge) sidebarCartBadge.style.display = 'none';
        return;
    }

    try {
        const res = await fetch('/api/cart/');
        if (res.ok) {
            const items = await res.json();
            const count = items.reduce((sum, item) => sum + item.quantity, 0);
            
            const headerCartBtn = document.getElementById('header-cart-btn');
            const headerCartBadge = document.getElementById('header-cart-badge');
            const sidebarCartBadge = document.getElementById('sidebar-cart-badge');
            
            if (headerCartBtn) headerCartBtn.style.display = 'block';
            if (headerCartBadge) headerCartBadge.textContent = count;
            
            if (sidebarCartBadge) {
                if (count > 0) {
                    sidebarCartBadge.style.display = 'inline-block';
                    sidebarCartBadge.textContent = count;
                } else {
                    sidebarCartBadge.style.display = 'none';
                }
            }
        }
    } catch (e) {
        console.error("Error updating cart badge:", e);
    }
}

async function addToCart(produceId, qty) {
    try {
        const res = await fetch('/api/cart/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ produce: produceId, quantity: qty })
        });
        if (res.ok) {
            alert("Added to cart successfully!");
            updateCartBadge();
        } else {
            const err = await res.json();
            if (err.not_connected) {
                if (confirm(err.detail + "\nWould you like to open the My Circle tab to send a connection request?")) {
                    switchTab('network');
                }
            } else {
                alert("Failed to add to cart: " + (err.detail || JSON.stringify(err)));
            }
        }
    } catch (e) {
        console.error("Error adding to cart:", e);
    }
}

async function removeFromCart(itemId) {
    try {
        const res = await fetch(`/api/cart/${itemId}/`, { method: 'DELETE' });
        if (res.ok) {
            loadCart();
            updateCartBadge();
        } else {
            alert("Failed to remove item.");
        }
    } catch (e) {
        console.error("Error removing from cart:", e);
    }
}
window.removeFromCart = removeFromCart;

async function loadCart() {
    try {
        const res = await fetch('/api/cart/');
        if (!res.ok) return;
        const items = await res.json();
        
        const container = document.getElementById('cart-items-container');
        container.innerHTML = '';
        
        let produceTotal = 0;
        let logisticsTotal = 0;
        
        if (items.length === 0) {
            container.innerHTML = '<div class="text-secondary text-center p-4">Your cart is empty.</div>';
        } else {
            items.forEach(item => {
                const sub = item.subtotal;
                const log = item.estimated_logistics;
                produceTotal += sub;
                logisticsTotal += log;
                
                const card = document.createElement('div');
                card.className = 'cart-item-card';
                card.innerHTML = `
                    <div class="cart-item-title-row">
                        <div>
                            <strong class="cart-item-name">${item.produce_details.variety || item.produce_details.name}</strong>
                            <div class="cart-item-variety">${item.produce_details.name}</div>
                        </div>
                        <button class="cart-item-remove-btn" onclick="removeFromCart(${item.id})">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                    <div class="cart-item-details">
                        <span>Quantity: <strong>${item.quantity} ${item.produce_details.unit}</strong></span>
                        <span class="cart-item-subtotal">GHS ${sub.toFixed(2)}</span>
                    </div>
                    <div class="cart-item-logistics">
                        <i class="fa-solid fa-truck"></i> Est. Logistics: GHS ${log.toFixed(2)}
                    </div>
                `;
                container.appendChild(card);
            });
        }
        
        const grandTotal = produceTotal + logisticsTotal;
        document.getElementById('cart-produce-total').textContent = `GHS ${produceTotal.toFixed(2)}`;
        document.getElementById('cart-logistics-total').textContent = `GHS ${logisticsTotal.toFixed(2)}`;
        document.getElementById('cart-grand-total').textContent = `GHS ${grandTotal.toFixed(2)}`;
        
        // Show modal
        document.getElementById('cart-modal').style.display = 'flex';
    } catch (e) {
        console.error("Error loading cart:", e);
    }
}

async function checkoutCart() {
    try {
        const res = await fetch('/api/cart/checkout/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        
        if (res.status === 201) {
            document.getElementById('cart-modal').style.display = 'none';
            alert("Checkout successful! Orders created and payments secured in platform escrow.");
            loadProfileData(); // updates header wallet balance
            updateCartBadge();
            switchTab('orders');
        } else if (res.status === 402 && data.needs_topup) {
            // Insufficient wallet balance, ask to top up
            if (confirm(`Insufficient balance. Cart total requires GHS ${data.shortfall.toFixed(2)} more. Would you like to fund your wallet now?`)) {
                document.getElementById('cart-modal').style.display = 'none';
                openTopUpModal(data.shortfall);
            }
        } else {
            if (data.not_connected) {
                if (confirm(data.detail + "\nWould you like to open the My Circle tab to join their circle of trust?")) {
                    document.getElementById('cart-modal').style.display = 'none';
                    switchTab('network');
                }
            } else {
                alert("Checkout failed: " + (data.detail || JSON.stringify(data)));
            }
        }
    } catch (e) {
        console.error("Error during checkout:", e);
    }
}

// --- Paystack Wallet Top-Up ---
function openTopUpModal(suggestedAmount = 50) {
    document.getElementById('topup-amount').value = Math.ceil(suggestedAmount);
    document.getElementById('topup-modal').style.display = 'flex';
}

async function initPaystackTopUp() {
    const amountInput = document.getElementById('topup-amount');
    const amount = parseFloat(amountInput.value);
    const errorDiv = document.getElementById('topup-error');
    const confirmBtn = document.getElementById('topup-btn-confirm');
    const btnText = confirmBtn.querySelector('.btn-text');
    const spinner = confirmBtn.querySelector('.spinner');
    
    errorDiv.style.display = 'none';
    
    if (isNaN(amount) || amount < 1) {
        errorDiv.textContent = "Minimum top-up amount is GHS 1";
        errorDiv.style.display = 'block';
        return;
    }
    
    // UI Loading state
    btnText.style.display = 'none';
    spinner.style.display = 'inline-block';
    confirmBtn.disabled = true;
    
    try {
        const res = await fetch('/api/payments/initialize/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: amount })
        });
        const data = await res.json();
        
        if (res.ok) {
            document.getElementById('topup-modal').style.display = 'none';
            
            const handler = PaystackPop.setup({
                key: data.public_key,
                email: currentUser.username + '@agriconnect.gh',
                amount: Math.round(amount * 100),
                currency: 'GHS',
                ref: data.reference,
                callback: function(response) {
                    verifyPayment(response.reference);
                },
                onClose: function() {
                    alert('Payment cancelled.');
                }
            });
            handler.openIframe();
        } else {
            errorDiv.textContent = "Initialization failed: " + (data.detail || JSON.stringify(data));
            errorDiv.style.display = 'block';
        }
    } catch (e) {
        errorDiv.textContent = "Error initializing Paystack. Please try again.";
        errorDiv.style.display = 'block';
        console.error("Error initializing Paystack:", e);
    } finally {
        btnText.style.display = 'inline-block';
        spinner.style.display = 'none';
        confirmBtn.disabled = false;
    }
}

async function verifyPayment(reference) {
    try {
        const res = await fetch(`/api/payments/verify/${reference}/`);
        const data = await res.json();
        if (res.ok) {
            alert(`Payment verified! ${data.message}`);
            loadProfileData(); // update wallet balance
            loadWalletTransactions();
        } else {
            alert("Verification failed: " + (data.detail || JSON.stringify(data)));
        }
    } catch (e) {
        console.error("Error verifying payment:", e);
    }
}

// --- Withdrawal ---
function openWithdrawModal() {
    document.getElementById('withdraw-amount').value = '';
    document.getElementById('withdraw-account-number').value = currentUser.phone_number || '';
    document.getElementById('withdraw-modal').style.display = 'flex';
}

async function submitWithdrawal(e) {
    e.preventDefault();
    const amount = parseFloat(document.getElementById('withdraw-amount').value);
    const channel = document.getElementById('withdraw-channel').value;
    const account_number = document.getElementById('withdraw-account-number').value;
    const bank_code = document.getElementById('withdraw-bank-code').value;
    
    const errorDiv = document.getElementById('withdraw-error');
    const submitBtn = document.getElementById('withdraw-btn-submit');
    const btnText = submitBtn.querySelector('.btn-text');
    const spinner = submitBtn.querySelector('.spinner');
    
    errorDiv.style.display = 'none';
    
    if (isNaN(amount) || amount < 1) {
        errorDiv.textContent = "Minimum withdrawal is GHS 1";
        errorDiv.style.display = 'block';
        return;
    }
    
    btnText.style.display = 'none';
    spinner.style.display = 'inline-block';
    submitBtn.disabled = true;
    
    try {
        const res = await fetch('/api/payments/withdraw/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                amount: amount,
                channel: channel,
                account_number: account_number,
                bank_code: channel === 'bank_account' ? bank_code : ''
            })
        });
        const data = await res.json();
        
        if (res.ok) {
            alert(`Withdrawal successful! ${data.message}`);
            document.getElementById('withdraw-modal').style.display = 'none';
            loadProfileData();
            loadWalletTransactions();
        } else {
            errorDiv.textContent = "Withdrawal failed: " + (data.detail || JSON.stringify(data));
            errorDiv.style.display = 'block';
        }
    } catch (e) {
        errorDiv.textContent = "Error processing withdrawal. Please try again.";
        errorDiv.style.display = 'block';
        console.error("Error processing withdrawal:", e);
    } finally {
        btnText.style.display = 'inline-block';
        spinner.style.display = 'none';
        submitBtn.disabled = false;
    }
}

// --- Wallet Transactions History ---
async function loadWalletTransactions() {
    if (currentTab !== 'analytics') return;
    
    try {
        const res = await fetch('/api/payments/transactions/');
        if (!res.ok) return;
        const txns = await res.json();
        
        const body = document.getElementById('wallet-transactions-body');
        if (!body) return;
        
        body.innerHTML = '';
        if (txns.length === 0) {
            body.innerHTML = '<tr><td colspan="5" class="text-center text-secondary">No transaction records found.</td></tr>';
            return;
        }
        
        txns.forEach(txn => {
            const tr = document.createElement('tr');
            
            const dateStr = new Date(txn.created_at).toLocaleDateString('en-US', {
                month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
            });
            
            let typeBadge = '';
            if (txn.transaction_type === 'TOPUP') {
                typeBadge = '<span class="badge badge-green">Deposit</span>';
            } else if (txn.transaction_type === 'PAYMENT') {
                typeBadge = '<span class="badge badge-orange">Payment</span>';
            } else if (txn.transaction_type === 'PAYOUT') {
                typeBadge = '<span class="badge badge-blue">Payout</span>';
            }
            
            const amountClass = txn.transaction_type === 'TOPUP' ? 'text-emerald' : 'text-orange';
            const prefix = txn.transaction_type === 'TOPUP' ? '+' : '-';
            
            tr.innerHTML = `
                <td>${dateStr}</td>
                <td><span class="font-xxs text-secondary">${txn.reference}</span></td>
                <td>${typeBadge}</td>
                <td>${txn.description}</td>
                <td><strong class="${amountClass}">${prefix} GHS ${txn.amount}</strong></td>
            `;
            body.appendChild(tr);
        });
    } catch (e) {
        console.error("Error loading wallet transactions:", e);
    }
}


// --- Driver Booking & Dispatch ---
async function loadTransportersForMap() {
    if (!map) return;
    try {
        const res = await fetch('/api/users/list/?role=TRANSPORTER');
        if (!res.ok) return;
        const drivers = await res.json();
        
        drivers.forEach(d => {
            const markerHtmlStyles = `
                background-color: #3b82f6;
                width: 16px;
                height: 16px;
                display: block;
                border-radius: 50%;
                border: 2px solid #fff;
                box-shadow: 0 0 8px rgba(0,0,0,0.5);
            `;
            
            const customIcon = L.divIcon({
                className: "my-custom-pin-driver",
                iconAnchor: [8, 8],
                html: `<span style="${markerHtmlStyles}" />`
            });
            
            const m = L.marker([d.latitude, d.longitude], { icon: customIcon })
                .addTo(map)
                .bindPopup(`
                    <div style="font-family: inherit; font-size: 11px; color:#fff; padding: 4px;">
                        <strong style="color:#3b82f6; font-size:13px;">${d.username}</strong><br>
                        <span>Transporter / Driver</span><br>
                        <span>Location: ${d.district}, ${d.region}</span><br>
                        <span>Phone: ${d.phone_number}</span><br>
                        <button class="btn btn-primary btn-xs mt-2" onclick="selectDriverFromMap(${d.id}, '${d.username}')" style="font-size: 10px; padding: 4px 8px; width: auto; background: var(--blue-accent); color: #fff;">
                            <i class="fa-solid fa-check"></i> Select Driver
                        </button>
                    </div>
                `);
            mapMarkers.push(m);
        });
    } catch (e) {
        console.error("Error loading transporters on map: ", e);
    }
}

window.selectDriverFromMap = function(driverId, driverName) {
    switchTab('logistics');
    setTimeout(() => {
        const dispatchSelect = document.getElementById('dispatch-driver');
        if (dispatchSelect) {
            dispatchSelect.value = driverId;
            if (map) map.closePopup();
            alert(`Selected driver: ${driverName}`);
        }
    }, 150);
};

async function loadFarmerDispatchDropdowns() {
    try {
        // Fetch and populate produce listings
        const res = await fetch(`/api/produce/?farmer=${currentUser.id}`);
        if (res.ok) {
            const list = await res.json();
            const prodSelect = document.getElementById('dispatch-produce');
            if (prodSelect) {
                prodSelect.innerHTML = '<option value="">-- Choose Listing to Ship --</option>';
                list.filter(p => p.status === 'AVAILABLE' && p.quantity_available > 0).forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = `${p.variety || p.name} (${p.quantity_available} ${p.unit} available)`;
                    prodSelect.appendChild(opt);
                });
            }
        }

        // Fetch and populate buyers and drivers from connections
        const connRes = await fetch('/api/users/connections/');
        if (connRes.ok) {
            const connData = await connRes.json();
            const connectedUsers = connData.connections.map(c => c.user);
            
            const buyers = connectedUsers.filter(u => u.role === 'BUYER');
            const buyerSelect = document.getElementById('dispatch-buyer');
            if (buyerSelect) {
                buyerSelect.innerHTML = '<option value="">-- Choose Client / Buyer --</option>';
                buyers.forEach(b => {
                    const opt = document.createElement('option');
                    opt.value = b.id;
                    opt.textContent = `${b.username} (${b.district}, ${b.region})`;
                    buyerSelect.appendChild(opt);
                });
            }

            const drivers = connectedUsers.filter(u => u.role === 'TRANSPORTER');
            const driverSelect = document.getElementById('dispatch-driver');
            if (driverSelect) {
                driverSelect.innerHTML = '<option value="">No Driver Pre-Assigned (Post to Marketplace)</option>';
                drivers.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.id;
                    opt.textContent = `${d.username} (${d.district})`;
                    driverSelect.appendChild(opt);
                });
            }
        }
    } catch (e) {
        console.error("Error loading dispatch dropdowns: ", e);
    }
}

function createFarmerJobCard(job) {
    const card = document.createElement('div');
    card.className = 'job-card';
    
    // Status Badge styling
    let statusBadge = '';
    if (job.status === 'PENDING_MATCH') {
        statusBadge = `<span class="badge badge-slate">Pending Driver Match</span>`;
    } else if (job.status === 'MATCHED') {
        statusBadge = `<span class="badge badge-blue">Driver Assigned</span>`;
    } else if (job.status === 'PICKED_UP') {
        statusBadge = `<span class="badge badge-orange">Picked Up / In Transit</span>`;
    } else if (job.status === 'DELIVERED') {
        statusBadge = `<span class="badge badge-green">Delivered</span>`;
    }

    // Payment Status Badge styling
    let paymentBadge = '';
    if (job.order_details.payment_status === 'UNPAID') {
        paymentBadge = `<span class="badge badge-red">Invoice Unpaid by Client</span>`;
    } else if (job.order_details.payment_status === 'HELD_IN_ESCROW') {
        paymentBadge = `<span class="badge badge-orange">Payment in Escrow</span>`;
    } else if (job.order_details.payment_status === 'RELEASED') {
        paymentBadge = `<span class="badge badge-green">Payment Released</span>`;
    }

    // Driver details
    let driverInfo = '';
    if (job.transporter_name) {
        driverInfo = `
            <div class="job-detail-row">
                <span>Driver:</span>
                <strong>${job.transporter_name} (${job.transporter_phone || 'No phone'})</strong>
            </div>
            <div class="job-detail-row">
                <span>Vehicle Mode:</span>
                <span>${job.vehicle_type}</span>
            </div>
        `;
    } else {
        driverInfo = `
            <div class="job-detail-row">
                <span>Driver:</span>
                <span class="text-orange">No driver matched yet</span>
            </div>
            <div class="job-detail-row">
                <span>Vehicle Mode:</span>
                <span>${job.vehicle_type}</span>
            </div>
        `;
    }

    card.innerHTML = `
        <div class="job-header">
            <div class="job-route">
                <span>Shipment #${job.id}</span>
                <i class="fa-solid fa-arrow-right"></i>
                <span>Client: ${job.order_details.buyer_name}</span>
            </div>
            <span class="badge badge-amber">GHS ${job.estimated_cost}</span>
        </div>
        <div class="job-body">
            <div class="job-detail-row">
                <span>Vegetable Cargo:</span>
                <strong class="text-primary">${job.order_details.quantity} ${job.order_details.produce_details.unit} of ${job.order_details.produce_details.variety || job.order_details.produce_details.name}</strong>
            </div>
            <div class="job-detail-row">
                <span>Delivery Status:</span>
                <span>${statusBadge}</span>
            </div>
            <div class="job-detail-row">
                <span>Client Payment:</span>
                <span>${paymentBadge}</span>
            </div>
            ${driverInfo}
        </div>
    `;
    return card;
}

async function submitDispatch(e) {
    e.preventDefault();
    const produce = document.getElementById('dispatch-produce').value;
    const buyer = document.getElementById('dispatch-buyer').value;
    const quantity = document.getElementById('dispatch-qty').value;
    const driver = document.getElementById('dispatch-driver').value;

    const errorDiv = document.getElementById('dispatch-error');
    const successDiv = document.getElementById('dispatch-success');
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';

    if (!produce || !buyer || !quantity) {
        errorDiv.textContent = "Please fill in all required fields.";
        errorDiv.style.display = 'block';
        return;
    }

    try {
        const res = await fetch('/api/orders/dispatch/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                produce: parseInt(produce),
                buyer: parseInt(buyer),
                quantity: parseInt(quantity),
                driver: driver ? parseInt(driver) : null
            })
        });

        const data = await res.json();
        if (res.ok) {
            successDiv.textContent = "Dispatch invoice created successfully! Client has been notified.";
            successDiv.style.display = 'block';
            document.getElementById('dispatch-goods-form').reset();
            loadLogisticsJobs();
        } else {
            if (data.not_connected) {
                if (confirm(data.detail + "\nWould you like to open the My Circle tab to connect with this buyer?")) {
                    switchTab('network');
                }
            } else {
                errorDiv.textContent = "Dispatch failed: " + (data.detail || JSON.stringify(data));
                errorDiv.style.display = 'block';
            }
        }
    } catch (err) {
        errorDiv.textContent = "Error submitting dispatch.";
        errorDiv.style.display = 'block';
        console.error(err);
    }
}

function openAssignDriverModal(jobId) {
    const jobIdInput = document.getElementById('assign-job-id');
    if (jobIdInput) jobIdInput.value = jobId;
    
    const errorDiv = document.getElementById('assign-driver-error');
    if (errorDiv) errorDiv.style.display = 'none';

    const modal = document.getElementById('assign-driver-modal');
    if (modal) modal.style.display = 'flex';
}

async function submitAssignDriver(e) {
    e.preventDefault();
    const jobId = document.getElementById('assign-job-id').value;
    const driverId = document.getElementById('assign-driver-select').value;
    const errorDiv = document.getElementById('assign-driver-error');
    
    let paidBy = 'UNSET';
    const paidByInput = document.querySelector('input[name="assign_paid_by"]:checked');
    if (paidByInput) {
        paidBy = paidByInput.value;
    }

    errorDiv.style.display = 'none';

    if (!jobId || !driverId) {
        errorDiv.textContent = "Please select a driver.";
        errorDiv.style.display = 'block';
        return;
    }

    try {
        const res = await fetch(`/api/logistics/jobs/${jobId}/assign/`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ driver: parseInt(driverId), paid_by: paidBy })
        });

        const data = await res.json();
        if (res.ok) {
            alert("Transporter hired and matched to your order successfully!");
            const modal = document.getElementById('assign-driver-modal');
            if (modal) modal.style.display = 'none';
            loadOrders();
        } else {
            errorDiv.textContent = "Assignment failed: " + (data.detail || JSON.stringify(data));
            errorDiv.style.display = 'block';
        }
    } catch (err) {
        errorDiv.textContent = "Error assigning driver.";
        errorDiv.style.display = 'block';
        console.error(err);
    }
}


// ==========================================================================
// TRUST CIRCLE NETWORK & MESSAGING FUNCTIONS
// ==========================================================================

// Load Connections Circle & Discover Directory
async function loadNetwork() {
    try {
        const res = await fetch('/api/connections/');
        if (!res.ok) return;
        const data = await res.json();

        // 1. Render Active Circle Connections count and list
        const activeCountEl = document.getElementById('active-connection-count');
        if (activeCountEl) {
            activeCountEl.textContent = `${data.connections.length} Connected`;
        }

        const connectionsGrid = document.getElementById('active-connections-grid');
        if (connectionsGrid) {
            connectionsGrid.innerHTML = '';
            if (data.connections.length === 0) {
                connectionsGrid.innerHTML = '<div class="text-secondary p-3 w-full text-center font-sm">No connections in your circle yet. Discover people below to send an invite!</div>';
            } else {
                data.connections.forEach(conn => {
                    const u = conn.user;
                    const card = document.createElement('div');
                    card.className = 'connection-user-card';
                    card.innerHTML = `
                        <div class="connection-user-header">
                            <div>
                                <strong style="font-size: 15px; color: var(--text-primary);">${u.username}</strong>
                                <span class="badge ${u.role === 'FARMER' ? 'badge-green' : (u.role === 'BUYER' ? 'badge-blue' : 'badge-orange')}" style="padding: 1px 6px; font-size: 9px; margin-left: 6px;">
                                    ${u.role.charAt(0) + u.role.slice(1).toLowerCase()}
                                </span>
                            </div>
                            <span class="text-secondary font-xxs"><i class="fa-solid fa-circle text-emerald" style="font-size: 6px;"></i> Active Circle</span>
                        </div>
                        <div class="connection-user-body">
                            <span class="text-secondary font-xs"><i class="fa-solid fa-location-dot"></i> ${u.district}, ${u.region}</span>
                            ${u.phone_number ? `<br><span class="text-secondary font-xs"><i class="fa-solid fa-phone"></i> ${u.phone_number}</span>` : ''}
                        </div>
                        <div style="display: flex; gap: 8px; margin-top: auto;">
                            <button class="btn btn-primary btn-sm flex-grow" onclick="openChat(${u.id}, '${u.username}', '${u.role}', true)">
                                <i class="fa-solid fa-comment-dots"></i> Message
                            </button>
                            <button class="btn btn-secondary btn-sm" onclick="deleteConnection(${conn.connection_id})" title="Remove from Circle">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </div>
                    `;
                    connectionsGrid.appendChild(card);
                });
            }
        }

        // 2. Render Pending Invitations Incoming/Outgoing cards
        const incomingGrid = document.getElementById('incoming-requests-list');
        const outgoingGrid = document.getElementById('outgoing-requests-list');
        const incomingCard = document.getElementById('incoming-requests-card');
        const outgoingCard = document.getElementById('outgoing-requests-card');
        const pendingSection = document.getElementById('pending-invitations-section');

        let showIncoming = false;
        let showOutgoing = false;

        if (incomingGrid && incomingCard) {
            incomingGrid.innerHTML = '';
            if (data.incoming_requests.length > 0) {
                showIncoming = true;
                incomingCard.style.display = 'block';
                data.incoming_requests.forEach(req => {
                    const row = document.createElement('div');
                    row.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 10px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: var(--radius-sm);';
                    row.innerHTML = `
                        <div>
                            <strong style="font-size: 13px;">${req.sender_username}</strong>
                            <span class="badge ${req.sender_role === 'FARMER' ? 'badge-green' : (req.sender_role === 'BUYER' ? 'badge-blue' : 'badge-orange')}" style="padding: 1px 4px; font-size: 8px; margin-left: 4px;">
                                ${req.sender_role.charAt(0) + req.sender_role.slice(1).toLowerCase()}
                            </span>
                        </div>
                        <div style="display: flex; gap: 6px;">
                            <button class="btn btn-success btn-xs" onclick="respondToConnection(${req.id}, 'accept')" style="padding: 4px 8px; width: auto;">Accept</button>
                            <button class="btn btn-secondary btn-xs" onclick="respondToConnection(${req.id}, 'reject')" style="padding: 4px 8px; width: auto;">Reject</button>
                        </div>
                    `;
                    incomingGrid.appendChild(row);
                });
            } else {
                incomingCard.style.display = 'none';
            }
        }

        if (outgoingGrid && outgoingCard) {
            outgoingGrid.innerHTML = '';
            if (data.outgoing_requests.length > 0) {
                showOutgoing = true;
                outgoingCard.style.display = 'block';
                data.outgoing_requests.forEach(req => {
                    const row = document.createElement('div');
                    row.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 10px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: var(--radius-sm);';
                    row.innerHTML = `
                        <div>
                            <strong style="font-size: 13px;">${req.receiver_username}</strong>
                            <span class="badge ${req.receiver_role === 'FARMER' ? 'badge-green' : (req.receiver_role === 'BUYER' ? 'badge-blue' : 'badge-orange')}" style="padding: 1px 4px; font-size: 8px; margin-left: 4px;">
                                ${req.receiver_role.charAt(0) + req.receiver_role.slice(1).toLowerCase()}
                            </span>
                        </div>
                        <span class="text-secondary font-xxs" style="font-style: italic;"><i class="fa-solid fa-clock"></i> Invited</span>
                    `;
                    outgoingGrid.appendChild(row);
                });
            } else {
                outgoingCard.style.display = 'none';
            }
        }

        if (pendingSection) {
            if (showIncoming || showOutgoing) {
                pendingSection.style.display = 'grid';
            } else {
                pendingSection.style.display = 'none';
            }
        }

        // Cache discover directory so we can do local client-side search filtering
        discoverUsersCache = data.discover;
        renderDiscoverUsers();

    } catch (e) {
        console.error("Error loading network circle:", e);
    }
}

// Render Discover People list with client-side searching
function renderDiscoverUsers() {
    const grid = document.getElementById('discover-users-grid');
    if (!grid) return;

    grid.innerHTML = '';

    const filterVal = (document.getElementById('network-search').value || '').toLowerCase().trim();

    const filtered = discoverUsersCache.filter(u => {
        return u.username.toLowerCase().includes(filterVal) ||
               u.role.toLowerCase().includes(filterVal) ||
               u.district.toLowerCase().includes(filterVal) ||
               u.region.toLowerCase().includes(filterVal);
    });

    if (filtered.length === 0) {
        grid.innerHTML = '<div class="text-secondary p-4 w-full text-center font-sm">No matches in platform directory. Try searching a different term.</div>';
        return;
    }

    filtered.forEach(u => {
        const card = document.createElement('div');
        card.className = 'connection-user-card';

        let actionHtml = '';
        if (u.status === 'NONE') {
            actionHtml = `
                <button class="btn btn-primary btn-sm" onclick="sendConnectionRequest(${u.id})" style="padding: 8px;">
                    <i class="fa-solid fa-user-plus"></i> Connect
                </button>
            `;
        } else if (u.status === 'PENDING_SENT') {
            actionHtml = `
                <button class="btn btn-secondary btn-sm" disabled style="opacity: 0.65; cursor: not-allowed; padding: 8px;">
                    <i class="fa-solid fa-clock"></i> Invited
                </button>
            `;
        } else if (u.status === 'PENDING_RECEIVED') {
            actionHtml = `
                <div style="display: flex; gap: 6px; width: 100%;">
                    <button class="btn btn-success btn-sm flex-grow" onclick="respondToConnection(${u.connection_id}, 'accept')" style="padding: 8px;">Accept</button>
                    <button class="btn btn-secondary btn-sm" onclick="respondToConnection(${u.connection_id}, 'reject')" style="padding: 8px; width: auto;"><i class="fa-solid fa-xmark"></i></button>
                </div>
            `;
        } else if (u.status === 'ACCEPTED') {
            actionHtml = `
                <div style="display: flex; gap: 6px; width: 100%; align-items: center;">
                    <span class="badge badge-green text-center block" style="padding: 6px; width: auto; font-size: 10px;"><i class="fa-solid fa-circle-check"></i> Connected</span>
                    <button class="btn btn-primary btn-sm flex-grow" onclick="openChat(${u.id}, '${u.username}', '${u.role}', true)" style="padding: 8px;">
                        <i class="fa-solid fa-comment-dots"></i> Message
                    </button>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="connection-user-header">
                <div>
                    <strong style="font-size: 15px; color: var(--text-primary);">${u.username}</strong>
                    <span class="badge ${u.role === 'FARMER' ? 'badge-green' : (u.role === 'BUYER' ? 'badge-blue' : 'badge-orange')}" style="padding: 1px 6px; font-size: 9px; margin-left: 6px;">
                        ${u.role.charAt(0) + u.role.slice(1).toLowerCase()}
                    </span>
                </div>
            </div>
            <div class="connection-user-body">
                <span class="text-secondary font-xs"><i class="fa-solid fa-location-dot"></i> ${u.district}, ${u.region}</span>
            </div>
            <div style="margin-top: auto; width: 100%;">
                ${actionHtml}
            </div>
        `;
        grid.appendChild(card);
    });
}

// Send request
async function sendConnectionRequest(userId) {
    try {
        const res = await fetch('/api/connections/request/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ receiver_id: userId })
        });
        if (res.ok) {
            alert("Connection invite sent successfully!");
            loadNetwork();
        } else {
            const err = await res.json();
            alert("Invite failed: " + (err.detail || JSON.stringify(err)));
        }
    } catch (e) {
        console.error(e);
    }
}

// Respond request
async function respondToConnection(requestId, action) {
    try {
        const res = await fetch('/api/connections/respond/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ request_id: requestId, action: action })
        });
        if (res.ok) {
            alert(`Invite request ${action}ed successfully!`);
            loadNetwork();
        } else {
            const err = await res.json();
            alert("Action failed: " + (err.detail || JSON.stringify(err)));
        }
    } catch (e) {
        console.error(e);
    }
}

// Break connection
async function deleteConnection(connectionId) {
    if (confirm("Are you sure you want to remove this contact from your Circle of Trust? Transactions between you will be disabled.")) {
        try {
            const res = await fetch(`/api/connections/delete/${connectionId}/`, {
                method: 'DELETE',
                credentials: 'same-origin'
            });
            if (res.ok) {
                alert("Connection removed.");
                loadNetwork();
            }
        } catch (e) {
            console.error(e);
        }
    }
}

// Global Chat shortcut to open tab and load chat hist
window.openChat = function(userId, username, role, isConnected) {
    activeChatPartnerId = userId;
    switchTab('messages');
    setTimeout(() => {
        loadChatHistory(userId);
    }, 150);
};

// Messaging center: list active chat threads
async function loadChats() {
    try {
        const res = await fetch('/api/messages/chats/');
        if (!res.ok) return;
        const chats = await res.json();

        const container = document.getElementById('chats-list-container');
        container.innerHTML = '';

        if (chats.length === 0) {
            container.innerHTML = `
                <div class="text-secondary p-4 text-center font-sm" style="margin-top: 50px;">
                    <i class="fa-solid fa-comment-slash" style="font-size: 24px; display: block; margin-bottom: 8px;"></i>
                    No active chats. Start messaging by clicking "Send Message" in My Circle!
                </div>
            `;
            return;
        }

        chats.forEach(chat => {
            const p = chat.partner;
            const item = document.createElement('div');
            item.className = 'chat-thread-item';
            if (activeChatPartnerId && activeChatPartnerId === p.id) {
                item.classList.add('active');
            }

            // Initials avatar
            const initials = p.username.slice(0, 2).toUpperCase();
            
            // Format last message snippet
            let preview = 'Start conversation...';
            let timeStr = '';
            if (chat.last_message) {
                preview = chat.last_message.content;
                const date = new Date(chat.last_message.created_at);
                timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            }

            // Unread Badge
            const badgeHtml = chat.unread_count > 0 ? 
                `<span class="badge badge-orange" style="border-radius: 50%; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; font-size: 9px; padding: 0;">${chat.unread_count}</span>` : '';

            item.innerHTML = `
                <div class="chat-avatar" style="width: 38px; height: 38px; border-radius: 50%; background-color: var(--border-color); display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight:700; color: var(--emerald-light); flex-shrink:0;">
                    ${initials}
                </div>
                <div class="chat-thread-info">
                    <div class="chat-thread-name-row">
                        <strong style="font-size: 13px;">${p.username}</strong>
                        <span class="text-secondary" style="font-size: 9px;">${timeStr}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                        <span class="chat-thread-msg-preview">${preview}</span>
                        ${badgeHtml}
                    </div>
                </div>
            `;

            item.addEventListener('click', () => {
                // Set active and load history
                activeChatPartnerId = p.id;
                document.querySelectorAll('.chat-thread-item').forEach(el => el.classList.remove('active'));
                item.classList.add('active');
                loadChatHistory(p.id);
            });

            container.appendChild(item);
        });

        // Contextual auto-load active chat pane if partner set but UI not updated
        if (activeChatPartnerId && document.getElementById('active-chat-pane').style.display === 'none') {
            loadChatHistory(activeChatPartnerId);
        }

    } catch (e) {
        console.error("Error loading chats threads:", e);
    }
}

// Fetch messages history
async function loadChatHistory(partnerId, silent = false) {
    try {
        const res = await fetch(`/api/messages/history/${partnerId}/`);
        if (!res.ok) return;
        const messages = await res.json();

        // Fetch partner details from cached explore or directory to set header
        const partnerObj = discoverUsersCache.find(u => u.id === partnerId) || {
            username: 'User #' + partnerId,
            role: 'MEMBER',
            status: 'NONE'
        };

        if (!silent) {
            // Update UI headers
            document.getElementById('chat-header-username').textContent = partnerObj.username;
            document.getElementById('chat-header-role').textContent = partnerObj.role.charAt(0) + partnerObj.role.slice(1).toLowerCase();
            document.getElementById('chat-header-role').className = `badge ${partnerObj.role === 'FARMER' ? 'badge-green' : (partnerObj.role === 'BUYER' ? 'badge-blue' : 'badge-orange')}`;
            
            const circleBadge = document.getElementById('chat-header-circle-status');
            const contextualConnect = document.getElementById('chat-contextual-connect-btn');
            const warningEl = document.getElementById('chat-circle-warning');

            if (partnerObj.status === 'ACCEPTED') {
                circleBadge.style.display = 'inline-block';
                circleBadge.textContent = 'In Circle';
                circleBadge.className = 'badge badge-green';
                contextualConnect.style.display = 'none';
                warningEl.style.display = 'none';
            } else {
                circleBadge.style.display = 'inline-block';
                circleBadge.textContent = 'Outside Circle';
                circleBadge.className = 'badge badge-slate';
                
                warningEl.style.display = 'flex';

                if (partnerObj.status === 'NONE') {
                    contextualConnect.style.display = 'inline-block';
                    contextualConnect.textContent = 'Add to Circle';
                    contextualConnect.disabled = false;
                } else if (partnerObj.status === 'PENDING_SENT') {
                    contextualConnect.style.display = 'inline-block';
                    contextualConnect.textContent = 'Invite Sent';
                    contextualConnect.disabled = true;
                } else {
                    contextualConnect.style.display = 'none';
                }
            }
        }

        // Render message bubbles
        const chatBody = document.getElementById('chat-messages-body');
        const wasAtBottom = chatBody.scrollHeight - chatBody.clientHeight <= chatBody.scrollTop + 50;

        chatBody.innerHTML = '';
        if (messages.length === 0) {
            chatBody.innerHTML = '<div class="text-secondary font-xs text-center p-4">No message records found. Type a message below to start trading.</div>';
        } else {
            messages.forEach(msg => {
                const bubbleRow = document.createElement('div');
                const isSent = msg.sender === currentUser.id;
                bubbleRow.className = `chat-message-row ${isSent ? 'sent' : 'received'}`;
                
                const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                bubbleRow.innerHTML = `
                    <div class="chat-bubble ${isSent ? 'sent' : 'received'}">
                        <span>${msg.content}</span>
                        <span class="chat-bubble-time">${time}</span>
                    </div>
                `;
                chatBody.appendChild(bubbleRow);
            });
        }

        // Display pane
        document.getElementById('chat-splash').style.display = 'none';
        document.getElementById('active-chat-pane').style.display = 'flex';

        // Auto-scroll to bottom
        if (!silent || wasAtBottom) {
            chatBody.scrollTop = chatBody.scrollHeight;
        }

    } catch (e) {
        console.error("Error loading messages history:", e);
    }
}

// Send Message action
async function sendDirectMessage() {
    const input = document.getElementById('chat-message-input');
    const content = input.value.trim();
    if (!content || !activeChatPartnerId) return;

    input.value = '';

    try {
        const res = await fetch('/api/messages/send/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                receiver_id: activeChatPartnerId,
                content: content
            })
        });

        if (res.ok) {
            // Append instantly and scroll
            loadChatHistory(activeChatPartnerId, true);
            // Refresh chats list to update thread previews
            loadChats();
        } else {
            alert("Error sending message.");
        }
    } catch (e) {
        console.error("Error sending message:", e);
    }
}

// Poll chats list and updates badges in background
async function pollMessages() {
    if (!currentUser) return;

    try {
        const res = await fetch('/api/messages/chats/');
        if (!res.ok) return;
        const chats = await res.json();

        // Calculate grand unread message count
        const totalUnread = chats.reduce((sum, c) => sum + c.unread_count, 0);
        
        // Update Sidebar message badge count
        const badge = document.getElementById('sidebar-message-badge');
        if (badge) {
            if (totalUnread > 0) {
                badge.textContent = totalUnread;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }

        // Realtime refresh active chat messages list if user is looking at messages tab and chat is active
        if (currentTab === 'messages') {
            // Reload thread lists previews
            const container = document.getElementById('chats-list-container');
            if (container) {
                // To avoid breaking click handlers, we can refresh thread items silently if activeChatPartnerId not changed,
                // but a simple render keeps unread count badges synced.
                // Let's render the chats list.
                // We do it only if we're not in the middle of active typing focus
                const msgInput = document.getElementById('chat-message-input');
                if (msgInput !== document.activeElement) {
                    loadChats();
                }
            }

            if (activeChatPartnerId) {
                loadChatHistory(activeChatPartnerId, true);
            }
        }
    } catch (e) {
        console.warn("Polling message error: ", e);
    }
}


// Poll and manage alerts/notifications
async function pollNotifications() {
    if (!currentUser) return;
    
    try {
        const res = await fetch('/api/notifications/');
        if (!res.ok) return;
        const notifications = await res.json();
        
        let unreadCount = 0;
        let newNotifications = [];
        
        notifications.forEach(notif => {
            if (!notif.is_read) {
                unreadCount++;
            }
            if (!seenNotificationIds.has(notif.id)) {
                seenNotificationIds.add(notif.id);
                newNotifications.push(notif);
            }
        });
        
        // Update header alerts badge
        const badge = document.getElementById('header-alerts-badge');
        if (badge) {
            if (unreadCount > 0) {
                badge.style.display = 'block';
            } else {
                badge.style.display = 'none';
            }
        }
        
        // Show premium visual toasts for newly arrived notifications
        const isFirstLoad = (seenNotificationIds.size === newNotifications.length);
        if (!isFirstLoad) {
            newNotifications.forEach(notif => {
                showToast(notif);
            });
        }
        
        renderNotificationsInModal(notifications, unreadCount);
    } catch (e) {
        console.error("Error polling notifications:", e);
    }
}

// Render notifications inside the inbox modal
function renderNotificationsInModal(notifications, unreadCount) {
    const listContainer = document.getElementById('alerts-list-container');
    const emptyState = document.getElementById('alerts-empty-state');
    const unreadCounter = document.getElementById('alerts-unread-count');
    
    if (unreadCounter) {
        unreadCounter.textContent = `${unreadCount} Unread`;
    }
    
    if (!listContainer) return;
    listContainer.innerHTML = '';
    
    if (notifications.length === 0) {
        if (emptyState) emptyState.style.display = 'block';
        return;
    }
    
    if (emptyState) emptyState.style.display = 'none';
    
    notifications.forEach(notif => {
        const notifTime = new Date(notif.created_at).toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
        
        const notifItem = document.createElement('div');
        notifItem.className = `notification-item ${notif.is_read ? '' : 'unread'}`;
        
        const iconClass = notif.notification_type === 'SMS' ? 'fa-solid fa-message' : 'fa-solid fa-envelope';
        const typeClass = notif.notification_type.toLowerCase();
        
        notifItem.innerHTML = `
            <div class="alert-toast-icon ${typeClass}">
                <i class="${iconClass}"></i>
            </div>
            <div class="alert-toast-body" style="flex-grow: 1;">
                <div class="flex justify-between items-start" style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <span class="alert-toast-title" style="font-size: 12px; margin-bottom: 2px;">${notif.title}</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="text-secondary" style="font-size: 10px;">${notifTime}</span>
                        <button class="delete-notif-btn" data-id="${notif.id}" style="background: none; border: none; cursor: pointer; color: var(--text-secondary); opacity: 0.6; padding: 2px 4px; font-size: 11px; transition: all 0.2s;" title="Delete notification"><i class="fa-solid fa-trash"></i></button>
                    </div>
                </div>
                <p class="alert-toast-text" style="margin: 0; font-size: 11px;">${notif.content}</p>
                <span class="notification-badge-type ${typeClass}">${notif.notification_type} Alert</span>
            </div>
        `;
        
        const deleteBtn = notifItem.querySelector('.delete-notif-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const notifId = e.currentTarget.getAttribute('data-id');
                try {
                    const delRes = await fetch(`/api/notifications/${notifId}/`, { method: 'DELETE' });
                    if (delRes.ok) {
                        // Animate and remove
                        notifItem.style.transition = 'all 0.3s ease';
                        notifItem.style.opacity = '0';
                        notifItem.style.transform = 'translateX(-20px)';
                        setTimeout(() => {
                            pollNotifications();
                        }, 300);
                    }
                } catch (err) {
                    console.error("Failed to delete notification:", err);
                }
            });
        }

        listContainer.appendChild(notifItem);
    });
}

// Display slide-in premium notification toast
function showToast(notif) {
    const container = document.getElementById('alert-toasts-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = 'alert-toast';
    
    const typeClass = notif.notification_type.toLowerCase();
    const iconClass = notif.notification_type === 'SMS' ? 'fa-solid fa-comment-sms' : 'fa-solid fa-envelope-open-text';
    
    toast.innerHTML = `
        <div class="alert-toast-icon ${typeClass}">
            <i class="${iconClass}"></i>
        </div>
        <div class="alert-toast-body">
            <h5 class="alert-toast-title">${notif.title}</h5>
            <p class="alert-toast-text">${notif.content}</p>
        </div>
        <button class="alert-toast-close">&times;</button>
    `;
    
    const closeBtn = toast.querySelector('.alert-toast-close');
    closeBtn.onclick = () => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    };
    
    container.appendChild(toast);
    
    // Auto-remove after 8 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }
    }, 8000);
}

// Dynamic Analytics Price Trend Chart builder using real system data
async function renderAnalyticsChart() {
    try {
        // Fetch all user listings, user orders, and circle connections in parallel
        const [resProduce, resOrders, resConnections] = await Promise.all([
            fetch('/api/produce/'),
            fetch('/api/orders/create/'),
            fetch('/api/connections/')
        ]);
        
        if (!resProduce.ok || !resOrders.ok || !resConnections.ok) return;
        
        const produces = await resProduce.ok ? await resProduce.json() : [];
        const orders = await resOrders.ok ? await resOrders.json() : [];
        const connectionsData = await resConnections.ok ? await resConnections.json() : { connections: [] };
        
        const myUsername = currentUser.username;
        const myRole = currentUser.role;
        const myConnectionsCount = connectionsData.connections.length;
        
        // Define variable metrics
        let totalRevenueOrSpent = 0;
        let activeCount = 0;
        let completedCount = 0;
        let secondaryMetric = 0;
        
        let primaryCrop = "None";
        let escrowBalance = 0;
        
        if (myRole === 'FARMER') {
            // Farmer data
            const myCrops = produces.filter(p => p.farmer_name === myUsername);
            activeCount = myCrops.filter(p => p.status === 'AVAILABLE').length;
            
            // Calculate total revenue from all orders
            totalRevenueOrSpent = orders.reduce((sum, o) => sum + parseFloat(o.total_price || 0), 0);
            completedCount = orders.filter(o => o.status === 'DELIVERED').length;
            
            // Fulfillment rate = total quantity sold across all orders
            secondaryMetric = orders.reduce((sum, o) => sum + parseInt(o.quantity || 0), 0);
            
            // Insights
            const cropCounts = {};
            myCrops.forEach(c => cropCounts[c.name] = (cropCounts[c.name] || 0) + 1);
            primaryCrop = Object.keys(cropCounts).reduce((a, b) => cropCounts[a] > cropCounts[b] ? a : b, "Tomatoes");
            
            escrowBalance = orders
                .filter(o => o.payment_status === 'HELD_IN_ESCROW')
                .reduce((sum, o) => sum + parseFloat(o.total_price || 0), 0);
                
        } else {
            // Buyer/Transporter data
            activeCount = orders.filter(o => o.status !== 'DELIVERED').length;
            totalRevenueOrSpent = orders.reduce((sum, o) => sum + parseFloat(o.total_price || 0), 0);
            completedCount = orders.filter(o => o.status === 'DELIVERED').length;
            
            // Fulfillment rate = total quantity bought
            secondaryMetric = orders.reduce((sum, o) => sum + parseInt(o.quantity || 0), 0);
            
            // Insights
            const cropCounts = {};
            orders.forEach(o => {
                const cropName = o.produce_details ? o.produce_details.name : "Tomatoes";
                cropCounts[cropName] = (cropCounts[cropName] || 0) + 1;
            });
            primaryCrop = Object.keys(cropCounts).reduce((a, b) => cropCounts[a] > cropCounts[b] ? a : b, "Tomatoes");
            
            escrowBalance = orders
                .filter(o => o.payment_status === 'HELD_IN_ESCROW')
                .reduce((sum, o) => sum + parseFloat(o.total_price || 0), 0);
        }
        
        // Update Card 1: Revenue or Spent
        const card1Title = document.getElementById('analytics-card1-title');
        const card1Val = document.getElementById('analytics-card1-val');
        const card1Trend = document.getElementById('analytics-card1-trend');
        if (card1Title) card1Title.textContent = myRole === 'BUYER' ? 'Total Spent' : 'Total Revenue';
        if (card1Val) card1Val.textContent = `GHS ${totalRevenueOrSpent.toFixed(2)}`;
        if (card1Trend) {
            card1Trend.innerHTML = `<i class="fa-solid fa-circle-check"></i> Real-time sync`;
        }
        
        // Update Card 2: Active listings or active orders
        const card2Title = document.getElementById('analytics-card2-title');
        const card2Val = document.getElementById('analytics-card2-val');
        const card2Trend = document.getElementById('analytics-card2-trend');
        if (card2Title) card2Title.textContent = myRole === 'BUYER' ? 'Active Orders' : 'Active Listings';
        if (card2Val) card2Val.textContent = myRole === 'BUYER' ? `${activeCount} Orders` : `${activeCount} Crops`;
        if (card2Trend) {
            card2Trend.innerHTML = `<i class="fa-solid fa-clock"></i> Live listings status`;
        }
        
        // Update Card 3: Completed orders
        const card3Title = document.getElementById('analytics-card3-title');
        const card3Val = document.getElementById('analytics-card3-val');
        const card3Trend = document.getElementById('analytics-card3-trend');
        if (card3Title) card3Title.textContent = myRole === 'BUYER' ? 'Completed Purchases' : 'Completed Sales';
        if (card3Val) card3Val.textContent = `${completedCount} Orders`;
        
        // Update Card 4: Quantity Fulfilled
        const card4Title = document.getElementById('analytics-card4-title');
        const card4Val = document.getElementById('analytics-card4-val');
        if (card4Title) card4Title.textContent = 'Units Transacted';
        if (card4Val) card4Val.textContent = `${secondaryMetric} Units`;
        
        // Update Side Insights Panel
        const insightCrop = document.getElementById('insight-crop');
        const insightConnections = document.getElementById('insight-connections');
        const insightEscrow = document.getElementById('insight-escrow');
        const insightSuccess = document.getElementById('insight-success');
        
        if (insightCrop) insightCrop.textContent = primaryCrop;
        if (insightConnections) insightConnections.textContent = `${myConnectionsCount} Connected`;
        if (insightEscrow) insightEscrow.textContent = `GHS ${escrowBalance.toFixed(2)}`;
        if (insightSuccess) {
            const successRate = orders.length > 0 
                ? Math.round((orders.filter(o => o.status !== 'REFUNDED').length / orders.length) * 100)
                : 100;
            insightSuccess.textContent = `${successRate}%`;
        }
        
        // Dynamic Chart title and legends
        const chartTitle = document.getElementById('analytics-chart-title');
        const legend1 = document.getElementById('analytics-legend-1');
        const legend2 = document.getElementById('analytics-legend-2');
        
        if (chartTitle) {
            chartTitle.innerHTML = `<i class="fa-solid fa-chart-area"></i> My Transaction Volume & Value Trends`;
        }
        if (legend1) {
            legend1.innerHTML = `<i class="fa-solid fa-circle text-emerald"></i> Gross Value (GHS)`;
        }
        if (legend2) {
            legend2.innerHTML = `<i class="fa-solid fa-circle text-amber"></i> Avg Order Value (GHS)`;
        }
        
        // Construct 5 historical price trend points ending at the real current database average
        // If they have no orders, we use base baseline
        const baseVal = totalRevenueOrSpent > 0 ? totalRevenueOrSpent : 150;
        const points = [
            { x: 50,  price: Math.round(baseVal * 0.7) },
            { x: 150, price: Math.round(baseVal * 0.95) },
            { x: 250, price: Math.round(baseVal * 0.6) },
            { x: 350, price: Math.round(baseVal * 0.85) },
            { x: 450, price: Math.round(baseVal) }
        ];
        
        // Helper: Map value to SVG Y coordinate (Price 0 GHS = Y=170, Price max = Y=30)
        const mapPriceToY = (price) => {
            const minPrice = 0;
            const maxPrice = Math.max(baseVal * 1.5, 200);
            const minY = 170;
            const maxY = 30;
            const clamped = Math.max(minPrice, Math.min(maxPrice, price));
            return minY - ((clamped - minPrice) / (maxPrice - minPrice)) * (minY - maxY);
        };
        
        // Calculate coordinates
        const coords = points.map(p => ({ x: p.x, y: mapPriceToY(p.price) }));
        
        // Build cubic Hermite spline path command string for smooth line rendering
        let pathCmd = `M ${coords[0].x} ${coords[0].y}`;
        for (let i = 0; i < coords.length - 1; i++) {
            const p0 = coords[i];
            const p1 = coords[i+1];
            const cp1x = p0.x + 50;
            const cp1y = p0.y;
            const cp2x = p1.x - 50;
            const cp2y = p1.y;
            pathCmd += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p1.x} ${p1.y}`;
        }
        
        // Build smooth fill command string
        const fillCmd = `${pathCmd} L 450 170 L 50 170 Z`;
        
        // Inject smooth path definitions
        const tomatoPath = document.getElementById('chart-tomato-path');
        const tomatoFill = document.getElementById('chart-tomato-fill');
        if (tomatoPath) tomatoPath.setAttribute('d', pathCmd);
        if (tomatoFill) tomatoFill.setAttribute('d', fillCmd);
        
        // Calculate dynamic dates for labels
        const today = new Date();
        const dateOptions = { month: 'short', day: 'numeric' };
        
        const labels = [
            new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', dateOptions),
            new Date(today.getTime() - 20 * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', dateOptions),
            new Date(today.getTime() - 10 * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', dateOptions),
            new Date(today.getTime() - 5 * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', dateOptions),
            today.toLocaleDateString('en-US', dateOptions)
        ];
        
        // Update label text nodes
        for (let i = 1; i <= 5; i++) {
            const labelEl = document.getElementById(`chart-date-${i}`);
            if (labelEl) labelEl.textContent = labels[i-1];
        }
        
        // Render dynamic Benchmark path (dashed orange comparison line representing moving avg order value)
        const avgVal = orders.length > 0 ? (totalRevenueOrSpent / orders.length) : 50;
        const accraPoints = [
            { x: 50,  price: Math.round(avgVal * 0.9) },
            { x: 150, price: Math.round(avgVal * 1.1) },
            { x: 250, price: Math.round(avgVal * 0.8) },
            { x: 350, price: Math.round(avgVal * 1.0) },
            { x: 450, price: Math.round(avgVal) }
        ];
        
        const accraCoords = accraPoints.map(p => ({ x: p.x, y: mapPriceToY(p.price) }));
        let accraCmd = `M ${accraCoords[0].x} ${accraCoords[0].y}`;
        for (let i = 0; i < accraCoords.length - 1; i++) {
            const p0 = accraCoords[i];
            const p1 = accraCoords[i+1];
            accraCmd += ` C ${p0.x + 50} ${p0.y}, ${p1.x - 50} ${p1.y}, ${p1.x} ${p1.y}`;
        }
        
        const pepperPath = document.getElementById('chart-pepper-path');
        if (pepperPath) pepperPath.setAttribute('d', accraCmd);
        
        // Clear and redraw interactive points & hover triggers
        const markersGroup = document.getElementById('chart-markers');
        const triggersGroup = document.getElementById('chart-triggers');
        if (markersGroup) markersGroup.innerHTML = '';
        if (triggersGroup) triggersGroup.innerHTML = '';
        
        coords.forEach((coord, index) => {
            const p = points[index];
            const dateStr = labels[index];
            
            // Draw small visual point marker
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', coord.x);
            circle.setAttribute('cy', coord.y);
            circle.setAttribute('r', '5');
            circle.setAttribute('fill', '#10b981');
            circle.setAttribute('stroke', '#0b0f19');
            circle.setAttribute('stroke-width', '2');
            circle.setAttribute('style', 'transition: all 0.2s ease;');
            if (markersGroup) markersGroup.appendChild(circle);
            
            // Draw larger invisible trigger area for hover
            const trigger = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            trigger.setAttribute('cx', coord.x);
            trigger.setAttribute('cy', coord.y);
            trigger.setAttribute('r', '20'); // Large radius makes hovering easy!
            trigger.setAttribute('fill', 'transparent');
            trigger.setAttribute('style', 'cursor: pointer;');
            
            // Bind hover events
            const tooltip = document.getElementById('chart-tooltip');
            
            trigger.addEventListener('mouseenter', (e) => {
                // Grow the marker point
                circle.setAttribute('r', '8');
                circle.setAttribute('fill', '#34d399');
                
                // Position and show tooltip
                if (tooltip) {
                    tooltip.style.display = 'block';
                    tooltip.style.opacity = '1';
                    tooltip.innerHTML = `
                        <div style="font-weight: 700; color: var(--text-primary); margin-bottom: 4px; font-size: 11px;">${dateStr}</div>
                        <div style="display: flex; align-items: center; gap: 6px; font-size: 10px;">
                            <i class="fa-solid fa-circle text-emerald" style="font-size: 8px;"></i>
                            <span>Volume: <strong>GHS ${p.price.toFixed(2)}</strong></span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px; font-size: 10px; margin-top: 3px; color: var(--text-secondary);">
                            <i class="fa-solid fa-circle text-amber" style="font-size: 8px;"></i>
                            <span>Avg Order: <strong>GHS ${accraPoints[index].price.toFixed(2)}</strong></span>
                        </div>
                    `;
                    
                    // Position tooltip relative to the SVG wrapper container
                    const rect = e.target.getBoundingClientRect();
                    const containerRect = document.querySelector('.chart-mockup-wrapper').getBoundingClientRect();
                    tooltip.style.left = `${rect.left - containerRect.left + 15}px`;
                    tooltip.style.top = `${rect.top - containerRect.top - 65}px`;
                }
            });
            
            trigger.addEventListener('mouseleave', () => {
                // Restore marker point size
                circle.setAttribute('r', '5');
                circle.setAttribute('fill', '#10b981');
                
                // Hide tooltip
                if (tooltip) {
                    tooltip.style.opacity = '0';
                    tooltip.style.display = 'none';
                }
            });
            
            if (triggersGroup) triggersGroup.appendChild(trigger);
        });
        
    } catch (err) {
        console.error("Error drawing pricing chart:", err);
    }
}

