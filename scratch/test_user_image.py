import os
import requests

image_path = r"C:\Users\Administrator\Downloads\images.jpg"
api_url = "https://api-inference.huggingface.co/models/linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification"

if not os.path.exists(image_path):
    print(f"Error: File not found at {image_path}")
    # Search in common locations in case the path is slightly different
    print("Files in C:\\Users\\Administrator\\Downloads:")
    try:
        for f in os.listdir("C:\\Users\\Administrator\\Downloads"):
            if f.endswith(('.jpg', '.jpeg', '.png')):
                print(f" - {f}")
    except Exception as e:
        print(f"Error listing downloads: {e}")
    exit(1)

with open(image_path, 'rb') as f:
    image_bytes = f.read()

print(f"Sending image ({len(image_bytes)} bytes) to Hugging Face Inference API...")
response = requests.post(api_url, data=image_bytes, timeout=10)

print(f"Response Status Code: {response.status_code}")
try:
    data = response.json()
    print("Response JSON:")
    import pprint
    pprint.pprint(data)
except Exception as e:
    print(f"Failed to parse JSON response: {e}")
    print(response.text)
