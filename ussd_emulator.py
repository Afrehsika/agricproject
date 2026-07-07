import tkinter as tk
from tkinter import messagebox, simpledialog
import requests
import os

API_BASE = "http://127.0.0.1:8000/api"
OAUTH_TOKEN_URL = "http://127.0.0.1:8000/o/token/"

class USSDEmulator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AgriConnect USSD Gateway Emulator")
        self.geometry("350x550")
        self.configure(bg="#2d2d2d")
        self.resizable(False, False)
        
        self.session = requests.Session()
        self.access_token = None
        self.phone_number = None
        self.ussd_session_id = "simulated_session_12345"
        self.ussd_text = ""
        
        self.build_ui()
        self.reset_ussd()
        
    def build_ui(self):
        # Header
        header = tk.Frame(self, bg="#0b0f19", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="USSD Gateway", fg="white", bg="#0b0f19", font=("Outfit", 14, "bold")).pack(pady=10)
        
        # Phone Info
        self.info_label = tk.Label(self, text="Not Connected", fg="white", bg="#2d2d2d", font=("Inter", 10))
        self.info_label.pack(pady=5)

        # Screen
        self.screen_frame = tk.Frame(self, bg="#dcf8c6", padx=10, pady=10)
        self.screen_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.screen_text = tk.Label(self.screen_frame, text="", bg="#dcf8c6", fg="black", font=("Inter", 11), justify=tk.LEFT, wraplength=290, anchor="nw")
        self.screen_text.pack(fill=tk.BOTH, expand=True)
        
        # Input area
        input_frame = tk.Frame(self, bg="#2d2d2d")
        input_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.input_field = tk.Entry(input_frame, font=("Inter", 12))
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.input_field.bind('<Return>', lambda e: self.handle_input())
        
        # Buttons
        btn_frame = tk.Frame(self, bg="#2d2d2d")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        self.btn_cancel = tk.Button(btn_frame, text="Cancel", font=("Inter", 10, "bold"), bg="#ff4d4f", fg="white", command=self.reset_ussd, width=10)
        self.btn_cancel.pack(side=tk.LEFT, expand=True)
        
        self.btn_send = tk.Button(btn_frame, text="Send", font=("Inter", 10, "bold"), bg="#4caf50", fg="white", command=self.handle_input, width=10)
        self.btn_send.pack(side=tk.RIGHT, expand=True)
        
        # Connect button
        auth_frame = tk.Frame(self, bg="#2d2d2d")
        auth_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.btn_connect = tk.Button(auth_frame, text="Connect SIM (Setup Phone)", font=("Inter", 10), command=self.connect_sim)
        self.btn_connect.pack()

    def connect_sim(self):
        client_id = simpledialog.askstring("OAuth Setup", "Enter OAuth2 Client ID:")
        if not client_id: return
        client_secret = simpledialog.askstring("OAuth Setup", "Enter OAuth2 Client Secret:")
        if not client_secret: return
        
        # Get Client Credentials Token
        try:
            res = requests.post(OAUTH_TOKEN_URL, data={
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret
            })
            if res.status_code == 200:
                self.access_token = res.json().get('access_token')
                self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
                messagebox.showinfo("OAuth Success", "Gateway Authenticated successfully.")
                
                # Now ask for phone number
                phone = simpledialog.askstring("SIM Setup", "Enter Simulated Phone Number (e.g., 0240001111):")
                if phone:
                    self.phone_number = phone
                    self.info_label.config(text=f"Phone: {self.phone_number}")
                    self.btn_connect.config(text="Change SIM")
                    self.reset_ussd()
            else:
                messagebox.showerror("OAuth Failed", f"Invalid credentials. Status: {res.status_code}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {e}")

    def reset_ussd(self):
        self.ussd_text = ""
        self.screen_text.config(text="Dial *920*44# to start USSD session.")
        self.input_field.delete(0, tk.END)
        self.btn_send.config(text="Dial")
        self.btn_cancel.config(text="Cancel")

    def handle_input(self):
        val = self.input_field.get().strip()
        self.input_field.delete(0, tk.END)
        
        if not self.phone_number or not self.access_token:
            self.screen_text.config(text="Error: SIM not connected or Gateway not authenticated.\n\nPlease Connect SIM first.")
            return

        if self.ussd_text == "":
            if val == "*920*44#" or val == "":
                self.ussd_text = ""
                self.btn_send.config(text="Send")
                self.btn_cancel.config(text="Exit")
            else:
                messagebox.showwarning("Invalid", "Invalid USSD String. Try dialing *920*44#")
                return
        else:
            # Append input to the session text path (e.g. 1*2)
            self.ussd_text = f"{self.ussd_text}*{val}" if self.ussd_text else val

        # Send to backend Webhook
        try:
            payload = {
                "sessionId": self.ussd_session_id,
                "serviceCode": "*920*44#",
                "phoneNumber": self.phone_number,
                "text": self.ussd_text
            }
            res = self.session.post(f"{API_BASE}/ussd/", json=payload)
            
            if res.status_code == 200:
                response_text = res.text
                
                # Africa's Talking format starts with CON (Continue) or END (End)
                if response_text.startswith("CON "):
                    self.screen_text.config(text=response_text[4:])
                elif response_text.startswith("END "):
                    self.screen_text.config(text=response_text[4:])
                    self.ussd_text = ""  # Reset session text
                    self.btn_send.config(text="Dial")
                else:
                    self.screen_text.config(text=response_text)
            else:
                self.screen_text.config(text=f"Gateway Error: HTTP {res.status_code}")
                self.ussd_text = ""
        except Exception as e:
            self.screen_text.config(text=f"Network Error: {e}")
            self.ussd_text = ""

if __name__ == "__main__":
    app = USSDEmulator()
    app.mainloop()
