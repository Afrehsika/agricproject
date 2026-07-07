document.addEventListener('DOMContentLoaded', () => {
    // --- Clock ---
    function updateClock() {
        const now = new Date();
        const hrs = String(now.getHours()).padStart(2, '0');
        const mins = String(now.getMinutes()).padStart(2, '0');
        document.getElementById('clock').textContent = `${hrs}:${mins}`;
    }
    setInterval(updateClock, 1000);
    updateClock();

    // --- Theme Toggle ---
    const themeToggle = document.getElementById('theme-toggle');
    themeToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            document.body.classList.remove('light-mode');
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
            document.body.classList.add('light-mode');
        }
    });

    // --- Dialer Input ---
    const dialInput = document.getElementById('dial-input');
    const dialKeys = document.querySelectorAll('.dial-key');
    const btnDelete = document.getElementById('btn-delete');
    
    dialKeys.forEach(key => {
        key.addEventListener('click', () => {
            dialInput.value += key.getAttribute('data-key');
        });
    });

    btnDelete.addEventListener('click', () => {
        dialInput.value = dialInput.value.slice(0, -1);
    });

    // Keyboard support for dialer
    document.addEventListener('keydown', (e) => {
        // If USSD overlay is not active
        if (!document.getElementById('ussd-overlay').classList.contains('active')) {
            if (/^[0-9*#]$/.test(e.key)) {
                dialInput.value += e.key;
            } else if (e.key === 'Backspace') {
                dialInput.value = dialInput.value.slice(0, -1);
            } else if (e.key === 'Enter') {
                startUSSD();
            }
        }
    });

    // --- API & State Management ---
    let accessToken = null;
    let currentSessionId = "";
    let currentSessionPath = ""; // Stores "1*2*1" etc.
    let currentServiceCode = "*920*44#";

    const btnAuth = document.getElementById('btn-auth');
    const statusMsg = document.getElementById('auth-status');
    const btnCall = document.getElementById('btn-call');
    
    // Auto-fill phone from dropdown
    const demoUserSelect = document.getElementById('demo-user-select');
    const configPhone = document.getElementById('config-phone');
    if (demoUserSelect) {
        demoUserSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                configPhone.value = e.target.value;
            }
        });
    }

    const ussdOverlay = document.getElementById('ussd-overlay');
    const ussdHeader = document.getElementById('ussd-header');
    const ussdLoading = document.getElementById('ussd-loading');
    const ussdInteractive = document.getElementById('ussd-interactive');
    const ussdText = document.getElementById('ussd-text');
    const ussdResponseInput = document.getElementById('ussd-response');
    const ussdInputWrapper = document.getElementById('ussd-input-wrapper');
    const btnUssdCancel = document.getElementById('btn-ussd-cancel');
    const btnUssdSend = document.getElementById('btn-ussd-send');

    // Authenticate Gateway
    btnAuth.addEventListener('click', async () => {
        const clientId = document.getElementById('config-client-id').value;
        const clientSecret = document.getElementById('config-client-secret').value;

        if (!clientId || !clientSecret) {
            statusMsg.textContent = "Please enter Client ID & Secret";
            statusMsg.style.color = "red";
            return;
        }

        btnAuth.textContent = "Connecting...";
        try {
            const formData = new URLSearchParams();
            formData.append('grant_type', 'client_credentials');

            const authString = btoa(clientId + ':' + clientSecret);

            const res = await fetch('/o/token/', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Authorization': `Basic ${authString}`
                },
                body: formData.toString()
            });

            if (res.ok) {
                const data = await res.json();
                accessToken = data.access_token;
                statusMsg.textContent = "Gateway Connected Successfully";
                statusMsg.style.color = "green";
                btnAuth.textContent = "Connected";
                
                // Pre-fill the shortcode
                if (dialInput.value === "") {
                    dialInput.value = "*920*44#";
                }
            } else {
                statusMsg.textContent = `Error: ${res.status}`;
                statusMsg.style.color = "red";
                btnAuth.textContent = "Connect Gateway";
            }
        } catch (err) {
            statusMsg.textContent = "Connection Failed.";
            statusMsg.style.color = "red";
            btnAuth.textContent = "Connect Gateway";
        }
    });

    // Start USSD Call
    btnCall.addEventListener('click', startUSSD);

    function startUSSD() {
        if (!accessToken) {
            alert("Please connect the Gateway via OAuth first!");
            return;
        }

        const dialVal = dialInput.value.trim();
        if (dialVal === "") return;

        // Reset Session
        currentSessionId = "sim_session_" + Math.random().toString(36).substr(2, 9);
        currentSessionPath = "";
        currentServiceCode = dialVal;
        
        openOverlay(true);
        sendUSSDRequest("");
    }

    // Send Input from overlay
    btnUssdSend.addEventListener('click', () => {
        const val = ussdResponseInput.value.trim();
        if (currentSessionPath === "") {
            currentSessionPath = val;
        } else {
            currentSessionPath += val ? "*" + val : "";
        }
        
        openOverlay(true);
        sendUSSDRequest(currentSessionPath);
    });

    // Cancel Session
    btnUssdCancel.addEventListener('click', closeOverlay);

    // Enter to Send inside overlay
    ussdResponseInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !ussdResponseInput.readOnly) {
            btnUssdSend.click();
        }
    });

    async function sendUSSDRequest(textString) {
        const phone = document.getElementById('config-phone').value || "0000000000";

        try {
            const res = await fetch('/api/ussd/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`
                },
                body: JSON.stringify({
                    phoneNumber: phone,
                    sessionId: currentSessionId,
                    serviceCode: currentServiceCode,
                    text: textString
                })
            });

            if (res.ok) {
                const responseText = await res.text();
                processResponse(responseText);
            } else {
                showError(`Gateway Error: ${res.status}`);
            }
        } catch (err) {
            showError(`Network Error: ${err.message}`);
        }
    }

    function processResponse(response) {
        // Africa's Talking format: CON (Continue) or END (End)
        openOverlay(false);
        
        if (response.startsWith("CON ")) {
            ussdText.textContent = response.substring(4);
            ussdInputWrapper.style.display = "block";
            btnUssdSend.style.display = "block";
            btnUssdCancel.textContent = "CANCEL";
            ussdResponseInput.value = "";
            ussdResponseInput.focus();
        } else if (response.startsWith("END ")) {
            ussdText.textContent = response.substring(4);
            ussdInputWrapper.style.display = "none";
            btnUssdSend.style.display = "none";
            btnUssdCancel.textContent = "OK";
        } else {
            ussdText.textContent = response;
            ussdInputWrapper.style.display = "none";
            btnUssdSend.style.display = "none";
            btnUssdCancel.textContent = "OK";
        }
    }

    function showError(msg) {
        openOverlay(false);
        ussdText.textContent = msg;
        ussdInputWrapper.style.display = "none";
        btnUssdSend.style.display = "none";
        btnUssdCancel.textContent = "OK";
    }

    function openOverlay(loading) {
        ussdOverlay.classList.add('active');
        ussdHeader.textContent = currentServiceCode;
        ussdHeader.style.display = "block";
        
        if (loading) {
            ussdLoading.classList.add('active');
            ussdInteractive.classList.remove('active');
        } else {
            ussdLoading.classList.remove('active');
            ussdInteractive.classList.add('active');
        }
    }

    function closeOverlay() {
        ussdOverlay.classList.remove('active');
        setTimeout(() => {
            ussdLoading.classList.remove('active');
            ussdInteractive.classList.remove('active');
            ussdHeader.style.display = "none";
            dialInput.value = "";
        }, 300); // Wait for transition
    }
});
