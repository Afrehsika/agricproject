import datetime
import re
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from produce.models import Produce


class CropDiseaseScannerView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        crop_name = request.data.get('crop_name', 'Tomatoes')
        uploaded_file = request.FILES.get('file')

        # 1. Attempt Real Hugging Face Inference if a file is uploaded
        if uploaded_file:
            try:
                import requests
                from requests.exceptions import ConnectionError as ReqConnectionError, Timeout as ReqTimeout

                api_url = "https://api-inference.huggingface.co/models/linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification"
                image_bytes = uploaded_file.read()

                hf_response = requests.post(api_url, data=image_bytes, timeout=8)
                print(f"Hugging Face Response Status: {hf_response.status_code}")

                if hf_response.status_code == 200:
                    predictions = hf_response.json()
                    if predictions and isinstance(predictions, list) and len(predictions) > 0:
                        top_pred = predictions[0]
                        raw_label = top_pred.get('label', '')
                        confidence_score = top_pred.get('score', 0.0)

                        label_parts = raw_label.split('___')
                        if len(label_parts) < 2:
                            label_parts = raw_label.split('__')

                        raw_disease = label_parts[1] if len(label_parts) > 1 else label_parts[0]
                        clean_disease = raw_disease.replace('_', ' ').title()

                        is_healthy = 'healthy' in raw_label.lower()
                        severity = 'None' if is_healthy else 'Moderate'

                        if is_healthy:
                            diagnosis = f"Healthy {crop_name}"
                            severity = "None"
                            treatment = _TREATMENT_MAP['healthy']
                        else:
                            diagnosis = clean_disease
                            if 'blight' in clean_disease.lower():
                                severity, treatment = 'Moderate', _TREATMENT_MAP['blight']
                            elif 'spot' in clean_disease.lower() or 'septoria' in clean_disease.lower():
                                severity, treatment = 'High', _TREATMENT_MAP['spot']
                            elif 'mildew' in clean_disease.lower():
                                severity, treatment = 'Moderate', _TREATMENT_MAP['mildew']
                            elif 'virus' in clean_disease.lower() or 'mosaic' in clean_disease.lower():
                                severity, treatment = 'High', _TREATMENT_MAP['virus']
                            else:
                                severity, treatment = 'Moderate', _TREATMENT_MAP['blight']

                        return Response({
                            'status': 'SUCCESS',
                            'source': 'AI_CLOUD',
                            'crop_analyzed': crop_name,
                            'diagnosis': diagnosis,
                            'confidence_score': f"{confidence_score * 100:.1f}%",
                            'severity_level': severity,
                            'treatment_plan': treatment,
                        })
                else:
                    print(f"Hugging Face Error Response: {hf_response.text}")

            except (ReqConnectionError, ReqTimeout) as e:
                print(f"Hugging Face unreachable (offline mode): {type(e).__name__}")
            except Exception as e:
                print(f"Hugging Face Inference failed: {e}")

        # 2. Local colour-histogram image analysis — reads actual pixel data
        if uploaded_file:
            try:
                result = _analyse_image_locally(uploaded_file, crop_name)
                if result:
                    return Response(result)
            except Exception as e:
                print(f"Local image analysis failed: {e}")

        # 3. Last-resort: no image uploaded at all
        return _no_image_fallback(crop_name)


# ---------------------------------------------------------------------------
# LOCAL COLOUR-HISTOGRAM IMAGE ANALYSER
# ---------------------------------------------------------------------------

_CROP_DISEASE_MAP = {
    'Tomatoes': {
        'blight':  ('Early Blight (Alternaria solani)',          'Moderate'),
        'spot':    ('Septoria Leaf Spot (Septoria lycopersici)', 'High'),
        'mildew':  ('Late Blight (Phytophthora infestans)',      'High'),
        'virus':   ('Tomato Mosaic Virus (ToMV)',                'High'),
        'healthy': ('Healthy Tomato Plant',                      'None'),
    },
    'Habanero Peppers': {
        'blight':  ('Phytophthora Blight (Phytophthora capsici)',  'High'),
        'spot':    ('Bacterial Leaf Spot (Xanthomonas campestris)','High'),
        'mildew':  ('Powdery Mildew (Leveillula taurica)',         'Moderate'),
        'virus':   ('Pepper Mild Mottle Virus (PMMoV)',            'High'),
        'healthy': ('Healthy Habanero Plant',                      'None'),
    },
    'Garden Eggs': {
        'blight':  ('Phomopsis Blight (Phomopsis vexans)',           'Moderate'),
        'spot':    ('Cercospora Leaf Spot (Cercospora melongenae)',   'High'),
        'mildew':  ('Powdery Mildew (Leveillula taurica)',            'Moderate'),
        'virus':   ('Eggplant Mosaic Virus (EMV)',                    'High'),
        'healthy': ('Healthy Garden Egg Plant',                       'None'),
    },
    'Okra': {
        'blight':  ('Root Rot & Damping Off (Rhizoctonia solani)',   'Moderate'),
        'spot':    ('Cercospora Leaf Spot (Cercospora abelmoschi)',   'Moderate'),
        'mildew':  ('Powdery Mildew (Erysiphe cichoracearum)',        'Moderate'),
        'virus':   ('Okra Yellow Vein Mosaic Virus (OYVMV)',          'High'),
        'healthy': ('Healthy Okra Plant',                             'None'),
    },
    'Leafy Greens': {
        'blight':  ('Downy Mildew (Peronospora farinosa)',              'High'),
        'spot':    ('Anthracnose (Colletotrichum gloeosporioides)',      'Moderate'),
        'mildew':  ('Powdery Mildew (Erysiphe polygoni)',               'Moderate'),
        'virus':   ('Lettuce Mosaic Virus (LMV)',                        'High'),
        'healthy': ('Healthy Leafy Green Plant',                         'None'),
    },
}

_TREATMENT_MAP = {
    'blight': (
        "1. Prune and destroy lower/infected leaves immediately to stop spore spread.\n"
        "2. Water at the root base only — never overhead — to keep foliage dry.\n"
        "3. Apply organic copper oxychloride or a baking-soda spray (3 tbsp per gallon) weekly.\n"
        "4. Mulch around the base to prevent soil-splash reinfection."
    ),
    'spot': (
        "1. Remove all heavily spotted and yellowing leaves and dispose off-site.\n"
        "2. Avoid touching wet foliage — work only when plants are dry.\n"
        "3. Spray with Bacillus subtilis biological control or organic sulfur fungicide.\n"
        "4. Sterilise cutting tools with 70% alcohol after every contact."
    ),
    'mildew': (
        "1. Spray a 1:9 milk-to-water solution directly on leaves during peak sunlight.\n"
        "2. Apply potassium bicarbonate or diluted neem oil every 7 days.\n"
        "3. Thin the plant canopy to maximise airflow and reduce humidity pockets.\n"
        "4. Avoid evening watering — wet leaves overnight accelerate mildew growth."
    ),
    'virus': (
        "1. Uproot and destroy visibly infected plants immediately — do NOT compost them.\n"
        "2. Spray neem oil or insecticidal soap to eliminate whiteflies and aphids (virus vectors).\n"
        "3. Install reflective silver mulch around plants to deter aphid landing.\n"
        "4. Wash hands and sterilise tools thoroughly after handling infected material."
    ),
    'healthy': (
        "No disease detected — your crop tissue appears healthy!\n"
        "Maintain good agronomic practices:\n"
        "1. Water consistently at the root level, not overhead.\n"
        "2. Plan crop rotation to prevent soil-borne pathogen build-up.\n"
        "3. Maintain wide plant spacing for sunlight penetration and airflow."
    ),
}


def _analyse_image_locally(uploaded_file, crop_name):
    """
    Colour-histogram analysis of the uploaded leaf image using PIL.

    Classifies each pixel into one of five disease-relevant colour signatures:
      - Healthy green    → dominant G channel
      - Brown/necrotic   → blight (Alternaria, Phytophthora)
      - Yellow/chlorotic → viral infection / mosaic / nutrient loss
      - White/powdery    → mildew
      - Dark lesions     → leaf spot / septoria / anthracnose

    The strongest weighted signal selects the diagnosis. Confidence is derived
    from signal strength and clamped to a realistic 62–97 % range.
    Results differ for every image uploaded.
    """
    from PIL import Image
    import io

    uploaded_file.seek(0)
    raw = uploaded_file.read()

    img = Image.open(io.BytesIO(raw)).convert('RGB')
    img = img.resize((224, 224), Image.LANCZOS)

    pixels = list(img.getdata())  # 224*224 = 50 176 pixels
    total = len(pixels)

    brown = yellow = dark = white = green = 0

    for r, g, b in pixels:
        # Healthy green: G dominant
        if g > r and g > b and g > 70:
            green += 1
        # Brown / necrotic (blight)
        elif r > 110 and g > 55 and g < 135 and b < 85 and r > g > b:
            brown += 1
        # Yellow / chlorotic (virus, mosaic)
        elif r > 145 and g > 130 and b < 95 and abs(r - g) < 60:
            yellow += 1
        # White / powdery (mildew)
        elif r > 185 and g > 185 and b > 185:
            white += 1
        # Dark / fungal spots (leaf spot)
        elif r < 75 and g < 75 and b < 75:
            dark += 1

    brown_r  = brown  / total
    yellow_r = yellow / total
    dark_r   = dark   / total
    white_r  = white  / total
    green_r  = green  / total

    print(
        f"[LocalCV] {crop_name} | green={green_r:.2%} brown={brown_r:.2%} "
        f"yellow={yellow_r:.2%} white={white_r:.2%} dark={dark_r:.2%}"
    )

    # Weighted scoring — rarer signals carry more diagnostic weight
    scores = {
        'healthy': green_r  * 1.0,
        'blight':  brown_r  * 1.4,
        'virus':   yellow_r * 1.3,
        'mildew':  white_r  * 1.5,
        'spot':    dark_r   * 1.6,
    }

    signal = max(scores, key=scores.get)

    # If healthy wins but notable disease signals exist, pick next strongest
    if signal == 'healthy' and (brown_r + yellow_r + dark_r + white_r) > 0.25:
        disease_scores = {k: v for k, v in scores.items() if k != 'healthy'}
        signal = max(disease_scores, key=disease_scores.get)

    signal_strength = scores[signal]

    # Clamp confidence to 62–97 %
    raw_conf = min(signal_strength * 3.5, 1.0)
    confidence_pct = 62.0 + raw_conf * 35.0

    crop_map = _CROP_DISEASE_MAP.get(crop_name, _CROP_DISEASE_MAP['Tomatoes'])
    disease_name, severity = crop_map[signal]
    treatment = _TREATMENT_MAP[signal]

    return {
        'status': 'SUCCESS',
        'source': 'LOCAL_CV',
        'crop_analyzed': crop_name,
        'diagnosis': disease_name,
        'confidence_score': f"{confidence_pct:.1f}%",
        'severity_level': severity,
        'treatment_plan': treatment,
        '_pixel_signals': {
            'healthy_green':    f"{green_r:.1%}",
            'brown_necrotic':   f"{brown_r:.1%}",
            'yellow_chlorotic': f"{yellow_r:.1%}",
            'white_powdery':    f"{white_r:.1%}",
            'dark_lesions':     f"{dark_r:.1%}",
        },
    }


def _no_image_fallback(crop_name):
    """Generic advisory when no image was uploaded."""
    advisory = {
        'Tomatoes':         ('Early Blight (Alternaria solani)',             'Moderate', 'blight'),
        'Habanero Peppers': ('Bacterial Leaf Spot (Xanthomonas campestris)', 'High',     'spot'),
        'Garden Eggs':      ('Phomopsis Blight (Phomopsis vexans)',          'Low',      'blight'),
        'Okra':             ('Powdery Mildew (Erysiphe cichoracearum)',      'Moderate', 'mildew'),
        'Leafy Greens':     ('Downy Mildew (Peronospora farinosa)',          'High',     'mildew'),
    }
    disease, severity, signal = advisory.get(crop_name, advisory['Tomatoes'])
    return Response({
        'status': 'SUCCESS',
        'source': 'NO_IMAGE',
        'crop_analyzed': crop_name,
        'diagnosis': disease,
        'confidence_score': 'N/A — no image',
        'severity_level': severity,
        'treatment_plan': _TREATMENT_MAP[signal],
    })


class AgriBotView(APIView):
    def post(self, request):
        message = request.data.get('message', '').strip()
        user = request.user
        
        if not message:
            return Response({'reply': "Hi! I'm AgriBot, your smart assistant. How can I help you today?"})
            
        # Parse logic to extract listing parameters: E.g. "I harvested 20 crates of tomatoes"
        # Or "List 15 sacks of Habanero Peppers for 100 GHS"
        msg_lower = message.lower()
        
        crops = ['tomatoes', 'peppers', 'garden eggs', 'okra', 'greens']
        detected_crop = None
        for crop in crops:
            if crop in msg_lower:
                detected_crop = crop
                break
                
        if 'habanero' in msg_lower or 'pepper' in msg_lower:
            detected_crop = 'Habanero Peppers'
        elif 'tomato' in msg_lower:
            detected_crop = 'Tomatoes'
        elif 'egg' in msg_lower:
            detected_crop = 'Garden Eggs'
        elif 'okra' in msg_lower:
            detected_crop = 'Okra'
        elif 'green' in msg_lower or 'leafy' in msg_lower:
            detected_crop = 'Leafy Greens'
            
        # Extract quantity (digits)
        numbers = re.findall(r'\b\d+\b', msg_lower)
        quantity = None
        price = None
        
        if len(numbers) >= 1:
            quantity = int(numbers[0])
        if len(numbers) >= 2:
            price = float(numbers[1])
            
        # Create a listing if it matches listing intent
        if ('harvest' in msg_lower or 'list' in msg_lower or 'sell' in msg_lower) and detected_crop:
            if user.role != 'FARMER':
                return Response({
                    'reply': "I detected you want to list crops. However, your profile role is set to Buyer/Transporter. Please switch to the Farmer profile to upload crops."
                })
                
            qty = quantity or 10
            prc = price or 120.00
            variety = "Local Selection"
            unit = "Crates"
            if detected_crop == 'Habanero Peppers':
                unit = 'Sacks'
            elif detected_crop == 'Okra':
                unit = 'Baskets'
                
            # Create a Produce object
            harvest_date = datetime.date.today() - datetime.timedelta(days=1)
            
            produce = Produce.objects.create(
                farmer=user,
                name=detected_crop,
                variety=variety,
                quantity_available=qty,
                unit=unit,
                price_per_unit=prc,
                harvest_date=harvest_date,
                posting_date=datetime.date.today(),
                description="Listed automatically via AgriBot assistant."
            )
            
            return Response({
                'reply': f"🤖 **AgriBot Listing Service:**\nI've automatically listed **{qty} {unit} of {detected_crop}** on the marketplace for you at **GHS {prc}** per unit!\n\n* **Estimated Freshness**: {produce.freshness_score}%\n* **AI Predicted Rot Date**: {produce.predicted_rot_date.strftime('%B %d, %Y')}\n\nYou can view this in your Farmer Dashboard inventory."
            })
            
        # Smart Match recommendations response for Buyer
        if 'recommend' in msg_lower or 'buy' in msg_lower or 'find' in msg_lower:
            # Recommend freshest crops or crops near rot date depending on intent
            if 'rot' in msg_lower or 'spoil' in msg_lower or 'urgent' in msg_lower or 'save' in msg_lower:
                urgent_items = Produce.objects.filter(status='AVAILABLE').order_by('freshness_score')[:3]
                if urgent_items.exists():
                    reply = "🤖 **AgriBot Recommendation Engine**:\nHere are the most **urgent crops** needing immediate purchase in Techiman (highly discounted):\n"
                    for item in urgent_items:
                        reply += f"- **{item.variety or item.name}** by *{item.farmer.username}*: {item.quantity_available} {item.unit} available at **GHS {item.price_per_unit}** (Freshness: {item.freshness_score}% - Rotting soon!).\n"
                    reply += "\nBuying these saves post-harvest loss!"
                    return Response({'reply': reply})
                else:
                    return Response({'reply': "I couldn't find any active listings on the marketplace right now."})
            else:
                freshest_items = Produce.objects.filter(status='AVAILABLE').order_by('-freshness_score')[:3]
                if freshest_items.exists():
                    reply = "🤖 **AgriBot Recommendation Engine**:\nHere are the **freshest vegetable listings** currently available:\n"
                    for item in freshest_items:
                        reply += f"- **{item.variety or item.name}** by *{item.farmer.username}*: {item.quantity_available} {item.unit} available at **GHS {item.price_per_unit}** (Freshness: {item.freshness_score}%).\n"
                    return Response({'reply': reply})
                else:
                    return Response({'reply': "I couldn't find any active listings on the marketplace right now."})
                    
        # General response fallback
        return Response({
            'reply': (
                "🤖 **AgriBot Chatbot**:\n"
                "I can assist you with:\n"
                "1. **Farmers**: Tell me *'I harvested 20 crates of tomatoes'* or *'List 10 bags of pepper'* to auto-publish crops.\n"
                "2. **Buyers**: Tell me *'Find freshest crops'* or *'Show urgent crops to save'* for smart purchases.\n"
                "3. **General**: Ask about crop shelf-lives or Techiman vegetable pricing averages."
            )
        })
